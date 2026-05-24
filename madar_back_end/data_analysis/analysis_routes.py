from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_analysis.data_cleaning import DataCleaning
from data_analysis.analysis_router import AnalysisRouter
from data_analysis.response_utils import sanitize_for_json


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)


class AnalysisRunRequest(BaseModel):
    input_path: str
    cleaning_actions: list[dict[str, Any]] = []
    analysis_requests: list[dict[str, Any]]


@router.post("/run")
def run_analysis(request: AnalysisRunRequest):
    try:
        cleaner = DataCleaning(request.input_path)

        if request.cleaning_actions:
            df = cleaner.apply_pipeline(request.cleaning_actions)
        else:
            df = cleaner.read()

        analysis_router = AnalysisRouter(df)
        results = analysis_router.run(request.analysis_requests)

        return sanitize_for_json({
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
            "results": results
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

