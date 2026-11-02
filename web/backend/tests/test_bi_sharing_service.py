import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from services import bi_sharing_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DASHBOARD = "22222222-2222-4222-8222-222222222222"
REPORT = "33333333-3333-4333-8333-333333333333"


class Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.equals = []
        self.not_equals = []
        self.limit_value = None

    def select(self, *_args): return self
    def eq(self, key, value): self.equals.append((key, value)); return self
    def neq(self, key, value): self.not_equals.append((key, value)); return self
    def is_(self, key, value): self.equals.append((key, None if value == "null" else value)); return self
    def in_(self, key, values): self.rows = [row for row in self.rows if row.get(key) in values]; return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, value): self.limit_value = value; return self

    def execute(self):
        rows = [row for row in self.rows if all(row.get(key) == value for key, value in self.equals)
                and all(row.get(key) != value for key, value in self.not_equals)]
        return SimpleNamespace(data=rows[:self.limit_value] if self.limit_value is not None else rows)


class Client:
    def __init__(self, tables=None, rpc_value=None, rpc_error=None):
        self.tables = tables or {}
        self.rpc_value = rpc_value
        self.rpc_error = rpc_error
        self.rpc_calls = []

    def table(self, name): return Query(self.tables.get(name, []))

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        if self.rpc_error:
            raise self.rpc_error
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.rpc_value))


class BiSharingServiceTests(unittest.TestCase):
    def patches(self):
        return (
            patch.object(bi_sharing_service.project_dataset_service, "require_data_project", return_value={"id": PROJECT}),
            patch.object(bi_sharing_service, "sharing_available", return_value=True),
        )

    def test_report_fields_are_compatible_before_and_after_lifecycle_schema(self):
        with patch.object(bi_sharing_service.project_dataset_service, "schema_version", return_value=165):
            self.assertNotIn("artifact_deleted_at", bi_sharing_service._report_fields(client=object()))
        with patch.object(bi_sharing_service.project_dataset_service, "schema_version", return_value=166):
            self.assertIn("artifact_deleted_at", bi_sharing_service._report_fields(client=object()))

    def test_dashboard_viewer_can_read_but_cannot_edit(self):
        client = Client({
            "bi_dashboards": [{"id": DASHBOARD, "tenant_id": 1, "project_id": PROJECT,
                               "creator_user_id": 7, "revision": 2}],
            "bi_dashboard_shares": [{"dashboard_id": DASHBOARD, "tenant_id": 1, "project_id": PROJECT,
                                     "owner_user_id": 7, "member_user_id": 8, "permission": "viewer", "revision": 1}],
        })
        with self.patches()[0], self.patches()[1]:
            result = bi_sharing_service.require_dashboard_access(
                tenant_id=1, project_id=PROJECT, user_id=8, dashboard_id=DASHBOARD, client=client,
            )
            self.assertFalse(result["access"]["can_edit"])
            with self.assertRaises(HTTPException) as denied:
                bi_sharing_service.require_dashboard_access(
                    tenant_id=1, project_id=PROJECT, user_id=8, dashboard_id=DASHBOARD,
                    minimum="editor", client=client,
                )
        self.assertEqual(denied.exception.status_code, 404)

    def test_dashboard_editor_is_scoped_to_exact_tenant_and_project(self):
        client = Client({
            "bi_dashboards": [{"id": DASHBOARD, "tenant_id": 1, "project_id": PROJECT,
                               "creator_user_id": 7, "revision": 2}],
            "bi_dashboard_shares": [{"dashboard_id": DASHBOARD, "tenant_id": 2, "project_id": PROJECT,
                                     "owner_user_id": 7, "member_user_id": 8, "permission": "editor"}],
        })
        with self.patches()[0], self.patches()[1], self.assertRaises(HTTPException) as denied:
            bi_sharing_service.require_dashboard_access(
                tenant_id=1, project_id=PROJECT, user_id=8, dashboard_id=DASHBOARD,
                minimum="editor", client=client,
            )
        self.assertEqual(denied.exception.status_code, 404)

    def test_shared_report_is_view_only_and_private_download_eligible(self):
        report = {"id": REPORT, "tenant_id": 1, "project_id": PROJECT, "creator_user_id": 7,
                  "archived_at": None, "artifact_storage_path": "private/reports/value.csv"}
        client = Client({
            "bi_report_runs": [report],
            "bi_report_shares": [{"report_id": REPORT, "tenant_id": 1, "project_id": PROJECT,
                                  "owner_user_id": 7, "member_user_id": 8, "permission": "viewer"}],
        })
        with self.patches()[0], self.patches()[1]:
            result = bi_sharing_service.require_report_access(
                tenant_id=1, project_id=PROJECT, user_id=8, report_id=REPORT,
                include_storage=True, client=client,
            )
            self.assertEqual(result["resource"]["artifact_storage_path"], "private/reports/value.csv")
            self.assertFalse(result["access"]["can_edit"])
            with self.assertRaises(HTTPException):
                bi_sharing_service.require_report_access(
                    tenant_id=1, project_id=PROJECT, user_id=8, report_id=REPORT,
                    owner_only=True, client=client,
                )

    def test_dashboard_share_mutation_is_revision_checked_and_owner_scoped(self):
        client = Client(rpc_value={"dashboard": {"id": DASHBOARD, "revision": 4}})
        with patch.object(bi_sharing_service, "require_sharing_schema"):
            result = bi_sharing_service.set_dashboard_share(
                tenant_id=1, project_id=PROJECT, user_id=7, dashboard_id=DASHBOARD,
                expected_revision=3, member_user_id=8, permission="editor", client=client,
            )
        self.assertEqual(result["dashboard"]["revision"], 4)
        name, params = client.rpc_calls[0]
        self.assertEqual(name, "set_bi_dashboard_share165")
        self.assertEqual(params["p_owner_user_id"], 7)
        self.assertEqual(params["p_expected_dashboard_revision"], 3)

    def test_revision_conflict_is_http_409(self):
        client = Client(rpc_error=RuntimeError("report_share_revision_conflict SQLSTATE 40001"))
        with patch.object(bi_sharing_service, "require_sharing_schema"), self.assertRaises(HTTPException) as conflict:
            bi_sharing_service.revoke_report_share(
                tenant_id=1, project_id=PROJECT, user_id=7, report_id=REPORT,
                member_user_id=8, expected_share_revision=2, client=client,
            )
        self.assertEqual(conflict.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
