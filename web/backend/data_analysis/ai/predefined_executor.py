from __future__ import annotations

import math
from typing import Any

import pandas as pd

from data_analysis.ai.result_validator import validate_analysis_result


class PredefinedExecutionError(RuntimeError):
    pass


FREQUENCY_MAP = {
    "day": "D",
    "week": "W",
    "month": "ME",
    "quarter": "QE",
    "year": "YE",
}

MAX_TABLE_ROWS = 100
MAX_CHART_POINTS = 500


def execute_predefined_plan(
    df: pd.DataFrame,
    action: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        raise PredefinedExecutionError("Expected a pandas DataFrame")

    action = str(action).strip().lower()

    if action == "summary":
        result = execute_summary(df, plan)
    elif action == "missing_values":
        result = execute_missing_values(df, plan)
    elif action == "kpi":
        result = execute_kpi(df, plan)
    elif action == "groupby":
        result = execute_groupby(df, plan)
    elif action == "trend":
        result = execute_trend(df, plan)
    elif action == "top_n":
        result = execute_top_n(df, plan)
    elif action == "correlation":
        result = execute_correlation(df, plan)
    elif action == "distribution":
        result = execute_distribution(df, plan)
    elif action == "chart":
        result = execute_chart(df, plan)
    else:
        raise PredefinedExecutionError(f"Unsupported predefined action: {action}")

    return validate_analysis_result(result)


def execute_summary(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    columns = _get_columns_or_all(df, plan.get("columns"))

    metrics = [
        {"label": "Rows", "value": int(len(df))},
        {"label": "Columns", "value": int(len(df.columns))},
        {"label": "Profiled columns", "value": int(len(columns))},
    ]

    rows = []

    for column in columns:
        series = df[column]
        row = {
            "column": column,
            "dtype": str(series.dtype),
            "non_null": int(series.notna().sum()),
            "missing": int(series.isna().sum()),
            "unique": int(series.nunique(dropna=True)),
        }

        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce").dropna()
            if not numeric.empty:
                row.update(
                    {
                        "min": _json_safe(numeric.min()),
                        "max": _json_safe(numeric.max()),
                        "mean": _json_safe(numeric.mean()),
                        "median": _json_safe(numeric.median()),
                    }
                )

        rows.append(row)

    result = {
        "title": "Dataset summary",
        "summary": "A compact summary of the selected dataset columns.",
        "metrics": metrics,
        "tables": [
            {
                "title": "Column summary",
                "columns": list(rows[0].keys()) if rows else [],
                "rows": rows[:MAX_TABLE_ROWS],
            }
        ],
        "charts": [],
    }

    return result


def execute_missing_values(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    columns = _get_columns_or_all(df, plan.get("columns"))
    total_rows = max(int(len(df)), 1)

    rows = []

    for column in columns:
        missing_count = int(df[column].isna().sum())
        missing_percent = round((missing_count / total_rows) * 100, 2)

        rows.append(
            {
                "column": column,
                "missing_count": missing_count,
                "missing_percent": missing_percent,
            }
        )

    rows = sorted(rows, key=lambda item: item["missing_count"], reverse=True)

    result = {
        "title": "Missing values",
        "summary": "Missing value counts and percentages for selected columns.",
        "metrics": [
            {
                "label": "Columns checked",
                "value": len(columns),
            }
        ],
        "tables": [
            {
                "title": "Missing values by column",
                "columns": ["column", "missing_count", "missing_percent"],
                "rows": rows[:MAX_TABLE_ROWS],
            }
        ],
        "charts": [
            {
                "type": "bar",
                "title": "Missing values by column",
                "description": "Top columns by missing value count.",
                "labels": [row["column"] for row in rows[:MAX_CHART_POINTS]],
                "values": [row["missing_count"] for row in rows[:MAX_CHART_POINTS]],
                "x_label": "Column",
                "y_label": "Missing count",
            }
        ],
    }

    return result


def execute_kpi(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    metric = plan.get("metric")

    if not isinstance(metric, dict):
        raise PredefinedExecutionError("kpi plan requires metric")

    column = _require_column(df, metric.get("column"))
    aggregation = str(metric.get("aggregation") or "sum").lower()
    output = str(metric.get("output") or f"{column}_{aggregation}")

    value = _aggregate_series(df[column], aggregation)

    result = {
        "title": "KPI result",
        "summary": f"Calculated {aggregation} for {column}.",
        "metrics": [
            {
                "label": output,
                "value": value,
            }
        ],
        "tables": [],
        "charts": [],
    }

    return result


def execute_groupby(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    group_by = plan.get("group_by") or []
    metrics = plan.get("metrics") or []

    if not isinstance(group_by, list) or not group_by:
        raise PredefinedExecutionError("groupby plan requires group_by")

    if not isinstance(metrics, list) or not metrics:
        raise PredefinedExecutionError("groupby plan requires metrics")

    group_by = [_require_column(df, column) for column in group_by]

    agg_spec = {}

    for metric in metrics:
        if not isinstance(metric, dict):
            continue

        column = _require_column(df, metric.get("column"))
        aggregation = str(metric.get("aggregation") or "sum").lower()
        output = str(metric.get("output") or f"{column}_{aggregation}")

        agg_spec[output] = (column, _pandas_aggregation_name(aggregation))

    if not agg_spec:
        raise PredefinedExecutionError("groupby plan has no valid metrics")

    result_df = (
        df.groupby(group_by, dropna=False)
        .agg(**agg_spec)
        .reset_index()
    )

    metric_columns = list(agg_spec.keys())

    if metric_columns:
        result_df = result_df.sort_values(metric_columns[0], ascending=False)

    result_df = result_df.head(MAX_TABLE_ROWS)

    rows = _dataframe_to_rows(result_df)
    columns = list(result_df.columns)

    chart = None

    if len(group_by) == 1 and metric_columns:
        chart = {
            "type": "bar",
            "title": "Grouped analysis",
            "description": f"{metric_columns[0]} by {group_by[0]}.",
            "labels": result_df[group_by[0]].astype(str).head(MAX_CHART_POINTS).tolist(),
            "values": result_df[metric_columns[0]].head(MAX_CHART_POINTS).apply(_json_safe).tolist(),
            "x_label": group_by[0],
            "y_label": metric_columns[0],
        }

    return {
        "title": "Grouped analysis",
        "summary": f"Grouped by {', '.join(group_by)}.",
        "metrics": [
            {
                "label": "Groups",
                "value": int(len(result_df)),
            }
        ],
        "tables": [
            {
                "title": "Grouped result",
                "columns": columns,
                "rows": rows,
            }
        ],
        "charts": [chart] if chart else [],
    }


def execute_trend(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    date_column = _require_column(df, plan.get("date_column"))

    metric = plan.get("metric")
    if not isinstance(metric, dict):
        raise PredefinedExecutionError("trend plan requires metric")

    metric_column = _require_column(df, metric.get("column"))
    aggregation = str(metric.get("aggregation") or "sum").lower()
    output = str(metric.get("output") or f"{metric_column}_{aggregation}")
    frequency = str(plan.get("frequency") or "month").lower()

    pandas_frequency = FREQUENCY_MAP.get(frequency, "ME")

    temp = df[[date_column, metric_column]].copy()
    temp[date_column] = pd.to_datetime(temp[date_column], errors="coerce")
    temp[metric_column] = pd.to_numeric(temp[metric_column], errors="coerce")
    temp = temp.dropna(subset=[date_column])

    if temp.empty:
        raise PredefinedExecutionError("No valid dates available for trend analysis")

    result_df = (
        temp.set_index(date_column)
        .resample(pandas_frequency)[metric_column]
        .agg(_pandas_aggregation_name(aggregation))
        .reset_index()
        .rename(columns={metric_column: output})
    )

    result_df = result_df.dropna().head(MAX_CHART_POINTS)

    rows = _dataframe_to_rows(result_df.head(MAX_TABLE_ROWS))

    return {
        "title": "Trend analysis",
        "summary": f"Trend of {metric_column} by {frequency}.",
        "metrics": [
            {
                "label": "Periods",
                "value": int(len(result_df)),
            }
        ],
        "tables": [
            {
                "title": "Trend result",
                "columns": list(result_df.columns),
                "rows": rows,
            }
        ],
        "charts": [
            {
                "type": "line",
                "title": "Trend analysis",
                "description": f"{output} by {frequency}.",
                "labels": result_df[date_column].astype(str).tolist(),
                "values": result_df[output].apply(_json_safe).tolist(),
                "x_label": date_column,
                "y_label": output,
            }
        ],
    }


def execute_top_n(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    group_by = plan.get("group_by") or []
    metric = plan.get("metric")

    if not isinstance(group_by, list) or not group_by:
        raise PredefinedExecutionError("top_n plan requires group_by")

    if not isinstance(metric, dict):
        raise PredefinedExecutionError("top_n plan requires metric")

    group_by = [_require_column(df, column) for column in group_by]
    metric_column = _require_column(df, metric.get("column"))
    aggregation = str(metric.get("aggregation") or "sum").lower()
    output = str(metric.get("output") or f"{metric_column}_{aggregation}")
    n = int(plan.get("n") or 10)
    sort_order = str(plan.get("sort_order") or "desc").lower()

    n = max(1, min(n, MAX_TABLE_ROWS))

    result_df = (
        df.groupby(group_by, dropna=False)
        .agg(**{output: (metric_column, _pandas_aggregation_name(aggregation))})
        .reset_index()
    )

    result_df = result_df.sort_values(output, ascending=(sort_order == "asc")).head(n)

    rows = _dataframe_to_rows(result_df)

    return {
        "title": f"Top {n} analysis",
        "summary": f"Top {n} records by {output}.",
        "metrics": [
            {
                "label": "Returned rows",
                "value": int(len(result_df)),
            }
        ],
        "tables": [
            {
                "title": f"Top {n}",
                "columns": list(result_df.columns),
                "rows": rows,
            }
        ],
        "charts": [
            {
                "type": "bar",
                "title": f"Top {n}",
                "description": f"Top {n} by {output}.",
                "labels": result_df[group_by[0]].astype(str).head(MAX_CHART_POINTS).tolist(),
                "values": result_df[output].head(MAX_CHART_POINTS).apply(_json_safe).tolist(),
                "x_label": group_by[0],
                "y_label": output,
            }
        ],
    }


def execute_correlation(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    x = _require_column(df, plan.get("x"))
    y = _require_column(df, plan.get("y"))
    method = str(plan.get("method") or "pearson").lower()

    if method not in {"pearson", "spearman", "kendall"}:
        method = "pearson"

    clean = df[[x, y]].copy()
    clean[x] = pd.to_numeric(clean[x], errors="coerce")
    clean[y] = pd.to_numeric(clean[y], errors="coerce")
    clean = clean.dropna()

    if clean.empty:
        raise PredefinedExecutionError("No valid numeric data for correlation")

    coefficient = clean[x].corr(clean[y], method=method)

    sample = clean.head(MAX_CHART_POINTS)

    return {
        "title": "Correlation analysis",
        "summary": f"Calculated {method} correlation between {x} and {y}.",
        "metrics": [
            {
                "label": f"{method} correlation",
                "value": _json_safe(coefficient),
            },
            {
                "label": "Rows used",
                "value": int(len(clean)),
            },
        ],
        "tables": [],
        "charts": [
            {
                "type": "scatter",
                "title": "Correlation scatter plot",
                "description": f"{x} versus {y}.",
                "x": sample[x].apply(_json_safe).tolist(),
                "y": sample[y].apply(_json_safe).tolist(),
                "x_label": x,
                "y_label": y,
            }
        ],
    }


def execute_distribution(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    column = _require_column(df, plan.get("column"))
    series = df[column]

    if pd.api.types.is_numeric_dtype(series) or _numeric_conversion_ratio(series) >= 0.8:
        numeric = pd.to_numeric(series, errors="coerce").dropna()

        if numeric.empty:
            raise PredefinedExecutionError("No valid numeric values for distribution")

        rows = [
            {"stat": "count", "value": int(numeric.count())},
            {"stat": "mean", "value": _json_safe(numeric.mean())},
            {"stat": "median", "value": _json_safe(numeric.median())},
            {"stat": "std", "value": _json_safe(numeric.std())},
            {"stat": "min", "value": _json_safe(numeric.min())},
            {"stat": "max", "value": _json_safe(numeric.max())},
            {"stat": "q1", "value": _json_safe(numeric.quantile(0.25))},
            {"stat": "q3", "value": _json_safe(numeric.quantile(0.75))},
        ]

        return {
            "title": "Distribution analysis",
            "summary": f"Numeric distribution summary for {column}.",
            "metrics": [
                {
                    "label": "Valid numeric rows",
                    "value": int(numeric.count()),
                }
            ],
            "tables": [
                {
                    "title": "Distribution statistics",
                    "columns": ["stat", "value"],
                    "rows": rows,
                }
            ],
            "charts": [
                {
                    "type": "histogram",
                    "title": "Distribution",
                    "description": f"Distribution of {column}.",
                    "values": numeric.head(MAX_CHART_POINTS).apply(_json_safe).tolist(),
                    "x_label": column,
                    "y_label": "Frequency",
                }
            ],
        }

    value_counts = series.dropna().astype(str).value_counts().head(MAX_TABLE_ROWS)

    rows = [
        {
            "value": value,
            "count": int(count),
        }
        for value, count in value_counts.items()
    ]

    return {
        "title": "Distribution analysis",
        "summary": f"Category distribution for {column}.",
        "metrics": [
            {
                "label": "Unique values",
                "value": int(series.nunique(dropna=True)),
            }
        ],
        "tables": [
            {
                "title": "Value counts",
                "columns": ["value", "count"],
                "rows": rows,
            }
        ],
        "charts": [
            {
                "type": "bar",
                "title": "Value counts",
                "description": f"Top values for {column}.",
                "labels": [row["value"] for row in rows[:MAX_CHART_POINTS]],
                "values": [row["count"] for row in rows[:MAX_CHART_POINTS]],
                "x_label": column,
                "y_label": "Count",
            }
        ],
    }


def execute_chart(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    chart_type = str(plan.get("type") or "bar").lower()
    x = _require_column(df, plan.get("x"))
    y = plan.get("y")

    if chart_type == "histogram":
        return execute_distribution(df, {"column": x})

    if y:
        y = _require_column(df, y)

    if chart_type == "scatter":
        if not y:
            raise PredefinedExecutionError("scatter chart requires y column")

        clean = df[[x, y]].copy().dropna().head(MAX_CHART_POINTS)

        return {
            "title": "Scatter chart",
            "summary": f"Scatter chart of {x} and {y}.",
            "metrics": [
                {
                    "label": "Points",
                    "value": int(len(clean)),
                }
            ],
            "tables": [],
            "charts": [
                {
                    "type": "scatter",
                    "title": "Scatter chart",
                    "description": f"{x} versus {y}.",
                    "x": clean[x].apply(_json_safe).tolist(),
                    "y": clean[y].apply(_json_safe).tolist(),
                    "x_label": x,
                    "y_label": y,
                }
            ],
        }

    if y:
        temp = df[[x, y]].copy()
        temp[y] = pd.to_numeric(temp[y], errors="coerce")
        grouped = (
            temp.groupby(x, dropna=False)[y]
            .sum()
            .reset_index()
            .sort_values(y, ascending=False)
            .head(MAX_CHART_POINTS)
        )

        values = grouped[y].apply(_json_safe).tolist()
        labels = grouped[x].astype(str).tolist()

    else:
        counts = df[x].dropna().astype(str).value_counts().head(MAX_CHART_POINTS)
        labels = counts.index.astype(str).tolist()
        values = [int(value) for value in counts.values]

    if chart_type not in {"bar", "line", "pie"}:
        chart_type = "bar"

    return {
        "title": "Chart",
        "summary": f"{chart_type} chart for {x}.",
        "metrics": [],
        "tables": [],
        "charts": [
            {
                "type": chart_type,
                "title": "Chart",
                "description": f"{chart_type} chart for {x}.",
                "labels": labels,
                "values": values,
                "x_label": x,
                "y_label": y or "Count",
            }
        ],
    }


def _get_columns_or_all(df: pd.DataFrame, columns: Any) -> list[str]:
    if not columns:
        return [str(column) for column in df.columns]

    if isinstance(columns, str):
        columns = [columns]

    if not isinstance(columns, list):
        raise PredefinedExecutionError("columns must be a list")

    return [_require_column(df, column) for column in columns]


def _require_column(df: pd.DataFrame, column: Any) -> str:
    column = str(column or "").strip()

    if not column:
        raise PredefinedExecutionError("Column is required")

    if column not in df.columns:
        raise PredefinedExecutionError(f"Column does not exist: {column}")

    return column


def _aggregate_series(series: pd.Series, aggregation: str) -> Any:
    aggregation = _pandas_aggregation_name(aggregation)

    if aggregation in {"sum", "mean", "median", "std", "var", "min", "max"}:
        numeric = pd.to_numeric(series, errors="coerce")
        value = getattr(numeric, aggregation)()
        return _json_safe(value)

    if aggregation == "count":
        return int(series.count())

    if aggregation == "nunique":
        return int(series.nunique(dropna=True))

    raise PredefinedExecutionError(f"Unsupported aggregation: {aggregation}")


def _pandas_aggregation_name(aggregation: str) -> str:
    aggregation = str(aggregation or "sum").strip().lower()

    aliases = {
        "average": "mean",
        "avg": "mean",
        "variance": "var",
    }

    aggregation = aliases.get(aggregation, aggregation)

    allowed = {
        "sum",
        "mean",
        "count",
        "min",
        "max",
        "median",
        "std",
        "var",
        "nunique",
    }

    if aggregation not in allowed:
        return "sum"

    return aggregation


def _dataframe_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []

    for record in df.to_dict(orient="records"):
        rows.append(
            {
                str(key): _json_safe(value)
                for key, value in record.items()
            }
        )

    return rows


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            return str(value)

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    if isinstance(value, int):
        return int(value)

    if isinstance(value, bool):
        return bool(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    return str(value)


def _numeric_conversion_ratio(series: pd.Series) -> float:
    non_null = series.dropna()

    if non_null.empty:
        return 0.0

    converted = pd.to_numeric(non_null, errors="coerce")

    return float(converted.notna().mean())