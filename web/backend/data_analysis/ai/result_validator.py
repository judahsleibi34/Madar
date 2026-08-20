from __future__ import annotations

import math
from typing import Any


ALLOWED_RESULT_KEYS = {
    "title",
    "summary",
    "metrics",
    "tables",
    "charts",
}

ALLOWED_METRIC_KEYS = {
    "label",
    "value",
    "description",
    "unit",
}

ALLOWED_TABLE_KEYS = {
    "title",
    "columns",
    "rows",
}

ALLOWED_CHART_KEYS = {
    "type",
    "title",
    "description",
    "x",
    "y",
    "labels",
    "values",
    "data",
    "x_label",
    "y_label",
}

ALLOWED_CHART_TYPES = {
    "bar",
    "line",
    "pie",
    "scatter",
    "histogram",
}

MAX_RESULT_STRING_LENGTH = 250_000
MAX_TITLE_LENGTH = 160
MAX_SUMMARY_LENGTH = 3_000
MAX_METRICS = 30
MAX_TABLES = 5
MAX_TABLE_COLUMNS = 30
MAX_TABLE_ROWS = 100
MAX_CELL_STRING_LENGTH = 300
MAX_CHARTS = 5
MAX_CHART_POINTS = 500


class ResultValidationError(ValueError):
    pass


def validate_analysis_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ResultValidationError("Analysis result must be a dictionary")

    if len(str(result)) > MAX_RESULT_STRING_LENGTH:
        raise ResultValidationError("Analysis result is too large")

    unexpected_keys = set(result.keys()) - ALLOWED_RESULT_KEYS
    if unexpected_keys:
        raise ResultValidationError(
            f"Analysis result contains unsupported keys: {sorted(unexpected_keys)}"
        )

    normalized = {
        "title": _validate_text(
            result.get("title", "Analysis result"),
            field_name="title",
            max_length=MAX_TITLE_LENGTH,
        ),
        "summary": _validate_text(
            result.get("summary", ""),
            field_name="summary",
            max_length=MAX_SUMMARY_LENGTH,
        ),
        "metrics": _validate_metrics(result.get("metrics", [])),
        "tables": _validate_tables(result.get("tables", [])),
        "charts": _validate_charts(result.get("charts", [])),
    }

    return normalized


def _validate_metrics(metrics: Any) -> list[dict[str, Any]]:
    if metrics is None:
        return []

    if not isinstance(metrics, list):
        raise ResultValidationError("metrics must be a list")

    if len(metrics) > MAX_METRICS:
        raise ResultValidationError("Too many metrics returned")

    normalized_metrics = []

    for metric in metrics:
        if not isinstance(metric, dict):
            raise ResultValidationError("Each metric must be a dictionary")

        unexpected_keys = set(metric.keys()) - ALLOWED_METRIC_KEYS
        if unexpected_keys:
            raise ResultValidationError(
                f"Metric contains unsupported keys: {sorted(unexpected_keys)}"
            )

        normalized_metrics.append(
            {
                "label": _validate_text(
                    metric.get("label", "Metric"),
                    field_name="metric.label",
                    max_length=120,
                ),
                "value": _make_json_safe(metric.get("value")),
                "description": _validate_optional_text(
                    metric.get("description"),
                    field_name="metric.description",
                    max_length=300,
                ),
                "unit": _validate_optional_text(
                    metric.get("unit"),
                    field_name="metric.unit",
                    max_length=40,
                ),
            }
        )

    return normalized_metrics


