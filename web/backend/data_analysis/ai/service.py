from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import re

from data_analysis.ai.code_validator import CodeValidationError, validate_generated_code
from data_analysis.ai.plan_validator import (
    PlanValidationError,
    validate_and_normalize_planner_response,
)
from data_analysis.ai.planner import AIPlannerError, ask_code_generator, ask_planner
from data_analysis.ai.predefined_executor import (
    PredefinedExecutionError,
    execute_predefined_plan,
)
from data_analysis.ai.profile import build_dataframe_profile
from data_analysis.ai.profile import SENSITIVE_COLUMN_KEYWORDS
from data_analysis.ai.result_validator import ResultValidationError
from data_analysis.ai.sandbox import SandboxExecutionError, run_generated_code_locally
from data_analysis.ai.settings import get_ai_limits_for_plan, is_ai_enabled


class AIAnalysisServiceError(RuntimeError):
    pass


STRICT_BLOCKED_REQUEST_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(read|open|load|parse|inspect|scan|view|show|print|dump)\b"
            r".{0,40}\b(file|files|document|documents|csv|excel|xlsx|xls|json|raw upload)\b",
            re.IGNORECASE,
        ),
        "I can analyze approved dataset columns, but I cannot read or expose raw file contents.",
    ),
    (
        re.compile(
            r"\b(show|print|list|dump|return|give|export|download|copy)\b"
            r".{0,50}\b(all|every|full|entire|complete|raw)\b"
            r".{0,50}\b(row|rows|record|records|dataset|dataframe|data|file)\b",
            re.IGNORECASE,
        ),
        "I cannot expose the full dataset or raw rows. Ask for an aggregate statistical summary instead.",
    ),
    (
        re.compile(
            r"\b(raw data|full data|entire dataset|complete dataset|all rows|every row|"
            r"all records|every record|data dump|dump the data|export the data|export dataset)\b",
            re.IGNORECASE,
        ),
        "I cannot expose the full dataset or raw rows. Ask for an aggregate statistical summary instead.",
    ),
    (
        re.compile(
            r"\b(chart|charts|plot|plots|graph|graphs|visual|visualization|image|images|theme|themes)\b",
            re.IGNORECASE,
        ),
        "I only answer statistical calculation questions. I cannot create, read, or explain charts or visual themes.",
    ),
    (
        re.compile(
            r"\b(ignore|bypass|override|disable)\b.{0,40}\b(policy|policies|rules|safety|guardrail|instructions)\b",
            re.IGNORECASE,
        ),
        "I cannot bypass safety rules or system instructions.",
    ),
)

SENSITIVE_REQUEST_TERMS = {
    str(keyword).strip().lower().replace("_", " ")
    for keyword in SENSITIVE_COLUMN_KEYWORDS
    if str(keyword).strip()
} | {
    "api key",
    "access key",
    "secret key",
    "private key",
    "credit card",
    "debit card",
    "card number",
    "identity number",
    "national id",
    "full name",
    "first name",
    "last name",
    "phone number",
    "email address",
}


