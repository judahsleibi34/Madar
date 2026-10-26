import logging
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from data_analysis import services as data_services
from services import project_data_source_service, project_dataset_service
from services.immutable_object_storage import (
    ImmutableObject,
    ImmutableObjectError,
    ObjectErrorCategory,
    configured_store,
    descriptor_from_row,
)
from services.storage_quota_service import finish_storage, release_storage


SOURCE_INGESTIONS_SCHEMA = 149
SOURCE_INGESTION_RECOVERY_SCHEMA = 150
INCREMENTAL_INGESTION_SCHEMA = 152
SHARED_IMMUTABLE_STORAGE_SCHEMA = 154
CREDENTIAL_VAULT_SCHEMA = 155
DEFAULT_UPLOAD_LEASE_SECONDS = 7200
logger = logging.getLogger(__name__)
INGESTION_FIELDS_149 = (
    "id,project_id,source_id,status,attempt_number,attempt_started_at,completed_at,"
    "result_dataset_id,result_version_id,failure_code,run_metadata,created_at,updated_at"
)
INGESTION_FIELDS_150 = (
    INGESTION_FIELDS_149 + ","
    "heartbeat_at,lease_expires_at,storage_reservation_id,storage_object_id,"
    "reconciliation_state,reconciliation_attempts,last_reconciled_at,reconciliation_code"
)
INGESTION_FIELDS_152 = (
    INGESTION_FIELDS_150 + ","
    "ingestion_kind,source_resource_id,expected_cursor,next_cursor,"
    "committed_revision,manifest_hash,staged_change_count"
)
FAILURE_CODES = {
    "upload_rejected",
    "upload_too_large",
    "storage_unavailable",
    "metadata_commit_failed",
    "ingestion_failed",
    "abandoned_ingestion",
    "provider_cancelled",
    "provider_timeout",
    "provider_unavailable",
    "provider_unauthorized",
    "provider_rate_limited",
    "provider_destination_forbidden",
    "provider_payload_invalid",
    "provider_payload_too_large",
}


def _rows(response) -> list[dict[str, Any]]:
    return list(getattr(response, "data", None) or [])


def _safe_uuid(value: object, *, detail: str = "Ingestion run was not found.") -> str:
    normalized = str(value or "").strip().lower()
    if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        normalized,
    ):
        raise HTTPException(status_code=404, detail=detail)
    return normalized


def _normalize_idempotency_key(value: object) -> str:
    key = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_idempotency_key",
                "message": "Idempotency-Key must contain 8 to 128 safe characters.",
            },
        )
    return key


def source_ingestions_available(*, client=None) -> bool:
    database = client or service_supabase
    result = (
        database.table("application_schema_state")
        .select("schema_version")
        .eq("contract_key", "core")
        .limit(1)
        .execute()
    )
    rows = _rows(result)
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= SOURCE_INGESTIONS_SCHEMA)
    except (TypeError, ValueError):
        return False


def ingestion_recovery_available(*, client=None) -> bool:
    database = client or service_supabase
    result = (
        database.table("application_schema_state")
        .select("schema_version")
        .eq("contract_key", "core")
        .limit(1)
        .execute()
    )
    rows = _rows(result)
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= SOURCE_INGESTION_RECOVERY_SCHEMA)
    except (TypeError, ValueError):
        return False


def incremental_ingestion_available(*, client=None) -> bool:
    database = client or service_supabase
    result = (
        database.table("application_schema_state")
        .select("schema_version")
        .eq("contract_key", "core")
        .limit(1)
        .execute()
    )
    rows = _rows(result)
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= INCREMENTAL_INGESTION_SCHEMA)
    except (TypeError, ValueError):
        return False


def shared_immutable_storage_available(*, client=None) -> bool:
    database = client or service_supabase
    result = database.table("application_schema_state").select("schema_version").eq(
        "contract_key", "core"
    ).limit(1).execute()
    rows = _rows(result)
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= SHARED_IMMUTABLE_STORAGE_SCHEMA)
    except (TypeError, ValueError):
        return False


def credential_vault_available(*, client=None) -> bool:
    database = client or service_supabase
    result = database.table("application_schema_state").select("schema_version").eq(
        "contract_key", "core"
    ).limit(1).execute()
    rows = _rows(result)
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= CREDENTIAL_VAULT_SCHEMA)
    except (TypeError, ValueError):
        return False


def require_source_ingestions_schema(*, client=None) -> None:
    if not source_ingestions_available(client=client):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "source_ingestions_upgrade_required",
                "message": "Source-linked imports require the database upgrade.",
            },
        )


