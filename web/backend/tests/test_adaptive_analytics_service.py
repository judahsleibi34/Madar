from tests.account_work_test_support import account_fixture
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from data_analysis import services as data_services
from data_analysis.assisted.assisted_analysis import AssistedAnalysis
from services import adaptive_analytics_service, bi_dashboard_service, bi_reporting_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
DASHBOARD = "44444444-4444-4444-8444-444444444444"
WIDGET = "55555555-5555-4555-8555-555555555555"


class AdaptiveAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.fence_client = self.enterContext(account_fixture([(3, 7)]))

    def test_central_policy_selects_by_workload_format_operation_and_resources(self):
        cases = [
            ({"workload": "metric", "file_format": "xlsx", "size_bytes": 1024,
              "row_count": 5, "operation": "sum"}, "pandas"),
            ({"workload": "explore", "file_format": "csv", "size_bytes": 11 * 1024 * 1024,
              "row_count": 100_001}, "duckdb"),
            ({"workload": "metric", "file_format": "csv", "size_bytes": 11 * 1024 * 1024,
              "row_count": 100_001, "operation": "sum", "polars_available": True}, "polars"),
            ({"workload": "metric", "file_format": "csv", "size_bytes": 11 * 1024 * 1024,
              "row_count": 100_001, "operation": "median", "polars_available": True}, "unsupported"),
            ({"workload": "metric", "file_format": "xlsx", "size_bytes": 11 * 1024 * 1024,
              "row_count": 100_001, "operation": "sum"}, "unsupported"),
            ({"workload": "metric", "file_format": "csv", "size_bytes": 11 * 1024 * 1024,
              "row_count": 100_001, "operation": "sum", "cleaning_actions": True,
              "polars_available": True}, "unsupported"),
            ({"workload": "metric", "file_format": "csv", "size_bytes": 11 * 1024 * 1024,
              "row_count": 100_001, "operation": "sum", "polars_available": False}, "unsupported"),
        ]
        for inputs, expected in cases:
            with self.subTest(inputs=inputs):
                self.assertEqual(adaptive_analytics_service.select_engine(**inputs).engine, expected)

    def test_polars_matches_pandas_for_supported_scalar_and_grouped_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            path.write_text(
                "region,amount,customer\n"
                "North,10,A\nNorth,,A\nSouth,30,A\nSouth,20,\n,40,C\n",
                encoding="utf-8",
            )
            frame = pd.read_csv(path)
            metrics = [
                {"operation": "count", "group_column": "region"},
                {"operation": "count", "value_column": "amount", "group_column": "region"},
                {"operation": "sum", "value_column": "amount", "group_column": "region"},
                {"operation": "mean", "value_column": "amount", "group_column": "region"},
                {"operation": "min", "value_column": "amount"},
                {"operation": "max", "value_column": "amount"},
                {"operation": "distinct_count", "value_column": "customer",
                 "group_column": "region"},
            ]
            for metric in metrics:
                with self.subTest(metric=metric):
                    pandas_result = AssistedAnalysis(frame).custom_metric(metric)
                    polars_result = adaptive_analytics_service.run_large_metric(
                        authorized_path=str(path), metric=metric, language="en", symbols={},
                        declared_rows=len(frame),
                    )["result"]
                    self.assertEqual(
                        polars_result["tables"][0]["rows"],
                        pandas_result["tables"][0]["rows"],
                    )

    def test_polars_date_metric_matches_pandas_dst_period_and_disclosures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dates.csv"
            path.write_text(
                "observed_at,amount\n"
                "2026-03-08T04:30:00Z,10\n"
                "2026-03-08T05:30:00Z,20\n"
                "2026-03-09T03:30:00Z,30\n"
                "2026-03-09T04:30:00Z,40\n"
                "bad,999\n"
                ",999\n",
                encoding="utf-8",
            )
            metric = {
                "operation": "date_aggregate", "date_column": "observed_at",
                "value_column": "amount", "aggregation": "sum", "period": "day",
                "timezone": "America/New_York", "start_date": "2026-03-08",
                "end_date": "2026-03-08",
            }
            pandas_result = AssistedAnalysis(pd.read_csv(path)).custom_metric(metric)
            polars_result = adaptive_analytics_service.run_large_metric(
                authorized_path=str(path), metric=metric, language="en", symbols={},
                declared_rows=6,
            )["result"]
        self.assertEqual(polars_result["tables"][0]["rows"],
                         pandas_result["tables"][0]["rows"])
        fields = {
            "invalid_date_count", "missing_date_count", "outside_period_count",
            "selected_row_count", "total_row_count", "start_inclusive", "end_exclusive",
            "partial_periods", "partial_period_reasons",
        }
        expected = pandas_result["metadata"]["mappings_used"]
        actual = polars_result["metadata"]["mappings_used"]
        self.assertEqual({key: actual[key] for key in fields},
                         {key: expected[key] for key in fields})

    def test_group_cardinality_memory_timeout_and_concurrency_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.write_text(
                "group_name,amount\n" + "".join(f"g-{index},{index}\n" for index in range(501)),
                encoding="utf-8",
            )
            with self.assertRaises(HTTPException) as cardinality:
                adaptive_analytics_service.run_large_metric(
                    authorized_path=str(path),
                    metric={"operation": "sum", "value_column": "amount",
                            "group_column": "group_name"},
                    language="en", symbols={}, declared_rows=501,
                )
            self.assertEqual(cardinality.exception.status_code, 413)
            self.assertEqual(cardinality.exception.detail["code"],
                             "analytics_group_cardinality_exceeded")

            with patch.object(adaptive_analytics_service, "POLARS_WORKER_RSS_BYTES", 1), \
                    self.assertRaises(HTTPException) as memory:
                adaptive_analytics_service.run_large_metric(
                    authorized_path=str(path), metric={"operation": "count"},
                    language="en", symbols={}, declared_rows=501,
                )
            self.assertEqual(memory.exception.status_code, 413)

            with patch.object(adaptive_analytics_service, "POLARS_WORKER_TIMEOUT_SECONDS", 0.001), \
                    self.assertRaises(HTTPException) as timeout:
                adaptive_analytics_service.run_large_metric(
                    authorized_path=str(path), metric={"operation": "count"},
                    language="en", symbols={}, declared_rows=501,
                )
            self.assertEqual(timeout.exception.status_code, 408)

        slots = adaptive_analytics_service._polars_slots
        self.assertTrue(slots.acquire(blocking=False))
        self.assertTrue(slots.acquire(blocking=False))
        try:
            with self.assertRaises(HTTPException) as busy:
                adaptive_analytics_service._run_polars_worker(
                    authorized_path="unused.csv", request={},
                )
            self.assertEqual(busy.exception.status_code, 429)
        finally:
            slots.release()
            slots.release()

    def test_late_csv_type_drift_and_excessive_width_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            drift = Path(directory) / "drift.csv"
            drift.write_text(
                "amount\n" + "".join(f"{index}\n" for index in range(10_000)) + "not-a-number\n",
                encoding="utf-8",
            )
            with self.assertRaises(HTTPException) as incompatible:
                adaptive_analytics_service.run_large_metric(
                    authorized_path=str(drift),
                    metric={"operation": "sum", "value_column": "amount"},
                    language="en", symbols={}, declared_rows=10_001,
                )
            self.assertEqual(incompatible.exception.status_code, 422)
            self.assertEqual(incompatible.exception.detail["code"],
                             "analytics_incompatible_schema")

            wide = Path(directory) / "wide.csv"
            headers = [f"column_{index}" for index in range(257)]
            wide.write_text(",".join(headers) + "\n" + ",".join("1" for _ in headers) + "\n",
                            encoding="utf-8")
            with self.assertRaises(HTTPException) as width:
                adaptive_analytics_service.run_large_metric(
                    authorized_path=str(wide), metric={"operation": "count"},
                    language="en", symbols={}, declared_rows=1,
                )
            self.assertEqual(width.exception.status_code, 413)
            self.assertEqual(width.exception.detail["code"],
                             "analytics_column_limit_exceeded")

    def test_data_service_never_falls_back_to_pandas_for_oversized_unsupported_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.csv"
            path.write_text("amount\n10\n20\n", encoding="utf-8")
            version = {"size_bytes": 11 * 1024 * 1024, "file_metadata": {"rows": 100_001}}
            with patch.object(data_services, "authorize_dataset_input_path", return_value=str(path)), \
                    patch.object(data_services, "build_authorized_cleaner") as cleaner:
                with self.assertRaises(HTTPException) as denied:
                    data_services.run_assisted_analysis(
                        input_path="large.csv", cleaning_actions=[{"operation": "drop_missing"}],
                        question=None, metric={"operation": "sum", "value_column": "amount"},
                        language="en", symbols={}, tenant_id="1", user_id="7",
                        dataset_version=version,
                    )
            self.assertEqual(denied.exception.status_code, 413)
            self.assertEqual(denied.exception.detail["code"],
                             "large_cleaning_pipeline_unsupported")
            cleaner.assert_not_called()

    def test_data_service_automatically_selects_pandas_then_polars(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.csv"
            path.write_text("amount\n10\n20\n", encoding="utf-8")
            cleaner = unittest.mock.MagicMock()
            cleaner.read.return_value = pd.DataFrame({"amount": [10, 20]})
            cleaner.prepare_dataframe.side_effect = lambda frame: (frame, [])
            cleaner.profile_dataframe.return_value = {}
            with patch.object(data_services, "authorize_dataset_input_path", return_value=str(path)), \
                    patch.object(data_services, "build_authorized_cleaner", return_value=cleaner):
                small = data_services.run_assisted_analysis(
                    input_path="adaptive.csv", cleaning_actions=[], question=None,
                    metric={"operation": "sum", "value_column": "amount"},
                    language="en", symbols={}, tenant_id="1", user_id="7",
                    dataset_version={"size_bytes": path.stat().st_size,
                                     "file_metadata": {"rows": 2}},
                )
                large = data_services.run_assisted_analysis(
                    input_path="adaptive.csv", cleaning_actions=[], question=None,
                    metric={"operation": "sum", "value_column": "amount"},
                    language="en", symbols={}, tenant_id="1", user_id="7",
                    dataset_version={"size_bytes": 11 * 1024 * 1024,
                                     "file_metadata": {"rows": 100_001}},
                )
        self.assertEqual(small["metadata"]["analytics_engine"], "pandas")
        self.assertEqual(large["metadata"]["analytics_engine"], "polars")
        self.assertEqual(small["result"]["kpis"][0]["value"],
                         large["result"]["kpis"][0]["value"])

    def test_large_dashboard_and_immutable_report_use_exact_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard.csv"
            with path.open("w", encoding="utf-8") as output:
                output.write("amount\n")
                for index in range(100_001):
                    output.write(f"{index}\n")
            version = {
                "id": VERSION, "version_number": 4, "version_kind": "derived",
                "content_hash": "a" * 64, "size_bytes": path.stat().st_size,
                "file_metadata": {"rows": 100_001},
            }
            dashboard = {
                "id": DASHBOARD, "revision": 4, "creator_user_id": 7,
                "access": {"can_edit": True},
                "widgets": [{
                    "id": WIDGET, "widget_type": "kpi", "title": "Rows",
                    "dataset_id": DATASET, "dataset_version_id": VERSION,
                    "version_policy": "pinned", "analysis_spec": {"operation": "count"},
                    "layout_config": {}, "display_options": {},
                }],
            }
            persistent = {"storage_identifier": "dashboard.csv", "version": version}
            with patch.object(bi_dashboard_service, "get_dashboard", return_value=dashboard), \
                    patch.object(bi_dashboard_service.project_dataset_service,
                                 "resolve_project_dataset_version", return_value=persistent) as resolve, \
                    patch.object(data_services, "authorize_dataset_input_path", return_value=str(path)):
                widget_result = bi_dashboard_service.execute_widget(
                    tenant_id=3, project_id=PROJECT, user_id=7, dashboard_id=DASHBOARD,
                    widget_id=WIDGET, refresh_latest=False, language="en", client=object(),
                )
            self.assertEqual(widget_result["status"], "ready")
            self.assertEqual(widget_result["result"]["kpis"][0]["value"], 100_001)
            self.assertEqual(widget_result["provenance"]["dataset_version_id"], VERSION)
            self.assertEqual(resolve.call_args.kwargs["version_id"], VERSION)

            run = {
                "id": "66666666-6666-4666-8666-666666666666",
                "tenant_id": 3, "project_id": PROJECT, "creator_user_id": 7,
                "definition_snapshot": {
                    "dashboard": {"name": "Operations"}, "report_policy": {},
                    "widgets": [{"id": WIDGET, "title": "Rows",
                                 "analysis_spec": {"operation": "count"}}],
                },
                "version_vector": [{
                    "widget_id": WIDGET, "dataset_id": DATASET,
                    "dataset_version_id": VERSION, "version_number": 4,
                    "content_hash": "a" * 64, "version_policy": "pinned",
                }],
            }
            with patch.object(
                bi_reporting_service.project_dataset_service, "get_project_dataset_freshness",
                return_value={"available": True, "resource": {}, "checkpoint": None},
            ), patch.object(
                bi_reporting_service.project_dataset_service,
                "resolve_project_dataset_version", return_value=persistent,
            ) as report_resolve, patch.object(
                data_services, "authorize_dataset_input_path", return_value=str(path),
            ), patch.object(
                bi_reporting_service, "_write_csv_artifact",
                return_value={"storage_key": "x", "filename": "x.csv"},
            ), patch.object(
                bi_reporting_service.project_dataset_service, "schema_version", return_value=166,
            ):
                status, snapshot, warnings, artifact = bi_reporting_service.execute_run(
                    run, client=object(),
                )
        self.assertEqual(status, "completed")
        self.assertEqual(warnings, [])
        self.assertEqual(snapshot["widgets"][0]["result"]["kpis"][0]["value"], 100_001)
        self.assertEqual(snapshot["version_vector"][0]["dataset_version_id"], VERSION)
        self.assertEqual(report_resolve.call_args.kwargs["version_id"], VERSION)
        self.assertIsNotNone(artifact)


if __name__ == "__main__":
    unittest.main()
