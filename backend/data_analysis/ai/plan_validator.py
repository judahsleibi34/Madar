from __future__ import annotations

from typing import Any


ALLOWED_INTENTS = {
    "chat",
    "analysis",
    "blocked",
    "insufficient_data",
}

ALLOWED_SAFETY_VALUES = {
    "safe",
    "unsafe",
}

ALLOWED_MODES = {
    "predefined",
    "generated_code",
}

ALLOWED_ACTIONS = {
    "summary",
    "missing_values",
    "kpi",
    "groupby",
    "trend",
    "top_n",
    "correlation",
    "distribution",
    "chart",
}

ALLOWED_AGGREGATIONS = {
    "sum",
    "mean",
    "average",
    "avg",
    "count",
    "min",
    "max",
    "median",
    "std",
    "variance",
    "var",
    "nunique",
}

AGGREGATION_ALIASES = {
    "average": "mean",
    "avg": "mean",
    "variance": "var",
}

ALLOWED_CORRELATION_METHODS = {
    "pearson",
    "spearman",
    "kendall",
}

ALLOWED_FREQUENCIES = {
    "day",
    "daily",
    "week",
    "weekly",
    "month",
    "monthly",
    "quarter",
    "quarterly",
    "year",
    "yearly",
}

FREQUENCY_ALIASES = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
    "quarterly": "quarter",
    "yearly": "year",
}

DEFAULT_TOP_N = 10
MAX_TOP_N = 50


class PlanValidationError(ValueError):
    pass


def validate_and_normalize_planner_response(
    response: dict[str, Any],
    allowed_columns: set[str] | list[str] | tuple[str, ...],
) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise PlanValidationError("Planner response must be a dictionary")

    allowed_column_set = {str(column) for column in allowed_columns}

    intent = str(response.get("intent", "")).strip().lower()

    if intent not in ALLOWED_INTENTS:
        raise PlanValidationError(f"Invalid intent: {intent}")

    safety = str(response.get("safety", "safe")).strip().lower()

    if safety not in ALLOWED_SAFETY_VALUES:
        raise PlanValidationError(f"Invalid safety value: {safety}")

    if intent == "chat":
        return _normalize_chat_response(response, safety)

    if intent == "blocked":
        return _normalize_blocked_response(response)

    if intent == "insufficient_data":
        return _normalize_insufficient_data_response(response)

    return _normalize_analysis_response(
        response=response,
        safety=safety,
        allowed_columns=allowed_column_set,
    )


def _normalize_chat_response(response: dict[str, Any], safety: str) -> dict[str, Any]:
    reply = str(response.get("reply", "")).strip()

    if not reply:
        reply = "Tell me what you want to analyze."

    return {
        "intent": "chat",
        "safety": safety,
        "reply": reply,
    }


def _normalize_blocked_response(response: dict[str, Any]) -> dict[str, Any]:
    reason = str(response.get("reason", "")).strip()

    if not reason:
        reason = "This request cannot be completed safely."

    return {
        "intent": "blocked",
        "safety": "unsafe",
        "reason": reason,
    }


def _normalize_insufficient_data_response(response: dict[str, Any]) -> dict[str, Any]:
    reason = str(response.get("reason", "")).strip()

    if not reason:
        reason = "The available columns are not enough to answer this request."

    missing_columns = response.get("missing_columns", [])

    if not isinstance(missing_columns, list):
        missing_columns = [str(missing_columns)]

    return {
        "intent": "insufficient_data",
        "safety": "safe",
        "reason": reason,
        "missing_columns": [str(column) for column in missing_columns],
    }


def _normalize_analysis_response(
    response: dict[str, Any],
    safety: str,
    allowed_columns: set[str],
) -> dict[str, Any]:
    if safety != "safe":
        return _normalize_blocked_response(
            {
                "reason": response.get(
                    "reason",
                    "The requested analysis was marked unsafe.",
                )
            }
        )

    mode = str(response.get("mode", "")).strip().lower()

    if mode not in ALLOWED_MODES:
        raise PlanValidationError(f"Invalid analysis mode: {mode}")

    columns_used = _normalize_columns_list(response.get("columns_used", []))
    _ensure_columns_allowed(columns_used, allowed_columns)

    if mode == "generated_code":
        return _normalize_generated_code_plan(response, columns_used)

    action = str(response.get("action", "")).strip().lower()

    if action not in ALLOWED_ACTIONS:
        raise PlanValidationError(f"Invalid predefined action: {action}")

    raw_plan = response.get("plan", {})

    if not isinstance(raw_plan, dict):
        raw_plan = {}

    normalized_plan = _normalize_predefined_plan(
        action=action,
        raw_plan=raw_plan,
        columns_used=columns_used,
        allowed_columns=allowed_columns,
    )

    return {
        "intent": "analysis",
        "safety": "safe",
        "mode": "predefined",
        "action": action,
        "columns_used": columns_used,
        "plan": normalized_plan,
    }


