import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from services import bi_dashboard_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION_1 = "33333333-3333-4333-8333-333333333331"
VERSION_2 = "33333333-3333-4333-8333-333333333332"
DASHBOARD = "44444444-4444-4444-8444-444444444444"
WIDGET = "55555555-5555-4555-8555-555555555555"


class FakeRpcResult:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return SimpleNamespace(data=self.value)


class FakeClient:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        if self.error:
            raise self.error
        return FakeRpcResult(self.value)


def dashboard(policy="pinned"):
    return {
        "id": DASHBOARD, "revision": 4,
        "widgets": [{
            "id": WIDGET, "widget_type": "kpi", "title": "Rows",
            "dataset_id": DATASET, "dataset_version_id": VERSION_1,
            "version_policy": policy, "analysis_spec": {"operation": "count"},
            "layout_config": {"x": 0, "y": 0, "w": 6, "h": 4},
            "display_options": {"show_table": True},
        }],
    }


class BiDashboardServiceTests(unittest.TestCase):
    def test_analysis_layout_and_display_validation_are_allowlisted(self):
        self.assertEqual(bi_dashboard_service.validate_analysis_spec({
            "operation": "date_aggregate", "date_column": "date", "period": "month",
            "aggregation": "count", "timezone": "UTC",
        })["operation"], "date_aggregate")
        for invalid in (
            {"operation": "sql", "code": "select 1"},
            {"operation": "sum"},
            {"operation": "date_aggregate", "date_column": "date", "timezone": "Asia/Hebron"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(HTTPException) as denied:
                bi_dashboard_service.validate_analysis_spec(invalid)
            self.assertEqual(denied.exception.status_code, 422)
        with self.assertRaises(HTTPException):
            bi_dashboard_service.validate_layout({"x": 10, "y": 0, "w": 4, "h": 3})
        with self.assertRaises(HTTPException):
            bi_dashboard_service.validate_display_options({"html": "<script>"})

    @patch.object(bi_dashboard_service, "dashboards_available", return_value=True)
    def test_revision_conflicts_are_returned_as_http_409(self, _available):
        client = FakeClient(error=RuntimeError("dashboard_revision_conflict SQLSTATE 40001"))
        with self.assertRaises(HTTPException) as conflict:
            bi_dashboard_service.update_dashboard(
                tenant_id=1, project_id=PROJECT, user_id=7, dashboard_id=DASHBOARD,
                expected_revision=2, name="Ops", description="", client=client,
            )
        self.assertEqual(conflict.exception.status_code, 409)

    def _execute(self, policy, refresh_latest):
        with patch.object(bi_dashboard_service, "get_dashboard", return_value=dashboard(policy)), \
             patch.object(bi_dashboard_service.project_dataset_service,
                          "list_project_dataset_versions", return_value={"items": [{"id": VERSION_2}]}), \
             patch.object(bi_dashboard_service.project_dataset_service,
                          "resolve_project_dataset_version", return_value={
                              "storage_identifier": "version.csv",
                              "version": {"id": VERSION_2 if refresh_latest and policy == "latest_committed" else VERSION_1,
                                          "version_number": 2, "version_kind": "derived", "content_hash": "a" * 64},
                          }) as resolve, \
             patch.object(bi_dashboard_service.data_services, "run_assisted_analysis",
                          return_value={"result": {"kpis": [{"value": 3}]}}), \
             patch.object(bi_dashboard_service, "update_widget", return_value={
                 "widget": {**dashboard(policy)["widgets"][0], "dataset_version_id": VERSION_2},
                 "dashboard": {"revision": 5},
             }) as update:
            result = bi_dashboard_service.execute_widget(
                tenant_id=1, project_id=PROJECT, user_id=7, dashboard_id=DASHBOARD,
                widget_id=WIDGET, refresh_latest=refresh_latest, language="en", client=object(),
            )
        return result, resolve, update

    def test_pinned_widget_reopens_its_exact_bound_version(self):
        result, resolve, update = self._execute("pinned", True)
        self.assertEqual(resolve.call_args.kwargs["version_id"], VERSION_1)
        self.assertEqual(result["provenance"]["dataset_version_id"], VERSION_1)
        update.assert_not_called()

    def test_latest_widget_only_advances_on_explicit_successful_refresh(self):
        stale, resolve, update = self._execute("latest_committed", False)
        self.assertEqual(resolve.call_args.kwargs["version_id"], VERSION_1)
        self.assertTrue(stale["latest_available"])
        update.assert_not_called()

        refreshed, resolve, update = self._execute("latest_committed", True)
        self.assertEqual(resolve.call_args.kwargs["version_id"], VERSION_2)
        self.assertEqual(refreshed["dashboard_revision"], 5)
        update.assert_called_once()

    @patch.object(bi_dashboard_service, "get_dashboard", return_value=dashboard("latest_committed"))
    @patch.object(bi_dashboard_service.project_dataset_service, "list_project_dataset_versions",
                  return_value={"items": [{"id": VERSION_2}]})
    @patch.object(bi_dashboard_service.project_dataset_service, "resolve_project_dataset_version",
                  return_value={"storage_identifier": "version.csv", "version": {"id": VERSION_2}})
    @patch.object(bi_dashboard_service.data_services, "run_assisted_analysis", side_effect=ValueError("missing column"))
    @patch.object(bi_dashboard_service, "update_widget")
    def test_incompatible_latest_schema_never_rebinds_widget(self, update, *_mocks):
        result = bi_dashboard_service.execute_widget(
            tenant_id=1, project_id=PROJECT, user_id=7, dashboard_id=DASHBOARD,
            widget_id=WIDGET, refresh_latest=True, language="en", client=object(),
        )
        self.assertEqual(result["status"], "needs_attention")
        self.assertEqual(result["reason"], "schema_incompatible")
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
