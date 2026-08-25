"""Typed, redaction-safe startup configuration contract."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


ConfigClass = Literal["required", "optional", "development-only", "production-only", "secret", "deprecated"]

CONFIG_CLASSIFICATION: dict[str, ConfigClass] = {
    "APP_ENV": "required",
    "SUPABASE_URL": "required",
    "SUPABASE_ANON_KEY": "secret",
    "SUPABASE_SERVICE_KEY": "secret",
    "CSRF_SECRET": "secret",
    "COOKIE_SECURE": "production-only",
    "COOKIE_SAMESITE": "required",
    "FRONTEND_URLS": "required",
    "REDIS_URL": "required",
    "RATE_LIMIT_ENABLED": "required",
    "RATE_LIMIT_FAIL_OPEN": "production-only",
    "ADMIN_MFA_LOGIN_ENFORCEMENT": "production-only",
    "EMAIL_CHANNEL_ENABLED": "optional",
    "SMTP_HOST": "secret",
    "SMTP_USERNAME": "secret",
    "SMTP_PASSWORD": "secret",
    "SMTP_FROM_EMAIL": "optional",
    "VAPID_PRIVATE_KEY": "secret",
    "MADAR_RELEASE_SHA": "required",
    "MADAR_BUILD_TIMESTAMP": "required",
    "SCHEMA_COMPATIBLE_MIN": "required",
    "SCHEMA_COMPATIBLE_MAX": "required",
    "BACKUP_FRESHNESS_REQUIRED": "production-only",
    "BACKUP_FRESHNESS_MARKER": "production-only",
    "DATA_DELETION_WORKER_ENABLED": "production-only",
    "DATA_DELETION_WORKER_REQUIRED": "production-only",
    "DATA_DELETION_WORKER_HEALTH_URL": "production-only",
    "FRONTEND_URL": "deprecated",
}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
        raise RuntimeError(f"configuration value is invalid: {name}")
    return normalized in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RuntimeConfiguration:
    environment: str
    release_sha: str
    schema_min: int
    schema_max: int
    email_channel_enabled: bool


def validate_runtime_configuration() -> RuntimeConfiguration:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    if environment not in {"development", "test", "prod", "production"}:
        raise RuntimeError("configuration value is invalid: APP_ENV")
    production = environment in {"prod", "production"}
    release_sha = os.getenv("MADAR_RELEASE_SHA", "development").strip()
    try:
        schema_min = int(os.getenv("SCHEMA_COMPATIBLE_MIN", "81"))
        schema_max = int(os.getenv("SCHEMA_COMPATIBLE_MAX", "83"))
    except ValueError as error:
        raise RuntimeError("schema compatibility configuration is invalid") from error
    if schema_min <= 0 or schema_max < schema_min:
        raise RuntimeError("schema compatibility configuration is invalid")
    email_enabled = env_bool("EMAIL_CHANNEL_ENABLED", False)
    if production:
        required = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "CSRF_SECRET", "FRONTEND_URLS", "REDIS_URL")
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            # Key names are safe; values are never included.
            raise RuntimeError("required production configuration is missing: " + ",".join(missing))
        if len(os.getenv("CSRF_SECRET", "")) < 32:
            raise RuntimeError("production secret is too short: CSRF_SECRET")
        if not env_bool("COOKIE_SECURE", True):
            raise RuntimeError("production cookie security is disabled")
        if env_bool("RATE_LIMIT_FAIL_OPEN", False):
            raise RuntimeError("production rate limiting is configured fail-open")
        if not env_bool("ADMIN_MFA_LOGIN_ENFORCEMENT", False):
            raise RuntimeError("administrator MFA login enforcement is disabled")
        if email_enabled and not all(os.getenv(name, "").strip() for name in ("SMTP_HOST", "SMTP_FROM_EMAIL")):
            raise RuntimeError("enabled email channel is missing SMTP configuration")
        if release_sha in {"", "development", "unknown"}:
            raise RuntimeError("production release identity is missing")
    return RuntimeConfiguration(environment, release_sha, schema_min, schema_max, email_enabled)


def redacted_configuration_inventory() -> list[dict[str, str | bool]]:
    return [
        {"name": name, "classification": classification, "configured": bool(os.getenv(name, "").strip())}
        for name, classification in sorted(CONFIG_CLASSIFICATION.items())
    ]