def _normalize_generated_code_plan(
    response: dict[str, Any],
    columns_used: list[str],
) -> dict[str, Any]:
    analysis_goal = str(response.get("analysis_goal", "")).strip()

    if not analysis_goal:
        analysis_goal = "Perform the requested analysis using the approved columns."

    assumptions = response.get("assumptions", [])

    if not isinstance(assumptions, list):
        assumptions = [str(assumptions)]

    return {
        "intent": "analysis",
        "safety": "safe",
        "mode": "generated_code",
        "columns_used": columns_used,
        "analysis_goal": analysis_goal,
        "assumptions": [str(item) for item in assumptions],
    }


def _normalize_predefined_plan(
    action: str,
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    if action == "summary":
        return _normalize_summary_plan(raw_plan, columns_used, allowed_columns)

    if action == "missing_values":
        return _normalize_missing_values_plan(raw_plan, columns_used, allowed_columns)

    if action == "kpi":
        return _normalize_kpi_plan(raw_plan, columns_used, allowed_columns)

    if action == "groupby":
        return _normalize_groupby_plan(raw_plan, columns_used, allowed_columns)

    if action == "trend":
        return _normalize_trend_plan(raw_plan, columns_used, allowed_columns)

    if action == "top_n":
        return _normalize_top_n_plan(raw_plan, columns_used, allowed_columns)

    if action == "correlation":
        return _normalize_correlation_plan(raw_plan, columns_used, allowed_columns)

    if action == "distribution":
        return _normalize_distribution_plan(raw_plan, columns_used, allowed_columns)

    if action == "chart":
        return _normalize_chart_plan(raw_plan, columns_used, allowed_columns)

    raise PlanValidationError(f"Unsupported action: {action}")


def _normalize_summary_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    columns = _first_present_list(
        raw_plan,
        ["columns", "selected_columns", "summary_columns"],
        fallback=columns_used,
    )

    columns = _normalize_columns_list(columns)
    _ensure_columns_allowed(columns, allowed_columns)

    return {
        "columns": columns,
    }


def _normalize_missing_values_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    columns = _first_present_list(
        raw_plan,
        ["columns", "selected_columns"],
        fallback=columns_used,
    )

    columns = _normalize_columns_list(columns)
    _ensure_columns_allowed(columns, allowed_columns)

    return {
        "columns": columns,
    }


def _normalize_kpi_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    metric = raw_plan.get("metric")

    if isinstance(metric, dict):
        column = _pick_column(
            metric.get("column") or metric.get("field") or metric.get("name"),
            columns_used,
        )
        aggregation = _normalize_aggregation(
            metric.get("aggregation") or metric.get("agg") or raw_plan.get("aggregation")
        )

    else:
        column = _pick_column(
            raw_plan.get("column") or raw_plan.get("metric_column") or raw_plan.get("field"),
            columns_used,
        )
        aggregation = _normalize_aggregation(raw_plan.get("aggregation") or raw_plan.get("agg"))

    _ensure_columns_allowed([column], allowed_columns)

    output = str(
        raw_plan.get("output")
        or raw_plan.get("output_name")
        or f"{column}_{aggregation}"
    )

    return {
        "metric": {
            "column": column,
            "aggregation": aggregation,
            "output": output,
        }
    }


def _normalize_groupby_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    group_by = _first_present_list(
        raw_plan,
        ["group_by", "groupby", "groupby_columns", "group_columns", "dimensions"],
        fallback=[],
    )

    group_by = _normalize_columns_list(group_by)

    metrics = _extract_metrics(raw_plan)

    if not group_by:
        group_by = _guess_groupby_columns(columns_used, metrics)

    if not metrics:
        metrics = _guess_metric_columns(columns_used, group_by)

    _ensure_columns_allowed(group_by, allowed_columns)

    normalized_metrics = []

    for metric in metrics:
        column = _pick_column(
            metric.get("column") or metric.get("field") or metric.get("name"),
            columns_used,
        )
        aggregation = _normalize_aggregation(metric.get("aggregation") or metric.get("agg"))
        output = str(metric.get("output") or f"{column}_{aggregation}")

        _ensure_columns_allowed([column], allowed_columns)

        normalized_metrics.append(
            {
                "column": column,
                "aggregation": aggregation,
                "output": output,
            }
        )

    if not group_by:
        raise PlanValidationError("groupby action requires group_by columns")

    if not normalized_metrics:
        raise PlanValidationError("groupby action requires metrics")

    return {
        "group_by": group_by,
        "metrics": normalized_metrics,
    }


def _normalize_trend_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    date_column = _pick_column(
        raw_plan.get("date_column")
        or raw_plan.get("date")
        or raw_plan.get("time_column")
        or raw_plan.get("x"),
        columns_used,
    )

    metric_data = raw_plan.get("metric", {})

    if isinstance(metric_data, dict):
        metric_column = _pick_column(
            metric_data.get("column") or metric_data.get("field") or raw_plan.get("y"),
            columns_used,
        )
        aggregation = _normalize_aggregation(
            metric_data.get("aggregation") or metric_data.get("agg") or raw_plan.get("aggregation")
        )
    else:
        metric_column = _pick_column(
            raw_plan.get("metric_column") or raw_plan.get("value_column") or raw_plan.get("y"),
            columns_used,
        )
        aggregation = _normalize_aggregation(raw_plan.get("aggregation") or raw_plan.get("agg"))

    frequency = _normalize_frequency(raw_plan.get("frequency") or raw_plan.get("freq") or "month")

    _ensure_columns_allowed([date_column, metric_column], allowed_columns)

    return {
        "date_column": date_column,
        "metric": {
            "column": metric_column,
            "aggregation": aggregation,
            "output": f"{metric_column}_{aggregation}",
        },
        "frequency": frequency,
    }


def _normalize_top_n_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    group_by = _first_present_list(
        raw_plan,
        ["group_by", "groupby", "category", "categories", "dimension"],
        fallback=[],
    )
    group_by = _normalize_columns_list(group_by)

    if not group_by and columns_used:
        group_by = [columns_used[0]]

    metric = raw_plan.get("metric", {})

    if isinstance(metric, dict):
        metric_column = _pick_column(
            metric.get("column") or metric.get("field") or raw_plan.get("metric_column"),
            columns_used,
        )
        aggregation = _normalize_aggregation(
            metric.get("aggregation") or metric.get("agg") or raw_plan.get("aggregation") or "sum"
        )
    else:
        metric_column = _pick_column(
            raw_plan.get("metric_column") or raw_plan.get("value_column"),
            columns_used,
        )
        aggregation = _normalize_aggregation(raw_plan.get("aggregation") or raw_plan.get("agg") or "sum")

    n = _normalize_positive_int(raw_plan.get("n") or raw_plan.get("limit") or DEFAULT_TOP_N)
    n = min(n, MAX_TOP_N)

    sort_order = str(raw_plan.get("sort_order") or raw_plan.get("order") or "desc").lower()
    if sort_order not in {"asc", "desc"}:
        sort_order = "desc"

    _ensure_columns_allowed(group_by + [metric_column], allowed_columns)

    return {
        "group_by": group_by,
        "metric": {
            "column": metric_column,
            "aggregation": aggregation,
            "output": f"{metric_column}_{aggregation}",
        },
        "n": n,
        "sort_order": sort_order,
    }


def _normalize_correlation_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    x = _pick_column(raw_plan.get("x") or raw_plan.get("column_x"), columns_used)
    y = _pick_column(raw_plan.get("y") or raw_plan.get("column_y"), columns_used[1:] or columns_used)

    if x == y:
        if len(columns_used) >= 2:
            y = columns_used[1]
        else:
            raise PlanValidationError("correlation action requires two different columns")

    method = str(raw_plan.get("method") or "pearson").strip().lower()

    if method not in ALLOWED_CORRELATION_METHODS:
        method = "pearson"

    _ensure_columns_allowed([x, y], allowed_columns)

    return {
        "x": x,
        "y": y,
        "method": method,
    }


def _normalize_distribution_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    column = _pick_column(
        raw_plan.get("column") or raw_plan.get("field") or raw_plan.get("x"),
        columns_used,
    )

    _ensure_columns_allowed([column], allowed_columns)

    return {
        "column": column,
    }


def _normalize_chart_plan(
    raw_plan: dict[str, Any],
    columns_used: list[str],
    allowed_columns: set[str],
) -> dict[str, Any]:
    chart_type = str(raw_plan.get("type") or raw_plan.get("chart_type") or "bar").lower()

    if chart_type not in {"bar", "line", "pie", "scatter", "histogram"}:
        chart_type = "bar"

    x = _pick_column(raw_plan.get("x") or raw_plan.get("x_axis"), columns_used)

    y = raw_plan.get("y") or raw_plan.get("y_axis")

    if y:
        y = _pick_column(y, columns_used)
        _ensure_columns_allowed([x, y], allowed_columns)
    else:
        _ensure_columns_allowed([x], allowed_columns)

    return {
        "type": chart_type,
        "x": x,
        "y": y,
    }


def _extract_metrics(raw_plan: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = raw_plan.get("metrics")

    if isinstance(metrics, list):
        return [metric for metric in metrics if isinstance(metric, dict)]

    metric = raw_plan.get("metric")

    if isinstance(metric, dict):
        return [metric]

    aggregation = raw_plan.get("aggregation")

    if isinstance(aggregation, dict):
        return [
            {
                "column": column,
                "aggregation": agg,
                "output": f"{column}_{_normalize_aggregation(agg)}",
            }
            for column, agg in aggregation.items()
        ]

    column = raw_plan.get("column") or raw_plan.get("metric_column") or raw_plan.get("value_column")

    if column:
        return [
            {
                "column": column,
                "aggregation": raw_plan.get("aggregation") or raw_plan.get("agg") or "sum",
            }
        ]

    return []


def _normalize_aggregation(value: Any) -> str:
    aggregation = str(value or "sum").strip().lower()
    aggregation = AGGREGATION_ALIASES.get(aggregation, aggregation)

    if aggregation not in ALLOWED_AGGREGATIONS:
        aggregation = "sum"

    return aggregation


def _normalize_frequency(value: Any) -> str:
    frequency = str(value or "month").strip().lower()
    frequency = FREQUENCY_ALIASES.get(frequency, frequency)

    if frequency not in {"day", "week", "month", "quarter", "year"}:
        frequency = "month"

    return frequency


def _normalize_positive_int(value: Any) -> int:
    try:
        number = int(value)
    except Exception:
        return DEFAULT_TOP_N

    if number <= 0:
        return DEFAULT_TOP_N

    return number


def _first_present_list(
    raw_plan: dict[str, Any],
    keys: list[str],
    fallback: Any,
) -> list[str]:
    for key in keys:
        if key in raw_plan:
            return _normalize_columns_list(raw_plan.get(key))

    return _normalize_columns_list(fallback)


def _normalize_columns_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]

    return [str(value)]


def _pick_column(value: Any, fallback_columns: list[str]) -> str:
    if value is not None and str(value).strip():
        return str(value)

    if fallback_columns:
        return str(fallback_columns[0])

    raise PlanValidationError("A required column is missing")


def _ensure_columns_allowed(columns: list[str], allowed_columns: set[str]) -> None:
    for column in columns:
        if column not in allowed_columns:
            raise PlanValidationError(f"Column is not allowed: {column}")


def _guess_groupby_columns(columns_used: list[str], metrics: list[dict[str, Any]]) -> list[str]:
    metric_columns = {
        str(metric.get("column"))
        for metric in metrics
        if metric.get("column")
    }

    return [
        column
        for column in columns_used
        if column not in metric_columns
    ][:1]


def _guess_metric_columns(columns_used: list[str], group_by: list[str]) -> list[dict[str, Any]]:
    for column in columns_used:
        if column not in group_by:
            return [
                {
                    "column": column,
                    "aggregation": "sum",
                    "output": f"{column}_sum",
                }
            ]

    return []