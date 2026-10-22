import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from data_analysis.routes import data_routes
from services import project_data_source_service


PROJECT_A = "11111111-1111-4111-8111-111111111111"
PROJECT_B = "22222222-2222-4222-8222-222222222222"
SOURCE_A = "33333333-3333-4333-8333-333333333333"


def project(project_id=PROJECT_A, tenant_id=1):
    return {
        "id": project_id,
        "tenant_id": tenant_id,
        "name": "Data project",
        "status": "draft",
        "draft_schema": {"workspaceKind": "data"},
    }


class FakeQuery:
    def __init__(self, table):
        self.table = table
        self.predicates = []
        self._limit = None
        self._range = None
        self._order = None
        self._descending = False
        self.operation = "select"
        self.payload = None

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.predicates.append((field, value, True))
        return self

    def neq(self, field, value):
        self.predicates.append((field, value, False))
        return self

    def order(self, field, desc=False):
        self._order = field
        self._descending = desc
        return self

    def limit(self, value):
        self._limit = value
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = dict(payload)
        return self

    def _matches(self, row):
        return all(
            (row.get(field) == value) if equals else (row.get(field) != value)
            for field, value, equals in self.predicates
        )

    def execute(self):
        if self.operation == "insert":
            row = {
                "id": SOURCE_A,
                "created_at": "2026-10-18T00:00:00Z",
                "updated_at": "2026-10-18T00:00:00Z",
                "latest_dataset_id": None,
                "latest_version_id": None,
                "last_ingested_at": None,
                "last_successful_sync_at": None,
                "last_error_code": None,
                **self.payload,
            }
            row["display_name_key"] = row["display_name"].strip().lower()
            self.table.append(row)
            return SimpleNamespace(data=[dict(row)])

        rows = [row for row in self.table if self._matches(row)]
        if self.operation == "update":
            for row in rows:
                row.update(self.payload)
            return SimpleNamespace(data=[dict(row) for row in rows])
        if self._order:
            rows.sort(key=lambda row: row.get(self._order) or "", reverse=self._descending)
        if self._range is not None:
            rows = rows[self._range[0] : self._range[1] + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        return SimpleNamespace(data=[dict(row) for row in rows])


class FakeClient:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return FakeQuery(self.tables.setdefault(name, []))


def source(**overrides):
    row = {
        "id": SOURCE_A,
        "tenant_id": 1,
        "project_id": PROJECT_A,
        "creator_user_id": 7,
        "source_type": "spreadsheet_upload",
        "display_name": "Monthly sales",
        "display_name_key": "monthly sales",
        "status": "active",
        "sync_mode": "manual",
        "sync_state": "idle",
        "latest_dataset_id": None,
        "latest_version_id": None,
        "created_at": "2026-10-18T00:00:00Z",
        "updated_at": "2026-10-18T00:00:00Z",
    }
    row.update(overrides)
    return row


class ProjectDataSourceServiceTests(unittest.TestCase):
    def test_schema_availability_fails_closed_before_148(self):
        old = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 147}]})
        current = FakeClient({"application_schema_state": [{"contract_key": "core", "schema_version": 148}]})
        self.assertFalse(project_data_source_service.project_data_sources_available(client=old))
        self.assertTrue(project_data_source_service.project_data_sources_available(client=current))
        with self.assertRaises(HTTPException) as unavailable:
            project_data_source_service.require_project_data_sources_schema(client=old)
        self.assertEqual(unavailable.exception.status_code, 503)

    def test_capabilities_are_project_scoped_and_hide_server_connection_details(self):
        client = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 156}],
            "builder_projects": [project()],
        })
        safe_provider = {
            "key": "approved_provider",
            "label": "Approved provider",
            "description": "Approved business records.",
            "credential_type": "bearer",
            "resources": [{"key": "orders", "label": "Orders"}],
        }
        with patch(
            "services.provider_registry.public_provider_capabilities",
            return_value=[safe_provider],
        ):
            result = project_data_source_service.project_data_source_capabilities(
                tenant_id=1, project_id=PROJECT_A, user_id=7, client=client,
            )
        self.assertTrue(result["source_registry_available"])
        self.assertTrue(result["automatic_sync_available"])
        self.assertEqual(result["providers"], [safe_provider])
        self.assertNotIn("base_url", repr(result))
        self.assertNotIn("headers", repr(result))
        with self.assertRaises(HTTPException) as denied:
            project_data_source_service.project_data_source_capabilities(
                tenant_id=2, project_id=PROJECT_A, user_id=7, client=client,
            )
        self.assertEqual(denied.exception.status_code, 404)

    def test_api_source_requires_schema151_and_non_production_fixture(self):
        old = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 150}],
            "builder_projects": [project()], "data_sources": [],
        })
        with self.assertRaises(HTTPException) as upgrade:
            project_data_source_service.create_project_data_source(
                tenant_id=1, project_id=PROJECT_A, user_id=7, source_type="api_provider",
                display_name="Synthetic orders", provider_key="synthetic_orders",
                resource_type="orders", client=old,
            )
        self.assertEqual(upgrade.exception.status_code, 503)

        current = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 151}],
            "builder_projects": [project()], "data_sources": [],
        })
        with patch.dict("os.environ", {
            "APP_ENV": "test", "MADAR_TEST_HTTP_PROVIDER_URL": "http://127.0.0.1:8080",
        }, clear=False):
            created = project_data_source_service.create_project_data_source(
                tenant_id=1, project_id=PROJECT_A, user_id=7, source_type="api_provider",
                display_name="Synthetic orders", provider_key="synthetic_orders",
                resource_type="orders", client=current,
            )
        self.assertEqual(created["provider_key"], "synthetic_orders")
        self.assertEqual(created["resource_type"], "orders")

        http_client = FakeClient({
            "application_schema_state": [{"contract_key": "core", "schema_version": 151}],
            "builder_projects": [project()], "data_sources": [],
        })
        with patch.dict("os.environ", {
            "APP_ENV": "test", "MADAR_TEST_HTTP_PROVIDER_URL": "http://127.0.0.1:8080",
        }, clear=False):
            http_source = project_data_source_service.create_project_data_source(
                tenant_id=1, project_id=PROJECT_A, user_id=7, source_type="api_provider",
                display_name="Local business records", provider_key="http_fixture",
                resource_type="records", client=http_client,
            )
        self.assertEqual(http_source["provider_key"], "http_fixture")
        with patch.dict("os.environ", {"APP_ENV": "production"}, clear=False):
            with self.assertRaises(HTTPException):
                project_data_source_service.create_project_data_source(
                    tenant_id=1, project_id=PROJECT_A, user_id=7, source_type="api_provider",
                    display_name="Forbidden local records", provider_key="http_fixture",
                    resource_type="records", client=http_client,
                )

    def test_registers_supported_source_in_authenticated_scope(self):
        client = FakeClient({"builder_projects": [project()], "data_sources": []})
        created = project_data_source_service.create_project_data_source(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            source_type="spreadsheet_upload",
            display_name=" Monthly sales ",
            client=client,
        )
        self.assertEqual(created["id"], SOURCE_A)
        self.assertEqual(created["project_id"], PROJECT_A)
        self.assertEqual(created["display_name"], "Monthly sales")
        self.assertEqual(created["sync_mode"], "manual")
        self.assertNotIn("creator_user_id", created)

    def test_duplicate_and_unsupported_sources_are_rejected(self):
        client = FakeClient({"builder_projects": [project()], "data_sources": [source()]})
        with self.assertRaises(HTTPException) as duplicate:
            project_data_source_service.create_project_data_source(
                tenant_id=1,
                project_id=PROJECT_A,
                user_id=7,
                source_type="spreadsheet_upload",
                display_name="MONTHLY SALES",
                client=client,
            )
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as unsupported:
            project_data_source_service.create_project_data_source(
                tenant_id=1,
                project_id=PROJECT_A,
                user_id=7,
                source_type="api",
                display_name="Unfinished connector",
                client=client,
            )
        self.assertEqual(unsupported.exception.status_code, 422)

    def test_active_source_names_are_unique_across_project_creators(self):
        client = FakeClient({"builder_projects": [project()], "data_sources": [source(creator_user_id=8)]})
        with self.assertRaises(HTTPException) as duplicate:
            project_data_source_service.create_project_data_source(
                tenant_id=1,
                project_id=PROJECT_A,
                user_id=7,
                source_type="spreadsheet_upload",
                display_name="Monthly sales",
                client=client,
            )
        self.assertEqual(duplicate.exception.status_code, 409)

    def test_listing_and_retrieval_are_tenant_project_and_user_scoped(self):
        rows = [
            source(),
            source(id="44444444-4444-4444-8444-444444444444", project_id=PROJECT_B),
            source(id="55555555-5555-4555-8555-555555555555", tenant_id=2),
            source(id="66666666-6666-4666-8666-666666666666", creator_user_id=8),
            source(id="77777777-7777-4777-8777-777777777777", status="archived"),
        ]
        client = FakeClient({"builder_projects": [project()], "data_sources": rows})
        listed = project_data_source_service.list_project_data_sources(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            limit=50,
            offset=0,
            client=client,
        )
        self.assertEqual([item["id"] for item in listed["items"]], [SOURCE_A])
        retrieved = project_data_source_service.get_project_data_source(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            source_id=SOURCE_A,
            client=client,
        )
        self.assertEqual(retrieved["display_name"], "Monthly sales")
        for tenant_id, project_id, user_id in (
            (2, PROJECT_A, 7),
            (1, PROJECT_B, 7),
            (1, PROJECT_A, 8),
        ):
            with self.assertRaises(HTTPException) as denied:
                project_data_source_service.get_project_data_source(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    user_id=user_id,
                    source_id=SOURCE_A,
                    client=client,
                )
            self.assertEqual(denied.exception.status_code, 404)

    def test_archiving_updates_lifecycle_without_deleting_identity(self):
        client = FakeClient({"builder_projects": [project()], "data_sources": [source()]})
        archived = project_data_source_service.update_project_data_source_status(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            source_id=SOURCE_A,
            status="archived",
            client=client,
        )
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["sync_state"], "disabled")
        with self.assertRaises(HTTPException) as invalid:
            project_data_source_service.update_project_data_source_status(
                tenant_id=1,
                project_id=PROJECT_A,
                user_id=7,
                source_id=SOURCE_A,
                status="deleted",
                client=client,
            )
        self.assertEqual(invalid.exception.status_code, 422)


