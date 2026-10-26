import os
import re
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services import project_dataset_service


DATA_SOURCES_SCHEMA = 148
API_DATA_SOURCES_SCHEMA = 151
INCREMENTAL_DATA_SOURCES_SCHEMA = 152
CREDENTIAL_VAULT_SCHEMA = 155
AUTOMATIC_SYNC_SCHEMA = 156
GOOGLE_SHEETS_SCHEMA = 157
WEBHOOK_INGESTION_SCHEMA = 158
SOURCE_TYPE_SPREADSHEET_UPLOAD = "spreadsheet_upload"
SOURCE_TYPE_API_PROVIDER = "api_provider"
SOURCE_TYPES = {SOURCE_TYPE_SPREADSHEET_UPLOAD, SOURCE_TYPE_API_PROVIDER}
SOURCE_STATUSES = {"active", "archived"}
SOURCE_FIELDS_148 = (
    "id,project_id,source_type,display_name,status,sync_mode,sync_state,"
    "latest_dataset_id,latest_version_id,last_ingested_at,last_successful_sync_at,"
    "last_error_code,created_at,updated_at"
)
SOURCE_FIELDS_151 = SOURCE_FIELDS_148 + ",provider_key,resource_type"


def _rows(response) -> list[dict[str, Any]]:
    return list(getattr(response, "data", None) or [])


def _safe_uuid(value: object, *, detail: str = "Data source was not found.") -> str:
    normalized = str(value or "").strip().lower()
    if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        normalized,
    ):
        raise HTTPException(status_code=404, detail=detail)
    return normalized


def _schema_version(*, client=None) -> int:
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
        return int(rows[0].get("schema_version")) if rows else 0
    except (TypeError, ValueError):
        return 0


def project_data_sources_available(*, client=None) -> bool:
    return _schema_version(client=client) >= DATA_SOURCES_SCHEMA


def api_data_sources_available(*, client=None) -> bool:
    return _schema_version(client=client) >= API_DATA_SOURCES_SCHEMA


def project_data_source_capabilities(
    *, tenant_id: int, project_id: str, user_id: int, client=None,
) -> dict:
    """Return project-scoped, secret-free Data Sources UI capabilities."""
    database = client or service_supabase
    project_dataset_service.require_data_project(
        project_id, tenant_id=int(tenant_id), client=database,
    )
    version = _schema_version(client=database)
    from services.provider_registry import public_provider_capabilities
    providers = public_provider_capabilities() if version >= API_DATA_SOURCES_SCHEMA else []
    if version < GOOGLE_SHEETS_SCHEMA:
        providers = [item for item in providers if item.get("key") != "google_sheets"]
    return {
        "source_registry_available": version >= DATA_SOURCES_SCHEMA,
        "api_sources_available": version >= API_DATA_SOURCES_SCHEMA,
        "incremental_resources_available": version >= INCREMENTAL_DATA_SOURCES_SCHEMA,
        "credential_vault_available": version >= CREDENTIAL_VAULT_SCHEMA,
        "automatic_sync_available": version >= AUTOMATIC_SYNC_SCHEMA,
        "google_sheets_available": version >= GOOGLE_SHEETS_SCHEMA and any(
            item.get("key") == "google_sheets" for item in providers
        ),
        "webhook_ingestion_available": version >= WEBHOOK_INGESTION_SCHEMA and any(
            item.get("webhook", {}).get("supported") for item in providers
        ),
        "providers": providers,
    }


def synthetic_api_provider_enabled() -> bool:
    return str(os.getenv("APP_ENV") or "").strip().lower() in {"development", "test"}


def _source_fields(*, client=None) -> str:
    return SOURCE_FIELDS_151 if api_data_sources_available(client=client) else SOURCE_FIELDS_148


def require_project_data_sources_schema(*, client=None) -> None:
    if not project_data_sources_available(client=client):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "project_data_sources_upgrade_required",
                "message": "Persistent project data sources require the database upgrade.",
            },
        )


def _normalize_name(value: object) -> str:
    name = str(value or "").strip()
    if not name or len(name) > 255:
        raise HTTPException(status_code=422, detail="Data source name must be between 1 and 255 characters.")
    return name


def _require_supported_type(value: object) -> str:
    source_type = str(value or "").strip().lower()
    if source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=422, detail="Data source type is not supported.")
    return source_type


def _duplicate_exists(
    *,
    database,
    tenant_id: int,
    project_id: str,
    source_type: str,
    display_name: str,
) -> bool:
    result = (
        database.table("data_sources")
        .select("id")
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", project_id)
        .eq("source_type", source_type)
        .eq("status", "active")
        .eq("display_name_key", display_name.lower())
        .limit(1)
        .execute()
    )
    return bool(_rows(result))


