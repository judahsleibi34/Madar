from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from data_analysis.data_reading import DataReadingNormal
from data_analysis.response_utils import dataframe_preview, sanitize_for_json


router = APIRouter(
    prefix="/data",
    tags=["Data"]
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class ReadDataRequest(BaseModel):
    input_path: str


@router.post("/read")
def read_data(request: ReadDataRequest):
    try:
        reader = DataReadingNormal(request.input_path)
        df = reader.read()

        return {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": dataframe_preview(df, 10)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload_data(file: UploadFile = File(...)):
    try:
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in [".csv", ".xls", ".xlsx"]:
            raise HTTPException(
                status_code=400,
                detail="Only .csv, .xls, and .xlsx files are supported"
            )

        unique_filename = f"{uuid4().hex}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename

        content = await file.read()
        file_path.write_bytes(content)

        reader = DataReadingNormal(str(file_path))
        df = reader.read()

        return {
            "file_path": str(file_path),
            "original_filename": file.filename,
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": dataframe_preview(df, 10)
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=400, detail=sanitize_for_json(str(e)))

