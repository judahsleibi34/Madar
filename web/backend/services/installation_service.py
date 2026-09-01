from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any

from database import service_supabase
from postgrest.exceptions import APIError


logger = logging.getLogger(__name__)
SAFE_POSTGREST_CODE = re.compile(r"^[A-Z0-9_]{1,20}$", re.IGNORECASE)


class PushSubscriptionBindingError(RuntimeError):
    """Sanitized expected or dependency failure from the binding RPC."""

    def __init__(self, *, status_code: int, code: str, message: str):
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.public_message = message


def _safe_postgrest_code(error: APIError) -> str:
    value = str(getattr(error, "code", "") or "").strip()
    return value if SAFE_POSTGREST_CODE.fullmatch(value) else "postgrest_error"


def _binding_error(error: APIError) -> PushSubscriptionBindingError:
    # Only compare known server-authored sentinel messages. Never return or log
    # raw PostgREST details, which can contain database or request material.
    message = str(getattr(error, "message", "") or "").strip().lower()
    if message == "active_tenant_membership_required":
        return PushSubscriptionBindingError(
            status_code=403,
            code="active_tenant_membership_required",
            message="An active workspace membership is required.",
        )
    if message == "app_installation_not_available":
        return PushSubscriptionBindingError(
            status_code=409,
            code="installation_unavailable",
            message="The application installation is not available.",
        )
    return PushSubscriptionBindingError(
        status_code=503,
        code="push_subscription_unavailable",
        message="Push subscription registration is temporarily unavailable.",
    )


def _row(response) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return data
    return data[0] if data else None


def register_installation(
    *,
    user_id: int | str,
    tenant_id: int | str,
    installation_id: str,
    platform: str,
    display_mode: str,
    notification_permission: str,
    installed_confirmed: bool,
) -> dict[str, Any] | None:
    return _row(
        service_supabase.rpc(
            "register_app_installation",
            {
                "p_user_id": int(user_id),
                "p_tenant_id": int(tenant_id),
                "p_installation_id": str(installation_id),
                "p_platform": platform,
                "p_display_mode": display_mode,
                "p_notification_permission": notification_permission,
                "p_installed_confirmed": bool(installed_confirmed),
            },
        ).execute()
    )


def bind_push_subscription(
    *,
    user_id: int | str,
    tenant_id: int | str,
    installation_id: str,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
) -> dict[str, Any] | None:
    try:
        return _row(
            service_supabase.rpc(
                "bind_web_push_subscription_to_installation",
                {
                    "p_user_id": int(user_id),
                    "p_tenant_id": int(tenant_id),
                    "p_installation_id": str(installation_id),
                    "p_endpoint": endpoint,
                    "p_p256dh": p256dh,
                    "p_auth": auth,
                    "p_user_agent": user_agent[:1000],
                },
            ).execute()
        )
    except APIError as error:
        logger.warning(
            "notifications.push_subscription_binding_failed",
            extra={
                "error_type": type(error).__name__,
                "error_code": _safe_postgrest_code(error),
            },
        )
        raise _binding_error(error) from error


def revoke_installation_push_bindings(
    *, user_id: int | str, installation_id: str
) -> int:
    response = service_supabase.rpc(
        "revoke_installation_push_subscriptions",
        {
            "p_user_id": int(user_id),
            "p_installation_id": str(installation_id),
        },
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, int):
        return data
    if isinstance(data, list) and data:
        value = data[0]
        if isinstance(value, dict):
            value = next(iter(value.values()), 0)
        return int(value or 0)
    return int(data or 0)


INSTALLATION_PUBLIC_FIELDS = (
    "id,installation_id,platform,display_mode,notification_permission,"
    "notifications_enabled,first_seen_at,last_seen_at,installed_confirmed_at,revoked_at"
)


