"""Durable, idempotent user and tenant deletion lifecycle."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import HTTPException

from database import service_supabase
from services.api_errors import error_detail
from services.builder_asset_storage import BUILDER_ASSET_BUCKET
from services.calendar_sync_service import (
    CalendarSyncError,
    disconnect_connection_for_deletion,
)
from services.upload_config import (
    assert_path_within_root,
    get_data_upload_dir,
    get_private_charts_dir,
)


logger = logging.getLogger(__name__)
SAFE_CODE = re.compile(r"^[a-z0-9_.-]{1,100}$")
TERMINAL_REQUEST_STATES = {
    "completed",
    "completed_with_retained_records",
    "failed_manual_intervention",
    "cancelled_before_execution",
}
PROVIDER_RESOURCE_BUCKETS = {
    "supabase_avatar": "avatars",
    "supabase_builder_asset": BUILDER_ASSET_BUCKET,
}
HOST_RESOURCE_ROOTS = {
    "host_dataset": get_data_upload_dir,
    "host_generated_artifact": get_private_charts_dir,
}
RETAINED_CLASSES = {
    "user": ["security_audit_metadata", "deletion_workflow_evidence"],
    "tenant": [
        "security_audit_metadata",
        "billing_webhook_replay_metadata",
        "deletion_workflow_evidence",
    ],
}


class DeletionStepError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = True):
        super().__init__(code)
        self.code = safe_code(code)
        self.retryable = retryable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_code(value: Any, fallback: str = "deletion_failed") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if SAFE_CODE.fullmatch(normalized) else fallback


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def _one(response: Any) -> dict[str, Any] | None:
    values = _rows(response)
    return values[0] if values else None


def _provider_absent(error: Exception) -> bool:
    status = int(getattr(error, "status", 0) or getattr(error, "status_code", 0) or 0)
    text = str(error).lower()
    return status in {404, 410} or any(token in text for token in ("not found", "already deleted", "user_not_found"))


def _rpc_error(error: Exception) -> HTTPException:
    text = str(error).lower()
    mappings = {
        "deletion_target_not_found": (404, "deletion_target_not_found", "Deletion target was not found."),
        "tenant_owner_requires_tenant_deletion": (409, "tenant_owner_requires_tenant_deletion", "Transfer ownership or request tenant deletion."),
        "admin_deletion_requires_break_glass": (409, "admin_deletion_requires_break_glass", "Administrator deletion requires the break-glass procedure."),
        "last_system_admin_required": (409, "last_system_admin_required", "At least one active system administrator is required."),
        "duplicate": (409, "deletion_already_requested", "An active deletion request already exists."),
    }
    for marker, (status, code, message) in mappings.items():
        if marker in text:
            return HTTPException(status_code=status, detail=error_detail(code, message))
    return HTTPException(status_code=503, detail=error_detail("deletion_request_unavailable", "Deletion could not be scheduled safely."))


def create_deletion_request(
    *, request_type: str, target_user_id: int | None, target_tenant_id: int | None,
    requested_by_user_id: int, retention_until: str | None = None, client=None,
) -> dict[str, Any]:
    database_client = client or service_supabase
    try:
        response = database_client.rpc("create_data_deletion_request", {
            "p_request_type": request_type,
            "p_target_user_id": target_user_id,
            "p_target_tenant_id": target_tenant_id,
            "p_requested_by_user_id": int(requested_by_user_id),
            "p_retention_until": retention_until,
        }).execute()
    except Exception as error:
        raise _rpc_error(error) from error
    row = _one(response)
    if not row:
        raise HTTPException(status_code=503, detail=error_detail("deletion_request_unavailable", "Deletion could not be scheduled safely."))
    logger.info("deletion.request_created", extra={"status_code": 202})
    return public_request_status(row, include_target=True)


def request_user_deletion(*, target_user_id: int, requested_by_user_id: int, client=None) -> dict[str, Any]:
    return create_deletion_request(
        request_type="user", target_user_id=target_user_id, target_tenant_id=None,
        requested_by_user_id=requested_by_user_id, client=client,
    )


def request_tenant_deletion(*, target_tenant_id: int, requested_by_user_id: int, client=None) -> dict[str, Any]:
    return create_deletion_request(
        request_type="tenant", target_user_id=None, target_tenant_id=target_tenant_id,
        requested_by_user_id=requested_by_user_id, client=client,
    )


def public_request_status(row: dict[str, Any], *, include_target: bool = False) -> dict[str, Any]:
    result = {
        "request_id": row.get("id"),
        "request_type": row.get("request_type"),
        "state": row.get("state"),
        "phase": row.get("current_phase"),
        "attempt_count": int(row.get("attempt_count") or 0),
        "retry_after": row.get("retry_after"),
        "last_error_code": safe_code(row.get("last_error_code"), "") or None,
        "verification_status": row.get("verification_status"),
        "retained_classes": row.get("retained_classes") or [],
        "completion_report": row.get("completion_report") or {},
        "created_at": row.get("created_at"),
        "completed_at": row.get("completed_at"),
    }
    if include_target:
        result["target_user_id"] = row.get("target_user_id_snapshot")
        result["target_tenant_id"] = row.get("target_tenant_id_snapshot")
    return result


def get_deletion_request(request_id: str, *, client=None) -> dict[str, Any] | None:
    response = (client or service_supabase).table("data_deletion_requests").select("*").eq("id", request_id).limit(1).execute()
    return _one(response)


def list_deletion_requests(*, limit: int = 100, client=None) -> list[dict[str, Any]]:
    response = (client or service_supabase).table("data_deletion_requests").select("*").order("created_at", desc=True).limit(max(1, min(int(limit), 500))).execute()
    return [public_request_status(row, include_target=True) for row in _rows(response)]


def cancel_deletion_request(request_id: str, *, client=None) -> dict[str, Any]:
    """Cancel only before any external/destructive phase has completed."""
    database_client = client or service_supabase
    request = get_deletion_request(request_id, client=database_client)
    if not request:
        raise HTTPException(status_code=404, detail="Deletion request was not found")
    if request.get("state") not in {"pending", "waiting_retention"}:
        raise HTTPException(status_code=409, detail=error_detail("deletion_cannot_be_cancelled", "Deletion has already started."))
    progressed = _rows(
        database_client.table("data_deletion_steps").select("id")
        .eq("request_id", request_id).eq("state", "completed").execute()
    )
    if progressed:
        raise HTTPException(status_code=409, detail=error_detail("deletion_cannot_be_cancelled", "Deletion has already started."))
    snapshot = request.get("freeze_snapshot") if isinstance(request.get("freeze_snapshot"), dict) else {}
    if request["request_type"] == "user" and request.get("target_user_id") is not None:
        original = str(snapshot.get("account_status") or "active")
        if original not in {"pending_verification", "active", "disabled", "expired_pending"}:
            original = "disabled"
        database_client.table("users").update({"account_status": original}).eq("id", request["target_user_id"]).execute()
    elif request["request_type"] == "tenant" and request.get("target_tenant_id") is not None:
        database_client.table("tenants").update({"lifecycle_state": "active", "deletion_requested_at": None}).eq("tenant_id", request["target_tenant_id"]).execute()
        for subject in _subjects(request_id, client=database_client):
            original = str(subject.get("account_status_snapshot") or "active")
            if original not in {"pending_verification", "active", "disabled", "expired_pending"}:
                original = "disabled"
            database_client.table("users").update({"account_status": original}).eq("id", subject["user_id_snapshot"]).eq("account_status", "deletion_pending").execute()
    response = database_client.table("data_deletion_requests").update({
        "state": "cancelled_before_execution", "cancellation_requested_at": utc_now().isoformat(),
        "lease_owner": None, "lease_until": None,
    }).eq("id", request_id).execute()
    return public_request_status(_one(response) or {**request, "state": "cancelled_before_execution"}, include_target=True)


def claim_deletion_requests(*, worker_id: str, limit: int = 5, lease_seconds: int = 300, client=None) -> list[dict[str, Any]]:
    response = (client or service_supabase).rpc("claim_data_deletion_requests", {
        "p_worker_id": str(worker_id)[:120], "p_limit": max(1, min(int(limit), 25)),
        "p_now": utc_now().isoformat(), "p_lease_seconds": max(30, min(int(lease_seconds), 3600)),
    }).execute()
    return _rows(response)


def _next_step(request_id: str, *, client) -> dict[str, Any] | None:
    response = client.table("data_deletion_steps").select("*").eq("request_id", request_id).in_(
        "state", ["pending", "processing", "waiting_retry"]
    ).order("step_order").limit(1).execute()
    return _one(response)


def _mark_step_processing(step: dict[str, Any], *, client) -> dict[str, Any]:
    response = client.table("data_deletion_steps").update({
        "state": "processing", "attempts": int(step.get("attempts") or 0) + 1,
        "started_at": step.get("started_at") or utc_now().isoformat(), "last_error_code": None,
    }).eq("id", step["id"]).eq("request_id", step["request_id"]).execute()
    return _one(response) or {**step, "state": "processing", "attempts": int(step.get("attempts") or 0) + 1}


def _finish_step(step: dict[str, Any], output: dict[str, Any], *, client) -> None:
    client.table("data_deletion_steps").update({
        "state": "completed", "completed_at": utc_now().isoformat(),
        "last_error_code": None, "output_safe": output,
    }).eq("id", step["id"]).eq("request_id", step["request_id"]).execute()


def _fail_step(request: dict[str, Any], step: dict[str, Any], error: DeletionStepError, *, client) -> None:
    attempts = int(step.get("attempts") or 0)
    exhausted = not error.retryable or attempts >= int(step.get("max_attempts") or 1)
    step_state = "manual_intervention" if exhausted else "waiting_retry"
    client.table("data_deletion_steps").update({"state": step_state, "last_error_code": error.code}).eq("id", step["id"]).execute()
    if exhausted:
        request_state = "failed_manual_intervention"
        retry_after = None
    else:
        request_state = "waiting_retry"
        retry_after = (utc_now() + timedelta(seconds=min(3600, 30 * (2 ** min(attempts - 1, 7))))).isoformat()
    client.table("data_deletion_requests").update({
        "state": request_state, "current_phase": step["step_key"],
        "last_error_code": error.code, "retry_after": retry_after,
        "lease_owner": None, "lease_until": None,
    }).eq("id", request["id"]).execute()
    if exhausted:
        invoke_alert("deletion_manual_intervention", error.code)


def invoke_alert(event: str, detail: str) -> None:
    hook = os.getenv("MADAR_ALERT_HOOK", "/scripts/madar_alert_hook.sh").strip()
    path = Path(hook)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        logger.error("deletion.alert_hook_unavailable", extra={"error_code": safe_code(event)})
        return
    try:
        subprocess.run([str(path), safe_code(event), safe_code(detail)], check=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        logger.error("deletion.alert_hook_failed", extra={"error_type": type(error).__name__})


def _subjects(request_id: str, *, client) -> list[dict[str, Any]]:
    return _rows(client.table("data_deletion_subjects").select("*").eq("request_id", request_id).execute())


def _resources(request_id: str, kinds: list[str], *, client) -> list[dict[str, Any]]:
    return _rows(client.table("data_deletion_resources").select("*").eq("request_id", request_id).in_("resource_kind", kinds).in_("state", ["pending", "manual_intervention"]).limit(10000).execute())


def _step_freeze(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    if request["request_type"] == "user":
        target = _one(client.table("users").select("id,account_status").eq("id", request["target_user_id_snapshot"]).limit(1).execute())
        if target and target.get("account_status") != "deletion_pending":
            client.table("users").update({"account_status": "deletion_pending"}).eq("id", target["id"]).execute()
    else:
        target = _one(client.table("tenants").select("tenant_id,lifecycle_state").eq("tenant_id", request["target_tenant_id_snapshot"]).limit(1).execute())
        if target and target.get("lifecycle_state") != "deletion_pending":
            client.table("tenants").update({"lifecycle_state": "deletion_pending", "deletion_requested_at": utc_now().isoformat()}).eq("tenant_id", target["tenant_id"]).execute()
    return {"frozen": True}


def _step_revoke_sessions(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    # The local account/tenant freeze is checked on every authenticated request,
    # invalidating privileges immediately. Provider identities are removed late.
    return {"local_session_authority_revoked": True, "provider_identity_deletion_phase": "delete_auth_identities"}


def _step_revoke_integrations(request: dict[str, Any], *, client, http_client=None, **_kwargs) -> dict[str, Any]:
    query = client.table("calendar_sync_connections").select("*")
    if request["request_type"] == "tenant":
        query = query.eq("tenant_id", request["target_tenant_id_snapshot"])
    else:
        query = query.eq("user_id", request["target_user_id_snapshot"])
    connections = _rows(query.limit(10000).execute())
    revoked = 0
    local_only = 0
    for connection in connections:
        try:
            outcome = disconnect_connection_for_deletion(connection, http_client=http_client, client=client)
        except (CalendarSyncError, httpx.HTTPError) as error:
            raise DeletionStepError(safe_code(getattr(error, "code", None), "integration_provider_unavailable")) from error
        if outcome == "provider_revoked":
            revoked += 1
        else:
            local_only += 1
    return {"connections": len(connections), "provider_revoked": revoked, "local_credentials_removed": len(connections), "provider_revocation_unsupported": local_only}


def _step_stop_queued_work(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    tenant_id = request.get("target_tenant_id_snapshot")
    user_id = request.get("target_user_id_snapshot")
    filters = [("tenant_id", tenant_id)] if request["request_type"] == "tenant" else [("user_id", user_id)]
    touched = 0
    for table, states, payload in (
        ("notification_outbox", ["pending", "processing", "failed"], {"status": "dead", "last_error_code": "deletion_pending"}),
        ("notification_deliveries", ["pending", "processing"], {"status": "dead", "last_error_code": "deletion_pending", "dead_at": utc_now().isoformat()}),
    ):
        query = client.table(table).update(payload).in_("status", states)
        for key, value in filters:
            query = query.eq(key, value)
        touched += len(_rows(query.execute()))
    now = utc_now().isoformat()
    for table in ("calendar_task_sync_jobs", "calendar_connection_sync_jobs"):
        query = client.table(table).update({
            "status": "failed", "last_error_code": "deletion_pending", "completed_at": now,
        }).in_("status", ["pending", "processing"])
        if request["request_type"] == "tenant":
            query = query.eq("tenant_id", tenant_id)
        else:
            connection_ids = [
                row["id"] for row in _rows(
                    client.table("calendar_sync_connections").select("id")
                    .eq("user_id", user_id).limit(10000).execute()
                ) if row.get("id") is not None
            ]
            if not connection_ids:
                continue
            query = query.in_("connection_id", connection_ids)
        touched += len(_rows(query.execute()))
    return {"queued_records_stopped": touched}


def _step_delete_provider_objects(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    resources = _resources(request["id"], list(PROVIDER_RESOURCE_BUCKETS), client=client)
    deleted = 0
    absent = 0
    for resource in resources:
        try:
            client.storage.from_(PROVIDER_RESOURCE_BUCKETS[resource["resource_kind"]]).remove([resource["resource_key"]])
            state = "deleted"
            deleted += 1
        except Exception as error:
            if _provider_absent(error):
                state = "absent"
                absent += 1
            else:
                client.table("data_deletion_resources").update({"attempts": int(resource.get("attempts") or 0) + 1, "last_error_code": "storage_provider_unavailable"}).eq("id", resource["id"]).execute()
                raise DeletionStepError("storage_provider_unavailable") from error
        client.table("data_deletion_resources").update({"state": state, "attempts": int(resource.get("attempts") or 0) + 1, "last_error_code": None}).eq("id", resource["id"]).execute()
    return {"deleted": deleted, "already_absent": absent}


def _safe_host_path(resource: dict[str, Any]) -> Path:
    root_factory = HOST_RESOURCE_ROOTS[resource["resource_kind"]]
    root = root_factory().resolve()
    key = str(resource.get("resource_key") or "")
    if not re.fullmatch(r"tenant_[1-9][0-9]*/user_[1-9][0-9]*/[A-Za-z0-9_.-]+", key):
        raise DeletionStepError("storage_key_invalid", retryable=False)
    candidate = root / key
    # Validate the parent separately and retain the lexical final component so
    # an existing symlink cannot disappear through ``Path.resolve`` before the
    # explicit refusal in the deletion step.
    assert_path_within_root(
        candidate.parent,
        root,
        error=DeletionStepError("storage_path_escape", retryable=False),
    )
    if candidate.is_symlink():
        raise DeletionStepError("storage_symlink_refused", retryable=False)
    return candidate


def _step_delete_host_files(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    resources = _resources(request["id"], list(HOST_RESOURCE_ROOTS), client=client)
    deleted = 0
    absent = 0
    for resource in resources:
        path = _safe_host_path(resource)
        try:
            if path.is_symlink():
                raise DeletionStepError("storage_symlink_refused", retryable=False)
            path.unlink()
            state = "deleted"
            deleted += 1
        except FileNotFoundError:
            state = "absent"
            absent += 1
        except DeletionStepError:
            raise
        except OSError as error:
            raise DeletionStepError("host_storage_unavailable") from error
        client.table("data_deletion_resources").update({"state": state, "attempts": int(resource.get("attempts") or 0) + 1, "last_error_code": None}).eq("id", resource["id"]).execute()
    unknown = _resources(request["id"], ["unknown_storage"], client=client)
    if unknown:
        for resource in unknown:
            client.table("data_deletion_resources").update({"state": "manual_intervention", "last_error_code": "storage_category_policy_undefined"}).eq("id", resource["id"]).execute()
        raise DeletionStepError("storage_category_policy_undefined", retryable=False)
    return {"deleted": deleted, "already_absent": absent}


def _step_delete_application_data(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    subjects = _subjects(request["id"], client=client)
    if request["request_type"] == "tenant":
        tenant_id = int(request["target_tenant_id_snapshot"])
        client.table("tenants").delete().eq("tenant_id", tenant_id).execute()
        for subject in subjects:
            client.table("users").delete().eq("id", subject["user_id_snapshot"]).execute()
        return {"tenant_deleted": True, "platform_users_deleted": len(subjects)}
    client.table("users").delete().eq("id", request["target_user_id_snapshot"]).execute()
    return {"user_deleted": True}


def _step_delete_auth_identities(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    deleted = 0
    absent = 0
    for subject in _subjects(request["id"], client=client):
        if subject.get("provider_state") in {"deleted", "absent"}:
            continue
        auth_id = str(subject.get("auth_id") or "").strip()
        if not auth_id:
            state = "absent"
            absent += 1
        else:
            try:
                client.auth.admin.delete_user(auth_id)
                state = "deleted"
                deleted += 1
            except Exception as error:
                if _provider_absent(error):
                    state = "absent"
                    absent += 1
                else:
                    client.table("data_deletion_subjects").update({"last_error_code": "auth_provider_unavailable"}).eq("request_id", request["id"]).eq("user_id_snapshot", subject["user_id_snapshot"]).execute()
                    raise DeletionStepError("auth_provider_unavailable") from error
        client.table("data_deletion_subjects").update({"provider_state": state, "last_error_code": None}).eq("request_id", request["id"]).eq("user_id_snapshot", subject["user_id_snapshot"]).execute()
    return {"deleted": deleted, "already_absent": absent}


def _step_verify(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    checks: dict[str, str] = {}
    if request["request_type"] == "tenant":
        tenant_id = request["target_tenant_id_snapshot"]
        checks["tenant_database"] = "verified" if not _rows(client.table("tenants").select("tenant_id").eq("tenant_id", tenant_id).limit(1).execute()) else "mismatch"
        checks["public_binding"] = "verified" if not _rows(client.table("website_settings").select("id").eq("tenant_id", tenant_id).limit(1).execute()) else "mismatch"
        checks["integrations"] = "verified" if not _rows(client.table("calendar_sync_connections").select("id").eq("tenant_id", tenant_id).limit(1).execute()) else "mismatch"
    else:
        user_id = request["target_user_id_snapshot"]
        checks["user_database"] = "verified" if not _rows(client.table("users").select("id").eq("id", user_id).limit(1).execute()) else "mismatch"
        checks["integrations"] = "verified" if not _rows(client.table("calendar_sync_connections").select("id").eq("user_id", user_id).limit(1).execute()) else "mismatch"
    resources = _rows(client.table("data_deletion_resources").select("*").eq("request_id", request["id"]).execute())
    subjects = _subjects(request["id"], client=client)
    storage_verified = all(row.get("state") in {"deleted", "absent"} for row in resources)
    if storage_verified:
        for resource in resources:
            kind = resource.get("resource_kind")
            if kind in HOST_RESOURCE_ROOTS:
                if _safe_host_path(resource).exists():
                    storage_verified = False
                    break
            elif kind in PROVIDER_RESOURCE_BUCKETS:
                key = str(resource.get("resource_key") or "")
                folder, _, filename = key.rpartition("/")
                try:
                    listed = client.storage.from_(PROVIDER_RESOURCE_BUCKETS[kind]).list(
                        folder, {"search": filename, "limit": 100}
                    )
                except Exception as error:
                    raise DeletionStepError("storage_provider_verification_unavailable") from error
                if any(str(item.get("name") or "") == filename for item in (listed or []) if isinstance(item, dict)):
                    storage_verified = False
                    break
    checks["storage"] = "verified" if storage_verified else "mismatch"
    auth_verified = all(row.get("provider_state") in {"deleted", "absent"} for row in subjects)
    if auth_verified:
        get_provider_user = getattr(client.auth.admin, "get_user_by_id", None)
        if callable(get_provider_user):
            for subject in subjects:
                auth_id = str(subject.get("auth_id") or "").strip()
                if not auth_id:
                    continue
                try:
                    response = get_provider_user(auth_id)
                    if getattr(response, "user", None) or (isinstance(response, dict) and response.get("user")):
                        auth_verified = False
                        break
                except Exception as error:
                    if not _provider_absent(error):
                        raise DeletionStepError("auth_provider_verification_unavailable") from error
    checks["auth"] = "verified" if auth_verified else "mismatch"
    if "mismatch" in checks.values():
        client.table("data_deletion_requests").update({"verification_status": "mismatch"}).eq("id", request["id"]).execute()
        raise DeletionStepError("deletion_verification_mismatch")
    retained = list(RETAINED_CLASSES[request["request_type"]])
    integration_step = _one(
        client.table("data_deletion_steps").select("output_safe")
        .eq("request_id", request["id"]).eq("step_key", "revoke_integrations")
        .limit(1).execute()
    )
    if int(((integration_step or {}).get("output_safe") or {}).get("provider_revocation_unsupported") or 0) > 0:
        retained.append("external_calendar_provider_grant_revocation_unsupported")
    report = {"request_id": request["id"], "target_type": request["request_type"], "status": "verified_with_retained_records", "steps": checks, "retained_classes": retained}
    client.table("data_deletion_requests").update({"verification_status": "verified_with_retained_records", "retained_classes": retained, "completion_report": report}).eq("id", request["id"]).execute()
    return {"verified": True, "retained_class_count": len(retained)}


def _step_finalize(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    current = get_deletion_request(request["id"], client=client)
    if not current or current.get("verification_status") not in {"verified", "verified_with_retained_records"}:
        raise DeletionStepError("deletion_verification_required", retryable=False)
    state = "completed_with_retained_records" if current.get("retained_classes") else "completed"
    client.table("data_deletion_requests").update({
        "state": state, "current_phase": "completed", "completed_at": utc_now().isoformat(),
        "lease_owner": None, "lease_until": None, "retry_after": None, "last_error_code": None,
    }).eq("id", request["id"]).execute()
    return {"state": state}


STEP_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "freeze": _step_freeze,
    "revoke_sessions": _step_revoke_sessions,
    "revoke_integrations": _step_revoke_integrations,
    "stop_queued_work": _step_stop_queued_work,
    "delete_provider_objects": _step_delete_provider_objects,
    "delete_host_files": _step_delete_host_files,
    "delete_application_data": _step_delete_application_data,
    "delete_auth_identities": _step_delete_auth_identities,
    "verify": _step_verify,
    "finalize": _step_finalize,
}


def process_deletion_request(request: dict[str, Any], *, client=None, http_client=None) -> dict[str, Any]:
    database_client = client or service_supabase
    while True:
        current = get_deletion_request(str(request["id"]), client=database_client) or request
        if current.get("state") in TERMINAL_REQUEST_STATES:
            return public_request_status(current, include_target=True)
        step = _next_step(str(request["id"]), client=database_client)
        if not step:
            raise DeletionStepError("deletion_step_plan_incomplete", retryable=False)
        step = _mark_step_processing(step, client=database_client)
        database_client.table("data_deletion_requests").update({"current_phase": step["step_key"]}).eq("id", request["id"]).execute()
        try:
            output = STEP_HANDLERS[step["step_key"]](current, client=database_client, http_client=http_client)
            _finish_step(step, output, client=database_client)
        except DeletionStepError as error:
            _fail_step(current, step, error, client=database_client)
            logger.warning("deletion.step_failed", extra={"error_code": error.code})
            return public_request_status(get_deletion_request(str(request["id"]), client=database_client) or current, include_target=True)
        except Exception as error:
            wrapped = DeletionStepError("deletion_step_unexpected")
            _fail_step(current, step, wrapped, client=database_client)
            logger.error("deletion.step_unexpected", extra={"error_type": type(error).__name__})
            return public_request_status(get_deletion_request(str(request["id"]), client=database_client) or current, include_target=True)


def get_deletion_metrics(*, client=None) -> dict[str, int]:
    rows = _rows((client or service_supabase).table("data_deletion_requests").select("state,created_at,updated_at").limit(5000).execute())
    now = utc_now()
    oldest = 0
    active_dates: list[datetime] = []
    for row in rows:
        if row.get("state") not in TERMINAL_REQUEST_STATES:
            try:
                date = datetime.fromisoformat(str(row.get("created_at") or "").replace("Z", "+00:00"))
                active_dates.append(date if date.tzinfo else date.replace(tzinfo=timezone.utc))
            except ValueError:
                pass
    if active_dates:
        oldest = max(0, int((now - min(active_dates)).total_seconds()))
    return {
        "deletion_pending": sum(row.get("state") == "pending" for row in rows),
        "deletion_in_progress": sum(row.get("state") == "in_progress" for row in rows),
        "deletion_retrying": sum(row.get("state") == "waiting_retry" for row in rows),
        "deletion_manual_intervention": sum(row.get("state") == "failed_manual_intervention" for row in rows),
        "deletion_completed": sum(row.get("state") in {"completed", "completed_with_retained_records"} for row in rows),
        "deletion_oldest_pending_age_seconds": oldest,
    }
