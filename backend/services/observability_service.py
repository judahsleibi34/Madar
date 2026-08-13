from __future__ import annotations

import contextvars
import hmac
import json
import logging
import os
import re
import threading
import time
from urllib.parse import urlsplit
from collections import defaultdict
from pathlib import Path
from shutil import disk_usage
from uuid import uuid4

from database import service_supabase
from services.notification_outbox_service import get_queue_metrics
from services.upload_config import get_data_upload_dir, get_private_charts_dir, get_public_uploads_dir

CORRELATION_ID = contextvars.ContextVar("madar_correlation_id", default="")
CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,80}$")
_lock = threading.Lock()
_requests: dict[tuple[str, str, str], int] = defaultdict(int)
_errors: dict[tuple[str, str], int] = defaultdict(int)
_latency_count: dict[tuple[str, str], int] = defaultdict(int)
_latency_sum: dict[tuple[str, str], float] = defaultdict(float)


def correlation_id(value: str | None) -> str:
    candidate = str(value or "").strip()
    return candidate if CORRELATION_PATTERN.fullmatch(candidate) else uuid4().hex


def record_request(*, method: str, route: str, status_code: int, elapsed_seconds: float) -> None:
    method_key = method.upper() if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"} else "OTHER"
    route_key = route if route.startswith("/") and len(route) <= 200 else "unmatched"
    status_class = f"{max(0, min(status_code // 100, 9))}xx"
    latency_key = (method_key, route_key)
    with _lock:
        _requests[(method_key, route_key, status_class)] += 1
        _latency_count[latency_key] += 1
        _latency_sum[latency_key] += max(0.0, elapsed_seconds)
        if status_code >= 500:
            _errors[(method_key, route_key)] += 1


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric(name: str, labels: dict[str, str], value: int | float) -> str:
    rendered = ",".join(f'{key}="{_escape(item)}"' for key, item in labels.items())
    return f"{name}{{{rendered}}} {value}"


def operational_snapshot() -> dict[str, int]:
    result: dict[str, int] = {
        "parser_isolated": int(os.getenv("PARSER_ISOLATED_WORKER_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}),
        "ai_local_execution_enabled": int(os.getenv("AI_ALLOW_LOCAL_EXEC", "false").strip().lower() in {"1", "true", "yes", "on"}),
    }
    try:
        result.update({f"notification_{key}": int(value) for key, value in get_queue_metrics().items()})
    except Exception:
        result["notification_metrics_available"] = 0
    try:
        expired_assets = (
            service_supabase.table("builder_assets")
            .select("id")
            .eq("status", "unreferenced")
            .lte("retention_until", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            .limit(5000)
            .execute()
        )
        result["asset_cleanup_backlog"] = len(getattr(expired_assets, "data", None) or [])
        reservations = (
            service_supabase.table("storage_reservations")
            .select("id")
            .eq("status", "reserved")
            .limit(5000)
            .execute()
        )
        result["quota_reservations"] = len(getattr(reservations, "data", None) or [])
    except Exception:
        result["storage_accounting_metrics_available"] = 0
    for name, path in {
        "public_assets": get_public_uploads_dir(),
        "private_uploads": get_data_upload_dir(),
        "generated_artifacts": get_private_charts_dir(),
    }.items():
        try:
            usage = disk_usage(path)
            result[f"storage_{name}_free_bytes"] = usage.free
            result[f"storage_{name}_used_bytes"] = usage.used
        except OSError:
            result[f"storage_{name}_available"] = 0
    marker = os.getenv("BACKUP_FRESHNESS_MARKER", "").strip()
    if marker:
        try:
            result["backup_age_seconds"] = max(0, int(time.time() - Path(marker).stat().st_mtime))
        except OSError:
            result["backup_marker_available"] = 0
    return result


def prometheus_metrics() -> str:
    lines = [
        "# HELP madar_http_requests_total HTTP requests by bounded route and status class.",
        "# TYPE madar_http_requests_total counter",
    ]
    with _lock:
        requests = dict(_requests)
        errors = dict(_errors)
        counts = dict(_latency_count)
        sums = dict(_latency_sum)
    for (method, route, status_class), value in sorted(requests.items()):
        lines.append(_metric("madar_http_requests_total", {"method": method, "route": route, "status_class": status_class}, value))
    for (method, route), value in sorted(errors.items()):
        lines.append(_metric("madar_http_errors_total", {"method": method, "route": route}, value))
    for (method, route), value in sorted(counts.items()):
        labels = {"method": method, "route": route}
        lines.append(_metric("madar_http_request_duration_seconds_count", labels, value))
        lines.append(_metric("madar_http_request_duration_seconds_sum", labels, round(sums[(method, route)], 6)))
    for key, value in sorted(operational_snapshot().items()):
        lines.append(f"madar_{key} {value}")
    return "\n".join(lines) + "\n"


def metrics_access_allowed(*, client_host: str | None, authorization: str | None) -> bool:
    token = os.getenv("METRICS_TOKEN", "").strip()
    if token:
        supplied = str(authorization or "")
        return supplied.startswith("Bearer ") and hmac.compare_digest(supplied[7:], token)
    return client_host in {"127.0.0.1", "::1", "testclient"}


class JsonFormatter(logging.Formatter):
    SAFE_EXTRA = ("correlation_id", "security_event_id", "error_code", "error_type", "status_code", "duration_ms", "method", "route")
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        event = record.getMessage()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", event):
            event = "log.message_redacted"
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "event": event,
        }
        current = CORRELATION_ID.get()
        if current:
            payload["correlation_id"] = current
        for name in self.SAFE_EXTRA:
            value = getattr(record, name, None)
            if value is not None and name not in payload:
                payload[name] = value
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class SafeAccessLogFilter(logging.Filter):
    """Remove query strings and suppress only successful liveness noise."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            sanitized = list(args)
            path = urlsplit(str(sanitized[2])).path or "/"
            sanitized[2] = path
            record.args = tuple(sanitized)
            try:
                status_code = int(sanitized[4])
            except (TypeError, ValueError):
                status_code = 0
            if path == "/health/live" and 200 <= status_code < 400:
                return False
        return True


def configure_access_logging() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    for handler in access_logger.handlers:
        if not any(isinstance(item, SafeAccessLogFilter) for item in handler.filters):
            handler.addFilter(SafeAccessLogFilter())


def configure_structured_logging() -> None:
    third_party_level = os.getenv("THIRD_PARTY_HTTP_LOG_LEVEL", "WARNING").strip().upper()
    if third_party_level not in {"WARNING", "ERROR", "CRITICAL"}:
        third_party_level = "WARNING"
    logging.getLogger("httpx").setLevel(third_party_level)
    logging.getLogger("httpcore").setLevel(third_party_level)
    configure_access_logging()
    if os.getenv("STRUCTURED_LOGS", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    root = logging.getLogger()
    if any(getattr(handler, "_madar_json", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._madar_json = True  # type: ignore[attr-defined]
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