def reserve_ingestion(
    *,
    tenant_id: int,
    project_id: str,
    source_id: str,
    user_id: int,
    idempotency_key: str,
    source_type: str = project_data_source_service.SOURCE_TYPE_SPREADSHEET_UPLOAD,
    resource_key: str | None = None,
    display_name: str | None = None,
    client=None,
) -> dict:
    database = client or service_supabase
    project_dataset_service.require_data_project(project_id, tenant_id=int(tenant_id), client=database)
    source = project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(user_id),
        source_id=source_id,
        client=database,
    )
    expected_type = str(source_type or "").strip().lower()
    if source.get("status") != "active" or source.get("source_type") != expected_type:
        raise HTTPException(status_code=409, detail="This data source is not active for this import type.")
    api_enabled = project_data_source_service.api_data_sources_available(client=database)
    if expected_type == project_data_source_service.SOURCE_TYPE_API_PROVIDER and not api_enabled:
        raise HTTPException(status_code=503, detail={
            "code": "api_data_sources_upgrade_required",
            "message": "API data sources require the database upgrade.",
        })

    recovery_enabled = ingestion_recovery_available(client=database)
    incremental_enabled = (
        expected_type == project_data_source_service.SOURCE_TYPE_API_PROVIDER
        and incremental_ingestion_available(client=database)
    )
    params = {
            "p_tenant_id": int(tenant_id),
            "p_project_id": _safe_uuid(project_id, detail="Data project was not found."),
            "p_source_id": _safe_uuid(source_id, detail="Data source was not found."),
            "p_user_id": int(user_id),
            "p_idempotency_key": _normalize_idempotency_key(idempotency_key),
    }
    if incremental_enabled:
        normalized_resource = str(resource_key or source.get("resource_type") or "").strip().lower()
        params.update({
            "p_resource_key": normalized_resource,
            "p_display_name": str(display_name or f"{source.get('display_name') or 'API'} — {normalized_resource}")[:255],
            "p_lease_seconds": DEFAULT_UPLOAD_LEASE_SECONDS,
        })
        rpc_name = "reserve_incremental_source_ingestion152"
    elif recovery_enabled:
        params["p_lease_seconds"] = DEFAULT_UPLOAD_LEASE_SECONDS
        rpc_name = "reserve_source_ingestion151" if api_enabled else "reserve_source_ingestion150"
    else:
        rpc_name = "reserve_source_ingestion149"
    result = database.rpc(
        rpc_name,
        params,
    ).execute()
    records = _rows(result)
    if not records:
        raise RuntimeError("Ingestion run was not reserved")
    record = records[0]
    record["shared_immutable_storage"] = bool(
        incremental_enabled and shared_immutable_storage_available(client=database)
    )
    return record


def stage_incremental_changes(
    *, tenant_id: int, ingestion_run_id: str, lease_token: str,
    changes: list[dict], client=None,
) -> int:
    if not changes:
        raise HTTPException(status_code=422, detail="Incremental change batch is empty.")
    database = client or service_supabase
    staged = 0
    for start in range(0, len(changes), 500):
        # PostgreSQL distinguishes SQL NULL from JSON null.  Tombstones carry no
        # payload, so omit a Python None before the JSONB RPC is serialized; a
        # non-null delete payload remains intact and is rejected by the schema.
        batch = []
        for change in changes[start:start + 500]:
            item = dict(change)
            if item.get("operation") == "delete" and item.get("payload") is None:
                item.pop("payload", None)
            batch.append(item)
        response = database.rpc("stage_incremental_changes152", {
            "p_tenant_id": int(tenant_id),
            "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
            "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
            "p_changes": batch,
        }).execute()
        value = getattr(response, "data", None)
        if isinstance(value, list) and value:
            value = value[0]
        if isinstance(value, dict) and value:
            value = next(iter(value.values()))
        if value is not None:
            staged = int(value)
    return staged


