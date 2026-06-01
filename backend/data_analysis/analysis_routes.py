from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_analysis.data_cleaning import DataCleaning
from data_analysis.analysis_catalog import ANALYSIS_CATALOG
from data_analysis.analysis_i18n import direction_for, localized_catalog, normalize_language, normalize_symbols
from data_analysis.analysis_router import AnalysisRouter
from data_analysis.assisted_analysis import AssistedAnalysis
from data_analysis.response_utils import sanitize_for_json


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)


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
def analysis_catalog(language: str = "en"):
    language = normalize_language(language)
    symbols = normalize_symbols()
    return sanitize_for_json({
        "language": language,
        "direction": direction_for(language),
        "symbols": symbols,
        "domains": localized_catalog(ANALYSIS_CATALOG, language),
        "response_shape": {
            "report_id": "string",
            "domain": "string",
            "title": "string",
            "summary": "string",
            "insights": "string[]",
            "kpis": "metric[]",
            "tables": "table[]",
            "charts": "chart[]",
            "warnings": "string[]",
            "metadata": "object",
        },
    })


@router.post("/run")
def run_analysis(request: AnalysisRunRequest):
    try:
        cleaner = DataCleaning(request.input_path)

        if request.cleaning_actions:
            df = cleaner.apply_pipeline(request.cleaning_actions)
        else:
            df = cleaner.read()

        df, preparation_warnings = cleaner.prepare_dataframe(df)

        language = normalize_language(request.language)
        symbols = normalize_symbols(request.symbols)

        analysis_router = AnalysisRouter(df, language=language, symbols=symbols)
        results = analysis_router.run(request.analysis_requests)

        return sanitize_for_json({
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
            "warnings": preparation_warnings,
            "metadata": {
                "cleaning_actions_applied": request.cleaning_actions,
                "analysis_request_count": len(request.analysis_requests),
                "language": language,
                "direction": direction_for(language),
                "symbols": symbols,
                "profiles": cleaner.profile_dataframe(df),
            },
            "results": results
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assist")
def assisted_analysis(request: AssistedAnalysisRequest):
    try:
        cleaner = DataCleaning(request.input_path)

        if request.cleaning_actions:
            df = cleaner.apply_pipeline(request.cleaning_actions)
        else:
            df = cleaner.read()

        df, preparation_warnings = cleaner.prepare_dataframe(df)
        language = normalize_language(request.language)
        symbols = normalize_symbols(request.symbols)

        analyzer = AssistedAnalysis(df, language=language, symbols=symbols)
        result = analyzer.answer_question(question=request.question, metric=request.metric)

        return sanitize_for_json({
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
            "warnings": preparation_warnings,
            "metadata": {
                "cleaning_actions_applied": request.cleaning_actions,
                "language": language,
                "direction": direction_for(language),
                "symbols": symbols,
                "profiles": cleaner.profile_dataframe(df),
                "ai_connected": False,
            },
            "result": result,
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