def list_user_installations(
    *, user_id: int | str, current_installation_id: str | None = None
) -> list[dict[str, Any]]:
    """List active installations owned by one authenticated account.

    The client installation UUID is used only as a user-scoped current-device
    hint and is deliberately omitted from the response records.
    """
    rows = (
        service_supabase.table("app_installations")
        .select(INSTALLATION_PUBLIC_FIELDS)
        .eq("user_id", int(user_id))
        .is_("revoked_at", "null")
        .order("last_seen_at", desc=True)
        .execute()
    )
    installations = getattr(rows, "data", None) or []
    installation_ids = [str(row["id"]) for row in installations if row.get("id")]
    active_subscription_ids: set[str] = set()
    if installation_ids:
        subscriptions = (
            service_supabase.table("web_push_subscriptions")
            .select("app_installation_id")
            .in_("app_installation_id", installation_ids)
            .is_("revoked_at", "null")
            .execute()
        )
        active_subscription_ids = {
            str(row["app_installation_id"])
            for row in (getattr(subscriptions, "data", None) or [])
            if row.get("app_installation_id")
        }

    current_value = str(current_installation_id or "")
    result = []
    for row in installations:
        result.append(
            {
                "id": str(row.get("id")),
                "platform": row.get("platform") or "unknown",
                "display_mode": row.get("display_mode") or "browser",
                "notification_permission": row.get("notification_permission") or "unknown",
                "notifications_enabled": bool(row.get("notifications_enabled")),
                "has_active_push_subscription": str(row.get("id")) in active_subscription_ids,
                "installed_confirmed_at": row.get("installed_confirmed_at"),
                "first_seen_at": row.get("first_seen_at"),
                "last_seen_at": row.get("last_seen_at"),
                "is_current": bool(current_value and str(row.get("installation_id")) == current_value),
            }
        )
    return result


def revoke_user_installation(
    *, user_id: int | str, installation_record_id: str
) -> dict[str, Any] | None:
    """Revoke one owned installation while retaining its historical rows."""
    response = (
        service_supabase.table("app_installations")
        .select("id,revoked_at")
        .eq("id", str(installation_record_id))
        .eq("user_id", int(user_id))
        .limit(1)
        .execute()
    )
    installation = _row(response)
    if not installation:
        return None
    if installation.get("revoked_at"):
        return installation

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        service_supabase.table("app_installations")
        .update({"revoked_at": now, "notifications_enabled": False, "updated_at": now})
        .eq("id", str(installation_record_id))
        .eq("user_id", int(user_id))
        .execute()
    )
    revoked = _row(updated)
    if not revoked:
        return None

    # Revoking the parent makes delivery ineligible immediately. Child rows
    # remain as tombstones because notification_deliveries may reference them.
    try:
        (
            service_supabase.table("web_push_subscriptions")
            .update({"revoked_at": now})
            .eq("app_installation_id", str(installation_record_id))
            .is_("revoked_at", "null")
            .execute()
        )
    except Exception:
        # The revoked parent is already ineligible at resolution and send time.
        logger.exception(
            "installation.push_binding_cleanup_failed",
            extra={"installation_record_id": str(installation_record_id)},
        )
    return revoked


def disable_installation_notifications(
    *, user_id: int | str, installation_id: str
) -> dict[str, Any] | None:
    """Disable Push only for the authenticated user's current client identity."""
    response = (
        service_supabase.table("app_installations")
        .select("id,revoked_at")
        .eq("user_id", int(user_id))
        .eq("installation_id", str(installation_id))
        .limit(1)
        .execute()
    )
    installation = _row(response)
    if not installation or installation.get("revoked_at"):
        return None

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        service_supabase.table("app_installations")
        .update({"notifications_enabled": False, "updated_at": now})
        .eq("id", str(installation["id"]))
        .eq("user_id", int(user_id))
        .is_("revoked_at", "null")
        .execute()
    )
    disabled = _row(updated)
    if not disabled:
        return None
    try:
        (
            service_supabase.table("web_push_subscriptions")
            .update({"revoked_at": now})
            .eq("app_installation_id", str(installation["id"]))
            .is_("revoked_at", "null")
            .execute()
        )
    except Exception:
        # notifications_enabled=false already makes this installation ineligible.
        logger.exception(
            "installation.push_binding_cleanup_failed",
            extra={"installation_record_id": str(installation["id"])},
        )
    return disabled
