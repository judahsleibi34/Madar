"""Private, provider-neutral report delivery and retention for candidate schema 166."""
from __future__ import annotations
from services.account_work_fence import scoped_work

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from fastapi import HTTPException

from database import service_supabase
from services import bi_sharing_service, project_dataset_service
from services.upload_config import get_private_charts_dir


DELIVERY_SCHEMA = 166
MAX_RECIPIENTS = 25
MAX_ATTACHMENT_BYTES = 1024 * 1024
MAX_CLEANUP_FILES = 20
MAX_CLEANUP_BYTES = 128 * 1024 * 1024
EMAIL_PATTERN = re.compile(r"^[^\s@\x00-\x1f\x7f]+@[^\s@\x00-\x1f\x7f]+\.[^\s@\x00-\x1f\x7f]+$")


class ReportDeliveryError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class EmailDelivery:
    recipient: str
    subject: str
    filename: str
    content_type: str
    attachment: bytes
    report_id: str


class EmailDeliveryAdapter(Protocol):
    def deliver(self, message: EmailDelivery) -> str: ...


@dataclass
class OfflineTestEmailAdapter:
    """In-memory adapter for tests; performs no DNS, socket, or filesystem writes."""
    delivered: list[dict[str, Any]] = field(default_factory=list)
    failure_code: str | None = None

    def deliver(self, message: EmailDelivery) -> str:
        if self.failure_code:
            raise ReportDeliveryError(self.failure_code, retryable=True)
        provider_id = "offline-" + hashlib.sha256(
            f"{message.report_id}:{message.recipient}".encode("utf-8")
        ).hexdigest()[:24]
        self.delivered.append({
            "recipient": message.recipient,
            "subject": message.subject,
            "filename": message.filename,
            "content_type": message.content_type,
            "size_bytes": len(message.attachment),
            "sha256": hashlib.sha256(message.attachment).hexdigest(),
            "report_id": message.report_id,
            "provider_message_id": provider_id,
        })
        return provider_id


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def _first(response) -> dict[str, Any]:
    rows = _rows(response)
    if not rows:
        raise RuntimeError("Report lifecycle operation returned no result")
    return rows[0]


def delivery_available(*, client=None) -> bool:
    return project_dataset_service.schema_version(client=client) >= DELIVERY_SCHEMA


def require_delivery_schema(*, client=None) -> None:
    if not delivery_available(client=client):
        raise HTTPException(status_code=503, detail={
            "code": "bi_report_delivery_upgrade_required",
            "message": "Report delivery and retention require the database upgrade.",
        })


def _safe_email(value: object) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ReportDeliveryError("recipient_email_invalid", retryable=False)
    return email


def _schedule(*, tenant_id: int, project_id: str, user_id: int, schedule_id: str, client) -> dict:
    rows = _rows(client.table("bi_report_schedules").select("*")
        .eq("id", project_dataset_service._safe_uuid(schedule_id, detail="Report schedule was not found."))
        .eq("tenant_id", tenant_id).eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).limit(1).execute())
    if not rows:
        raise HTTPException(status_code=404, detail="Report schedule was not found.")
    return rows[0]


def _members(*, tenant_id: int, owner_user_id: int, client) -> list[dict[str, Any]]:
    memberships = _rows(client.table("tenant_memberships").select("user_id,role")
        .eq("tenant_id", tenant_id).eq("status", "active").neq("user_id", owner_user_id)
        .limit(101).execute())[:100]
    by_id = {int(row["user_id"]): row for row in memberships}
    if not by_id:
        return []
    users = _rows(client.table("users").select("id,first_name,last_name,email")
        .eq("account_status", "active").in_("id", list(by_id)).execute())
    return [{**user, "tenant_role": by_id[int(user["id"])].get("role")} for user in users]


