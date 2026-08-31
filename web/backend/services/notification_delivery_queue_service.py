from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from database import service_supabase
from services.web_push_config import get_web_push_configuration


logger = logging.getLogger(__name__)
SAFE_CODE_PATTERN = re.compile(r"^[a-z0-9_.-]{1,100}$")
LEGACY_TENANT_EVENT_SETTLE_SECONDS = 300


class ResolutionDeferred(RuntimeError):
    """Resolution should retry after an old application writer can finish."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def _safe_code(value: str | None, fallback: str = "delivery_failed") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if SAFE_CODE_PATTERN.fullmatch(normalized) else fallback


def resolve_outbox_notification(row: dict[str, Any], *, client=None) -> int:
    outbox_id = str(row.get("id") or "")
    if not outbox_id:
        raise ValueError("notification outbox id is required")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if str(row.get("template") or "") == "tenant_event" and not payload.get("event_id"):
        try:
            created_at = datetime.fromisoformat(
                str(row.get("created_at") or "").replace("Z", "+00:00")
            )
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except ValueError:
            created_at = None
        if created_at is not None and (_now() - created_at).total_seconds() < LEGACY_TENANT_EVENT_SETTLE_SECONDS:
            # Phase 1 writers inserted the outbox before synchronously creating
            # and sending. Give an old writer time to mark its row sent during
            # migration-first rolling deployment; genuinely abandoned rows are
            # recovered after the settling window.
            raise ResolutionDeferred("legacy_tenant_event_settling")
    response = (client or service_supabase).rpc(
        "resolve_notification_outbox_v2",
        {
            "p_outbox_id": outbox_id,
            "p_now": _now().isoformat(),
            "p_email_enabled": os.getenv(
                "EMAIL_CHANNEL_ENABLED", "false"
            ).strip().lower() in {"1", "true", "yes", "on"},
            "p_web_push_enabled": get_web_push_configuration().operational,
        },
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else 0
    return int(data or 0)


def claim_deliveries(*, limit: int = 25, lease_seconds: int = 900, client=None) -> list[dict[str, Any]]:
    response = (client or service_supabase).rpc(
        "claim_notification_deliveries",
        {
            "p_limit": max(1, min(int(limit), 100)),
            "p_now": _now().isoformat(),
            "p_lease_seconds": max(30, min(int(lease_seconds), 3600)),
        },
    ).execute()
    return _rows(response)


def finish_delivery(
    delivery_id: str,
    *,
    outcome: str,
    error_code: str | None = None,
    error_detail_safe: str | None = None,
    retry_after_seconds: int = 60,
    provider_message_id: str | None = None,
    client=None,
) -> dict[str, Any] | None:
    clean_outcome = str(outcome or "").strip().lower()
    if clean_outcome not in {"sent", "retry", "dead", "revoked"}:
        raise ValueError("invalid notification delivery outcome")
    now = _now()
    response = (client or service_supabase).rpc(
        "finish_notification_delivery",
        {
            "p_delivery_id": delivery_id,
            "p_outcome": clean_outcome,
            "p_error_code": None if clean_outcome == "sent" else _safe_code(error_code),
            "p_error_detail_safe": (
                str(error_detail_safe or "")[:500] or None
                if clean_outcome != "sent"
                else None
            ),
            "p_available_at": (
                now
                + timedelta(seconds=max(1, min(int(retry_after_seconds), 86400)))
            ).isoformat()
            if clean_outcome == "retry"
            else None,
            "p_provider_message_id": str(provider_message_id or "")[:200] or None,
            "p_finished_at": now.isoformat(),
        },
    ).execute()
    rows = _rows(response)
    return rows[0] if rows else None


def cleanup_delivery_data(*, limit: int = 1000, client=None) -> dict[str, int]:
    response = (client or service_supabase).rpc(
        "cleanup_notification_delivery_data",
        {
            "p_now": _now().isoformat(),
            "p_limit": max(1, min(int(limit), 10000)),
        },
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else {}
    return {
        "deliveries": int((data or {}).get("deliveries") or 0),
        "outbox": int((data or {}).get("outbox") or 0),
    }


def get_delivery_metrics(*, client=None) -> dict[str, int]:
    response = (
        (client or service_supabase)
        .table("notification_deliveries")
        .select("status")
        .in_("status", ["pending", "processing", "sent", "dead"])
        .limit(5000)
        .execute()
    )
    rows = _rows(response)
    return {
        f"deliveries_{status}": sum(row.get("status") == status for row in rows)
        for status in ("pending", "processing", "sent", "dead")
    }


def get_delivery_channel_metrics(*, client=None) -> dict[str, Any]:
    rows = _rows(
        (client or service_supabase).table("notification_deliveries")
        .select("channel,status,created_at,sent_at,last_error_code")
        .in_("status", ["pending", "processing", "sent", "dead"])
        .limit(5000)
        .execute()
    )
    now = _now()
    result: dict[str, Any] = {}
    for channel in ("internal", "email", "web_push"):
        selected = [row for row in rows if row.get("channel") == channel]
        pending = [row for row in selected if row.get("status") in {"pending", "processing"}]
        dates = []
        for row in pending:
            try:
                value = datetime.fromisoformat(str(row.get("created_at") or "").replace("Z", "+00:00"))
                dates.append(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
            except ValueError:
                continue
        sent_dates = sorted(str(row.get("sent_at")) for row in selected if row.get("sent_at"))
        errors = [str(row.get("last_error_code")) for row in selected if row.get("last_error_code")]
        result[channel] = {
            "pending": sum(row.get("status") == "pending" for row in selected),
            "processing": sum(row.get("status") == "processing" for row in selected),
            "sent": sum(row.get("status") == "sent" for row in selected),
            "dead": sum(row.get("status") == "dead" for row in selected),
            "oldest_queued_age_seconds": max(0, int((now - min(dates)).total_seconds())) if dates else 0,
            "last_success_at": sent_dates[-1] if sent_dates else None,
            "last_error_code": errors[-1] if errors else None,
        }
    return result
