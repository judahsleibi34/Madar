from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil.rrule import rrulestr

from database import service_supabase
from services.notification_outbox_service import enqueue_notification


def _rows(response) -> list[dict[str, Any]]:
    return getattr(response, "data", None) or []


def _datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def next_task_reminder_time(payload: dict[str, Any]) -> str | None:
    rule_text = str(payload.get("task_recurrence_rule") or "").strip()
    if not rule_text:
        return None
    recurrence_start = _datetime(payload["task_recurrence_start"])
    delivered_for = _datetime(payload["scheduled_for"])
    minutes_before = int(payload.get("minutes_before") or 0)
    occurrence_start = delivered_for + timedelta(minutes=minutes_before)
    next_occurrence = rrulestr(rule_text, dtstart=recurrence_start).after(occurrence_start, inc=False)
    return (next_occurrence - timedelta(minutes=minutes_before)).isoformat() if next_occurrence else None


def enqueue_due_calendar_reminders(*, limit: int = 100, client=None) -> int:
    database_client = client or service_supabase
    due = _rows(
        database_client.table("calendar_event_reminders")
        .select("*")
        .eq("delivery_status", "scheduled")
        .lte("scheduled_for", datetime.now(timezone.utc).isoformat())
        .order("scheduled_for")
        .limit(max(1, min(int(limit), 500)))
        .execute()
    )
    queued = 0
    for reminder in due:
        event_rows = _rows(
            database_client.table("calendar_events")
            .select("*")
            .eq("id", reminder.get("event_id"))
            .eq("tenant_id", reminder.get("tenant_id"))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        event = event_rows[0] if event_rows else None
        if not event or event.get("status") == "cancelled":
            database_client.table("calendar_event_reminders").update(
                {"delivery_status": "cancelled"}
            ).eq("id", reminder.get("id")).execute()
            continue
        configured_channel = str(reminder.get("channel") or "in_app")
        outbox_channel = "internal" if configured_channel == "in_app" else configured_channel
        user_id = event.get("created_by")
        occurrence_start = _datetime(reminder.get("scheduled_for")) + timedelta(
            minutes=int(reminder.get("minutes_before") or 0)
        )
        payload = {
            "event_type": "calendar_reminder",
            "source_type": "calendar_event",
            "source_id": str(event.get("id") or ""),
            "title": str(event.get("title") or "Upcoming event")[:200],
            "body": f"Starts at {event.get('starts_at')}",
            "data": {
                "event_id": event.get("id"),
                "calendar_id": event.get("calendar_id"),
                "starts_at": event.get("starts_at"),
                "reminder_id": reminder.get("id"),
            },
            "reminder_id": reminder.get("id"),
        }
        queued_row = enqueue_notification(
            channel=outbox_channel,
            template="calendar_reminder",
            tenant_id=int(reminder["tenant_id"]),
            user_id=int(user_id) if user_id is not None else None,
            recipient_reference=f"user:{user_id}" if configured_channel == "email" and user_id else None,
            deduplication_key=f"calendar-reminder:{reminder['id']}",
            payload=payload,
            client=database_client,
        )
        if queued_row:
            database_client.table("calendar_event_reminders").update(
                {"delivery_status": "queued", "failure_code": None}
            ).eq("id", reminder.get("id")).eq("delivery_status", "scheduled").execute()
            queued += 1
    task_due = _rows(
        database_client.table("calendar_task_reminders")
        .select("*")
        .eq("delivery_status", "scheduled")
        .lte("scheduled_for", datetime.now(timezone.utc).isoformat())
        .order("scheduled_for")
        .limit(max(1, min(int(limit), 500)))
        .execute()
    )
    for reminder in task_due:
        task_rows = _rows(
            database_client.table("calendar_tasks")
            .select("*")
            .eq("id", reminder.get("task_id"))
            .eq("tenant_id", reminder.get("tenant_id"))
            .limit(1)
            .execute()
        )
        task = task_rows[0] if task_rows else None
        if not task or task.get("status") in {"done", "cancelled"} or not task.get("scheduled_start"):
            database_client.table("calendar_task_reminders").update(
                {"delivery_status": "cancelled"}
            ).eq("id", reminder.get("id")).execute()
            continue
        configured_channel = str(reminder.get("channel") or "in_app")
        outbox_channel = "internal" if configured_channel == "in_app" else configured_channel
        user_id = task.get("owner_user_id")
        payload = {
            "event_type": "calendar_task_reminder",
            "source_type": "calendar_task",
            "source_id": str(task.get("id") or ""),
            "title": str(task.get("title") or "Upcoming task")[:200],
            "body": f"Scheduled for {occurrence_start.isoformat()}",
            "data": {
                "task_id": task.get("id"),
                "scheduled_start": occurrence_start.isoformat(),
                "reminder_id": reminder.get("id"),
            },
            "reminder_id": reminder.get("id"),
            "reminder_source": "task",
            "scheduled_for": reminder.get("scheduled_for"),
            "minutes_before": reminder.get("minutes_before"),
            "task_recurrence_rule": task.get("recurrence_rule"),
            "task_recurrence_start": task.get("scheduled_start"),
        }
        queued_row = enqueue_notification(
            channel=outbox_channel,
            template="calendar_reminder",
            tenant_id=int(reminder["tenant_id"]),
            user_id=int(user_id) if user_id is not None else None,
            recipient_reference=f"user:{user_id}" if configured_channel == "email" and user_id else None,
            deduplication_key=f"calendar-task-reminder:{reminder['id']}:{reminder.get('scheduled_for')}",
            payload=payload,
            client=database_client,
        )
        if queued_row:
            database_client.table("calendar_task_reminders").update(
                {"delivery_status": "queued", "failure_code": None}
            ).eq("id", reminder.get("id")).eq("delivery_status", "scheduled").execute()
            queued += 1
    return queued


def mark_calendar_reminder_delivery(
    outbox_row: dict[str, Any], *, succeeded: bool, failure_code: str | None = None, client=None
) -> None:
    if str(outbox_row.get("template") or "") != "calendar_reminder":
        return
    reminder_id = (outbox_row.get("payload") or {}).get("reminder_id")
    if not reminder_id:
        return
    database_client = client or service_supabase
    values = {
        "delivery_status": "delivered" if succeeded else "failed",
        "delivered_at": datetime.now(timezone.utc).isoformat() if succeeded else None,
        "failure_code": None if succeeded else str(failure_code or "delivery_failed")[:200],
    }
    payload = outbox_row.get("payload") or {}
    if payload.get("reminder_source") == "task":
        if succeeded:
            next_scheduled_for = next_task_reminder_time(payload)
            if next_scheduled_for:
                values.update({
                    "delivery_status": "scheduled",
                    "scheduled_for": next_scheduled_for,
                })
        query = database_client.table("calendar_task_reminders").update(values).eq("id", reminder_id)
        if payload.get("scheduled_for"):
            query = query.eq("scheduled_for", payload["scheduled_for"])
        query.execute()
        return
    database_client.table("calendar_event_reminders").update(values).eq("id", reminder_id).execute()
