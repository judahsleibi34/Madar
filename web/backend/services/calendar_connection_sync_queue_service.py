from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from database import service_supabase
from services.calendar_sync_service import CalendarSyncError, sync_connection


TRANSIENT_CONNECTION_CODES = {
    "provider_connect_timeout",
    "provider_read_timeout",
    "provider_transport_error",
    "provider_rate_limited",
    "provider_unavailable",
    "google_sync_failed",
    "microsoft_sync_failed",
    "sync_time_budget_exceeded",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def enqueue_connection_sync(
    *,
    tenant_id: int,
    connection_id: str,
    operation: str = "incremental",
    client=None,
) -> dict[str, Any]:
    database_client = client or service_supabase
    rows = _rows(
        database_client.rpc(
            "enqueue_calendar_connection_sync_job",
            {
                "p_tenant_id": int(tenant_id),
                "p_connection_id": connection_id,
                "p_operation": operation,
            },
        ).execute()
    )
    if not rows:
        raise CalendarSyncError(
            "connection_sync_enqueue_failed",
            "Calendar synchronization could not be queued.",
        )
    database_client.table("calendar_sync_connections").update(
        {"inbound_sync_status": "pending", "inbound_sync_error_code": None}
    ).eq("id", connection_id).eq("tenant_id", int(tenant_id)).execute()
    return rows[0]


def claim_connection_sync_jobs(
    *, worker_id: str, limit: int = 2, client=None
) -> list[dict[str, Any]]:
    database_client = client or service_supabase
    return _rows(
        database_client.rpc(
            "claim_calendar_connection_sync_jobs",
            {
                "p_worker_id": str(worker_id)[:120],
                "p_limit": max(1, min(int(limit), 10)),
                "p_now": _now().isoformat(),
            },
        ).execute()
    )


def finish_connection_sync_job(
    job_id: str,
    *,
    succeeded: bool,
    error_code: str | None = None,
    result_counts: dict[str, int] | None = None,
    retry_after_seconds: int | None = None,
    client=None,
) -> dict[str, Any] | None:
    database_client = client or service_supabase
    next_attempt = (
        _now() + timedelta(seconds=max(1, min(int(retry_after_seconds), 3600)))
        if retry_after_seconds is not None
        else None
    )
    rows = _rows(
        database_client.rpc(
            "finish_calendar_connection_sync_job",
            {
                "p_job_id": job_id,
                "p_succeeded": bool(succeeded),
                "p_error_code": str(error_code or "")[:100] or None,
                "p_result_counts": result_counts or {},
                "p_next_attempt_at": next_attempt.isoformat()
                if next_attempt
                else None,
                "p_finished_at": _now().isoformat(),
            },
        ).execute()
    )
    return rows[0] if rows else None


def eligible_inbound_connections(
    *, interval_seconds: int, limit: int = 20, client=None
) -> list[dict[str, Any]]:
    database_client = client or service_supabase
    cutoff = (_now() - timedelta(seconds=max(60, interval_seconds))).isoformat()
    query = (
        database_client.table("calendar_sync_connections")
        .select(
            "id,tenant_id,last_inbound_success_at,last_attempt_at,"
            "inbound_sync_status"
        )
        .in_("provider", ["google", "microsoft"])
        .in_("status", ["connected", "degraded"])
        .in_("inbound_sync_status", ["idle", "synced"])
        .eq("inbound_sync_enabled", True)
        .not_.is_("encrypted_credentials", "null")
        .or_(
            "last_inbound_success_at.is.null,"
            f"last_inbound_success_at.lt.{cutoff}"
        )
        .order("last_inbound_success_at")
        .limit(max(1, min(int(limit), 100)))
    )
    return _rows(query.execute())


def process_connection_sync_job(
    job: dict[str, Any], *, http_client=None
) -> dict[str, int]:
    rows = _rows(
        service_supabase.table("calendar_sync_connections")
        .select("*")
        .eq("id", job["connection_id"])
        .eq("tenant_id", job["tenant_id"])
        .eq("inbound_sync_enabled", True)
        .limit(1)
        .execute()
    )
    if not rows:
        raise CalendarSyncError(
            "connection_sync_disabled",
            "Inbound calendar synchronization is disabled.",
        )
    connection = rows[0]
    if job.get("operation") == "full":
        connection = {**connection, "cursor_data": {}}
        service_supabase.table("calendar_sync_connections").update(
            {"inbound_sync_status": "full_resync_required"}
        ).eq("id", connection["id"]).eq(
            "tenant_id", connection["tenant_id"]
        ).execute()
    else:
        service_supabase.table("calendar_sync_connections").update(
            {"inbound_sync_status": "syncing", "inbound_sync_error_code": None}
        ).eq("id", connection["id"]).eq(
            "tenant_id", connection["tenant_id"]
        ).execute()
    try:
        counts = sync_connection(connection, http_client=http_client)
    except httpx.ConnectTimeout as error:
        raise CalendarSyncError(
            "provider_connect_timeout", "Calendar provider timed out."
        ) from error
    except (
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
    ) as error:
        raise CalendarSyncError(
            "provider_read_timeout", "Calendar provider timed out."
        ) from error
    except httpx.TransportError as error:
        raise CalendarSyncError(
            "provider_transport_error", "Calendar provider is unavailable."
        ) from error
    service_supabase.table("calendar_sync_connections").update(
        {
            "inbound_sync_status": "synced",
            "last_inbound_success_at": _now().isoformat(),
            "inbound_sync_error_code": None,
        }
    ).eq("id", connection["id"]).eq(
        "tenant_id", connection["tenant_id"]
    ).execute()
    return {key: int(value) for key, value in counts.items()}


def mark_connection_sync_failed(
    job: dict[str, Any], error_code: str, *, terminal: bool
) -> None:
    service_supabase.table("calendar_sync_connections").update(
        {
            "inbound_sync_status": "failed" if terminal else "pending",
            "inbound_sync_error_code": str(error_code)[:100],
        }
    ).eq("id", job["connection_id"]).eq(
        "tenant_id", job["tenant_id"]
    ).execute()


def get_connection_sync_queue_metrics(*, client=None) -> dict[str, int]:
    database_client = client or service_supabase
    rows = _rows(
        database_client.table("calendar_connection_sync_jobs")
        .select("status")
        .in_("status", ["pending", "processing", "failed"])
        .limit(5000)
        .execute()
    )
    counts = {
        status: sum(row.get("status") == status for row in rows)
        for status in ("pending", "processing", "failed")
    }
    return {
        "queue_depth": counts["pending"] + counts["processing"],
        **counts,
    }
