from pathlib import Path
from uuid import uuid4
import os
import re

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File
from pydantic import BaseModel

from data_analysis.io.data_reading import DataReadingNormal
from data_analysis.core.response_utils import dataframe_preview, sanitize_for_json
from services.auth_service import get_authenticated_user_row


router = APIRouter(
    prefix="/data",
    tags=["Data"]
)


UPLOAD_DIR = Path(os.getenv("DATA_UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


PREVIEW_LIMIT = 100
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
UPLOAD_CHUNK_SIZE = 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xls", ".xlsx"}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


class ReadDataRequest(BaseModel):
    input_path: str


def get_storage_scope(request: Request, response: Response) -> tuple[str, str]:
    _, user_data = get_authenticated_user_row(request, response)
    tenant_id = user_data.get("tenant_id")
    user_id = user_data.get("id")

    if tenant_id is None or user_id is None:
        raise HTTPException(status_code=400, detail="User storage scope is not available.")

    return safe_scope_value(tenant_id), safe_scope_value(user_id)


def safe_scope_value(value: object) -> str:
    text = str(value).strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise HTTPException(status_code=400, detail="Invalid user storage scope.")

    return text


def get_user_upload_dir(tenant_id: str, user_id: str) -> Path:
    scoped_dir = UPLOAD_DIR / f"tenant_{tenant_id}" / f"user_{user_id}"
    scoped_dir.mkdir(parents=True, exist_ok=True)
    return scoped_dir


def validate_upload_filename(filename: str) -> str:
    clean_filename = (filename or "").strip()

    if (
        not clean_filename
        or "\x00" in clean_filename
        or "/" in clean_filename
        or "\\" in clean_filename
        or Path(clean_filename).name != clean_filename
        or ".." in Path(clean_filename).parts
    ):
        raise HTTPException(status_code=400, detail="Invalid upload filename.")

    extension = Path(clean_filename).suffix.lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .xls, and .xlsx files are supported.",
        )

    return extension


def validate_upload_content_type(content_type: str | None) -> None:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()

    if normalized not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported upload content type.",
        )


async def read_limited_upload(file: UploadFile) -> bytes:
    content = bytearray()

    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)

        if not chunk:
            break

        content.extend(chunk)

        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Uploaded file is too large.",
            )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    return bytes(content)


def build_dataset_response(df, *, file_path: str, original_filename: str | None = None):
    return {
        "file_path": file_path,
        "original_filename": original_filename or file_path,
        "rows": int(len(df)),
        "columns": [sanitize_for_json(column) for column in df.columns],
        "preview": dataframe_preview(df, PREVIEW_LIMIT),
    }


@router.post("/read")
def read_data(
    request: ReadDataRequest,
    fastapi_request: Request,
    response: Response,
):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        reader = DataReadingNormal(request.input_path, tenant_id=tenant_id, user_id=user_id)
        df = reader.read()

        return build_dataset_response(
            df,
            file_path=request.input_path,
            original_filename=request.input_path,
        )

    except HTTPException:
        raise

    except Exception as error:
        print("DATA READ ERROR:", type(error).__name__)
        raise HTTPException(
            status_code=400,
            detail="Could not read data file.",
        )


@router.post("/upload")
async def upload_data(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    try:
        filename = file.filename or ""
        file_extension = validate_upload_filename(filename)
        validate_upload_content_type(file.content_type)
        content = await read_limited_upload(file)
        tenant_id, user_id = get_storage_scope(request, response)

        unique_filename = f"{uuid4().hex}{file_extension}"
        file_path = get_user_upload_dir(tenant_id, user_id) / unique_filename
        file_path.write_bytes(content)

        reader = DataReadingNormal(str(file_path), tenant_id=tenant_id, user_id=user_id)
        df = reader.read()

        return build_dataset_response(
            df,
            file_path=str(file_path),
            original_filename=filename,
        )

    except HTTPException:
        raise

    except Exception as error:
        print("DATA UPLOAD ERROR:", type(error).__name__)
        raise HTTPException(
            status_code=400,
            detail="Could not process uploaded data file.",
        )
