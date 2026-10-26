"""One-shot API ingestion using the durable Data Sources lifecycle."""

from __future__ import annotations

from io import BytesIO

from fastapi import HTTPException, UploadFile

from data_analysis import services as data_services
from services import project_data_source_service
from services.data_source_api_provider import (
    ProviderErrorCategory,
    ProviderFetchError,
    ProviderNoChanges,
    fetch_bounded_records,
    get_provider,
)


_HTTP_BY_PROVIDER_ERROR = {
    ProviderErrorCategory.CANCELLED: 408,
    ProviderErrorCategory.TIMEOUT: 504,
    ProviderErrorCategory.UNAVAILABLE: 502,
    ProviderErrorCategory.UNAUTHORIZED: 401,
    ProviderErrorCategory.RATE_LIMITED: 429,
    ProviderErrorCategory.DESTINATION_FORBIDDEN: 502,
    ProviderErrorCategory.INVALID_RESPONSE: 422,
    ProviderErrorCategory.PAYLOAD_TOO_LARGE: 413,
}


def provider_failure_code(error: Exception) -> str:
    if isinstance(error, ProviderFetchError):
        return error.category.value
    if isinstance(error, HTTPException) and isinstance(error.detail, dict):
        code = str(error.detail.get("code") or "")
        if code.startswith("provider_"):
            return code
    return "ingestion_failed"


def _safe_provider_http_error(error: ProviderFetchError) -> HTTPException:
    messages = {
        ProviderErrorCategory.CANCELLED: "The provider import was cancelled.",
        ProviderErrorCategory.TIMEOUT: "The provider did not finish within the allowed time.",
        ProviderErrorCategory.UNAVAILABLE: "The provider is temporarily unavailable.",
        ProviderErrorCategory.UNAUTHORIZED: "The provider credential is invalid or revoked.",
        ProviderErrorCategory.RATE_LIMITED: "The provider rate limit was reached.",
        ProviderErrorCategory.DESTINATION_FORBIDDEN: "The provider destination is not permitted.",
        ProviderErrorCategory.INVALID_RESPONSE: "The provider returned unsupported records.",
        ProviderErrorCategory.PAYLOAD_TOO_LARGE: "The provider response exceeded the import limits.",
    }
    return HTTPException(
        status_code=_HTTP_BY_PROVIDER_ERROR[error.category],
        detail={"code": error.category.value, "message": messages[error.category]},
    )


async def process_api_source(
    *,
    tenant_id: int,
    project_id: str,
    source_id: str,
    user_id: int,
    ingestion_run_id: str,
    lifecycle_heartbeat=None,
    metadata_persister=None,
    incremental_persister=None,
    noop_persister=None,
    metadata_failure_resolver=None,
    storage_reservation_persister=None,
    storage_object_persister=None,
    storage_object_failure_resolver=None,
    cancelled=lambda: False,
    provider=None,
    resource_type: str | None = None,
    sync_cursor: str | None = None,
    fixture_batch: int = 1,
    shared_immutable: bool = False,
    provider_audit=None,
) -> dict:
    source = project_data_source_service.get_project_data_source(
        tenant_id=tenant_id,
        project_id=project_id,
        source_id=source_id,
        user_id=user_id,
    )
    if source.get("source_type") != project_data_source_service.SOURCE_TYPE_API_PROVIDER:
        raise HTTPException(status_code=409, detail="This source does not support API ingestion.")
    provider_key = str(source.get("provider_key") or "")
    if (
        provider_key == "synthetic_orders"
        and not project_data_source_service.synthetic_api_provider_enabled()
    ):
        raise HTTPException(status_code=404, detail="API provider was not found.")
    resource_type = str(resource_type or source.get("resource_type") or "").strip().lower()
    adapter = provider
    try:
        from services.provider_credentials import AuthorizedSource
        adapter = adapter or get_provider(
            provider_key,
            fixture_batch=fixture_batch,
            cancelled=cancelled,
            heartbeat=lifecycle_heartbeat,
            audit=provider_audit,
            source_scope=AuthorizedSource(
                tenant_id=int(tenant_id), project_id=project_id,
                source_id=source_id, provider_key=provider_key, user_id=int(user_id),
            ),
        )
        try:
            batch = fetch_bounded_records(
                adapter,
                resource_type=resource_type,
                cancelled=cancelled,
                heartbeat=lifecycle_heartbeat,
                sync_cursor=sync_cursor,
            )
        except ProviderNoChanges as no_changes:
            revalidate = getattr(adapter, "revalidate_credential", None)
            if callable(revalidate):
                revalidate()
            credential_reference = getattr(adapter, "credential_reference", lambda: None)()
            if noop_persister is None:
                raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE) from no_changes
            result = noop_persister(no_changes.next_cursor, credential_reference)
            return {
                **result,
                "provider": {"provider_key": provider_key, "resource_type": resource_type,
                             "record_count": 0, "page_count": 0,
                             "next_cursor": no_changes.next_cursor, "no_changes": True},
            }
        revalidate = getattr(adapter, "revalidate_credential", None)
        if callable(revalidate):
            revalidate()
        credential_reference = getattr(adapter, "credential_reference", lambda: None)()
    except ProviderFetchError as error:
        raise _safe_provider_http_error(error) from error
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    generated_name = f"{provider_key}-{resource_type}-{ingestion_run_id}.csv"
    upload = UploadFile(
        filename=generated_name,
        file=BytesIO(batch.csv_bytes),
        headers={"content-type": "text/csv"},
    )

    def persist_with_provenance(artifact: dict):
        artifact = {
            **artifact,
            "provider_metadata": {
                "provider_key": provider_key,
                "resource_type": resource_type,
                "record_count": batch.record_count,
                "page_count": batch.page_count,
                "continuation_present": batch.final_continuation is not None,
                "credential": credential_reference,
            },
        }
        if incremental_persister is not None:
            return incremental_persister(artifact, batch)
        return metadata_persister(artifact) if metadata_persister is not None else None

    result = await data_services.process_upload(
        upload,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        metadata_persister=persist_with_provenance,
        metadata_failure_resolver=metadata_failure_resolver,
        storage_reservation_persister=storage_reservation_persister,
        storage_object_persister=storage_object_persister,
        storage_object_failure_resolver=storage_object_failure_resolver,
        lifecycle_heartbeat=lifecycle_heartbeat,
        shared_immutable=shared_immutable,
        cancelled=cancelled,
    )
    return {
        **result,
        "provider": {
            "provider_key": provider_key,
            "resource_type": resource_type,
            "record_count": batch.record_count,
            "page_count": batch.page_count,
            "next_cursor": batch.next_cursor,
            "schema_fingerprint": batch.schema_fingerprint,
        },
    }
