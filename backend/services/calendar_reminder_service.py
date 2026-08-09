from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from dateutil.rrule import rrulestr

from database import service_supabase
from services.notification_outbox_service import enqueue_notification


logger = logging.getLogger(__name__)


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


def _enqueue_reminder_notification(
    *,
    reminder_source: str,
    reminder: dict[str, Any],
    channel: str,
    user_id: int,
    recipient_reference: str | None,
    deduplication_key: str,
    payload: dict[str, Any],
    client,
) -> dict[str, Any] | None:
    rpc = getattr(client, "rpc", None)
    if callable(rpc):
        response = rpc(
            "enqueue_calendar_reminder_notification",
            {
                "p_reminder_source": reminder_source,
                "p_reminder_id": reminder["id"],
                "p_scheduled_for": reminder["scheduled_for"],
                "p_tenant_id": int(reminder["tenant_id"]),
                "p_user_id": int(user_id),
                "p_channel": channel,
                "p_recipient_reference": recipient_reference,
                "p_deduplication_key": deduplication_key,
                "p_payload": payload,
            },
        ).execute()
        rows = _rows(response)
        return rows[0] if rows else None

    # Lightweight in-memory unit-test clients do not implement RPC. Production
    # enqueue and scheduled->queued transition share the database transaction.
    queued = enqueue_notification(
        channel=channel,
        template="calendar_reminder",
        tenant_id=int(reminder["tenant_id"]),
        user_id=int(user_id),
        recipient_reference=recipient_reference,
        deduplication_key=deduplication_key,
        payload=payload,
        client=client,
    )
    if queued:
        table = (
            "calendar_task_reminders"
            if reminder_source == "task"
            else "calendar_event_reminders"
        )
        client.table(table).update(
            {"delivery_status": "queued", "failure_code": None}
        ).eq("id", reminder.get("id")).eq("delivery_status", "scheduled").execute()
    return queued


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
        active_creator = []
        if user_id is not None:
            active_creator = _rows(
                database_client.table("tenant_memberships")
                .select("user_id")
                .eq("tenant_id", reminder.get("tenant_id"))
                .eq("user_id", user_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
        if not active_creator:
            database_client.table("calendar_event_reminders").update(
                {"delivery_status": "cancelled", "failure_code": "owner_inactive"}
            ).eq("id", reminder.get("id")).execute()
            logger.warning(
                "calendar_event_reminder.cancelled",
                extra={"tenant_id": reminder.get("tenant_id"), "user_id": user_id, "error_code": "owner_inactive"},
            )
            continue
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
        queued_row = _enqueue_reminder_notification(
            reminder_source="event",
            reminder=reminder,
            channel=outbox_channel,
            user_id=int(user_id),
            recipient_reference=f"user:{user_id}" if configured_channel == "email" and user_id else None,
            deduplication_key=f"calendar-reminder:{reminder['id']}",
            payload=payload,
            client=database_client,
        )
        if queued_row:
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
        active_owner = []
        if user_id is not None:
            active_owner = _rows(
                database_client.table("tenant_memberships")
                .select("user_id")
                .eq("tenant_id", reminder.get("tenant_id"))
                .eq("user_id", user_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
        if not active_owner:
            database_client.table("calendar_task_reminders").update(
                {"delivery_status": "cancelled", "failure_code": "owner_inactive"}
            ).eq("id", reminder.get("id")).execute()
            continue
        try:
            occurrence_start = _datetime(reminder.get("scheduled_for")) + timedelta(
                minutes=int(reminder.get("minutes_before") or 0)
            )
        except (TypeError, ValueError, OverflowError):
            database_client.table("calendar_task_reminders").update(
                {"delivery_status": "failed", "failure_code": "reminder_time_invalid"}
            ).eq("id", reminder.get("id")).execute()
            logger.warning(
                "calendar_task_reminder.invalid",
                extra={"error_code": "reminder_time_invalid"},
            )
            continue
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
        queued_row = _enqueue_reminder_notification(
            reminder_source="task",
            reminder=reminder,
            channel=outbox_channel,
            user_id=int(user_id),
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


def finalize_calendar_reminder_deliveries(outbox_id: str, *, client=None) -> bool:
    """Finalize a reminder only after every independent delivery is terminal."""
    database_client = client or service_supabase
    deliveries = _rows(
        database_client.table("notification_deliveries")
        .select("status,last_error_code")
        .eq("outbox_id", outbox_id)
        .execute()
    )
    if not deliveries or any(
        row.get("status") in {"pending", "processing"} for row in deliveries
    ):
        return False
    outbox_rows = _rows(
        database_client.table("notification_outbox")
        .select("*")
        .eq("id", outbox_id)
        .limit(1)
        .execute()
    )
    if not outbox_rows:
        return False
    succeeded = any(row.get("status") == "sent" for row in deliveries)
    failure_code = next(
        (
            str(row.get("last_error_code"))
            for row in deliveries
            if row.get("last_error_code")
        ),
        "delivery_failed",
    )
    mark_calendar_reminder_delivery(
        outbox_rows[0],
        succeeded=succeeded,
        failure_code=None if succeeded else failure_code,
        client=database_client,
    )
    return True
