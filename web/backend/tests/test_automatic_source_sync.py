import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from data_analysis.routes import data_routes
from services import automatic_source_sync_service as service


PROJECT = "11111111-1111-4111-8111-111111111111"
SOURCE = "22222222-2222-4222-8222-222222222222"
RESOURCE = "33333333-3333-4333-8333-333333333333"
SCHEDULE = "44444444-4444-4444-8444-444444444444"
RUN = "55555555-5555-4555-8555-555555555555"
LEASE = "66666666-6666-4666-8666-666666666666"
RUN_LEASE = "77777777-7777-4777-8777-777777777777"


class Response:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, data):
        self.data = data
    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self
    def execute(self): return Response(self.data)


class Database:
    def __init__(self):
        self.calls = []
        self.responses = {}
    def table(self, name):
        return Query([{"schema_version": 156}] if name == "application_schema_state" else [])
    def rpc(self, name, params):
        self.calls.append((name, params))
        return Query(self.responses.get(name, True))


def claim():
    return {
        "schedule_id": SCHEDULE, "lease_token": LEASE, "fence": 3,
        "tenant_id": 1, "project_id": PROJECT, "source_id": SOURCE,
        "source_resource_id": RESOURCE, "resource_key": "records",
        "provider_key": "http_fixture", "actor_user_id": 7,
        "credential_revision": 4, "interval_seconds": 3600,
    }


