from __future__ import annotations

from typing import Any

from database import service_supabase


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
