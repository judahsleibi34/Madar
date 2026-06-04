from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from data_analysis.cleaning.data_cleaning import DataCleaning
from data_analysis.visualization.visualization import DataVisualization
from data_analysis.core.response_utils import sanitize_for_json
from data_analysis.routes.data_routes import get_storage_scope


router = APIRouter(
    prefix="/visualization",
    tags=["Visualization"]
)


class VisualizationRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    chart_config: dict[str, Any]


@router.post("/create")
def create_visualization(request: VisualizationRequest, fastapi_request: Request, response: Response):
    try:
        tenant_id, user_id = get_storage_scope(fastapi_request, response)
        cleaner = DataCleaning(request.input_path, tenant_id=tenant_id, user_id=user_id)

        if request.cleaning_actions:
            df = cleaner.apply_pipeline(request.cleaning_actions)
        else:
            df = cleaner.read()

        visualizer = DataVisualization(df)
        chart_path = visualizer.plot(**request.chart_config)

        return sanitize_for_json({
            "chart_path": chart_path,
            "rows_used": int(len(df)),
            "columns_used": list(df.columns)
        })

    except HTTPException:
        raise

    except Exception as error:
        print("VISUALIZATION CREATE ERROR:", type(error).__name__)
        raise HTTPException(status_code=400, detail="Could not create visualization.")

