import asyncio
import csv
import io
import math
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from data_analysis.routes import data_routes
from services import project_api_ingestion_service, project_data_source_service
from services.data_source_api_provider import (
    ProviderErrorCategory,
    ProviderFetchError,
    ProviderPage,
    ProviderRecord,
    SyntheticOrdersProvider,
    fetch_bounded_records,
)
from tests.test_provider_http_transport import LocalFixture, TOKEN
from services.provider_credentials import AuthorizedSource, test_credential_store


PROJECT = "11111111-1111-4111-8111-111111111111"
SOURCE = "33333333-3333-4333-8333-333333333333"
RUN = "44444444-4444-4444-8444-444444444444"
LEASE = "99999999-9999-4999-8999-999999999991"
RESOURCE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DATASET = "55555555-5555-4555-8555-555555555555"
VERSION = "66666666-6666-4666-8666-666666666666"


class ApiProviderContractTests(unittest.TestCase):
    def test_synthetic_orders_are_bounded_normalized_and_deterministic(self):
        batch = fetch_bounded_records(SyntheticOrdersProvider(), resource_type="orders")
        self.assertEqual(batch.record_count, 3)
        self.assertEqual(batch.page_count, 1)
        rows = list(csv.DictReader(io.StringIO(batch.csv_bytes.decode("utf-8"))))
        self.assertEqual(rows[0]["_source_record_id"], "A")
        self.assertEqual(batch.next_cursor, "orders:1")
        self.assertEqual(batch.changes[1]["payload"]["amount"], 20)

    def test_invalid_nested_records_and_payload_limits_fail_closed(self):
        class NestedProvider:
            provider_key = "test"
            supported_resources = frozenset({"orders"})
            def fetch_page(self, _request):
                return ProviderPage((ProviderRecord("one", {"unsafe": {"nested": True}}),))

        with self.assertRaises(ProviderFetchError) as invalid:
            fetch_bounded_records(NestedProvider(), resource_type="orders")
        self.assertEqual(invalid.exception.category, ProviderErrorCategory.INVALID_RESPONSE)
        with self.assertRaises(ProviderFetchError) as limited:
            fetch_bounded_records(
                SyntheticOrdersProvider(), resource_type="orders", max_records=2,
            )
        self.assertEqual(limited.exception.category, ProviderErrorCategory.PAYLOAD_TOO_LARGE)

        class DuplicateProvider:
            provider_key = "duplicate"
            supported_resources = frozenset({"orders"})
            def fetch_page(self, _request):
                return ProviderPage((
                    ProviderRecord("same", {"value": 1}),
                    ProviderRecord("same", {"value": 2}),
                ))

        with self.assertRaises(ProviderFetchError) as duplicate:
            fetch_bounded_records(DuplicateProvider(), resource_type="orders")
        self.assertEqual(duplicate.exception.category, ProviderErrorCategory.INVALID_RESPONSE)

        class NonFiniteProvider:
            provider_key = "nonfinite"
            supported_resources = frozenset({"orders"})
            def fetch_page(self, _request):
                return ProviderPage((ProviderRecord("one", {"value": math.inf}),))

        with self.assertRaises(ProviderFetchError) as nonfinite:
            fetch_bounded_records(NonFiniteProvider(), resource_type="orders")
        self.assertEqual(nonfinite.exception.category, ProviderErrorCategory.INVALID_RESPONSE)

    def test_cancellation_timeout_and_pagination_loop_are_explicit(self):
        with self.assertRaises(ProviderFetchError) as cancelled:
            fetch_bounded_records(
                SyntheticOrdersProvider(), resource_type="orders", cancelled=lambda: True,
            )
        self.assertEqual(cancelled.exception.category, ProviderErrorCategory.CANCELLED)

        class TimeoutProvider:
            provider_key = "timeout"
            supported_resources = frozenset({"orders"})
            def fetch_page(self, _request):
                raise ProviderFetchError(ProviderErrorCategory.TIMEOUT)

        with self.assertRaises(ProviderFetchError) as timed_out:
            fetch_bounded_records(TimeoutProvider(), resource_type="orders")
        self.assertEqual(timed_out.exception.category, ProviderErrorCategory.TIMEOUT)

        class LoopProvider:
            provider_key = "loop"
            supported_resources = frozenset({"orders"})
            def fetch_page(self, _request):
                return ProviderPage((ProviderRecord("one", {"value": 1}),), "same")

        with self.assertRaises(ProviderFetchError) as looped:
            fetch_bounded_records(LoopProvider(), resource_type="orders")
        self.assertEqual(looped.exception.category, ProviderErrorCategory.INVALID_RESPONSE)


