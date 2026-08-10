from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from database import service_supabase
from services.calendar_workspace_cache_service import invalidate_calendar_workspace_cache


logger = logging.getLogger(__name__)
ACTIVE_TASK_STATUSES = ["todo", "in_progress", "blocked", "done"]


def _rows(response) -> list[dict[str, Any]]:
    return getattr(response, "data", None) or []


def archive_ended_calendar_tasks(
    *, limit: int = 100, now: datetime | None = None, client=None
) -> int:
    """Archive non-recurring tasks after their scheduled end time."""
    database_client = client or service_supabase
    cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    due_tasks = _rows(
        database_client.table("calendar_tasks")
        .select("id,tenant_id,status,version,scheduled_end,recurrence_rule")
        .in_("status", ACTIVE_TASK_STATUSES)
        .is_("recurrence_rule", "null")
        .lte("scheduled_end", cutoff)
        .order("scheduled_end")
        .limit(max(1, min(int(limit), 500)))
        .execute()
    )
    archived = 0
    affected_tenants: set[int] = set()
    for task in due_tasks:
        task_id = str(task.get("id") or "")
        tenant_id = task.get("tenant_id")
        version = int(task.get("version") or 1)
        if not task_id or tenant_id is None or not task.get("scheduled_end"):
            continue
        updated = _rows(
            database_client.table("calendar_tasks")
            .update({"status": "cancelled", "version": version + 1})
            .eq("id", task_id)
            .eq("tenant_id", tenant_id)
            .eq("version", version)
            .in_("status", ACTIVE_TASK_STATUSES)
            .execute()
        )
        if not updated:
            continue
        database_client.table("calendar_task_reminders").update({
            "delivery_status": "cancelled",
            "failure_code": "task_automatically_archived",
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).in_(
            "delivery_status", ["scheduled", "queued"]
        ).execute()
        archived += 1
        affected_tenants.add(int(tenant_id))
    for tenant_id in affected_tenants:
        invalidate_calendar_workspace_cache(tenant_id)
    if archived:
        logger.info("calendar_tasks.automatically_archived", extra={"count": archived})
    return archived