def complete_incremental_ingestion(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    ingestion_run_id: str, lease_token: str, storage_object_id: str,
    change_count: int, manifest_hash: str, next_cursor: str | None,
    schema_fingerprint: str, credential_reference: dict | None = None, client=None,
) -> dict:
    database = client or service_supabase
    params = {
        "p_tenant_id": int(tenant_id),
        "p_project_id": _safe_uuid(project_id, detail="Data project was not found."),
        "p_source_id": _safe_uuid(source_id, detail="Data source was not found."),
        "p_user_id": int(user_id),
        "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
        "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
        "p_storage_object_id": _safe_uuid(storage_object_id, detail="Storage object was not found."),
        "p_change_count": int(change_count),
        "p_manifest_hash": str(manifest_hash),
        "p_next_cursor": next_cursor,
        "p_schema_fingerprint": str(schema_fingerprint),
    }
    rpc_name = "complete_incremental_ingestion152"
    if credential_vault_available(client=database):
        reference = credential_reference if isinstance(credential_reference, dict) else {}
        if not all(reference.get(key) is not None for key in (
            "credential_id", "credential_version", "source_revision",
        )):
            raise HTTPException(status_code=409, detail={
                "code": "provider_credential_revision_missing",
                "message": "The provider credential must be re-resolved before committing.",
            })
        params.update({
            "p_credential_id": _safe_uuid(
                reference["credential_id"], detail="Provider credential was not found.",
            ),
            "p_credential_version": int(reference["credential_version"]),
            "p_credential_revision": int(reference["source_revision"]),
        })
        rpc_name = "complete_incremental_ingestion155"
    records = _rows(database.rpc(rpc_name, params).execute())
    if not records:
        raise RuntimeError("Incremental ingestion was not completed")
    record = records[0]
    return {
        "persistent_dataset_id": record.get("dataset_id"),
        "dataset_version_id": record.get("latest_checkpoint_version_id"),
        "source_resource_id": record.get("source_resource_id"),
        "committed_revision": int(record.get("committed_revision") or 0),
        "ingestion_run_id": record.get("ingestion_run_id"),
        "ingestion_status": record.get("ingestion_status") or "succeeded",
        "change_counts": {
            "inserted": int(record.get("inserted_count") or 0),
            "updated": int(record.get("updated_count") or 0),
            "deleted": int(record.get("deleted_count") or 0),
            "duplicate": int(record.get("duplicate_count") or 0),
            "stale_ignored": int(record.get("stale_count") or 0),
        },
        "checkpoint_current": False,
    }


def complete_noop_ingestion(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    ingestion_run_id: str, lease_token: str, next_cursor: str,
    credential_reference: dict, client=None,
) -> dict:
    """Settle a complete unchanged snapshot without creating a dataset revision."""
    database = client or service_supabase
    reference = credential_reference if isinstance(credential_reference, dict) else {}
    if not all(reference.get(key) is not None for key in (
        "credential_id", "credential_version", "source_revision",
    )):
        raise HTTPException(status_code=409, detail={
            "code": "provider_credential_revision_missing",
            "message": "The provider credential must be re-resolved before completion.",
        })
    rows = _rows(database.rpc("complete_noop_source_ingestion161", {
        "p_tenant_id": int(tenant_id),
        "p_project_id": _safe_uuid(project_id, detail="Data project was not found."),
        "p_source_id": _safe_uuid(source_id, detail="Data source was not found."),
        "p_actor_user_id": int(user_id),
        "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
        "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
        "p_next_cursor": str(next_cursor),
        "p_credential_id": _safe_uuid(
            reference["credential_id"], detail="Provider credential was not found.",
        ),
        "p_credential_version": int(reference["credential_version"]),
        "p_credential_revision": int(reference["source_revision"]),
    }).execute())
    if not rows:
        raise RuntimeError("No-change ingestion was not completed")
    record = rows[0]
    return {
        "persistent_dataset_id": record.get("dataset_id"),
        "dataset_version_id": None,
        "source_resource_id": record.get("source_resource_id"),
        "committed_revision": int(record.get("committed_revision") or 0),
        "ingestion_run_id": record.get("ingestion_run_id"),
        "ingestion_status": record.get("ingestion_status") or "succeeded",
        "no_changes": True,
        "checkpoint_current": True,
    }


