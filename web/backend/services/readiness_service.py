from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
from services.notification_delivery_queue_service import get_delivery_channel_metrics
from services.calendar_task_sync_queue_service import get_task_sync_queue_metrics
from services.calendar_connection_sync_queue_service import (
    get_connection_sync_queue_metrics,
)
from services.supabase_api_key import supabase_api_headers

try:
    import redis
except ImportError:  # pragma: no cover - installed in the runtime image
    redis = None


READINESS_TIMEOUT_SECONDS = float(os.getenv("READINESS_TIMEOUT_SECONDS", "2"))
READINESS_CACHE_SECONDS = float(os.getenv("READINESS_CACHE_SECONDS", "5"))
DEFAULT_SCHEMA_COMPATIBLE_MIN = 81
DEFAULT_SCHEMA_COMPATIBLE_MAX = 83

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


def check_environment() -> str:
    value = os.getenv("APP_ENV", "").strip().lower()
    return "ok" if value in {"development", "test", "staging", "prod", "production"} else "misconfigured"


def _supabase_headers() -> dict[str, str]:
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    return supabase_api_headers(service_key)


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
        response = requests.get(
            _supabase_url(
                "/rest/v1/application_schema_state"
                "?select=schema_version&contract_key=eq.core&limit=1"
            ),
            headers=_supabase_headers(),
            timeout=READINESS_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if response.status_code in {400, 404}:
            return "missing"
        if not 200 <= response.status_code < 300:
            return "unavailable"
        rows = response.json()
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
        ):
            return "missing"
        version = int(rows[0].get("schema_version") or 0)
        minimum = int(os.getenv("SCHEMA_COMPATIBLE_MIN", str(DEFAULT_SCHEMA_COMPATIBLE_MIN)))
        maximum = int(os.getenv("SCHEMA_COMPATIBLE_MAX", str(DEFAULT_SCHEMA_COMPATIBLE_MAX)))
        if minimum <= 0 or maximum < minimum:
            return "misconfigured"
        return "ok" if minimum <= version <= maximum else "incompatible"
    except (requests.RequestException, TypeError, ValueError):
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


def check_data_deletion_worker() -> str:
    if not _env_bool("DATA_DELETION_WORKER_REQUIRED", False):
        return "disabled"
    if not _env_bool("DATA_DELETION_WORKER_ENABLED", False):
        return "misconfigured"
    url = os.getenv("DATA_DELETION_WORKER_HEALTH_URL", "").strip()
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


def check_notification_email() -> str:
    if not _env_bool("EMAIL_CHANNEL_ENABLED", False):
        return "disabled"
    required = ("SMTP_HOST", "SMTP_FROM_EMAIL")
    if not all(os.getenv(name, "").strip() for name in required):
        return "unavailable"
    try:
        metrics = get_delivery_channel_metrics().get("email", {})
        maximum_dead = int(os.getenv("NOTIFICATION_EMAIL_MAX_DEAD", "0"))
        return "degraded" if int(metrics.get("dead") or 0) > maximum_dead else "configured"
    except Exception:
        return "unavailable"


def check_notification_push() -> str:
    enabled = _env_bool("WEB_PUSH_ENABLED", False)
    if not enabled:
        return "disabled"
    return "configured" if os.getenv("VAPID_PRIVATE_KEY", "").strip() else "unavailable"


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
    health_url = os.getenv("REMOTE_INGESTION_WORKER_HEALTH_URL", "").strip()
    worker_url = os.getenv("REMOTE_INGESTION_WORKER_URL", "").strip()
    if not health_url or not worker_url:
        return "misconfigured"
    try:
        response = requests.get(
            health_url, timeout=READINESS_TIMEOUT_SECONDS, allow_redirects=False
        )
        payload = response.json() if response.status_code == 200 else {}
        return (
            "ok"
            if payload.get("status") == "ok"
            and payload.get("isolation") == "remote_ingestion_worker"
            and payload.get("policy") == "pinned_https_v1"
            else "unavailable"
        )
    except (requests.RequestException, TypeError, ValueError):
        return "unavailable"


