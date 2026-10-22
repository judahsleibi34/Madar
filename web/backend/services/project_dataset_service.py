import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from database import service_supabase
from services.immutable_object_storage import configured_store, descriptor_from_row
from services.upload_config import get_data_upload_dir, safe_scope_part


DATA_PROJECT_KIND = "data"
DATASET_STATUS_ACTIVE = "active"
PROJECT_DATASETS_SCHEMA = 147
SHARED_IMMUTABLE_STORAGE_SCHEMA = 154


def _rows(response) -> list[dict[str, Any]]:
    return list(getattr(response, "data", None) or [])


def _safe_uuid(value: object, *, detail: str = "Data project was not found.") -> str:
    normalized = str(value or "").strip().lower()
    if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        normalized,
    ):
        raise HTTPException(status_code=404, detail=detail)
    return normalized


def project_datasets_available(*, client=None) -> bool:
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
        return bool(rows and int(rows[0].get("schema_version")) >= PROJECT_DATASETS_SCHEMA)
    except (TypeError, ValueError):
        return False


def _shared_immutable_storage_available(*, client=None) -> bool:
    database = client or service_supabase
    rows = _rows(database.table("application_schema_state").select("schema_version")
                 .eq("contract_key", "core").limit(1).execute())
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= SHARED_IMMUTABLE_STORAGE_SCHEMA)
    except (TypeError, ValueError):
        return False


def _storage_fields(*, shared: bool) -> str:
    fields = "id,tenant_id,user_id,category,storage_key,status"
    if shared:
        fields += ",storage_backend,storage_bucket,provider_object_key,verified_size_bytes,verified_sha256,integrity_verified_at"
    return fields


def _hydrate_shared_object(*, row: dict, tenant_id: int, user_id: int, client) -> None:
    if row.get("storage_backend") != "supabase_private":
        return
    descriptor = descriptor_from_row(row)
    filename = Path(str(row.get("storage_key") or "")).name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=404, detail="Dataset version was not found.")
    directory = get_data_upload_dir() / safe_scope_part("tenant", tenant_id) / safe_scope_part("user", user_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = (directory / filename).resolve()
    if target.parent != directory.resolve():
        raise HTTPException(status_code=404, detail="Dataset version was not found.")
    temporary = directory / f".{filename}.{uuid4().hex}.download"
    try:
        configured_store(client=client).download_to_path(
            tenant_id=tenant_id, descriptor=descriptor, target_path=temporary,
        )
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def require_project_datasets_schema(*, client=None) -> None:
    if not project_datasets_available(client=client):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "project_datasets_upgrade_required",
                "message": "Persistent project datasets require the database upgrade.",
            },
        )


def require_data_project(project_id: str, *, tenant_id: int, client=None) -> dict:
    database = client or service_supabase
    normalized_id = _safe_uuid(project_id)
    result = (
        database.table("builder_projects")
        .select("id,tenant_id,name,status,draft_schema")
        .eq("id", normalized_id)
        .eq("tenant_id", int(tenant_id))
        .neq("status", "archived")
        .limit(1)
        .execute()
    )
    projects = _rows(result)
    if not projects:
        raise HTTPException(status_code=404, detail="Data project was not found.")
    project = projects[0]
    schema = project.get("draft_schema") if isinstance(project.get("draft_schema"), dict) else {}
    if schema.get("workspaceKind") != DATA_PROJECT_KIND:
        raise HTTPException(status_code=404, detail="Data project was not found.")
    return project


def create_initial_dataset_version(
    *,
    tenant_id: int,
    project_id: str,
    creator_user_id: int,
    display_name: str,
    artifact: dict,
    client=None,
) -> dict:
    database = client or service_supabase
    normalized_name = str(display_name or artifact.get("original_filename") or "Dataset").strip()
    if not normalized_name:
        normalized_name = "Dataset"
    normalized_name = normalized_name[:255]
    response_metadata = artifact.get("response") if isinstance(artifact.get("response"), dict) else {}
    params = {
        "p_tenant_id": int(tenant_id),
        "p_project_id": _safe_uuid(project_id),
        "p_creator_user_id": int(creator_user_id),
        "p_display_name": normalized_name,
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
        },
    }
    result = database.rpc("create_project_dataset_with_version147", params).execute()
    records = _rows(result)
    if not records:
        raise RuntimeError("Dataset metadata was not created")
    record = records[0]
    return {
        "persistent_dataset_id": record.get("dataset_id"),
        "dataset_version_id": record.get("version_id"),
        "version_number": int(record.get("version_number") or 1),
        "project_id": project_id,
    }


def _version_projection(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "version_number": row.get("version_number"),
        "version_kind": row.get("version_kind"),
        "original_filename": row.get("original_filename"),
        "content_type": row.get("content_type"),
        "file_extension": row.get("file_extension"),
        "size_bytes": row.get("size_bytes"),
        "content_hash": row.get("content_hash"),
        "file_metadata": row.get("file_metadata") or {},
        "created_at": row.get("created_at"),
    }


