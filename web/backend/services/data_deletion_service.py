"""Durable, idempotent user and tenant deletion lifecycle."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
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


class DeletionOwnershipLost(RuntimeError):
    """The original claim is unusable; never acknowledge it or fall back."""


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
    # Error text can mention an absent object while the request itself timed
    # out. Only structured provider absence is authoritative.
    code = getattr(error, "code", None)
    return status in {404, 410} or code in {"user_not_found", "object_not_found"}


def _rpc_error(error: Exception) -> HTTPException:
    text = str(error).lower()
    mappings = {
        "deletion_request_unauthorized": (403, "deletion_request_unauthorized", "Deletion is not authorized."),
        "deletion_scope_already_requested": (409, "deletion_already_requested", "An active deletion request already exists."),
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


def _claim_parameters(request: dict[str, Any]) -> dict[str, Any]:
    if (not request.get("lease_owner") or type(request.get("claim_generation")) is not int
            or request["claim_generation"] <= 0 or type(request.get("attempt_count")) is not int
            or request["attempt_count"] <= 0):
        raise DeletionOwnershipLost("deletion_claim_missing")
    return {"p_request_id": str(request["id"]), "p_owner": request["lease_owner"],
            "p_generation": request["claim_generation"], "p_attempt": request["attempt_count"]}


def _owned_rpc(name: str, request: dict[str, Any], parameters: dict[str, Any], *, client):
    try:
        return client.rpc(name, {**_claim_parameters(request), **parameters}).execute().data
    except DeletionOwnershipLost:
        raise
    except Exception as error:
        if any(code in str(error) for code in ("deletion_claim_lost", "deletion_step_claim_lost", "deletion_effect_claim_lost")):
            raise DeletionOwnershipLost("deletion_claim_lost") from None
        raise


def _transition(request, action, *, step=None, data=None, client):
    return _owned_rpc("transition_data_deletion_v2", request, {
        "p_action": action, "p_step_id": (step or {}).get("id"),
        "p_step_attempt": (step or {}).get("attempts"), "p_data": data or {},
    }, client=client)


def cancel_deletion_request(request_id: str, *, client=None) -> dict[str, Any]:
    try:
        row = _one((client or service_supabase).rpc("cancel_data_deletion_request_v2", {
            "p_request_id": request_id,
        }).execute())
    except Exception as error:
        if "deletion_cannot_be_cancelled" in str(error):
            raise HTTPException(status_code=409, detail=error_detail("deletion_cannot_be_cancelled", "Deletion has already started.")) from None
        raise _rpc_error(error) from error
    if not row:
        raise HTTPException(status_code=503, detail="Deletion cancellation was not acknowledged")
    return public_request_status(row, include_target=True)


def claim_deletion_requests(*, worker_id: str, limit: int = 5, lease_seconds: int = 300, client=None) -> list[dict[str, Any]]:
    return _rows((client or service_supabase).rpc("claim_data_deletion_requests_v2", {
        "p_worker_id": str(worker_id), "p_limit": max(1, min(int(limit), 25)),
        "p_lease_seconds": max(30, min(int(lease_seconds), 3600)),
    }).execute())


def _next_step(request_id: str, *, client) -> dict[str, Any] | None:
    return _one(client.table("data_deletion_steps").select("*").eq("request_id", request_id).in_(
        "state", ["pending", "processing", "waiting_retry"]
    ).order("step_order").limit(1).execute())


def _mark_step_processing(step: dict[str, Any], *, request=None, client) -> dict[str, Any]:
    claim = request or step.get("_claim") or {}
    result = _transition(claim, "begin", client=client)
    if not isinstance(result, dict) or result.get("blocked"):
        raise DeletionStepError("deletion_step_attempts_exhausted", retryable=False)
    return {**result, "_claim": dict(claim)}


def _finish_step(step: dict[str, Any], output: dict[str, Any], *, client) -> None:
    _transition(step.get("_claim") or {}, "complete", step=step, data=output, client=client)


def _fail_step(request: dict[str, Any], step: dict[str, Any], error: DeletionStepError, *, client) -> None:
    _transition(request, "fail", step=step, data={"code": error.code, "retryable": error.retryable}, client=client)
    if not error.retryable or int(step.get("attempts") or 0) >= int(step.get("max_attempts") or 1):
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


def _local_step(request, *, client, **_kwargs):
    step = request.get("_step") or {}
    return _owned_rpc("run_data_deletion_local_step_v2", request, {
        "p_step_id": step.get("id"), "p_step_attempt": step.get("attempts"),
    }, client=client)


_step_freeze = _local_step
_step_revoke_sessions = _local_step


def _effect(request, kind, target, action, *, outcome=None, client):
    step = request.get("_step") or {}
    return _owned_rpc("data_deletion_effect_v2", request, {
        "p_step_id": step.get("id"), "p_step_attempt": step.get("attempts"),
        "p_kind": kind, "p_target": str(target), "p_action": action, "p_outcome": outcome,
    }, client=client)


def _intent(request, kind, target, *, client):
    # Renew BEFORE durable intent, never after an external call has lost ownership.
    _transition(request, "renew", client=client)
    return _effect(request, kind, target, "intent", client=client)


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
        intent = _intent(request, "connection", connection["id"], client=client)
        if intent.get("already_confirmed"):
            continue
        connection = intent["target"]
        try:
            outcome = disconnect_connection_for_deletion(connection, http_client=http_client, client=client, remove_local=False)
        except (CalendarSyncError, httpx.HTTPError) as error:
            raise DeletionStepError("integration_outcome_uncertain", retryable=False) from error
        _effect(request, "connection", connection["id"], "confirm", outcome=outcome, client=client)
        if outcome == "provider_revoked":
            revoked += 1
        else:
            local_only += 1
    return {"connections": len(connections), "provider_revoked": revoked, "local_credentials_removed": len(connections), "provider_revocation_unsupported": local_only}


_step_stop_queued_work = _local_step


def _step_delete_provider_objects(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    resources = _resources(request["id"], list(PROVIDER_RESOURCE_BUCKETS), client=client)
    deleted = 0
    absent = 0
    for resource in resources:
        intent = _intent(request, "resource", resource["id"], client=client)
        if intent.get("already_confirmed"):
            continue
        resource = intent["target"]
        try:
            client.storage.from_(PROVIDER_RESOURCE_BUCKETS[resource["resource_kind"]]).remove([resource["resource_key"]])
            state = "deleted"
            deleted += 1
        except Exception as error:
            if _provider_absent(error):
                state = "absent"
                absent += 1
            else:
                raise DeletionStepError("storage_outcome_uncertain", retryable=False) from error
        _effect(request, "resource", resource["id"], "confirm", outcome=state, client=client)
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


def _unlink_host_resource(resource: dict[str, Any]) -> None:
    """Unlink beneath pinned directory FDs; parent swaps cannot escape scope."""
    import stat
    root = HOST_RESOURCE_ROOTS[resource["resource_kind"]]().resolve()
    parts = str(resource["resource_key"]).split("/")
    _safe_host_path(resource)
    descriptors = []
    try:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(descriptor)
        for component in parts[:-1]:
            descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            descriptors.append(descriptor)
        leaf = os.stat(parts[-1], dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISLNK(leaf.st_mode) or not stat.S_ISREG(leaf.st_mode):
            raise DeletionStepError("storage_symlink_refused", retryable=False)
        os.unlink(parts[-1], dir_fd=descriptor)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _step_delete_host_files(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    resources = _resources(request["id"], list(HOST_RESOURCE_ROOTS), client=client)
    deleted = 0
    absent = 0
    for resource in resources:
        # Validate before intent; an invalid path is never an attempted operation.
        _safe_host_path(resource)
        intent = _intent(request, "resource", resource["id"], client=client)
        if intent.get("already_confirmed"):
            continue
        resource = intent["target"]
        path = _safe_host_path(resource)
        try:
            if path.is_symlink():
                raise DeletionStepError("storage_symlink_refused", retryable=False)
            _unlink_host_resource(resource)
            state = "deleted"
            deleted += 1
        except FileNotFoundError:
            state = "absent"
            absent += 1
        except DeletionStepError:
            raise
        except OSError as error:
            raise DeletionStepError("host_storage_outcome_uncertain", retryable=False) from error
        _effect(request, "resource", resource["id"], "confirm", outcome=state, client=client)
    if _resources(request["id"], ["unknown_storage"], client=client):
        raise DeletionStepError("storage_category_policy_undefined", retryable=False)
    return {"deleted": deleted, "already_absent": absent}


_step_delete_application_data = _local_step


def _step_delete_auth_identities(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    deleted = 0
    absent = 0
    for subject in _subjects(request["id"], client=client):
        if subject.get("provider_state") in {"deleted", "absent"}:
            continue
        intent = _intent(request, "subject", subject["user_id_snapshot"], client=client)
        if intent.get("already_confirmed"):
            continue
        subject = intent["target"]
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
                    raise DeletionStepError("auth_outcome_uncertain", retryable=False) from error
        _effect(request, "subject", subject["user_id_snapshot"], "confirm", outcome=state, client=client)
    return {"deleted": deleted, "already_absent": absent}


def _provider_object_present(client, bucket: str, key: str) -> bool:
    folder, _, filename = key.rpartition("/")
    # Search is substring-based and paginated. An empty first exact-match set
    # does not establish absence. Bound provider work and refuse incomplete or
    # malformed listings instead of falsely certifying deletion.
    page_size = 100
    for offset in range(0, 1000, page_size):
        try:
            listed = client.storage.from_(bucket).list(folder, {
                "search": filename, "limit": page_size, "offset": offset,
                "sortBy": {"column": "name", "order": "asc"},
            })
        except Exception as error:
            raise DeletionStepError("storage_provider_verification_unavailable") from error
        if (not isinstance(listed, list) or len(listed) > page_size
                or any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
                       or not item["name"] for item in listed)):
            raise DeletionStepError("storage_provider_verification_unavailable")
        if any(item["name"] == filename for item in listed):
            return True
        if len(listed) < page_size:
            return False
    raise DeletionStepError("storage_provider_verification_incomplete")


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
                if _provider_object_present(client, PROVIDER_RESOURCE_BUCKETS[kind], key):
                    storage_verified = False
                    break
    checks["storage"] = "verified" if storage_verified else "mismatch"
    auth_verified = all(row.get("provider_state") in {"deleted", "absent"} for row in subjects)
    if auth_verified:
        get_provider_user = getattr(client.auth.admin, "get_user_by_id", None)
        if not callable(get_provider_user):
            raise DeletionStepError("auth_provider_verification_unavailable")
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
    return {**report, "verified": True, "retained_class_count": len(retained)}


def _step_finalize(request: dict[str, Any], *, client, **_kwargs) -> dict[str, Any]:
    # The complete transition validates verification and ALL authoritative steps
    # and finalizes atomically with the final step. No read-then-update authority.
    _claim_parameters(request)
    return {"finalization_requested": True}


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
    # Never replace this original claim with a fresh row owned by a successor.
    original = dict(request)
    _claim_parameters(original)
    while True:
        current = get_deletion_request(str(original["id"]), client=database_client)
        if current and current.get("state") in TERMINAL_REQUEST_STATES:
            return public_request_status(current, include_target=True)
        step = None
        try:
            step = _mark_step_processing({}, request=original, client=database_client)
            context = {**original, "_step": step}
            output = STEP_HANDLERS[step["step_key"]](context, client=database_client, http_client=http_client)
            _finish_step(step, output, client=database_client)
        except DeletionOwnershipLost:
            logger.warning("deletion.ownership_lost")
            raise
        except Exception as error:
            if step is None:
                raise
            failure = error if isinstance(error, DeletionStepError) else DeletionStepError("deletion_step_unexpected", retryable=False)
            # RPC failure here propagates; never report an unacknowledged failure
            # as successfully persisted, and never attempt a legacy mutation.
            _fail_step(original, step, failure, client=database_client)
            logger.warning("deletion.step_failed", extra={"error_code": failure.code})
            return public_request_status(get_deletion_request(str(original["id"]), client=database_client) or original, include_target=True)


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
