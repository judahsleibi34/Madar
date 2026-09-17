"""Typed, redaction-safe startup configuration contract."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from services.supabase_api_key import (
    is_opaque_supabase_api_key,
    is_supabase_secret_api_key,
)
from services.web_push_config import get_web_push_configuration


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
    "WEB_PUSH_ENABLED": "optional",
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
    "CALENDAR_CREDENTIALS_SECRET", "METRICS_TOKEN",
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
    "COMMERCIAL_ACCESS_TEST_LOOKUPS", "COMMERCIAL_SYNTHETIC_DATABASE_DSN",
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
    "MAX_UPLOAD_BYTES", "NOTIFICATION_DEAD_READINESS_WINDOW_SECONDS",
    "NOTIFICATION_EMAIL_MAX_DEAD",
    "NOTIFICATION_QUEUE_MAX_AGE_SECONDS", "NOTIFICATION_QUEUE_MAX_DEAD",
    "NOTIFICATION_QUEUE_MAX_DEPTH", "PRIVATE_CHARTS_DIR", "PUBLIC_UPLOADS_DIR",
    "READINESS_CACHE_SECONDS", "READINESS_TIMEOUT_SECONDS",
    "REMOTE_INGESTION_WORKER_URL", "SMTP_PORT", "SMTP_USE_TLS",
    "STORAGE_DISK_FREE_FLOOR_BYTES", "SUPABASE_HTTP_TIMEOUT_SECONDS",
)})

# Bounded tunables and operational endpoints use reviewed defaults. Listing
# them explicitly keeps the generated contract complete without making every
# optional integration or tuning knob a startup prerequisite.
CONFIG_CLASSIFICATION.update({name: "optional" for name in (
    "ADMIN_ACCOUNT_ACCESS_CODE_TTL_MINUTES", "ADMIN_ACCOUNT_ACCESS_MAX_CODE_ATTEMPTS",
    "ADMIN_ACCOUNT_ACCESS_SESSION_TTL_MINUTES", "AI_PROVIDER", "AI_SANDBOX_MAX_INPUT_BYTES",
    "AI_SANDBOX_MAX_OUTPUT_BYTES", "AI_SANDBOX_MEMORY_BYTES", "AUTH_RATE_LIMIT_LIMIT",
    "AUTH_RATE_LIMIT_WINDOW_SECONDS", "AVATAR_UPLOAD_DIR", "AVATAR_UPLOAD_RATE_LIMIT_LIMIT",
    "AVATAR_UPLOAD_RATE_LIMIT_WINDOW_SECONDS", "BUILDER_ASSET_UPLOAD_RATE_LIMIT_LIMIT",
    "BUILDER_ASSET_UPLOAD_RATE_LIMIT_WINDOW_SECONDS", "BUILDER_SUPPORTED_SCHEMA_VERSIONS",
    "CALENDAR_INBOUND_SYNC_BATCH_SIZE", "CALENDAR_INBOUND_SYNC_INTERVAL_SECONDS",
    "CALENDAR_SYNC_BATCH_SIZE", "CALENDAR_SYNC_POLL_SECONDS", "CALENDAR_SYNC_WORKER_HEALTH_HOST",
    "CALENDAR_SYNC_WORKER_HEALTH_PORT", "CALENDAR_SYNC_WORKER_HEALTH_URL",
    "CALENDAR_WORKSPACE_CACHE_MAX_ENTRIES", "CALENDAR_WORKSPACE_CACHE_TTL_SECONDS",
    "CSV_CHUNK_SIZE_ROWS", "CSV_DUPLICATE_TRACK_ROWS", "DATAFRAME_CACHE_MAX_ITEMS",
    "DATAFRAME_MAX_CELL_CHARS", "DATAFRAME_MAX_COLUMNS", "DATAFRAME_MAX_ROWS",
    "DATAFRAME_MAX_TOTAL_CELL_CHARS", "DATAFRAME_URL_CACHE_SECONDS",
    "DATA_ANALYSIS_RATE_LIMIT_LIMIT", "DATA_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS",
    "DATA_DELETION_WORKER_BATCH_SIZE", "DATA_DELETION_WORKER_HEALTH_HOST",
    "DATA_DELETION_WORKER_HEALTH_PORT", "DATA_DELETION_WORKER_POLL_SECONDS",
    "DATA_UPLOAD_RATE_LIMIT_LIMIT", "DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
    "DATA_VISUALIZATION_RATE_LIMIT_LIMIT", "DATA_VISUALIZATION_RATE_LIMIT_WINDOW_SECONDS",
    "DATA_VISUALIZATION_TENANT_RATE_LIMIT_LIMIT", "DATA_VISUALIZATION_TENANT_RATE_LIMIT_WINDOW_SECONDS",
    "DATA_WORKSPACE_RATE_LIMIT_LIMIT", "DATA_WORKSPACE_RATE_LIMIT_WINDOW_SECONDS",
    "ECOMMERCE_CATALOG_CACHE_MAX_ENTRIES", "ECOMMERCE_CATALOG_CACHE_TTL_SECONDS",
    "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "EMAIL_VERIFICATION_RESEND_DAILY_LIMIT",
    "EMAIL_VERIFICATION_RESEND_HOURLY_LIMIT", "ENFORCE_BUILDER_CLIENT_CONTRACT",
    "LARGE_DATASET_THRESHOLD_BYTES", "MAX_BUILDER_SCHEMA_BYTES", "MAX_CSV_BYTES",
    "MAX_EXCEL_CELL_CHARS", "MAX_EXCEL_COLUMNS", "MAX_EXCEL_FILE_BYTES", "MAX_EXCEL_ROWS",
    "MAX_EXCEL_SHEETS", "MAX_EXCEL_UNCOMPRESSED_BYTES", "MAX_EXCEL_UPLOAD_BYTES",
    "MAX_EXCEL_ZIP_COMPRESSION_RATIO", "MAX_EXCEL_ZIP_ENTRIES",
    "MAX_EXCEL_ZIP_ENTRY_NAME_CHARS", "MAX_FULL_DATAFRAME_BYTES", "MAX_PREVIEW_ROWS",
    "MIN_PUBLIC_SUBMISSION_ELAPSED_MS", "NOTIFICATION_WORKER_BATCH_SIZE",
    "NOTIFICATION_WORKER_CONCURRENCY", "NOTIFICATION_WORKER_HEALTH_HOST",
    "NOTIFICATION_WORKER_HEALTH_PORT", "NOTIFICATION_WORKER_HEALTH_URL",
    "NOTIFICATION_WORKER_POLL_SECONDS", "PARSER_CHILD_STARTUP_TIMEOUT_SECONDS",
    "PARSER_JOB_TIMEOUT_SECONDS", "PARSER_WORKER_HEALTH_HOST", "PARSER_WORKER_HEALTH_URL",
    "PARSER_WORKER_MAX_RESULT_BYTES", "PARSER_WORKER_PORT", "PARSER_WORKER_PROCESS",
    "PARSER_WORKER_TIMEOUT_SECONDS", "PARSER_WORKER_URL", "PASSWORD_RATE_LIMIT_LIMIT",
    "PASSWORD_RATE_LIMIT_WINDOW_SECONDS", "PASSWORD_RESET_TTL_MINUTES", "PATH",
    "PENDING_VERIFICATION_TTL_SECONDS",
    "PUBLIC_CONTACT_RATE_LIMIT_LIMIT", "PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SECONDS",
    "PUBLIC_FORM_SUBMISSION_RATE_LIMIT_LIMIT", "PUBLIC_FORM_SUBMISSION_RATE_LIMIT_WINDOW_SECONDS",
    "PUBLIC_RATE_LIMIT_LIMIT", "PUBLIC_RATE_LIMIT_WINDOW_SECONDS",
    "REMOTE_INGESTION_BACKEND_TIMEOUT_SECONDS", "REMOTE_INGESTION_DEADLINE_SECONDS",
    "REMOTE_INGESTION_HARD_TIMEOUT_SECONDS", "REMOTE_INGESTION_MAX_RESULT_BYTES",
    "REMOTE_INGESTION_WORKER_HEALTH_URL", "REMOTE_INGESTION_WORKER_HOST",
    "REMOTE_INGESTION_WORKER_PORT", "RESERVATION_CANCELLATION_TTL_DAYS",
    "SESSION_INACTIVITY_TIMEOUT_SECONDS", "SUPPORTED_BUILDER_CLIENT_CONTRACTS",
    "THIRD_PARTY_HTTP_LOG_LEVEL",
)})
CONFIG_CLASSIFICATION.update({name: "production-only" for name in (
    "MADAR_ENV_FILE", "PASSWORD_RESET_LEGACY_LINKS_ALLOWED_UNTIL", "PUBLISH_BETA_TENANT_IDS",
)})
CONFIG_CLASSIFICATION["MADAR_ENV_OVERRIDE"] = "development-only"


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
    if environment not in {"development", "test", "staging", "prod", "production"}:
        raise RuntimeError("configuration value is invalid: APP_ENV")
    production = environment in {"prod", "production"}
    production_like = production or environment == "staging"
    release_sha = os.getenv("MADAR_RELEASE_SHA", "development").strip()
    try:
        schema_min = int(os.getenv("SCHEMA_COMPATIBLE_MIN", "81"))
        schema_max = int(os.getenv("SCHEMA_COMPATIBLE_MAX", "83"))
    except ValueError as error:
        raise RuntimeError("schema compatibility configuration is invalid") from error
    if schema_min <= 0 or schema_max < schema_min:
        raise RuntimeError("schema compatibility configuration is invalid")
    email_enabled = env_bool("EMAIL_CHANNEL_ENABLED", False)
    if production_like:
        required = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "CSRF_SECRET", "FRONTEND_URLS", "REDIS_URL")
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            # Key names are safe; values are never included.
            raise RuntimeError("required production configuration is missing: " + ",".join(missing))
        service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        if (
            is_opaque_supabase_api_key(service_key)
            and not is_supabase_secret_api_key(service_key)
        ):
            raise RuntimeError("production server credential type is invalid: SUPABASE_SERVICE_KEY")
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
        web_push = get_web_push_configuration()
        if web_push.administratively_enabled and not web_push.operational:
            if web_push.missing_fields:
                raise RuntimeError(
                    "enabled Web Push channel is missing VAPID configuration: "
                    + ",".join(web_push.missing_fields)
                )
            raise RuntimeError("enabled Web Push channel has invalid VAPID configuration")
        if not re.fullmatch(r"[0-9a-f]{40}", release_sha):
            raise RuntimeError("production release identity is missing")
        origins = os.getenv("CSRF_TRUSTED_ORIGINS", "").strip() or os.getenv("FRONTEND_URLS", "")
        for origin in (value.strip() for value in origins.split(",") if value.strip()):
            parsed = urlsplit(origin)
            staging_loopback = (
                environment == "staging"
                and parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            )
            if (
                "*" in origin
                or (parsed.scheme != "https" and not staging_loopback)
                or not parsed.hostname
                or parsed.path not in {"", "/"}
            ):
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
