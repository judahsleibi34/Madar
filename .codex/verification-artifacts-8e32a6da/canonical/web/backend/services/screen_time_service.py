from datetime import date, datetime, timedelta, timezone
from typing import Any

from database import service_supabase


MAX_HEARTBEAT_SECONDS = 60


def current_week_start() -> date:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


def _schema_before_screen_time(error: Exception) -> bool:
    raw = str(error).lower()
    missing_object = (
        "workspace_screen_time" in raw or "record_workspace_screen_time" in raw
    ) and (
        "pgrst202" in raw
        or "pgrst205" in raw
        or "schema cache" in raw
        or "does not exist" in raw
        or "could not find" in raw
    )
    if not missing_object:
        return False
    try:
        response = (
            service_supabase.table("application_schema_state")
            .select("schema_version")
            .eq("contract_key", "core")
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return len(rows) == 1 and int(rows[0].get("schema_version", -1)) < 92
    except Exception:
        return False


def record_screen_time(*, tenant_id: int, user_id: int, active_seconds: int) -> None:
    seconds = max(1, min(MAX_HEARTBEAT_SECONDS, int(active_seconds)))
    try:
        service_supabase.rpc(
            "record_workspace_screen_time",
            {
                "p_tenant_id": int(tenant_id),
                "p_user_id": int(user_id),
                "p_activity_date": datetime.now(timezone.utc).date().isoformat(),
                "p_active_seconds": seconds,
            },
        ).execute()
    except Exception as error:
        if not _schema_before_screen_time(error):
            raise


def _rows(response) -> list[dict[str, Any]]:
    return getattr(response, "data", None) or []


def get_weekly_screen_time(
    *,
    tenant_id: int,
    current_user_id: int,
    project_id: str | None = None,
    period: str = "week",
) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    if period == "today":
        range_start = today
    elif period == "month":
        range_start = today.replace(day=1)
    else:
        period = "week"
        range_start = today - timedelta(days=6)
    range_end = today

    try:
        activity_rows = _rows(
            service_supabase.table("workspace_screen_time_daily")
            .select("user_id,active_seconds")
            .eq("tenant_id", tenant_id)
            .gte("activity_date", range_start.isoformat())
            .lte("activity_date", range_end.isoformat())
            .execute()
        )
    except Exception as error:
        if not _schema_before_screen_time(error):
            raise
        activity_rows = []
    seconds_by_user: dict[int, int] = {}
    for row in activity_rows:
        user_id = int(row.get("user_id") or 0)
        if user_id:
            seconds_by_user[user_id] = seconds_by_user.get(user_id, 0) + int(
                row.get("active_seconds") or 0
            )

    role_by_user: dict[int, str] = {}
    workspace_rows = _rows(
        service_supabase.table("tenant_memberships")
        .select("user_id,role,status")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .execute()
    )
    for row in workspace_rows:
        user_id = int(row.get("user_id") or 0)
        if user_id:
            role_by_user[user_id] = str(row.get("role") or "member")

    site_query = (
        service_supabase.table("tenant_site_memberships")
        .select("id,user_id,role,status")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
    )
    site_rows = _rows(site_query.execute())

    allowed_site_memberships: set[str] | None = None
    if project_id:
        assignment_rows = _rows(
            service_supabase.table("tenant_site_project_role_assignments")
            .select("membership_id")
            .eq("project_id", project_id)
            .execute()
        )
        allowed_site_memberships = {
            str(row.get("membership_id"))
            for row in assignment_rows
            if row.get("membership_id") is not None
        }

    for row in site_rows:
        if (
            allowed_site_memberships is not None
            and str(row.get("id")) not in allowed_site_memberships
        ):
            continue
        user_id = int(row.get("user_id") or 0)
        if user_id and user_id not in role_by_user:
            role_by_user[user_id] = str(row.get("role") or "site member")

    role_by_user.setdefault(int(current_user_id), "member")
    user_ids = sorted(role_by_user)
    if not user_ids:
        return {
            "period": period,
            "range_start": range_start.isoformat(),
            "range_end": range_end.isoformat(),
            "total_seconds": 0,
            "users": [],
        }

    user_rows = _rows(
        service_supabase.table("users")
        .select("id,first_name,last_name,email")
        .in_("id", user_ids)
        .execute()
    )
    users = []
    for row in user_rows:
        user_id = int(row.get("id") or 0)
        first_name = str(row.get("first_name") or "").strip()
        last_name = str(row.get("last_name") or "").strip()
        name = " ".join(part for part in (first_name, last_name) if part).strip()
        if not name:
            name = str(row.get("email") or "User").split("@", 1)[0]
        users.append(
            {
                "user_id": user_id,
                "name": name,
                "role": role_by_user.get(user_id, "member").replace("_", " "),
                "active_seconds": seconds_by_user.get(user_id, 0),
                "is_current_user": user_id == int(current_user_id),
            }
        )

    users.sort(key=lambda item: (-item["active_seconds"], item["name"].lower()))
    return {
        "period": period,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "total_seconds": sum(item["active_seconds"] for item in users),
        "users": users,
    }