class ApiSourceExecutionTests(unittest.TestCase):
    def _source(self):
        return {
            "id": SOURCE, "project_id": PROJECT, "source_type": "api_provider",
            "status": "active", "provider_key": "synthetic_orders", "resource_type": "orders",
        }

    def test_execution_reuses_upload_storage_and_injects_safe_provenance(self):
        observed = {}

        async def fake_upload(file, **options):
            observed["payload"] = file.file.read()
            artifact = {
                "storage_object_id": "77777777-7777-4777-8777-777777777777",
                "original_filename": file.filename, "content_type": "text/csv",
                "file_extension": ".csv", "file_size": len(observed["payload"]),
                "sha256": "a" * 64, "response": {"rows": 3, "column_count": 7},
            }
            persisted = options["metadata_persister"](artifact)
            return {"rows": 3, **persisted}

        def persist(artifact):
            observed["provider_metadata"] = artifact["provider_metadata"]
            return {"ingestion_run_id": RUN, "ingestion_status": "succeeded"}

        with (
            patch.object(project_data_source_service, "get_project_data_source", return_value=self._source()),
            patch.object(project_data_source_service, "synthetic_api_provider_enabled", return_value=True),
            patch.object(project_api_ingestion_service.data_services, "process_upload", side_effect=fake_upload) as upload,
        ):
            result = asyncio.run(project_api_ingestion_service.process_api_source(
                tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
                ingestion_run_id=RUN, metadata_persister=persist,
            ))
        upload.assert_called_once()
        self.assertIn(b"Order A", observed["payload"])
        self.assertEqual(observed["provider_metadata"]["record_count"], 3)
        self.assertNotIn("records", observed["provider_metadata"])
        self.assertEqual(result["provider"]["page_count"], 1)

    def test_three_incremental_fixture_batches_have_explicit_ordering(self):
        first = fetch_bounded_records(SyntheticOrdersProvider(1), resource_type="orders")
        second = fetch_bounded_records(
            SyntheticOrdersProvider(2), resource_type="orders", sync_cursor=first.next_cursor,
        )
        third = fetch_bounded_records(
            SyntheticOrdersProvider(3), resource_type="orders", sync_cursor=second.next_cursor,
        )
        self.assertEqual([item["source_record_id"] for item in first.changes], ["A", "B", "C"])
        self.assertEqual([item["source_record_id"] for item in second.changes], ["B", "D"])
        self.assertEqual(third.changes[1]["operation"], "delete")
        self.assertLess(third.changes[2]["source_order"], second.changes[0]["source_order"])
        self.assertEqual(third.changes[0]["content_hash"], second.changes[1]["content_hash"])

    def test_real_http_fixture_reuses_one_incremental_dataset_and_advances_terminal_cursor(self):
        source = {
            **self._source(),
            "provider_key": "http_fixture",
            "resource_type": "records",
        }
        observed = []

        async def fake_upload(file, **options):
            payload = file.file.read()
            artifact = {
                "storage_object_id": "77777777-7777-4777-8777-777777777777",
                "original_filename": file.filename, "content_type": "text/csv",
                "file_extension": ".csv", "file_size": len(payload),
                "sha256": "a" * 64, "response": {"rows": 3, "column_count": 6},
            }
            return options["metadata_persister"](artifact)

        def persist(_artifact, batch):
            observed.append(batch)
            return {
                "persistent_dataset_id": DATASET,
                "dataset_version_id": None,
                "committed_revision": len(observed),
                "ingestion_status": "succeeded",
            }

        with LocalFixture() as fixture, patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": fixture.base_url,
        }, clear=False), patch.object(
            project_data_source_service, "get_project_data_source", return_value=source,
        ), patch.object(
            project_data_source_service, "synthetic_api_provider_enabled", return_value=True,
        ), patch.object(
            project_api_ingestion_service.data_services, "process_upload", side_effect=fake_upload,
        ):
            test_credential_store().put(
                AuthorizedSource(1, PROJECT, SOURCE, "http_fixture"), TOKEN,
            )
            first = asyncio.run(project_api_ingestion_service.process_api_source(
                tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
                ingestion_run_id=RUN, incremental_persister=persist,
            ))
            second = asyncio.run(project_api_ingestion_service.process_api_source(
                tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
                ingestion_run_id="44444444-4444-4444-8444-444444444445",
                incremental_persister=persist, sync_cursor=first["provider"]["next_cursor"],
            ))
        self.assertEqual(first["persistent_dataset_id"], second["persistent_dataset_id"])
        self.assertEqual(first["provider"]["next_cursor"], "cursor-1")
        self.assertEqual(second["provider"]["next_cursor"], "cursor-2")
        self.assertEqual(
            [(change["source_record_id"], change["operation"]) for change in observed[1].changes],
            [("B", "upsert"), ("D", "upsert"), ("A", "delete")],
        )

    def test_api_route_reserves_fenced_run_and_is_idempotent(self):
        async def fake_process(**options):
            artifact = {
                "storage_object_id": "77777777-7777-4777-8777-777777777777",
                "original_filename": "orders.csv", "content_type": "text/csv",
                "file_extension": ".csv", "file_size": 50, "sha256": "a" * 64,
                "response": {"rows": 3}, "provider_metadata": {
                    "provider_key": "synthetic_orders", "resource_type": "orders",
                    "record_count": 3, "page_count": 2,
                },
            }
            return options["metadata_persister"](artifact)

        response = SimpleNamespace(status_code=201)
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(data_routes.project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(data_routes.project_source_ingestion_service, "reserve_ingestion", return_value={
                "ingestion_run_id": RUN, "lease_token": LEASE, "disposition": "reserved",
            }) as reserve,
            patch.object(data_routes.project_source_ingestion_service, "complete_ingestion", return_value={
                "persistent_dataset_id": DATASET, "dataset_version_id": VERSION,
                "ingestion_run_id": RUN, "ingestion_status": "succeeded",
            }) as complete,
            patch.object(project_api_ingestion_service, "process_api_source", side_effect=fake_process),
        ):
            result = asyncio.run(data_routes.ingest_api_source(
                user_id=7, project_id=PROJECT, source_id=SOURCE,
                request=SimpleNamespace(), response=response, idempotency_key="api-orders-0001",
            ))
        self.assertEqual(result["dataset_version_id"], VERSION)
        self.assertEqual(reserve.call_args.kwargs["source_type"], "api_provider")
        self.assertEqual(complete.call_args.kwargs["source_type"], "api_provider")

        replay_response = SimpleNamespace(status_code=201)
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(data_routes.project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(data_routes.project_source_ingestion_service, "reserve_ingestion", return_value={
                "ingestion_run_id": RUN, "disposition": "succeeded",
                "result_dataset_id": DATASET, "result_version_id": VERSION,
            }),
            patch.object(project_api_ingestion_service, "process_api_source") as process,
        ):
            replay = asyncio.run(data_routes.ingest_api_source(
                user_id=7, project_id=PROJECT, source_id=SOURCE,
                request=SimpleNamespace(), response=replay_response, idempotency_key="api-orders-0001",
            ))
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay_response.status_code, 200)
        process.assert_not_called()

    def test_schema152_route_stages_then_atomically_completes_incremental_batch(self):
        batch = fetch_bounded_records(SyntheticOrdersProvider(1), resource_type="orders")

        async def fake_process(**options):
            return options["incremental_persister"]({
                "storage_object_id": "77777777-7777-4777-8777-777777777777",
                "sha256": "a" * 64,
            }, batch)

        response = SimpleNamespace(status_code=201)
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(data_routes.project_source_ingestion_service, "require_source_ingestions_schema"),
            patch.object(data_routes.project_source_ingestion_service, "reserve_ingestion", return_value={
                "ingestion_run_id": RUN, "lease_token": LEASE, "disposition": "reserved",
                "source_resource_id": RESOURCE, "expected_cursor": None,
            }),
            patch.object(data_routes.project_source_ingestion_service, "stage_incremental_changes", return_value=3) as stage,
            patch.object(data_routes.project_source_ingestion_service, "complete_incremental_ingestion", return_value={
                "persistent_dataset_id": DATASET, "dataset_version_id": None,
                "source_resource_id": RESOURCE, "committed_revision": 1,
                "ingestion_run_id": RUN, "ingestion_status": "succeeded",
            }) as complete,
            patch.object(project_api_ingestion_service, "process_api_source", side_effect=fake_process),
        ):
            result = asyncio.run(data_routes.ingest_api_source(
                user_id=7, project_id=PROJECT, source_id=SOURCE,
                request=SimpleNamespace(), response=response,
                idempotency_key="api-orders-152-1", resource_type="orders", fixture_batch=1,
            ))
        self.assertEqual(result["committed_revision"], 1)
        self.assertIsNone(result["dataset_version_id"])
        self.assertEqual(len(stage.call_args.kwargs["changes"]), 3)
        self.assertEqual(complete.call_args.kwargs["next_cursor"], "orders:1")

    def test_production_fixture_is_not_exposed(self):
        with patch.dict("os.environ", {"APP_ENV": "production"}, clear=False):
            self.assertFalse(project_data_source_service.synthetic_api_provider_enabled())
        error = project_api_ingestion_service._safe_provider_http_error(
            ProviderFetchError(ProviderErrorCategory.UNAVAILABLE)
        )
        self.assertIsInstance(error, HTTPException)
        self.assertNotIn("response", str(error.detail).lower())


if __name__ == "__main__":
    unittest.main()
