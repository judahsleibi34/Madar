from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from fastapi import HTTPException

from database import service_supabase


CALENDAR_ROLES = frozenset({"availability", "viewer", "editor", "owner"})
CALENDAR_CAPABILITIES = frozenset({
    "view_metadata",
    "view_availability",
    "view_details",
    "create_event",
    "update_event",
    "delete_event",
    "manage_tasks",
    "manage_reminders",
    "view_history",
    "manage_members",
    "view_conflicts",
    "review_invitations",
    "view_sync_state",
    "manage_oauth_connection",
    "trigger_sync",
    "import_export",
})
ROLE_CAPABILITIES = {
    "availability": frozenset({"view_metadata", "view_availability"}),
    "viewer": frozenset({"view_metadata", "view_availability", "view_details", "import_export"}),
    "editor": frozenset({
        "view_metadata", "view_availability", "view_details", "create_event",
        "update_event", "delete_event", "manage_tasks", "manage_reminders",
        "view_history", "view_conflicts", "review_invitations", "trigger_sync",
        "view_sync_state", "import_export",
    }),
    "owner": CALENDAR_CAPABILITIES,
}
SHARED_VISIBILITIES = frozenset({"team", "organization", "public"})
MAX_ACCESSIBLE_CALENDARS = 500


@dataclass(frozen=True)
class CalendarAccess:
    calendar: dict[str, Any]
    role: str
    capabilities: frozenset[str]
    tenant_admin_override: bool = False

    def allows(self, capability: str) -> bool:
        return capability in CALENDAR_CAPABILITIES and capability in self.capabilities


def _rows(response) -> list[dict[str, Any]]:
    return getattr(response, "data", None) or []


def _is_tenant_admin(context) -> bool:
    return (
        str(getattr(context, "membership_status", "") or "").lower() == "active"
        and str(getattr(context, "role", "") or "").lower() in {"owner", "admin"}
    )


def _require_active_context(context) -> None:
    if str(getattr(context, "membership_status", "") or "").lower() != "active":
        raise HTTPException(status_code=403, detail="Active tenant membership required")


def _same_integer(left: Any, right: Any) -> bool:
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return False


def _membership_role(*, calendar_id: str, context, client) -> str | None:
    rows = _rows(
        client.table("calendar_memberships")
        .select("role")
        .eq("calendar_id", calendar_id)
        .eq("tenant_id", context.tenant_id)
        .eq("user_id", context.user_id)
        .limit(1)
        .execute()
    )
    role = str(rows[0].get("role") or "").lower() if rows else ""
    return role if role in CALENDAR_ROLES else None


