"""Isolated Polars worker. Accepts only allowlisted deterministic metric JSON."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
import json
import math
import os
import re
import sys
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import polars as pl


OPERATIONS = {"count", "sum", "mean", "min", "max", "distinct_count", "date_aggregate"}
NUMERIC_TYPES = {
    pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Int128,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
    pl.Float32, pl.Float64, pl.Decimal,
}
GROUP_TYPES = {pl.String, pl.Boolean, pl.Int8, pl.Int16, pl.Int32, pl.Int64,
               pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64}
DATE_PARSE_CACHE_ENTRIES = 4096
DATE_PARSE_CACHE_MAX_TEXT = 512
DATE_ISO_FAST_PATH = True
DATE_CSV_BATCH_BYTES = 512 * 1024
DATE_CSV_RECORD_BYTES = 2 * 1024 * 1024
# Exact, aware ISO forms only. Other forms retain pandas' established parser,
# including naive/DST localization and sub-microsecond timestamps.
_AWARE_ISO = re.compile(
    r"(?:19|20)[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z"
)


def date_csv_batches(source: str, schema: dict[str, Any], columns: list[str]):
    """Parse bounded raw CSV buffers; never map/prefetch the complete source.

    Quote parity includes escaped double quotes, which contribute an even
    count. Raw bytes, including CRLF and embedded newlines, reach Polars intact.
    Polars remains responsible for dialect, value and schema validation.
    """
    def parse(header, data):
        return pl.read_csv(
            bytes(header + data), schema=schema,
            columns=list(dict.fromkeys(columns)), try_parse_dates=False,
            n_threads=1, low_memory=True,
        ).select(columns)

    with open(source, "rb") as stream:
        header = bytearray()
        quoted = False
        while True:
            line = stream.readline(DATE_CSV_RECORD_BYTES + 1)
            # Polars skips empty physical lines before the CSV header. Repeating
            # an empty line as the header would drop each batch's first record.
            if not header and line in (b"\n", b"\r\n"):
                continue
            header.extend(line)
            if len(header) > DATE_CSV_RECORD_BYTES:
                raise WorkerError("analytics_csv_record_limit_exceeded")
            quoted ^= bool(line.count(b'"') % 2)
            if not line or not quoted:
                break
        pending = bytearray()
        record_bytes = 0
        for_line = stream.readline
        while True:
            line = for_line(DATE_CSV_RECORD_BYTES + 1)
            if not line:
                if quoted:
                    raise WorkerError("analytics_incompatible_schema")
                if pending:
                    yield parse(header, pending)
                return
            pending.extend(line)
            record_bytes += len(line)
            if record_bytes > DATE_CSV_RECORD_BYTES:
                raise WorkerError("analytics_csv_record_limit_exceeded")
            quoted ^= bool(line.count(b'"') % 2)
            if not quoted:
                record_bytes = 0
                if len(pending) >= DATE_CSV_BATCH_BYTES:
                    yield parse(header, pending)
                    pending.clear()


class WorkerError(Exception):
    pass


def fail(code: str) -> None:
    sys.stdout.write(json.dumps({"ok": False, "code": code}, separators=(",", ":")))
    raise SystemExit(2)


def safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return str(value)


def strict_localize(value: datetime, zone: ZoneInfo) -> datetime:
    candidates: list[datetime] = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        roundtrip = candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if roundtrip == value and candidate.utcoffset() not in [item.utcoffset() for item in candidates]:
            candidates.append(candidate)
    if len(candidates) != 1:
        raise ValueError("ambiguous_or_nonexistent_local_time")
    return candidates[0]


def strict_boundary(value: date, zone: ZoneInfo) -> datetime:
    return strict_localize(datetime.combine(value, time.min), zone)


def period_key(value: datetime, period: str) -> str:
    if period == "day":
        return value.date().isoformat()
    if period == "month":
        return f"{value.year:04d}-{value.month:02d}"
    start = value.date() - timedelta(days=value.weekday())
    return f"{start.isoformat()}/{(start + timedelta(days=6)).isoformat()}"


def is_period_start(value: datetime, period: str) -> bool:
    return period == "day" or period == "week" and value.weekday() == 0 or period == "month" and value.day == 1


def is_period_end(value: datetime, period: str) -> bool:
    if period == "day":
        return True
    if period == "week":
        return value.weekday() == 6
    return (value + timedelta(days=1)).month != value.month


def metric_columns(metric: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(str(metric[key]) for key in (
        "value_column", "group_column", "date_column",
    ) if metric.get(key)))


def simple_metric(
    frame: pl.LazyFrame, schema: dict[str, Any], metric: dict[str, Any], max_groups: int,
) -> tuple[list[dict[str, Any]], int]:
    operation = str(metric["operation"])
    value_column = metric.get("value_column")
    group_column = metric.get("group_column")
    for column in metric_columns(metric):
        if column not in schema:
            raise WorkerError("analytics_incompatible_schema")
    if group_column and schema[str(group_column)] not in GROUP_TYPES:
        raise WorkerError("analytics_incompatible_schema")
    if operation not in {"count", "distinct_count"}:
        if not value_column or schema[str(value_column)].base_type() not in NUMERIC_TYPES:
            raise WorkerError("analytics_incompatible_schema")
    if operation == "distinct_count" and not value_column:
        raise WorkerError("analytics_incompatible_schema")

    if operation == "count" and not value_column:
        expression = pl.len().alias("value")
    else:
        value = pl.col(str(value_column))
        if schema[str(value_column)].base_type() in {pl.Float32, pl.Float64}:
            value = value.fill_nan(None)
        expression = {
            "count": value.count(),
            "sum": value.sum(),
            "mean": value.mean(),
            "min": value.min(),
            "max": value.max(),
            "distinct_count": value.drop_nulls().n_unique(),
        }[operation].alias("value")
    if group_column:
        result = frame.group_by(str(group_column)).agg(
            expression, pl.len().alias("__madar_row_count"),
        ).sort(
            str(group_column), nulls_last=True, maintain_order=True,
        ).limit(max_groups + 1).collect(engine="streaming")
        rows_used = int(result["__madar_row_count"].sum())
        result = result.drop("__madar_row_count")
    else:
        result = frame.select(
            expression, pl.len().alias("__madar_row_count"),
        ).collect(engine="streaming")
        rows_used = int(result["__madar_row_count"].item())
        result = result.drop("__madar_row_count")
    if result.height > max_groups:
        raise WorkerError("analytics_group_cardinality_exceeded")
    return ([
        {key: safe_value(value) for key, value in row.items()} for row in result.to_dicts()
    ], rows_used)


def date_metric(
    frame: pl.LazyFrame, schema: dict[str, Any], metric: dict[str, Any], max_groups: int,
    max_rows: int, *, batches=None,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    # Import only for date metrics: this preserves the established Timestamp
    # parsing/localization semantics without adding pandas to numeric workers.
    import pandas as pd

    date_column = str(metric.get("date_column") or "")
    value_column = str(metric.get("value_column") or "")
    aggregation = str(metric.get("aggregation") or "count").lower()
    period = str(metric.get("period") or "month").lower()
    timezone_name = str(metric.get("timezone") or "UTC")
    if not date_column or date_column not in schema or period not in {"day", "week", "month"} \
            or aggregation not in {"count", "sum", "mean", "min", "max"}:
        raise WorkerError("analytics_incompatible_schema")
    if aggregation != "count" and (
        not value_column or value_column not in schema
        or schema[value_column].base_type() not in NUMERIC_TYPES
    ):
        raise WorkerError("analytics_incompatible_schema")
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise WorkerError("analytics_incompatible_schema") from error

    start_text = str(metric.get("start_date") or "")
    end_text = str(metric.get("end_date") or "")
    if bool(start_text) != bool(end_text):
        raise WorkerError("analytics_incompatible_schema")
    start_boundary = end_boundary = None
    if start_text:
        try:
            start_date, end_date = date.fromisoformat(start_text), date.fromisoformat(end_text)
            if start_date.isoformat() != start_text or end_date.isoformat() != end_text or start_date > end_date:
                raise ValueError
            start_boundary = strict_boundary(start_date, zone)
            end_boundary = strict_boundary(end_date + timedelta(days=1), zone)
        except ValueError as error:
            raise WorkerError("analytics_invalid_date_field") from error

    columns = [date_column] + ([value_column] if aggregation != "count" else [])
    # Repeated timestamps are common in reporting exports. Cache only parsing
    # and period calculation, preserving per-row numeric accumulation order.
    # The cache belongs to this query/zone/period and has a fixed entry bound.
    def parse_date(raw_date):
        try:
            if isinstance(raw_date, (int, float, bool)):
                raise ValueError
            if DATE_ISO_FAST_PATH and isinstance(raw_date, str) and _AWARE_ISO.fullmatch(raw_date):
                try:
                    parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).astimezone(zone)
                    return parsed, period_key(parsed, period)
                except ValueError:
                    # Let pandas decide validity for unusual offset/calendar
                    # combinations instead of introducing a new rejection rule.
                    pass
            timestamp = pd.Timestamp(raw_date)
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize(zone, ambiguous="raise", nonexistent="raise")
            else:
                timestamp = timestamp.tz_convert(zone)
            parsed = timestamp.to_pydatetime()
            return parsed, period_key(parsed, period)
        except (TypeError, ValueError):
            return None

    cached_parse_date = lru_cache(maxsize=DATE_PARSE_CACHE_ENTRIES)(parse_date)
    missing = invalid = outside = selected = total = 0
    minimum = maximum = selected_minimum = selected_maximum = None
    groups: dict[str, dict[str, Any]] = {}
    if batches is None:
        batches = frame.select(columns).collect_batches(
            chunk_size=5000, maintain_order=True, engine="streaming",
        )
    for batch in batches:
        for row in batch.iter_rows():
            total += 1
            if total > max_rows:
                raise WorkerError("analytics_row_limit_exceeded")
            raw_date = row[0]
            if raw_date is None or str(raw_date).strip() == "":
                missing += 1
                continue
            parsed_value = (
                cached_parse_date(raw_date)
                if isinstance(raw_date, str) and len(raw_date) <= DATE_PARSE_CACHE_MAX_TEXT
                else parse_date(raw_date)
            )
            if parsed_value is None:
                invalid += 1
                continue
            parsed, key = parsed_value
            minimum = parsed if minimum is None or parsed < minimum else minimum
            maximum = parsed if maximum is None or parsed > maximum else maximum
            if start_boundary is not None and not (start_boundary <= parsed < end_boundary):
                outside += 1
                continue
            selected += 1
            selected_minimum = parsed if selected_minimum is None or parsed < selected_minimum else selected_minimum
            selected_maximum = parsed if selected_maximum is None or parsed > selected_maximum else selected_maximum
            state = groups.get(key)
            if state is None:
                state = {"sum": 0, "count": 0, "min": None, "max": None, "rows": 0}
                groups[key] = state
            state["rows"] += 1
            if aggregation != "count":
                value = row[1]
                if value is None or isinstance(value, float) and math.isnan(value):
                    continue
                state["sum"] += value
                state["count"] += 1
                state["min"] = value if state["min"] is None or value < state["min"] else state["min"]
                state["max"] = value if state["max"] is None or value > state["max"] else state["max"]
            if len(groups) > max_groups:
                raise WorkerError("analytics_group_cardinality_exceeded")
    if minimum is None:
        raise WorkerError("analytics_invalid_date_field")
    rows: list[dict[str, Any]] = []
    for key in sorted(groups):
        state = groups[key]
        if aggregation == "count":
            value = state["rows"]
        elif aggregation == "sum":
            value = state["sum"]
        elif aggregation == "mean":
            value = state["sum"] / state["count"] if state["count"] else None
        else:
            value = state[aggregation]
        rows.append({"period": key, "value": safe_value(value)})
    partial_reasons: list[str] = []
    if start_boundary is not None:
        if not is_period_start(start_boundary, period):
            partial_reasons.append("requested_start_inside_period")
        requested_end = end_boundary - timedelta(days=1)
        if not is_period_end(requested_end, period):
            partial_reasons.append("requested_end_inside_period")
    if selected_minimum is not None and not is_period_start(selected_minimum, period):
        partial_reasons.append("observed_coverage_starts_inside_period")
    if selected_maximum is not None and not is_period_end(selected_maximum, period):
        partial_reasons.append("observed_coverage_ends_inside_period")
    mappings = {
        "date_column": date_column, "value_column": value_column or None,
        "aggregation": aggregation, "period": period, "timezone": timezone_name,
        "invalid_date_count": invalid, "missing_date_count": missing,
        "excluded_date_count": invalid + missing, "outside_period_count": outside,
        "selected_row_count": selected, "total_row_count": total,
        "requested_start_date": start_text or None, "requested_end_date": end_text or None,
        "start_inclusive": start_boundary.isoformat() if start_boundary else None,
        "end_exclusive": end_boundary.isoformat() if end_boundary else None,
        "coverage_start": minimum.isoformat(), "coverage_end": maximum.isoformat(),
        "selected_coverage_start": selected_minimum.isoformat() if selected_minimum else None,
        "selected_coverage_end": selected_maximum.isoformat() if selected_maximum else None,
        "partial_periods": bool(partial_reasons), "partial_period_reasons": partial_reasons,
    }
    return rows, mappings, total


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(16 * 1024 + 1)
        if len(raw) > 16 * 1024:
            fail("analytics_request_limit_exceeded")
        request = json.loads(raw)
        metric = request.get("metric") if isinstance(request.get("metric"), dict) else {}
        operation = str(metric.get("operation") or "").lower()
        if operation not in OPERATIONS:
            fail("analytics_incompatible_schema")
        source_fd = int(request["source_fd"])
        if source_fd < 3:
            fail("analytics_incompatible_schema")
        source_format = str(request.get("source_format") or "csv").lower()
        if source_format == "csv":
            frame = pl.scan_csv(
                f"/proc/self/fd/{source_fd}", infer_schema_length=10_000,
                try_parse_dates=False, low_memory=True, glob=False, raise_if_empty=True,
            )
        elif source_format == "parquet":
            frame = pl.scan_parquet(
                f"/proc/self/fd/{source_fd}", glob=False, low_memory=True,
            )
        else:
            fail("analytics_incompatible_schema")
        schema = dict(frame.collect_schema())
        max_columns = int(request.get("max_columns") or 0)
        max_groups = int(request.get("max_groups") or 0)
        max_rows = int(request.get("max_rows") or 0)
        if max_columns < 1 or len(schema) > max_columns:
            fail("analytics_column_limit_exceeded")
        if max_groups < 1 or max_rows < 1:
            fail("analytics_group_cardinality_exceeded")
        if operation == "date_aggregate":
            batches = None
            if source_format == "csv":
                columns = [str(metric.get("date_column") or "")]
                if str(metric.get("aggregation") or "count").lower() != "count":
                    columns.append(str(metric.get("value_column") or ""))
                batches = date_csv_batches(f"/proc/self/fd/{source_fd}", schema, columns)
            rows, mappings, rows_used = date_metric(
                frame, schema, metric, max_groups, max_rows, batches=batches,
            )
        else:
            rows, rows_used = simple_metric(frame, schema, metric, max_groups)
            mappings = {}
        if rows_used > max_rows:
            fail("analytics_row_limit_exceeded")
        output = {
            "ok": True, "rows": rows, "mappings": mappings, "rows_used": rows_used,
            "columns_used": list(schema),
        }
        encoded = json.dumps(output, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > 512 * 1024:
            fail("analytics_result_limit_exceeded")
        sys.stdout.buffer.write(encoded)
    except WorkerError as error:
        fail(str(error))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, pl.exceptions.PolarsError):
        fail("analytics_incompatible_schema")


if __name__ == "__main__":
    main()
