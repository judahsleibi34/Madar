from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

import requests

from services.upload_config import (
    get_data_upload_dir,
    get_private_charts_dir,
    get_public_uploads_dir,
)

try:
    import redis
except ImportError:  # pragma: no cover - installed in the runtime image
    redis = None


READINESS_TIMEOUT_SECONDS = float(os.getenv("READINESS_TIMEOUT_SECONDS", "2"))
READINESS_CACHE_SECONDS = float(os.getenv("READINESS_CACHE_SECONDS", "5"))
REQUIRED_SCHEMA_SELECTS = {
    "users": "id,account_kind,account_status,email_verified,pending_email",
    "tenant_memberships": "id,tenant_id,auth_id,status",
    "builder_projects": "id,draft_revision,published_revision,schema_version",
    "builder_reservations": "id,idempotency_key_hash,request_hash,exclusive_slot",
    "features": "id,payment_status,billing_state_changed_at",
    "email_verification_attempts": "id,email_hash,status",
    "pending_account_onboarding": "id,auth_id,status,expires_at",
    "password_reset_requests": "id,nonce_hash,status,processing_started_at",
    "billing_webhook_events": "id,provider_event_id,tenant_id,provider_occurred_at,status",
    "notification_outbox": "id,channel,status,deduplication_key",
    "builder_form_submissions": "id,idempotency_key_hash,request_hash",
    "builder_assets": "id,tenant_id,status,size_bytes,retention_until",
    "builder_asset_references": "asset_id,project_id,reference_path",
    "storage_accounts": "tenant_id,scope_key,used_bytes,reserved_bytes,quota_bytes",
    "storage_reservations": "id,status,bytes,expires_at",
    "storage_objects": "id,tenant_id,category,size_bytes,status",
}

_cache_lock = Lock()
_cached_at = 0.0
_cached_result: dict | None = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_env() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or "development"
    ).strip().lower()


def _supabase_headers() -> dict[str, str]:
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }


def _supabase_url(path: str) -> str:
    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    return f"{base_url}{path}"


def check_database() -> str:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        return "misconfigured"
    try:
        response = requests.get(
            _supabase_url("/rest/v1/users?select=id&limit=1"),
            headers=_supabase_headers(),
            timeout=READINESS_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        return "ok" if 200 <= response.status_code < 300 else "unavailable"
    except requests.RequestException:
        return "unavailable"


def check_auth() -> str:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_ANON_KEY"):
        return "misconfigured"
    try:
        response = requests.get(
            _supabase_url("/auth/v1/health"),
            headers={"apikey": os.getenv("SUPABASE_ANON_KEY", "")},
            timeout=READINESS_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        return "ok" if 200 <= response.status_code < 300 else "unavailable"
    except requests.RequestException:
        return "unavailable"


def check_schema() -> str:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        return "misconfigured"
    try:
        def check_table(item: tuple[str, str]) -> bool:
            table, columns = item
            response = requests.get(
                _supabase_url(f"/rest/v1/{table}?select={columns}&limit=0"),
                headers={**_supabase_headers(), "Range": "0-0"},
                timeout=READINESS_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            return 200 <= response.status_code < 300

        schema_items = tuple(REQUIRED_SCHEMA_SELECTS.items())
        with ThreadPoolExecutor(max_workers=min(4, len(schema_items))) as executor:
            table_states = tuple(executor.map(check_table, schema_items))
        return "ok" if all(table_states) else "missing"
    except requests.RequestException:
        return "unavailable"


def check_redis() -> str:
    rate_limit_enabled = _env_bool("RATE_LIMIT_ENABLED", True)
    fail_open = _env_bool("RATE_LIMIT_FAIL_OPEN", False)
    production = _app_env() in {"prod", "production"}
    if not rate_limit_enabled:
        return "insecure" if production else "disabled"
    if fail_open and production:
        return "insecure"
    if redis is None:
        return "optional_unavailable" if fail_open else "unavailable"
    try:
        client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/0"),
            socket_connect_timeout=READINESS_TIMEOUT_SECONDS,
            socket_timeout=READINESS_TIMEOUT_SECONDS,
        )
        client.ping()
        return "ok"
    except Exception:
        return "optional_unavailable" if fail_open else "unavailable"


def _directory_accessible(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        resolved = path.resolve()
        if not resolved.is_dir() or not os.access(resolved, os.R_OK | os.W_OK | os.X_OK):
            return False
        with tempfile.NamedTemporaryFile(
            prefix=".madar-readiness-",
            dir=resolved,
            delete=True,
        ) as probe:
            probe.write(b"ready")
            probe.flush()
        return True
    except OSError:
        return False


def check_storage() -> str:
    paths = (get_public_uploads_dir(), get_data_upload_dir(), get_private_charts_dir())
    return "ok" if all(_directory_accessible(path) for path in paths) else "unavailable"


def check_admin_mfa_policy() -> str:
    environment = _app_env()
    if environment not in {"prod", "production"}:
        return "not_required"
    return (
        "ok"
        if _env_bool("ADMIN_MFA_LOGIN_ENFORCEMENT", False)
        else "insecure"
    )


def _is_required_state_ready(component: str, state: str) -> bool:
    if component == "redis" and state in {"disabled", "optional_unavailable"}:
        return True
    if component == "admin_mfa_policy" and state == "not_required":
        return True
    return state == "ok"


def compute_readiness() -> dict:
    checks = {
        "database": check_database,
        "redis": check_redis,
        "auth": check_auth,
        "storage": check_storage,
        "schema": check_schema,
        "admin_mfa_policy": check_admin_mfa_policy,
    }
    def safe_check(check) -> str:
        try:
            return check()
        except Exception:
            return "unavailable"

    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        futures = {
            name: executor.submit(safe_check, check)
            for name, check in checks.items()
        }
        components = {name: future.result() for name, future in futures.items()}
    ready = all(
        _is_required_state_ready(component, state)
        for component, state in components.items()
    )
    return {"ready": ready, "components": components}


def get_readiness(*, use_cache: bool = True) -> dict:
    global _cached_at, _cached_result
    now = time.monotonic()
    with _cache_lock:
        if (
            use_cache
            and _cached_result is not None
            and now - _cached_at < READINESS_CACHE_SECONDS
        ):
            return dict(_cached_result)
        result = compute_readiness()
        _cached_at = now
        _cached_result = result
        return dict(result)


def clear_readiness_cache() -> None:
    global _cached_at, _cached_result
    with _cache_lock:
        _cached_at = 0.0
        _cached_result = None