def complete_ingestion(
    *,
    tenant_id: int,
    project_id: str,
    source_id: str,
    user_id: int,
    ingestion_run_id: str,
    display_name: str,
    artifact: dict,
    source_type: str = project_data_source_service.SOURCE_TYPE_SPREADSHEET_UPLOAD,
    lease_token: str | None = None,
    client=None,
) -> dict:
    database = client or service_supabase
    response_metadata = artifact.get("response") if isinstance(artifact.get("response"), dict) else {}
    provider_metadata = artifact.get("provider_metadata") if isinstance(artifact.get("provider_metadata"), dict) else {}
    normalized_name = str(display_name or artifact.get("original_filename") or "Dataset").strip()[:255]
    params = {
        "p_tenant_id": int(tenant_id),
        "p_project_id": _safe_uuid(project_id, detail="Data project was not found."),
        "p_source_id": _safe_uuid(source_id, detail="Data source was not found."),
        "p_user_id": int(user_id),
        "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
        "p_display_name": normalized_name or "Dataset",
        "p_storage_object_id": str(artifact["storage_object_id"]),
        "p_original_filename": str(artifact.get("original_filename") or normalized_name)[:255],
        "p_content_type": str(artifact.get("content_type") or "application/octet-stream")[:255],
        "p_file_extension": str(artifact.get("file_extension") or "")[:16],
        "p_size_bytes": int(artifact["file_size"]),
        "p_content_hash": str(artifact.get("sha256") or "") or None,
        "p_file_metadata": {
            "rows": response_metadata.get("rows"),
            "columns": response_metadata.get("columns") or [],
            "column_count": response_metadata.get("column_count"),
            "format": response_metadata.get("format"),
            "processing_mode": response_metadata.get("processing_mode"),
            **({"provider": {
                "provider_key": provider_metadata.get("provider_key"),
                "resource_type": provider_metadata.get("resource_type"),
            }} if provider_metadata else {}),
        },
        "p_run_metadata": {
            "rows": response_metadata.get("rows"),
            "column_count": response_metadata.get("column_count"),
            "format": response_metadata.get("format"),
            "size_bytes": int(artifact["file_size"]),
            **({
                "provider_key": provider_metadata.get("provider_key"),
                "resource_type": provider_metadata.get("resource_type"),
                "record_count": provider_metadata.get("record_count"),
                "page_count": provider_metadata.get("page_count"),
                "continuation_present": bool(provider_metadata.get("continuation_present")),
            } if provider_metadata else {}),
        },
    }
    rpc_name = "complete_source_ingestion149"
    if lease_token:
        params["p_lease_token"] = _safe_uuid(lease_token, detail="Ingestion lease was not found.")
        if project_data_source_service.api_data_sources_available(client=database):
            rpc_name = "complete_source_ingestion151"
        else:
            rpc_name = "complete_source_ingestion150"
    if source_type == project_data_source_service.SOURCE_TYPE_API_PROVIDER and rpc_name != "complete_source_ingestion151":
        raise HTTPException(status_code=503, detail={
            "code": "api_data_sources_upgrade_required",
            "message": "API data sources require the database upgrade.",
        })
    records = _rows(database.rpc(rpc_name, params).execute())
    if not records:
        raise RuntimeError("Ingestion metadata was not completed")
    record = records[0]
    return {
        "persistent_dataset_id": record.get("dataset_id"),
        "dataset_version_id": record.get("version_id"),
        "version_number": int(record.get("version_number") or 1),
        "project_id": project_id,
        "source_id": source_id,
        "ingestion_run_id": record.get("ingestion_run_id"),
        "ingestion_status": record.get("ingestion_status") or "succeeded",
    }


def fail_ingestion(
    *,
    tenant_id: int,
    project_id: str,
    source_id: str,
    user_id: int,
    ingestion_run_id: str,
    failure_code: str,
    lease_token: str | None = None,
    client=None,
) -> None:
    database = client or service_supabase
    normalized_code = str(failure_code or "ingestion_failed").strip().lower()
    if normalized_code not in FAILURE_CODES:
        normalized_code = "ingestion_failed"
    params = {
            "p_tenant_id": int(tenant_id),
            "p_project_id": _safe_uuid(project_id, detail="Data project was not found."),
            "p_source_id": _safe_uuid(source_id, detail="Data source was not found."),
            "p_user_id": int(user_id),
            "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
            "p_failure_code": normalized_code,
    }
    rpc_name = "fail_source_ingestion149"
    if lease_token:
        params["p_lease_token"] = _safe_uuid(lease_token, detail="Ingestion lease was not found.")
        rpc_name = "fail_source_ingestion150"
    database.rpc(rpc_name, params).execute()


def heartbeat_ingestion(*, tenant_id: int, ingestion_run_id: str, lease_token: str, client=None) -> None:
    (client or service_supabase).rpc("heartbeat_source_ingestion150", {
        "p_tenant_id": int(tenant_id),
        "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
        "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
        "p_lease_seconds": DEFAULT_UPLOAD_LEASE_SECONDS,
    }).execute()


def attach_storage_reservation(*, tenant_id: int, ingestion_run_id: str, lease_token: str,
                               storage_reservation_id: str, client=None) -> None:
    (client or service_supabase).rpc("attach_source_ingestion_reservation150", {
        "p_tenant_id": int(tenant_id),
        "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
        "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
        "p_storage_reservation_id": _safe_uuid(storage_reservation_id, detail="Storage reservation was not found."),
    }).execute()


def attach_storage_object(*, tenant_id: int, ingestion_run_id: str, lease_token: str,
                          storage_object_id: str, client=None) -> None:
    (client or service_supabase).rpc("attach_source_ingestion_storage150", {
        "p_tenant_id": int(tenant_id),
        "p_ingestion_run_id": _safe_uuid(ingestion_run_id),
        "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
        "p_storage_object_id": _safe_uuid(storage_object_id, detail="Storage object was not found."),
    }).execute()


