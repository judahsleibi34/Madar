from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_analysis.data_cleaning import DataCleaning
from data_analysis.response_utils import dataframe_preview, sanitize_for_json


router = APIRouter(
    prefix="/cleaning",
    tags=["Cleaning"]
)


class InputPathRequest(BaseModel):
    input_path: str


class CleaningApplyRequest(BaseModel):
    input_path: str
    actions: list[dict[str, Any]]


@router.post("/inspect")
def inspect_data(request: InputPathRequest):
    try:
        cleaner = DataCleaning(request.input_path)
        return sanitize_for_json(cleaner.data_inspection())

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/statistics")
def statistical_inspection(request: InputPathRequest):
    try:
        cleaner = DataCleaning(request.input_path)
        return sanitize_for_json(cleaner.statistical_inspection())

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/missing-report")
def missing_values_report(request: InputPathRequest):
    try:
        cleaner = DataCleaning(request.input_path)
        return sanitize_for_json(cleaner.missing_values_report())

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/quality-report")
def quality_report(request: InputPathRequest):
    try:
        cleaner = DataCleaning(request.input_path)
        return sanitize_for_json(cleaner.quality_report())

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/column-types")
def column_types(request: InputPathRequest):
    try:
        cleaner = DataCleaning(request.input_path)
        return sanitize_for_json(cleaner.column_types())

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/apply")
def apply_cleaning(request: CleaningApplyRequest):
    try:
        cleaner = DataCleaning(request.input_path)
        df = cleaner.apply_pipeline(request.actions)

        return {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": dataframe_preview(df, 20)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

