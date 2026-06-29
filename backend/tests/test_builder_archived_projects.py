import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes, public_site_routes
from services.tenant_service import TenantContext


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = []
        self.neq_filters = []
        self.not_null_columns = set()
        self.insert_payload = None
        self.update_payload = None
        self.order_column = None
        self.order_desc = False
        self.limit_count = None
        self.range_start = None
        self.range_end = None
        self.payload = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def neq(self, column, value):
        self.neq_filters.append((column, value))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        if value == "null":
            self.not_null_columns.add(column)
        return self

    def order(self, column, desc=False):
        self.order_column = column
        self.order_desc = desc
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        self.payload = payload
        return self

    def execute(self):
        rows = list(self.supabase.tables.get(self.table_name, []))

        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]

        for column, value in self.neq_filters:
            rows = [row for row in rows if row.get(column) != value]

        for column in self.not_null_columns:
            rows = [row for row in rows if row.get(column) is not None]

        if self.insert_payload is not None:
            row = {"id": self.supabase.next_id(self.table_name), **self.insert_payload}
            self.supabase.tables.setdefault(self.table_name, []).append(row)
            return FakeResponse([row])

        if self.update_payload is not None:
            updated_rows = []
            for row in self.supabase.tables.get(self.table_name, []):
                if all(row.get(column) == value for column, value in self.filters):
                    row.update(self.update_payload)
                    updated_rows.append(row)
            return FakeResponse(updated_rows)

        if self.order_column:
            rows = sorted(
                rows,
                key=lambda row: row.get(self.order_column) or "",
                reverse=self.order_desc,
            )

        if self.range_start is not None and self.range_end is not None:
            rows = rows[self.range_start : self.range_end + 1]

        if self.limit_count is not None:
            rows = rows[: self.limit_count]

        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "website_settings": [
                {"id": 1, "tenant_id": 1, "user_id": 2, "subdomain": "tenant-site"}
            ],
            "builder_projects": [
                {
                    "id": "project-1",
                    "tenant_id": 1,
                    "name": "Published site",
                    "slug": "published-site",
                    "status": "published",
                    "published_schema": {"pages": [], "forms": []},
                    "published_version": 4,
                    "last_published_at": "2026-06-03T13:00:00+00:00",
                    "updated_at": "2026-06-03T13:00:00+00:00",
                }
            ],
            "builder_form_submissions": [],
        }
        self.id_counters = {}

    def next_id(self, table_name):
        self.id_counters[table_name] = self.id_counters.get(table_name, 0) + 1
        return f"{table_name}-{self.id_counters[table_name]}"

    def table(self, table_name):
        return FakeQuery(self, table_name)


def fake_context(tenant_id=1, role="owner"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=2,
        auth_id="auth-1",
        role=role,
        membership_status="active",
        user={},
        membership={"role": role},
    )


def build_builder_client(fake_supabase):
    app = FastAPI()
    app.include_router(builder_routes.router)
    app.state.fake_supabase = fake_supabase
    return TestClient(app)


def build_public_client(fake_supabase):
    app = FastAPI()
    app.include_router(public_site_routes.router)
    app.state.fake_supabase = fake_supabase
    return TestClient(app)


