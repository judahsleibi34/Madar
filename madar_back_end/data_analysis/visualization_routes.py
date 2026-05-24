from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_analysis.data_cleaning import DataCleaning
from data_analysis.visualization import DataVisualization
from data_analysis.response_utils import sanitize_for_json


router = APIRouter(
    prefix="/visualization",
    tags=["Visualization"]
)


class VisualizationRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    chart_config: dict[str, Any]


@router.post("/create")
def create_visualization(request: VisualizationRequest):
    try:
        cleaner = DataCleaning(request.input_path)

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

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

