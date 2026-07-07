import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from data_analysis import services as data_services
from data_analysis.routes.data_routes import get_storage_scope
from services.rate_limit_service import enforce_data_workspace_rate_limit


router = APIRouter(
    prefix="/users/{user_id}/cleaning",
    tags=["Cleaning"],
)
logger = logging.getLogger(__name__)


class InputPathRequest(BaseModel):
    input_path: str


class CleaningApplyRequest(BaseModel):
    input_path: str
    actions: list[dict[str, Any]]


@router.post("/inspect")
def inspect_data(user_id: int, request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_inspect",
            tenant_id=tenant_id,
        )
        return data_services.inspect_dataset(request.input_path, tenant_id=tenant_id, user_id=scoped_user_id)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.inspect_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not inspect data.")


@router.post("/prepare-report")
def preparation_report(user_id: int, request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_prepare_report",
            tenant_id=tenant_id,
        )
        return data_services.preparation_report(request.input_path, tenant_id=tenant_id, user_id=scoped_user_id)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.prepare_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not prepare data report.")


@router.post("/statistics")
def statistical_inspection(user_id: int, request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_statistics",
            tenant_id=tenant_id,
        )
        return data_services.statistical_inspection(request.input_path, tenant_id=tenant_id, user_id=scoped_user_id)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.statistics_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not calculate statistics.")


@router.post("/missing-report")
def missing_values_report(user_id: int, request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_missing_report",
            tenant_id=tenant_id,
        )
        return data_services.missing_values_report(request.input_path, tenant_id=tenant_id, user_id=scoped_user_id)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.missing_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not calculate missing values.")


@router.post("/quality-report")
def quality_report(user_id: int, request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_quality_report",
            tenant_id=tenant_id,
        )
        return data_services.quality_report(request.input_path, tenant_id=tenant_id, user_id=scoped_user_id)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.quality_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not calculate quality report.")


@router.post("/column-types")
def column_types(user_id: int, request: InputPathRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_column_types",
            tenant_id=tenant_id,
        )
        return data_services.column_types(request.input_path, tenant_id=tenant_id, user_id=scoped_user_id)

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.column_types_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not detect column types.")


@router.post("/apply")
def apply_cleaning(user_id: int, request: CleaningApplyRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_apply",
            tenant_id=tenant_id,
        )
        return data_services.apply_cleaning(
            request.input_path,
            request.actions,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.apply_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not apply cleaning actions.")


@router.post("/export")
def export_cleaned_dataframe(user_id: int, request: CleaningApplyRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "cleaning_export",
            tenant_id=tenant_id,
        )
        return data_services.export_cleaned_dataframe(
            request.input_path,
            request.actions,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.cleaning.export_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not export cleaned data.")
