from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import disk_usage
from threading import Lock

import requests

from services.upload_config import (
    get_data_upload_dir,
    get_private_charts_dir,
    get_public_uploads_dir,
)
from services.storage_quota_service import DEFAULT_DISK_FREE_FLOOR_BYTES
from services.notification_outbox_service import get_queue_metrics

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
    "tenant_site_project_roles": "id,tenant_id,project_id,role_key,capabilities,deleted_at",
    "tenant_site_project_role_assignments": "membership_id,project_id,role_id",
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
    if not all(_directory_accessible(path) for path in paths):
        return "unavailable"
    try:
        floor = int(os.getenv("STORAGE_DISK_FREE_FLOOR_BYTES", str(DEFAULT_DISK_FREE_FLOOR_BYTES)))
        if floor <= 0:
            return "misconfigured"
        if any(disk_usage(path).free < floor for path in paths):
            return "low_disk"
    except (OSError, ValueError):
        return "unavailable"
    return "ok"


def check_notification_worker() -> str:
    if not _env_bool("NOTIFICATION_WORKER_REQUIRED", False):
        return "disabled"
    if not _env_bool("NOTIFICATION_WORKER_ENABLED", False):
        return "misconfigured"
    url = os.getenv("NOTIFICATION_WORKER_HEALTH_URL", "").strip()
    if not url:
        return "misconfigured"
    try:
        response = requests.get(url, timeout=READINESS_TIMEOUT_SECONDS, allow_redirects=False)
        return "ok" if response.status_code == 200 else "unavailable"
    except requests.RequestException:
        return "unavailable"


def check_notification_queue() -> str:
    if not _env_bool("NOTIFICATION_WORKER_REQUIRED", False):
        return "disabled"
    try:
        metrics = get_queue_metrics()
        maximum_depth = int(os.getenv("NOTIFICATION_QUEUE_MAX_DEPTH", "1000"))
        maximum_age = int(os.getenv("NOTIFICATION_QUEUE_MAX_AGE_SECONDS", "900"))
        maximum_dead = int(os.getenv("NOTIFICATION_QUEUE_MAX_DEAD", "0"))
        if min(maximum_depth, maximum_age, maximum_dead) < 0:
            return "misconfigured"
        if (
            metrics.get("queue_depth", 0) > maximum_depth
            or metrics.get("oldest_pending_age_seconds", 0) > maximum_age
            or metrics.get("dead", 0) > maximum_dead
        ):
            return "backlogged"
        return "ok"
    except Exception:
        return "unavailable"


def check_backup_freshness() -> str:
    required = _env_bool("BACKUP_FRESHNESS_REQUIRED", False)
    marker = os.getenv("BACKUP_FRESHNESS_MARKER", "").strip()
    if not marker:
        return "missing" if required else "disabled"
    try:
        maximum_age = int(os.getenv("BACKUP_MAX_AGE_SECONDS", "129600"))
        if maximum_age <= 0:
            return "misconfigured"
        age = datetime.now(timezone.utc).timestamp() - Path(marker).stat().st_mtime
        return "ok" if 0 <= age <= maximum_age else "stale"
    except (OSError, ValueError):
        return "missing" if required else "unavailable"


def check_admin_mfa_policy() -> str:
    environment = _app_env()
    if environment not in {"prod", "production"}:
        return "not_required"
    return (
        "ok"
        if _env_bool("ADMIN_MFA_LOGIN_ENFORCEMENT", False)
        else "insecure"
    )


def check_ai_execution_guard() -> str:
    local_exec = _env_bool("AI_ALLOW_LOCAL_EXEC", False)
    isolated = _env_bool("AI_ISOLATED_WORKER_ENABLED", False)
    if not local_exec:
        return "disabled"
    return "ok" if isolated else "insecure"


def check_remote_ingestion_guard() -> str:
    enabled = _env_bool("ALLOW_REMOTE_DATASET_URLS", False)
    if not enabled:
        return "disabled"
    return "ok" if _env_bool("REMOTE_INGESTION_EGRESS_ENFORCED", False) else "insecure"


def check_parser_isolation() -> str:
    return "in_process" if _app_env() in {"prod", "production"} else "development"


def _is_required_state_ready(component: str, state: str) -> bool:
    if component == "redis" and state in {"disabled", "optional_unavailable"}:
        return True
    if component == "admin_mfa_policy" and state == "not_required":
        return True
    if component in {"ai_execution_guard", "remote_ingestion_guard", "notification_worker", "notification_queue", "backup_freshness"} and state == "disabled":
        return True
    if component == "parser_isolation" and state == "development":
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
        "ai_execution_guard": check_ai_execution_guard,
        "remote_ingestion_guard": check_remote_ingestion_guard,
        "parser_isolation": check_parser_isolation,
        "notification_worker": check_notification_worker,
        "notification_queue": check_notification_queue,
        "backup_freshness": check_backup_freshness,
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
    return {"ready": ready, "status": "ready" if ready else "degraded", "components": components}


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