class ArchivedBuilderProjectTests(unittest.TestCase):
    def test_builder_project_list_excludes_archived_projects(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"].extend(
            [
                {
                    "id": "archived-project",
                    "tenant_id": 1,
                    "name": "Archived project",
                    "slug": "archived-project",
                    "status": "archived",
                    "updated_at": "2026-06-03T17:00:00+00:00",
                },
                {
                    "id": "active-project",
                    "tenant_id": 1,
                    "name": "Active project",
                    "slug": "active-project",
                    "status": "draft",
                    "updated_at": "2026-06-03T18:00:00+00:00",
                },
            ]
        )
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_context", return_value=fake_context()):
            response = client.get("/builder/projects")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        returned_ids = {project["id"] for project in body["projects"]}
        self.assertIn("active-project", returned_ids)
        self.assertNotIn("archived-project", returned_ids)

    def test_archived_project_is_not_returned_by_get_route(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "project-1",
                "tenant_id": 1,
                "name": "Archived Landing Page",
                "slug": "archived-landing-page",
                "status": "archived",
                "draft_schema": {"pages": []},
                "published_schema": {"pages": []},
                "published_version": 7,
                "last_published_at": "2026-06-03T13:00:00+00:00",
            }
        ]
        request = type("Request", (), {"path_params": {"user_id": "2"}})()
        response = object()

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_context", return_value=fake_context()):
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.get_builder_project("project-1", request, response)

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")

    def test_archived_project_compatibility_get_route_is_not_returned(self):
        fake_supabase = FakeSupabase()
        archived_project = {
            "id": "project-1",
            "tenant_id": 1,
            "name": "Archived Landing Page",
            "slug": "archived-landing-page",
            "status": "archived",
            "draft_schema": {"pages": []},
            "published_schema": {"pages": []},
            "published_version": 7,
            "last_published_at": "2026-06-03T13:00:00+00:00",
        }

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_context", return_value=fake_context()):
            fake_supabase.tables["builder_projects"] = [archived_project]
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.get_builder_project("project-1", object(), object())

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")

    def test_archived_project_cross_tenant_is_not_distinguishable(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "project-1",
                "tenant_id": 1,
                "name": "Archived Landing Page",
                "slug": "archived-landing-page",
                "status": "archived",
                "draft_schema": {"pages": []},
                "published_schema": {"pages": []},
                "published_version": 7,
                "last_published_at": "2026-06-03T13:00:00+00:00",
            }
        ]
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.get("/builder/projects/project-1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_archived_project_update_is_rejected(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "project-1",
                "tenant_id": 1,
                "name": "Archived Landing Page",
                "slug": "archived-landing-page",
                "status": "archived",
                "draft_schema": {"pages": []},
                "published_schema": {"pages": []},
                "published_version": 7,
                "last_published_at": "2026-06-03T13:00:00+00:00",
            }
        ]
        request = type("Request", (), {"path_params": {"user_id": "2"}})()
        response = object()
        archived_project = {"id": "project-1", "tenant_id": 1, "status": "archived", "draft_schema": {"pages": []}}

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()):
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.update_builder_project(
                    "project-1",
                    type("Update", (), {"name": "New name", "slug": "new-slug", "status": "draft", "draft_schema": None})(),
                    request,
                    response,
                )

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")
        self.assertIsNone(fake_supabase.table("builder_projects").payload)

    def test_archived_project_compatibility_update_is_rejected(self):
        fake_supabase = FakeSupabase()
        archived_project = {
            "id": "project-1",
            "tenant_id": 1,
            "name": "Archived Landing Page",
            "slug": "archived-landing-page",
            "status": "archived",
            "draft_schema": {"pages": []},
            "published_schema": {"pages": []},
            "published_version": 7,
            "last_published_at": "2026-06-03T13:00:00+00:00",
        }
        fake_supabase.tables["builder_projects"] = [archived_project]
        request = type("Request", (), {"path_params": {"user_id": "2"}})()
        response = object()

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()):
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.update_builder_project(
                    "project-1",
                    type("Update", (), {"name": "New name", "slug": "new-slug", "status": "draft", "draft_schema": None})(),
                    request,
                    response,
                )

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")
        self.assertIsNone(fake_supabase.table("builder_projects").payload)

    def test_archived_project_publish_is_rejected(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "project-1",
                "tenant_id": 1,
                "name": "Archived Landing Page",
                "slug": "archived-landing-page",
                "status": "archived",
                "draft_schema": {"pages": []},
                "published_schema": {"pages": []},
                "published_version": 7,
                "last_published_at": "2026-06-03T13:00:00+00:00",
            }
        ]
        request = type("Request", (), {"path_params": {"user_id": "2"}})()
        response = object()

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(builder_routes, "require_public_subdomain") as require_public_subdomain,              patch.object(builder_routes, "record_audit_event") as record_audit:
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.publish_builder_project("project-1", request, response)

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")
        self.assertIsNone(fake_supabase.table("builder_projects").payload)
        require_public_subdomain.assert_not_called()
        record_audit.assert_not_called()

    def test_archived_project_compatibility_publish_is_rejected(self):
        fake_supabase = FakeSupabase()
        archived_project = {
            "id": "project-1",
            "tenant_id": 1,
            "name": "Archived Landing Page",
            "slug": "archived-landing-page",
            "status": "archived",
            "draft_schema": {"pages": []},
            "published_schema": {"pages": []},
            "published_version": 7,
            "last_published_at": "2026-06-03T13:00:00+00:00",
        }
        fake_supabase.tables["builder_projects"] = [archived_project]
        request = type("Request", (), {"path_params": {"user_id": "2"}})()
        response = object()

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(builder_routes, "require_public_subdomain") as require_public_subdomain,              patch.object(builder_routes, "record_audit_event") as record_audit:
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.publish_builder_project("project-1", request, response)

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")
        self.assertIsNone(fake_supabase.table("builder_projects").payload)
        require_public_subdomain.assert_not_called()
        record_audit.assert_not_called()

    def test_archived_project_archive_is_rejected_when_already_archived(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "project-1",
                "tenant_id": 1,
                "name": "Archived Landing Page",
                "slug": "archived-landing-page",
                "status": "archived",
                "draft_schema": {"pages": []},
                "published_schema": {"pages": []},
                "published_version": 7,
                "last_published_at": "2026-06-03T13:00:00+00:00",
            }
        ]
        request = type("Request", (), {"path_params": {"user_id": "2"}})()
        response = object()

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_admin_access", return_value=fake_context(role="owner")),              patch.object(builder_routes, "record_audit_event") as record_audit:
            with self.assertRaises(HTTPException) as exc_info:
                builder_routes.archive_builder_project("project-1", request, response)

        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertEqual(exc_info.exception.detail, "Builder project not found")
        self.assertIsNone(fake_supabase.table("builder_projects").payload)
        record_audit.assert_not_called()

    def test_public_site_does_not_serve_archived_published_projects(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"][0]["status"] = "archived"
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase),              patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Published site not found")