def storage_object_attachment_state(*, tenant_id: int, ingestion_run_id: str,
                                    lease_token: str, storage_object_id: str,
                                    client=None) -> bool | None:
    """Return True/False only when the exact fenced attachment can be read authoritatively."""
    try:
        rows = _rows(
            (client or service_supabase).table("data_source_ingestion_runs")
            .select("status,lease_token,storage_object_id")
            .eq("id", _safe_uuid(ingestion_run_id))
            .eq("tenant_id", int(tenant_id))
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    if not rows:
        return None
    current = rows[0]
    if current.get("status") == "succeeded":
        return current.get("storage_object_id") == storage_object_id
    if current.get("lease_token") != lease_token:
        return None
    return current.get("storage_object_id") == storage_object_id


def recover_completed_ingestion(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    ingestion_run_id: str, client=None,
) -> dict | bool | None:
    """Resolve an ambiguous completion without exposing or releasing its storage object."""
    try:
        current = get_ingestion(
            tenant_id=tenant_id,
            project_id=project_id,
            source_id=source_id,
            user_id=user_id,
            ingestion_run_id=ingestion_run_id,
            client=client,
        )
    except Exception:
        return None
    if current.get("status") == "succeeded":
        return {
            "persistent_dataset_id": current.get("result_dataset_id"),
            "dataset_version_id": current.get("result_version_id"),
            "version_number": 1 if current.get("result_version_id") else None,
            "committed_revision": current.get("committed_revision"),
            "source_resource_id": current.get("source_resource_id"),
            "checkpoint_current": bool(current.get("result_version_id")),
            "project_id": project_id,
            "source_id": source_id,
            "ingestion_run_id": current.get("id"),
            "ingestion_status": "succeeded",
            "completion_recovered": True,
        }
    if current.get("status") in {"pending", "processing", "failed"}:
        return False
    return None


def _settle_reconciliation(*, run_id: str, lease_token: str, outcome: str, code: str,
                           client, retry_seconds: int = 86400) -> dict:
    records = _rows(client.rpc("settle_source_ingestion_reconciliation150", {
        "p_ingestion_run_id": _safe_uuid(run_id),
        "p_lease_token": _safe_uuid(lease_token, detail="Ingestion lease was not found."),
        "p_outcome": outcome,
        "p_code": code,
        "p_retry_seconds": max(300, min(int(retry_seconds), 604800)),
    }).execute())
    if not records:
        raise RuntimeError("Ingestion reconciliation was not settled")
    return records[0]


def _safe_private_upload_path(*, tenant_id: int, user_id: int, storage_key: str) -> Path | None:
    parts = Path(str(storage_key or "")).parts
    if len(parts) != 3 or parts[0] != f"tenant_{tenant_id}" or parts[1] != f"user_{user_id}":
        return None
    filename = parts[2]
    if not re.fullmatch(r"[0-9a-f]{32}\.(csv|xls|xlsx)", filename):
        return None
    root = data_services.get_user_upload_dir(str(tenant_id), str(user_id)).resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root:
        return None
    return candidate


def _query_one(client, table: str, fields: str, **equals) -> dict | None:
    query = client.table(table).select(fields)
    for field, value in equals.items():
        query = query.eq(field, value)
    rows = _rows(query.limit(1).execute())
    return rows[0] if rows else None


def reconcile_claimed_ingestion(run: dict, *, client=None) -> dict:
    """Reconcile one database-fenced run without inferring failure from age alone."""
    database = client or service_supabase
    run_id = _safe_uuid(run.get("id"))
    lease_token = _safe_uuid(run.get("lease_token"), detail="Ingestion lease was not found.")
    tenant_id = int(run["tenant_id"])
    user_id = int(run["initiated_by_user_id"])

    current = _query_one(
        database, "data_source_ingestion_runs", "*", id=run_id, tenant_id=tenant_id
    )
    if not current:
        return {"id": run_id, "outcome": "missing"}
    if current.get("status") == "succeeded":
        return {"id": run_id, "outcome": "succeeded"}
    if current.get("status") != "processing" or current.get("lease_token") != lease_token:
        return {"id": run_id, "outcome": "fenced"}
    if current.get("result_dataset_id") or current.get("result_version_id"):
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="inconsistent_result_lineage", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "inconsistent_result_lineage"}

    reservation_id = current.get("storage_reservation_id")
    if not reservation_id:
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="storage_reservation_untracked", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "storage_reservation_untracked"}

    shared_enabled = shared_immutable_storage_available(client=database)
    reservation_fields = "id,tenant_id,user_id,category,status"
    if shared_enabled:
        reservation_fields += (",storage_backend,storage_bucket,provider_object_key,"
                               "expected_size_bytes,expected_sha256,transfer_state")
    reservation = _query_one(
        database, "storage_reservations", reservation_fields,
        id=reservation_id, tenant_id=tenant_id, user_id=user_id, category="dataset",
    )
    if not reservation:
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="storage_reservation_missing", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "storage_reservation_missing"}

    if reservation.get("status") == "reserved":
        shared_descriptor = None
        if shared_enabled and reservation.get("storage_backend") == "supabase_private":
            try:
                shared_descriptor = ImmutableObject(
                    backend="supabase_private", bucket=reservation["storage_bucket"],
                    object_key=reservation["provider_object_key"],
                    size_bytes=int(reservation["expected_size_bytes"]),
                    sha256=reservation["expected_sha256"],
                )
                configured_store(client=database).read(
                    tenant_id=tenant_id, descriptor=shared_descriptor,
                )
            except ImmutableObjectError as error:
                if error.category == ObjectErrorCategory.MISSING:
                    shared_descriptor = None
                else:
                    _settle_reconciliation(
                        run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                        code="immutable_storage_unverifiable", client=database,
                    )
                    return {"id": run_id, "outcome": "ambiguous",
                            "code": "immutable_storage_unverifiable"}
        try:
            finish_storage(reservation_id=str(reservation_id), succeeded=False, client=database)
        except Exception:
            _settle_reconciliation(
                run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                code="reservation_release_failed", client=database,
            )
            return {"id": run_id, "outcome": "ambiguous", "code": "reservation_release_failed"}
        if shared_descriptor is not None:
            try:
                configured_store(client=database).delete(
                    tenant_id=tenant_id, descriptor=shared_descriptor,
                )
            except ImmutableObjectError:
                _settle_reconciliation(
                    run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                    code="immutable_storage_cleanup_failed", client=database,
                )
                return {"id": run_id, "outcome": "ambiguous",
                        "code": "immutable_storage_cleanup_failed"}
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="failed",
            code="abandoned_before_storage_commit", client=database,
        )
        return {"id": run_id, "outcome": "failed", "code": "abandoned_before_storage_commit"}

    if reservation.get("status") in {"released", "expired"}:
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="failed",
            code="storage_not_committed", client=database,
        )
        return {"id": run_id, "outcome": "failed", "code": "storage_not_committed"}

    if reservation.get("status") != "committed":
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="storage_reservation_state_unknown", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "storage_reservation_state_unknown"}

    object_fields = "id,reservation_id,tenant_id,user_id,category,storage_key,status"
    if shared_enabled:
        object_fields += (",storage_backend,storage_bucket,provider_object_key,"
                          "verified_size_bytes,verified_sha256,integrity_verified_at")
    storage_object = _query_one(
        database, "storage_objects", object_fields,
        reservation_id=reservation_id, tenant_id=tenant_id, user_id=user_id, category="dataset",
    )
    if not storage_object:
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="committed_storage_missing", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "committed_storage_missing"}

    if not current.get("storage_object_id"):
        try:
            database.rpc("attach_source_ingestion_storage150", {
                "p_tenant_id": tenant_id,
                "p_ingestion_run_id": run_id,
                "p_lease_token": lease_token,
                "p_storage_object_id": storage_object["id"],
            }).execute()
        except Exception:
            _settle_reconciliation(
                run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                code="storage_attachment_failed", client=database,
            )
            return {"id": run_id, "outcome": "ambiguous", "code": "storage_attachment_failed"}

    storage_key = str(storage_object.get("storage_key") or "")
    if storage_object.get("status") == "active":
        try:
            released = release_storage(
                tenant_id=tenant_id, category="dataset", storage_key=storage_key, client=database
            )
        except Exception:
            released = False
        if not released:
            refreshed = _query_one(database, "storage_objects", "status", id=storage_object["id"])
            if not refreshed or refreshed.get("status") != "deleted":
                _settle_reconciliation(
                    run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                    code="storage_release_failed", client=database,
                )
                return {"id": run_id, "outcome": "ambiguous", "code": "storage_release_failed"}
    elif storage_object.get("status") != "deleted":
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="storage_object_state_unknown", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "storage_object_state_unknown"}

    if shared_enabled and storage_object.get("storage_backend") == "supabase_private":
        try:
            configured_store(client=database).delete(
                tenant_id=tenant_id, descriptor=descriptor_from_row(storage_object),
            )
        except ImmutableObjectError:
            _settle_reconciliation(
                run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                code="immutable_storage_cleanup_failed", client=database,
            )
            return {"id": run_id, "outcome": "ambiguous",
                    "code": "immutable_storage_cleanup_failed"}
        upload_path = None
    else:
        upload_path = _safe_private_upload_path(
            tenant_id=tenant_id, user_id=user_id, storage_key=storage_key
        )
    if upload_path is None and not (
        shared_enabled and storage_object.get("storage_backend") == "supabase_private"
    ):
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="storage_path_invalid", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "storage_path_invalid"}
    try:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
    except OSError:
        _settle_reconciliation(
            run_id=run_id, lease_token=lease_token, outcome="ambiguous",
            code="file_cleanup_failed", client=database,
        )
        return {"id": run_id, "outcome": "ambiguous", "code": "file_cleanup_failed"}

    _settle_reconciliation(
        run_id=run_id, lease_token=lease_token, outcome="failed",
        code="abandoned_after_storage_commit", client=database,
    )
    return {"id": run_id, "outcome": "failed", "code": "abandoned_after_storage_commit"}


