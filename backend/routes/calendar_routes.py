from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import time
from typing import Annotated, Any, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from database import service_supabase
from services.tenant_service import require_active_tenant_member as _require_active_tenant_member
from services.entitlement_service import require_entitlement
from services.audit_service import record_audit_event
from services.calendar_authorization_service import (
    availability_event,
    list_accessible_calendars,
    public_calendar_metadata,
    require_calendar_access,
)
from services.calendar_sync_service import (
    CalendarSyncError,
    authorization_url,
    consume_oauth_state,
    credentials_allow_direction,
    decode_oauth_state,
    decrypt_credentials,
    disconnect_connection,
    encrypt_credentials,
    exchange_authorization_code,
    frontend_calendar_url,
    sync_connection,
)
from services.calendar_task_sync_queue_service import enqueue_task_sync
from services.calendar_connection_sync_queue_service import enqueue_connection_sync
from services.calendar_workspace_cache_service import (
    calendar_workspace_cache_key,
    get_or_create_calendar_workspace,
    invalidate_calendar_workspace_cache,
)


router = APIRouter(prefix="/calendar", tags=["Calendar"])
logger = logging.getLogger(__name__)
MAX_RANGE_DAYS = 370
MAX_EXPANDED_OCCURRENCES = 2000
MAX_DEPENDENCY_EDGES = 5000
PENDING_CONNECTION_TTL = timedelta(minutes=15)
MAX_PENDING_CONNECTION_CLEANUP = 10
CALENDAR_SCHEMA_TABLES = (
    "calendars",
    "calendar_memberships",
    "calendar_events",
    "calendar_tasks",
    "calendar_task_reminders",
    "calendar_sync_connections",
    "calendar_invitation_reviews",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=400, detail="Calendar range must include a timezone")
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end <= start:
        raise HTTPException(status_code=400, detail="Calendar range end must be after start")
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise HTTPException(status_code=400, detail=f"Calendar range cannot exceed {MAX_RANGE_DAYS} days")
    return start, end


def validate_timezone(value: str) -> str:
    candidate = str(value or "UTC").strip() or "UTC"
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(status_code=400, detail="Unknown IANA timezone") from error
    return candidate


def is_calendar_schema_missing_error(error: Exception) -> bool:
    raw = str(error).lower()
    missing_schema = (
        "pgrst205" in raw
        or "could not find the table" in raw
        or "schema cache" in raw
    )
    return missing_schema and any(table_name in raw for table_name in CALENDAR_SCHEMA_TABLES)


