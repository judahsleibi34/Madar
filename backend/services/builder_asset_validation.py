from __future__ import annotations

from pathlib import Path
import zipfile

import olefile


DOCX_REQUIRED_ENTRIES = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
}
DOCX_MAX_ENTRIES = 2048
DOCX_MAX_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
DOCX_MAX_ENTRY_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
DOCX_MAX_COMPRESSION_RATIO = 200


class BuilderAssetValidationError(ValueError):
    pass


def detect_builder_asset_content_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "video/mp4"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    if content.startswith(b"PK\x03\x04"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return None


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as source:
        if not source.read(8).startswith(b"%PDF-"):
            raise BuilderAssetValidationError("builder_asset_pdf_invalid")
        source.seek(max(0, path.stat().st_size - 4096))
        if b"%%EOF" not in source.read(4096):
            raise BuilderAssetValidationError("builder_asset_pdf_invalid")


def _validate_docx(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > DOCX_MAX_ENTRIES:
                raise BuilderAssetValidationError("builder_asset_docx_invalid")

            names = {entry.filename.replace("\\", "/") for entry in entries}
            if not DOCX_REQUIRED_ENTRIES.issubset(names):
                raise BuilderAssetValidationError("builder_asset_docx_invalid")

            total_uncompressed = 0
            for entry in entries:
                normalized_name = entry.filename.replace("\\", "/")
                if (
                    normalized_name.startswith("/")
                    or normalized_name.startswith("../")
                    or "/../" in normalized_name
                    or entry.flag_bits & 0x1
                ):
                    raise BuilderAssetValidationError("builder_asset_docx_invalid")
                if entry.file_size > DOCX_MAX_ENTRY_UNCOMPRESSED_BYTES:
                    raise BuilderAssetValidationError("builder_asset_docx_too_complex")
                total_uncompressed += entry.file_size
                if total_uncompressed > DOCX_MAX_TOTAL_UNCOMPRESSED_BYTES:
                    raise BuilderAssetValidationError("builder_asset_docx_too_complex")
                if entry.file_size and (
                    entry.compress_size <= 0
                    or entry.file_size / entry.compress_size > DOCX_MAX_COMPRESSION_RATIO
                ):
                    raise BuilderAssetValidationError("builder_asset_docx_too_complex")

            content_types = archive.getinfo("[Content_Types].xml")
            if content_types.file_size > 1024 * 1024:
                raise BuilderAssetValidationError("builder_asset_docx_too_complex")
            content_type_xml = archive.read(content_types)
            if b"wordprocessingml.document" not in content_type_xml:
                raise BuilderAssetValidationError("builder_asset_docx_invalid")
    except (zipfile.BadZipFile, KeyError, OSError) as error:
        raise BuilderAssetValidationError("builder_asset_docx_invalid") from error


def _validate_doc(path: Path) -> None:
    try:
        if not olefile.isOleFile(path):
            raise BuilderAssetValidationError("builder_asset_doc_invalid")
        with olefile.OleFileIO(path) as document:
            streams = {"/".join(parts) for parts in document.listdir(streams=True, storages=False)}
            if "WordDocument" not in streams or not ({"0Table", "1Table"} & streams):
                raise BuilderAssetValidationError("builder_asset_doc_invalid")
    except (OSError, TypeError, ValueError) as error:
        raise BuilderAssetValidationError("builder_asset_doc_invalid") from error


def validate_builder_asset_file(path: Path, content_type: str) -> None:
    if content_type == "application/pdf":
        _validate_pdf(path)
    elif content_type == "application/msword":
        _validate_doc(path)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        _validate_docx(path)
