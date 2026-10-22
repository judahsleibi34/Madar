"""Exact-revision checkpoints for incremental Data Source datasets.

Checkpoint state is reconstructed from immutable, quota-accounted change chunks.
The mutable current-record projection is deliberately not used as historical truth.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from database import service_supabase
from data_analysis import services as data_services
from services import project_data_source_service
from services.checkpoint_streaming import (
    MAX_CHECKPOINT_CHANGES, MAX_CHECKPOINT_RECORDS, DiskBackedState,
    ReconstructionArtifact, create_workspace,
)
from services.immutable_object_storage import (
    ImmutableObject, ImmutableObjectError, ObjectErrorCategory,
    configured_store, descriptor_from_row,
)
from services.storage_quota_service import (
    finish_immutable_storage, finish_storage, verify_immutable_storage,
)


HISTORY_PAGE_SIZE = 1_000
BACKGROUND_CHECKPOINT_SCHEMA = 153
SHARED_IMMUTABLE_STORAGE_SCHEMA = 154
logger = logging.getLogger(__name__)


def _rows(response) -> list[dict[str, Any]]:
    return list(getattr(response, "data", None) or [])


def _rpc_row(response) -> dict:
    value = getattr(response, "data", None)
    if isinstance(value, list):
        return value[0] if value else {}
    return value if isinstance(value, dict) else {}


def background_checkpoints_available(*, client=None) -> bool:
    database = client or service_supabase
    rows = _rows(database.table("application_schema_state").select("schema_version")
                 .eq("contract_key", "core").limit(1).execute())
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= BACKGROUND_CHECKPOINT_SCHEMA)
    except (TypeError, ValueError):
        return False


def shared_immutable_storage_available(*, client=None) -> bool:
    database = client or service_supabase
    rows = _rows(database.table("application_schema_state").select("schema_version")
                 .eq("contract_key", "core").limit(1).execute())
    try:
        return bool(rows and int(rows[0].get("schema_version")) >= SHARED_IMMUTABLE_STORAGE_SCHEMA)
    except (TypeError, ValueError):
        return False


def _safe_chunk_path(*, tenant_id: int, user_id: int, storage_key: str) -> Path:
    parts = Path(str(storage_key or "")).parts
    if len(parts) != 3 or parts[0] != f"tenant_{tenant_id}" or parts[1] != f"user_{user_id}":
        raise RuntimeError("incremental_history_storage_path_invalid")
    if not parts[2].endswith(".csv"):
        raise RuntimeError("incremental_history_storage_format_invalid")
    root = data_services.get_user_upload_dir(str(tenant_id), str(user_id)).resolve()
    path = (root / parts[2]).resolve()
    if path.parent != root or not path.is_file():
        raise RuntimeError("incremental_history_storage_missing")
    return path


class _ChunkCursor:
    def __init__(self, path: Path, *, delete_on_close: bool = False):
        self.path = path
        self.delete_on_close = delete_on_close
        self.handle = path.open("r", encoding="utf-8", newline="")
        self.reader = csv.DictReader(self.handle)
        self.ordinal = 0

    def row(self, ordinal: int) -> dict[str, str]:
        if ordinal != self.ordinal + 1:
            raise RuntimeError("incremental_history_ordinal_invalid")
        try:
            value = next(self.reader)
        except StopIteration as error:
            raise RuntimeError("incremental_history_ordinal_invalid") from error
        except UnicodeDecodeError as error:
            raise RuntimeError("incremental_history_storage_corrupt") from error
        self.ordinal = ordinal
        return value

    def finish(self) -> None:
        try:
            if next(self.reader, None) is not None:
                raise RuntimeError("incremental_history_lineage_incomplete")
        finally:
            self.handle.close()
            if self.delete_on_close:
                self.path.unlink(missing_ok=True)

    def close(self) -> None:
        self.handle.close()
        if self.delete_on_close:
            self.path.unlink(missing_ok=True)


def _open_chunk(*, database, storage_object_id: str, tenant_id: int, user_id: int,
                workspace: Path, cancelled) -> tuple[_ChunkCursor, int]:
    shared_enabled = shared_immutable_storage_available(client=database)
    fields = "id,storage_key,status,tenant_id,user_id,category"
    if shared_enabled:
        fields += ",storage_backend,storage_bucket,provider_object_key,verified_size_bytes,verified_sha256,integrity_verified_at"
    records = _rows(
        database.table("storage_objects")
        .select(fields)
        .eq("id", storage_object_id)
        .eq("tenant_id", tenant_id)
        .eq("category", "dataset")
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not records:
        raise RuntimeError("incremental_history_storage_unavailable")
    if shared_enabled and records[0].get("storage_backend") == "supabase_private":
        descriptor = descriptor_from_row(records[0])
        object_token = hashlib.sha256(str(storage_object_id).encode("utf-8")).hexdigest()
        path = workspace / f"history-{object_token}.csv"
        configured_store(client=database).download_to_path(
            tenant_id=tenant_id, descriptor=descriptor, target_path=path,
            cancelled=cancelled,
        )
        return _ChunkCursor(path, delete_on_close=True), descriptor.size_bytes
    path = _safe_chunk_path(
        tenant_id=tenant_id, user_id=int(records[0]["user_id"]),
        storage_key=records[0]["storage_key"]
    )
    return _ChunkCursor(path), path.stat().st_size


def reconstruct_dataset_revision(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    dataset_id: str, user_id: int, target_revision: int, client=None,
    checkpoint_id: str | None = None, cancelled=lambda: False,
    progress_callback=None,
) -> ReconstructionArtifact:
    """Replay exact immutable history into private bounded disk-backed state."""
    database = client or service_supabase
    project_data_source_service.get_project_data_source(
        tenant_id=tenant_id, project_id=project_id, source_id=source_id,
        user_id=user_id, client=database,
    )
    resources = _rows(
        database.table("data_source_resources")
        .select("id,dataset_id,committed_revision,resource_key")
        .eq("id", resource_id).eq("tenant_id", tenant_id)
        .eq("project_id", project_id).eq("source_id", source_id)
        .eq("dataset_id", dataset_id).limit(1).execute()
    )
    if not resources or target_revision < 1 \
            or target_revision > int(resources[0].get("committed_revision") or 0):
        raise HTTPException(status_code=404, detail="Dataset revision was not found.")

    workspace = create_workspace(checkpoint_id)
    state = DiskBackedState(workspace)
    offset = 0
    seen = 0
    chunk_id = None
    chunk: _ChunkCursor | None = None
    immutable_bytes_read = 0
    database_reads = 1
    try:
        while True:
            if cancelled():
                raise ImmutableObjectError(
                    ObjectErrorCategory.CANCELLED, "checkpoint_reconstruction_cancelled",
                )
            page = _rows(
                database.table("data_dataset_record_changes")
                .select(
                    "storage_object_id,row_ordinal,source_record_id,operation,outcome,"
                    "content_hash,committed_revision"
                )
                .eq("tenant_id", tenant_id).eq("project_id", project_id)
                .eq("source_id", source_id).eq("source_resource_id", resource_id)
                .eq("dataset_id", dataset_id).lte("committed_revision", target_revision)
                .order("committed_revision").order("row_ordinal")
                .range(offset, offset + HISTORY_PAGE_SIZE - 1).execute()
            )
            database_reads += 1
            if not page:
                break
            for change in page:
                seen += 1
                if seen > MAX_CHECKPOINT_CHANGES:
                    raise HTTPException(status_code=413, detail={
                        "code": "checkpoint_history_limit",
                        "message": "This checkpoint exceeds the current bounded reconstruction limit.",
                    })
                if change["storage_object_id"] != chunk_id:
                    if chunk is not None:
                        chunk.finish()
                    chunk_id = change["storage_object_id"]
                    chunk, bytes_read = _open_chunk(
                        database=database, storage_object_id=chunk_id,
                        tenant_id=tenant_id, user_id=user_id, workspace=workspace,
                        cancelled=cancelled,
                    )
                    database_reads += 1
                    immutable_bytes_read += bytes_read
                raw = chunk.row(int(change["row_ordinal"]))
                if raw.get("_source_record_id") != change["source_record_id"] \
                        or raw.get("_change_operation") != change["operation"] \
                        or raw.get("_content_hash") != change["content_hash"]:
                    raise RuntimeError("incremental_history_chunk_mismatch")
                payload = None
                if change["outcome"] not in {"duplicate", "stale_ignored", "deleted"}:
                    try:
                        payload = json.loads(raw.get("_payload_json") or "")
                    except (TypeError, ValueError) as error:
                        raise RuntimeError("incremental_history_payload_invalid") from error
                state.apply(
                    record_id=change["source_record_id"],
                    outcome=change["outcome"], payload=payload,
                )
            state.commit_and_validate(workspace)
            if progress_callback is not None:
                progress_callback()
            if len(page) < HISTORY_PAGE_SIZE:
                break
            offset += HISTORY_PAGE_SIZE
        if chunk is not None:
            chunk.finish()
            chunk = None
        output_path, record_count, state_hash, output_hash, output_size, columns = \
            state.finalize(workspace=workspace)
        writes = state.writes
        state.close()
        return ReconstructionArtifact(
            workspace=workspace, csv_path=output_path, record_count=record_count,
            change_count=seen, state_hash=state_hash,
            checkpoint_sha256=output_hash, checkpoint_size_bytes=output_size,
            resource_key=resources[0]["resource_key"],
            latest_committed_revision=int(resources[0]["committed_revision"]),
            database_reads=database_reads, database_writes=writes,
            immutable_bytes_read=immutable_bytes_read, columns=columns,
        )
    except Exception:
        if chunk is not None:
            chunk.close()
        state.close()
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def _checkpoint_view(checkpoint: dict, *, database) -> dict:
    resources = _rows(
        database.table("data_source_resources")
        .select("committed_revision,latest_checkpoint_version_id")
        .eq("id", checkpoint["source_resource_id"])
        .eq("tenant_id", checkpoint["tenant_id"]).limit(1).execute()
    )
    latest_committed = int(resources[0]["committed_revision"]) if resources else 0
    ready = _rows(
        database.table("data_dataset_checkpoints")
        .select("id,target_revision,version_id,status")
        .eq("tenant_id", checkpoint["tenant_id"])
        .eq("dataset_id", checkpoint["dataset_id"])
        .eq("status", "ready").order("target_revision", desc=True).limit(1).execute()
    )
    latest_ready = int(ready[0]["target_revision"]) if ready else None
    return {
        "checkpoint_id": checkpoint["id"],
        "checkpoint_status": checkpoint["status"],
        "target_revision": int(checkpoint["target_revision"]),
        "latest_committed_revision": latest_committed,
        "latest_ready_revision": latest_ready,
        "latest_ready_version_id": ready[0].get("version_id") if ready else None,
        "dataset_version_id": checkpoint.get("version_id"),
        "analytics_stale": latest_ready is None or latest_ready < latest_committed,
        "attempt_count": int(checkpoint.get("attempt_count") or 0),
        "max_attempts": int(checkpoint.get("max_attempts") or 3),
        "failure_code": checkpoint.get("failure_code"),
    }


def enqueue_dataset_checkpoint(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    dataset_id: str, user_id: int, target_revision: int, client=None,
) -> dict:
    database = client or service_supabase
    checkpoint = _rpc_row(database.rpc("request_dataset_checkpoint153", {
        "p_tenant_id": tenant_id, "p_project_id": project_id,
        "p_source_id": source_id, "p_resource_id": resource_id,
        "p_dataset_id": dataset_id, "p_user_id": user_id,
        "p_target_revision": target_revision,
    }).execute())
    if not checkpoint:
        raise RuntimeError("Checkpoint request was not created")
    return _checkpoint_view(checkpoint, database=database)


def get_dataset_checkpoint(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    checkpoint_id: str, user_id: int, client=None,
) -> dict:
    database = client or service_supabase
    project_data_source_service.get_project_data_source(
        tenant_id=tenant_id, project_id=project_id, source_id=source_id,
        user_id=user_id, client=database,
    )
    rows = _rows(database.table("data_dataset_checkpoints").select("*")
        .eq("id", checkpoint_id).eq("tenant_id", tenant_id)
        .eq("project_id", project_id).eq("source_id", source_id)
        .eq("source_resource_id", resource_id).limit(1).execute())
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset checkpoint was not found.")
    return _checkpoint_view(rows[0], database=database)


def claim_dataset_checkpoints(*, worker_id: str, limit: int = 5,
                              lease_seconds: int = 900, client=None) -> list[dict]:
    database = client or service_supabase
    return _rows(database.rpc("claim_dataset_checkpoints153", {
        "p_worker_id": str(worker_id)[:120], "p_limit": max(1, min(limit, 20)),
        "p_lease_seconds": max(60, min(lease_seconds, 3600)),
    }).execute())


def _heartbeat(checkpoint: dict, *, lease_seconds: int, database) -> None:
    ok = database.rpc("heartbeat_dataset_checkpoint153", {
        "p_checkpoint_id": checkpoint["id"], "p_lease_token": checkpoint["lease_token"],
        "p_lease_seconds": lease_seconds,
    }).execute()
    if getattr(ok, "data", None) is False:
        raise RuntimeError("checkpoint_lease_lost")


def _settle(checkpoint: dict, *, outcome: str, code: str, database,
            retry_seconds: int = 60) -> dict:
    return _rpc_row(database.rpc("settle_dataset_checkpoint153", {
        "p_checkpoint_id": checkpoint["id"], "p_lease_token": checkpoint["lease_token"],
        "p_outcome": outcome, "p_failure_code": code,
        "p_retry_seconds": retry_seconds,
    }).execute())


def _publish(checkpoint: dict, *, database) -> dict:
    result = _rpc_row(database.rpc("publish_dataset_checkpoint153", {
        "p_checkpoint_id": checkpoint["id"], "p_lease_token": checkpoint["lease_token"],
    }).execute())
    return {"outcome": "ready", "checkpoint_id": checkpoint["id"], **result}


def _reconstruction_upload(reconstruction, *, filename: str) -> UploadFile:
    path = getattr(reconstruction, "csv_path", None)
    if path is not None:
        stream = Path(path).open("rb")
    else:
        stream = io.BytesIO(reconstruction["csv_bytes"])
    return UploadFile(
        filename=filename, file=stream, headers={"content-type": "text/csv"},
    )


def _validate_reconstruction_artifact(reconstruction, artifact: dict) -> None:
    expected_hash = getattr(reconstruction, "checkpoint_sha256", None)
    expected_size = getattr(reconstruction, "checkpoint_size_bytes", None)
    if expected_hash is not None and artifact.get("sha256") != expected_hash:
        raise RuntimeError("checkpoint_artifact_hash_mismatch")
    if expected_size is not None and int(artifact.get("file_size") or -1) != expected_size:
        raise RuntimeError("checkpoint_artifact_size_mismatch")


def _reconstruction_shape(reconstruction):
    columns = getattr(reconstruction, "columns", None)
    if columns is None:
        return None
    return int(reconstruction["record_count"]), ("_source_record_id", *columns)


def _cleanup_reconstruction(reconstruction, upload: UploadFile | None) -> None:
    if upload is not None:
        upload.file.close()
    cleanup = getattr(reconstruction, "cleanup", None)
    if callable(cleanup):
        cleanup()


async def materialize_claimed_checkpoint(checkpoint: dict, *, lease_seconds: int = 900,
                                         client=None) -> dict:
    database = client or service_supabase
    reconstruction = None
    upload = None
    try:
        reconstruction = reconstruct_dataset_revision(
            tenant_id=int(checkpoint["tenant_id"]), project_id=checkpoint["project_id"],
            source_id=checkpoint["source_id"], resource_id=checkpoint["source_resource_id"],
            dataset_id=checkpoint["dataset_id"], user_id=int(checkpoint["requested_by_user_id"]),
            target_revision=int(checkpoint["target_revision"]), client=database,
            checkpoint_id=checkpoint["id"],
            progress_callback=lambda: _heartbeat(
                checkpoint, lease_seconds=lease_seconds, database=database),
        )
        filename = f"{reconstruction['resource_key']}-revision-{checkpoint['target_revision']}.csv"
        database.rpc("prepare_dataset_checkpoint153", {
            "p_checkpoint_id": checkpoint["id"], "p_lease_token": checkpoint["lease_token"],
            "p_filename": filename, "p_record_count": reconstruction["record_count"],
            "p_state_hash": reconstruction["state_hash"],
        }).execute()
        upload = _reconstruction_upload(reconstruction, filename=filename)

        def attach_reservation(reservation_id):
            database.rpc("attach_dataset_checkpoint_storage153", {
                "p_checkpoint_id": checkpoint["id"], "p_lease_token": checkpoint["lease_token"],
                "p_reservation_id": reservation_id, "p_storage_object_id": None,
            }).execute()

        def attach_object(object_id):
            database.rpc("attach_dataset_checkpoint_storage153", {
                "p_checkpoint_id": checkpoint["id"], "p_lease_token": checkpoint["lease_token"],
                "p_reservation_id": None, "p_storage_object_id": object_id,
            }).execute()

        def attachment_state(object_id):
            rows = _rows(database.table("data_dataset_checkpoints").select("storage_object_id,status")
                         .eq("id", checkpoint["id"]).limit(1).execute())
            return bool(rows and rows[0].get("storage_object_id") == object_id)

        def publish(_artifact):
            _validate_reconstruction_artifact(reconstruction, _artifact)
            return _publish(checkpoint, database=database)

        def recover(_error):
            rows = _rows(database.table("data_dataset_checkpoints")
                         .select("status,version_id,storage_object_id")
                         .eq("id", checkpoint["id"]).limit(1).execute())
            if rows and rows[0].get("status") == "ready":
                return {"outcome": "ready", "checkpoint_id": checkpoint["id"],
                        "dataset_version_id": rows[0].get("version_id"),
                        "completion_recovered": True}
            # Once an accounted object is attached, an uncertain publish must be
            # reconciled; returning False would release and delete durable evidence.
            return None

        result = await data_services.process_upload(
            upload, tenant_id=str(checkpoint["tenant_id"]),
            user_id=str(checkpoint["requested_by_user_id"]), metadata_persister=publish,
            metadata_failure_resolver=recover,
            storage_reservation_persister=attach_reservation,
            storage_object_persister=attach_object,
            storage_object_failure_resolver=attachment_state,
            lifecycle_heartbeat=lambda: _heartbeat(
                checkpoint, lease_seconds=lease_seconds, database=database),
            shared_immutable=shared_immutable_storage_available(client=database),
            prevalidated_csv_shape=_reconstruction_shape(reconstruction),
        )
        return {"checkpoint_id": checkpoint["id"], "outcome": "ready", **result}
    except HTTPException as error:
        rows = _rows(database.table("data_dataset_checkpoints")
                     .select("status,storage_object_id")
                     .eq("id", checkpoint["id"]).limit(1).execute())
        if rows and rows[0].get("status") == "materializing" \
                and rows[0].get("storage_object_id"):
            return {"checkpoint_id": checkpoint["id"],
                    "outcome": "awaiting_reconciliation"}
        terminal = error.status_code == 413
        try:
            _settle(checkpoint, outcome="failed" if terminal else "retry",
                    code="checkpoint_size_limit" if terminal else "checkpoint_materialization_failed",
                    database=database)
        except Exception:
            logger.exception("checkpoint.settlement_failed")
        return {"checkpoint_id": checkpoint["id"],
                "outcome": "failed" if terminal else "retry"}
    except Exception:
        try:
            _settle(checkpoint, outcome="retry", code="checkpoint_materialization_failed",
                    database=database)
        except Exception:
            logger.exception("checkpoint.settlement_failed")
        return {"checkpoint_id": checkpoint["id"], "outcome": "retry"}
    finally:
        _cleanup_reconstruction(reconstruction, upload)


def reconcile_expired_checkpoints(*, worker_id: str, limit: int = 5,
                                  lease_seconds: int = 300, client=None) -> list[dict]:
    database = client or service_supabase
    claimed = _rows(database.rpc("claim_expired_dataset_checkpoints153", {
        "p_worker_id": str(worker_id)[:120], "p_limit": max(1, min(limit, 20)),
        "p_lease_seconds": max(60, min(lease_seconds, 3600)),
    }).execute())
    results = []
    for checkpoint in claimed:
        try:
            if checkpoint.get("storage_object_id") and checkpoint.get("expected_state_hash") is not None:
                results.append(_publish(checkpoint, database=database))
                continue
            if checkpoint.get("storage_object_id"):
                _settle(checkpoint, outcome="ambiguous", code="checkpoint_artifact_unverifiable",
                        database=database)
                results.append({"checkpoint_id": checkpoint["id"], "outcome": "ambiguous"})
                continue
            if checkpoint.get("storage_reservation_id"):
                shared_enabled = shared_immutable_storage_available(client=database)
                reservation_fields = "status"
                if shared_enabled:
                    reservation_fields += (",storage_backend,storage_bucket,provider_object_key,"
                                           "expected_size_bytes,expected_sha256,transfer_state")
                reservations = _rows(database.table("storage_reservations").select(reservation_fields)
                    .eq("id", checkpoint["storage_reservation_id"]).limit(1).execute())
                if not reservations:
                    _settle(checkpoint, outcome="ambiguous", code="checkpoint_storage_ambiguous",
                            database=database)
                    results.append({"checkpoint_id": checkpoint["id"], "outcome": "ambiguous"})
                    continue
                reservation = reservations[0]
                if shared_enabled and reservation.get("storage_backend") == "supabase_private":
                    if reservation.get("status") == "reserved":
                        descriptor = ImmutableObject(
                            backend="supabase_private", bucket=reservation["storage_bucket"],
                            object_key=reservation["provider_object_key"],
                            size_bytes=int(reservation["expected_size_bytes"]),
                            sha256=reservation["expected_sha256"],
                        )
                        try:
                            configured_store(client=database).verify(
                                tenant_id=int(checkpoint["tenant_id"]), descriptor=descriptor,
                            )
                        except ImmutableObjectError as error:
                            if error.category == ObjectErrorCategory.MISSING:
                                finish_storage(
                                    reservation_id=checkpoint["storage_reservation_id"],
                                    succeeded=False, client=database,
                                )
                            else:
                                _settle(checkpoint, outcome="ambiguous",
                                        code="checkpoint_storage_ambiguous", database=database)
                                results.append({"checkpoint_id": checkpoint["id"],
                                                "outcome": "ambiguous"})
                                continue
                        else:
                            verify_immutable_storage(
                                reservation_id=checkpoint["storage_reservation_id"], client=database,
                            )
                            object_id = finish_immutable_storage(
                                reservation_id=checkpoint["storage_reservation_id"],
                                storage_key=(f"tenant_{checkpoint['tenant_id']}/"
                                             f"user_{checkpoint['requested_by_user_id']}/"
                                             f"{checkpoint['storage_reservation_id']}.csv"),
                                client=database,
                            )
                            database.rpc("attach_dataset_checkpoint_storage153", {
                                "p_checkpoint_id": checkpoint["id"],
                                "p_lease_token": checkpoint["lease_token"],
                                "p_reservation_id": None,
                                "p_storage_object_id": object_id,
                            }).execute()
                            checkpoint["storage_object_id"] = object_id
                            results.append(_publish(checkpoint, database=database))
                            continue
                    elif reservation.get("status") == "committed":
                        objects = _rows(database.table("storage_objects").select("id")
                            .eq("reservation_id", checkpoint["storage_reservation_id"])
                            .eq("tenant_id", checkpoint["tenant_id"])
                            .eq("status", "active").limit(1).execute())
                        if objects:
                            database.rpc("attach_dataset_checkpoint_storage153", {
                                "p_checkpoint_id": checkpoint["id"],
                                "p_lease_token": checkpoint["lease_token"],
                                "p_reservation_id": None,
                                "p_storage_object_id": objects[0]["id"],
                            }).execute()
                            checkpoint["storage_object_id"] = objects[0]["id"]
                            results.append(_publish(checkpoint, database=database))
                            continue
                        _settle(checkpoint, outcome="ambiguous",
                                code="checkpoint_storage_ambiguous", database=database)
                        results.append({"checkpoint_id": checkpoint["id"],
                                        "outcome": "ambiguous"})
                        continue
                elif reservation.get("status") == "reserved":
                    finish_storage(reservation_id=checkpoint["storage_reservation_id"],
                                   succeeded=False, client=database)
                else:
                    _settle(checkpoint, outcome="ambiguous", code="checkpoint_storage_ambiguous",
                            database=database)
                    results.append({"checkpoint_id": checkpoint["id"], "outcome": "ambiguous"})
                    continue
            settled = _settle(checkpoint, outcome="retry", code="checkpoint_worker_abandoned",
                              database=database)
            results.append({"checkpoint_id": checkpoint["id"],
                            "outcome": "retry" if settled.get("status") == "pending" else "failed"})
        except Exception:
            logger.exception("checkpoint.reconciliation_failed")
            results.append({"checkpoint_id": checkpoint.get("id"), "outcome": "error"})
    return results


async def materialize_dataset_checkpoint(
    *, tenant_id: int, project_id: str, source_id: str, resource_id: str,
    dataset_id: str, user_id: int, target_revision: int, client=None,
) -> dict:
    database = client or service_supabase
    checkpoint = _rpc_row(database.rpc("request_dataset_checkpoint152", {
        "p_tenant_id": tenant_id, "p_project_id": project_id,
        "p_source_id": source_id, "p_resource_id": resource_id,
        "p_dataset_id": dataset_id, "p_user_id": user_id,
        "p_target_revision": target_revision,
    }).execute())
    if not checkpoint:
        raise RuntimeError("Checkpoint request was not created")
    if checkpoint.get("status") == "ready":
        resources = _rows(
            database.table("data_source_resources").select("committed_revision")
            .eq("id", resource_id).eq("tenant_id", tenant_id).limit(1).execute()
        )
        latest_revision = int(resources[0]["committed_revision"]) if resources else target_revision
        return {
            "persistent_dataset_id": dataset_id,
            "dataset_version_id": checkpoint.get("version_id"),
            "committed_revision": target_revision,
            "checkpoint_current": latest_revision == target_revision,
            "latest_committed_revision": latest_revision,
            "idempotent_replay": True,
        }

    reconstruction = None
    upload = None
    try:
        reconstruction = reconstruct_dataset_revision(
            tenant_id=tenant_id, project_id=project_id, source_id=source_id,
            resource_id=resource_id, dataset_id=dataset_id, user_id=user_id,
            target_revision=target_revision, client=database,
        )
        upload = _reconstruction_upload(
            reconstruction,
            filename=f"{reconstruction['resource_key']}-revision-{target_revision}.csv",
        )

        def publish(artifact: dict):
            _validate_reconstruction_artifact(reconstruction, artifact)
            result = _rpc_row(database.rpc("publish_dataset_checkpoint152", {
                "p_checkpoint_id": checkpoint["id"],
                "p_storage_object_id": artifact["storage_object_id"],
                "p_original_filename": artifact["original_filename"],
                "p_size_bytes": artifact["file_size"],
                "p_content_hash": artifact["sha256"],
                "p_record_count": reconstruction["record_count"],
                "p_state_hash": reconstruction["state_hash"],
            }).execute())
            resources = _rows(
                database.table("data_source_resources").select("committed_revision")
                .eq("id", resource_id).eq("tenant_id", tenant_id).limit(1).execute()
            )
            latest_revision = (
                int(resources[0]["committed_revision"])
                if resources else reconstruction["latest_committed_revision"]
            )
            return {
                "persistent_dataset_id": result.get("dataset_id"),
                "dataset_version_id": result.get("version_id"),
                "version_number": result.get("version_number"),
                "committed_revision": result.get("target_revision"),
                "checkpoint_current": latest_revision == int(result.get("target_revision") or 0),
                "latest_committed_revision": latest_revision,
            }

        def recover(_error):
            rows = _rows(
                database.table("data_dataset_checkpoints")
                .select("status,version_id,target_revision")
                .eq("id", checkpoint["id"]).limit(1).execute()
            )
            if rows and rows[0].get("status") == "ready":
                resources = _rows(
                    database.table("data_source_resources").select("committed_revision")
                    .eq("id", resource_id).eq("tenant_id", tenant_id).limit(1).execute()
                )
                latest_revision = int(resources[0]["committed_revision"]) if resources else target_revision
                return {
                    "persistent_dataset_id": dataset_id,
                    "dataset_version_id": rows[0].get("version_id"),
                    "committed_revision": rows[0].get("target_revision"),
                    "checkpoint_current": latest_revision == int(rows[0]["target_revision"]),
                    "latest_committed_revision": latest_revision,
                    "completion_recovered": True,
                }
            return False if rows else None

        return await data_services.process_upload(
            upload, tenant_id=str(tenant_id), user_id=str(user_id),
            metadata_persister=publish, metadata_failure_resolver=recover,
            prevalidated_csv_shape=_reconstruction_shape(reconstruction),
        )
    except Exception:
        try:
            database.rpc("fail_dataset_checkpoint152", {
                "p_checkpoint_id": checkpoint["id"], "p_user_id": user_id,
                "p_failure_code": "checkpoint_materialization_failed",
            }).execute()
        except Exception:
            pass
        raise
    finally:
        _cleanup_reconstruction(reconstruction, upload)
