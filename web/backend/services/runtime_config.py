"""Typed, redaction-safe startup configuration contract."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit


ConfigClass = Literal["required", "optional", "development-only", "production-only", "secret", "deprecated", "unknown"]

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

# High-risk operational configuration is classified here even when the
# integration is optional. This keeps the generated inventory useful without
# making roadmap providers mandatory at startup.
CONFIG_CLASSIFICATION.update({name: "secret" for name in (
    "ADMIN_ACCOUNT_ACCESS_SECRET", "BILLING_WEBHOOK_SECRET",
    "CALENDAR_CREDENTIALS_SECRET", "GEMINI_API_KEY", "METRICS_TOKEN",
    "OPENAI_API_KEY", "PENDING_VERIFICATION_SECRET", "RESERVATION_TOKEN_SECRET",
    "SECRET_KEY", "SESSION_ACTIVITY_SECRET", "VERIFICATION_HASH_SECRET",
    "WEB_PUSH_VAPID_PRIVATE_KEY", "WEB_PUSH_VAPID_PUBLIC_KEY",
)})
CONFIG_CLASSIFICATION.update({name: "production-only" for name in (
    "AI_ALLOW_LOCAL_EXEC", "AI_ISOLATED_WORKER_ENABLED", "ALLOW_REMOTE_DATASET_URLS",
    "CALENDAR_FEATURE_ENABLED", "CALENDAR_SYNC_WORKER_ENABLED",
    "NOTIFICATION_WORKER_ENABLED", "PARSER_ISOLATED_WORKER_ENABLED",
    "PUBLIC_SITE_DOMAIN", "PYGWALKER_TELEMETRY_ENABLED", "STRUCTURED_LOGS",
    "TRUSTED_PROXY_IPS", "WEB_PUSH_VAPID_SUBJECT",
)})
CONFIG_CLASSIFICATION.update({name: "development-only" for name in (
    "COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS", "MADAR_TEST_REPOSITORY_ROOT",
    "MADAR_TEST_TENANT_LIFECYCLE_LOOKUPS", "POSTGRES_TEST_URL",
)})
CONFIG_CLASSIFICATION.update({name: "deprecated" for name in (
    "ENV", "ENVIRONMENT", "FASTAPI_ENV", "GENERATED_CHARTS_DIR", "UPLOADS_DIR",
    "VAPID_PRIVATE_KEY",
)})
CONFIG_CLASSIFICATION.update({name: "optional" for name in (
    "BACKUP_MAX_AGE_SECONDS", "BUILDER_ASSET_BUCKET", "BUILDER_ASSET_MAX_BYTES",
    "BUILDER_DOCUMENT_MAX_BYTES", "BUILDER_VIDEO_MAX_BYTES",
    "CSRF_TOKEN_MAX_AGE_SECONDS", "CSRF_TRUSTED_ORIGINS", "DATA_UPLOAD_DIR",
    "LOG_LEVEL", "MADAR_ALERT_HOOK", "MADAR_MIGRATIONS_DIR",
    "MADAR_UPLOAD_WORKSPACE_DIR", "MAX_DATASET_UPLOAD_BYTES", "MAX_REMOTE_DATA_BYTES",
    "MAX_UPLOAD_BYTES", "NOTIFICATION_EMAIL_MAX_DEAD",
    "NOTIFICATION_QUEUE_MAX_AGE_SECONDS", "NOTIFICATION_QUEUE_MAX_DEAD",
    "NOTIFICATION_QUEUE_MAX_DEPTH", "PRIVATE_CHARTS_DIR", "PUBLIC_UPLOADS_DIR",
    "READINESS_CACHE_SECONDS", "READINESS_TIMEOUT_SECONDS",
    "REMOTE_INGESTION_WORKER_URL", "SMTP_PORT", "SMTP_USE_TLS",
    "STORAGE_DISK_FREE_FLOOR_BYTES", "SUPABASE_HTTP_TIMEOUT_SECONDS",
)})


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
        if not env_bool("RATE_LIMIT_ENABLED", True):
            raise RuntimeError("production rate limiting is disabled")
        if env_bool("RATE_LIMIT_FAIL_OPEN", False):
            raise RuntimeError("production rate limiting is configured fail-open")
        if not env_bool("ADMIN_MFA_LOGIN_ENFORCEMENT", False):
            raise RuntimeError("administrator MFA login enforcement is disabled")
        if email_enabled and not all(os.getenv(name, "").strip() for name in ("SMTP_HOST", "SMTP_FROM_EMAIL")):
            raise RuntimeError("enabled email channel is missing SMTP configuration")
        if not re.fullmatch(r"[0-9a-f]{40}", release_sha):
            raise RuntimeError("production release identity is missing")
        origins = os.getenv("CSRF_TRUSTED_ORIGINS", "").strip() or os.getenv("FRONTEND_URLS", "")
        for origin in (value.strip() for value in origins.split(",") if value.strip()):
            parsed = urlsplit(origin)
            if "*" in origin or parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}:
                raise RuntimeError("production trusted origin configuration is unsafe")
        if not os.getenv("REDIS_URL", "").startswith(("redis://", "rediss://")):
            raise RuntimeError("production Redis URL is invalid")
        if env_bool("PYGWALKER_TELEMETRY_ENABLED", False):
            raise RuntimeError("production analytics telemetry must be disabled")
        if env_bool("AI_ALLOW_LOCAL_EXEC", False):
            raise RuntimeError("production AI local execution is disabled by policy")
        if env_bool("ALLOW_REMOTE_DATASET_URLS", False) and not env_bool("AI_ISOLATED_WORKER_ENABLED", False):
            raise RuntimeError("remote dataset ingestion requires the isolated worker")
        if env_bool("CALENDAR_FEATURE_ENABLED", False):
            if len(os.getenv("CALENDAR_CREDENTIALS_SECRET", "")) < 32:
                raise RuntimeError("enabled calendar integration is missing credential encryption")
            if not env_bool("CALENDAR_SYNC_WORKER_ENABLED", False):
                raise RuntimeError("enabled calendar integration is missing its worker")
    return RuntimeConfiguration(environment, release_sha, schema_min, schema_max, email_enabled)


def redacted_configuration_inventory(observed_keys: set[str] | None = None) -> list[dict[str, str | bool]]:
    names = set(CONFIG_CLASSIFICATION) | set(observed_keys or ())
    return [
        {"name": name, "classification": CONFIG_CLASSIFICATION.get(name, "unknown"), "configured": bool(os.getenv(name, "").strip())}
        for name in sorted(names)
    ]
