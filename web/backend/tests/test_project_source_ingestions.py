import asyncio
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import ANY, patch

from fastapi import HTTPException, UploadFile

from data_analysis import services as data_services
from data_analysis.routes import data_routes
from services import project_source_ingestion_service


PROJECT_A = "11111111-1111-4111-8111-111111111111"
PROJECT_B = "22222222-2222-4222-8222-222222222222"
SOURCE_A = "33333333-3333-4333-8333-333333333333"
RUN_A = "44444444-4444-4444-8444-444444444444"
DATASET_A = "55555555-5555-4555-8555-555555555555"
VERSION_A = "66666666-6666-4666-8666-666666666666"
STORAGE_A = "77777777-7777-4777-8777-777777777777"
RESERVATION_A = "88888888-8888-4888-8888-888888888881"
LEASE_A = "99999999-9999-4999-8999-999999999991"


class FakeQuery:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self._limit = None
        self._range = None

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def neq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) != value]
        return self

    def order(self, field, desc=False):
        self.rows.sort(key=lambda row: row.get(field) or "", reverse=desc)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def execute(self):
        rows = self.rows
        if self._range is not None:
            rows = rows[self._range[0] : self._range[1] + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        return SimpleNamespace(data=rows)


class FakeRpc:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return SimpleNamespace(data=self.result)


class FakeClient:
    def __init__(self, tables=None, rpc_results=None):
        self.tables = tables or {}
        self.rpc_results = rpc_results or {}
        self.rpc_calls = []

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return FakeRpc(self.rpc_results.get(name, []))


def project(project_id=PROJECT_A, tenant_id=1):
    return {
        "id": project_id,
        "tenant_id": tenant_id,
        "name": "Data project",
        "status": "draft",
        "draft_schema": {"workspaceKind": "data"},
    }


def source(**overrides):
    value = {
        "id": SOURCE_A,
        "tenant_id": 1,
        "project_id": PROJECT_A,
        "creator_user_id": 7,
        "source_type": "spreadsheet_upload",
        "display_name": "Monthly sales",
        "status": "active",
        "sync_mode": "manual",
        "sync_state": "idle",
    }
    value.update(overrides)
    return value


def run(**overrides):
    value = {
        "id": RUN_A,
        "tenant_id": 1,
        "project_id": PROJECT_A,
        "source_id": SOURCE_A,
        "initiated_by_user_id": 7,
        "status": "succeeded",
        "attempt_number": 1,
        "result_dataset_id": DATASET_A,
        "result_version_id": VERSION_A,
        "created_at": "2026-10-18T00:00:00Z",
    }
    value.update(overrides)
    return value


class ProjectSourceIngestionServiceTests(unittest.TestCase):
    def test_resource_status_summary_is_scoped_and_keeps_checkpoint_freshness_distinct(self):
        resource_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        client = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 156}],
            "data_source_resources": [
                {"id": resource_id, "tenant_id": 1, "project_id": PROJECT_A,
                 "source_id": SOURCE_A, "resource_key": "orders",
                 "dataset_id": DATASET_A, "committed_revision": 4,
                 "latest_checkpoint_version_id": VERSION_A},
                {"id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "tenant_id": 2,
                 "project_id": PROJECT_A, "source_id": SOURCE_A,
                 "resource_key": "foreign", "committed_revision": 99},
            ],
            "data_source_ingestion_runs": [
                {"id": RUN_A, "tenant_id": 1, "project_id": PROJECT_A,
                 "source_id": SOURCE_A, "source_resource_id": resource_id,
                 "ingestion_kind": "incremental", "status": "succeeded",
                 "committed_revision": 4, "completed_at": "2026-10-20T10:00:00Z",
                 "created_at": "2026-10-20T09:00:00Z"},
            ],
            "data_dataset_checkpoints": [
                {"id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc", "tenant_id": 1,
                 "project_id": PROJECT_A, "source_id": SOURCE_A,
                 "source_resource_id": resource_id, "target_revision": 3,
                 "status": "ready", "version_id": VERSION_A,
                 "created_at": "2026-10-20T10:01:00Z"},
            ],
        })
        with (
            patch.object(
                project_source_ingestion_service.project_data_source_service,
                "get_project_data_source",
                return_value={"provider_key": "approved_provider", "resource_type": "orders"},
            ),
            patch("services.provider_registry.resource_supported", return_value=True),
        ):
            result = project_source_ingestion_service.list_source_resource_statuses(
                tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A,
                user_id=7, client=client,
            )
        self.assertTrue(result["available"])
        self.assertTrue(result["provider_registered"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["committed_revision"], 4)
        self.assertEqual(result["items"][0]["latest_checkpoint"]["target_revision"], 3)

    def test_resource_status_falls_back_before_incremental_schema(self):
        client = FakeClient({"application_schema_state": [
            {"contract_key": "core", "schema_version": 151},
        ]})
        with patch.object(
            project_source_ingestion_service.project_data_source_service,
            "get_project_data_source",
            return_value={"provider_key": "approved_provider", "resource_type": "orders"},
        ):
            result = project_source_ingestion_service.list_source_resource_statuses(
                tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A,
                user_id=7, client=client,
            )
        self.assertEqual(result["available"], False)
        self.assertEqual(result["items"], [])

    def test_tombstone_none_payload_is_serialized_as_sql_null(self):
        client = FakeClient(rpc_results={"stage_incremental_changes152": 1})
        changes = [{
            "ordinal": 1, "source_record_id": "A", "operation": "delete",
            "payload": None, "content_hash": "a" * 64,
            "schema_fingerprint": "b" * 64,
        }]
        staged = project_source_ingestion_service.stage_incremental_changes(
            tenant_id=1, ingestion_run_id=RUN_A, lease_token=LEASE_A,
            changes=changes, client=client,
        )
        self.assertEqual(staged, 1)
        sent = client.rpc_calls[0][1]["p_changes"][0]
        self.assertNotIn("payload", sent)
        self.assertIn("payload", changes[0])

    def test_non_null_tombstone_payload_is_left_for_database_rejection(self):
        client = FakeClient(rpc_results={"stage_incremental_changes152": 1})
        project_source_ingestion_service.stage_incremental_changes(
            tenant_id=1, ingestion_run_id=RUN_A, lease_token=LEASE_A,
            changes=[{
                "ordinal": 1, "source_record_id": "A", "operation": "delete",
                "payload": {"unexpected": True}, "content_hash": "a" * 64,
                "schema_fingerprint": "b" * 64,
            }], client=client,
        )
        self.assertEqual(
            client.rpc_calls[0][1]["p_changes"][0]["payload"],
            {"unexpected": True},
        )

    def test_schema_availability_fails_closed_before_149(self):
        old = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 148}]})
        current = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 149}]})
        self.assertFalse(project_source_ingestion_service.source_ingestions_available(client=old))
        self.assertTrue(project_source_ingestion_service.source_ingestions_available(client=current))
        with self.assertRaises(HTTPException) as unavailable:
            project_source_ingestion_service.require_source_ingestions_schema(client=old)
        self.assertEqual(unavailable.exception.status_code, 503)

    def test_recovery_schema_is_independently_gated(self):
        old = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 149}]})
        current = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 150}]})
        self.assertFalse(project_source_ingestion_service.ingestion_recovery_available(client=old))
        self.assertTrue(project_source_ingestion_service.ingestion_recovery_available(client=current))

    def test_schema150_reservation_returns_fenced_lease(self):
        client = FakeClient(
            {
                "application_schema_state": [{"contract_key": "core", "schema_version": 150}],
                "builder_projects": [project()], "data_sources": [source()],
            },
            {"reserve_source_ingestion150": [{
                "ingestion_run_id": RUN_A, "run_status": "processing", "disposition": "reserved",
                "lease_token": LEASE_A,
            }]},
        )
        result = project_source_ingestion_service.reserve_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            idempotency_key="upload-150-test", client=client,
        )
        self.assertEqual(result["lease_token"], LEASE_A)
        self.assertEqual(client.rpc_calls[0][0], "reserve_source_ingestion150")
        self.assertEqual(client.rpc_calls[0][1]["p_lease_seconds"], 7200)

    def test_schema151_api_reservation_uses_new_rpc_without_weakening_scope(self):
        api_source = source(source_type="api_provider", provider_key="synthetic_orders", resource_type="orders")
        client = FakeClient(
            {
                "application_schema_state": [{"contract_key": "core", "schema_version": 151}],
                "builder_projects": [project()], "data_sources": [api_source],
            },
            {"reserve_source_ingestion151": [{
                "ingestion_run_id": RUN_A, "run_status": "processing", "disposition": "reserved",
                "lease_token": LEASE_A,
            }]},
        )
        result = project_source_ingestion_service.reserve_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            idempotency_key="api-orders-0001", source_type="api_provider", client=client,
        )
        self.assertEqual(result["lease_token"], LEASE_A)
        self.assertEqual(client.rpc_calls[0][0], "reserve_source_ingestion151")
        with self.assertRaises(HTTPException):
            project_source_ingestion_service.reserve_ingestion(
                tenant_id=2, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
                idempotency_key="api-orders-0002", source_type="api_provider", client=client,
            )

    def test_schema152_api_reservation_binds_stable_resource(self):
        api_source = source(
            source_type="api_provider", provider_key="synthetic_orders", resource_type="orders",
        )
        resource_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        client = FakeClient(
            {
                "application_schema_state": [{"contract_key": "core", "schema_version": 152}],
                "builder_projects": [project()], "data_sources": [api_source],
            },
            {"reserve_incremental_source_ingestion152": [{
                "ingestion_run_id": RUN_A, "run_status": "processing",
                "disposition": "reserved", "lease_token": LEASE_A,
                "source_resource_id": resource_id, "expected_cursor": "orders:2",
            }]},
        )
        result = project_source_ingestion_service.reserve_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            idempotency_key="api-orders-152", source_type="api_provider",
            resource_key="orders", client=client,
        )
        self.assertEqual(result["source_resource_id"], resource_id)
        self.assertEqual(client.rpc_calls[0][0], "reserve_incremental_source_ingestion152")
        self.assertEqual(client.rpc_calls[0][1]["p_resource_key"], "orders")

    def test_reservation_is_scoped_and_passes_idempotency_to_rpc(self):
        client = FakeClient(
            {"builder_projects": [project()], "data_sources": [source()]},
            {"reserve_source_ingestion149": [{
                "ingestion_run_id": RUN_A, "run_status": "processing", "disposition": "reserved",
            }]},
        )
        reserved = project_source_ingestion_service.reserve_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            idempotency_key="upload-123456", client=client,
        )
        self.assertEqual(reserved["ingestion_run_id"], RUN_A)
        self.assertEqual(client.rpc_calls[0][0], "reserve_source_ingestion149")
        self.assertEqual(client.rpc_calls[0][1]["p_tenant_id"], 1)
        self.assertEqual(client.rpc_calls[0][1]["p_idempotency_key"], "upload-123456")

        for changed_source in (
            source(status="archived"),
            source(source_type="api"),
            source(project_id=PROJECT_B),
            source(tenant_id=2),
            source(creator_user_id=8),
        ):
            isolated = FakeClient({"builder_projects": [project()], "data_sources": [changed_source]})
            with self.assertRaises(HTTPException):
                project_source_ingestion_service.reserve_ingestion(
                    tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
                    idempotency_key="upload-123456", client=isolated,
                )

    def test_completion_uses_one_atomic_rpc_and_safe_metadata(self):
        client = FakeClient(rpc_results={"complete_source_ingestion149": [{
            "dataset_id": DATASET_A,
            "version_id": VERSION_A,
            "version_number": 1,
            "ingestion_run_id": RUN_A,
            "ingestion_status": "succeeded",
        }]})
        result = project_source_ingestion_service.complete_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            ingestion_run_id=RUN_A, display_name="sales.csv",
            artifact={
                "storage_object_id": STORAGE_A,
                "original_filename": "sales.csv",
                "content_type": "text/csv",
                "file_extension": ".csv",
                "file_size": 18,
                "sha256": "a" * 64,
                "response": {"rows": 2, "columns": ["secret_name"], "column_count": 1, "format": "csv"},
            }, client=client,
        )
        self.assertEqual(result["persistent_dataset_id"], DATASET_A)
        self.assertEqual(result["ingestion_status"], "succeeded")
        rpc_name, params = client.rpc_calls[0]
        self.assertEqual(rpc_name, "complete_source_ingestion149")
        self.assertEqual(params["p_source_id"], SOURCE_A)
        self.assertNotIn("columns", params["p_run_metadata"])
        self.assertEqual(params["p_run_metadata"]["rows"], 2)

    def test_schema150_completion_and_failure_carry_fence(self):
        client = FakeClient(rpc_results={"complete_source_ingestion150": [{
            "dataset_id": DATASET_A, "version_id": VERSION_A, "version_number": 1,
            "ingestion_run_id": RUN_A, "ingestion_status": "succeeded",
        }], "fail_source_ingestion150": [True]})
        project_source_ingestion_service.complete_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            ingestion_run_id=RUN_A, lease_token=LEASE_A, display_name="sales.csv",
            artifact={"storage_object_id": STORAGE_A, "original_filename": "sales.csv",
                      "content_type": "text/csv", "file_extension": ".csv", "file_size": 18,
                      "sha256": "a" * 64, "response": {}}, client=client,
        )
        project_source_ingestion_service.fail_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            ingestion_run_id=RUN_A, lease_token=LEASE_A, failure_code="ingestion_failed",
            client=client,
        )
        self.assertEqual(client.rpc_calls[0][0], "complete_source_ingestion150")
        self.assertEqual(client.rpc_calls[0][1]["p_lease_token"], LEASE_A)
        self.assertEqual(client.rpc_calls[1][0], "fail_source_ingestion150")

    def test_history_and_detail_are_tenant_project_source_and_user_scoped(self):
        tables = {
            "builder_projects": [project()],
            "data_sources": [source()],
            "data_source_ingestion_runs": [
                run(),
                run(id="88888888-8888-4888-8888-888888888888", project_id=PROJECT_B),
                run(id="99999999-9999-4999-8999-999999999999", tenant_id=2),
                run(id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", initiated_by_user_id=8),
            ],
        }
        client = FakeClient(tables)
        listed = project_source_ingestion_service.list_ingestions(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            limit=20, offset=0, client=client,
        )
        self.assertEqual([item["id"] for item in listed["items"]], [RUN_A])
        detail = project_source_ingestion_service.get_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            ingestion_run_id=RUN_A, client=client,
        )
        self.assertEqual(detail["result_version_id"], VERSION_A)

    def test_ambiguous_completion_recovers_success_or_preserves_unknown(self):
        client = FakeClient({
            "builder_projects": [project()],
            "data_sources": [source()],
            "data_source_ingestion_runs": [run()],
        })
        recovered = project_source_ingestion_service.recover_completed_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            ingestion_run_id=RUN_A, client=client,
        )
        self.assertTrue(recovered["completion_recovered"])
        self.assertEqual(recovered["persistent_dataset_id"], DATASET_A)

        unavailable = FakeClient({"builder_projects": [project()], "data_sources": []})
        self.assertIsNone(project_source_ingestion_service.recover_completed_ingestion(
            tenant_id=1, project_id=PROJECT_A, source_id=SOURCE_A, user_id=7,
            ingestion_run_id=RUN_A, client=unavailable,
        ))

    def test_reconciliation_without_durable_storage_lineage_stays_ambiguous(self):
        claimed = run(
            tenant_id=1, initiated_by_user_id=7, status="processing",
            result_dataset_id=None, result_version_id=None, lease_token=LEASE_A,
            storage_reservation_id=None,
        )
        with (
            patch.object(project_source_ingestion_service, "_query_one", return_value=claimed),
            patch.object(project_source_ingestion_service, "_settle_reconciliation", return_value={}) as settle,
        ):
            result = project_source_ingestion_service.reconcile_claimed_ingestion(
                claimed, client=FakeClient()
            )
        self.assertEqual(result["outcome"], "ambiguous")
        self.assertEqual(settle.call_args.kwargs["code"], "storage_reservation_untracked")

    def test_reconciliation_releases_reserved_quota_before_failure(self):
        claimed = run(
            tenant_id=1, initiated_by_user_id=7, status="processing",
            result_dataset_id=None, result_version_id=None, lease_token=LEASE_A,
            storage_reservation_id=RESERVATION_A,
        )
        reservation = {"id": RESERVATION_A, "tenant_id": 1, "user_id": 7,
                       "category": "dataset", "status": "reserved"}
        with (
            patch.object(project_source_ingestion_service, "_query_one", side_effect=[claimed, reservation]),
            patch.object(project_source_ingestion_service, "finish_storage") as finish,
            patch.object(project_source_ingestion_service, "_settle_reconciliation", return_value={}) as settle,
        ):
            result = project_source_ingestion_service.reconcile_claimed_ingestion(
                claimed, client=FakeClient()
            )
        self.assertEqual(result["outcome"], "failed")
        finish.assert_called_once_with(
            reservation_id=RESERVATION_A, succeeded=False, client=ANY
        )
        self.assertEqual(settle.call_args.kwargs["outcome"], "failed")

    def test_reconciliation_preserves_active_storage_when_release_is_unconfirmed(self):
        claimed = run(
            tenant_id=1, initiated_by_user_id=7, status="processing",
            result_dataset_id=None, result_version_id=None, lease_token=LEASE_A,
            storage_reservation_id=RESERVATION_A, storage_object_id=STORAGE_A,
        )
        reservation = {"id": RESERVATION_A, "tenant_id": 1, "user_id": 7,
                       "category": "dataset", "status": "committed"}
        storage = {"id": STORAGE_A, "reservation_id": RESERVATION_A, "tenant_id": 1,
                   "user_id": 7, "category": "dataset",
                   "storage_key": "tenant_1/user_7/" + "a" * 32 + ".csv", "status": "active"}
        with (
            patch.object(project_source_ingestion_service, "_query_one", side_effect=[claimed, reservation, storage, {"status": "active"}]),
            patch.object(project_source_ingestion_service, "release_storage", side_effect=RuntimeError("down")),
            patch.object(project_source_ingestion_service, "_settle_reconciliation", return_value={}) as settle,
        ):
            result = project_source_ingestion_service.reconcile_claimed_ingestion(
                claimed, client=FakeClient()
            )
        self.assertEqual(result["outcome"], "ambiguous")
        self.assertEqual(settle.call_args.kwargs["code"], "storage_release_failed")

    def test_shared_reconciliation_releases_accounting_before_provider_delete(self):
        claimed = run(
            tenant_id=1, initiated_by_user_id=7, status="processing",
            result_dataset_id=None, result_version_id=None, lease_token=LEASE_A,
            storage_reservation_id=RESERVATION_A, storage_object_id=STORAGE_A,
        )
        reservation = {"id": RESERVATION_A, "tenant_id": 1, "user_id": 7,
                       "category": "dataset", "status": "committed"}
        storage = {
            "id": STORAGE_A, "reservation_id": RESERVATION_A, "tenant_id": 1,
            "user_id": 7, "category": "dataset", "storage_key": "logical.csv",
            "status": "active", "storage_backend": "supabase_private",
            "storage_bucket": "madar-data-immutable",
            "provider_object_key": f"tenant_1/dataset/{RESERVATION_A}/{'a' * 64}.csv",
            "verified_size_bytes": 18, "verified_sha256": "a" * 64,
            "integrity_verified_at": "2026-10-19T00:00:00Z",
        }
        events = []
        store = SimpleNamespace(delete=lambda **_kwargs: events.append("delete"))
        with (
            patch.object(project_source_ingestion_service, "shared_immutable_storage_available", return_value=True),
            patch.object(project_source_ingestion_service, "_query_one", side_effect=[claimed, reservation, storage]),
            patch.object(project_source_ingestion_service, "release_storage",
                         side_effect=lambda **_kwargs: events.append("release") or True),
            patch.object(project_source_ingestion_service, "configured_store", return_value=store),
            patch.object(project_source_ingestion_service, "_settle_reconciliation", return_value={}),
        ):
            result = project_source_ingestion_service.reconcile_claimed_ingestion(
                claimed, client=FakeClient()
            )
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(events, ["release", "delete"])

    def test_bounded_reconciliation_isolates_one_run_failure(self):
        second_run = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaab"
        claimed = [
            run(status="processing", lease_token=LEASE_A),
            run(id=second_run, status="processing", lease_token=LEASE_A),
        ]
        client = FakeClient(
            {"application_schema_state": [{"contract_key": "core", "schema_version": 150}]},
            {"claim_stale_source_ingestions150": claimed},
        )
        with (
            patch.object(
                project_source_ingestion_service,
                "reconcile_claimed_ingestion",
                side_effect=[RuntimeError("synthetic"), {"id": second_run, "outcome": "failed"}],
            ),
            patch.object(project_source_ingestion_service, "_settle_reconciliation", return_value={}) as settle,
        ):
            result = project_source_ingestion_service.reconcile_stale_ingestions(
                worker_id="test-worker", client=client
            )
        self.assertEqual(result["claimed"], 2)
        self.assertEqual([item["outcome"] for item in result["results"]], ["ambiguous", "failed"])
        self.assertEqual(settle.call_args.kwargs["code"], "reconciliation_internal_error")