def check_calendar_configuration() -> str:
    if not _env_bool("CALENDAR_FEATURE_ENABLED", False):
        return "disabled"
    if not _env_bool("CALENDAR_SYNC_REQUIRED", False):
        return "ok"
    if not _env_bool("CALENDAR_SYNC_WORKER_ENABLED", False):
        return "misconfigured"
    if len(os.getenv("CALENDAR_CREDENTIALS_SECRET", "").strip()) < 24:
        return "misconfigured"
    from urllib.parse import urlparse
    for name in ("PUBLIC_API_URL", "FRONTEND_PRIMARY_URL"):
        parsed = urlparse(os.getenv(name, "").strip())
        if parsed.scheme != "https" or not parsed.netloc or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            return "misconfigured"
    providers = (
        ("GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET"),
        ("MICROSOFT_CALENDAR_CLIENT_ID", "MICROSOFT_CALENDAR_CLIENT_SECRET"),
    )
    if not any(all(os.getenv(name, "").strip() for name in pair) for pair in providers):
        return "misconfigured"
    return "ok"


def check_calendar_sync_worker() -> str:
    if not _env_bool("CALENDAR_FEATURE_ENABLED", False):
        return "disabled"
    if not _env_bool("CALENDAR_SYNC_REQUIRED", False):
        return "disabled"
    url = os.getenv("CALENDAR_SYNC_WORKER_HEALTH_URL", "").strip()
    if not url:
        return "misconfigured"
    try:
        response = requests.get(
            url, timeout=READINESS_TIMEOUT_SECONDS, allow_redirects=False
        )
        return "ok" if response.status_code == 200 else "unavailable"
    except requests.RequestException:
        return "unavailable"


def check_calendar_sync_queue() -> str:
    if not _env_bool("CALENDAR_FEATURE_ENABLED", False):
        return "disabled"
    if not _env_bool("CALENDAR_SYNC_REQUIRED", False):
        return "disabled"
    try:
        metrics = get_task_sync_queue_metrics()
        inbound_metrics = get_connection_sync_queue_metrics()
        if (
            metrics.get("queue_depth", 0) > 1000
            or metrics.get("failed", 0) > 100
            or metrics.get("reconciliation_required", 0) > 0
            or inbound_metrics.get("queue_depth", 0) > 100
            or inbound_metrics.get("failed", 0) > 20
        ):
            return "backlogged"
        return "ok"
    except Exception:
        return "unavailable"


def check_parser_isolation() -> str:
    if not _env_bool("PARSER_ISOLATED_WORKER_ENABLED", False):
        return "in_process" if _app_env() in {"prod", "production"} else "development"
    url = os.getenv("PARSER_WORKER_HEALTH_URL", "").strip()
    if not url:
        return "misconfigured"
    try:
        response = requests.get(
            url, timeout=READINESS_TIMEOUT_SECONDS, allow_redirects=False
        )
        payload = response.json() if response.status_code == 200 else {}
        return (
            "ok"
            if payload.get("status") == "ok"
            and payload.get("isolation") == "parser_worker"
            else "unavailable"
        )
    except (requests.RequestException, TypeError, ValueError):
        return "unavailable"


def _is_required_state_ready(component: str, state: str) -> bool:
    if component == "redis" and state in {"disabled", "optional_unavailable"}:
        return True
    if component == "admin_mfa_policy" and state == "not_required":
        return True
    if component in {"ai_execution_guard", "remote_ingestion_guard", "notification_worker", "notification_queue", "notification_email", "notification_push", "backup_freshness", "calendar_configuration", "calendar_sync_worker", "calendar_sync_queue", "data_deletion_worker"} and state == "disabled":
        return True
    if component in {"notification_email", "notification_push"} and state == "configured":
        return True
    if component == "parser_isolation" and state == "development":
        return True
    return state == "ok"


def compute_readiness() -> dict:
    checks = {
        "environment": check_environment,
        "database": check_database,
        "redis": check_redis,
        "auth": check_auth,
        "storage": check_storage,
        "schema": check_schema,
        "admin_mfa_policy": check_admin_mfa_policy,
        "ai_execution_guard": check_ai_execution_guard,
        "remote_ingestion_guard": check_remote_ingestion_guard,
        "calendar_configuration": check_calendar_configuration,
        "calendar_sync_worker": check_calendar_sync_worker,
        "calendar_sync_queue": check_calendar_sync_queue,
        "parser_isolation": check_parser_isolation,
        "notification_worker": check_notification_worker,
        "data_deletion_worker": check_data_deletion_worker,
        "notification_queue": check_notification_queue,
        "notification_email": check_notification_email,
        "notification_push": check_notification_push,
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
