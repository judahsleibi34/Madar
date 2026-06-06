from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from data_analysis.cleaning.data_cleaning import DataCleaning
from data_analysis.core.response_utils import dataframe_preview, sanitize_for_json
from data_analysis.routes.data_routes import get_storage_scope


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
def inspect_data(request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        return sanitize_for_json(cleaner.data_inspection())

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING INSPECT ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not inspect data.")


@router.post("/prepare-report")
def preparation_report(request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        return sanitize_for_json(cleaner.preparation_report())

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING PREPARE ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not prepare data report.")


@router.post("/statistics")
def statistical_inspection(request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        return sanitize_for_json(cleaner.statistical_inspection())

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING STATISTICS ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not calculate statistics.")


@router.post("/missing-report")
def missing_values_report(request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        return sanitize_for_json(cleaner.missing_values_report())

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING MISSING ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not calculate missing values.")


@router.post("/quality-report")
def quality_report(request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        return sanitize_for_json(cleaner.quality_report())

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING QUALITY ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not calculate quality report.")


@router.post("/column-types")
def column_types(request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        return sanitize_for_json(cleaner.column_types())

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING COLUMN TYPES ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not detect column types.")


@router.post("/apply")
def apply_cleaning(request: CleaningApplyRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)
        df = cleaner.apply_pipeline(request.actions)

        return {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": dataframe_preview(df, 20)
        }

    except HTTPException:
        raise

    except Exception as error:
        print("CLEANING APPLY ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not apply cleaning actions.")

