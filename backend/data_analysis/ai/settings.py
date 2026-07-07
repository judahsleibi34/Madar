from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
AI_ENV_PATH = BACKEND_ROOT / ".env.ai"

load_dotenv(AI_ENV_PATH)


SUPPORTED_PLANS = {"free", "pro", "enterprise"}
SUPPORTED_PROVIDERS = {"mock", "gemini", "openai", "deepseek"}


@dataclass(frozen=True)
class AIModelConfig:
    provider: str
    model: str
    max_output_tokens: int


@dataclass(frozen=True)
class AILimits:
    daily_messages: int
    daily_code_generations: int
    global_daily_messages: int | None
    global_daily_code_generations: int | None
    max_rows: int
    max_profile_columns: int
    sandbox_timeout_seconds: int
    max_code_length: int
    max_ast_nodes: int


class AISettingsError(RuntimeError):
    pass


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or str(value).strip() == "":
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise AISettingsError(f"{name} must be an integer") from exc


def get_str_env(name: str, default: str = "") -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def normalize_plan_name(plan_name: str | None) -> str:
    normalized = str(plan_name or "free").strip().lower()

    if normalized in {"trial", "free_trial", "free-trial"}:
        return "free"

    if normalized in {"business", "team", "paid"}:
        return "pro"

    if normalized in {"enterprise", "enterprise_plan"}:
        return "enterprise"

    if normalized not in SUPPORTED_PLANS:
        return "free"

    return normalized


def is_ai_enabled() -> bool:
    return get_bool_env("AI_ENABLED", default=True)


def get_app_environment() -> str:
    return get_str_env(
        "APP_ENV",
        get_str_env("ENV", get_str_env("FASTAPI_ENV", "development")),
    ).lower()


def is_production_environment() -> bool:
    return get_app_environment() in {"prod", "production"}


def is_local_ai_exec_allowed() -> bool:
    return get_bool_env(
        "AI_ALLOW_LOCAL_EXEC",
        default=not is_production_environment(),
    )


def is_mock_mode_enabled() -> bool:
    return get_bool_env("AI_MOCK_MODE", default=False)


def get_default_provider() -> str:
    provider = get_str_env("AI_PROVIDER", "gemini").lower()

    if provider not in SUPPORTED_PROVIDERS:
        raise AISettingsError(f"Unsupported AI_PROVIDER: {provider}")

    return provider


def get_provider_for_plan(plan_name: str | None) -> str:
    plan = normalize_plan_name(plan_name)

    if is_mock_mode_enabled():
        return "mock"

    env_name = f"AI_{plan.upper()}_PROVIDER"
    provider = get_str_env(env_name, get_default_provider()).lower()

    if provider not in SUPPORTED_PROVIDERS:
        raise AISettingsError(f"Unsupported provider for {plan}: {provider}")

    return provider


def get_model_for_plan(plan_name: str | None) -> str:
    plan = normalize_plan_name(plan_name)

    if is_mock_mode_enabled():
        return "mock"

    env_name = f"AI_{plan.upper()}_MODEL"

    fallback_model = {
        "free": "gemini-2.5-flash",
        "pro": "gemini-2.5-flash",
        "enterprise": "gpt-5.5",
    }.get(plan, "gemini-2.5-flash")

    return get_str_env(env_name, fallback_model)


def get_model_config_for_plan(plan_name: str | None) -> AIModelConfig:
    return AIModelConfig(
        provider=get_provider_for_plan(plan_name),
        model=get_model_for_plan(plan_name),
        max_output_tokens=get_max_output_tokens_for_plan(plan_name),
    )


def get_max_output_tokens_for_plan(plan_name: str | None) -> int:
    plan = normalize_plan_name(plan_name)
    defaults = {
        "free": 900,
        "pro": 1800,
        "enterprise": 3000,
    }

    return get_int_env(f"AI_{plan.upper()}_MAX_OUTPUT_TOKENS", defaults[plan])


def get_ai_limits_for_plan(plan_name: str | None) -> AILimits:
    plan = normalize_plan_name(plan_name)
    prefix = f"AI_{plan.upper()}"

    default_messages = {
        "free": 5,
        "pro": 100,
        "enterprise": 1000,
    }

    default_code_generations = {
        "free": 1,
        "pro": 25,
        "enterprise": 200,
    }

    default_rows = {
        "free": 3000,
        "pro": 100000,
        "enterprise": 500000,
    }

    default_profile_columns = {
        "free": 20,
        "pro": 80,
        "enterprise": 150,
    }

    default_timeout = {
        "free": 5,
        "pro": 10,
        "enterprise": 15,
    }

    global_daily_messages = None
    global_daily_code_generations = None

    if plan == "free":
        global_daily_messages = get_int_env(
            "AI_FREE_GLOBAL_DAILY_MESSAGES",
            30,
        )
        global_daily_code_generations = get_int_env(
            "AI_FREE_GLOBAL_DAILY_CODE_GENERATIONS",
            6,
        )

    return AILimits(
        daily_messages=get_int_env(
            f"{prefix}_DAILY_MESSAGES",
            default_messages[plan],
        ),
        daily_code_generations=get_int_env(
            f"{prefix}_DAILY_CODE_GENERATIONS",
            default_code_generations[plan],
        ),
        global_daily_messages=global_daily_messages,
        global_daily_code_generations=global_daily_code_generations,
        max_rows=get_int_env(
            f"{prefix}_MAX_ROWS",
            default_rows[plan],
        ),
        max_profile_columns=get_int_env(
            f"{prefix}_MAX_PROFILE_COLUMNS",
            default_profile_columns[plan],
        ),
        sandbox_timeout_seconds=get_int_env(
            f"{prefix}_SANDBOX_TIMEOUT_SECONDS",
            default_timeout[plan],
        ),
        max_code_length=get_int_env(
            "AI_DEFAULT_MAX_CODE_LENGTH",
            16000,
        ),
        max_ast_nodes=get_int_env(
            "AI_DEFAULT_MAX_AST_NODES",
            1200,
        ),
    )


def get_provider_api_key(provider: str) -> str:
    normalized_provider = provider.strip().lower()

    if normalized_provider == "mock":
        return ""

    if normalized_provider == "gemini":
        key = get_str_env("GEMINI_API_KEY", "")
    elif normalized_provider == "openai":
        key = get_str_env("OPENAI_API_KEY", "")
    elif normalized_provider == "deepseek":
        key = get_str_env("DEEPSEEK_API_KEY", "")
    else:
        raise AISettingsError(f"Unsupported provider: {provider}")

    if not key:
        raise AISettingsError(f"Missing API key for provider: {normalized_provider}")

    return key


def get_ai_runtime_summary(plan_name: str | None) -> dict:
    plan = normalize_plan_name(plan_name)
    model_config = get_model_config_for_plan(plan)
    limits = get_ai_limits_for_plan(plan)

    return {
        "ai_enabled": is_ai_enabled(),
        "mock_mode": is_mock_mode_enabled(),
        "plan": plan,
        "provider": model_config.provider,
        "model": model_config.model,
        "max_output_tokens": model_config.max_output_tokens,
        "limits": {
            "daily_messages": limits.daily_messages,
            "daily_code_generations": limits.daily_code_generations,
            "global_daily_messages": limits.global_daily_messages,
            "global_daily_code_generations": limits.global_daily_code_generations,
            "max_rows": limits.max_rows,
            "max_profile_columns": limits.max_profile_columns,
            "sandbox_timeout_seconds": limits.sandbox_timeout_seconds,
            "max_code_length": limits.max_code_length,
            "max_ast_nodes": limits.max_ast_nodes,
        },
    }
