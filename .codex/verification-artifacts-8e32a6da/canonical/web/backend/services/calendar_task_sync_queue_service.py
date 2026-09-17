from __future__ import annotations

import hashlib
import hmac
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from database import service_supabase
from services.calendar_sync_service import (
    CalendarSyncError,
    _outbound_payload,
    _refresh,
    decrypt_credentials,
    encrypt_credentials,
)


logger = logging.getLogger(__name__)
ACTIVE_STATUSES = {"pending", "processing"}
TRANSIENT_CODES = {
    "provider_connect_timeout",
    "provider_read_timeout",
    "provider_transport_error",
    "provider_rate_limited",
    "provider_unavailable",
}
PROVIDER_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def enqueue_task_sync(
    *,
    tenant_id: int,
    task_id: str,
    connection_id: str,
    operation: str,
    task_version: int,
    client=None,
) -> dict[str, Any]:
    database_client = client or service_supabase
    response = database_client.rpc(
        "enqueue_calendar_task_sync_job",
        {
            "p_tenant_id": int(tenant_id),
            "p_task_id": task_id,
            "p_connection_id": connection_id,
            "p_operation": operation,
            "p_task_version": max(1, int(task_version)),
        },
    ).execute()
    rows = _rows(response)
    if not rows:
        raise CalendarSyncError(
            "task_sync_enqueue_failed",
            "Google synchronization could not be queued.",
        )
    return rows[0]


def claim_task_sync_jobs(
    *, worker_id: str, limit: int = 10, client=None
) -> list[dict[str, Any]]:
    database_client = client or service_supabase
    return _rows(
        database_client.rpc(
            "claim_calendar_task_sync_jobs",
            {
                "p_worker_id": str(worker_id)[:120],
                "p_limit": max(1, min(int(limit), 50)),
                "p_now": _now().isoformat(),
            },
        ).execute()
    )


def finish_task_sync_job(
    job_id: str,
    *,
    status: str,
    error_code: str | None = None,
    retry_after_seconds: int | None = None,
    client=None,
) -> dict[str, Any] | None:
    database_client = client or service_supabase
    retry_at = (
        _now() + timedelta(seconds=max(1, min(int(retry_after_seconds), 3600)))
        if retry_after_seconds is not None
        else None
    )
    rows = _rows(
        database_client.rpc(
            "finish_calendar_task_sync_job",
            {
                "p_job_id": job_id,
                "p_status": status,
                "p_error_code": str(error_code or "")[:100] or None,
                "p_next_attempt_at": retry_at.isoformat() if retry_at else None,
                "p_finished_at": _now().isoformat(),
            },
        ).execute()
    )
    return rows[0] if rows else None


def complete_task_sync_delete(job_id: str, *, client=None) -> dict[str, Any] | None:
    database_client = client or service_supabase
    rows = _rows(
        database_client.rpc(
            "complete_calendar_task_sync_delete",
            {"p_job_id": job_id, "p_finished_at": _now().isoformat()},
        ).execute()
    )
    return rows[0] if rows else None


