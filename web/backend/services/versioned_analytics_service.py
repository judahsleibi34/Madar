"""Bounded, authorized exploration of one immutable project dataset version."""
from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
from fastapi import HTTPException

from data_analysis import services as data_services
from data_analysis.core.response_utils import sanitize_for_json
from services import project_dataset_service


MAX_EXPLORATION_SOURCE_BYTES = 10 * 1024 * 1024
MAX_EXPLORATION_ROWS = 100_000
MAX_PAGE_SIZE = 100
MAX_OFFSET = 10_000
MAX_SELECTED_COLUMNS = 64
MAX_FILTERS = 8
MAX_RESPONSE_BYTES = 512 * 1024
EXPLORATION_DEADLINE_SECONDS = 3.0
FILTER_OPERATORS = {"eq", "gte", "lte", "missing", "not_missing"}


def _deadline(started: float) -> None:
    if time.monotonic() - started > EXPLORATION_DEADLINE_SECONDS:
        raise HTTPException(status_code=408, detail={
            "code": "dataset_exploration_deadline_exceeded",
            "message": "The bounded dataset query exceeded its execution deadline.",
        })


def _technical_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    non_missing = series.dropna()
    if len(non_missing):
        parsed = pd.to_datetime(non_missing, errors="coerce", utc=True, format="mixed")
        if parsed.notna().all():
            return "datetime"
    return "text"


def _require_column(field: object, columns: list[str]) -> str:
    normalized = str(field or "")
    if normalized not in columns:
        raise HTTPException(status_code=422, detail={
            "code": "dataset_exploration_invalid_field",
            "message": "A selected field is not present in this dataset version.",
        })
    return normalized


def _coerce_filter_value(value: Any, kind: str) -> Any:
    if kind == "number":
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail={
                "code": "dataset_exploration_invalid_numeric_filter",
                "message": "The filter value is not compatible with the numeric field.",
            }) from error
    if kind == "datetime":
        parsed = pd.to_datetime(value, errors="coerce", utc=True, format="mixed")
        if pd.isna(parsed):
            raise HTTPException(status_code=422, detail={
                "code": "dataset_exploration_invalid_date_filter",
                "message": "The filter value is not a valid date or datetime.",
            })
        return parsed
    return value


def explore_dataset_version(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    dataset_id: str,
    version_id: str,
    columns: list[str],
    filters: list[dict[str, Any]],
    sort: list[dict[str, str]],
    limit: int,
    offset: int,
    client=None,
) -> dict:
    if limit < 1 or limit > MAX_PAGE_SIZE or offset < 0 or offset > MAX_OFFSET:
        raise HTTPException(status_code=422, detail="Dataset page bounds are invalid.")
    if len(columns) > MAX_SELECTED_COLUMNS or len(filters) > MAX_FILTERS or len(sort) > 2:
        raise HTTPException(status_code=422, detail="Dataset query complexity exceeds the supported limit.")

    started = time.monotonic()
    persistent = project_dataset_service.resolve_project_dataset_version(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(user_id),
        dataset_id=dataset_id, version_id=version_id, client=client,
    )
    version = persistent["version"]
    metadata = version.get("file_metadata") if isinstance(version.get("file_metadata"), dict) else {}
    declared_rows = metadata.get("rows")
    if int(version.get("size_bytes") or 0) > MAX_EXPLORATION_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail={
            "code": "dataset_exploration_source_too_large",
            "message": "This storage format cannot be queried safely within the bounded exploration limit.",
        })
    if isinstance(declared_rows, int) and declared_rows > MAX_EXPLORATION_ROWS:
        raise HTTPException(status_code=413, detail={
            "code": "dataset_exploration_row_limit_exceeded",
            "message": "This dataset version exceeds the bounded exploration row limit.",
        })
    _deadline(started)
    frame = data_services.read_dataset(
        persistent["storage_identifier"], tenant_id=str(tenant_id), user_id=str(user_id),
    )
    frame = frame.copy()
    frame.columns = [str(column) for column in frame.columns]
    if len(frame) > MAX_EXPLORATION_ROWS:
        raise HTTPException(status_code=413, detail={
            "code": "dataset_exploration_row_limit_exceeded",
            "message": "This dataset version exceeds the bounded exploration row limit.",
        })
    actual_columns = list(frame.columns)
    selected = [_require_column(column, actual_columns) for column in columns] if columns else actual_columns[:MAX_SELECTED_COLUMNS]
    if not selected:
        raise HTTPException(status_code=422, detail="The dataset version has no explorable columns.")
    technical_types = {column: _technical_type(frame[column]) for column in actual_columns}

    working = frame
    for item in filters:
        field = _require_column(item.get("field"), actual_columns)
        operator = str(item.get("operator") or "")
        if operator not in FILTER_OPERATORS:
            raise HTTPException(status_code=422, detail={
                "code": "dataset_exploration_unsupported_filter",
                "message": "The requested filter operation is not supported.",
            })
        series = working[field]
        if operator == "missing":
            mask = series.isna()
        elif operator == "not_missing":
            mask = series.notna()
        else:
            kind = technical_types[field]
            if operator in {"gte", "lte"} and kind not in {"number", "datetime"}:
                raise HTTPException(status_code=422, detail={
                    "code": "dataset_exploration_incompatible_filter",
                    "message": "Range filters require a numeric or verified date field.",
                })
            value = _coerce_filter_value(item.get("value"), kind)
            comparable = series
            if kind == "number":
                comparable = pd.to_numeric(series, errors="coerce")
            elif kind == "datetime":
                comparable = pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
            if operator == "eq":
                mask = comparable == value
            elif operator == "gte":
                mask = comparable >= value
            else:
                mask = comparable <= value
        working = working.loc[mask]
        _deadline(started)

    if sort:
        sort_columns = [_require_column(item.get("field"), actual_columns) for item in sort]
        directions = []
        for item in sort:
            direction = str(item.get("direction") or "asc").lower()
            if direction not in {"asc", "desc"}:
                raise HTTPException(status_code=422, detail="Dataset sort direction is invalid.")
            directions.append(direction == "asc")
        working = working.sort_values(sort_columns, ascending=directions, kind="mergesort", na_position="last")
        _deadline(started)

    total = int(len(working))
    page = working.loc[:, selected].iloc[offset:offset + limit]
    rows = sanitize_for_json(page.to_dict(orient="records"))
    result = {
        "rows": rows,
        "columns": [{"name": column, "technical_type": technical_types[column]} for column in selected],
        "pagination": {
            "limit": limit, "offset": offset, "returned": len(rows), "total": total,
            "has_more": offset + len(rows) < total,
        },
        "provenance": {
            "project_id": persistent["dataset"]["project_id"],
            "dataset_id": persistent["dataset"]["id"],
            "dataset_version_id": version["id"],
            "version_number": version["version_number"],
            "content_hash": version.get("content_hash"),
        },
        "limits": {
            "max_page_size": MAX_PAGE_SIZE,
            "max_offset": MAX_OFFSET,
            "max_source_bytes": MAX_EXPLORATION_SOURCE_BYTES,
            "max_rows": MAX_EXPLORATION_ROWS,
        },
    }
    if len(json.dumps(result, default=str).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise HTTPException(status_code=413, detail="Dataset exploration result exceeds the response limit.")
    _deadline(started)
    return result
