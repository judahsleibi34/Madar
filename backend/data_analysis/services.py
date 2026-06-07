import logging
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from data_analysis.assisted.assisted_analysis import AssistedAnalysis
from data_analysis.cleaning.data_cleaning import DataCleaning
from data_analysis.core.analysis_catalog import ANALYSIS_CATALOG
from data_analysis.core.analysis_i18n import (
    direction_for,
    localized_catalog,
    normalize_language,
    normalize_symbols,
)
from data_analysis.core.response_utils import dataframe_preview, sanitize_for_json
from data_analysis.io.data_reading import DataReadingNormal
from data_analysis.router import AnalysisRouter
from data_analysis.visualization.visualization import DataVisualization

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("DATA_UPLOAD_DIR", "uploads"))
PREVIEW_LIMIT = 100
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
UPLOAD_CHUNK_SIZE = 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xls", ".xlsx"}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


def safe_scope_value(value: object) -> str:
    text = str(value).strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise HTTPException(status_code=400, detail="Invalid user storage scope.")

    return text


def get_user_upload_dir(tenant_id: str, user_id: str) -> Path:
    scoped_dir = UPLOAD_DIR / f"tenant_{tenant_id}" / f"user_{user_id}"
    scoped_dir.mkdir(parents=True, exist_ok=True)
    return scoped_dir


def validate_upload_filename(filename: str) -> str:
    clean_filename = (filename or "").strip()

    if (
        not clean_filename
        or "\x00" in clean_filename
        or "/" in clean_filename
        or "\\" in clean_filename
        or Path(clean_filename).name != clean_filename
        or ".." in Path(clean_filename).parts
    ):
        raise HTTPException(status_code=400, detail="Invalid upload filename.")

    extension = Path(clean_filename).suffix.lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .xls, and .xlsx files are supported.",
        )

    return extension


def validate_upload_content_type(content_type: str | None) -> None:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()

    if normalized not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported upload content type.",
        )


async def read_limited_upload(file: UploadFile) -> bytes:
    content = bytearray()

    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)

        if not chunk:
            break

        content.extend(chunk)

        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Uploaded file is too large.",
            )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    return bytes(content)


def build_dataset_response(df, *, file_path: str, original_filename: str | None = None):
    return {
        "file_path": file_path,
        "original_filename": original_filename or file_path,
        "rows": int(len(df)),
        "columns": [sanitize_for_json(column) for column in df.columns],
        "preview": dataframe_preview(df, PREVIEW_LIMIT),
    }


def read_dataset(input_path: str, *, tenant_id: str, user_id: str):
    reader = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return reader.read()


async def process_upload(file: UploadFile, *, tenant_id: str, user_id: str):
    filename = file.filename or ""
    file_extension = validate_upload_filename(filename)
    validate_upload_content_type(file.content_type)
    content = await read_limited_upload(file)

    unique_filename = f"{uuid4().hex}{file_extension}"
    file_path = get_user_upload_dir(tenant_id, user_id) / unique_filename
    file_path.write_bytes(content)

    reader = DataCleaning(str(file_path), tenant_id=tenant_id, user_id=user_id)
    df = reader.read()

    logger.info(
        "data.upload.accepted",
        extra={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "filename": Path(filename).name,
            "stored_path": str(file_path),
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
        },
    )

    return build_dataset_response(
        df,
        file_path=str(file_path),
        original_filename=filename,
    )


def process_read(input_path: str, *, tenant_id: str, user_id: str):
    reader = DataReadingNormal(input_path, tenant_id=tenant_id, user_id=user_id)
    df = reader.read()

    return build_dataset_response(
        df,
        file_path=input_path,
        original_filename=input_path,
    )


def inspect_dataset(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.data_inspection())


def preparation_report(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.preparation_report())


def statistical_inspection(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.statistical_inspection())


def missing_values_report(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.missing_values_report())


def quality_report(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.quality_report())


def column_types(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.column_types())


def apply_cleaning(input_path: str, actions: list[dict], *, tenant_id: str, user_id: str):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(actions)

    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "preview": dataframe_preview(df, 20),
    }


def get_analysis_catalog(language: str = "en"):
    language = normalize_language(language)
    symbols = normalize_symbols()
    return sanitize_for_json(
        {
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
        }
    )


def run_analysis(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    analysis_requests: list[dict],
    language: str,
    symbols: dict,
    tenant_id: str,
    user_id: str,
):
    try:
        cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
        df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
        df, preparation_warnings = cleaner.prepare_dataframe(df)
        language = normalize_language(language)
        symbols = normalize_symbols(symbols)

        analysis_router = AnalysisRouter(df, language=language, symbols=symbols)
        results = analysis_router.run(analysis_requests)

        return sanitize_for_json(
            {
                "rows_used": int(len(df)),
                "columns_used": list(df.columns),
                "warnings": preparation_warnings,
                "metadata": {
                    "cleaning_actions_applied": cleaning_actions,
                    "analysis_request_count": len(analysis_requests),
                    "language": language,
                    "direction": direction_for(language),
                    "symbols": symbols,
                    "profiles": cleaner.profile_dataframe(df),
                },
                "results": results,
            }
        )

    except Exception as error:
        logger.warning(
            "data.analysis.failed",
            extra={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "error_type": type(error).__name__,
            },
        )
        raise


def run_assisted_analysis(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    question: str | None,
    metric: dict | None,
    language: str,
    symbols: dict,
    tenant_id: str,
    user_id: str,
):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
    df, preparation_warnings = cleaner.prepare_dataframe(df)
    language = normalize_language(language)
    symbols = normalize_symbols(symbols)

    analyzer = AssistedAnalysis(df, language=language, symbols=symbols)
    result = analyzer.answer_question(question=question, metric=metric)

    return sanitize_for_json(
        {
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
            "warnings": preparation_warnings,
            "metadata": {
                "cleaning_actions_applied": cleaning_actions,
                "language": language,
                "direction": direction_for(language),
                "symbols": symbols,
                "profiles": cleaner.profile_dataframe(df),
                "ai_connected": False,
            },
            "result": result,
        }
    )


def create_visualization(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    chart_config: dict,
    tenant_id: str,
    user_id: str,
):
    cleaner = DataCleaning(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
    visualizer = DataVisualization(df)
    chart_path = visualizer.plot(**chart_config)

    return sanitize_for_json(
        {
            "chart_path": chart_path,
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
        }
    )