class ProjectDataSourceRouteTests(unittest.TestCase):
    def test_capabilities_use_authenticated_tenant_and_user_scope(self):
        request = SimpleNamespace()
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("3", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit") as rate_limit,
            patch.object(
                project_data_source_service,
                "project_data_source_capabilities",
                return_value={"source_registry_available": False, "providers": []},
            ) as capabilities,
        ):
            result = data_routes.get_project_data_source_capabilities(
                user_id=7, project_id=PROJECT_A,
                request=request, response=SimpleNamespace(),
            )
        self.assertFalse(result["source_registry_available"])
        rate_limit.assert_called_once_with(request, "7", "read", tenant_id="3")
        capabilities.assert_called_once_with(
            tenant_id=3, project_id=PROJECT_A, user_id=7,
        )

    def test_create_uses_only_authenticated_scope(self):
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit"),
            patch.object(project_data_source_service, "require_project_data_sources_schema"),
            patch.object(
                project_data_source_service,
                "create_project_data_source",
                return_value={"id": SOURCE_A},
            ) as create,
        ):
            result = data_routes.create_project_data_source(
                user_id=7,
                project_id=PROJECT_A,
                payload=data_routes.CreateProjectDataSourceRequest(display_name="Monthly sales"),
                request=SimpleNamespace(),
                response=SimpleNamespace(),
            )
        self.assertEqual(result["id"], SOURCE_A)
        create.assert_called_once_with(
            tenant_id=1,
            project_id=PROJECT_A,
            user_id=7,
            source_type="spreadsheet_upload",
            display_name="Monthly sales",
        )

    def test_retrieval_is_read_only_and_status_update_is_rate_limited(self):
        request = SimpleNamespace()
        response = SimpleNamespace()
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit") as rate_limit,
            patch.object(project_data_source_service, "require_project_data_sources_schema"),
            patch.object(
                project_data_source_service,
                "get_project_data_source",
                return_value={"id": SOURCE_A},
            ),
        ):
            data_routes.get_project_data_source(
                user_id=7,
                project_id=PROJECT_A,
                source_id=SOURCE_A,
                request=request,
                response=response,
            )
        rate_limit.assert_not_called()

        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(data_routes, "enforce_data_workspace_rate_limit") as rate_limit,
            patch.object(project_data_source_service, "require_project_data_sources_schema"),
            patch.object(
                project_data_source_service,
                "update_project_data_source_status",
                return_value={"id": SOURCE_A, "status": "archived"},
            ),
        ):
            result = data_routes.update_project_data_source(
                user_id=7,
                project_id=PROJECT_A,
                source_id=SOURCE_A,
                payload=data_routes.UpdateProjectDataSourceRequest(status="archived"),
                request=request,
                response=response,
            )
        self.assertEqual(result["status"], "archived")
        rate_limit.assert_called_once_with(request, "7", "source_write", tenant_id="1")

    def test_list_falls_back_cleanly_before_migration_148(self):
        with (
            patch.object(data_routes, "get_storage_scope", return_value=("1", "7")),
            patch.object(project_data_source_service, "project_data_sources_available", return_value=False),
            patch.object(project_data_source_service, "list_project_data_sources") as listing,
        ):
            result = data_routes.list_project_data_sources(
                user_id=7,
                project_id=PROJECT_A,
                request=SimpleNamespace(),
                response=SimpleNamespace(),
                limit=50,
                offset=0,
            )
        self.assertFalse(result["available"])
        self.assertEqual(result["items"], [])
        listing.assert_not_called()


if __name__ == "__main__":
    unittest.main()
