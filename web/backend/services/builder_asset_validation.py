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
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav"
    if content.startswith(b"ID3") or (len(content) >= 4 and content[0] == 0xff and content[1] & 0xe0 == 0xe0):
        return "audio/mpeg"
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
    if content_type in {"audio/mpeg", "audio/wav"}:
        _validate_audio(path, content_type)
    elif content_type == "application/pdf":
        _validate_pdf(path)
    elif content_type == "application/msword":
        _validate_doc(path)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        _validate_docx(path)


def _validate_audio(path: Path, content_type: str) -> None:
    if content_type == 'audio/wav':
        import wave
        try:
            with wave.open(str(path), 'rb') as audio:
                if not 1 <= audio.getnchannels() <= 8 or not 8000 <= audio.getframerate() <= 192000 or audio.getnframes() < 1:
                    raise BuilderAssetValidationError('builder_asset_audio_invalid')
                expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
                actual = 0
                while chunk := audio.readframes(8192):
                    actual += len(chunk)
                if actual != expected:
                    raise BuilderAssetValidationError('builder_asset_audio_truncated')
        except (wave.Error, EOFError, OSError) as error:
            raise BuilderAssetValidationError('builder_asset_audio_invalid') from error
        return
    # MPEG Layer III frame validation; do not accept an ID3 signature alone.
    with path.open('rb') as source:
        size = path.stat().st_size
        header = source.read(10)
        offset = 0
        if header[:3] == b'ID3':
            if len(header) < 10 or any(value & 0x80 for value in header[6:10]):
                raise BuilderAssetValidationError('builder_asset_audio_invalid')
            offset = 10 + sum(value << shift for value, shift in zip(header[6:10], (21, 14, 7, 0)))
            if header[5] & 0x10: offset += 10
        frames = 0
        while offset + 4 <= size:
            source.seek(offset)
            header = source.read(4)
            if header[:3] == b'TAG' and size - offset == 128: break
            bits = int.from_bytes(header, 'big')
            version, layer = (bits >> 19) & 3, (bits >> 17) & 3
            bitrate_index, rate_index = (bits >> 12) & 15, (bits >> 10) & 3
            if bits >> 21 != 0x7ff or version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
                raise BuilderAssetValidationError('builder_asset_audio_invalid')
            rates = (44100, 48000, 32000)
            rate = rates[rate_index] // (1 if version == 3 else 2 if version == 2 else 4)
            bitrates = (0,32,40,48,56,64,80,96,112,128,160,192,224,256,320) if version == 3 else (0,8,16,24,32,40,48,56,64,80,96,112,128,144,160)
            length = (144 if version == 3 else 72) * bitrates[bitrate_index] * 1000 // rate + ((bits >> 9) & 1)
            if offset + length > size:
                raise BuilderAssetValidationError('builder_asset_audio_truncated')
            offset += length
            frames += 1
        if not frames or (offset != size and size - offset != 128):
            raise BuilderAssetValidationError('builder_asset_audio_invalid')
