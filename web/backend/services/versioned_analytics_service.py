"""Bounded, authorized exploration of one immutable project dataset version."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any

import duckdb
import pandas as pd
from fastapi import HTTPException

from data_analysis import services as data_services
from data_analysis.core.response_utils import sanitize_for_json
from services import adaptive_analytics_service, parquet_cache_service, project_dataset_service


MAX_EXPLORATION_SOURCE_BYTES = adaptive_analytics_service.SMALL_DATASET_MAX_BYTES
MAX_EXPLORATION_ROWS = adaptive_analytics_service.SMALL_DATASET_MAX_ROWS
MAX_SCALABLE_CSV_SOURCE_BYTES = adaptive_analytics_service.SCALABLE_CSV_MAX_BYTES
MAX_SCALABLE_CSV_ROWS = adaptive_analytics_service.SCALABLE_CSV_MAX_ROWS
MAX_PAGE_SIZE = 100
MAX_OFFSET = 10_000
MAX_SELECTED_COLUMNS = 64
MAX_FILTERS = 8
MAX_RESPONSE_BYTES = 512 * 1024
EXPLORATION_DEADLINE_SECONDS = 3.0
SCALABLE_EXPLORATION_DEADLINE_SECONDS = 10.0
SCALABLE_EXPLORATION_MEMORY_LIMIT = "128MiB"
SCALABLE_EXPLORATION_SCRATCH_LIMIT = "256MiB"
MAX_CONCURRENT_SCALABLE_EXPLORATIONS = 2
FILTER_OPERATORS = {"eq", "gte", "lte", "missing", "not_missing"}
_scalable_exploration_slots = threading.BoundedSemaphore(MAX_CONCURRENT_SCALABLE_EXPLORATIONS)
_boundary_exploration_slot = threading.BoundedSemaphore(1)


def _deadline(started: float, seconds: float = EXPLORATION_DEADLINE_SECONDS) -> None:
    if time.monotonic() - started > seconds:
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


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _quote_setting_value(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _duckdb_technical_type(type_name: object) -> str:
    normalized = str(type_name or "").upper()
    if normalized == "BOOLEAN":
        return "boolean"
    if normalized.startswith((
        "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UTINYINT",
        "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT", "DECIMAL", "FLOAT",
        "DOUBLE", "REAL",
    )):
        return "number"
    if normalized.startswith(("DATE", "TIME", "TIMESTAMP")):
        return "datetime"
    return "text"


def _internal_column_name(columns: list[str], suffix: str) -> str:
    candidate = f"__madar_{suffix}"
    while candidate in columns:
        candidate = f"_{candidate}"
    return candidate


def _configure_duckdb(connection, *, source_path: str, scratch_path: str) -> None:
    source = _quote_setting_value(source_path)
    scratch = _quote_setting_value(scratch_path)
    connection.execute(f"SET memory_limit={_quote_setting_value(SCALABLE_EXPLORATION_MEMORY_LIMIT)}")
    connection.execute(f"SET max_temp_directory_size={_quote_setting_value(SCALABLE_EXPLORATION_SCRATCH_LIMIT)}")
    connection.execute(f"SET temp_directory={scratch}")
    connection.execute("SET threads=1")
    connection.execute("SET preserve_insertion_order=true")
    connection.execute(f"SET allowed_paths=[{source}]")
    connection.execute(f"SET allowed_directories=[{scratch}]")
    connection.execute("SET autoinstall_known_extensions=false")
    connection.execute("SET autoload_known_extensions=false")
    connection.execute("SET allow_community_extensions=false")
    connection.execute("SET enable_external_access=false")
    connection.execute("SET lock_configuration=true")


def _execute_duckdb(connection, sql: str, parameters: list[Any], *, started: float):
    remaining = SCALABLE_EXPLORATION_DEADLINE_SECONDS - (time.monotonic() - started)
    if remaining <= 0:
        _deadline(started, SCALABLE_EXPLORATION_DEADLINE_SECONDS)
    timer = threading.Timer(max(0.001, remaining), connection.interrupt)
    timer.daemon = True
    timer.start()
    try:
        return connection.execute(sql, parameters)
    except duckdb.InterruptException as error:
        raise HTTPException(status_code=408, detail={
            "code": "dataset_exploration_deadline_exceeded",
            "message": "The bounded dataset query exceeded its execution deadline.",
        }) from error
    finally:
        timer.cancel()


def _duckdb_filter_clause(
    filters: list[dict[str, Any]], actual_columns: list[str], technical_types: dict[str, str],
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    for item in filters:
        field = _require_column(item.get("field"), actual_columns)
        operator = str(item.get("operator") or "")
        if operator not in FILTER_OPERATORS:
            raise HTTPException(status_code=422, detail={
                "code": "dataset_exploration_unsupported_filter",
                "message": "The requested filter operation is not supported.",
            })
        identifier = _quote_identifier(field)
        if operator == "missing":
            clauses.append(f"{identifier} IS NULL")
            continue
        if operator == "not_missing":
            clauses.append(f"{identifier} IS NOT NULL")
            continue
        kind = technical_types[field]
        if operator in {"gte", "lte"} and kind not in {"number", "datetime"}:
            raise HTTPException(status_code=422, detail={
                "code": "dataset_exploration_incompatible_filter",
                "message": "Range filters require a numeric or verified date field.",
            })
        value = _coerce_filter_value(item.get("value"), kind)
        if kind == "datetime" and hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        comparison = {"eq": "=", "gte": ">=", "lte": "<="}[operator]
        clauses.append(f"{identifier} {comparison} ?")
        parameters.append(value)
    return (" AND ".join(clauses) if clauses else "TRUE"), parameters


def _explore_scalable_csv(
    *, storage_identifier: str, tenant_id: int, user_id: int, columns: list[str],
    filters: list[dict[str, Any]], sort: list[dict[str, str]], limit: int, offset: int,
    started: float, project_id: str | None = None, dataset_id: str | None = None,
    version_id: str | None = None, content_hash: str | None = None,
    declared_rows: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    if not _scalable_exploration_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail={
                "code": "dataset_exploration_busy",
                "message": "The bounded dataset query capacity is currently in use.",
            },
            headers={"Retry-After": "1"},
        )
    boundary_acquired = False
    try:
        authorized = data_services.authorize_dataset_input_path(
            storage_identifier, tenant_id=str(tenant_id), user_id=str(user_id),
            require_small=False, operation="bounded scalable dataset exploration",
        )
        source = Path(authorized)
        if source.suffix.lower() != ".csv" or not source.is_file():
            raise HTTPException(status_code=413, detail={
                "code": "dataset_exploration_scalable_format_unsupported",
                "message": "Scalable exploration currently supports CSV dataset versions only.",
            })
        actual_size = source.stat().st_size
        if actual_size <= 0 or actual_size > MAX_SCALABLE_CSV_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail={
                "code": "dataset_exploration_scalable_source_limit_exceeded",
                "message": "This CSV exceeds the bounded scalable exploration source limit.",
            })
        query_source = source
        if all((project_id, dataset_id, version_id, content_hash)):
            artifact = parquet_cache_service.get_or_create(
                source_path=str(source), tenant_id=tenant_id, user_id=user_id,
                project_id=str(project_id), dataset_id=str(dataset_id),
                version_id=str(version_id), source_hash=str(content_hash),
                source_size=actual_size, declared_rows=declared_rows,
            )
            if artifact is not None:
                query_source = artifact.path
        with query_source.open("rb") as source_file:
            if actual_size > 100 * 1024 * 1024:
                boundary_acquired = _boundary_exploration_slot.acquire(blocking=False)
                if not boundary_acquired:
                    raise HTTPException(status_code=429, detail={
                        "code": "dataset_exploration_boundary_busy",
                        "message": "The boundary-size dataset query capacity is currently in use.",
                    }, headers={"Retry-After": "1"})
            descriptor_path = f"/proc/self/fd/{source_file.fileno()}"
            with tempfile.TemporaryDirectory(prefix="madar-explore-", dir=source.parent) as scratch:
                connection = duckdb.connect(":memory:")
                try:
                    _configure_duckdb(connection, source_path=descriptor_path, scratch_path=scratch)
                    source_sql = (
                        "read_parquet(?)" if query_source.suffix.lower() == ".parquet"
                        else "read_csv_auto(?, header=true, sample_size=-1, strict_mode=true)"
                    )
                    schema_rows = _execute_duckdb(
                        connection, f"DESCRIBE SELECT * FROM {source_sql}", [descriptor_path],
                        started=started,
                    ).fetchall()
                    actual_columns = [str(row[0]) for row in schema_rows]
                    if not actual_columns:
                        raise HTTPException(status_code=422, detail="The dataset version has no explorable columns.")
                    technical_types = {
                        str(row[0]): _duckdb_technical_type(row[1]) for row in schema_rows
                    }
                    selected = (
                        [_require_column(column, actual_columns) for column in columns]
                        if columns else actual_columns[:MAX_SELECTED_COLUMNS]
                    )
                    if not selected:
                        raise HTTPException(status_code=422, detail="The dataset version has no explorable columns.")
                    filter_sql, filter_parameters = _duckdb_filter_clause(
                        filters, actual_columns, technical_types,
                    )
                    sort_fields: list[tuple[str, str]] = []
                    for item in sort:
                        field = _require_column(item.get("field"), actual_columns)
                        direction = str(item.get("direction") or "asc").lower()
                        if direction not in {"asc", "desc"}:
                            raise HTTPException(status_code=422, detail="Dataset sort direction is invalid.")
                        sort_fields.append((field, direction.upper()))

                    required = list(dict.fromkeys(
                        selected
                        + [str(item.get("field")) for item in filters]
                        + [field for field, _ in sort_fields]
                    ))
                    ordinal_name = _internal_column_name(actual_columns, "source_ordinal")
                    source_total_name = _internal_column_name(
                        actual_columns + [ordinal_name], "source_total",
                    )
                    total_name = _internal_column_name(
                        actual_columns + [ordinal_name, source_total_name], "filtered_total",
                    )
                    projected_sql = ", ".join(_quote_identifier(column) for column in required)
                    selected_sql = ", ".join(_quote_identifier(column) for column in selected)
                    order_sql = ", ".join(
                        f"{_quote_identifier(field)} {direction} NULLS LAST"
                        for field, direction in sort_fields
                    )
                    if order_sql:
                        order_sql += ", "
                    order_sql += f"{_quote_identifier(ordinal_name)} ASC"
                    query = f"""
                        WITH source AS (
                            SELECT
                                row_number() OVER () AS {_quote_identifier(ordinal_name)},
                                count(*) OVER () AS {_quote_identifier(source_total_name)},
                                {projected_sql}
                            FROM {source_sql}
                        ), filtered AS (
                            SELECT *, count(*) OVER () AS {_quote_identifier(total_name)}
                            FROM source WHERE {filter_sql}
                        )
                        SELECT
                            {selected_sql},
                            {_quote_identifier(total_name)},
                            {_quote_identifier(source_total_name)}
                        FROM filtered
                        ORDER BY {order_sql}
                        LIMIT ? OFFSET ?
                    """
                    result_rows = _execute_duckdb(
                        connection, query,
                        [descriptor_path, *filter_parameters, int(limit), int(offset)],
                        started=started,
                    ).fetchall()
                    if result_rows:
                        total = int(result_rows[0][-2])
                        source_total = int(result_rows[0][-1])
                        values = [row[:-2] for row in result_rows]
                    else:
                        count_query = f"""
                            WITH source AS (
                                SELECT {projected_sql} FROM {source_sql}
                            )
                            SELECT count(*), count(*) FILTER (WHERE {filter_sql}) FROM source
                        """
                        counts = _execute_duckdb(
                            connection, count_query, [descriptor_path, *filter_parameters],
                            started=started,
                        ).fetchone()
                        source_total = int(counts[0])
                        total = int(counts[1])
                        values = []
                    if source_total > MAX_SCALABLE_CSV_ROWS:
                        raise HTTPException(status_code=413, detail={
                            "code": "dataset_exploration_scalable_row_limit_exceeded",
                            "message": "This CSV exceeds the bounded scalable exploration row limit.",
                        })
                    rows = sanitize_for_json([
                        {column: value for column, value in zip(selected, row)} for row in values
                    ])
                    column_metadata = [
                        {"name": column, "technical_type": technical_types[column]}
                        for column in selected
                    ]
                    return rows, column_metadata, total
                except HTTPException:
                    raise
                except (duckdb.OutOfMemoryException, duckdb.IOException) as error:
                    raise HTTPException(status_code=413, detail={
                        "code": "dataset_exploration_resource_limit_exceeded",
                        "message": "The bounded dataset query exceeded its memory or scratch-disk limit.",
                    }) from error
                except duckdb.Error as error:
                    raise HTTPException(status_code=422, detail={
                        "code": "dataset_exploration_invalid_csv",
                        "message": "The CSV dataset could not be queried safely.",
                    }) from error
                finally:
                    connection.close()
    except OSError as error:
        raise HTTPException(status_code=503, detail={
            "code": "dataset_exploration_storage_unavailable",
            "message": "The authorized dataset or bounded scratch storage is unavailable.",
        }) from error
    except duckdb.Error as error:
        raise HTTPException(status_code=503, detail={
            "code": "dataset_exploration_engine_unavailable",
            "message": "The bounded dataset query engine is unavailable.",
        }) from error
    finally:
        if boundary_acquired:
            _boundary_exploration_slot.release()
        _scalable_exploration_slots.release()


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
    declared_size = int(version.get("size_bytes") or 0)
    decision = adaptive_analytics_service.select_engine(
        workload="explore",
        file_format=Path(str(persistent["storage_identifier"])).suffix,
        size_bytes=declared_size,
        row_count=declared_rows if isinstance(declared_rows, int) else None,
    )
    if decision.engine == "unsupported":
        code = (
            "dataset_exploration_scalable_format_unsupported"
            if decision.reason == "large_format_unsupported"
            else "dataset_exploration_scalable_source_limit_exceeded"
            if declared_size > MAX_SCALABLE_CSV_SOURCE_BYTES
            else "dataset_exploration_scalable_row_limit_exceeded"
        )
        raise HTTPException(status_code=413, detail={
            "code": code,
            "message": "This dataset exceeds the bounded compatible exploration policy.",
        })
    scalable = decision.engine == "duckdb"
    if scalable:
        if Path(str(persistent["storage_identifier"])).suffix.lower() != ".csv":
            raise HTTPException(status_code=413, detail={
                "code": "dataset_exploration_scalable_format_unsupported",
                "message": "Scalable exploration currently supports CSV dataset versions only.",
            })
        if declared_size > MAX_SCALABLE_CSV_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail={
                "code": "dataset_exploration_scalable_source_limit_exceeded",
                "message": "This CSV exceeds the bounded scalable exploration source limit.",
            })
        if isinstance(declared_rows, int) and declared_rows > MAX_SCALABLE_CSV_ROWS:
            raise HTTPException(status_code=413, detail={
                "code": "dataset_exploration_scalable_row_limit_exceeded",
                "message": "This CSV exceeds the bounded scalable exploration row limit.",
            })
        rows, column_metadata, total = _explore_scalable_csv(
            storage_identifier=persistent["storage_identifier"],
            tenant_id=int(tenant_id), user_id=int(user_id), columns=columns,
            filters=filters, sort=sort, limit=limit, offset=offset, started=started,
            project_id=project_id, dataset_id=dataset_id, version_id=version_id,
            content_hash=version.get("content_hash"),
            declared_rows=declared_rows if isinstance(declared_rows, int) else None,
        )
        limits = {
            "max_page_size": MAX_PAGE_SIZE,
            "max_offset": MAX_OFFSET,
            "max_source_bytes": MAX_SCALABLE_CSV_SOURCE_BYTES,
            "max_rows": MAX_SCALABLE_CSV_ROWS,
        }
    elif declared_size > MAX_EXPLORATION_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail={
            "code": "dataset_exploration_source_too_large",
            "message": "This storage format cannot be queried safely within the bounded exploration limit.",
        })
    elif isinstance(declared_rows, int) and declared_rows > MAX_EXPLORATION_ROWS:
        raise HTTPException(status_code=413, detail={
            "code": "dataset_exploration_row_limit_exceeded",
            "message": "This dataset version exceeds the bounded exploration row limit.",
        })
    else:
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
        column_metadata = [
            {"name": column, "technical_type": technical_types[column]} for column in selected
        ]
        limits = {
            "max_page_size": MAX_PAGE_SIZE,
            "max_offset": MAX_OFFSET,
            "max_source_bytes": MAX_EXPLORATION_SOURCE_BYTES,
            "max_rows": MAX_EXPLORATION_ROWS,
        }
    result = {
        "rows": rows,
        "columns": column_metadata,
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
        "limits": limits,
    }
    if len(json.dumps(result, default=str).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise HTTPException(status_code=413, detail="Dataset exploration result exceeds the response limit.")
    _deadline(
        started,
        SCALABLE_EXPLORATION_DEADLINE_SECONDS if scalable else EXPLORATION_DEADLINE_SECONDS,
    )
    return result