def retry_delay(attempt: int, *, retry_after: int | None = None) -> int:
    if retry_after is not None:
        return max(1, min(int(retry_after), 900))
    base = min(30 * (2 ** max(0, int(attempt) - 1)), 900)
    return min(900, base + random.randint(0, max(1, base // 5)))


def _marker(task: dict[str, Any], connection: dict[str, Any]) -> str:
    secret = os.getenv("CALENDAR_CREDENTIALS_SECRET", "").encode()
    if len(secret) < 24:
        raise CalendarSyncError(
            "calendar_secret_missing",
            "Calendar credential encryption is not configured.",
        )
    material = (
        f"{connection['tenant_id']}:{connection['id']}:{task['id']}".encode()
    )
    return hmac.new(secret, material, hashlib.sha256).hexdigest()


def _provider_error(response: httpx.Response) -> CalendarSyncError:
    status = int(response.status_code)
    if status == 429:
        return CalendarSyncError("provider_rate_limited", "Calendar provider is busy.")
    if status in {500, 502, 503, 504}:
        return CalendarSyncError("provider_unavailable", "Calendar provider is unavailable.")
    if status in {401, 403}:
        return CalendarSyncError(
            "provider_authorization_failed",
            "Reconnect the calendar account before synchronizing.",
        )
    return CalendarSyncError("provider_write_failed", "Calendar provider rejected the change.")


def _request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    try:
        return client.request(method, url, **kwargs)
    except httpx.ConnectTimeout as error:
        raise CalendarSyncError("provider_connect_timeout", "Calendar provider timed out.") from error
    except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as error:
        raise CalendarSyncError("provider_read_timeout", "Calendar provider timed out.") from error
    except httpx.TransportError as error:
        raise CalendarSyncError("provider_transport_error", "Calendar provider is unavailable.") from error


def _load_job_state(job: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    tenant_id = int(job["tenant_id"])
    tasks = _rows(
        service_supabase.table("calendar_tasks")
        .select("*")
        .eq("id", job["task_id"])
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    connections = _rows(
        service_supabase.table("calendar_sync_connections")
        .select("*")
        .eq("id", job["connection_id"])
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    if not tasks or not connections:
        raise CalendarSyncError("sync_binding_missing", "Synchronization binding no longer exists.")
    task, connection = tasks[0], connections[0]
    if (
        str(task.get("sync_connection_id") or "") != str(connection["id"])
        or str(connection.get("provider") or "") != "google"
        or str(connection.get("direction") or "") != "two_way"
        or str(connection.get("status") or "") not in {"connected", "degraded"}
        or not connection.get("encrypted_credentials")
    ):
        raise CalendarSyncError("sync_binding_invalid", "Synchronization binding is no longer valid.")
    if int(task.get("version") or 1) > int(job.get("task_version") or 1):
        raise CalendarSyncError("sync_job_superseded", "A newer task version is queued.")
    events = []
    if task.get("sync_event_id"):
        events = _rows(
            service_supabase.table("calendar_events")
            .select("*")
            .eq("id", task["sync_event_id"])
            .eq("tenant_id", tenant_id)
            .eq("calendar_id", connection["local_calendar_id"])
            .limit(1)
            .execute()
        )
    if not events:
        raise CalendarSyncError("sync_event_missing", "The synchronized event no longer exists.")
    return task, connection, events[0]


def _credentials(connection: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    credentials = _refresh(
        "google", decrypt_credentials(connection["encrypted_credentials"]), client
    )
    service_supabase.table("calendar_sync_connections").update(
        {"encrypted_credentials": encrypt_credentials(credentials)}
    ).eq("id", connection["id"]).eq("tenant_id", connection["tenant_id"]).execute()
    return credentials


def _lookup_marker(
    client: httpx.Client,
    headers: dict[str, str],
    marker: str,
    collection_url: str,
) -> list[dict[str, Any]]:
    response = _request(
        client,
        "GET",
        collection_url,
        headers=headers,
        params={
            "privateExtendedProperty": f"madarTaskSync={marker}",
            "maxResults": 10,
            "singleEvents": "false",
            "showDeleted": "false",
        },
    )
    if response.status_code >= 400:
        raise _provider_error(response)
    return [
        item
        for item in ((response.json() or {}).get("items") or [])
        if isinstance(item, dict) and item.get("status") != "cancelled"
    ]


def process_task_sync_job(
    job: dict[str, Any], *, http_client: httpx.Client | None = None
) -> str:
    task, connection, event = _load_job_state(job)
    client = http_client or httpx.Client(timeout=PROVIDER_TIMEOUT)
    credentials = _credentials(connection, client)
    headers = {
        "Authorization": f"Bearer {credentials['access_token']}",
        "Content-Type": "application/json",
    }
    marker = _marker(task, connection)
    source_prefix = f"{connection['id']}:"
    source_id = str(event.get("source_id") or "")
    remote_id = (
        source_id[len(source_prefix):]
        if str(event.get("source_type") or "") == "google"
        and source_id.startswith(source_prefix)
        else ""
    )
    provider_calendar_id = quote(
        str(connection.get("provider_calendar_id") or "primary"), safe=""
    )
    collection = (
        "https://www.googleapis.com/calendar/v3/calendars/"
        f"{provider_calendar_id}/events"
    )

    if job.get("operation") == "delete":
        if remote_id:
            response = _request(
                client,
                "DELETE",
                f"{collection}/{quote(remote_id, safe='')}",
                headers=headers,
            )
            if response.status_code not in {204, 404, 410}:
                raise _provider_error(response)
        service_supabase.table("calendar_events").update(
            {
                "deleted_at": _now().isoformat(),
                "version": int(event.get("version") or 1) + 1,
            }
        ).eq("id", event["id"]).eq("tenant_id", connection["tenant_id"]).execute()
        return "provider_deleted"

    matches = (
        []
        if remote_id
        else _lookup_marker(client, headers, marker, collection)
    )
    if len(matches) > 1:
        service_supabase.table("calendar_tasks").update(
            {
                "sync_status": "reconciliation_required",
                "sync_error_code": "multiple_provider_matches",
            }
        ).eq("id", task["id"]).eq("tenant_id", connection["tenant_id"]).execute()
        return "reconciliation_required"
    if len(matches) == 1:
        remote_id = str(matches[0].get("id") or "")

    payload = _outbound_payload(event, "google")
    payload["extendedProperties"] = {"private": {"madarTaskSync": marker}}
    if remote_id:
        response = _request(
            client,
            "PATCH",
            f"{collection}/{quote(remote_id, safe='')}",
            headers=headers,
            json=payload,
        )
        if response.status_code == 404:
            remote_id = ""
        elif response.status_code >= 400:
            raise _provider_error(response)
    if not remote_id:
        response = _request(client, "POST", collection, headers=headers, json=payload)
        if response.status_code >= 400:
            raise _provider_error(response)
    remote = response.json()
    saved_remote_id = str(remote.get("id") or remote_id)
    if not saved_remote_id:
        raise CalendarSyncError("provider_response_invalid", "Calendar provider response was invalid.")
    now = _now().isoformat()
    service_supabase.table("calendar_events").update(
        {
            "source_type": "google",
            "source_id": f"{connection['id']}:{saved_remote_id}",
            "external_etag": str(remote.get("etag") or ""),
            "last_synced_at": now,
        }
    ).eq("id", event["id"]).eq("tenant_id", connection["tenant_id"]).execute()
    service_supabase.table("calendar_tasks").update(
        {"sync_status": "synced", "sync_error_code": None}
    ).eq("id", task["id"]).eq("tenant_id", connection["tenant_id"]).execute()
    return "succeeded"


def get_task_sync_queue_metrics(*, client=None) -> dict[str, int]:
    database_client = client or service_supabase
    rows = _rows(
        database_client.table("calendar_task_sync_jobs")
        .select("status")
        .in_(
            "status",
            ["pending", "processing", "failed", "reconciliation_required"],
        )
        .limit(5000)
        .execute()
    )
    counts = {
        status: sum(row.get("status") == status for row in rows)
        for status in ("pending", "processing", "failed", "reconciliation_required")
    }
    return {"queue_depth": counts["pending"] + counts["processing"], **counts}
