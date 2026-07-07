import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from data_analysis import services as data_services
from data_analysis.routes.data_routes import get_storage_scope
from services.rate_limit_service import (
    enforce_data_workspace_rate_limit,
    enforce_visualization_generation_rate_limit,
)


router = APIRouter(
    prefix="/users/{user_id}/visualization",
    tags=["Visualization"],
)
logger = logging.getLogger(__name__)

CHART_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".html": "text/html; charset=utf-8",
}

PRIVATE_FILE_SECURITY_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
PRIVATE_HTML_SECURITY_HEADERS = {
    **PRIVATE_FILE_SECURITY_HEADERS,
    "Content-Security-Policy": (
        "default-src 'none'; "
        "img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'; "
        "sandbox"
    ),
    "X-Frame-Options": "DENY",
}


class VisualizationRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    chart_config: dict[str, Any]


class VisualizationColumnProfileRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    columns: list[str] = []


@router.post("/columns/profile")
def profile_visualization_columns(user_id: int, request: VisualizationColumnProfileRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "visualization_profile",
            tenant_id=tenant_id,
        )
        return data_services.profile_visualization_columns(
            input_path=request.input_path,
            cleaning_actions=request.cleaning_actions,
            columns=request.columns,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.visualization.profile_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not inspect the selected fields for visualization.")


@router.post("/create")
def create_visualization(user_id: int, request: VisualizationRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_visualization_generation_rate_limit(
            fastapi_request,
            scoped_user_id,
            tenant_id=tenant_id,
        )
        return data_services.create_visualization(
            input_path=request.input_path,
            cleaning_actions=request.cleaning_actions,
            chart_config=request.chart_config,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.visualization.create_failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not create the visualization. Please check the selected fields and chart type.")


@router.get("/charts/{chart_id:path}")
def get_private_chart(user_id: int, chart_id: str, fastapi_request: Request, response: Response):
    tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
    chart_path = data_services.resolve_private_chart_path(
        chart_id,
        tenant_id=tenant_id,
        user_id=scoped_user_id,
    )
    media_type = CHART_MEDIA_TYPES.get(Path(chart_path).suffix.lower(), "application/octet-stream")
    headers = (
        PRIVATE_HTML_SECURITY_HEADERS
        if Path(chart_path).suffix.lower() == ".html"
        else PRIVATE_FILE_SECURITY_HEADERS
    )
    return FileResponse(
        path=str(chart_path),
        media_type=media_type,
        filename=Path(chart_path).name,
        content_disposition_type="attachment",
        headers=headers,
    )