def reconcile_stale_ingestions(*, worker_id: str, limit: int = 20,
                               lease_seconds: int = 900, client=None) -> dict:
    """Run one bounded, service-role-only reconciliation batch."""
    database = client or service_supabase
    if not ingestion_recovery_available(client=database):
        return {"available": False, "claimed": 0, "results": []}
    claimed = _rows(database.rpc("claim_stale_source_ingestions150", {
        "p_worker_id": str(worker_id or "source-ingestion-reconciler")[:120],
        "p_limit": max(1, min(int(limit), 100)),
        "p_lease_seconds": max(60, min(int(lease_seconds), 3600)),
    }).execute())
    results = []
    for run in claimed:
        try:
            results.append(reconcile_claimed_ingestion(run, client=database))
        except Exception as error:
            run_id = str(run.get("id") or "")
            lease_token = str(run.get("lease_token") or "")
            try:
                _settle_reconciliation(
                    run_id=run_id, lease_token=lease_token, outcome="ambiguous",
                    code="reconciliation_internal_error", client=database,
                )
                outcome = "ambiguous"
            except Exception:
                outcome = "error"
                logger.exception(
                    "data.source_ingestion.reconciliation_settlement_failed",
                    extra={"ingestion_run_id": run_id},
                )
            logger.error(
                "data.source_ingestion.reconciliation_failed",
                extra={"ingestion_run_id": run_id, "error_type": type(error).__name__},
            )
            results.append({"id": run_id, "outcome": outcome,
                            "code": "reconciliation_internal_error"})
    return {"available": True, "claimed": len(claimed), "results": results}