def list_project_datasets(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    limit: int,
    offset: int,
    client=None,
) -> dict:
    database = client or service_supabase
    require_data_project(project_id, tenant_id=tenant_id, client=database)
    query = (
        database.table("data_datasets")
        .select("id,project_id,display_name,status,created_at,updated_at")
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id))
        .eq("creator_user_id", int(user_id))
        .eq("status", DATASET_STATUS_ACTIVE)
        .order("updated_at", desc=True)
        .range(int(offset), int(offset) + int(limit))
    )
    datasets = _rows(query.execute())
    has_more = len(datasets) > limit
    datasets = datasets[:limit]
    dataset_ids = [row["id"] for row in datasets]
    latest_by_dataset: dict[str, dict] = {}
    if dataset_ids:
        versions = _rows(
            database.table("data_dataset_versions")
            .select(
                "id,dataset_id,version_number,version_kind,original_filename,content_type,"
                "file_extension,size_bytes,content_hash,file_metadata,created_at"
            )
            .in_("dataset_id", dataset_ids)
            .eq("tenant_id", int(tenant_id))
            .order("version_number", desc=True)
            .execute()
        )
        for version in versions:
            latest_by_dataset.setdefault(str(version.get("dataset_id")), version)
    return {
        "items": [
            {**dataset, "latest_version": _version_projection(latest_by_dataset.get(str(dataset["id"])))}
            for dataset in datasets
        ],
        "pagination": {"limit": limit, "offset": offset, "has_more": has_more},
    }


def reopen_project_dataset(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    dataset_id: str,
    client=None,
) -> dict:
    database = client or service_supabase
    require_data_project(project_id, tenant_id=tenant_id, client=database)
    normalized_dataset_id = _safe_uuid(dataset_id)
    datasets = _rows(
        database.table("data_datasets")
        .select("id,project_id,display_name,status,created_at,updated_at")
        .eq("id", normalized_dataset_id)
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project_id))
        .eq("creator_user_id", int(user_id))
        .eq("status", DATASET_STATUS_ACTIVE)
        .limit(1)
        .execute()
    )
    if not datasets:
        raise HTTPException(status_code=404, detail="Dataset was not found.")
    versions = _rows(
        database.table("data_dataset_versions")
        .select("*")
        .eq("tenant_id", int(tenant_id))
        .eq("dataset_id", normalized_dataset_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    if not versions:
        raise HTTPException(status_code=404, detail="Dataset was not found.")
    version = versions[0]
    shared_storage = _shared_immutable_storage_available(client=database)
    storage_rows = _rows(
        database.table("storage_objects")
        .select(_storage_fields(shared=shared_storage))
        .eq("id", version.get("storage_object_id"))
        .eq("tenant_id", int(tenant_id))
        .eq("user_id", int(user_id))
        .eq("category", "dataset")
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not storage_rows:
        raise HTTPException(status_code=404, detail="Dataset was not found.")
    if shared_storage:
        _hydrate_shared_object(
            row=storage_rows[0], tenant_id=int(tenant_id), user_id=int(user_id),
            client=database,
        )
    storage_key = str(storage_rows[0].get("storage_key") or "")
    storage_name = Path(storage_key).name
    if not storage_name:
        raise HTTPException(status_code=404, detail="Dataset was not found.")
    return {
        "dataset": datasets[0],
        "version": _version_projection(version),
        "storage_identifier": storage_name,
    }


def resolve_project_dataset_version(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    dataset_id: str,
    version_id: str,
    client=None,
) -> dict:
    """Resolve one authorized immutable version without exposing its storage key."""
    database = client or service_supabase
    require_data_project(project_id, tenant_id=tenant_id, client=database)
    normalized_project_id = _safe_uuid(project_id)
    normalized_dataset_id = _safe_uuid(
        dataset_id,
        detail="Dataset version was not found.",
    )
    normalized_version_id = _safe_uuid(
        version_id,
        detail="Dataset version was not found.",
    )
    datasets = _rows(
        database.table("data_datasets")
        .select("id,project_id,display_name,status,created_at,updated_at")
        .eq("id", normalized_dataset_id)
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", normalized_project_id)
        .eq("creator_user_id", int(user_id))
        .eq("status", DATASET_STATUS_ACTIVE)
        .limit(1)
        .execute()
    )
    if not datasets:
        raise HTTPException(status_code=404, detail="Dataset version was not found.")

    versions = _rows(
        database.table("data_dataset_versions")
        .select("*")
        .eq("id", normalized_version_id)
        .eq("tenant_id", int(tenant_id))
        .eq("dataset_id", normalized_dataset_id)
        .limit(1)
        .execute()
    )
    if not versions:
        raise HTTPException(status_code=404, detail="Dataset version was not found.")

    version = versions[0]
    shared_storage = _shared_immutable_storage_available(client=database)
    storage_rows = _rows(
        database.table("storage_objects")
        .select(_storage_fields(shared=shared_storage))
        .eq("id", version.get("storage_object_id"))
        .eq("tenant_id", int(tenant_id))
        .eq("user_id", int(user_id))
        .eq("category", "dataset")
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not storage_rows:
        raise HTTPException(status_code=404, detail="Dataset version was not found.")

    if shared_storage:
        _hydrate_shared_object(
            row=storage_rows[0], tenant_id=int(tenant_id), user_id=int(user_id),
            client=database,
        )

    storage_name = Path(str(storage_rows[0].get("storage_key") or "")).name
    if not storage_name:
        raise HTTPException(status_code=404, detail="Dataset version was not found.")

    return {
        "dataset": datasets[0],
        "version": _version_projection(version),
        "storage_identifier": storage_name,
    }