def resolve_calendar_access(
    context,
    calendar_id: str,
    *,
    client=None,
    calendar: dict[str, Any] | None = None,
) -> CalendarAccess:
    _require_active_context(context)
    database_client = client or service_supabase
    if calendar is None:
        rows = _rows(
            database_client.table("calendars")
            .select("*")
            .eq("id", str(calendar_id))
            .eq("tenant_id", context.tenant_id)
            .limit(1)
            .execute()
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Calendar not found")
        calendar = rows[0]
    elif str(calendar.get("id")) != str(calendar_id) or not _same_integer(
        calendar.get("tenant_id"), context.tenant_id
    ):
        raise HTTPException(status_code=404, detail="Calendar not found")

    if _is_tenant_admin(context):
        return CalendarAccess(calendar, "owner", CALENDAR_CAPABILITIES, True)
    if _same_integer(calendar.get("owner_user_id"), context.user_id):
        return CalendarAccess(calendar, "owner", CALENDAR_CAPABILITIES)

    role = _membership_role(
        calendar_id=str(calendar_id), context=context, client=database_client
    )
    if role:
        return CalendarAccess(calendar, role, ROLE_CAPABILITIES[role])
    if str(calendar.get("visibility") or "private").lower() in SHARED_VISIBILITIES:
        return CalendarAccess(calendar, "viewer", ROLE_CAPABILITIES["viewer"])
    raise HTTPException(status_code=404, detail="Calendar not found")


def require_calendar_access(
    context,
    calendar_id: str,
    capability: str,
    *,
    client=None,
    calendar: dict[str, Any] | None = None,
) -> CalendarAccess:
    if capability not in CALENDAR_CAPABILITIES:
        raise HTTPException(status_code=403, detail="Calendar access denied")
    access = resolve_calendar_access(
        context, calendar_id, client=client, calendar=calendar
    )
    if not access.allows(capability):
        raise HTTPException(status_code=403, detail="Calendar access denied")
    return access


def list_accessible_calendars(context, *, client=None) -> list[CalendarAccess]:
    _require_active_context(context)
    database_client = client or service_supabase
    if _is_tenant_admin(context):
        calendars = _rows(
            database_client.table("calendars")
            .select("*")
            .eq("tenant_id", context.tenant_id)
            .order("created_at")
            .limit(MAX_ACCESSIBLE_CALENDARS)
            .execute()
        )
        return [CalendarAccess(calendar, "owner", CALENDAR_CAPABILITIES, True) for calendar in calendars]
    else:
        memberships = _rows(
            database_client.table("calendar_memberships")
            .select("calendar_id,role")
            .eq("tenant_id", context.tenant_id)
            .eq("user_id", context.user_id)
            .limit(MAX_ACCESSIBLE_CALENDARS)
            .execute()
        )
        membership_roles = {
            str(row.get("calendar_id")): str(row.get("role") or "").lower()
            for row in memberships
            if str(row.get("role") or "").lower() in CALENDAR_ROLES
        }
        membership_ids = [str(row.get("calendar_id")) for row in memberships if row.get("calendar_id")]
        filters = [
            f"owner_user_id.eq.{int(context.user_id)}",
            "visibility.in.(team,organization,public)",
        ]
        if membership_ids:
            filters.append("id.in.(" + ",".join(membership_ids) + ")")
        calendars = _rows(
            database_client.table("calendars")
            .select("*")
            .eq("tenant_id", context.tenant_id)
            .or_(",".join(filters))
            .order("created_at")
            .limit(MAX_ACCESSIBLE_CALENDARS)
            .execute()
        )
    accesses: list[CalendarAccess] = []
    for calendar in calendars:
        calendar_id = str(calendar.get("id"))
        if _same_integer(calendar.get("owner_user_id"), context.user_id):
            accesses.append(CalendarAccess(calendar, "owner", CALENDAR_CAPABILITIES))
            continue
        role = membership_roles.get(calendar_id)
        if role:
            accesses.append(CalendarAccess(calendar, role, ROLE_CAPABILITIES[role]))
            continue
        if str(calendar.get("visibility") or "private").lower() in SHARED_VISIBILITIES:
            accesses.append(CalendarAccess(calendar, "viewer", ROLE_CAPABILITIES["viewer"]))
    return accesses


def availability_event(row: dict[str, Any]) -> dict[str, Any]:
    interval = "\x1f".join(
        str(row.get(field) or "") for field in ("calendar_id", "starts_at", "ends_at")
    )
    opaque_id = hashlib.sha256(interval.encode()).hexdigest()[:32]
    return {
        "id": f"availability::{opaque_id}",
        "calendar_id": row.get("calendar_id"),
        "starts_at": row.get("starts_at"),
        "ends_at": row.get("ends_at"),
        "transparency": "free" if row.get("transparency") == "free" else "busy",
        "read_only": True,
        "availability_only": True,
    }


def public_calendar_metadata(access: CalendarAccess) -> dict[str, Any]:
    calendar = access.calendar
    payload = {
        "id": calendar.get("id"),
        "name": calendar.get("name"),
        "color": calendar.get("color"),
        "timezone": calendar.get("timezone"),
        "visibility": calendar.get("visibility"),
        "is_default": bool(calendar.get("is_default")),
        "access_role": access.role,
    }
    if access.role == "availability":
        payload["name"] = "Availability"
        payload["is_default"] = False
    return payload
