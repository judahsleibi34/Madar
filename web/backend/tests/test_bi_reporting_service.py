import tempfile
import unittest
from datetime import datetime, time, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from services import bi_reporting_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
WIDGET = "44444444-4444-4444-8444-444444444444"
RUN = "55555555-5555-4555-8555-555555555555"


def claimed_run(*, require_ready=False):
    return {
        "id": RUN, "tenant_id": 3, "project_id": PROJECT, "creator_user_id": 7,
        "lease_token": "66666666-6666-4666-8666-666666666666", "lease_fence": 2,
        "definition_snapshot": {
            "dashboard": {"name": "Operations"},
            "report_policy": {"require_ready_checkpoints": require_ready},
            "widgets": [{"id": WIDGET, "title": "Rows", "analysis_spec": {"operation": "count"}}],
        },
        "version_vector": [{"widget_id": WIDGET, "dataset_id": DATASET,
                            "dataset_version_id": VERSION, "version_number": 4,
                            "content_hash": "a" * 64, "version_policy": "pinned"}],
    }


class BiReportingServiceTests(unittest.TestCase):
    def test_daily_weekly_monthly_and_dst_resolution_are_deterministic(self):
        spring = bi_reporting_service.next_occurrence(
            cadence="daily", timezone_name="America/New_York", local_time=time(2, 30),
            weekday=None, month_day=None, after=datetime(2026, 3, 8, 6, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(spring, datetime(2026, 3, 8, 7, 0, tzinfo=timezone.utc))
        fall = bi_reporting_service.next_occurrence(
            cadence="daily", timezone_name="America/New_York", local_time=time(1, 30),
            weekday=None, month_day=None, after=datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(fall, datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc))
        monthly = bi_reporting_service.next_occurrence(
            cadence="monthly", timezone_name="UTC", local_time=time(9), weekday=None,
            month_day=31, after=datetime(2027, 1, 31, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(monthly, datetime(2027, 2, 28, 9, tzinfo=timezone.utc))
        weekly = bi_reporting_service.next_occurrence(
            cadence="weekly", timezone_name="UTC", local_time=time(9), weekday=0,
            month_day=None, after=datetime(2026, 10, 25, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(weekly, datetime(2026, 10, 26, 9, tzinfo=timezone.utc))

    def test_invalid_timezone_is_rejected(self):
        with self.assertRaises(HTTPException) as denied:
            bi_reporting_service.validate_timezone("Mars/Olympus")
        self.assertEqual(denied.exception.status_code, 422)

    def test_csv_formula_injection_is_neutralized_and_artifact_is_private(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            bi_reporting_service, "get_private_charts_dir", return_value=Path(directory)
        ):
            artifact = bi_reporting_service._write_csv_artifact(
                run={**claimed_run(), "definition_snapshot": {"dashboard": {"name": "=Unsafe"}}},
                results=[{"title": "=cmd", "status": "ready", "provenance": {},
                          "result": {"kpis": [{"label": "+value", "value": "@payload"}]}}],
            )
            body = (Path(directory) / artifact["storage_key"]).read_text(encoding="utf-8-sig")
            self.assertIn("'=cmd", body)
            self.assertIn("'+value", body)
            self.assertIn("'@payload", body)
            self.assertTrue(artifact["storage_key"].startswith("reports/tenant_3/"))

    @patch.object(bi_reporting_service.project_dataset_service, "get_project_dataset_freshness",
                  return_value={"available": True, "resource": {}, "checkpoint": None})
    @patch.object(bi_reporting_service.project_dataset_service, "resolve_project_dataset_version",
                  return_value={"storage_identifier": "immutable.csv"})
    @patch.object(bi_reporting_service.data_services, "run_assisted_analysis",
                  return_value={"result": {"kpis": [{"label": "Rows", "value": 3}]}})
    @patch.object(bi_reporting_service, "_write_csv_artifact", return_value={"storage_key": "x", "filename": "x.csv"})
    def test_execution_uses_captured_exact_version_vector(self, _artifact, analysis, resolve, _freshness):
        status, snapshot, warnings, artifact = bi_reporting_service.execute_run(claimed_run(), client=object())
        self.assertEqual(status, "completed")
        self.assertEqual(warnings, [])
        self.assertEqual(snapshot["version_vector"][0]["dataset_version_id"], VERSION)
        self.assertEqual(resolve.call_args.kwargs["version_id"], VERSION)
        self.assertEqual(analysis.call_args.kwargs["input_path"], "immutable.csv")
        self.assertIsNotNone(artifact)

    @patch.object(bi_reporting_service.project_dataset_service, "get_project_dataset_freshness",
                  return_value={"available": True, "resource": {"committed_revision": 8,
                      "pending_reconciliation": False}, "checkpoint": {"status": "completed", "target_revision": 7}})
    def test_required_checkpoint_defers_stale_source(self, _freshness):
        with self.assertRaises(bi_reporting_service.ReportExecutionError) as error:
            bi_reporting_service.execute_run(claimed_run(require_ready=True), client=object())
        self.assertEqual(error.exception.code, "report_checkpoint_not_ready")
        self.assertTrue(error.exception.retryable)


if __name__ == "__main__":
    unittest.main()
