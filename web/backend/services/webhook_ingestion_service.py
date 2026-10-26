"""Fenced, provider-neutral webhook receipt and bounded background processing."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi import HTTPException, UploadFile

from data_analysis import services as data_services
from database import service_supabase
from services import (
    data_source_credential_service,
    project_dataset_checkpoint_service,
    project_source_ingestion_service,
)
from services.data_source_api_provider import (
    ProviderFetchRequest,
    ProviderPage,
    ProviderRecord,
    fetch_bounded_records,
)
from services.webhook_registry import (
    MAX_WEBHOOK_BODY_BYTES,
    WebhookAdapterError,
    get_webhook_adapter,
    webhook_capability,
)


WEBHOOK_SCHEMA = 162
DEFAULT_LEASE_SECONDS = 300


class WebhookIngestionError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _rows(response) -> list[dict[str, Any]]:
    value = getattr(response, "data", None)
    if isinstance(value, dict):
        return [value]
    return list(value or [])


def _uuid(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise WebhookIngestionError("webhook_not_found", status_code=404) from error


def _schema_version(*, client=None) -> int:
    rows = _rows((client or service_supabase).table("application_schema_state")
                 .select("schema_version").eq("contract_key", "core").limit(1).execute())
    try:
        return int(rows[0]["schema_version"]) if rows else 0
    except (KeyError, TypeError, ValueError):
        return 0


def webhook_runtime_enabled() -> bool:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    return environment in {"development", "test"} and (
        os.getenv("MADAR_WEBHOOK_INGRESS_ENABLED", "").strip().lower() == "true"
    )


def webhooks_available(*, client=None) -> bool:
    return webhook_runtime_enabled() and _schema_version(client=client) >= WEBHOOK_SCHEMA


def _source(*, tenant_id: int, project_id: str, source_id: str, user_id: int, client=None) -> dict:
    from services import project_data_source_service
    return project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(user_id), client=client,
    )


def _require_capability(source: dict) -> dict:
    provider = str(source.get("provider_key") or "")
    resource = str(source.get("resource_type") or "")
    capability = webhook_capability(provider, resource)
    if capability is None:
        raise WebhookIngestionError("webhook_provider_unavailable", status_code=409)
    return capability


def status(*, tenant_id: int, project_id: str, source_id: str, user_id: int, client=None) -> dict:
    database = client or service_supabase
    source = _source(tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                     user_id=user_id, client=database)
    capability = webhook_capability(
        str(source.get("provider_key") or ""), str(source.get("resource_type") or ""),
    )
    if not webhooks_available(client=database) or capability is None:
        return {"available": False, "capability": capability, "endpoint": None}
    rows = _rows(database.rpc("get_data_source_webhook_status162", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
    }).execute())
    return {"available": True, "capability": capability,
            "endpoint": rows[0] if rows else None}


def provision(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    enabled: bool = False, expected_fence: int | None = None,
    resource_id: str | None = None, client=None, vault_client=None,
) -> dict:
    database = client or service_supabase
    if not webhooks_available(client=database):
        raise WebhookIngestionError("webhook_upgrade_or_runtime_required", status_code=503)
    source = _source(tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                     user_id=user_id, client=database)
    capability = _require_capability(source)
    secret = secrets.token_urlsafe(48)
    try:
        credential = data_source_credential_service.provision_credential(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(user_id), provider_key=str(source["provider_key"]),
            credential_type=str(capability["credential_type"]), secret=secret,
            client=database, vault_client=vault_client,
        )
        rows = _rows(database.rpc("configure_data_source_webhook162", {
            "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
            "p_source_id": _uuid(source_id),
            "p_source_resource_id": _uuid(resource_id) if resource_id else None,
            "p_actor_user_id": int(user_id), "p_provider_key": source["provider_key"],
            "p_resource_type": source["resource_type"], "p_enabled": bool(enabled),
            "p_credential_id": credential["credential_id"],
            "p_credential_version": int(credential["credential_version"]),
            "p_credential_revision": int(credential["source_revision"]),
            "p_expected_fence": expected_fence,
        }).execute())
    except data_source_credential_service.DataSourceCredentialError as error:
        raise WebhookIngestionError(error.code, status_code=503) from error
    if not rows:
        raise WebhookIngestionError("webhook_endpoint_write_failed", status_code=409)
    endpoint = rows[0]
    # This is the sole response that contains the newly generated plaintext.
    return {
        "endpoint": endpoint,
        "one_time_secret": secret,
        "ingress_path": f"/data/webhooks/{endpoint['id']}",
        "secret_will_not_be_shown_again": True,
    }


def configure(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    enabled: bool, expected_fence: int, client=None,
) -> dict:
    database = client or service_supabase
    current = status(tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                     user_id=user_id, client=database)
    endpoint = current.get("endpoint") or {}
    if not current.get("available") or not endpoint:
        raise WebhookIngestionError("webhook_endpoint_not_found", status_code=404)
    source = _source(tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                     user_id=user_id, client=database)
    rows = _rows(database.rpc("configure_data_source_webhook162", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_source_resource_id": endpoint["source_resource_id"],
        "p_actor_user_id": int(user_id), "p_provider_key": source["provider_key"],
        "p_resource_type": source["resource_type"], "p_enabled": bool(enabled),
        "p_credential_id": _active_credential(endpoint, "credential_id"),
        "p_credential_version": int(endpoint["credential_version"]),
        "p_credential_revision": _source_revision(source, endpoint),
        "p_expected_fence": int(expected_fence),
    }).execute())
    if not rows:
        raise WebhookIngestionError("webhook_endpoint_write_failed", status_code=409)
    return rows[0]


def revoke(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    expected_fence: int, client=None,
) -> dict:
    database = client or service_supabase
    current = status(tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                     user_id=user_id, client=database)
    endpoint = current.get("endpoint") or {}
    if not current.get("available") or not endpoint:
        raise WebhookIngestionError("webhook_endpoint_not_found", status_code=404)
    rows = _rows(database.rpc("revoke_data_source_webhook162", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_expected_fence": int(expected_fence),
    }).execute())
    if not rows:
        raise WebhookIngestionError("webhook_endpoint_write_failed", status_code=409)
    try:
        data_source_credential_service.revoke_credential(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(user_id), provider_key=str(_source(
                tenant_id=tenant_id, project_id=project_id, source_id=source_id,
                user_id=user_id, client=database,
            )["provider_key"]), expected_revision=int(endpoint["credential_revision"]),
            client=database,
        )
    except data_source_credential_service.DataSourceCredentialError as error:
        # Endpoint fencing is already safe; surface credential cleanup for retry.
        raise WebhookIngestionError(error.code, status_code=409) from error
    return rows[0]


def retry_event(
    *, tenant_id: int, project_id: str, source_id: str, event_id: str,
    user_id: int, client=None,
) -> bool:
    result = (client or service_supabase).rpc("retry_data_source_webhook_event162", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_event_id": _uuid(event_id),
        "p_actor_user_id": int(user_id),
    }).execute()
    return getattr(result, "data", None) is True


def _active_credential(endpoint: dict, key: str):
    # Status RPC deliberately omits credential IDs. Resolve it service-side.
    value = endpoint.get(key)
    if value is None:
        raise WebhookIngestionError("webhook_rotation_required", status_code=409)
    return value


def _source_revision(source: dict, endpoint: dict) -> int:
    value = source.get("credential_revision") or endpoint.get("credential_revision")
    if value is None:
        raise WebhookIngestionError("webhook_rotation_required", status_code=409)
    return int(value)


def receive(*, endpoint_id: str, raw_body: bytes, headers: dict[str, str], client=None,
            vault_client=None, received_at_epoch: int | None = None) -> dict:
    database = client or service_supabase
    if not webhooks_available(client=database):
        raise WebhookIngestionError("webhook_not_found", status_code=404)
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise WebhookIngestionError("webhook_payload_too_large", status_code=413)
    resolved = _rows(database.rpc("resolve_data_source_webhook162", {
        "p_endpoint_id": _uuid(endpoint_id),
    }).execute())
    if not resolved:
        raise WebhookIngestionError("webhook_not_found", status_code=404)
    endpoint = resolved[0]
    adapter = get_webhook_adapter(str(endpoint["provider_key"]))
    if adapter is None:
        raise WebhookIngestionError("webhook_not_found", status_code=404)
    try:
        credential = data_source_credential_service.resolve_persistent_credential(
            tenant_id=int(endpoint["tenant_id"]), project_id=str(endpoint["project_id"]),
            source_id=str(endpoint["source_id"]), user_id=int(endpoint["actor_user_id"]),
            provider_key=str(endpoint["provider_key"]), credential_type="webhook_hmac",
            client=database, vault_client=vault_client,
        )
        reference = credential.reference.as_metadata()
        if (reference["credential_id"] != str(endpoint["credential_id"])
                or int(reference["credential_version"]) != int(endpoint["credential_version"])
                or int(reference["source_revision"]) != int(endpoint["credential_revision"])):
            raise WebhookIngestionError("webhook_not_found", status_code=404)
        normalized = adapter.verify_and_normalize(
            raw_body=raw_body, headers=headers,
            secret=credential.secret.reveal_for_request(),
            received_at_epoch=received_at_epoch,
        )
        credential.validate()
    except WebhookAdapterError as error:
        raise WebhookIngestionError(error.code, status_code=error.status_code) from error
    except data_source_credential_service.DataSourceCredentialError as error:
        raise WebhookIngestionError("webhook_not_found", status_code=404) from error
    if normalized.resource_type != str(endpoint["resource_type"]):
        raise WebhookIngestionError("webhook_resource_unsupported", status_code=422)
    rows = _rows(database.rpc("accept_data_source_webhook_event162", {
        "p_endpoint_id": endpoint["endpoint_id"],
        "p_endpoint_fence": int(endpoint["endpoint_fence"]),
        "p_credential_id": reference["credential_id"],
        "p_credential_version": int(reference["credential_version"]),
        "p_credential_revision": int(reference["source_revision"]),
        "p_provider_event_id": normalized.provider_event_id,
        "p_event_type": normalized.event_type, "p_delivery_kind": normalized.delivery_kind,
        "p_occurred_at": datetime.fromtimestamp(
            normalized.occurred_at_epoch, tz=timezone.utc,
        ).isoformat(),
        "p_payload_hash": hashlib.sha256(raw_body).hexdigest(),
        "p_normalized_payload": dict(normalized.normalized_payload),
    }).execute())
    if not rows:
        raise WebhookIngestionError("webhook_acceptance_failed", status_code=503)
    return rows[0]


def claim_events(*, worker_id: str, limit: int = 10,
                 lease_seconds: int = DEFAULT_LEASE_SECONDS, client=None) -> list[dict]:
    return _rows((client or service_supabase).rpc("claim_data_source_webhook_events162", {
        "p_worker_id": str(worker_id)[:200], "p_limit": max(1, min(int(limit), 50)),
        "p_lease_seconds": max(60, min(int(lease_seconds), 1800)),
    }).execute())


def reconcile_expired(*, limit: int = 100, client=None) -> int:
    value = getattr((client or service_supabase).rpc("reconcile_expired_webhook_events162", {
        "p_limit": max(1, min(int(limit), 500)),
    }).execute(), "data", 0)
    return int(value or 0)


def _lease(event: dict) -> dict[str, object]:
    return {"p_event_id": event["id"], "p_lease_token": event["lease_token"],
            "p_lease_fence": int(event["lease_fence"])}


def _complete(event: dict, revision: int, *, client) -> None:
    result = client.rpc("complete_data_source_webhook_event162", {
        **_lease(event), "p_result_revision": int(revision),
    }).execute()
    if getattr(result, "data", None) is not True:
        raise RuntimeError("webhook_event_lease_lost")


def _fail(event: dict, code: str, *, transient: bool, phase: str, client) -> None:
    client.rpc("fail_data_source_webhook_event162", {
        **_lease(event), "p_error_category": code,
        "p_transient": bool(transient), "p_diagnostic_metadata": {"phase": phase},
    }).execute()


@dataclass
class _EventProvider:
    record: ProviderRecord
    provider_key: str
    resource: str

    @property
    def supported_resources(self):
        return frozenset({self.resource})

    def fetch_page(self, request: ProviderFetchRequest) -> ProviderPage:
        return ProviderPage((self.record,))

    def next_cursor(self, resource_type: str, current_cursor: str | None) -> str:
        return str(self.record.event_id)


def _current_record(event: dict, record_id: str, *, client) -> dict | None:
    resources = _rows(client.table("data_source_resources").select("dataset_id")
                      .eq("id", event["source_resource_id"])
                      .eq("tenant_id", int(event["tenant_id"])).limit(1).execute())
    if not resources or not resources[0].get("dataset_id"):
        return None
    rows = _rows(client.table("data_dataset_current_records")
                 .select("source_order,content_hash,is_deleted")
                 .eq("tenant_id", int(event["tenant_id"]))
                 .eq("dataset_id", resources[0]["dataset_id"])
                 .eq("source_record_id", record_id).limit(1).execute())
    return rows[0] if rows else None


async def execute_event(event: dict, *, client=None) -> dict:
    database = client or service_supabase
    run_id = None
    run_lease = None
    try:
        if event["delivery_kind"] == "change_notification":
            value = database.rpc("request_webhook_reconciliation162", _lease(event)).execute()
            revision = int(getattr(value, "data", 0) or 0)
            _complete(event, revision, client=database)
            return {"event_id": event["id"], "outcome": "reconciliation_scheduled",
                    "committed_revision": revision}

        payload = dict(event["normalized_payload"])["record"]
        record = ProviderRecord(
            stable_id=str(payload["id"]), values=dict(payload["data"]),
            operation="upsert", source_order=int(payload["version"]),
            event_id=str(event["provider_event_id"]),
        )
        adapter = _EventProvider(record, str(event.get("provider_key") or "webhook"),
                                 str(event.get("resource_type") or "records"))
        batch = fetch_bounded_records(adapter, resource_type=adapter.resource)
        reservation = project_source_ingestion_service.reserve_ingestion(
            tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
            source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
            idempotency_key=f"webhook:{event['id']}", source_type="api_provider",
            resource_key=adapter.resource, display_name=f"Webhook {adapter.resource}", client=database,
        )
        if reservation.get("disposition") == "succeeded":
            revision = int(reservation.get("committed_revision") or 0)
            _complete(event, revision, client=database)
            return {"event_id": event["id"], "outcome": "recovered", "committed_revision": revision}
        run_id = str(reservation["ingestion_run_id"])
        run_lease = str(reservation["lease_token"])
        attached = database.rpc("attach_webhook_event_ingestion162", {
            **_lease(event), "p_ingestion_run_id": run_id,
        }).execute()
        if getattr(attached, "data", None) is not True:
            raise RuntimeError("webhook_event_lease_lost")
        resolved = data_source_credential_service.resolve_persistent_credential(
            tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
            source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
            provider_key=str(event["provider_key"]), credential_type="webhook_hmac",
            client=database,
        )
        reference = resolved.reference.as_metadata()
        if (reference["credential_id"] != str(event["credential_id"])
                or int(reference["source_revision"]) != int(event["credential_revision"])):
            raise WebhookIngestionError("webhook_credential_fenced", status_code=409)
        existing = _current_record(event, str(payload["id"]), client=database)
        change = batch.changes[0]
        if existing and int(existing.get("source_order") or -1) >= int(payload["version"]):
            if (int(existing.get("source_order") or -1) == int(payload["version"])
                    and existing.get("content_hash") != change["content_hash"]):
                raise WebhookIngestionError("webhook_record_revision_conflict", status_code=409)
            result = project_source_ingestion_service.complete_noop_ingestion(
                tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
                source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
                ingestion_run_id=run_id, lease_token=run_lease,
                next_cursor=str(event["provider_event_id"]), credential_reference=reference,
                client=database,
            )
        else:
            upload = UploadFile(filename=f"webhook-{event['id']}.csv", file=BytesIO(batch.csv_bytes),
                                headers={"content-type": "text/csv"})

            def persist(artifact: dict) -> dict:
                project_source_ingestion_service.stage_incremental_changes(
                    tenant_id=int(event["tenant_id"]), ingestion_run_id=run_id,
                    lease_token=run_lease, changes=[dict(change)], client=database,
                )
                return project_source_ingestion_service.complete_incremental_ingestion(
                    tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
                    source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
                    ingestion_run_id=run_id, lease_token=run_lease,
                    storage_object_id=artifact["storage_object_id"], change_count=1,
                    manifest_hash=artifact["sha256"], next_cursor=str(event["provider_event_id"]),
                    schema_fingerprint=batch.schema_fingerprint,
                    credential_reference=reference, client=database,
                )

            result = await data_services.process_upload(
                upload, tenant_id=str(event["tenant_id"]), user_id=str(event["actor_user_id"]),
                metadata_persister=persist, shared_immutable=True,
                storage_reservation_persister=lambda value: project_source_ingestion_service.attach_storage_reservation(
                    tenant_id=int(event["tenant_id"]), ingestion_run_id=run_id,
                    lease_token=run_lease, storage_reservation_id=value, client=database),
                storage_object_persister=lambda value: project_source_ingestion_service.attach_storage_object(
                    tenant_id=int(event["tenant_id"]), ingestion_run_id=run_id,
                    lease_token=run_lease, storage_object_id=value, client=database),
                storage_object_failure_resolver=lambda value: project_source_ingestion_service.storage_object_attachment_state(
                    tenant_id=int(event["tenant_id"]), ingestion_run_id=run_id,
                    lease_token=run_lease, storage_object_id=value, client=database),
                metadata_failure_resolver=lambda _error: project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
                    source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
                    ingestion_run_id=run_id, client=database),
                lifecycle_heartbeat=lambda: (
                    database.rpc("heartbeat_data_source_webhook_event162", {
                        **_lease(event), "p_lease_seconds": DEFAULT_LEASE_SECONDS,
                    }).execute(),
                    project_source_ingestion_service.heartbeat_ingestion(
                        tenant_id=int(event["tenant_id"]), ingestion_run_id=run_id,
                        lease_token=run_lease, client=database),
                ),
            )
            try:
                project_dataset_checkpoint_service.enqueue_dataset_checkpoint(
                    tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
                    source_id=str(event["source_id"]), resource_id=str(event["source_resource_id"]),
                    dataset_id=str(result["persistent_dataset_id"]), user_id=int(event["actor_user_id"]),
                    target_revision=int(result["committed_revision"]), client=database,
                )
            except Exception:
                pass
        revision = int(result.get("committed_revision") or 0)
        _complete(event, revision, client=database)
        return {"event_id": event["id"], "outcome": "processed",
                "committed_revision": revision, "no_changes": bool(result.get("no_changes"))}
    except Exception as error:
        if run_id:
            try:
                recovered = project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
                    source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
                    ingestion_run_id=run_id, client=database,
                )
                if isinstance(recovered, dict):
                    revision = int(recovered.get("committed_revision") or 0)
                    _complete(event, revision, client=database)
                    return {"event_id": event["id"], "outcome": "recovered",
                            "committed_revision": revision}
            except Exception:
                pass
        if run_id and run_lease:
            try:
                project_source_ingestion_service.fail_ingestion(
                    tenant_id=int(event["tenant_id"]), project_id=str(event["project_id"]),
                    source_id=str(event["source_id"]), user_id=int(event["actor_user_id"]),
                    ingestion_run_id=run_id, lease_token=run_lease,
                    failure_code="ingestion_failed", client=database,
                )
            except Exception:
                pass
        transient = not isinstance(error, (WebhookIngestionError, HTTPException))
        code = error.code if isinstance(error, WebhookIngestionError) else "webhook_processing_failed"
        try:
            _fail(event, code, transient=transient, phase="processing", client=database)
        except Exception:
            pass
        return {"event_id": event.get("id"), "outcome": "failed",
                "error_category": code, "retryable": transient}


async def run_batch(*, worker_id: str, limit: int = 10,
                    lease_seconds: int = DEFAULT_LEASE_SECONDS, client=None) -> dict:
    database = client or service_supabase
    if not webhooks_available(client=database):
        return {"available": False, "reconciled": 0, "claimed": 0, "results": []}
    reconciled = reconcile_expired(limit=max(limit, 20), client=database)
    claims = claim_events(worker_id=worker_id, limit=limit,
                          lease_seconds=lease_seconds, client=database)
    results = [await execute_event(event, client=database) for event in claims]
    return {"available": True, "reconciled": reconciled,
            "claimed": len(claims), "results": results}