def create_project_data_source(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    source_type: str,
    display_name: str,
    provider_key: str | None = None,
    resource_type: str | None = None,
    client=None,
) -> dict:
    database = client or service_supabase
    project = project_dataset_service.require_data_project(
        project_id,
        tenant_id=int(tenant_id),
        client=database,
    )
    normalized_project_id = _safe_uuid(project.get("id"))
    normalized_type = _require_supported_type(source_type)
    normalized_name = _normalize_name(display_name)
    normalized_provider = None
    normalized_resource = None
    if normalized_type == SOURCE_TYPE_API_PROVIDER:
        if not api_data_sources_available(client=database):
            raise HTTPException(status_code=503, detail={
                "code": "api_data_sources_upgrade_required",
                "message": "API data sources require the database upgrade.",
            })
        normalized_provider = str(provider_key or "").strip().lower()
        normalized_resource = str(resource_type or "").strip().lower()
        from services.provider_registry import resource_supported
        supported_fixture = (
            (normalized_provider == "synthetic_orders" and normalized_resource == "orders")
            or resource_supported(normalized_provider, normalized_resource)
        )
        if not supported_fixture:
            raise HTTPException(status_code=422, detail="API provider or resource type is not supported.")
        if normalized_provider == "synthetic_orders" and not synthetic_api_provider_enabled():
            raise HTTPException(status_code=404, detail="API provider was not found.")
    elif provider_key is not None or resource_type is not None:
        raise HTTPException(status_code=422, detail="Spreadsheet sources cannot include provider settings.")
    if _duplicate_exists(
        database=database,
        tenant_id=int(tenant_id),
        project_id=normalized_project_id,
        source_type=normalized_type,
        display_name=normalized_name,
    ):
        raise HTTPException(status_code=409, detail="An active data source with this name already exists.")

    payload = {
        "tenant_id": int(tenant_id),
        "project_id": normalized_project_id,
        "creator_user_id": int(user_id),
        "source_type": normalized_type,
        "display_name": normalized_name,
        "status": "active",
        "sync_mode": "manual",
        "sync_state": "idle",
    }
    if normalized_type == SOURCE_TYPE_API_PROVIDER:
        payload.update({"provider_key": normalized_provider, "resource_type": normalized_resource})
    try:
        created = _rows(database.table("data_sources").insert(payload).execute())
    except Exception:
        if _duplicate_exists(
            database=database,
            tenant_id=int(tenant_id),
            project_id=normalized_project_id,
            source_type=normalized_type,
            display_name=normalized_name,
        ):
            raise HTTPException(
                status_code=409,
                detail="An active data source with this name already exists.",
            )
        raise
    if not created:
        raise RuntimeError("Data source was not created")
    return {key: created[0].get(key) for key in _source_fields(client=database).split(",")}


def list_project_data_sources(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    limit: int,
    offset: int,
    client=None,
) -> dict:
    database = client or service_supabase
    project = project_dataset_service.require_data_project(
        project_id,
        tenant_id=int(tenant_id),
        client=database,
    )
    rows = _rows(
        database.table("data_sources")
        .select(_source_fields(client=database))
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project.get("id")))
        .eq("creator_user_id", int(user_id))
        .eq("status", "active")
        .order("updated_at", desc=True)
        .range(int(offset), int(offset) + int(limit))
        .execute()
    )
    has_more = len(rows) > limit
    return {
        "items": rows[:limit],
        "pagination": {"limit": limit, "offset": offset, "has_more": has_more},
    }


def get_project_data_source(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    source_id: str,
    client=None,
) -> dict:
    database = client or service_supabase
    project = project_dataset_service.require_data_project(
        project_id,
        tenant_id=int(tenant_id),
        client=database,
    )
    rows = _rows(
        database.table("data_sources")
        .select(_source_fields(client=database))
        .eq("id", _safe_uuid(source_id))
        .eq("tenant_id", int(tenant_id))
        .eq("project_id", _safe_uuid(project.get("id")))
        .eq("creator_user_id", int(user_id))
        .limit(1)
        .execute()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Data source was not found.")
    return rows[0]


def update_project_data_source_status(
    *,
    tenant_id: int,
    project_id: str,
    user_id: int,
    source_id: str,
    status: str,
    client=None,
) -> dict:
    database = client or service_supabase
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in SOURCE_STATUSES:
        raise HTTPException(status_code=422, detail="Data source status is not supported.")
    current = get_project_data_source(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(user_id),
        source_id=source_id,
        client=database,
    )
    if current.get("status") == normalized_status:
        return current
    try:
        updated = _rows(
            database.table("data_sources")
            .update({
                "status": normalized_status,
                "sync_state": "disabled" if normalized_status == "archived" else "idle",
            })
            .eq("id", current["id"])
            .eq("tenant_id", int(tenant_id))
            .eq("project_id", _safe_uuid(project_id))
            .eq("creator_user_id", int(user_id))
            .execute()
        )
    except Exception:
        if normalized_status == "active" and _duplicate_exists(
            database=database,
            tenant_id=int(tenant_id),
            project_id=_safe_uuid(project_id),
            source_type=str(current.get("source_type") or ""),
            display_name=str(current.get("display_name") or ""),
        ):
            raise HTTPException(
                status_code=409,
                detail="An active data source with this name already exists.",
            )
        raise
    if not updated:
        raise HTTPException(status_code=404, detail="Data source was not found.")
    return updated[0]
