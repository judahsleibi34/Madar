from __future__ import annotations

import hashlib
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from pypdf import PdfReader

from app.core.config import Settings
from app.core.errors import ApiError

_ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


@dataclass(frozen=True)
class StagedFile:
    path: Path
    sha256: str
    size: int
    filename: str
    mime_type: str


class LocalDocumentStorage:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.upload_directory.resolve()
        self.temp = settings.temp_directory.resolve()
        self.max_bytes = settings.max_file_size_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        self.temp.mkdir(parents=True, exist_ok=True)

    async def stage(self, upload: UploadFile) -> StagedFile:
        original = upload.filename or ""
        if (
            not original
            or Path(original).name != original
            or ".." in original
            or "/" in original
            or "\\" in original
        ):
            raise ApiError(422, "INVALID_FILENAME", "The uploaded filename is not allowed.")
        suffix = Path(original).suffix.lower()
        if suffix not in _ALLOWED:
            raise ApiError(
                415, "UNSUPPORTED_FILE_TYPE", "Only PDF, DOCX, and TXT files are supported."
            )
        filename = _SAFE.sub("_", original).strip(" .")[:255]
        if not filename:
            raise ApiError(422, "INVALID_FILENAME", "The uploaded filename is not allowed.")

        path = self.temp / f"{uuid.uuid4()}.upload"
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("xb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ApiError(
                            413, "FILE_TOO_LARGE", "An uploaded file exceeds the configured limit."
                        )
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if size == 0:
                raise ApiError(422, "EMPTY_FILE", "Empty files are not accepted.")
            self._validate(path, suffix)
            return StagedFile(path, digest.hexdigest(), size, filename, _ALLOWED[suffix])
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    def _validate(self, path: Path, suffix: str) -> None:
        header = path.read_bytes()[:8]
        if suffix == ".pdf":
            if not header.startswith(b"%PDF-"):
                raise ApiError(422, "INVALID_PDF", "The file is not a valid PDF.")
            try:
                if PdfReader(path).is_encrypted:
                    raise ApiError(
                        422, "ENCRYPTED_PDF", "Password-protected PDFs are not supported."
                    )
            except ApiError:
                raise
            except Exception as error:
                raise ApiError(422, "INVALID_PDF", "The file is not a valid PDF.") from error
        elif suffix == ".docx":
            if not header.startswith(b"PK"):
                raise ApiError(422, "INVALID_DOCX", "The file is not a valid DOCX document.")
            try:
                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                        raise ValueError
            except (OSError, zipfile.BadZipFile, ValueError) as error:
                raise ApiError(
                    422, "INVALID_DOCX", "The file is not a valid DOCX document."
                ) from error
        else:
            sample = path.read_bytes()[:65536]
            if b"\x00" in sample:
                raise ApiError(422, "INVALID_TEXT", "The TXT file appears to contain binary data.")
            try:
                sample.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ApiError(422, "INVALID_TEXT", "TXT files must use UTF-8 encoding.") from error

    def commit(self, staged: StagedFile, owner_id: uuid.UUID) -> str:
        key = f"{owner_id}/{staged.sha256[:2]}/{uuid.uuid4()}{Path(staged.filename).suffix.lower()}"
        destination = self._resolve(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged.path, destination)
        return key

    def discard(self, staged: StagedFile) -> None:
        staged.path.unlink(missing_ok=True)

    def open(self, key: str) -> BinaryIO:
        return self._resolve(key).open("rb")

    def path(self, key: str) -> Path:
        return self._resolve(key)

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ApiError(400, "INVALID_STORAGE_KEY", "The storage key is invalid.")
        return candidate
