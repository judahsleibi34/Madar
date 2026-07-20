from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from database import service_supabase

logger = logging.getLogger(__name__)

ALLOWED_CHANNELS = {"internal", "email", "web_push"}
SAFE_CODE_PATTERN = re.compile(r"^[a-z0-9_.-]{1,100}$")
MAX_OUTBOX_PAYLOAD_BYTES = 64 * 1024


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _first(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        if isinstance(data.get("result"), dict):
            return data["result"]
        return data
    if isinstance(data, list) and data:
        row = data[0]
        return row if isinstance(row, dict) else None
    return None


def _safe_code(value: str | None, fallback: str = "delivery_failed") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if SAFE_CODE_PATTERN.fullmatch(normalized) else fallback


def enqueue_notification(
    *,
    channel: str,
    template: str,
    payload: dict[str, Any],
    tenant_id: int | None = None,
    user_id: int | None = None,
    recipient_hash: str | None = None,
    recipient_reference: str | None = None,
    deduplication_key: str | None = None,
    available_at: datetime | None = None,
    retention_days: int = 90,
    client=None,
) -> dict[str, Any] | None:
    clean_channel = str(channel or "").strip().lower()
    clean_template = str(template or "").strip()
    if clean_channel not in ALLOWED_CHANNELS or not clean_template:
        raise ValueError("invalid notification outbox request")
    if not isinstance(payload, dict):
        raise ValueError("notification payload must be an object")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > MAX_OUTBOX_PAYLOAD_BYTES:
        raise ValueError("notification payload is too large")

    now = _now()
    row = {
        "tenant_id": int(tenant_id) if tenant_id is not None else None,
        "user_id": int(user_id) if user_id is not None else None,
        "channel": clean_channel,
        "template": clean_template[:120],
        "recipient_hash": recipient_hash or None,
        "recipient_reference": str(recipient_reference or "")[:200] or None,
        "payload": payload,
        "status": "pending",
        "available_at": (available_at or now).isoformat(),
        "deduplication_key": str(deduplication_key or "")[:240] or None,
        "retention_until": (
            now + timedelta(days=max(1, min(int(retention_days), 3650)))
        ).isoformat(),
    }

    database_client = client or service_supabase
    try:
        response = database_client.table("notification_outbox").insert(row).execute()
        return _first(getattr(response, "data", None)) or row
    except Exception as error:
        if row["deduplication_key"] and (
            "duplicate" in str(error).lower() or "unique" in str(error).lower()
        ):
            try:
                query = (
                    database_client.table("notification_outbox")
                    .select("*")
                    .eq("channel", clean_channel)
                    .eq("deduplication_key", row["deduplication_key"])
                )
                if tenant_id is not None:
                    query = query.eq("tenant_id", int(tenant_id))
                else:
                    query = query.is_("tenant_id", "null")
                response = query.limit(1).execute()
                return _first(getattr(response, "data", None))
            except Exception as lookup_error:
                logger.warning(
                    "notifications.outbox_dedup_lookup_failed",
                    extra={"error_type": type(lookup_error).__name__},
                )
        logger.warning(
            "notifications.outbox_enqueue_failed",
            extra={
                "channel": clean_channel,
                "template": clean_template[:120],
                "error_type": type(error).__name__,
            },
        )
        return None


def mark_notification_result(
    outbox_id: str,
    *,
    succeeded: bool,
    failure_code: str | None = None,
    retry_after_seconds: int = 60,
    client=None,
) -> bool:
    now = _now()
    payload: dict[str, Any]
    if succeeded:
        payload = {
            "status": "sent",
            "sent_at": now.isoformat(),
            "processing_started_at": None,
            "last_error_code": None,
        }
    else:
        payload = {
            "status": "failed",
            "available_at": (
                now + timedelta(seconds=max(1, min(int(retry_after_seconds), 86400)))
            ).isoformat(),
            "processing_started_at": None,
            "last_error_code": _safe_code(failure_code),
        }
    try:
        database_client = client or service_supabase
        rpc = getattr(database_client, "rpc", None)
        if callable(rpc):
            response = rpc(
                "finish_notification_outbox",
                {
                    "p_outbox_id": outbox_id,
                    "p_succeeded": bool(succeeded),
                    "p_failure_code": None if succeeded else _safe_code(failure_code),
                    "p_available_at": (
                        now
                        + timedelta(
                            seconds=max(1, min(int(retry_after_seconds), 86400))
                        )
                    ).isoformat()
                    if not succeeded
                    else None,
                    "p_finished_at": now.isoformat(),
                },
            ).execute()
            return bool(getattr(response, "data", None))
        response = (
            database_client.table("notification_outbox")
            .update(payload)
            .eq("id", outbox_id)
            .execute()
        )
        return bool(getattr(response, "data", None))
    except Exception as error:
        logger.warning(
            "notifications.outbox_result_failed",
            extra={"error_type": type(error).__name__},
        )
        return False


def claim_notifications(*, limit: int = 25) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    response = service_supabase.rpc(
        "claim_notification_outbox",
        {"p_limit": safe_limit, "p_now": _now().isoformat()},
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def get_queue_metrics(*, client=None, now: datetime | None = None) -> dict[str, int]:
    database_client = client or service_supabase
    response = (
        database_client.table("notification_outbox")
        .select("status,created_at")
        .in_("status", ["pending", "failed", "processing", "dead", "sent"])
        .limit(5000)
        .execute()
    )
    rows = [
        row
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, dict)
    ]
    counts = {
        status: sum(row.get("status") == status for row in rows)
        for status in ("pending", "failed", "processing", "dead", "sent")
    }
    pending_dates = []
    for row in rows:
        if row.get("status") not in {"pending", "failed"} or not row.get("created_at"):
            continue
        try:
            pending_dates.append(
                datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            )
        except ValueError:
            continue
    current = now or _now()
    oldest_age = (
        max(0, int((current - min(pending_dates)).total_seconds()))
        if pending_dates
        else 0
    )
    return {
        "queue_depth": counts["pending"] + counts["failed"],
        "oldest_pending_age_seconds": oldest_age,
        **counts,
    }
