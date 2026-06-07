import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes
from services.tenant_service import TenantContext, require_builder_admin_access


class FakeQuery:
    def __init__(self):
        self.payload = None

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        return type("Response", (), {"data": [{"id": "project-1", **(self.payload or {})}]})()


class FakeSupabase:
    def __init__(self):
        self.query = FakeQuery()

    def table(self, _name):
        return self.query


def build_client(fake_supabase):
    app = FastAPI()
    app.include_router(builder_routes.router)
    app.state.fake_supabase = fake_supabase
    return TestClient(app)


def fake_context(role="owner"):
    return TenantContext(
        tenant_id=1,
        user_id=2,
        auth_id="auth-1",
        role=role,
        membership_status="active",
        user={},
        membership={"role": role},
    )


class BuilderBackendHardeningTests(unittest.TestCase):
    def test_publish_accepts_no_body(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "draft_schema": {"pages": []},
                     "published_version": 0,
                 },
             ), \
             patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ):
            response = client.post("/users/2/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"]["published_schema"], {"pages": []})
        self.assertEqual(fake_supabase.query.payload["published_version"], 1)

    def test_publish_accepts_empty_body(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "draft_schema": {"version": 1},
                     "published_version": 2,
                 },
             ), \
             patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ):
            response = client.post("/users/2/builder/projects/project-1/publish", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project"]["published_schema"], {"version": 1})
        self.assertEqual(fake_supabase.query.payload["published_version"], 3)


    def test_publish_requires_configured_site_subdomain(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "draft_schema": {"pages": []},
                     "published_version": 0,
                 },
             ),              patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 side_effect=HTTPException(
                     status_code=400,
                     detail="Configure a website subdomain before going live.",
                 ),
             ):
            response = client.post("/users/2/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Configure a website subdomain before going live.",
        )

    def test_update_rejects_oversized_draft_schema(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "MAX_BUILDER_SCHEMA_BYTES", 100), \
             patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "draft_schema": {"pages": []},
                 },
             ):
            response = client.put(
                "/users/2/builder/projects/project-1",
                json={"draft_schema": {"pages": [{"content": "x" * 200}]}},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "draft_schema is too large")

    def test_member_cannot_archive_project(self):
        with patch(
            "services.tenant_service.get_current_tenant_context",
            return_value=fake_context(role="member"),
        ):
            with self.assertRaises(HTTPException) as error:
                require_builder_admin_access(request=None, response=None)

        self.assertEqual(error.exception.status_code, 403)


    def test_archive_route_denies_member_access(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(
            builder_routes,
            "require_builder_admin_access",
            side_effect=HTTPException(status_code=403, detail="Builder admin access required"),
        ):
            response = client.delete("/users/2/builder/projects/project-1")

        self.assertEqual(response.status_code, 403)

    def test_database_requires_service_key(self):
        database_path = Path(__file__).resolve().parents[1] / "database.py"

        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_ANON_KEY": "anon-key",
            },
            clear=True,
        ), patch("dotenv.load_dotenv", return_value=False):
            spec = importlib.util.spec_from_file_location(
                "database_missing_service_key_test",
                database_path,
            )
            module = importlib.util.module_from_spec(spec)

            with self.assertRaisesRegex(RuntimeError, "SUPABASE_SERVICE_KEY"):
                spec.loader.exec_module(module)


if __name__ == "__main__":
    unittest.main()