def run_ai_analysis_on_dataframe(
    df: pd.DataFrame,
    user_message: str,
    user_plan: str | None = "free",
    dataset_name: str | None = None,
    daily_messages_used: int | None = None,
    daily_code_generations_used: int | None = None,
    global_daily_messages_used: int | None = None,
    global_daily_code_generations_used: int | None = None,
    reserve_code_generation: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    if not is_ai_enabled():
        return _error_response(
            code="ai_disabled",
            message="AI analysis is currently disabled.",
        )

    if not isinstance(df, pd.DataFrame):
        return _error_response(
            code="invalid_dataframe",
            message="AI analysis expected a valid dataframe.",
        )

    if not str(user_message or "").strip():
        return _chat_response("Tell me what you want to analyze.")

    strict_block = _strict_request_block(user_message)

    if strict_block:
        return strict_block

    limits = get_ai_limits_for_plan(user_plan)

    if (
        daily_messages_used is None
        or daily_code_generations_used is None
        or global_daily_messages_used is None
        or global_daily_code_generations_used is None
    ):
        return _error_response(
            code="usage_counters_required",
            message="AI usage counters are required before provider calls.",
        )

    limit_error = _check_usage_limits(
        limits=limits,
        daily_messages_used=daily_messages_used,
        daily_code_generations_used=daily_code_generations_used,
        global_daily_messages_used=global_daily_messages_used,
        global_daily_code_generations_used=global_daily_code_generations_used,
    )

    if limit_error:
        return limit_error

    if len(df) > limits.max_rows:
        return _error_response(
            code="row_limit_exceeded",
            message=(
                f"This dataset has {len(df)} rows. "
                f"Your current plan allows up to {limits.max_rows} rows for AI analysis."
            ),
        )

    try:
        allowed_columns_error = _validate_allowed_columns_available(
            df=df,
            dataset_name=dataset_name,
            limits=limits,
        )

        if allowed_columns_error:
            return allowed_columns_error

        full_profile = build_dataframe_profile(
            df=df,
            dataset_name=dataset_name,
            max_columns=limits.max_profile_columns,
            max_sample_rows=3,
            max_sample_values=5,
            max_top_values=5,
        )

        allowed_columns = _get_non_sensitive_columns(full_profile)

        if not allowed_columns:
            return _error_response(
                code="no_allowed_columns",
                message="No safe columns are available for AI analysis.",
            )

        compact_profile = build_compact_profile(full_profile)

        raw_plan = ask_planner(
            compact_profile=compact_profile,
            allowed_columns=allowed_columns,
            user_message=user_message,
            user_plan=user_plan,
        )

        normalized_plan = validate_and_normalize_planner_response(
            response=raw_plan,
            allowed_columns=allowed_columns,
        )

        return _execute_normalized_plan(
            df=df,
            normalized_plan=normalized_plan,
            full_profile=full_profile,
            user_plan=user_plan,
            limits=limits,
            daily_code_generations_used=daily_code_generations_used,
            global_daily_code_generations_used=global_daily_code_generations_used,
            reserve_code_generation=reserve_code_generation,
        )

    except PlanValidationError as exc:
        return _error_response(
            code="invalid_ai_plan",
            message="The AI planner returned an invalid or unsafe plan.",
        )

    except AIPlannerError as exc:
        return _error_response(
            code="ai_provider_error",
            message="The AI provider could not complete the request.",
        )

    except Exception as exc:
        return _error_response(
            code="ai_analysis_failed",
            message="AI analysis failed unexpectedly.",
        )


def validate_ai_request_before_provider(
    *,
    df: pd.DataFrame,
    user_message: str,
    user_plan: str | None = "free",
    dataset_name: str | None = None,
) -> dict[str, Any] | None:
    if not is_ai_enabled():
        return _error_response(
            code="ai_disabled",
            message="AI analysis is currently disabled.",
        )

    if not isinstance(df, pd.DataFrame):
        return _error_response(
            code="invalid_dataframe",
            message="AI analysis expected a valid dataframe.",
        )

    if not str(user_message or "").strip():
        return _chat_response("Tell me what you want to analyze.")

    strict_block = _strict_request_block(user_message)

    if strict_block:
        return strict_block

    limits = get_ai_limits_for_plan(user_plan)

    if len(df) > limits.max_rows:
        return _error_response(
            code="row_limit_exceeded",
            message=(
                f"This dataset has {len(df)} rows. "
                f"Your current plan allows up to {limits.max_rows} rows for AI analysis."
            ),
        )

    return _validate_allowed_columns_available(
        df=df,
        dataset_name=dataset_name,
        limits=limits,
    )


def _validate_allowed_columns_available(
    *,
    df: pd.DataFrame,
    dataset_name: str | None,
    limits: Any,
) -> dict[str, Any] | None:
    full_profile = build_dataframe_profile(
        df=df,
        dataset_name=dataset_name,
        max_columns=limits.max_profile_columns,
        max_sample_rows=3,
        max_sample_values=5,
        max_top_values=5,
    )

    if not _get_non_sensitive_columns(full_profile):
        return _error_response(
            code="no_allowed_columns",
            message="No safe columns are available for AI analysis.",
        )

    return None


def build_compact_profile(full_profile: dict[str, Any]) -> dict[str, Any]:
    columns = []
    sensitive_count = 0

    for column in full_profile.get("columns", []):
        name = str(column.get("name", "")).strip()
        kind = _compact_kind(column.get("kind"))

        if not name:
            continue

        if column.get("is_sensitive"):
            sensitive_count += 1
            continue

        columns.append(
            [
                name,
                kind,
            ]
        )

    return {
        "rows": int(full_profile.get("row_count", 0)),
        "column_count": int(full_profile.get("column_count", 0)),
        "profiled_column_count": int(full_profile.get("profiled_column_count", len(columns))),
        "columns_truncated": bool(full_profile.get("columns_truncated", False)),
        "sensitive_columns_omitted": sensitive_count,
        "cols": columns,
    }


def _strict_request_block(user_message: str) -> dict[str, Any] | None:
    message = str(user_message or "").strip()

    if not message:
        return None

    normalized = _normalize_request_text(message)

    if _asks_to_reveal_sensitive_values(normalized):
        return _blocked_response(
            "I cannot reveal sensitive or identifying values. Ask for aggregated, anonymized analysis instead."
        )

    for pattern, reason in STRICT_BLOCKED_REQUEST_PATTERNS:
        if pattern.search(message):
            return _blocked_response(reason)

    return None


def _normalize_request_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("_", " ").lower()).strip()