if __name__ == "__main__":
    unittest.main()

class PublicSiteContractTests(unittest.TestCase):
    def test_public_site_returns_latest_published_project_and_hides_draft_schema(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "project-old",
                "tenant_id": 1,
                "name": "Older Published Site",
                "slug": "older-published-site",
                "status": "published",
                "draft_schema": {"pages": [{"id": "draft-old"}]},
                "published_schema": {"pages": [{"id": "published-old"}]},
                "published_version": 1,
                "last_published_at": "2026-06-01T10:00:00+00:00",
                "updated_at": "2026-06-01T10:00:00+00:00",
            },
            {
                "id": "project-new",
                "tenant_id": 1,
                "name": "Newest Published Site",
                "slug": "newest-published-site",
                "status": "published",
                "draft_schema": {"pages": [{"id": "draft-new"}]},
                "published_schema": {"pages": [{"id": "published-new"}]},
                "published_version": 2,
                "last_published_at": "2026-06-02T10:00:00+00:00",
                "updated_at": "2026-06-02T10:00:00+00:00",
            },
        ]
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project"]["id"], "project-new")
        self.assertEqual(body["project"]["published_version"], 2)
        self.assertEqual(body["project"]["published_schema"], {"pages": [{"id": "published-new"}]})
        self.assertNotIn("draft_schema", body["project"])

    def test_public_site_without_published_project_returns_not_found(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"] = [
            {
                "id": "draft-project",
                "tenant_id": 1,
                "name": "Draft Site",
                "slug": "draft-site",
                "status": "draft",
                "draft_schema": {"pages": []},
                "updated_at": "2026-06-02T10:00:00+00:00",
            }
        ]
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Published site not found")