def calendar_feature_enabled() -> bool:
    return os.getenv("CALENDAR_FEATURE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def require_calendar_feature() -> None:
    if not calendar_feature_enabled():
        raise HTTPException(
            status_code=503,
            detail={"code": "calendar_feature_disabled", "message": "Calendar features are disabled."},
        )


def require_active_tenant_member(request: Request, response: Response):
    context = _require_active_tenant_member(request, response)
    require_entitlement(
        context.tenant_id,
        "internal_calendar",
        message="Business Plus is required to use the internal calendar.",
    )
    return context


def ensure_default_calendar(context) -> dict[str, Any]:
    response = (
        service_supabase.table("calendars")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .eq("owner_user_id", context.user_id)
        .eq("is_default", True)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if rows:
        return rows[0]
    timezone_name = validate_timezone(str(context.user.get("timezone") or "UTC"))
    created = (
        service_supabase.table("calendars")
        .insert({
            "tenant_id": context.tenant_id,
            "owner_user_id": context.user_id,
            "name": "My calendar",
            "timezone": timezone_name,
            "visibility": "private",
            "is_default": True,
        })
        .execute()
    )
    rows = getattr(created, "data", None) or []
    if not rows:
        raise HTTPException(status_code=500, detail="Default calendar could not be created")
    service_supabase.table("calendar_memberships").insert({
        "calendar_id": rows[0]["id"],
        "tenant_id": context.tenant_id,
        "user_id": context.user_id,
        "role": "owner",
    }).execute()
    return rows[0]


def tenant_calendar(calendar_id: str, tenant_id: int) -> dict[str, Any]:
    response = (
        service_supabase.table("calendars")
        .select("*")
        .eq("id", calendar_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Calendar not found")
    return rows[0]


def tenant_event(event_id: str, tenant_id: int) -> dict[str, Any]:
    response = (
        service_supabase.table("calendar_events")
        .select("*")
        .eq("id", event_id)
        .eq("tenant_id", tenant_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found")
    return rows[0]


def tenant_task(task_id: str, tenant_id: int) -> dict[str, Any]:
    rows = getattr(
        service_supabase.table("calendar_tasks")
        .select("*")
        .eq("id", task_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found")
    return rows[0]


def require_calendar_creator(context) -> None:
    if str(context.role or "").lower() not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=403, detail="Calendar creation access required")


def validate_active_task_owner(context, owner_user_id: int | None) -> int:
    selected = int(owner_user_id if owner_user_id is not None else context.user_id)
    memberships = getattr(
        service_supabase.table("tenant_memberships")
        .select("user_id")
        .eq("tenant_id", context.tenant_id)
        .eq("user_id", selected)
        .eq("status", "active")
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    users = getattr(
        service_supabase.table("users")
        .select("id,account_status")
        .eq("id", selected)
        .eq("account_status", "active")
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    if not memberships or not users:
        raise HTTPException(status_code=400, detail="Task owner must be an active organization member")
    return selected


def validate_project_reference(context, project_id: UUID | str | None) -> str | None:
    if project_id is None:
        return None
    project_value = str(project_id)
    rows = getattr(
        service_supabase.table("builder_projects")
        .select("id,status")
        .eq("id", project_value)
        .eq("tenant_id", context.tenant_id)
        .neq("status", "archived")
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_value


def require_task_access(context, task: dict[str, Any], capability: str = "manage_tasks") -> None:
    calendar_id = task.get("calendar_id")
    if calendar_id:
        require_calendar_access(context, str(calendar_id), capability)
        return
    if str(context.role or "").lower() in {"owner", "admin"}:
        return
    if int(task.get("owner_user_id") or -1) != int(context.user_id):
        raise HTTPException(status_code=404, detail="Task not found")


def record_calendar_audit(context, request: Request, action: str, target_type: str, target_id: Any, metadata: dict | None = None) -> None:
    invalidate_calendar_workspace_cache(context.tenant_id)
    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )


def sanitized_conflict(row: dict[str, Any]) -> dict[str, Any]:
    local = row.get("local_data") if isinstance(row.get("local_data"), dict) else {}
    remote = row.get("remote_data") if isinstance(row.get("remote_data"), dict) else {}
    return {
        "id": row.get("id"),
        "connection_id": row.get("connection_id"),
        "event_id": row.get("event_id"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "local": {
            "title": local.get("title"),
            "starts_at": local.get("starts_at"),
            "ends_at": local.get("ends_at"),
            "location": local.get("location"),
            "version": local.get("version"),
        },
        "remote": {
            "title": remote.get("summary") or remote.get("subject"),
            "starts_at": remote.get("start"),
            "ends_at": remote.get("end"),
            "location": remote.get("location"),
        },
    }


def sanitized_invitation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "event_id": row.get("event_id"),
        "sender_email": row.get("sender_email"),
        "trust_level": row.get("trust_level"),
        "reasons": list(row.get("reasons") or [])[:20],
        "disposition": row.get("disposition"),
        "created_at": row.get("created_at"),
    }


def workspace_task_rows(context, detail_ids: list[str]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if detail_ids:
        tasks = getattr(
            service_supabase.table("calendar_tasks").select("*")
            .eq("tenant_id", context.tenant_id).in_("calendar_id", detail_ids)
            .neq("status", "cancelled").is_("archived_at", "null")
            .order("due_at").limit(1000).execute(),
            "data", None,
        ) or []
    unassigned_query = (
        service_supabase.table("calendar_tasks").select("*")
        .eq("tenant_id", context.tenant_id)
        .is_("calendar_id", "null")
        .neq("status", "cancelled")
        .is_("archived_at", "null")
    )
    if str(context.role or "").lower() not in {"owner", "admin"}:
        unassigned_query = unassigned_query.eq("owner_user_id", context.user_id)
    unassigned_tasks = getattr(
        unassigned_query.order("due_at").limit(1000).execute(), "data", None
    ) or []
    return list({
        str(task.get("id")): task
        for task in [*tasks, *unassigned_tasks]
        if task.get("id")
    }.values())


def workspace_linked_task_event_ids(context, detail_ids: list[str]) -> set[str]:
    rows: list[dict[str, Any]] = []
    if detail_ids:
        rows = getattr(
            service_supabase.table("calendar_tasks").select("sync_event_id")
            .eq("tenant_id", context.tenant_id).in_("calendar_id", detail_ids)
            .is_("archived_at", "null")
            .limit(1000).execute(),
            "data", None,
        ) or []
    return {
        str(row.get("sync_event_id"))
        for row in rows
        if row.get("sync_event_id")
    }


def safe_task_payload(task: dict[str, Any]) -> dict[str, Any]:
    payload = dict(task)
    payload["is_synchronized"] = bool(payload.pop("sync_event_id", None))
    payload.pop("sync_error_code", None)
    return payload


def sync_task_reminder(
    task: dict[str, Any], minutes_before: int | None, *, schedule_changed: bool = False
) -> None:
    task_id = str(task["id"])
    tenant_id = int(task["tenant_id"])
    query = (
        service_supabase.table("calendar_task_reminders")
        .select("*")
        .eq("task_id", task_id)
        .eq("tenant_id", tenant_id)
        .eq("channel", "in_app")
        .limit(1)
        .execute()
    )
    existing_rows = getattr(query, "data", None) or []
    existing = existing_rows[0] if existing_rows else None
    if minutes_before is None:
        if existing:
            service_supabase.table("calendar_task_reminders").delete().eq("id", existing["id"]).execute()
        return

    scheduled_start = task.get("scheduled_start")
    scheduled_start_dt = (
        datetime.fromisoformat(str(scheduled_start).replace("Z", "+00:00"))
        if scheduled_start
        else None
    )
    scheduled_for = iso(scheduled_start_dt - timedelta(minutes=minutes_before)) if scheduled_start_dt else None
    inactive = task.get("status") in {"done", "cancelled"} or bool(task.get("archived_at"))
    reminder_changed = not existing or int(existing.get("minutes_before") or 0) != minutes_before
    values = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "channel": "in_app",
        "minutes_before": minutes_before,
        "scheduled_for": scheduled_for,
    }
    if inactive:
        values.update({"delivery_status": "cancelled", "failure_code": None})
    elif schedule_changed or reminder_changed or (existing and existing.get("delivery_status") in {"cancelled", "failed"}):
        values.update({"delivery_status": "scheduled", "delivered_at": None, "failure_code": None})

    if existing:
        service_supabase.table("calendar_task_reminders").update(values).eq("id", existing["id"]).execute()
    else:
        values.setdefault("delivery_status", "scheduled")
        service_supabase.table("calendar_task_reminders").insert(values).execute()


def event_payload(row: dict[str, Any], *, occurrence_start: datetime | None = None) -> dict[str, Any]:
    payload = dict(row)
    payload.pop("source_id", None)
    payload.pop("external_etag", None)
    payload["read_only"] = False
    source_type = str(row.get("source_type") or "madar")
    payload["source_label"] = "Madar" if source_type == "madar" else source_type.title()
    if occurrence_start is not None:
        original_start = datetime.fromisoformat(str(row["starts_at"]).replace("Z", "+00:00"))
        original_end = datetime.fromisoformat(str(row["ends_at"]).replace("Z", "+00:00"))
        payload["series_id"] = row["id"]
        payload["occurrence_start"] = iso(occurrence_start)
        payload["starts_at"] = iso(occurrence_start)
        payload["ends_at"] = iso(occurrence_start + (original_end - original_start))
        payload["id"] = f"{row['id']}::{iso(occurrence_start)}"
    return payload


def expand_events(rows: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for row in rows:
        starts_at = datetime.fromisoformat(str(row["starts_at"]).replace("Z", "+00:00"))
        ends_at = datetime.fromisoformat(str(row["ends_at"]).replace("Z", "+00:00"))
        rule_text = str(row.get("recurrence_rule") or "").strip()
        if not rule_text:
            if starts_at < end and ends_at > start:
                expanded.append(event_payload(row))
            continue
        exclusions = {str(item) for item in (row.get("recurrence_exclusions") or [])}
        try:
            rule = rrulestr(rule_text, dtstart=starts_at)
            occurrences = rule.between(start - (ends_at - starts_at), end, inc=True)
        except (TypeError, ValueError, OverflowError):
            continue
        for occurrence in occurrences[:MAX_EXPANDED_OCCURRENCES]:
            occurrence = occurrence.astimezone(timezone.utc)
            if iso(occurrence) not in exclusions and occurrence < end:
                expanded.append(event_payload(row, occurrence_start=occurrence))
    return sorted(expanded, key=lambda item: item.get("starts_at") or "")[:MAX_EXPANDED_OCCURRENCES]


def reservation_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"reservation::{row['id']}",
        "source_id": row["id"],
        "source_type": "reservation",
        "source_label": "Reservation",
        "calendar_id": "reservations",
        "title": row.get("reservation_title") or row.get("customer_name") or "Reservation",
        "description": "",
        "location": row.get("site_subdomain") or "",
        "starts_at": row.get("starts_at"),
        "ends_at": row.get("ends_at") or row.get("starts_at"),
        "timezone": row.get("timezone") or "UTC",
        "status": "cancelled" if row.get("status") in {"cancelled", "rejected"} else "confirmed",
        "reservation_status": row.get("status") or "new",
        "customer_name": row.get("customer_name"),
        "customer_email": row.get("customer_email"),
        "project_id": row.get("project_id"),
        "read_only": True,
        "version": 1,
    }


def write_change(context, event_id: str, action: str, scope: str, before, after) -> None:
    service_supabase.table("calendar_event_changes").insert({
        "tenant_id": context.tenant_id,
        "event_id": event_id,
        "changed_by": context.user_id,
        "action": action,
        "scope": scope,
        "before_data": before,
        "after_data": after,
    }).execute()


def event_conflicts(tenant_id: int, calendar_id: str, start: datetime, end: datetime, exclude_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        service_supabase.table("calendar_events")
        .select("id,title,starts_at,ends_at,version")
        .eq("tenant_id", tenant_id)
        .eq("calendar_id", calendar_id)
        .eq("transparency", "busy")
        .neq("status", "cancelled")
        .is_("deleted_at", "null")
        .lt("starts_at", iso(end))
        .gt("ends_at", iso(start))
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    return getattr(query.limit(20).execute(), "data", None) or []


def truncated_recurrence_rule(rule: str, until: datetime) -> str:
    parts = [part for part in str(rule or "").split(";") if part and not part.upper().startswith(("UNTIL=", "COUNT="))]
    parts.append("UNTIL=" + until.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    return ";".join(parts)


def exclude_occurrence(context, event: dict[str, Any], occurrence_start: datetime) -> dict[str, Any]:
    occurrence = iso(occurrence_start)
    exclusions = list(event.get("recurrence_exclusions") or [])
    if occurrence not in exclusions:
        exclusions.append(occurrence)
    rows = getattr(service_supabase.table("calendar_events").update({
        "recurrence_exclusions": exclusions, "version": int(event.get("version") or 1) + 1,
    }).eq("id", event["id"]).eq("tenant_id", context.tenant_id).execute(), "data", None) or []
    return rows[0] if rows else event


class CalendarCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#5b7cfa", pattern=r"^#[0-9a-fA-F]{6}$")
    timezone: str = "UTC"
    visibility: Literal["private", "team", "organization", "public"] = "private"
    is_default: bool = False

    @field_validator("timezone")
    @classmethod
    def timezone_is_valid(cls, value: str) -> str:
        return validate_timezone(value)


class AttendeeWrite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(default="", max_length=160)


class ReminderWrite(BaseModel):
    channel: Literal["in_app", "email", "web_push"] = "in_app"
    minutes_before: int = Field(default=15, ge=0, le=525600)


class EventWrite(BaseModel):
    calendar_id: UUID
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=20000)
    location: str = Field(default="", max_length=500)
    starts_at: datetime
    ends_at: datetime
    timezone: str = "UTC"
    all_day: bool = False
    status: Literal["tentative", "confirmed", "cancelled"] = "confirmed"
    visibility: Literal["calendar_default", "private", "team", "organization", "public"] = "calendar_default"
    transparency: Literal["busy", "free"] = "busy"
    recurrence_rule: Optional[str] = Field(default=None, max_length=1000)
    project_id: Optional[UUID] = None
    attendees: list[AttendeeWrite] = Field(default_factory=list, max_length=200)
    reminders: list[ReminderWrite] = Field(default_factory=list, max_length=20)
    expected_version: Optional[int] = Field(default=None, ge=1)
    allow_conflicts: bool = False

    @field_validator("timezone")
    @classmethod
    def timezone_is_valid(cls, value: str) -> str:
        return validate_timezone(value)


class TaskWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=20000)
    calendar_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    owner_user_id: Optional[int] = None
    status: Literal["todo", "in_progress", "blocked", "done", "cancelled"] = "todo"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    estimate_minutes: Optional[int] = Field(default=None, ge=1, le=525600)
    due_at: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    reminder_minutes_before: Optional[int] = Field(default=10, ge=0, le=525600)
    recurrence_rule: Optional[str] = Field(default=None, max_length=100)
    milestone: bool = False

    @field_validator("recurrence_rule")
    @classmethod
    def task_recurrence_is_supported(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper()
        if normalized not in {"FREQ=DAILY", "FREQ=WEEKLY", "FREQ=MONTHLY"}:
            raise ValueError("Unsupported task recurrence")
        return normalized

    @field_validator("due_at", "scheduled_start", "scheduled_end")
    @classmethod
    def task_datetime_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Task date and time values must include a timezone")
        return value

    @model_validator(mode="after")
    def task_schedule_is_ordered(self) -> "TaskWrite":
        if self.scheduled_end is not None and self.scheduled_start is None:
            raise ValueError("Scheduled end requires a scheduled start")
        if (
            self.scheduled_start is not None
            and self.scheduled_end is not None
            and self.scheduled_end <= self.scheduled_start
        ):
            raise ValueError("Scheduled end must be after scheduled start")
        return self


class CalendarMemberWrite(BaseModel):
    user_id: int
    role: Literal["availability", "viewer", "editor", "owner"] = "viewer"


class TaskDependencyWrite(BaseModel):
    depends_on_task_id: UUID


class TaskSyncWrite(BaseModel):
    connection_id: UUID


class ConnectionWrite(BaseModel):
    provider: Literal["google", "microsoft", "ics"]
    account_label: str = Field(default="", max_length=160)
    direction: Literal["read", "two_way"] = "read"


class IcsImportWrite(BaseModel):
    calendar_id: UUID
    content: str = Field(min_length=20, max_length=2 * 1024 * 1024)


def tenant_connection(connection_id: str, tenant_id: int, user_id: int | None = None) -> dict[str, Any]:
    query = service_supabase.table("calendar_sync_connections").select("*").eq("id", connection_id).eq("tenant_id", tenant_id)
    if user_id is not None:
        query = query.eq("user_id", user_id)
    rows = getattr(query.limit(1).execute(), "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Calendar connection not found")
    return rows[0]


def safe_connection_payload(connection: dict[str, Any]) -> dict[str, Any]:
    return {
        key: connection.get(key)
        for key in (
            "id",
            "local_calendar_id",
            "provider",
            "account_label",
            "direction",
            "status",
            "last_success_at",
            "last_attempt_at",
            "last_error_code",
            "pending_changes",
            "failed_changes",
            "inbound_sync_enabled",
            "inbound_sync_status",
            "last_inbound_success_at",
            "inbound_sync_error_code",
            "created_at",
        )
    } | {
        "provider_calendar_label": (
            "Primary Google calendar"
            if connection.get("provider") == "google"
            else "Primary provider calendar"
        )
    }


def _connection_created_at(connection: dict[str, Any]) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(connection.get("created_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def reusable_pending_connection(context, payload: ConnectionWrite, request: Request) -> dict[str, Any] | None:
    if payload.provider not in {"google", "microsoft"}:
        return None
    newest = getattr(
        service_supabase.table("calendar_sync_connections")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .eq("user_id", context.user_id)
        .eq("provider", payload.provider)
        .eq("direction", payload.direction)
        .eq("status", "setup_required")
        .is_("encrypted_credentials", "null")
        .order("created_at", desc=True)
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    cutoff = utc_now() - PENDING_CONNECTION_TTL
    created_at = _connection_created_at(newest[0]) if newest else None
    reusable = newest[0] if created_at is not None and created_at >= cutoff else None
    stale = getattr(
        service_supabase.table("calendar_sync_connections")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .eq("user_id", context.user_id)
        .eq("provider", payload.provider)
        .eq("direction", payload.direction)
        .eq("status", "setup_required")
        .is_("encrypted_credentials", "null")
        .lt("created_at", iso(cutoff))
        .order("created_at")
        .limit(MAX_PENDING_CONNECTION_CLEANUP)
        .execute(),
        "data",
        None,
    ) or []
    for connection in stale:
        deleted = getattr(
            service_supabase.table("calendar_sync_connections")
            .delete()
            .eq("id", connection.get("id"))
            .eq("tenant_id", context.tenant_id)
            .eq("user_id", context.user_id)
            .eq("status", "setup_required")
            .is_("encrypted_credentials", "null")
            .execute(),
            "data",
            None,
        ) or []
        if deleted:
            calendar_removed = remove_empty_connection_calendar(connection)
            record_calendar_audit(
                context,
                request,
                "calendar.connection_expired",
                "calendar_sync_connection",
                connection.get("id"),
                {
                    "provider": payload.provider,
                    "empty_calendar_removed": calendar_removed,
                },
            )
    return reusable


def mark_pending_connection_failed(connection: dict[str, Any], error_code: str) -> None:
    if (
        str(connection.get("status") or "") != "setup_required"
        or connection.get("encrypted_credentials")
    ):
        return
    service_supabase.table("calendar_sync_connections").update({
        "status": "disconnected",
        "last_attempt_at": iso(utc_now()),
        "last_error_code": str(error_code or "oauth_failed")[:80],
    }).eq("id", connection.get("id")).eq("tenant_id", connection.get("tenant_id")).eq(
        "status", "setup_required"
    ).is_("encrypted_credentials", "null").execute()


def remove_empty_connection_calendar(connection: dict[str, Any]) -> bool:
    calendar_id = connection.get("local_calendar_id")
    if not calendar_id:
        return False
    calendars = getattr(
        service_supabase.table("calendars")
        .select("id")
        .eq("id", calendar_id)
        .eq("tenant_id", connection.get("tenant_id"))
        .eq("owner_user_id", connection.get("user_id"))
        .eq("is_default", False)
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    if not calendars:
        return False
    for table_name, field_name in (
        ("calendar_events", "calendar_id"),
        ("calendar_tasks", "calendar_id"),
        ("calendar_sync_connections", "local_calendar_id"),
    ):
        rows = getattr(
            service_supabase.table(table_name)
            .select("id")
            .eq("tenant_id", connection.get("tenant_id"))
            .eq(field_name, calendar_id)
            .limit(1)
            .execute(),
            "data",
            None,
        ) or []
        if rows:
            return False
    deleted = getattr(
        service_supabase.table("calendars")
        .delete()
        .eq("id", calendar_id)
        .eq("tenant_id", connection.get("tenant_id"))
        .eq("owner_user_id", connection.get("user_id"))
        .eq("is_default", False)
        .execute(),
        "data",
        None,
    ) or []
    return bool(deleted)


def sync_http_error(error: CalendarSyncError) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": error.code, "message": str(error)})


def task_sync_connection(context, task: dict[str, Any], connection_id: str) -> dict[str, Any]:
    existing_connection_id = task.get("sync_connection_id")
    if existing_connection_id and str(existing_connection_id) != str(connection_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "task_sync_connection_change_requires_unlink",
                "message": "Keep the current Google link or switch this task to Madar only first.",
            },
        )
    connection = tenant_connection(connection_id, context.tenant_id)
    require_calendar_access(
        context, str(connection.get("local_calendar_id")), "trigger_sync"
    )
    if str(connection.get("provider") or "") != "google":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "task_provider_unsupported",
                "message": "Task synchronization currently supports Google Calendar.",
            },
        )
    if str(connection.get("status") or "") not in {"connected", "degraded"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_connection_not_connected",
                "message": "Connect this calendar account before synchronizing tasks.",
            },
        )
    if connection.get("direction") != "two_way":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_write_access_required",
                "message": "Enable Google write access before synchronizing tasks.",
            },
        )
    if not task.get("scheduled_start") and not task.get("due_at"):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "task_schedule_required",
                "message": "Schedule this task before synchronizing it.",
            },
        )
    return connection


def queue_task_to_provider(
    context, task: dict[str, Any], connection: dict[str, Any]
) -> dict[str, Any]:
    start_value = task.get("scheduled_start") or task.get("due_at")
    start_at = datetime.fromisoformat(str(start_value).replace("Z", "+00:00"))
    end_value = task.get("scheduled_end")
    end_at = (
        datetime.fromisoformat(str(end_value).replace("Z", "+00:00"))
        if end_value
        else start_at + timedelta(minutes=int(task.get("estimate_minutes") or 60))
    )
    event_values = {
        "tenant_id": context.tenant_id,
        "calendar_id": connection["local_calendar_id"],
        "created_by": context.user_id,
        "title": task.get("title") or "Task",
        "description": task.get("description") or "",
        "location": "",
        "starts_at": iso(start_at),
        "ends_at": iso(end_at),
        "timezone": str(context.user.get("timezone") or "UTC"),
        "all_day": False,
        "status": "confirmed",
        "visibility": "private",
        "transparency": "busy",
        "recurrence_rule": task.get("recurrence_rule"),
        "project_id": task.get("project_id"),
    }
    linked_event = None
    if task.get("sync_event_id"):
        rows = getattr(
            service_supabase.table("calendar_events")
            .select("*")
            .eq("id", task["sync_event_id"])
            .eq("tenant_id", context.tenant_id)
            .eq("calendar_id", connection["local_calendar_id"])
            .is_("deleted_at", "null")
            .limit(1)
            .execute(),
            "data",
            None,
        ) or []
        linked_event = rows[0] if rows else None
    if linked_event:
        event_values["version"] = int(linked_event.get("version") or 1) + 1
        event_rows = getattr(
            service_supabase.table("calendar_events")
            .update(event_values)
            .eq("id", linked_event["id"])
            .eq("tenant_id", context.tenant_id)
            .execute(),
            "data",
            None,
        ) or []
    else:
        event_values.update({"source_type": "madar", "version": 1})
        event_rows = getattr(
            service_supabase.table("calendar_events").insert(event_values).execute(),
            "data",
            None,
        ) or []
    if not event_rows:
        raise HTTPException(status_code=500, detail="Task synchronization could not be prepared")
    event = event_rows[0]
    updated = getattr(service_supabase.table("calendar_tasks").update({
        "sync_connection_id": connection["id"],
        "sync_event_id": event["id"],
        "sync_status": "pending",
        "sync_error_code": None,
    }).eq("id", task["id"]).eq("tenant_id", context.tenant_id).execute(),
        "data",
        None,
    ) or []
    queued_task = updated[0] if updated else {
        **task,
        "sync_connection_id": connection["id"],
        "sync_event_id": event["id"],
        "sync_status": "pending",
        "sync_error_code": None,
    }
    operation = "update" if linked_event else "create"
    enqueue_task_sync(
        tenant_id=context.tenant_id,
        task_id=str(task["id"]),
        connection_id=str(connection["id"]),
        operation=operation,
        task_version=int(queued_task.get("version") or task.get("version") or 1),
    )
    return queued_task


def _calendar_workspace_payload(context, start: datetime, end: datetime) -> dict[str, Any]:
    ensure_default_calendar(context)
    accesses = list_accessible_calendars(context)
    access_by_id = {str(access.calendar.get("id")): access for access in accesses}
    full_detail_ids = [calendar_id for calendar_id, access in access_by_id.items() if access.role in {"editor", "owner"}]
    viewer_ids = [calendar_id for calendar_id, access in access_by_id.items() if access.role == "viewer"]
    detail_ids = [*full_detail_ids, *viewer_ids]
    availability_ids = [calendar_id for calendar_id, access in access_by_id.items() if access.role == "availability"]
    review_ids = {calendar_id for calendar_id, access in access_by_id.items() if access.allows("review_invitations")}
    sync_state_ids = [calendar_id for calendar_id, access in access_by_id.items() if access.allows("view_sync_state")]

    def event_rows(calendar_ids: list[str], fields: str, visibility_mode: str = "all") -> list[dict[str, Any]]:
        if not calendar_ids:
            return []
        normal_query = service_supabase.table("calendar_events").select(fields).eq("tenant_id", context.tenant_id).in_("calendar_id", calendar_ids).is_("deleted_at", "null")
        recurring_query = service_supabase.table("calendar_events").select(fields).eq("tenant_id", context.tenant_id).in_("calendar_id", calendar_ids).is_("deleted_at", "null")
        if visibility_mode == "exclude_private":
            normal_query = normal_query.neq("visibility", "private")
            recurring_query = recurring_query.neq("visibility", "private")
        elif visibility_mode == "private_only":
            normal_query = normal_query.eq("visibility", "private")
            recurring_query = recurring_query.eq("visibility", "private")
        normal = getattr(
            normal_query.lt("starts_at", iso(end)).gt("ends_at", iso(start)).order("starts_at").limit(2000).execute(),
            "data", None,
        ) or []
        recurring = getattr(
            recurring_query.not_.is_("recurrence_rule", "null").lt("starts_at", iso(end)).order("starts_at", desc=True).limit(500).execute(),
            "data", None,
        ) or []
        return list({str(row.get("id")): row for row in [*normal, *recurring]}.values())

    detail_event_rows = [
        *event_rows(full_detail_ids, "*"),
        *event_rows(viewer_ids, "*", "exclude_private"),
    ]
    availability_rows = event_rows(
        availability_ids,
        "id,calendar_id,starts_at,ends_at,transparency,recurrence_rule,recurrence_exclusions",
    )
    availability_rows.extend(event_rows(
        viewer_ids,
        "id,calendar_id,starts_at,ends_at,transparency,recurrence_rule,recurrence_exclusions",
        "private_only",
    ))
    events = expand_events(detail_event_rows, start, end)
    events.extend(availability_event(row) for row in expand_events(availability_rows, start, end))

    if str(context.role or "").lower() in {"owner", "admin", "member"}:
        reservations = getattr(
            service_supabase.table("builder_reservations").select("*")
            .eq("tenant_id", context.tenant_id).lt("starts_at", iso(end))
            .gt("ends_at", iso(start)).limit(1000).execute(), "data", None,
        ) or []
        events.extend(reservation_payload(row) for row in reservations if row.get("starts_at"))

    tasks = workspace_task_rows(context, detail_ids)
    linked_task_event_ids = workspace_linked_task_event_ids(context, detail_ids)
    if linked_task_event_ids:
        events = [
            event
            for event in events
            if str(event.get("id") or "").split("::", 1)[0]
            not in linked_task_event_ids
            and str(event.get("series_id") or "") not in linked_task_event_ids
        ]
    task_ids = [str(row.get("id")) for row in tasks if row.get("id")]
    task_reminder_rows = []
    if task_ids:
        task_reminder_rows = getattr(
            service_supabase.table("calendar_task_reminders")
            .select("task_id,minutes_before,delivery_status,scheduled_for")
            .eq("tenant_id", context.tenant_id).in_("task_id", task_ids)
            .eq("channel", "in_app").limit(1000).execute(), "data", None,
        ) or []
    task_reminders = {str(row.get("task_id")): row for row in task_reminder_rows}
    for task in tasks:
        reminder = task_reminders.get(str(task.get("id")))
        task["reminder_minutes_before"] = reminder.get("minutes_before") if reminder else 10
    safe_tasks = [safe_task_payload(task) for task in tasks]

    connections = []
    if sync_state_ids:
        connections = getattr(
            service_supabase.table("calendar_sync_connections")
            .select("id,local_calendar_id,provider,account_label,direction,status,last_success_at,last_attempt_at,last_error_code,pending_changes,failed_changes,inbound_sync_enabled,inbound_sync_status,last_inbound_success_at,inbound_sync_error_code,created_at")
            .eq("tenant_id", context.tenant_id)
            .in_("local_calendar_id", sync_state_ids).limit(100).execute(), "data", None,
        ) or []

    review_event_ids = {
        str(row.get("id")) for row in detail_event_rows
        if str(row.get("calendar_id")) in review_ids and row.get("id")
    }
    invitation_reviews = []
    if review_event_ids:
        review_rows = getattr(
            service_supabase.table("calendar_invitation_reviews")
            .select("id,event_id,sender_email,trust_level,reasons,disposition,created_at")
            .eq("tenant_id", context.tenant_id).in_("event_id", sorted(review_event_ids))
            .eq("disposition", "quarantined").order("created_at", desc=True).limit(50).execute(),
            "data", None,
        ) or []
        invitation_reviews = [sanitized_invitation(row) for row in review_rows]
    quarantined_event_ids = {str(review.get("event_id")) for review in invitation_reviews if review.get("event_id")}
    events = [event for event in events if str(event.get("id") or "").split("::", 1)[0] not in quarantined_event_ids and str(event.get("series_id") or "") not in quarantined_event_ids]
    workload_by_user: dict[str, dict[str, Any]] = {}
    for task in tasks:
        owner = str(task.get("owner_user_id") or "unassigned")
        item = workload_by_user.setdefault(owner, {"user_id": task.get("owner_user_id"), "open_tasks": 0, "estimate_minutes": 0, "scheduled_minutes": 0})
        if task.get("status") not in {"done", "cancelled"}:
            item["open_tasks"] += 1
            item["estimate_minutes"] += int(task.get("estimate_minutes") or 0)
            if task.get("scheduled_start") and task.get("scheduled_end"):
                scheduled_start = datetime.fromisoformat(str(task["scheduled_start"]).replace("Z", "+00:00"))
                scheduled_end = datetime.fromisoformat(str(task["scheduled_end"]).replace("Z", "+00:00"))
                item["scheduled_minutes"] += max(0, int((scheduled_end - scheduled_start).total_seconds() / 60))
    return {
        "success": True,
        "calendars": [public_calendar_metadata(access) for access in accesses],
        "events": sorted(events, key=lambda item: item.get("starts_at") or ""),
        "tasks": safe_tasks,
        "workload": list(workload_by_user.values()),
        "connections": connections,
        "invitation_reviews": invitation_reviews,
        "viewer_timezone": str(context.user.get("timezone") or "UTC"),
    }


@router.get("/bootstrap")
def calendar_bootstrap(request: Request, response: Response, start: datetime, end: datetime):
    context = require_active_tenant_member(request, response)
    start, end = parse_range(start, end)
    if not calendar_feature_enabled():
        return _calendar_disabled_payload(context, start, end)
    try:
        cache_key = calendar_workspace_cache_key(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            role=context.role,
            start=iso(start),
            end=iso(end),
        )
        if getattr(request, "headers", {}).get("X-Calendar-Cache-Bypass") == "1":
            invalidate_calendar_workspace_cache(context.tenant_id)
        payload, cache_hit = get_or_create_calendar_workspace(
            cache_key,
            context.tenant_id,
            lambda: _calendar_workspace_payload(context, start, end),
        )
        payload["calendar_features_available"] = True
        response.headers["X-Calendar-Cache"] = "hit" if cache_hit else "miss"
        response.headers["Cache-Control"] = "private, no-store"
        return payload
    except Exception as error:
        if not is_calendar_schema_missing_error(error):
            raise
        logger.error(
            "calendar.schema_missing",
            extra={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail={"code": "calendar_schema_unavailable", "message": "Calendar storage is not ready."},
        ) from error


def _calendar_disabled_payload(context, start: datetime, end: datetime) -> dict[str, Any]:
    reservations = []
    if str(context.role or "").lower() in {"owner", "admin", "member"}:
        reservations = getattr(
            service_supabase.table("builder_reservations")
            .select("*").eq("tenant_id", context.tenant_id)
            .lt("starts_at", iso(end)).gt("ends_at", iso(start)).limit(1000).execute(),
            "data", None,
        ) or []
    events = [reservation_payload(row) for row in reservations if row.get("starts_at")]
    return {
        "success": True,
        "calendar_features_available": False,
        "warning": "Calendar features are disabled. Reservations remain available.",
        "calendars": [], "events": sorted(events, key=lambda item: item.get("starts_at") or ""),
        "tasks": [], "workload": [], "connections": [], "invitation_reviews": [],
        "viewer_timezone": str(context.user.get("timezone") or "UTC"),
    }


@router.post("/calendars", status_code=201)
def create_calendar(payload: CalendarCreate, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    require_calendar_creator(context)
    if payload.is_default:
        service_supabase.table("calendars").update({"is_default": False}).eq("tenant_id", context.tenant_id).eq("owner_user_id", context.user_id).execute()
    row = {**payload.model_dump(), "tenant_id": context.tenant_id, "owner_user_id": context.user_id}
    created = getattr(service_supabase.table("calendars").insert(row).execute(), "data", None) or []
    if not created:
        raise HTTPException(status_code=500, detail="Calendar could not be created")
    service_supabase.table("calendar_memberships").insert({"calendar_id": created[0]["id"], "tenant_id": context.tenant_id, "user_id": context.user_id, "role": "owner"}).execute()
    record_calendar_audit(context, request, "calendar.created", "calendar", created[0]["id"])
    return {"success": True, "calendar": created[0]}


def require_calendar_manager(context, calendar_id: str) -> dict[str, Any]:
    return require_calendar_access(context, calendar_id, "manage_members").calendar


@router.get("/calendars/{calendar_id}/members")
def list_calendar_members(calendar_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    require_calendar_access(context, calendar_id, "manage_members")
    rows = getattr(service_supabase.table("calendar_memberships").select("calendar_id,user_id,role,created_at").eq("calendar_id", calendar_id).eq("tenant_id", context.tenant_id).limit(500).execute(), "data", None) or []
    return {"success": True, "members": rows}


@router.put("/calendars/{calendar_id}/members")
def share_calendar(calendar_id: str, payload: CalendarMemberWrite, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    require_calendar_manager(context, calendar_id)
    tenant_members = getattr(service_supabase.table("tenant_memberships").select("user_id").eq("tenant_id", context.tenant_id).eq("user_id", payload.user_id).eq("status", "active").limit(1).execute(), "data", None) or []
    if not tenant_members:
        raise HTTPException(status_code=400, detail="User is not an active member of this organization")
    rows = getattr(service_supabase.table("calendar_memberships").upsert({"calendar_id": calendar_id, "tenant_id": context.tenant_id, **payload.model_dump()}, on_conflict="calendar_id,user_id").execute(), "data", None) or []
    record_calendar_audit(
        context, request, "calendar.member_assigned", "calendar_membership",
        f"{calendar_id}:{payload.user_id}", {"role": payload.role},
    )
    return {"success": True, "membership": rows[0] if rows else None, "visibility_preview": {"availability": "Busy/free only", "viewer": "View event details", "editor": "Create and edit events", "owner": "Manage events and sharing"}[payload.role]}


def replace_event_children(context, event: dict[str, Any], payload: EventWrite) -> None:
    event_id = event["id"]
    service_supabase.table("calendar_event_attendees").delete().eq("event_id", event_id).eq("tenant_id", context.tenant_id).execute()
    if payload.attendees:
        service_supabase.table("calendar_event_attendees").insert([{"event_id": event_id, "tenant_id": context.tenant_id, "email": item.email.strip().lower(), "display_name": item.display_name, "is_external": True} for item in payload.attendees]).execute()
    service_supabase.table("calendar_event_reminders").delete().eq("event_id", event_id).eq("tenant_id", context.tenant_id).execute()
    if payload.reminders:
        starts_at = payload.starts_at.astimezone(timezone.utc)
        service_supabase.table("calendar_event_reminders").insert([{"event_id": event_id, "tenant_id": context.tenant_id, "channel": item.channel, "minutes_before": item.minutes_before, "scheduled_for": iso(starts_at - timedelta(minutes=item.minutes_before))} for item in payload.reminders]).execute()


def normalized_event_row(context, payload: EventWrite) -> dict[str, Any]:
    if payload.starts_at.tzinfo is None or payload.ends_at.tzinfo is None or payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="Event end must be after start and include a timezone")
    require_calendar_access(context, str(payload.calendar_id), "create_event")
    return {
        "tenant_id": context.tenant_id, "calendar_id": str(payload.calendar_id), "created_by": context.user_id,
        "title": payload.title.strip(), "description": payload.description, "location": payload.location,
        "starts_at": iso(payload.starts_at), "ends_at": iso(payload.ends_at), "timezone": payload.timezone,
        "all_day": payload.all_day, "status": payload.status, "visibility": payload.visibility,
        "transparency": payload.transparency, "recurrence_rule": payload.recurrence_rule or None,
        "project_id": validate_project_reference(context, payload.project_id),
    }


@router.post("/events", status_code=201)
def create_event(payload: EventWrite, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    row = normalized_event_row(context, payload)
    conflicts = event_conflicts(context.tenant_id, row["calendar_id"], payload.starts_at, payload.ends_at)
    if conflicts and not payload.allow_conflicts:
        raise HTTPException(status_code=409, detail={"code": "calendar_event_conflict", "message": "This time overlaps another busy event.", "conflicts": conflicts})
    created = getattr(service_supabase.table("calendar_events").insert(row).execute(), "data", None) or []
    if not created:
        raise HTTPException(status_code=500, detail="Event could not be created")
    replace_event_children(context, created[0], payload)
    write_change(context, created[0]["id"], "created", "event", None, created[0])
    record_calendar_audit(context, request, "calendar.event_created", "calendar_event", created[0]["id"], {"calendar_id": row["calendar_id"]})
    return {"success": True, "event": created[0], "conflicts": conflicts}


@router.put("/events/{event_id}")
def update_event(event_id: str, payload: EventWrite, request: Request, response: Response, scope: Literal["event", "occurrence", "future", "series"] = "event", occurrence_start: Optional[datetime] = None):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    before = tenant_event(event_id, context.tenant_id)
    require_calendar_access(context, str(before.get("calendar_id")), "update_event")
    if payload.expected_version is not None and int(before.get("version") or 1) != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "calendar_version_conflict", "message": "This event changed in another session.", "current": before})
    row = normalized_event_row(context, payload)
    require_calendar_access(context, row["calendar_id"], "update_event")
    conflicts = event_conflicts(context.tenant_id, row["calendar_id"], payload.starts_at, payload.ends_at, event_id)
    if conflicts and not payload.allow_conflicts:
        raise HTTPException(status_code=409, detail={"code": "calendar_event_conflict", "message": "This time overlaps another busy event.", "conflicts": conflicts})
    if scope in {"occurrence", "future"}:
        if not before.get("recurrence_rule") or occurrence_start is None:
            raise HTTPException(status_code=400, detail="A recurring occurrence must be selected for this edit scope")
        occurrence_start = occurrence_start.astimezone(timezone.utc)
        if scope == "occurrence":
            parent = exclude_occurrence(context, before, occurrence_start)
            row.update({"recurrence_rule": None, "recurrence_parent_id": event_id, "recurrence_original_start": iso(occurrence_start), "version": 1})
            created = getattr(service_supabase.table("calendar_events").insert(row).execute(), "data", None) or []
            if not created:
                raise HTTPException(status_code=500, detail="Recurring occurrence could not be updated")
            replace_event_children(context, created[0], payload)
            write_change(context, created[0]["id"], "created", "occurrence", None, created[0])
            write_change(context, event_id, "updated", "occurrence", before, parent)
            record_calendar_audit(context, request, "calendar.event_updated", "calendar_event", event_id, {"scope": scope})
            return {"success": True, "event": created[0], "series": parent, "conflicts": conflicts}
        parent_rule = truncated_recurrence_rule(before["recurrence_rule"], occurrence_start - timedelta(seconds=1))
        parent_rows = getattr(service_supabase.table("calendar_events").update({"recurrence_rule": parent_rule, "version": int(before.get("version") or 1) + 1}).eq("id", event_id).eq("tenant_id", context.tenant_id).execute(), "data", None) or []
        row.update({"recurrence_parent_id": None, "recurrence_original_start": None, "version": 1})
        created = getattr(service_supabase.table("calendar_events").insert(row).execute(), "data", None) or []
        if not created:
            raise HTTPException(status_code=500, detail="Future recurring events could not be updated")
        replace_event_children(context, created[0], payload)
        write_change(context, event_id, "updated", "future", before, parent_rows[0] if parent_rows else before)
        write_change(context, created[0]["id"], "created", "future", None, created[0])
        record_calendar_audit(context, request, "calendar.event_updated", "calendar_event", event_id, {"scope": scope})
        return {"success": True, "event": created[0], "series": parent_rows[0] if parent_rows else before, "conflicts": conflicts}
    row["version"] = int(before.get("version") or 1) + 1
    updated = getattr(service_supabase.table("calendar_events").update(row).eq("id", event_id).eq("tenant_id", context.tenant_id).execute(), "data", None) or []
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")
    replace_event_children(context, updated[0], payload)
    write_change(context, event_id, "updated", scope, before, updated[0])
    record_calendar_audit(context, request, "calendar.event_updated", "calendar_event", event_id, {"scope": scope})
    return {"success": True, "event": updated[0], "conflicts": conflicts}


@router.delete("/events/{event_id}")
def delete_event(event_id: str, request: Request, response: Response, expected_version: int = Query(ge=1), scope: Literal["event", "occurrence", "future", "series"] = "event", occurrence_start: Optional[datetime] = None):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    before = tenant_event(event_id, context.tenant_id)
    require_calendar_access(context, str(before.get("calendar_id")), "delete_event")
    if int(before.get("version") or 1) != expected_version:
        raise HTTPException(status_code=409, detail={"code": "calendar_version_conflict", "current": before})
    if scope in {"occurrence", "future"}:
        if not before.get("recurrence_rule") or occurrence_start is None:
            raise HTTPException(status_code=400, detail="A recurring occurrence must be selected for this delete scope")
        if scope == "occurrence":
            updated = exclude_occurrence(context, before, occurrence_start)
        else:
            updated_rows = getattr(service_supabase.table("calendar_events").update({
                "recurrence_rule": truncated_recurrence_rule(before["recurrence_rule"], occurrence_start - timedelta(seconds=1)),
                "version": expected_version + 1,
            }).eq("id", event_id).eq("tenant_id", context.tenant_id).execute(), "data", None) or []
            updated = updated_rows[0] if updated_rows else before
        write_change(context, event_id, "cancelled", scope, before, updated)
        record_calendar_audit(context, request, "calendar.event_deleted", "calendar_event", event_id, {"scope": scope})
        return {"success": True, "event": updated}
    deleted_at = iso(utc_now())
    updated = getattr(service_supabase.table("calendar_events").update({"deleted_at": deleted_at, "version": expected_version + 1}).eq("id", event_id).eq("tenant_id", context.tenant_id).execute(), "data", None) or []
    write_change(context, event_id, "deleted", scope, before, updated[0] if updated else None)
    record_calendar_audit(context, request, "calendar.event_deleted", "calendar_event", event_id, {"scope": scope})
    return {"success": True}


@router.get("/events/{event_id}/history")
def event_history(event_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    event = tenant_event(event_id, context.tenant_id)
    require_calendar_access(context, str(event.get("calendar_id")), "view_history")
    rows = getattr(service_supabase.table("calendar_event_changes").select("*").eq("tenant_id", context.tenant_id).eq("event_id", event_id).order("created_at", desc=True).limit(100).execute(), "data", None) or []
    return {"success": True, "history": rows}


@router.post("/tasks", status_code=201)
def create_task(payload: TaskWrite, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    calendar_id = str(payload.calendar_id) if payload.calendar_id else str(
        ensure_default_calendar(context)["id"]
    )
    require_calendar_access(context, calendar_id, "manage_tasks")
    row = payload.model_dump(mode="json", exclude={"reminder_minutes_before"})
    row.update({
        "tenant_id": context.tenant_id,
        "calendar_id": calendar_id,
        "owner_user_id": validate_active_task_owner(context, payload.owner_user_id),
        "project_id": validate_project_reference(context, payload.project_id),
    })
    created = getattr(service_supabase.table("calendar_tasks").insert(row).execute(), "data", None) or []
    if created:
        sync_task_reminder(created[0], payload.reminder_minutes_before, schedule_changed=True)
        created[0]["reminder_minutes_before"] = payload.reminder_minutes_before
        record_calendar_audit(context, request, "calendar.task_created", "calendar_task", created[0]["id"], {"calendar_id": row.get("calendar_id")})
    return {
        "success": True,
        "task": safe_task_payload(created[0]) if created else None,
    }


@router.get("/tasks/archived")
def list_archived_tasks(request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    detail_ids = [
        str(access.calendar.get("id"))
        for access in list_accessible_calendars(context)
        if access.role in {"viewer", "editor", "owner"}
    ]
    tasks: list[dict[str, Any]] = []
    if detail_ids:
        tasks = getattr(
            service_supabase.table("calendar_tasks").select("*")
            .eq("tenant_id", context.tenant_id).in_("calendar_id", detail_ids)
            .not_.is_("archived_at", "null").order("archived_at", desc=True)
            .limit(1000).execute(),
            "data", None,
        ) or []
    unassigned_query = (
        service_supabase.table("calendar_tasks").select("*")
        .eq("tenant_id", context.tenant_id)
        .is_("calendar_id", "null")
        .not_.is_("archived_at", "null")
    )
    if str(context.role or "").lower() not in {"owner", "admin"}:
        unassigned_query = unassigned_query.eq("owner_user_id", context.user_id)
    unassigned_tasks = getattr(
        unassigned_query.order("archived_at", desc=True).limit(1000).execute(),
        "data",
        None,
    ) or []
    archived_tasks = list({
        str(task.get("id")): task
        for task in [*tasks, *unassigned_tasks]
        if task.get("id")
    }.values())
    archived_tasks.sort(key=lambda task: str(task.get("archived_at") or ""), reverse=True)
    return {
        "success": True,
        "tasks": [safe_task_payload(task) for task in archived_tasks],
    }


@router.put("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskWrite, request: Request, response: Response, expected_version: int = Query(ge=1)):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    before = tenant_task(task_id, context.tenant_id)
    require_task_access(context, before)
    if payload.calendar_id:
        require_calendar_access(context, str(payload.calendar_id), "manage_tasks")
    else:
        require_task_access(context, {**before, "calendar_id": None})
    row = payload.model_dump(mode="json", exclude={"reminder_minutes_before"})
    row["owner_user_id"] = validate_active_task_owner(context, payload.owner_user_id)
    row["project_id"] = validate_project_reference(context, payload.project_id)
    row["version"] = expected_version + 1
    linked_connection = None
    if before.get("sync_connection_id"):
        linked_connection = task_sync_connection(
            context,
            {**before, **row},
            str(before["sync_connection_id"]),
        )
    updated = getattr(service_supabase.table("calendar_tasks").update(row).eq("id", task_id).eq("tenant_id", context.tenant_id).eq("version", expected_version).execute(), "data", None) or []
    if not updated:
        raise HTTPException(status_code=409, detail="Task changed or was removed")
    schedule_changed = (
        before.get("scheduled_start") != updated[0].get("scheduled_start")
        or before.get("recurrence_rule") != updated[0].get("recurrence_rule")
    )
    sync_task_reminder(
        updated[0], payload.reminder_minutes_before, schedule_changed=schedule_changed
    )
    updated[0]["reminder_minutes_before"] = payload.reminder_minutes_before
    record_calendar_audit(
        context, request, "calendar.task_updated", "calendar_task", task_id,
        {"owner_changed": before.get("owner_user_id") != updated[0].get("owner_user_id")},
    )
    if linked_connection:
        try:
            updated[0] = queue_task_to_provider(
                context, updated[0], linked_connection
            )
        except CalendarSyncError as error:
            raise sync_http_error(error) from error
    return {"success": True, "task": safe_task_payload(updated[0])}


@router.post("/tasks/{task_id}/sync", status_code=202)
def sync_task(
    task_id: str, payload: TaskSyncWrite, request: Request, response: Response
):
    started_at = time.monotonic()
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    task = tenant_task(task_id, context.tenant_id)
    require_task_access(context, task)
    connection = task_sync_connection(context, task, str(payload.connection_id))
    try:
        updated = queue_task_to_provider(context, task, connection)
    except CalendarSyncError as error:
        raise sync_http_error(error) from error
    record_calendar_audit(
        context,
        request,
        "calendar.task_sync_queued",
        "calendar_task",
        task_id,
        {"provider": connection.get("provider")},
    )
    logger.info(
        "calendar.task_sync_queued",
        extra={
            "provider": connection.get("provider"),
            "duration_ms": round((time.monotonic() - started_at) * 1000),
        },
    )
    return {
        "success": True,
        "status": "queued",
        "sync_status": "pending",
        "task": safe_task_payload(updated),
    }


@router.post("/tasks/{task_id}/archive")
def archive_task(
    task_id: str,
    request: Request,
    response: Response,
    expected_version: int = Query(ge=1),
):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    task = tenant_task(task_id, context.tenant_id)
    require_task_access(context, task)
    updated = getattr(
        service_supabase.table("calendar_tasks").update({
            "archived_at": iso(utc_now()),
            "version": expected_version + 1,
        }).eq("id", task_id).eq("tenant_id", context.tenant_id)
        .eq("version", expected_version).is_("archived_at", "null").execute(),
        "data", None,
    ) or []
    if not updated:
        raise HTTPException(status_code=409, detail="Task changed or was removed")
    sync_task_reminder(updated[0], None)
    record_calendar_audit(
        context,
        request,
        "calendar.task_archived",
        "calendar_task",
        task_id,
        {"previous_status": task.get("status")},
    )
    return {"success": True, "task": safe_task_payload(updated[0])}


@router.delete("/tasks/{task_id}/sync")
def unlink_task_sync(task_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    task = tenant_task(task_id, context.tenant_id)
    require_task_access(context, task)
    updated = getattr(
        service_supabase.table("calendar_tasks").update({
            "sync_connection_id": None,
            "sync_event_id": None,
            "sync_status": "not_synced",
            "sync_error_code": None,
        }).eq("id", task_id).eq("tenant_id", context.tenant_id).execute(),
        "data",
        None,
    ) or []
    record_calendar_audit(
        context,
        request,
        "calendar.task_sync_unlinked",
        "calendar_task",
        task_id,
        {"provider_event_preserved": bool(task.get("sync_event_id"))},
    )
    return {
        "success": True,
        "task": safe_task_payload(updated[0]) if updated else None,
    }


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    request: Request,
    response: Response,
    mode: Literal["local_only", "local_and_provider"] = "local_only",
):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    task = tenant_task(task_id, context.tenant_id)
    require_task_access(context, task)
    provider_deleted = False
    provider_delete_queued = False
    if mode == "local_and_provider":
        if not task.get("sync_connection_id") or not task.get("sync_event_id"):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "task_not_synchronized",
                    "message": "This task is not linked to a provider event.",
                },
            )
        connection = task_sync_connection(
            context, task, str(task["sync_connection_id"])
        )
        tenant_event(str(task["sync_event_id"]), context.tenant_id)
        service_supabase.table("calendar_tasks").update({
            "sync_status": "pending",
            "sync_error_code": None,
        }).eq("id", task_id).eq("tenant_id", context.tenant_id).execute()
        enqueue_task_sync(
            tenant_id=context.tenant_id,
            task_id=task_id,
            connection_id=str(connection["id"]),
            operation="delete",
            task_version=int(task.get("version") or 1),
        )
        provider_delete_queued = True
        record_calendar_audit(
            context,
            request,
            "calendar.task_provider_delete_queued",
            "calendar_task",
            task_id,
            {"mode": mode},
        )
        response.status_code = 202
        return {
            "success": True,
            "status": "queued",
            "sync_status": "pending",
            "provider_event_deleted": False,
        }
    deleted = getattr(
        service_supabase.table("calendar_tasks")
        .delete()
        .eq("id", task_id)
        .eq("tenant_id", context.tenant_id)
        .execute(),
        "data",
        None,
    ) or []
    if not deleted:
        raise HTTPException(status_code=409, detail="Task changed or was removed")
    record_calendar_audit(
        context,
        request,
        "calendar.task_deleted",
        "calendar_task",
        task_id,
        {
            "mode": mode,
            "was_synchronized": bool(task.get("sync_event_id")),
            "provider_event_deleted": provider_deleted,
        },
    )
    return {
        "success": True,
        "provider_event_deleted": provider_deleted,
        "provider_delete_queued": provider_delete_queued,
    }


def dependency_would_cycle(tenant_id: int, task_id: str, dependency_id: str) -> bool:
    rows = getattr(
        service_supabase.table("calendar_task_dependencies")
        .select("task_id,depends_on_task_id")
        .eq("tenant_id", tenant_id)
        .limit(MAX_DEPENDENCY_EDGES + 1)
        .execute(),
        "data",
        None,
    ) or []
    if len(rows) > MAX_DEPENDENCY_EDGES:
        raise HTTPException(status_code=409, detail="Task dependency graph is too large to validate safely")
    graph: dict[str, set[str]] = {}
    for row in rows:
        graph.setdefault(str(row.get("task_id")), set()).add(str(row.get("depends_on_task_id")))
    graph.setdefault(task_id, set()).add(dependency_id)
    pending = [dependency_id]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        if len(visited) > MAX_DEPENDENCY_EDGES:
            raise HTTPException(status_code=409, detail="Task dependency graph is too large to validate safely")
        pending.extend(graph.get(current, ()))
    return False


@router.post("/tasks/{task_id}/dependencies", status_code=201)
def add_task_dependency(task_id: str, payload: TaskDependencyWrite, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    dependency_id = str(payload.depends_on_task_id)
    if dependency_id == task_id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")
    rows = getattr(service_supabase.table("calendar_tasks").select("id,calendar_id,owner_user_id,status").eq("tenant_id", context.tenant_id).in_("id", [task_id, dependency_id]).execute(), "data", None) or []
    if len({str(row.get("id")) for row in rows}) != 2:
        raise HTTPException(status_code=404, detail="Task dependency was not found")
    tasks_by_id = {str(row.get("id")): row for row in rows}
    require_task_access(context, tasks_by_id[task_id])
    require_task_access(context, tasks_by_id[dependency_id])
    if tasks_by_id[dependency_id].get("status") == "cancelled":
        raise HTTPException(status_code=404, detail="Task dependency was not found")
    if dependency_would_cycle(context.tenant_id, task_id, dependency_id):
        raise HTTPException(status_code=409, detail="This dependency would create a cycle")
    service_supabase.table("calendar_task_dependencies").upsert({"tenant_id": context.tenant_id, "task_id": task_id, "depends_on_task_id": dependency_id}, on_conflict="task_id,depends_on_task_id").execute()
    record_calendar_audit(context, request, "calendar.task_dependency_added", "calendar_task", task_id, {"depends_on_task_id": dependency_id})
    return {"success": True}


@router.get("/invitation-reviews")
def list_invitation_reviews(request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    calendar_ids = [
        str(access.calendar.get("id")) for access in list_accessible_calendars(context)
        if access.allows("review_invitations")
    ]
    if not calendar_ids:
        return {"success": True, "reviews": []}
    event_rows = getattr(
        service_supabase.table("calendar_events").select("id")
        .eq("tenant_id", context.tenant_id).in_("calendar_id", calendar_ids)
        .limit(5000).execute(), "data", None,
    ) or []
    event_ids = [str(row.get("id")) for row in event_rows if row.get("id")]
    if not event_ids:
        return {"success": True, "reviews": []}
    rows = getattr(
        service_supabase.table("calendar_invitation_reviews")
        .select("id,event_id,sender_email,trust_level,reasons,disposition,created_at")
        .eq("tenant_id", context.tenant_id).in_("event_id", event_ids)
        .eq("disposition", "quarantined").order("created_at", desc=True).limit(200).execute(),
        "data", None,
    ) or []
    return {"success": True, "reviews": [sanitized_invitation(row) for row in rows]}


@router.post("/invitation-reviews/{review_id}")
def resolve_invitation_review(review_id: str, disposition: Literal["allowed", "blocked", "reported"], request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    existing = getattr(service_supabase.table("calendar_invitation_reviews").select("id,event_id").eq("id", review_id).eq("tenant_id", context.tenant_id).eq("disposition", "quarantined").limit(1).execute(), "data", None) or []
    if not existing:
        raise HTTPException(status_code=404, detail="Invitation review not found")
    event = tenant_event(str(existing[0].get("event_id")), context.tenant_id)
    require_calendar_access(context, str(event.get("calendar_id")), "review_invitations")
    rows = getattr(service_supabase.table("calendar_invitation_reviews").update({"disposition": disposition}).eq("id", review_id).eq("tenant_id", context.tenant_id).eq("disposition", "quarantined").execute(), "data", None) or []
    if not rows:
        raise HTTPException(status_code=409, detail="Invitation review changed")
    if disposition in {"blocked", "reported"} and rows[0].get("event_id"):
        service_supabase.table("calendar_events").update({"status": "cancelled", "deleted_at": iso(utc_now())}).eq("id", rows[0]["event_id"]).eq("tenant_id", context.tenant_id).execute()
    record_calendar_audit(context, request, "calendar.invitation_reviewed", "calendar_invitation_review", review_id, {"disposition": disposition})
    return {"success": True, "review": sanitized_invitation(rows[0])}


@router.post("/connections", status_code=201)
def create_sync_connection(payload: ConnectionWrite, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    require_calendar_creator(context)
    existing = reusable_pending_connection(context, payload, request)
    if existing:
        record_calendar_audit(
            context,
            request,
            "calendar.connection_reused",
            "calendar_sync_connection",
            existing["id"],
            {"provider": payload.provider},
        )
        return {
            "success": True,
            "connection": safe_connection_payload(existing),
            "requires_oauth": True,
            "reused": True,
        }
    calendar = getattr(service_supabase.table("calendars").insert({
        "tenant_id": context.tenant_id, "owner_user_id": context.user_id,
        "name": payload.account_label or f"{payload.provider.title()} Calendar",
        "color": "#4285f4" if payload.provider == "google" else "#0078d4" if payload.provider == "microsoft" else "#7c6ee6",
        "timezone": str(context.user.get("timezone") or "UTC"), "visibility": "private", "is_default": False,
    }).execute(), "data", None) or []
    if not calendar:
        raise HTTPException(status_code=500, detail="Connection calendar could not be created")
    service_supabase.table("calendar_memberships").insert({"calendar_id": calendar[0]["id"], "tenant_id": context.tenant_id, "user_id": context.user_id, "role": "owner"}).execute()
    created = getattr(service_supabase.table("calendar_sync_connections").insert({"tenant_id": context.tenant_id, "user_id": context.user_id, "local_calendar_id": calendar[0]["id"], **payload.model_dump(), "status": "connected" if payload.provider == "ics" else "setup_required"}).execute(), "data", None) or []
    if created:
        record_calendar_audit(context, request, "calendar.connection_created", "calendar_sync_connection", created[0]["id"], {"provider": payload.provider})
    safe_connection = safe_connection_payload(created[0]) if created else None
    return {"success": True, "connection": safe_connection, "requires_oauth": payload.provider in {"google", "microsoft"}, "reused": False}


@router.post("/connections/{connection_id}/authorize")
def authorize_sync_connection(connection_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = tenant_connection(connection_id, context.tenant_id, context.user_id)
    require_calendar_access(context, str(connection.get("local_calendar_id")), "manage_oauth_connection")
    try:
        url = authorization_url(connection)
    except CalendarSyncError as error:
        raise sync_http_error(error) from error
    return {"success": True, "authorization_url": url}


@router.post("/connections/{connection_id}/upgrade")
def upgrade_sync_connection(connection_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = tenant_connection(connection_id, context.tenant_id, context.user_id)
    require_calendar_access(
        context, str(connection.get("local_calendar_id")), "manage_oauth_connection"
    )
    if (
        connection.get("provider") != "google"
        or connection.get("direction") != "read"
        or str(connection.get("status") or "") not in {"connected", "degraded"}
        or not connection.get("encrypted_credentials")
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_upgrade_unavailable",
                "message": "This calendar connection cannot be upgraded.",
            },
        )
    try:
        url = authorization_url(connection, direction_override="two_way")
    except CalendarSyncError as error:
        raise sync_http_error(error) from error
    record_calendar_audit(
        context,
        request,
        "calendar.oauth_upgrade_requested",
        "calendar_sync_connection",
        connection_id,
        {"provider": "google"},
    )
    return {"success": True, "authorization_url": url}


@router.get("/oauth/{provider}/callback")
def calendar_oauth_callback(
    provider: Literal["google", "microsoft"],
    request: Request,
    response: Response,
    state: str = Query(min_length=1, max_length=8192),
    code: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
    error: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = None
    try:
        state_data = decode_oauth_state(state)
        if state_data.get("provider") != provider or int(state_data.get("tenant_id")) != context.tenant_id or int(state_data.get("user_id")) != context.user_id:
            raise CalendarSyncError("oauth_state_mismatch", "Calendar authorization does not match this account.")
        connection = tenant_connection(str(state_data.get("connection_id")), context.tenant_id, context.user_id)
        if str(connection.get("local_calendar_id")) != str(state_data.get("calendar_id")):
            raise CalendarSyncError("oauth_state_mismatch", "Calendar authorization does not match this calendar.")
        require_calendar_access(context, str(connection.get("local_calendar_id")), "manage_oauth_connection")
        consume_oauth_state(state_data)
        if error:
            raise CalendarSyncError("oauth_access_denied", "Calendar authorization was not completed.")
        if not code:
            raise CalendarSyncError("oauth_code_missing", "Calendar authorization did not return a code.")
        previous_credentials = (
            decrypt_credentials(connection["encrypted_credentials"])
            if connection.get("encrypted_credentials")
            else None
        )
        credentials = exchange_authorization_code(
            provider, code, previous_credentials=previous_credentials
        )
        intended_direction = str(state_data.get("direction") or "read")
        if intended_direction not in {"read", "two_way"}:
            raise CalendarSyncError("oauth_direction_invalid", "Calendar access mode is invalid.")
        if not credentials_allow_direction(provider, credentials, intended_direction):
            raise CalendarSyncError(
                "oauth_scope_insufficient",
                "The calendar provider did not grant the requested access.",
            )
        previous_direction = str(connection.get("direction") or "read")
        service_supabase.table("calendar_sync_connections").update({
            "encrypted_credentials": encrypt_credentials(credentials), "status": "connected",
            "direction": intended_direction, "last_error_code": None,
            "last_attempt_at": iso(utc_now()),
        }).eq("id", connection["id"]).eq("tenant_id", context.tenant_id).execute()
        action = (
            "calendar.oauth_upgraded"
            if previous_direction != intended_direction
            else "calendar.oauth_connected"
        )
        record_calendar_audit(
            context,
            request,
            action,
            "calendar_sync_connection",
            connection["id"],
            {"provider": provider, "direction": intended_direction},
        )
    except CalendarSyncError as error:
        if connection is not None:
            mark_pending_connection_failed(connection, error.code)
        logger.warning("calendar.oauth_failed", extra={"error_code": error.code})
        return RedirectResponse(frontend_calendar_url(status="error"), status_code=303)
    return RedirectResponse(frontend_calendar_url(status="connected"), status_code=303)


@router.delete("/connections/{connection_id}")
def remove_incomplete_sync_connection(connection_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = tenant_connection(connection_id, context.tenant_id)
    require_calendar_access(context, str(connection.get("local_calendar_id")), "manage_oauth_connection")
    if (
        str(connection.get("status") or "") not in {"setup_required", "disconnected"}
        or connection.get("encrypted_credentials")
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_connection_requires_disconnect",
                "message": "Connected calendar accounts must be disconnected.",
            },
        )
    deleted = getattr(
        service_supabase.table("calendar_sync_connections")
        .delete()
        .eq("id", connection_id)
        .eq("tenant_id", context.tenant_id)
        .in_("status", ["setup_required", "disconnected"])
        .is_("encrypted_credentials", "null")
        .execute(),
        "data",
        None,
    ) or []
    if not deleted:
        raise HTTPException(status_code=409, detail="Calendar connection changed")
    calendar_removed = remove_empty_connection_calendar(connection)
    record_calendar_audit(
        context,
        request,
        "calendar.connection_removed",
        "calendar_sync_connection",
        connection_id,
        {
            "provider": connection.get("provider"),
            "empty_calendar_removed": calendar_removed,
        },
    )
    return {"success": True, "removed": True}


@router.post("/connections/{connection_id}/disconnect")
def disconnect_sync_connection(connection_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = tenant_connection(connection_id, context.tenant_id)
    require_calendar_access(context, str(connection.get("local_calendar_id")), "manage_oauth_connection")
    if (
        str(connection.get("status") or "") not in {"connected", "degraded"}
        and not connection.get("encrypted_credentials")
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_connection_not_connected",
                "message": "This calendar account is not connected.",
            },
        )
    revoked = disconnect_connection(connection)
    record_calendar_audit(context, request, "calendar.oauth_disconnected", "calendar_sync_connection", connection_id, {"provider": connection.get("provider"), "provider_revocation_confirmed": revoked})
    return {"success": True, "provider_revocation_confirmed": revoked}


@router.post("/connections/{connection_id}/sync", status_code=202)
def run_connection_sync(connection_id: str, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = tenant_connection(connection_id, context.tenant_id)
    require_calendar_access(context, str(connection.get("local_calendar_id")), "trigger_sync")
    if (
        connection.get("status") not in {"connected", "degraded"}
        or connection.get("provider") not in {"google", "microsoft"}
        or not connection.get("encrypted_credentials")
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_connection_not_ready",
                "message": "Finish connecting this calendar before synchronizing.",
            },
        )
    if not connection.get("inbound_sync_enabled", True):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_inbound_sync_disabled",
                "message": "Inbound synchronization is disabled for this calendar.",
            },
        )
    try:
        enqueue_connection_sync(
            tenant_id=context.tenant_id,
            connection_id=connection_id,
            operation="incremental",
        )
    except CalendarSyncError as error:
        raise sync_http_error(error) from error
    record_calendar_audit(
        context,
        request,
        "calendar.sync_queued",
        "calendar_sync_connection",
        connection_id,
    )
    return {
        "success": True,
        "status": "queued",
        "sync_status": "pending",
    }


class InboundSyncWrite(BaseModel):
    enabled: bool


@router.patch("/connections/{connection_id}/inbound")
def set_connection_inbound_sync(
    connection_id: str,
    payload: InboundSyncWrite,
    request: Request,
    response: Response,
):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    connection = tenant_connection(connection_id, context.tenant_id)
    require_calendar_access(
        context,
        str(connection.get("local_calendar_id")),
        "manage_oauth_connection",
    )
    if connection.get("status") not in {"connected", "degraded"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "calendar_connection_not_ready",
                "message": "Finish connecting this calendar before changing synchronization.",
            },
        )
    values = {
        "inbound_sync_enabled": payload.enabled,
        "inbound_sync_status": "idle" if not payload.enabled else "pending",
        "inbound_sync_error_code": None,
    }
    rows = getattr(
        service_supabase.table("calendar_sync_connections")
        .update(values)
        .eq("id", connection_id)
        .eq("tenant_id", context.tenant_id)
        .execute(),
        "data",
        None,
    ) or []
    if payload.enabled:
        try:
            enqueue_connection_sync(
                tenant_id=context.tenant_id,
                connection_id=connection_id,
                operation="incremental",
            )
        except CalendarSyncError as error:
            service_supabase.table("calendar_sync_connections").update(
                {
                    "inbound_sync_enabled": bool(
                        connection.get("inbound_sync_enabled", True)
                    ),
                    "inbound_sync_status": connection.get(
                        "inbound_sync_status", "idle"
                    ),
                }
            ).eq("id", connection_id).eq(
                "tenant_id", context.tenant_id
            ).execute()
            raise sync_http_error(error) from error
    record_calendar_audit(
        context,
        request,
        "calendar.inbound_sync_changed",
        "calendar_sync_connection",
        connection_id,
        {"enabled": payload.enabled},
    )
    return {
        "success": True,
        "connection": safe_connection_payload(rows[0] if rows else {
            **connection,
            **values,
        }),
    }


@router.get("/sync-conflicts")
def list_sync_conflicts(request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    calendar_ids = [str(access.calendar.get("id")) for access in list_accessible_calendars(context) if access.allows("view_conflicts")]
    if not calendar_ids:
        return {"success": True, "conflicts": []}
    connections = getattr(service_supabase.table("calendar_sync_connections").select("id").eq("tenant_id", context.tenant_id).in_("local_calendar_id", calendar_ids).limit(500).execute(), "data", None) or []
    connection_ids = [str(row.get("id")) for row in connections if row.get("id")]
    if not connection_ids:
        return {"success": True, "conflicts": []}
    rows = getattr(service_supabase.table("calendar_sync_conflicts").select("id,connection_id,event_id,local_data,remote_data,status,created_at").eq("tenant_id", context.tenant_id).in_("connection_id", connection_ids).eq("status", "unresolved").order("created_at", desc=True).limit(200).execute(), "data", None) or []
    return {"success": True, "conflicts": [sanitized_conflict(row) for row in rows]}


@router.post("/sync-conflicts/{conflict_id}/resolve")
def resolve_sync_conflict(conflict_id: str, resolution: Literal["keep_local", "use_remote", "ignore"], request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    rows = getattr(service_supabase.table("calendar_sync_conflicts").select("*").eq("id", conflict_id).eq("tenant_id", context.tenant_id).eq("status", "unresolved").limit(1).execute(), "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Sync conflict not found")
    conflict = rows[0]
    connection = tenant_connection(str(conflict.get("connection_id")), context.tenant_id)
    require_calendar_access(context, str(connection.get("local_calendar_id")), "view_conflicts")
    if resolution == "use_remote" and conflict.get("event_id"):
        remote = conflict.get("remote_data") or {}
        start = remote.get("start") or {}
        end = remote.get("end") or {}
        service_supabase.table("calendar_events").update({
            "title": remote.get("summary") or remote.get("subject") or "Untitled event",
            "description": remote.get("description") or "",
            "starts_at": start.get("dateTime") if isinstance(start, dict) else start,
            "ends_at": end.get("dateTime") if isinstance(end, dict) else end,
            "version": int((conflict.get("local_data") or {}).get("version") or 1) + 1,
            "last_synced_at": iso(utc_now()),
        }).eq("id", conflict["event_id"]).eq("tenant_id", context.tenant_id).execute()
    service_supabase.table("calendar_sync_conflicts").update({"status": "ignored" if resolution == "ignore" else "resolved", "resolution": resolution, "resolved_at": iso(utc_now())}).eq("id", conflict_id).eq("tenant_id", context.tenant_id).execute()
    record_calendar_audit(context, request, "calendar.sync_conflict_resolved", "calendar_sync_conflict", conflict_id, {"resolution": resolution})
    return {"success": True}


def ics_escape(value: Any) -> str:
    escape = chr(92)
    return (
        str(value or "")
        .replace(escape, escape * 2)
        .replace(";", escape + ";")
        .replace(",", escape + ",")
        .replace(chr(10), escape + "n")
    )


def ics_date(value: Any) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def parse_ics_datetime(value: str) -> datetime:
    raw = value.strip()
    if len(raw) == 8:
        return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
    if raw.endswith("Z"):
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def parse_ics_events(content: str) -> list[dict[str, str]]:
    unfolded: list[str] = []
    for raw_line in content.replace(chr(13), "").split(chr(10)):
        if raw_line.startswith((" ", chr(9))) and unfolded:
            unfolded[-1] += raw_line[1:]
        else:
            unfolded.append(raw_line)
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.split(";", 1)[0].upper()] = value
    return events


def ics_unescape(value: str) -> str:
    escape = chr(92)
    return value.replace(escape + "n", chr(10)).replace(escape + ",", ",").replace(escape + ";", ";").replace(escape * 2, escape)


def invitation_risk_reasons(sender_email: str, title: str, description: str) -> list[str]:
    reasons: list[str] = []
    domain = sender_email.rsplit("@", 1)[-1].lower() if "@" in sender_email else ""
    combined = f"{title} {description}".lower()
    if not domain:
        reasons.append("sender_address_invalid")
    if "xn--" in domain:
        reasons.append("internationalized_domain_requires_review")
    if combined.count("http://") + combined.count("https://") >= 3:
        reasons.append("unusually_many_links")
    if any(term in combined for term in ("password", "verify account", "wire transfer", "crypto payment")):
        reasons.append("sensitive_or_payment_language")
    return reasons


@router.post("/import.ics")
def import_calendar_ics(payload: IcsImportWrite, request: Request, response: Response):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    calendar_id = str(payload.calendar_id)
    require_calendar_access(context, calendar_id, "import_export")
    require_calendar_access(context, calendar_id, "create_event")
    imported = updated = skipped = 0
    for item in parse_ics_events(payload.content)[:5000]:
        try:
            starts_at = parse_ics_datetime(item["DTSTART"])
            ends_at = parse_ics_datetime(item.get("DTEND") or item["DTSTART"])
        except (KeyError, ValueError):
            skipped += 1
            continue
        if ends_at <= starts_at:
            ends_at = starts_at + timedelta(hours=1)
        fallback_uid = hashlib.sha256((item.get("DTSTART", "") + item.get("SUMMARY", "")).encode()).hexdigest()
        uid = str(item.get("UID") or f"generated-{fallback_uid}")[:500]
        source_id = f"{calendar_id}:{uid}"
        row = {
            "tenant_id": context.tenant_id, "calendar_id": calendar_id, "created_by": context.user_id,
            "title": ics_unescape(item.get("SUMMARY") or "Untitled event")[:240],
            "description": ics_unescape(item.get("DESCRIPTION") or "")[:20000],
            "location": ics_unescape(item.get("LOCATION") or "")[:500],
            "starts_at": iso(starts_at), "ends_at": iso(ends_at), "timezone": "UTC",
            "all_day": len(item.get("DTSTART") or "") == 8, "status": "confirmed",
            "visibility": "calendar_default", "transparency": "busy",
            "recurrence_rule": item.get("RRULE") or None, "source_type": "ics", "source_id": source_id,
            "last_synced_at": iso(utc_now()), "deleted_at": None,
        }
        existing = getattr(service_supabase.table("calendar_events").select("id,version").eq("tenant_id", context.tenant_id).eq("source_type", "ics").eq("source_id", source_id).limit(1).execute(), "data", None) or []
        saved_event = None
        if existing:
            row["version"] = int(existing[0].get("version") or 1) + 1
            saved_rows = getattr(service_supabase.table("calendar_events").update(row).eq("id", existing[0]["id"]).execute(), "data", None) or []
            saved_event = saved_rows[0] if saved_rows else {"id": existing[0]["id"]}
            updated += 1
        else:
            saved_rows = getattr(service_supabase.table("calendar_events").insert(row).execute(), "data", None) or []
            saved_event = saved_rows[0] if saved_rows else None
            imported += 1
        organizer = str(item.get("ORGANIZER") or "").split(":")[-1].removeprefix("mailto:").strip().lower()
        reasons = invitation_risk_reasons(organizer, row["title"], row["description"]) if organizer else []
        if saved_event and organizer and reasons:
            service_supabase.table("calendar_invitation_reviews").upsert({
                "tenant_id": context.tenant_id, "event_id": saved_event["id"], "sender_email": organizer,
                "trust_level": "suspicious", "reasons": reasons, "disposition": "quarantined",
            }, on_conflict="tenant_id,event_id,sender_email").execute()
    record_calendar_audit(context, request, "calendar.ics_imported", "calendar", calendar_id, {"imported": imported, "updated": updated, "skipped": skipped})
    return {"success": True, "imported": imported, "updated": updated, "skipped": skipped}


@router.get("/export.ics", response_class=PlainTextResponse)
def export_calendar(request: Request, response: Response, start: datetime, end: datetime, calendar_id: Optional[str] = None):
    require_calendar_feature()
    context = require_active_tenant_member(request, response)
    start, end = parse_range(start, end)
    query = service_supabase.table("calendar_events").select("*").eq("tenant_id", context.tenant_id).is_("deleted_at", "null").lt("starts_at", iso(end)).gt("ends_at", iso(start))
    if calendar_id:
        require_calendar_access(context, calendar_id, "import_export")
        query = query.eq("calendar_id", calendar_id)
    else:
        calendar_ids = [
            str(access.calendar.get("id")) for access in list_accessible_calendars(context)
            if access.allows("import_export") and access.allows("view_details")
        ]
        if not calendar_ids:
            raise HTTPException(status_code=403, detail="Calendar export access required")
        query = query.in_("calendar_id", calendar_ids)
    rows = getattr(query.order("starts_at").limit(5000).execute(), "data", None) or []
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Madar//Calendar//EN", "CALSCALE:GREGORIAN"]
    for row in rows:
        lines.extend(["BEGIN:VEVENT", f"UID:{row['id']}@madar", f"DTSTAMP:{ics_date(row.get('updated_at') or row.get('created_at'))}", f"DTSTART:{ics_date(row['starts_at'])}", f"DTEND:{ics_date(row['ends_at'])}", f"SUMMARY:{ics_escape(row['title'])}", f"DESCRIPTION:{ics_escape(row.get('description'))}", f"LOCATION:{ics_escape(row.get('location'))}"])
        if row.get("recurrence_rule"):
            lines.append(f"RRULE:{row['recurrence_rule']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return PlainTextResponse("\r\n".join(lines) + "\r\n", media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=madar-calendar.ics"})