def list_ingestions(
    *,
    tenant_id: int,
    project_id: str,
    source_id: str,
    user_id: int,
    limit: int,
    offset: int,
    client=None,
) -> dict:
    database = client or service_supabase
    project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(user_id),
        source_id=source_id, client=database,
    )
    fields = (INGESTION_FIELDS_152 if incremental_ingestion_available(client=database)
              else INGESTION_FIELDS_150 if ingestion_recovery_available(client=database)
              else INGESTION_FIELDS_149)
    rows = _rows(
        database.table("data_source_ingestion_runs")
        .select(fields)
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id, detail="Data project was not found."))
        .eq("source_id", _safe_uuid(source_id, detail="Data source was not found."))
        .eq("initiated_by_user_id", int(user_id))
        .order("created_at", desc=True)
        .range(int(offset), int(offset) + int(limit))
        .execute()
    )
    has_more = len(rows) > limit
    return {"items": rows[:limit], "pagination": {"limit": limit, "offset": offset, "has_more": has_more}}


def list_source_resource_statuses(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    limit: int = 100, client=None,
) -> dict:
    """Return scoped, secret-free freshness state for a Data Source detail view."""
    database = client or service_supabase
    source = project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(user_id),
        source_id=source_id, client=database,
    )
    if not incremental_ingestion_available(client=database):
        return {
            "available": False,
            "provider_registered": False,
            "checkpoint_capable": False,
            "items": [],
            "has_more": False,
        }

    bounded_limit = max(1, min(int(limit), 100))
    resources = _rows(
        database.table("data_source_resources")
        .select(
            "id,resource_key,dataset_id,committed_revision,"
            "latest_checkpoint_version_id,created_at,updated_at"
        )
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id, detail="Data project was not found."))
        .eq("source_id", _safe_uuid(source_id, detail="Data source was not found."))
        .order("resource_key")
        .limit(bounded_limit + 1)
        .execute()
    )
    visible = resources[:bounded_limit]
    visible_ids = {str(item.get("id")) for item in visible}

    ingestions = _rows(
        database.table("data_source_ingestion_runs")
        .select(
            "id,source_resource_id,status,completed_at,failure_code,"
            "committed_revision,created_at,updated_at"
        )
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id, detail="Data project was not found."))
        .eq("source_id", _safe_uuid(source_id, detail="Data source was not found."))
        .eq("ingestion_kind", "incremental")
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    checkpoints = _rows(
        database.table("data_dataset_checkpoints")
        .select(
            "id,source_resource_id,target_revision,status,version_id,"
            "failure_code,created_at,completed_at"
        )
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id, detail="Data project was not found."))
        .eq("source_id", _safe_uuid(source_id, detail="Data source was not found."))
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )

    latest_ingestion: dict[str, dict] = {}
    latest_success: dict[str, dict] = {}
    for ingestion in ingestions:
        resource_id = str(ingestion.get("source_resource_id") or "")
        if resource_id not in visible_ids:
            continue
        latest_ingestion.setdefault(resource_id, ingestion)
        if ingestion.get("status") == "succeeded":
            latest_success.setdefault(resource_id, ingestion)

    latest_checkpoint: dict[str, dict] = {}
    for checkpoint in checkpoints:
        resource_id = str(checkpoint.get("source_resource_id") or "")
        if resource_id in visible_ids:
            latest_checkpoint.setdefault(resource_id, checkpoint)

    from services.provider_registry import resource_supported
    provider_key = str(source.get("provider_key") or "")
    resource_type = str(source.get("resource_type") or "")
    return {
        "available": True,
        "provider_registered": resource_supported(provider_key, resource_type),
        "checkpoint_capable": True,
        "items": [
            {
                **resource,
                "latest_ingestion": latest_ingestion.get(str(resource.get("id"))),
                "latest_successful_ingestion": latest_success.get(str(resource.get("id"))),
                "latest_checkpoint": latest_checkpoint.get(str(resource.get("id"))),
            }
            for resource in visible
        ],
        "has_more": len(resources) > bounded_limit,
    }