def get_delivery_config(*, tenant_id: int, project_id: str, user_id: int,
                        schedule_id: str, client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    schedule = _schedule(tenant_id=tenant_id, project_id=project_id, user_id=user_id,
                         schedule_id=schedule_id, client=database)
    configs = _rows(database.table("bi_report_delivery_configs").select("*")
        .eq("schedule_id", schedule["id"]).eq("tenant_id", tenant_id)
        .eq("owner_user_id", user_id).limit(1).execute())
    recipients = _rows(database.table("bi_report_delivery_recipients").select("member_user_id")
        .eq("schedule_id", schedule["id"]).eq("tenant_id", tenant_id)
        .eq("owner_user_id", user_id).limit(MAX_RECIPIENTS).execute())
    return {"config": configs[0] if configs else {"schedule_id": schedule["id"], "enabled": False, "revision": 0},
            "recipient_user_ids": [int(row["member_user_id"]) for row in recipients],
            "members": _members(tenant_id=tenant_id, owner_user_id=user_id, client=database)}


def configure_delivery(*, tenant_id: int, project_id: str, user_id: int, schedule_id: str,
                       expected_schedule_revision: int, enabled: bool,
                       recipient_user_ids: list[int], client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    normalized = [int(value) for value in recipient_user_ids]
    if len(normalized) > MAX_RECIPIENTS or len(set(normalized)) != len(normalized):
        raise HTTPException(status_code=422, detail="Choose up to 25 distinct workspace members.")
    try:
        return _first(database.rpc("configure_bi_report_delivery166", {
            "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
            "p_owner_user_id": user_id, "p_schedule_id": project_dataset_service._safe_uuid(schedule_id),
            "p_expected_schedule_revision": expected_schedule_revision, "p_enabled": bool(enabled),
            "p_recipient_user_ids": normalized,
        }).execute())
    except Exception as error:
        message = str(error).lower()
        if "revision_conflict" in message or "40001" in message:
            raise HTTPException(status_code=409, detail="The report schedule changed. Reload and try again.") from error
        if "recipient_forbidden" in message:
            raise HTTPException(status_code=422, detail="Choose active members of this workspace.") from error
        raise


def get_lifecycle_settings(*, tenant_id: int, project_id: str, user_id: int, client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    rows = _rows(database.table("bi_report_lifecycle_settings").select("*")
        .eq("tenant_id", tenant_id).eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("owner_user_id", user_id).limit(1).execute())
    return rows[0] if rows else {"retention_days": 90, "cleanup_enabled": False, "revision": 0}


def configure_lifecycle(*, tenant_id: int, project_id: str, user_id: int,
                        expected_revision: int | None, retention_days: int,
                        cleanup_enabled: bool, client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    if not 7 <= int(retention_days) <= 365:
        raise HTTPException(status_code=422, detail="Report retention must be between 7 and 365 days.")
    try:
        return _first(database.rpc("configure_bi_report_lifecycle166", {
            "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
            "p_owner_user_id": user_id, "p_expected_revision": expected_revision,
            "p_retention_days": int(retention_days), "p_cleanup_enabled": bool(cleanup_enabled),
        }).execute())
    except Exception as error:
        if "revision_conflict" in str(error).lower() or "40001" in str(error):
            raise HTTPException(status_code=409, detail="Report retention settings changed. Reload and try again.") from error
        raise


def list_deliveries(*, tenant_id: int, project_id: str, user_id: int,
                    report_id: str, client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    bi_sharing_service.require_report_access(tenant_id=tenant_id, project_id=project_id,
        user_id=user_id, report_id=report_id, owner_only=True, client=database)
    rows = _rows(database.table("bi_report_deliveries")
        .select("id,recipient_user_id,channel,status,attempts,max_attempts,last_error_code,provider_message_id,sent_at,created_at,updated_at")
        .eq("report_id", project_dataset_service._safe_uuid(report_id)).eq("tenant_id", tenant_id)
        .eq("project_id", project_dataset_service._safe_uuid(project_id)).eq("owner_user_id", user_id)
        .order("created_at", desc=True).limit(MAX_RECIPIENTS).execute())
    members = _members(tenant_id=tenant_id, owner_user_id=user_id, client=database)
    by_id = {int(member["id"]): member for member in members}
    return {"items": [{**row, "recipient": by_id.get(int(row["recipient_user_id"]), {
        "id": row["recipient_user_id"], "email": "", "first_name": "", "last_name": "",
    })} for row in rows]}


def claim_deliveries(*, worker_id: str, limit: int = 10, lease_seconds: int = 300, client=None) -> list[dict[str, Any]]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    return _rows(database.rpc("claim_bi_report_deliveries166", {
        "p_worker_id": str(worker_id)[:160], "p_limit": max(1, min(int(limit), 25)),
        "p_lease_seconds": max(30, min(int(lease_seconds), 1800)),
        "p_now": datetime.now(timezone.utc).isoformat(),
    }).execute())


def _private_attachment(report: dict[str, Any]) -> tuple[bytes, str, str]:
    if report.get("artifact_deleted_at") or not report.get("artifact_storage_key"):
        raise ReportDeliveryError("report_artifact_unavailable", retryable=False)
    root = get_private_charts_dir().resolve()
    path = (root / str(report["artifact_storage_key"])).resolve()
    if root not in path.parents or not path.is_file():
        raise ReportDeliveryError("report_artifact_unavailable", retryable=False)
    size = path.stat().st_size
    if size <= 0 or size > MAX_ATTACHMENT_BYTES or size != int(report.get("artifact_size_bytes") or -1):
        raise ReportDeliveryError("report_artifact_integrity_failed", retryable=False)
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != report.get("artifact_sha256"):
        raise ReportDeliveryError("report_artifact_integrity_failed", retryable=False)
    return content, str(report.get("artifact_filename") or "report.csv"), str(report.get("artifact_content_type") or "text/csv")


def _cleanup_private_report(report: dict[str, Any]) -> tuple[int, str]:
    content, _filename, _content_type = _private_attachment(report)
    root = get_private_charts_dir().resolve()
    path = (root / str(report["artifact_storage_key"])).resolve()
    report_directory = path.parent
    candidates = list(report_directory.rglob("*"))
    files = [candidate for candidate in candidates if candidate.is_file()]
    if len(files) > MAX_CLEANUP_FILES or any(candidate.is_symlink() for candidate in candidates):
        raise ReportDeliveryError("report_cleanup_bounds_exceeded", retryable=False)
    resolved = [candidate.resolve() for candidate in files]
    if any(report_directory not in candidate.parents for candidate in resolved) \
            or sum(candidate.stat().st_size for candidate in resolved) > MAX_CLEANUP_BYTES:
        raise ReportDeliveryError("report_cleanup_bounds_exceeded", retryable=False)
    size, digest = len(content), hashlib.sha256(content).hexdigest()
    for candidate in resolved:
        candidate.unlink()
    for directory in sorted((candidate for candidate in candidates if candidate.is_dir()),
                            key=lambda value: len(value.parts), reverse=True):
        directory.rmdir()
    report_directory.rmdir()
    return size, digest


@scoped_work("row", "owner_user_id")
def process_delivery(row: dict[str, Any], *, adapter: EmailDeliveryAdapter, client=None) -> dict[str, Any]:
    database = client or service_supabase
    now = datetime.now(timezone.utc).isoformat()
    params = {"p_delivery_id": row["id"], "p_lease_token": row["lease_token"], "p_lease_fence": row["lease_fence"]}
    try:
        context = getattr(database.rpc("authorize_bi_report_delivery166", params).execute(), "data", None)
        if isinstance(context, list): context = context[0] if context else None
        if not isinstance(context, dict): raise ReportDeliveryError("report_delivery_access_revoked", retryable=False)
        recipient = _safe_email(context.get("recipient_email"))
        report = context.get("report") or {}
        content, filename, content_type = _private_attachment(report)
        provider_id = adapter.deliver(EmailDelivery(recipient=recipient, subject="Your Madar report",
            filename=filename, content_type=content_type, attachment=content, report_id=str(report["id"])))
        outcome, error_code = "sent", None
    except ReportDeliveryError as error:
        outcome = "retry" if error.retryable else "revoked" if error.code in {
            "report_delivery_access_revoked", "recipient_email_invalid",
        } else "failed"
        error_code, provider_id = error.code, None
    except Exception as error:
        message = str(error).lower()
        outcome = "revoked" if "access_revoked" in message or "recipient_unavailable" in message else "retry"
        error_code, provider_id = ("recipient_access_revoked" if outcome == "revoked" else "delivery_unexpected"), None
    result = _first(database.rpc("finish_bi_report_delivery166", {
        **params, "p_outcome": outcome, "p_error_code": error_code,
        "p_provider_message_id": provider_id, "p_now": now,
    }).execute())
    return {"id": row["id"], "status": result.get("status"), "error_code": result.get("last_error_code")}


def run_delivery_batch(*, worker_id: str, adapter: EmailDeliveryAdapter,
                       limit: int = 10, lease_seconds: int = 300, client=None) -> dict[str, Any]:
    if adapter is None:
        raise RuntimeError("A report delivery adapter must be explicitly provided")
    database = client or service_supabase
    rows = claim_deliveries(worker_id=worker_id, limit=limit, lease_seconds=lease_seconds, client=database)
    return {"claimed": len(rows), "results": [process_delivery(row, adapter=adapter, client=database) for row in rows]}


def claim_cleanup(*, worker_id: str, limit: int = 10, lease_seconds: int = 300, client=None) -> list[dict[str, Any]]:
    database = client or service_supabase
    require_delivery_schema(client=database)
    return _rows(database.rpc("claim_bi_report_cleanup166", {
        "p_worker_id": str(worker_id)[:160], "p_limit": max(1, min(int(limit), 25)),
        "p_lease_seconds": max(30, min(int(lease_seconds), 1800)),
        "p_now": datetime.now(timezone.utc).isoformat(),
    }).execute())


@scoped_work("row", "owner_user_id")
def process_cleanup(row: dict[str, Any], *, client=None) -> dict[str, Any]:
    database = client or service_supabase
    claim = {"p_job_id": row["id"], "p_lease_token": row["lease_token"],
             "p_lease_fence": row["lease_fence"]}
    context = getattr(database.rpc("authorize_bi_report_cleanup166", {
        **claim, "p_now": datetime.now(timezone.utc).isoformat(),
    }).execute(), "data", None)
    if isinstance(context, list):
        context = context[0] if context else None
    if not isinstance(context, dict) or not context.get("authorized"):
        return {"id": row["id"], "status": (context or {}).get("status", "cancelled"),
                "error_code": "cleanup_disabled"}
    report = context.get("report")
    success, error_code, size, digest = False, "report_artifact_unavailable", None, None
    if isinstance(report, dict):
        try:
            size, digest = _cleanup_private_report(report)
            success, error_code = True, None
        except ReportDeliveryError as error:
            error_code = error.code
        except Exception:
            error_code = "report_cleanup_unexpected"
    result = _first(database.rpc("finish_bi_report_cleanup166", {
        **claim,
        "p_success": success, "p_error_code": error_code, "p_deleted_size_bytes": size,
        "p_deleted_sha256": digest, "p_now": datetime.now(timezone.utc).isoformat(),
    }).execute())
    return {"id": row["id"], "status": result.get("status"), "error_code": result.get("last_error_code")}


def run_cleanup_batch(*, worker_id: str, limit: int = 10, lease_seconds: int = 300, client=None) -> dict[str, Any]:
    database = client or service_supabase
    rows = claim_cleanup(worker_id=worker_id, limit=limit, lease_seconds=lease_seconds, client=database)
    return {"claimed": len(rows), "results": [process_cleanup(row, client=database) for row in rows]}
