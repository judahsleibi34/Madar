from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document as WordDocument
from fastapi import UploadFile
from pypdf import PdfWriter

from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.document_extraction.extractors import extract_document
from app.services.document_storage.local import LocalDocumentStorage


@pytest.mark.asyncio
async def test_txt_is_streamed_validated_and_committed() -> None:
    storage = LocalDocumentStorage(get_settings())
    staged = await storage.stage(UploadFile(filename="candidate.txt", file=BytesIO(b"hello cv")))
    key = storage.commit(staged, __import__("uuid").uuid4())
    try:
        assert storage.path(key).read_bytes() == b"hello cv"
        assert staged.sha256
    finally:
        storage.delete(key)


@pytest.mark.asyncio
async def test_path_like_filename_is_rejected() -> None:
    storage = LocalDocumentStorage(get_settings())
    with pytest.raises(ApiError) as captured:
        await storage.stage(UploadFile(filename="../candidate.txt", file=BytesIO(b"hello")))
    assert captured.value.code == "INVALID_FILENAME"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("empty.txt", b"", "EMPTY_FILE"),
        ("candidate.exe", b"not executable", "UNSUPPORTED_FILE_TYPE"),
        ("fake.pdf", b"not a pdf", "INVALID_PDF"),
        ("fake.docx", b"not a docx", "INVALID_DOCX"),
        ("binary.txt", b"text" + bytes([0]) + b"binary", "INVALID_TEXT"),
    ],
)
async def test_invalid_uploads_are_rejected(filename: str, content: bytes, code: str) -> None:
    storage = LocalDocumentStorage(get_settings())
    with pytest.raises(ApiError) as captured:
        await storage.stage(UploadFile(filename=filename, file=BytesIO(content)))
    assert captured.value.code == code


@pytest.mark.asyncio
async def test_valid_pdf_and_docx_are_staged_and_extracted() -> None:
    storage = LocalDocumentStorage(get_settings())
    pdf_buffer = BytesIO()
    pdf_writer = PdfWriter()
    pdf_writer.add_blank_page(width=612, height=792)
    pdf_writer.write(pdf_buffer)
    pdf_buffer.seek(0)
    pdf = await storage.stage(UploadFile(filename="candidate.pdf", file=pdf_buffer))

    docx_buffer = BytesIO()
    document = WordDocument()
    document.add_paragraph("Python FastAPI candidate")
    document.save(docx_buffer)
    docx_buffer.seek(0)
    docx = await storage.stage(UploadFile(filename="candidate.docx", file=docx_buffer))
    try:
        pdf_result = extract_document(pdf.path, pdf.mime_type)
        assert pdf_result.page_count == 1
        assert pdf_result.warnings == ["Page 1 contained no extractable text."]
        assert extract_document(docx.path, docx.mime_type).text == "Python FastAPI candidate"
    finally:
        storage.discard(pdf)
        storage.discard(docx)


@pytest.mark.asyncio
async def test_encrypted_pdf_is_rejected() -> None:
    storage = LocalDocumentStorage(get_settings())
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    writer.write(buffer)
    buffer.seek(0)
    with pytest.raises(ApiError) as captured:
        await storage.stage(UploadFile(filename="encrypted.pdf", file=buffer))
    assert captured.value.code == "ENCRYPTED_PDF"
