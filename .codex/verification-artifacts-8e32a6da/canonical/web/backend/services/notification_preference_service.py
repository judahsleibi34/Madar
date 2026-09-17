"""Tenant-scoped, sparse user notification preference overrides."""
from __future__ import annotations

from typing import Any

from database import service_supabase


PREFERENCE_CATEGORIES = {
    "calendar": {"in_app", "push", "email"},
    "reservations": {"in_app", "push"},
    "forms": {"in_app", "push"},
    "general": {"in_app", "push"},
}


def notification_category(*, event_type: Any = None, source_type: Any = None) -> str:
    event_value = str(event_type or "").lower()
    source_value = str(source_type or "").lower()
    if "calendar" in event_value or source_value in {"calendar_event", "calendar_task"}:
        return "calendar"
    if "reservation" in event_value or "reservation" in source_value:
        return "reservations"
    if "form" in event_value or source_value in {"form", "formblock"}:
        return "forms"
    return "general"


def preference_channel_for_delivery(channel: str) -> str | None:
    return {"internal": "in_app", "web_push": "push", "email": "email"}.get(str(channel or ""))


def allowed_preference(category: str, channel: str) -> bool:
    return channel in PREFERENCE_CATEGORIES.get(category, set())


def list_notification_preferences(*, tenant_id: int | str, user_id: int | str) -> list[dict[str, Any]]:
    response = (
        service_supabase.table("notification_preferences")
        .select("category,channel,enabled,updated_at")
        .eq("tenant_id", int(tenant_id))
        .eq("user_id", int(user_id))
        .execute()
    )
    return [row for row in (getattr(response, "data", None) or []) if isinstance(row, dict)]


def preference_enabled(
    *, tenant_id: int | str, user_id: int | str, category: str, channel: str
) -> bool:
    """Missing rows deliberately preserve the historic enabled behavior."""
    if not allowed_preference(category, channel):
        return True
    try:
        response = (
            service_supabase.table("notification_preferences")
            .select("enabled")
            .eq("tenant_id", int(tenant_id))
            .eq("user_id", int(user_id))
            .eq("category", category)
            .eq("channel", channel)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return bool(rows[0].get("enabled", True)) if rows else True
    except Exception:
        # During rolling deployment before migration 080, preserve delivery.
        return True


def set_notification_preference(
    *, tenant_id: int | str, user_id: int | str, category: str, channel: str, enabled: bool
) -> dict[str, Any]:
    if not allowed_preference(category, channel):
        raise ValueError("notification_preference_not_supported")
    payload = {
        "tenant_id": int(tenant_id),
        "user_id": int(user_id),
        "category": category,
        "channel": channel,
        "enabled": bool(enabled),
    }
    response = service_supabase.table("notification_preferences").upsert(
        payload, on_conflict="tenant_id,user_id,category,channel"
    ).execute()
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else payload
