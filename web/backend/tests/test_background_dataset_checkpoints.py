import asyncio
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from data_analysis.routes import data_routes
from services import project_dataset_checkpoint_service as checkpoints
from services.checkpoint_streaming import ReconstructionArtifact, create_workspace


CHECKPOINT = "11111111-1111-4111-8111-111111111111"
LEASE = "22222222-2222-4222-8222-222222222222"
DATASET = "33333333-3333-4333-8333-333333333333"


class Query:
    def __init__(self, rows): self.rows = [dict(row) for row in rows]
    def select(self, *_args): return self
    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self
    def limit(self, value): self.rows = self.rows[:value]; return self
    def order(self, key, desc=False):
        self.rows.sort(key=lambda row: row.get(key), reverse=desc); return self
    def execute(self): return SimpleNamespace(data=self.rows)


class Rpc:
    def __init__(self, client, name, args): self.client, self.name, self.args = client, name, args
    def execute(self):
        self.client.calls.append((self.name, self.args))
        value = self.client.responses.get(self.name, {})
        if callable(value): value = value(self.args)
        return SimpleNamespace(data=value)


class Client:
    def __init__(self, *, responses=None, tables=None):
        self.responses = responses or {}; self.tables = tables or {}; self.calls = []
    def rpc(self, name, args): return Rpc(self, name, args)
    def table(self, name): return Query(self.tables.get(name, []))


def claimed(**overrides):
    row = {
        "id": CHECKPOINT, "lease_token": LEASE, "tenant_id": 1,
        "project_id": "project", "source_id": "source",
        "source_resource_id": "resource", "dataset_id": "dataset",
        "requested_by_user_id": 7, "target_revision": 2,
        "attempt_count": 1, "max_attempts": 3,
    }
    row.update(overrides)
    return row


