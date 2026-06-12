import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from data_analysis import services as data_services
from data_analysis.routes.data_routes import get_storage_scope


router = APIRouter(
    prefix="/users/{user_id}/visualization",
    tags=["Visualization"],
)
logger = logging.getLogger(__name__)


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
