import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from data_analysis import services as data_services
from data_analysis.routes.data_routes import get_storage_scope


router = APIRouter(
    prefix="/users/{user_id}/analysis",
    tags=["Analysis"],
)
logger = logging.getLogger(__name__)


class AnalysisRunRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    analysis_requests: list[dict[str, Any]]
    language: str = "en"
    symbols: dict[str, Any] = {}


class AssistedAnalysisRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    question: str | None = None
    metric: dict[str, Any] | None = None
    language: str = "en"
    symbols: dict[str, Any] = {}


@router.get("/catalog")
def analysis_catalog(user_id: int, fastapi_request: Request, response: Response, language: str = "en"):
    get_storage_scope(fastapi_request, response, user_id)
    return data_services.get_analysis_catalog(language)


@router.post("/run")
def run_analysis(user_id: int, request: AnalysisRunRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        return data_services.run_analysis(
            input_path=request.input_path,
            cleaning_actions=request.cleaning_actions,
            analysis_requests=request.analysis_requests,
            language=request.language,
            symbols=request.symbols,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.analysis.run_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not run analysis.")


@router.post("/assist")
def assisted_analysis(user_id: int, request: AssistedAnalysisRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        return data_services.run_assisted_analysis(
            input_path=request.input_path,
            cleaning_actions=request.cleaning_actions,
            question=request.question,
            metric=request.metric,
            language=request.language,
            symbols=request.symbols,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.analysis.assist_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not run assisted analysis.")