class BackgroundCheckpointTests(unittest.TestCase):
    def test_claimed_job_streams_private_artifact_and_cleans_workspace(self):
        client = Client(responses={
            "prepare_dataset_checkpoint153": True,
            "heartbeat_dataset_checkpoint153": True,
            "attach_dataset_checkpoint_storage153": True,
            "publish_dataset_checkpoint153": [{
                "dataset_id": "dataset", "version_id": "version",
                "version_number": 1, "target_revision": 2,
            }],
        })
        content = b"_source_record_id,value\nA,1\n"
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "DATA_CHECKPOINT_SCRATCH_DIR": root,
        }, clear=False):
            workspace = create_workspace(CHECKPOINT)
            csv_path = workspace / "checkpoint.csv"
            csv_path.write_bytes(content)
            artifact = ReconstructionArtifact(
                workspace=workspace, csv_path=csv_path, record_count=1,
                change_count=1, state_hash="a" * 64,
                checkpoint_sha256=hashlib.sha256(content).hexdigest(),
                checkpoint_size_bytes=len(content), resource_key="orders",
                latest_committed_revision=2, database_reads=3, database_writes=2,
                immutable_bytes_read=100, columns=("value",),
            )

            async def upload(upload_file, **options):
                self.assertEqual(Path(upload_file.file.name), csv_path)
                self.assertEqual(upload_file.file.read(), content)
                options["storage_reservation_persister"]("reservation")
                options["storage_object_persister"]("object")
                return options["metadata_persister"]({
                    "storage_object_id": "object", "sha256": artifact.checkpoint_sha256,
                    "file_size": len(content),
                })

            with (
                patch.object(checkpoints, "reconstruct_dataset_revision", return_value=artifact),
                patch.object(checkpoints.data_services, "process_upload", side_effect=upload),
            ):
                result = asyncio.run(checkpoints.materialize_claimed_checkpoint(
                    claimed(), client=client,
                ))
            self.assertEqual(result["outcome"], "ready")
            self.assertFalse(workspace.exists())

    def test_route_enqueues_and_returns_202_without_materializing(self):
        response = SimpleNamespace(status_code=201)
        expected = {"checkpoint_id": CHECKPOINT, "checkpoint_status": "pending"}
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(data_routes.project_source_ingestion_service,
                         "incremental_ingestion_available", return_value=True),
            patch.object(checkpoints, "background_checkpoints_available", return_value=True),
            patch.object(checkpoints, "enqueue_dataset_checkpoint", return_value=expected) as enqueue,
            patch.object(checkpoints, "materialize_dataset_checkpoint", new=AsyncMock()) as legacy,
        ):
            result = asyncio.run(data_routes.create_incremental_checkpoint(
                user_id=7, project_id="project", source_id="source", resource_id="resource",
                payload=data_routes.CreateDatasetCheckpointRequest(
                    dataset_id=DATASET, target_revision=2),
                request=SimpleNamespace(), response=response,
            ))
        self.assertEqual(response.status_code, 202)
        self.assertEqual(result, expected)
        enqueue.assert_called_once()
        legacy.assert_not_awaited()

    def test_claimed_job_attaches_accounting_and_publishes(self):
        client = Client(responses={
            "prepare_dataset_checkpoint153": True,
            "heartbeat_dataset_checkpoint153": True,
            "attach_dataset_checkpoint_storage153": True,
            "publish_dataset_checkpoint153": [{
                "dataset_id": "dataset", "version_id": "version",
                "version_number": 1, "target_revision": 2,
            }],
        })
        reconstruction = {
            "resource_key": "orders", "csv_bytes": b"_source_record_id\nA\n",
            "record_count": 1, "state_hash": "a" * 64,
        }

        async def upload(_file, **options):
            options["storage_reservation_persister"]("reservation")
            options["storage_object_persister"]("object")
            return options["metadata_persister"]({"storage_object_id": "object"})

        with (
            patch.object(checkpoints, "reconstruct_dataset_revision", return_value=reconstruction),
            patch.object(checkpoints.data_services, "process_upload", side_effect=upload),
        ):
            result = asyncio.run(checkpoints.materialize_claimed_checkpoint(
                claimed(), client=client,
            ))
        self.assertEqual(result["outcome"], "ready")
        self.assertEqual([name for name, _ in client.calls].count(
            "attach_dataset_checkpoint_storage153"), 2)
        self.assertIn("publish_dataset_checkpoint153", [name for name, _ in client.calls])

    def test_size_limit_is_terminal_and_other_failure_retries(self):
        for error, expected_outcome, expected_settlement in (
            (HTTPException(status_code=413, detail="large"), "failed", "failed"),
            (RuntimeError("transient"), "retry", "retry"),
        ):
            client = Client(responses={"settle_dataset_checkpoint153": {
                "id": CHECKPOINT, "status": expected_settlement,
            }})
            with patch.object(checkpoints, "reconstruct_dataset_revision", side_effect=error):
                result = asyncio.run(checkpoints.materialize_claimed_checkpoint(
                    claimed(), client=client,
                ))
            self.assertEqual(result["outcome"], expected_outcome)
            settlement = next(args for name, args in client.calls
                              if name == "settle_dataset_checkpoint153")
            self.assertEqual(settlement["p_outcome"], expected_settlement)

    def test_expired_artifact_is_published_without_duplicate_upload(self):
        job = claimed(storage_object_id="object", expected_state_hash="a" * 64)
        client = Client(responses={
            "claim_expired_dataset_checkpoints153": [job],
            "publish_dataset_checkpoint153": [{
                "dataset_id": "dataset", "version_id": "version",
                "version_number": 1, "target_revision": 2,
            }],
        })
        result = checkpoints.reconcile_expired_checkpoints(worker_id="worker", client=client)
        self.assertEqual(result[0]["outcome"], "ready")

    def test_expired_shared_upload_is_verified_accounted_and_published(self):
        reservation = "44444444-4444-4444-8444-444444444444"
        job = claimed(
            storage_reservation_id=reservation, storage_object_id=None,
            expected_state_hash="a" * 64, expected_record_count=1,
        )
        client = Client(
            responses={
                "claim_expired_dataset_checkpoints153": [job],
                "attach_dataset_checkpoint_storage153": True,
                "publish_dataset_checkpoint153": [{
                    "dataset_id": "dataset", "version_id": "version",
                    "version_number": 1, "target_revision": 2,
                }],
            },
            tables={"storage_reservations": [{
                "id": reservation, "status": "reserved",
                "storage_backend": "supabase_private",
                "storage_bucket": "madar-data-immutable",
                "provider_object_key": (
                    f"tenant_1/dataset/{reservation}/{'b' * 64}.csv"
                ),
                "expected_size_bytes": 12, "expected_sha256": "b" * 64,
                "transfer_state": "ambiguous",
            }]},
        )
        store = SimpleNamespace(verify=lambda **_kwargs: None)
        with (
            patch.object(checkpoints, "shared_immutable_storage_available", return_value=True),
            patch.object(checkpoints, "configured_store", return_value=store),
            patch.object(checkpoints, "verify_immutable_storage") as verify,
            patch.object(checkpoints, "finish_immutable_storage", return_value="object") as finish,
        ):
            result = checkpoints.reconcile_expired_checkpoints(
                worker_id="worker", client=client,
            )
        self.assertEqual(result[0]["outcome"], "ready")
        verify.assert_called_once()
        finish.assert_called_once()
        self.assertEqual(
            [name for name, _ in client.calls].count("attach_dataset_checkpoint_storage153"), 1,
        )

    def test_uncertain_publish_preserves_attached_artifact_for_reconciliation(self):
        job = claimed()
        client = Client(
            responses={
                "prepare_dataset_checkpoint153": True,
                "heartbeat_dataset_checkpoint153": True,
                "attach_dataset_checkpoint_storage153": True,
            },
            tables={"data_dataset_checkpoints": [{
                **job, "status": "materializing", "storage_object_id": "object",
            }]},
        )
        reconstruction = {
            "resource_key": "orders", "csv_bytes": b"_source_record_id\nA\n",
            "record_count": 1, "state_hash": "a" * 64,
        }

        async def uncertain(_file, **options):
            options["storage_reservation_persister"]("reservation")
            options["storage_object_persister"]("object")
            self.assertIsNone(options["metadata_failure_resolver"](RuntimeError("lost")))
            raise HTTPException(status_code=503, detail={"code": "metadata_outcome_unknown"})

        with (
            patch.object(checkpoints, "reconstruct_dataset_revision", return_value=reconstruction),
            patch.object(checkpoints.data_services, "process_upload", side_effect=uncertain),
        ):
            result = asyncio.run(checkpoints.materialize_claimed_checkpoint(job, client=client))
        self.assertEqual(result["outcome"], "awaiting_reconciliation")
        self.assertNotIn("settle_dataset_checkpoint153", [name for name, _ in client.calls])

    def test_status_is_authorized_and_reports_stale_analytics(self):
        job = {**claimed(), "status": "pending", "version_id": None}
        client = Client(tables={
            "data_dataset_checkpoints": [job, {
                **job, "id": "ready", "status": "ready", "target_revision": 1,
                "version_id": "version-1",
            }],
            "data_source_resources": [{
                "id": "resource", "tenant_id": 1, "committed_revision": 2,
                "latest_checkpoint_version_id": "version-1",
            }],
        })
        with patch.object(checkpoints.project_data_source_service,
                          "get_project_data_source", return_value={"id": "source"}) as authorize:
            result = checkpoints.get_dataset_checkpoint(
                tenant_id=1, project_id="project", source_id="source",
                resource_id="resource", checkpoint_id=CHECKPOINT, user_id=7, client=client,
            )
        authorize.assert_called_once()
        self.assertEqual(result["latest_committed_revision"], 2)
        self.assertEqual(result["latest_ready_revision"], 1)
        self.assertTrue(result["analytics_stale"])


if __name__ == "__main__":
    unittest.main()
