from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from database import service_supabase

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(response) -> list[dict[str, Any]]:
    return getattr(response, "data", None) or []


def _web_push_enabled() -> bool:
    return bool(
        os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
        and os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
        and os.getenv("WEB_PUSH_VAPID_SUBJECT", "").strip()
    )


def get_web_push_public_config() -> dict[str, Any]:
    public_key = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()

    return {
        "enabled": bool(public_key and _web_push_enabled()),
        "public_key": public_key,
    }


def list_user_notifications(
    *,
    user_id: int | str,
    limit: int = 30,
    unread_only: bool = False,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    query = (
        service_supabase.table("user_notifications")
        .select("*")
        .eq("user_id", int(user_id))
        .order("created_at", desc=True)
        .limit(safe_limit)
    )

    if unread_only:
        query = query.is_("read_at", "null")

    response = query.execute()
    notifications = [_format_notification(row) for row in _rows(response)]

    unread_response = (
        service_supabase.table("user_notifications")
        .select("id")
        .eq("user_id", int(user_id))
        .is_("read_at", "null")
        .limit(1000)
        .execute()
    )

    return {
        "items": notifications,
        "notifications": notifications,
        "unread_count": len(_rows(unread_response)),
    }


def mark_notification_read(*, user_id: int | str, notification_id: str) -> dict[str, Any] | None:
    response = (
        service_supabase.table("user_notifications")
        .update({"read_at": _utc_now()})
        .eq("id", notification_id)
        .eq("user_id", int(user_id))
        .execute()
    )
    rows = _rows(response)
    return _format_notification(rows[0]) if rows else None


def mark_all_notifications_read(*, user_id: int | str) -> int:
    response = (
        service_supabase.table("user_notifications")
        .update({"read_at": _utc_now()})
        .eq("user_id", int(user_id))
        .is_("read_at", "null")
        .execute()
    )
    return len(_rows(response))


def upsert_web_push_subscription(
    *,
    user_id: int | str,
    tenant_id: int | str | None,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
) -> dict[str, Any]:
    payload = {
        "user_id": int(user_id),
        "tenant_id": int(tenant_id) if tenant_id is not None else None,
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth,
        "user_agent": user_agent[:1000],
        "last_seen_at": _utc_now(),
        "revoked_at": None,
    }

    try:
        response = (
            service_supabase.table("web_push_subscriptions")
            .upsert(payload, on_conflict="endpoint")
            .execute()
        )
    except TypeError:
        existing = (
            service_supabase.table("web_push_subscriptions")
            .select("id")
            .eq("endpoint", endpoint)
            .limit(1)
            .execute()
        )
        existing_rows = _rows(existing)

        if existing_rows:
            response = (
                service_supabase.table("web_push_subscriptions")
                .update(payload)
                .eq("id", existing_rows[0]["id"])
                .execute()
            )
        else:
            response = service_supabase.table("web_push_subscriptions").insert(payload).execute()

    rows = _rows(response)
    return rows[0] if rows else payload


def revoke_web_push_subscription(*, user_id: int | str, endpoint: str) -> int:
    response = (
        service_supabase.table("web_push_subscriptions")
        .update({"revoked_at": _utc_now()})
        .eq("user_id", int(user_id))
        .eq("endpoint", endpoint)
        .execute()
    )
    return len(_rows(response))


def create_tenant_notification_event(
    *,
    tenant_id: int | str,
    event_type: str,
    source_type: str,
    source_id: str | None,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    event_payload = {
        "tenant_id": int(tenant_id),
        "event_type": event_type,
        "source_type": source_type,
        "source_id": source_id,
        "title": title[:200],
        "body": body[:1000],
        "data": data or {},
    }

    try:
        event_response = service_supabase.table("notification_events").insert(event_payload).execute()
        event_rows = _rows(event_response)
        event = event_rows[0] if event_rows else event_payload
        event_id = event.get("id")
        recipients = _list_active_tenant_recipients(tenant_id)

        if recipients and event_id:
            inbox_payload = [
                {
                    "event_id": event_id,
                    "tenant_id": int(tenant_id),
                    "user_id": int(user["user_id"]),
                    "event_type": event_type,
                    "title": event_payload["title"],
                    "body": event_payload["body"],
                    "data": event_payload["data"],
                }
                for user in recipients
                if user.get("user_id") is not None
            ]

            if inbox_payload:
                service_supabase.table("user_notifications").insert(inbox_payload).execute()

        _send_tenant_push_notifications(
            tenant_id=tenant_id,
            title=event_payload["title"],
            body=event_payload["body"],
            data={
                **event_payload["data"],
                "event_type": event_type,
                "source_type": source_type,
                "source_id": source_id,
            },
        )
        return event

    except Exception as error:
        logger.warning(
            "notifications.event_create_failed",
            extra={
                "tenant_id": tenant_id,
                "event_type": event_type,
                "error_type": type(error).__name__,
            },
        )
        return None


def create_builder_block_event_notification(
    *,
    tenant_id: int | str,
    event_type: str,
    block_type: str,
    source_id: str | None,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return create_tenant_notification_event(
        tenant_id=tenant_id,
        event_type=event_type,
        source_type=block_type,
        source_id=source_id,
        title=title,
        body=body,
        data={
            "block_type": block_type,
            **(data or {}),
        },
    )


def _list_active_tenant_recipients(tenant_id: int | str) -> list[dict[str, Any]]:
    response = (
        service_supabase.table("tenant_memberships")
        .select("user_id, role, status")
        .eq("tenant_id", int(tenant_id))
        .eq("status", "active")
        .execute()
    )
    return _rows(response)


def _send_tenant_push_notifications(
    *,
    tenant_id: int | str,
    title: str,
    body: str,
    data: dict[str, Any],
) -> None:
    if not _web_push_enabled():
        return

    response = (
        service_supabase.table("web_push_subscriptions")
        .select("id, endpoint, p256dh, auth")
        .eq("tenant_id", int(tenant_id))
        .is_("revoked_at", "null")
        .execute()
    )

    for subscription in _rows(response):
        _send_web_push(subscription=subscription, title=title, body=body, data=data)


def _send_web_push(
    *,
    subscription: dict[str, Any],
    title: str,
    body: str,
    data: dict[str, Any],
) -> None:
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("notifications.web_push_dependency_missing")
        return

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "data": data,
        },
        separators=(",", ":"),
    )
    subscription_info = {
        "endpoint": subscription.get("endpoint"),
        "keys": {
            "p256dh": subscription.get("p256dh"),
            "auth": subscription.get("auth"),
        },
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip(),
            vapid_claims={"sub": os.getenv("WEB_PUSH_VAPID_SUBJECT", "").strip()},
        )
    except WebPushException as error:
        status_code = getattr(getattr(error, "response", None), "status_code", None)

        if status_code in {404, 410}:
            service_supabase.table("web_push_subscriptions").update(
                {"revoked_at": _utc_now()}
            ).eq("id", subscription.get("id")).execute()
            return

        logger.warning(
            "notifications.web_push_send_failed",
            extra={"error_type": type(error).__name__, "status_code": status_code},
        )
    except Exception as error:
        logger.warning(
            "notifications.web_push_send_failed",
            extra={"error_type": type(error).__name__},
        )


def _format_notification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "event_id": row.get("event_id"),
        "tenant_id": row.get("tenant_id"),
        "event_type": row.get("event_type"),
        "title": row.get("title"),
        "body": row.get("body"),
        "data": row.get("data") or {},
        "read_at": row.get("read_at"),
        "created_at": row.get("created_at"),
        "unread": not bool(row.get("read_at")),
    }