def _validate_tables(tables: Any) -> list[dict[str, Any]]:
    if tables is None:
        return []

    if not isinstance(tables, list):
        raise ResultValidationError("tables must be a list")

    if len(tables) > MAX_TABLES:
        raise ResultValidationError("Too many tables returned")

    normalized_tables = []

    for table in tables:
        if not isinstance(table, dict):
            raise ResultValidationError("Each table must be a dictionary")

        unexpected_keys = set(table.keys()) - ALLOWED_TABLE_KEYS
        if unexpected_keys:
            raise ResultValidationError(
                f"Table contains unsupported keys: {sorted(unexpected_keys)}"
            )

        title = _validate_text(
            table.get("title", "Table"),
            field_name="table.title",
            max_length=160,
        )

        columns = table.get("columns", [])
        rows = table.get("rows", [])

        if not isinstance(columns, list):
            raise ResultValidationError("table.columns must be a list")

        if not isinstance(rows, list):
            raise ResultValidationError("table.rows must be a list")

        if len(columns) > MAX_TABLE_COLUMNS:
            raise ResultValidationError("Table has too many columns")

        if len(rows) > MAX_TABLE_ROWS:
            rows = rows[:MAX_TABLE_ROWS]

        safe_columns = [
            _validate_text(column, field_name="table.column", max_length=120)
            for column in columns
        ]

        safe_rows = []

        for row in rows:
            if isinstance(row, dict):
                safe_row = {
                    str(key): _make_json_safe(value)
                    for key, value in row.items()
                    if str(key) in safe_columns
                }
                safe_rows.append(safe_row)

            elif isinstance(row, list):
                safe_rows.append([
                    _make_json_safe(value)
                    for value in row[: len(safe_columns)]
                ])

            else:
                raise ResultValidationError("table.rows entries must be dict or list")

        normalized_tables.append(
            {
                "title": title,
                "columns": safe_columns,
                "rows": safe_rows,
            }
        )

    return normalized_tables


def _validate_charts(charts: Any) -> list[dict[str, Any]]:
    if charts is None:
        return []

    if not isinstance(charts, list):
        raise ResultValidationError("charts must be a list")

    if len(charts) > MAX_CHARTS:
        raise ResultValidationError("Too many charts returned")

    normalized_charts = []

    for chart in charts:
        if not isinstance(chart, dict):
            raise ResultValidationError("Each chart must be a dictionary")

        unexpected_keys = set(chart.keys()) - ALLOWED_CHART_KEYS
        if unexpected_keys:
            raise ResultValidationError(
                f"Chart contains unsupported keys: {sorted(unexpected_keys)}"
            )

        chart_type = str(chart.get("type", "")).lower().strip()
        if chart_type not in ALLOWED_CHART_TYPES:
            raise ResultValidationError(f"Unsupported chart type: {chart_type}")

        normalized_chart: dict[str, Any] = {
            "type": chart_type,
            "title": _validate_text(
                chart.get("title", "Chart"),
                field_name="chart.title",
                max_length=160,
            ),
            "description": _validate_optional_text(
                chart.get("description"),
                field_name="chart.description",
                max_length=400,
            ),
        }

        for key in ("x", "y", "labels", "values", "data"):
            if key in chart:
                normalized_chart[key] = _limit_chart_value(chart[key])

        for key in ("x_label", "y_label"):
            if key in chart:
                normalized_chart[key] = _validate_optional_text(
                    chart.get(key),
                    field_name=f"chart.{key}",
                    max_length=120,
                )

        normalized_charts.append(normalized_chart)

    return normalized_charts


def _limit_chart_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value[:MAX_CHART_POINTS]]

    if isinstance(value, dict):
        limited = {}
        for key, item in value.items():
            if isinstance(item, list):
                limited[str(key)] = [_make_json_safe(v) for v in item[:MAX_CHART_POINTS]]
            else:
                limited[str(key)] = _make_json_safe(item)
        return limited

    return _make_json_safe(value)


def _validate_text(value: Any, field_name: str, max_length: int) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def _validate_optional_text(value: Any, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None

    return _validate_text(value, field_name=field_name, max_length=max_length)


def _make_json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, bool):
        return bool(value)

    if isinstance(value, int):
        return int(value)

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    if isinstance(value, str):
        if len(value) > MAX_CELL_STRING_LENGTH:
            return value[:MAX_CELL_STRING_LENGTH] + "..."
        return value

    if hasattr(value, "item"):
        try:
            return _make_json_safe(value.item())
        except Exception:
            return str(value)

    if isinstance(value, list):
        return [_make_json_safe(item) for item in value[:MAX_TABLE_ROWS]]

    if isinstance(value, dict):
        return {
            str(key): _make_json_safe(item)
            for key, item in list(value.items())[:MAX_TABLE_COLUMNS]
        }

    return str(value)