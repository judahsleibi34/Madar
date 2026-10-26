"""Bounded one-shot automatic synchronization for API Data Sources.

PostgreSQL owns due-time selection, leases, fencing and retry state.  This module
only executes claims through the existing incremental ingestion pipeline; it does
not introduce another storage or cursor path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services import (
    project_api_ingestion_service,
    project_dataset_checkpoint_service,
    project_source_ingestion_service,
)


AUTOMATIC_SYNC_SCHEMA = 156
DEFAULT_LEASE_SECONDS = 900
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncFailure:
    category: str
    transient: bool
    credential_attention: bool = False
    phase: str = "execution"


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return list(data or [])


def automatic_sync_available(*, client=None) -> bool:
    database = client or service_supabase
    rows = _rows(database.table("application_schema_state").select("schema_version")
                 .eq("contract_key", "core").limit(1).execute())
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= AUTOMATIC_SYNC_SCHEMA)
    except (TypeError, ValueError):
        return False


def configure_schedule(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    user_id: int, enabled: bool, interval_seconds: int,
    expected_fence: int | None = None, client=None,
) -> dict:
    """Authorized service boundary for a future customer scheduling control."""
    database = client or service_supabase
    params = {
        "p_tenant_id": int(tenant_id), "p_project_id": project_id,
        "p_source_id": source_id, "p_source_resource_id": resource_id,
        "p_actor_user_id": int(user_id), "p_enabled": bool(enabled),
        "p_interval_seconds": max(900, min(int(interval_seconds), 604800)),
        "p_expected_fence": expected_fence,
    }
    rows = _rows(database.rpc("configure_data_source_sync156", params).execute())
    if not rows:
        raise RuntimeError("Automatic synchronization schedule was not saved")
    return rows[0]


def get_schedule(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    user_id: int, client=None,
) -> dict | None:
    database = client or service_supabase
    from services import project_data_source_service
    project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(user_id), client=database,
    )
    rows = _rows(database.table("data_source_sync_schedules").select(
        "id,source_resource_id,enabled,interval_seconds,next_due_at,last_attempt_at,"
        "last_success_at,status,retry_count,last_error_category,diagnostic_metadata,fence,updated_at"
    ).eq("tenant_id", int(tenant_id)).eq("project_id", project_id)
      .eq("source_id", source_id).eq("source_resource_id", resource_id)
      .limit(1).execute())
    return rows[0] if rows else None


def reconcile_expired_claims(
    *, worker_id: str, limit: int = 20, now: str | None = None, client=None,
) -> list[dict]:
    params: dict[str, object] = {
        "p_worker_id": str(worker_id)[:200], "p_limit": max(1, min(int(limit), 100)),
    }
    if now is not None:
        params["p_now"] = now
    return _rows((client or service_supabase).rpc(
        "reconcile_expired_source_syncs156", params,
    ).execute())


def claim_due_syncs(
    *, worker_id: str, limit: int = 5, lease_seconds: int = DEFAULT_LEASE_SECONDS,
    tenant_limit: int = 2, provider_limit: int = 4,
    now: str | None = None, client=None,
) -> list[dict]:
    params: dict[str, object] = {
        "p_worker_id": str(worker_id)[:200], "p_limit": max(1, min(int(limit), 50)),
        "p_lease_seconds": max(60, min(int(lease_seconds), 3600)),
        "p_tenant_limit": max(1, min(int(tenant_limit), 20)),
        "p_provider_limit": max(1, min(int(provider_limit), 50)),
    }
    if now is not None:
        params["p_now"] = now
    return _rows((client or service_supabase).rpc(
        "claim_due_data_source_syncs156", params,
    ).execute())


def _lease_params(claim: dict) -> dict[str, object]:
    return {
        "p_schedule_id": claim["schedule_id"],
        "p_lease_token": claim["lease_token"],
        "p_fence": int(claim["fence"]),
    }


def heartbeat_claim(claim: dict, *, lease_seconds: int, client=None) -> None:
    params = {
        **_lease_params(claim),
        "p_lease_seconds": max(60, min(int(lease_seconds), 3600)),
    }
    result = (client or service_supabase).rpc("heartbeat_source_sync156", params).execute()
    if getattr(result, "data", None) is not True:
        raise RuntimeError("source_sync_lease_lost")


def _attach_ingestion(claim: dict, ingestion_run_id: str, *, client=None) -> None:
    result = (client or service_supabase).rpc("attach_source_sync_ingestion156", {
        **_lease_params(claim), "p_ingestion_run_id": ingestion_run_id,
    }).execute()
    if getattr(result, "data", None) is not True:
        raise RuntimeError("source_sync_ingestion_not_attached")


def _complete_claim(claim: dict, ingestion_run_id: str, *, client=None) -> dict:
    rows = _rows((client or service_supabase).rpc("complete_source_sync156", {
        **_lease_params(claim), "p_ingestion_run_id": ingestion_run_id,
        "p_credential_revision": int(claim["credential_revision"]),
    }).execute())
    if not rows:
        raise RuntimeError("source_sync_completion_missing")
    return rows[0]


def _classify_failure(error: Exception, *, phase: str) -> SyncFailure:
    code = project_api_ingestion_service.provider_failure_code(error)
    if isinstance(error, HTTPException) and isinstance(error.detail, dict):
        code = str(error.detail.get("code") or code)
    if code in {"provider_unauthorized", "provider_credentials_revoked",
                "provider_credentials_invalid"}:
        return SyncFailure(code, False, True, phase)
    if code in {"provider_timeout", "provider_unavailable", "provider_rate_limited",
                "provider_credentials_key_service_unavailable",
                "provider_credentials_unavailable", "storage_unavailable"}:
        return SyncFailure(code, True, False, phase)
    if code == "ingestion_failed":
        code = "automatic_sync_failed"
    return SyncFailure(code, False, False, phase)


def _fail_claim(claim: dict, failure: SyncFailure, *, client=None) -> dict:
    database = client or service_supabase
    rows = _rows(database.rpc("fail_source_sync156", {
        **_lease_params(claim), "p_error_category": failure.category,
        "p_transient": failure.transient,
        "p_credential_attention": failure.credential_attention,
        "p_diagnostic_metadata": {"phase": failure.phase},
    }).execute())
    return rows[0] if rows else {}


def _credential_state_requires_attention(claim: dict, *, client=None) -> bool:
    """Distinguish missing/revoked credentials from transient Vault failures."""
    try:
        from services.data_source_credential_service import list_credential_metadata
        credentials = list_credential_metadata(
            tenant_id=int(claim["tenant_id"]), project_id=str(claim["project_id"]),
            source_id=str(claim["source_id"]), user_id=int(claim["actor_user_id"]),
            provider_key=str(claim["provider_key"]), client=client,
        )
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    for credential in credentials:
        if credential.get("status") != "active":
            continue
        expires_at = credential.get("expires_at")
        if not expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if expiry.tzinfo is not None and expiry > now:
            return False
    return True


async def execute_claim(
    claim: dict, *, lease_seconds: int = DEFAULT_LEASE_SECONDS,
    fixture_batch: int = 1, provider=None, client=None,
) -> dict:
    """Execute one claimed schedule through the existing fenced commit path."""
    database = client or service_supabase
    tenant_id = int(claim["tenant_id"])
    project_id = str(claim["project_id"])
    source_id = str(claim["source_id"])
    resource_id = str(claim["source_resource_id"])
    user_id = int(claim["actor_user_id"])
    run_id: str | None = None
    run_lease: str | None = None
    metadata_started = False

    try:
        reservation = project_source_ingestion_service.reserve_ingestion(
            tenant_id=tenant_id, project_id=project_id, source_id=source_id,
            user_id=user_id,
            idempotency_key=f"auto:{claim['schedule_id']}:{int(claim['fence'])}",
            source_type="api_provider", resource_key=str(claim["resource_key"]),
            display_name=f"Automatic {claim['resource_key']}", client=database,
        )
        if reservation.get("disposition") != "reserved" or not reservation.get("lease_token"):
            raise RuntimeError("automatic_sync_ingestion_not_reserved")
        run_id = str(reservation["ingestion_run_id"])
        run_lease = str(reservation["lease_token"])
        if str(reservation.get("source_resource_id")) != resource_id:
            raise RuntimeError("automatic_sync_resource_mismatch")
        _attach_ingestion(claim, run_id, client=database)

        def heartbeat() -> None:
            heartbeat_claim(claim, lease_seconds=lease_seconds, client=database)
            project_source_ingestion_service.heartbeat_ingestion(
                tenant_id=tenant_id, ingestion_run_id=run_id,
                lease_token=run_lease, client=database,
            )

        def persist_incremental(artifact: dict, batch) -> dict:
            nonlocal metadata_started
            metadata_started = True
            project_source_ingestion_service.stage_incremental_changes(
                tenant_id=tenant_id, ingestion_run_id=run_id,
                lease_token=run_lease, changes=[dict(item) for item in batch.changes],
                client=database,
            )
            return project_source_ingestion_service.complete_incremental_ingestion(
                tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                user_id=user_id, ingestion_run_id=run_id, lease_token=run_lease,
                storage_object_id=artifact["storage_object_id"],
                change_count=len(batch.changes), manifest_hash=artifact["sha256"],
                next_cursor=batch.next_cursor,
                schema_fingerprint=batch.schema_fingerprint,
                credential_reference=(artifact.get("provider_metadata") or {}).get("credential"),
                client=database,
            )

        result = await project_api_ingestion_service.process_api_source(
            tenant_id=tenant_id, project_id=project_id, source_id=source_id,
            user_id=user_id, ingestion_run_id=run_id, lifecycle_heartbeat=heartbeat,
            storage_reservation_persister=lambda reservation_id: (
                project_source_ingestion_service.attach_storage_reservation(
                    tenant_id=tenant_id, ingestion_run_id=run_id, lease_token=run_lease,
                    storage_reservation_id=reservation_id, client=database,
                )
            ),
            storage_object_persister=lambda storage_object_id: (
                project_source_ingestion_service.attach_storage_object(
                    tenant_id=tenant_id, ingestion_run_id=run_id, lease_token=run_lease,
                    storage_object_id=storage_object_id, client=database,
                )
            ),
            storage_object_failure_resolver=lambda storage_object_id: (
                project_source_ingestion_service.storage_object_attachment_state(
                    tenant_id=tenant_id, ingestion_run_id=run_id, lease_token=run_lease,
                    storage_object_id=storage_object_id, client=database,
                )
            ),
            incremental_persister=persist_incremental,
            noop_persister=lambda next_cursor, credential_reference: (
                project_source_ingestion_service.complete_noop_ingestion(
                    tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                    user_id=user_id, ingestion_run_id=run_id, lease_token=run_lease,
                    next_cursor=next_cursor,
                    credential_reference=credential_reference, client=database,
                )
            ),
            metadata_failure_resolver=lambda _error: (
                project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                    user_id=user_id, ingestion_run_id=run_id, client=database,
                )
            ),
            resource_type=str(claim["resource_key"]),
            sync_cursor=reservation.get("expected_cursor"), fixture_batch=fixture_batch,
            shared_immutable=bool(reservation.get("shared_immutable_storage")),
            provider=provider,
            provider_audit=lambda metadata: logger.info(
                "data.automatic_sync.transport",
                extra={"tenant_id": tenant_id, "project_id": project_id,
                       "source_id": source_id, **metadata},
            ),
        )
        _complete_claim(claim, run_id, client=database)

        checkpoint = None
        checkpoint_error = None
        if not result.get("no_changes"):
            try:
                checkpoint = project_dataset_checkpoint_service.enqueue_dataset_checkpoint(
                    tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                    resource_id=resource_id,
                    dataset_id=str(result["persistent_dataset_id"]), user_id=user_id,
                    target_revision=int(result["committed_revision"]), client=database,
                )
            except Exception:
                checkpoint_error = "checkpoint_enqueue_failed"
                logger.exception("data.automatic_sync.checkpoint_enqueue_failed", extra={
                    "tenant_id": tenant_id, "project_id": project_id, "source_id": source_id,
                })
        return {
            "schedule_id": claim["schedule_id"], "outcome": "succeeded",
            "ingestion_run_id": run_id,
            "dataset_id": result.get("persistent_dataset_id"),
            "committed_revision": result.get("committed_revision"),
            "no_changes": bool(result.get("no_changes")),
            "checkpoint": checkpoint, "checkpoint_error": checkpoint_error,
        }
    except Exception as error:
        if run_id and run_lease:
            try:
                recovered = project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                    user_id=user_id, ingestion_run_id=run_id, client=database,
                )
            except Exception:
                recovered = None
            if isinstance(recovered, dict):
                try:
                    _complete_claim(claim, run_id, client=database)
                    return {"schedule_id": claim["schedule_id"], "outcome": "succeeded",
                            "ingestion_run_id": run_id, "completion_recovered": True,
                            **recovered}
                except Exception:
                    pass
            try:
                project_source_ingestion_service.fail_ingestion(
                    tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                    user_id=user_id, ingestion_run_id=run_id, lease_token=run_lease,
                    failure_code=project_api_ingestion_service.provider_failure_code(error),
                    client=database,
                )
            except Exception:
                logger.exception("data.automatic_sync.ingestion_failure_record_failed")
        failure = _classify_failure(
            error, phase="commit" if metadata_started else "provider",
        )
        if failure.category == "provider_unavailable" and not metadata_started \
                and _credential_state_requires_attention(claim, client=database):
            failure = SyncFailure(
                "provider_credentials_revoked", False, True, "provider",
            )
        _fail_claim(claim, failure, client=database)
        return {"schedule_id": claim["schedule_id"], "outcome": "failed",
                "error_category": failure.category, "retryable": failure.transient,
                "credential_attention": failure.credential_attention}


async def run_batch(
    *, worker_id: str, limit: int = 5, lease_seconds: int = DEFAULT_LEASE_SECONDS,
    tenant_limit: int = 2, provider_limit: int = 4, now: str | None = None,
    client=None,
) -> dict:
    database = client or service_supabase
    reconciled = reconcile_expired_claims(
        worker_id=f"{worker_id}:reconcile", limit=max(limit, 20), now=now, client=database,
    )
    claims = claim_due_syncs(
        worker_id=worker_id, limit=limit, lease_seconds=lease_seconds,
        tenant_limit=tenant_limit, provider_limit=provider_limit, now=now, client=database,
    )
    results = []
    for claim in claims:
        results.append(await execute_claim(
            claim, lease_seconds=lease_seconds, client=database,
        ))
    return {"available": True, "reconciled": reconciled,
            "claimed": len(claims), "results": results}
