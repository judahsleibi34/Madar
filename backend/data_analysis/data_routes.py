from pathlib import Path
from uuid import uuid4
import os

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from data_analysis.data_reading import DataReadingNormal
from data_analysis.response_utils import dataframe_preview, sanitize_for_json


router = APIRouter(
    prefix="/data",
    tags=["Data"]
)


UPLOAD_DIR = Path(os.getenv("DATA_UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


PREVIEW_LIMIT = 100
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))


class ReadDataRequest(BaseModel):
    input_path: str


def build_dataset_response(df, *, file_path: str, original_filename: str | None = None):
    return {
        "file_path": file_path,
        "original_filename": original_filename or file_path,
        "rows": int(len(df)),
        "columns": [sanitize_for_json(column) for column in df.columns],
        "preview": dataframe_preview(df, PREVIEW_LIMIT),
    }


@router.post("/read")
def read_data(request: ReadDataRequest):
    try:
        reader = DataReadingNormal(request.input_path)
        df = reader.read()

        return build_dataset_response(
            df,
            file_path=request.input_path,
            original_filename=request.input_path,
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=sanitize_for_json(str(e)),
        )


@router.post("/upload")
async def upload_data(file: UploadFile = File(...)):
    try:
        filename = file.filename or ""
        file_extension = Path(filename).suffix.lower()

        if file_extension not in [".csv", ".xls", ".xlsx"]:
            raise HTTPException(
                status_code=400,
                detail="Only .csv, .xls, and .xlsx files are supported",
            )

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Uploaded file is too large",
            )

        unique_filename = f"{uuid4().hex}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        file_path.write_bytes(content)

        reader = DataReadingNormal(str(file_path))
        df = reader.read()

        return build_dataset_response(
            df,
            file_path=str(file_path),
            original_filename=filename,
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=sanitize_for_json(str(e)),
        )