class AutomaticSourceSyncTests(unittest.TestCase):
    def test_schema_gate_and_schedule_configuration_are_bounded(self):
        database = Database()
        database.responses["configure_data_source_sync156"] = [{"id": SCHEDULE}]
        self.assertTrue(service.automatic_sync_available(client=database))
        result = service.configure_schedule(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE,
            resource_id=RESOURCE, user_id=7, enabled=True,
            interval_seconds=1, client=database,
        )
        self.assertEqual(result["id"], SCHEDULE)
        _, params = database.calls[-1]
        self.assertEqual(params["p_interval_seconds"], 900)
        self.assertTrue(params["p_enabled"])

    def test_schedule_configuration_accepts_postgrest_composite_object(self):
        database = Database()
        database.responses["configure_data_source_sync156"] = {
            "id": SCHEDULE, "enabled": True,
        }
        result = service.configure_schedule(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE,
            resource_id=RESOURCE, user_id=7, enabled=True,
            interval_seconds=900, client=database,
        )
        self.assertEqual(result, {"id": SCHEDULE, "enabled": True})

    def test_claim_passes_operator_concurrency_limits_and_clock(self):
        database = Database()
        database.responses["claim_due_data_source_syncs156"] = [claim()]
        result = service.claim_due_syncs(
            worker_id="worker-1", limit=8, tenant_limit=2, provider_limit=3,
            now="2030-01-01T00:00:00Z", client=database,
        )
        self.assertEqual(result[0]["schedule_id"], SCHEDULE)
        _, params = database.calls[-1]
        self.assertEqual(params["p_tenant_limit"], 2)
        self.assertEqual(params["p_provider_limit"], 3)
        self.assertEqual(params["p_now"], "2030-01-01T00:00:00Z")

    def test_disabled_or_not_due_selection_is_owned_by_database_rpc(self):
        database = Database()
        database.responses["claim_due_data_source_syncs156"] = []
        self.assertEqual(service.claim_due_syncs(worker_id="worker-1", client=database), [])
        self.assertEqual(database.calls[-1][0], "claim_due_data_source_syncs156")

    def test_success_reuses_incremental_commit_and_enqueues_checkpoint(self):
        database = Database()
        database.responses["complete_source_sync156"] = [{"id": SCHEDULE, "status": "idle"}]
        artifact = {"storage_object_id": "88888888-8888-4888-8888-888888888888",
                    "sha256": "a" * 64,
                    "provider_metadata": {"credential": {
                        "credential_id": "99999999-9999-4999-8999-999999999999",
                        "credential_version": 2, "source_revision": 4}}}
        batch = SimpleNamespace(
            changes=({"ordinal": 1},), next_cursor="cursor-2",
            schema_fingerprint="b" * 64,
        )

        async def process(**options):
            persisted = options["incremental_persister"](artifact, batch)
            return {**persisted, "provider": {"next_cursor": "cursor-2"}}

        with (
            patch.object(service.project_source_ingestion_service, "reserve_ingestion", return_value={
                "disposition": "reserved", "ingestion_run_id": RUN,
                "lease_token": RUN_LEASE, "source_resource_id": RESOURCE,
                "expected_cursor": "cursor-1", "shared_immutable_storage": True,
            }),
            patch.object(service.project_source_ingestion_service, "stage_incremental_changes") as stage,
            patch.object(service.project_source_ingestion_service, "complete_incremental_ingestion",
                         return_value={"persistent_dataset_id": "dataset-1", "committed_revision": 2}) as complete,
            patch.object(service.project_api_ingestion_service, "process_api_source", side_effect=process),
            patch.object(service.project_dataset_checkpoint_service, "enqueue_dataset_checkpoint",
                         return_value={"checkpoint_id": "checkpoint-1"}) as checkpoint,
        ):
            result = asyncio.run(service.execute_claim(claim(), client=database))
        self.assertEqual(result["outcome"], "succeeded")
        self.assertEqual(result["committed_revision"], 2)
        stage.assert_called_once()
        self.assertEqual(complete.call_args.kwargs["next_cursor"], "cursor-2")
        checkpoint.assert_called_once_with(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, resource_id=RESOURCE,
            dataset_id="dataset-1", user_id=7, target_revision=2, client=database,
        )
        self.assertEqual(
            [name for name, _ in database.calls],
            ["attach_source_sync_ingestion156", "complete_source_sync156"],
        )

    def test_unchanged_snapshot_settles_without_upload_revision_or_checkpoint(self):
        database = Database()
        database.responses["complete_source_sync156"] = [{"id": SCHEDULE, "status": "idle"}]
        credential = {
            "credential_id": "99999999-9999-4999-8999-999999999999",
            "credential_version": 2, "source_revision": 4,
        }

        async def process(**options):
            persisted = options["noop_persister"]("snapshot:unchanged", credential)
            return {**persisted, "provider": {"next_cursor": "snapshot:unchanged",
                                               "no_changes": True}}

        with (
            patch.object(service.project_source_ingestion_service, "reserve_ingestion", return_value={
                "disposition": "reserved", "ingestion_run_id": RUN,
                "lease_token": RUN_LEASE, "source_resource_id": RESOURCE,
                "expected_cursor": "snapshot:old", "shared_immutable_storage": True,
            }),
            patch.object(service.project_source_ingestion_service, "complete_noop_ingestion",
                         return_value={"persistent_dataset_id": "dataset-1",
                                       "committed_revision": 3, "no_changes": True}) as complete,
            patch.object(service.project_api_ingestion_service, "process_api_source", side_effect=process),
            patch.object(service.project_dataset_checkpoint_service,
                         "enqueue_dataset_checkpoint") as checkpoint,
        ):
            result = asyncio.run(service.execute_claim(claim(), client=database))
        self.assertEqual(result["outcome"], "succeeded")
        self.assertTrue(result["no_changes"])
        self.assertEqual(result["committed_revision"], 3)
        self.assertEqual(complete.call_args.kwargs["next_cursor"], "snapshot:unchanged")
        self.assertEqual(complete.call_args.kwargs["credential_reference"], credential)
        checkpoint.assert_not_called()

    def test_unchanged_snapshot_uses_reconciled_google_sheets_rpc(self):
        database = Database()
        database.responses["complete_noop_source_ingestion161"] = [{
            "dataset_id": "88888888-8888-4888-8888-888888888888",
            "source_resource_id": RESOURCE,
            "committed_revision": 3,
            "ingestion_run_id": RUN,
            "ingestion_status": "succeeded",
        }]
        result = service.project_source_ingestion_service.complete_noop_ingestion(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            ingestion_run_id=RUN, lease_token=RUN_LEASE,
            next_cursor="snapshot:unchanged",
            credential_reference={
                "credential_id": "99999999-9999-4999-8999-999999999999",
                "credential_version": 2, "source_revision": 4,
            },
            client=database,
        )
        self.assertEqual(database.calls[-1][0], "complete_noop_source_ingestion161")
        self.assertEqual(result["committed_revision"], 3)
        self.assertTrue(result["no_changes"])

    def test_checkpoint_failure_does_not_undo_durable_ingestion(self):
        database = Database()
        database.responses["complete_source_sync156"] = [{"id": SCHEDULE}]
        async def process(**_options):
            return {"persistent_dataset_id": "dataset-1", "committed_revision": 1}
        with (
            patch.object(service.project_source_ingestion_service, "reserve_ingestion", return_value={
                "disposition": "reserved", "ingestion_run_id": RUN,
                "lease_token": RUN_LEASE, "source_resource_id": RESOURCE,
            }),
            patch.object(service.project_api_ingestion_service, "process_api_source", side_effect=process),
            patch.object(service.project_dataset_checkpoint_service, "enqueue_dataset_checkpoint",
                         side_effect=RuntimeError("offline")),
        ):
            result = asyncio.run(service.execute_claim(claim(), client=database))
        self.assertEqual(result["outcome"], "succeeded")
        self.assertEqual(result["checkpoint_error"], "checkpoint_enqueue_failed")

    def test_rate_limit_is_transient_and_unauthorized_needs_credentials(self):
        rate = service._classify_failure(HTTPException(
            status_code=429, detail={"code": "provider_rate_limited"}), phase="provider")
        unauthorized = service._classify_failure(HTTPException(
            status_code=401, detail={"code": "provider_unauthorized"}), phase="provider")
        self.assertTrue(rate.transient)
        self.assertFalse(rate.credential_attention)
        self.assertFalse(unauthorized.transient)
        self.assertTrue(unauthorized.credential_attention)

    def test_provider_failure_is_redacted_and_settled(self):
        database = Database()
        database.responses["fail_source_sync156"] = [{"id": SCHEDULE, "status": "backoff"}]
        with patch.object(
            service.project_source_ingestion_service, "reserve_ingestion",
            side_effect=HTTPException(status_code=503, detail={"code": "provider_unavailable"}),
        ):
            result = asyncio.run(service.execute_claim(claim(), client=database))
        self.assertEqual(result, {
            "schedule_id": SCHEDULE, "outcome": "failed",
            "error_category": "provider_unavailable", "retryable": True,
            "credential_attention": False,
        })
        _, params = database.calls[-1]
        self.assertEqual(params["p_diagnostic_metadata"], {"phase": "provider"})
        self.assertNotIn("detail", params["p_diagnostic_metadata"])

    def test_missing_active_credential_requires_attention_not_retry(self):
        database = Database()
        database.responses["fail_source_sync156"] = [{"id": SCHEDULE}]
        with (
            patch.object(
                service.project_source_ingestion_service, "reserve_ingestion",
                side_effect=HTTPException(
                    status_code=502, detail={"code": "provider_unavailable"},
                ),
            ),
            patch(
                "services.data_source_credential_service.list_credential_metadata",
                return_value=[{"status": "revoked", "expires_at": None}],
            ),
        ):
            result = asyncio.run(service.execute_claim(claim(), client=database))
        self.assertEqual(result["error_category"], "provider_credentials_revoked")
        self.assertTrue(result["credential_attention"])
        self.assertFalse(result["retryable"])

    def test_lost_completion_response_recovers_without_advancing_twice(self):
        database = Database()
        database.responses["complete_source_sync156"] = [{"id": SCHEDULE}]
        async def process(**_options):
            raise RuntimeError("lost response")
        with (
            patch.object(service.project_source_ingestion_service, "reserve_ingestion", return_value={
                "disposition": "reserved", "ingestion_run_id": RUN,
                "lease_token": RUN_LEASE, "source_resource_id": RESOURCE,
            }),
            patch.object(service.project_api_ingestion_service, "process_api_source", side_effect=process),
            patch.object(service.project_source_ingestion_service, "recover_completed_ingestion",
                         return_value={"persistent_dataset_id": "dataset-1", "committed_revision": 5}),
        ):
            result = asyncio.run(service.execute_claim(claim(), client=database))
        self.assertTrue(result["completion_recovered"])
        self.assertEqual(result["committed_revision"], 5)
        self.assertEqual([name for name, _ in database.calls].count("complete_source_sync156"), 1)

    def test_batch_reconciles_before_claiming(self):
        with (
            patch.object(service, "reconcile_expired_claims", return_value=[{"outcome": "backoff"}]) as reconcile,
            patch.object(service, "claim_due_syncs", return_value=[]) as claim_due,
        ):
            result = asyncio.run(service.run_batch(worker_id="worker-1", client=Database()))
        self.assertEqual(result["claimed"], 0)
        reconcile.assert_called_once()
        claim_due.assert_called_once()

    def test_schedule_read_falls_back_before_migration_activation(self):
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(service, "automatic_sync_available", return_value=False),
        ):
            result = data_routes.get_automatic_sync_schedule(
                user_id=7, project_id=PROJECT, source_id=SOURCE,
                resource_id=RESOURCE, request=SimpleNamespace(),
                response=SimpleNamespace(),
            )
        self.assertEqual(result, {"available": False, "schedule": None})

    def test_schedule_write_propagates_authorized_tenant_scope(self):
        saved = {"id": SCHEDULE, "enabled": True, "interval_seconds": 1800}
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("9", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(service, "automatic_sync_available", return_value=True),
            patch.object(service, "configure_schedule", return_value=saved) as configure,
        ):
            result = data_routes.configure_automatic_sync_schedule(
                user_id=7, project_id=PROJECT, source_id=SOURCE,
                resource_id=RESOURCE,
                payload=data_routes.ConfigureAutomaticSyncRequest(
                    enabled=True, interval_seconds=1800, expected_fence=4,
                ),
                request=SimpleNamespace(), response=SimpleNamespace(),
            )
        self.assertEqual(result, {"available": True, "schedule": saved})
        configure.assert_called_once_with(
            tenant_id=9, project_id=PROJECT, source_id=SOURCE,
            resource_id=RESOURCE, user_id=7, enabled=True,
            interval_seconds=1800, expected_fence=4,
        )

    def test_resource_status_route_propagates_authorized_scope(self):
        expected = {"available": True, "items": []}
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("9", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit") as rate_limit,
            patch.object(
                data_routes.project_source_ingestion_service,
                "list_source_resource_statuses",
                return_value=expected,
            ) as list_resources,
        ):
            result = data_routes.list_source_resource_statuses(
                user_id=7, project_id=PROJECT, source_id=SOURCE,
                request=SimpleNamespace(), response=SimpleNamespace(), limit=25,
            )
        self.assertEqual(result, expected)
        rate_limit.assert_called_once()
        list_resources.assert_called_once_with(
            tenant_id=9, project_id=PROJECT, source_id=SOURCE,
            user_id=7, limit=25,
        )

    def test_schedule_routes_propagate_authentication_and_authorization_denials(self):
        for status_code in (401, 403):
            with (
                self.subTest(status_code=status_code),
                patch.object(
                    data_routes, "get_storage_scope",
                    side_effect=HTTPException(status_code=status_code, detail="denied"),
                ),
                patch.object(service, "get_schedule") as get_schedule,
            ):
                with self.assertRaises(HTTPException) as denied:
                    data_routes.get_automatic_sync_schedule(
                        user_id=7, project_id=PROJECT, source_id=SOURCE,
                        resource_id=RESOURCE, request=SimpleNamespace(),
                        response=SimpleNamespace(),
                    )
                self.assertEqual(denied.exception.status_code, status_code)
                get_schedule.assert_not_called()


if __name__ == "__main__":
    unittest.main()