def get_ingestion(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    ingestion_run_id: str, client=None,
) -> dict:
    database = client or service_supabase
    project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(user_id),
        source_id=source_id, client=database,
    )
    fields = (INGESTION_FIELDS_152 if incremental_ingestion_available(client=database)
              else INGESTION_FIELDS_150 if ingestion_recovery_available(client=database)
              else INGESTION_FIELDS_149)
    rows = _rows(
        database.table("data_source_ingestion_runs")
        .select(fields)
        .eq("id", _safe_uuid(ingestion_run_id))
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id, detail="Data project was not found."))
        .eq("source_id", _safe_uuid(source_id, detail="Data source was not found."))
        .eq("initiated_by_user_id", int(user_id))
        .limit(1)
        .execute()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Ingestion run was not found.")
    return rows[0]


def list_incremental_records(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    user_id: int, limit: int, offset: int, include_deleted: bool = False,
    client=None,
) -> dict:
    database = client or service_supabase
    if not incremental_ingestion_available(client=database):
        raise HTTPException(status_code=503, detail={
            "code": "incremental_ingestion_upgrade_required",
            "message": "Incremental records require the database upgrade.",
        })
    project_data_source_service.get_project_data_source(
        tenant_id=tenant_id, project_id=project_id, user_id=user_id,
        source_id=source_id, client=database,
    )
    resources = _rows(
        database.table("data_source_resources")
        .select(
            "id,resource_key,dataset_id,committed_revision,committed_cursor,"
            "latest_checkpoint_version_id"
        )
        .eq("id", _safe_uuid(resource_id, detail="Source resource was not found."))
        .eq("tenant_id", tenant_id)
        .eq("project_id", _safe_uuid(project_id, detail="Data project was not found."))
        .eq("source_id", _safe_uuid(source_id, detail="Data source was not found."))
        .limit(1).execute()
    )
    if not resources or not resources[0].get("dataset_id"):
        raise HTTPException(status_code=404, detail="Source resource was not found.")
    resource = resources[0]
    checkpoints = _rows(
        database.table("data_dataset_checkpoints")
        .select("target_revision,version_id")
        .eq("tenant_id", tenant_id).eq("dataset_id", resource["dataset_id"])
        .eq("status", "ready").order("target_revision", desc=True).limit(1).execute()
    )
    resource["latest_checkpoint_revision"] = (
        checkpoints[0].get("target_revision") if checkpoints else None
    )
    query = (
        database.table("data_dataset_current_records")
        .select(
            "source_record_id,payload,source_order,is_deleted,schema_fingerprint,"
            "last_committed_revision,updated_at"
        )
        .eq("tenant_id", tenant_id).eq("dataset_id", resource["dataset_id"])
    )
    if not include_deleted:
        query = query.eq("is_deleted", False)
    records = _rows(
        query.order("source_record_id")
        .range(offset, offset + limit).execute()
    )
    has_more = len(records) > limit
    return {
        "resource": resource,
        "items": records[:limit],
        "pagination": {"limit": limit, "offset": offset, "has_more": has_more},
        "checkpoint_current": bool(
            resource.get("latest_checkpoint_version_id")
            and resource.get("committed_revision") == resource.get("latest_checkpoint_revision")
        ),
    }