class ProjectSourceIngestionRouteTests(unittest.TestCase):
    def _file(self):
        return UploadFile(filename="sales.csv", file=BytesIO(b"name,value\na,1\n"))

    def test_authorized_upload_reuses_upload_engine_and_completes_run(self):
        reservation = {"ingestion_run_id": RUN_A, "disposition": "reserved"}

        async def fake_upload(
            _file, *, tenant_id, user_id, metadata_persister, metadata_failure_resolver
        ):
            persisted = metadata_persister({
                "storage_object_id": STORAGE_A, "original_filename": "sales.csv",
                "content_type": "text/csv", "file_extension": ".csv", "file_size": 18,
                "sha256": "a" * 64, "response": {"rows": 1, "column_count": 2},
            })
            return {"rows": 1, **persisted}

        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(project_source_ingestion_service, "reserve_ingestion", return_value=reservation),
            patch.object(project_source_ingestion_service, "complete_ingestion", return_value={
                "persistent_dataset_id": DATASET_A, "dataset_version_id": VERSION_A,
                "ingestion_run_id": RUN_A, "ingestion_status": "succeeded",
            }) as complete,
            patch.object(data_services, "process_upload", side_effect=fake_upload) as upload,
        ):
            result = asyncio.run(data_routes.upload_source_ingestion(
                user_id=7, project_id=PROJECT_A, source_id=SOURCE_A,
                request=SimpleNamespace(), response=SimpleNamespace(status_code=201),
                file=self._file(), idempotency_key="upload-123456",
            ))
        self.assertEqual(result["ingestion_run_id"], RUN_A)
        upload.assert_called_once()
        complete.assert_called_once()

    def test_succeeded_idempotent_replay_does_not_write_file_again(self):
        response = SimpleNamespace(status_code=201)
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(project_source_ingestion_service, "reserve_ingestion", return_value={
                "ingestion_run_id": RUN_A, "disposition": "succeeded",
                "result_dataset_id": DATASET_A, "result_version_id": VERSION_A,
            }),
            patch.object(data_services, "process_upload") as upload,
        ):
            result = asyncio.run(data_routes.upload_source_ingestion(
                user_id=7, project_id=PROJECT_A, source_id=SOURCE_A,
                request=SimpleNamespace(), response=response, file=self._file(),
                idempotency_key="upload-123456",
            ))
        self.assertTrue(result["idempotent_replay"])
        self.assertEqual(response.status_code, 200)
        upload.assert_not_called()

    def test_schema150_upload_wires_heartbeat_and_storage_attachments(self):
        reservation = {"ingestion_run_id": RUN_A, "disposition": "reserved", "lease_token": LEASE_A}
        observed = {}

        async def fake_upload(_file, *, tenant_id, user_id, **options):
            observed.update(options)
            options["lifecycle_heartbeat"]()
            options["storage_reservation_persister"](RESERVATION_A)
            options["storage_object_persister"](STORAGE_A)
            return {"ingestion_run_id": RUN_A, "ingestion_status": "succeeded"}

        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(project_source_ingestion_service, "reserve_ingestion", return_value=reservation),
            patch.object(project_source_ingestion_service, "heartbeat_ingestion") as heartbeat,
            patch.object(project_source_ingestion_service, "attach_storage_reservation") as attach_reservation,
            patch.object(project_source_ingestion_service, "attach_storage_object") as attach_object,
            patch.object(data_services, "process_upload", side_effect=fake_upload),
        ):
            asyncio.run(data_routes.upload_source_ingestion(
                user_id=7, project_id=PROJECT_A, source_id=SOURCE_A,
                request=SimpleNamespace(), response=SimpleNamespace(status_code=201),
                file=self._file(), idempotency_key="upload-150-test",
            ))
        heartbeat.assert_called_once()
        attach_reservation.assert_called_once()
        attach_object.assert_called_once()
        self.assertIn("storage_object_failure_resolver", observed)

    def test_upload_failure_records_only_safe_failure_code(self):
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(project_source_ingestion_service, "reserve_ingestion", return_value={
                "ingestion_run_id": RUN_A, "disposition": "reserved",
            }),
            patch.object(data_services, "process_upload", side_effect=HTTPException(status_code=413, detail="raw")),
            patch.object(project_source_ingestion_service, "fail_ingestion") as failed,
        ):
            with self.assertRaises(HTTPException):
                asyncio.run(data_routes.upload_source_ingestion(
                    user_id=7, project_id=PROJECT_A, source_id=SOURCE_A,
                    request=SimpleNamespace(), response=SimpleNamespace(), file=self._file(),
                    idempotency_key="upload-123456",
                ))
        self.assertEqual(failed.call_args.kwargs["failure_code"], "upload_too_large")

    def test_history_falls_back_before_migration_149(self):
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(project_source_ingestion_service, "source_ingestions_available", return_value=False),
            patch.object(project_source_ingestion_service, "list_ingestions") as listing,
        ):
            result = data_routes.list_source_ingestions(
                user_id=7, project_id=PROJECT_A, source_id=SOURCE_A,
                request=SimpleNamespace(), response=SimpleNamespace(), limit=20, offset=0,
            )
        self.assertFalse(result["available"])
        listing.assert_not_called()


if __name__ == "__main__":
    unittest.main()