def _asks_to_reveal_sensitive_values(normalized_message: str) -> bool:
    reveal_verbs = {
        "show",
        "list",
        "print",
        "give",
        "return",
        "display",
        "export",
        "download",
        "extract",
        "reveal",
        "find",
        "lookup",
        "search",
    }

    if not any(re.search(rf"\b{re.escape(verb)}\b", normalized_message) for verb in reveal_verbs):
        return False

    return any(
        re.search(rf"\b{re.escape(term)}\b", normalized_message)
        for term in SENSITIVE_REQUEST_TERMS
        if len(term) >= 2
    )


def _execute_normalized_plan(
    df: pd.DataFrame,
    normalized_plan: dict[str, Any],
    full_profile: dict[str, Any],
    user_plan: str | None,
    limits: Any,
    daily_code_generations_used: int,
    global_daily_code_generations_used: int,
    reserve_code_generation: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    intent = normalized_plan.get("intent")

    if intent == "chat":
        return _chat_response(normalized_plan.get("reply", "Tell me what you want to analyze."))

    if intent == "blocked":
        return _blocked_response(
            normalized_plan.get("reason", "This request cannot be completed safely.")
        )

    if intent == "insufficient_data":
        return _error_response(
            code="insufficient_data",
            message=normalized_plan.get(
                "reason",
                "The available data is not enough to answer this request.",
            ),
            details={
                "missing_columns": normalized_plan.get("missing_columns", []),
            },
        )

    if intent != "analysis":
        return _error_response(
            code="unsupported_intent",
            message="Unsupported AI intent.",
        )

    mode = normalized_plan.get("mode")

    if mode == "predefined":
        return _run_predefined_mode(
            df=df,
            normalized_plan=normalized_plan,
        )

    if mode == "generated_code":
        code_limit_error = _check_code_generation_limits(
            limits=limits,
            daily_code_generations_used=daily_code_generations_used,
            global_daily_code_generations_used=global_daily_code_generations_used,
        )

        if code_limit_error:
            return code_limit_error

        if reserve_code_generation is not None and not reserve_code_generation():
            return _error_response(
                code="daily_code_generation_limit_reached",
                message="You reached today’s advanced AI analysis limit. You can still use basic predefined analysis.",
            )

        return _run_generated_code_mode(
            df=df,
            normalized_plan=normalized_plan,
            full_profile=full_profile,
            user_plan=user_plan,
            limits=limits,
        )

    return _error_response(
        code="unsupported_mode",
        message="Unsupported AI analysis mode.",
    )


def _run_predefined_mode(
    df: pd.DataFrame,
    normalized_plan: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = execute_predefined_plan(
            df=df,
            action=normalized_plan["action"],
            plan=normalized_plan["plan"],
        )

        return _success_response(
            mode="predefined",
            result=result,
            plan=normalized_plan,
        )

    except PredefinedExecutionError as exc:
        return _error_response(
            code="predefined_execution_failed",
            message="The predefined analysis could not be executed.",
        )

    except ResultValidationError as exc:
        return _error_response(
            code="invalid_predefined_result",
            message="The predefined analysis result was not in a safe format.",
        )


def _run_generated_code_mode(
    df: pd.DataFrame,
    normalized_plan: dict[str, Any],
    full_profile: dict[str, Any],
    user_plan: str | None,
    limits: Any,
) -> dict[str, Any]:
    approved_columns = normalized_plan.get("columns_used", [])

    if not approved_columns:
        return _error_response(
            code="missing_approved_columns",
            message="Generated-code analysis requires approved columns.",
        )

    try:
        code_response = ask_code_generator(
            full_profile=full_profile,
            approved_columns=approved_columns,
            analysis_goal=normalized_plan.get("analysis_goal", ""),
            assumptions=normalized_plan.get("assumptions", []),
            user_plan=user_plan,
        )

        mode = str(code_response.get("mode", "")).strip().lower()

        if mode == "insufficient_data":
            return _error_response(
                code="code_generation_insufficient_data",
                message=code_response.get(
                    "reason",
                    "The code generator did not have enough data.",
                ),
            )

        if mode != "generated_code":
            return _error_response(
                code="invalid_code_generation_response",
                message="The code generator returned an unsupported response.",
            )

        code = str(code_response.get("code", "")).strip()

        validate_generated_code(
            code=code,
            approved_columns=set(approved_columns),
            require_result_variable=True,
            max_code_length=limits.max_code_length,
            max_ast_nodes=limits.max_ast_nodes,
        )

        result = run_generated_code_locally(
            df=df,
            code=code,
            approved_columns=set(approved_columns),
            timeout_seconds=limits.sandbox_timeout_seconds,
        )

        return _success_response(
            mode="generated_code",
            result=result,
            plan=normalized_plan,
            generated_code=code,
        )

    except AIPlannerError as exc:
        return _error_response(
            code="code_generation_failed",
            message="The AI code generator could not complete the request.",
        )

    except CodeValidationError as exc:
        return _error_response(
            code="generated_code_blocked",
            message="The generated analysis code was blocked by safety rules.",
        )

    except SandboxExecutionError as exc:
        return _error_response(
            code="sandbox_execution_failed",
            message="The generated analysis could not be executed safely.",
        )

    except ResultValidationError as exc:
        return _error_response(
            code="invalid_generated_result",
            message="The generated analysis result was not in a safe format.",
        )


def _get_non_sensitive_columns(full_profile: dict[str, Any]) -> list[str]:
    columns = []

    for column in full_profile.get("columns", []):
        name = str(column.get("name", "")).strip()

        if not name:
            continue

        if column.get("is_sensitive"):
            continue

        columns.append(name)

    return columns


def _compact_kind(kind: Any) -> str:
    value = str(kind or "").strip().lower()

    if value in {"numeric", "numeric_like_text"}:
        return "num"

    if value in {"datetime", "datetime_like_text"}:
        return "date"

    if value in {"categorical", "boolean"}:
        return "cat"

    if value in {"text", "long_text"}:
        return "text"

    if value == "empty":
        return "empty"

    return "unknown"


def _check_usage_limits(
    limits: Any,
    daily_messages_used: int,
    daily_code_generations_used: int,
    global_daily_messages_used: int,
    global_daily_code_generations_used: int,
) -> dict[str, Any] | None:
    if daily_messages_used >= limits.daily_messages:
        return _error_response(
            code="daily_ai_message_limit_reached",
            message="You reached today’s AI analysis limit. Try again tomorrow or upgrade for more AI analysis.",
        )

    if (
        limits.global_daily_messages is not None
        and global_daily_messages_used >= limits.global_daily_messages
    ):
        return _error_response(
            code="global_free_ai_limit_reached",
            message="The free AI analysis pool is busy today. Try again later or upgrade for more access.",
        )

    return None


def _check_code_generation_limits(
    limits: Any,
    daily_code_generations_used: int,
    global_daily_code_generations_used: int,
) -> dict[str, Any] | None:
    if daily_code_generations_used >= limits.daily_code_generations:
        return _error_response(
            code="daily_code_generation_limit_reached",
            message="You reached today’s advanced AI analysis limit. You can still use basic predefined analysis.",
        )

    if (
        limits.global_daily_code_generations is not None
        and global_daily_code_generations_used >= limits.global_daily_code_generations
    ):
        return _error_response(
            code="global_free_code_generation_limit_reached",
            message="The free advanced AI analysis pool is busy today. Try again later or upgrade for more access.",
        )

    return None


def _success_response(
    mode: str,
    result: dict[str, Any],
    plan: dict[str, Any],
    generated_code: str | None = None,
) -> dict[str, Any]:
    response = {
        "success": True,
        "type": "analysis_result",
        "mode": mode,
        "result": _remove_chart_outputs(result),
        "plan": plan,
    }

    if generated_code is not None:
        response["generated_code"] = generated_code

    return response


def _remove_chart_outputs(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return result

    cleaned = dict(result)
    cleaned["charts"] = []
    return cleaned


def _chat_response(reply: str) -> dict[str, Any]:
    return {
        "success": True,
        "type": "chat",
        "reply": str(reply),
    }


def _blocked_response(reason: str) -> dict[str, Any]:
    return {
        "success": False,
        "type": "blocked",
        "code": "blocked_request",
        "message": str(reason),
    }


def _error_response(
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    response = {
        "success": False,
        "type": "error",
        "code": code,
        "message": message,
    }

    if details is not None:
        response["details"] = details

    return response
