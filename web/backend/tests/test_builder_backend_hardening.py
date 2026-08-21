import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import database
from routes import builder_routes
from services.tenant_service import TenantContext, require_builder_admin_access


class FakeQuery:
    def __init__(self):
        self.payload = None
        self.base_row = None

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        row = {"id": "project-1"}
        if self.base_row:
            row.update(self.base_row)
        if self.payload:
            row.update(self.payload)
        return type("Response", (), {"data": [row]})()


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


def builder_schema_with_element(element):
    return {
        "siteChrome": {
            "logoUrl": "https://cdn.example.com/logo.png",
            "madarLink": "/",
        },
        "pages": [
            {
                "id": "page-1",
                "sections": [
                    {
                        "id": "section-1",
                        "rows": [
                            {
                                "id": "row-1",
                                "columns": [
                                    {
                                        "id": "column-1",
                                        "elements": [element],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


class BuilderBackendHardeningTests(unittest.TestCase):
    def test_publish_validation_preserves_nested_page_routes(self):
        schema, _ = builder_routes.validate_publish_schema({
            "defaultPageId": "home",
            "pages": [
                {"id": "home", "name": "Home", "slug": "/", "sections": []},
                {
                    "id": "team",
                    "name": "Team",
                    "slug": "/about/team",
                    "sections": [],
                },
            ],
            "forms": [],
        })

        self.assertEqual(schema["pages"][1]["slug"], "/about/team")

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
             ), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.post("/builder/projects/project-1/publish")

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
             ), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.post("/builder/projects/project-1/publish", json={})

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
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Configure a website subdomain before going live.",
        )
        self.assertIsNone(fake_supabase.query.payload)

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
                "/builder/projects/project-1",
                json={"draft_schema": {"pages": [{"content": "x" * 200}]}},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "draft_schema is too large")

    def test_update_rejects_unsafe_image_url(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {"pages": []}},
             ):
            response = client.put(
                "/builder/projects/project-1",
                json={
                    "draft_schema": builder_schema_with_element(
                        {"id": "element-1", "type": "image", "content": "javascript:alert(1)"}
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("draft_schema", response.json()["detail"])

    def test_update_rejects_unsafe_embed_url(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {"pages": []}},
             ):
            response = client.put(
                "/builder/projects/project-1",
                json={
                    "draft_schema": builder_schema_with_element(
                        {"id": "element-1", "type": "embed", "content": "data:text/html,<script>alert(1)</script>"}
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("draft_schema", response.json()["detail"])

    def test_update_rejects_unsafe_action_url(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {"pages": []}},
             ):
            response = client.put(
                "/builder/projects/project-1",
                json={
                    "draft_schema": builder_schema_with_element(
                        {
                            "id": "element-1",
                            "type": "button",
                            "content": "Open",
                            "action": {"type": "openUrl", "url": "javascript:alert(1)"},
                        }
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("action.url", response.json()["detail"])

    def test_update_rejects_unsafe_carousel_image_url(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)
        carousel_content = "Title\nDescription\njavascript:alert(1)"

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {"pages": []}},
             ):
            response = client.put(
                "/builder/projects/project-1",
                json={
                    "draft_schema": builder_schema_with_element(
                        {"id": "element-1", "type": "carousel", "content": carousel_content}
                    )
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("slide[0].image", response.json()["detail"])

    def test_update_allows_safe_https_and_relative_navigation_urls(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)
        schema = builder_schema_with_element(
            {
                "id": "element-1",
                "type": "button",
                "content": "Contact",
                "action": {"type": "openUrl", "url": "/contact"},
            }
        )
        schema["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"].append(
            {
                "id": "element-2",
                "type": "image",
                "content": "https://images.example.com/photo.jpg",
            }
        )

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {"pages": []}},
             ):
            response = client.put(
                "/builder/projects/project-1",
                json={"draft_schema": schema},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_supabase.query.payload["draft_schema"], schema)

    def test_publish_revalidates_saved_draft_schema(self):
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
                     "draft_schema": builder_schema_with_element(
                         {"id": "element-1", "type": "image", "content": "data:image/png;base64,AAAA"}
                     ),
                     "published_version": 0,
                 },
             ), \
             patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ):
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 400)
        self.assertIn("draft_schema", response.json()["detail"])

    def test_successful_publish_records_audit_event(self):
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
                     "name": "Landing Page",
                     "slug": "landing-page",
                     "draft_schema": {"pages": []},
                     "published_version": 0,
                 },
             ), \
             patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 200)
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 1)
        self.assertEqual(audit_kwargs["actor_user_id"], 2)
        self.assertEqual(audit_kwargs["action"], "builder.project_published")
        self.assertEqual(audit_kwargs["target_type"], "builder_project")
        self.assertEqual(audit_kwargs["target_id"], "project-1")
        self.assertEqual(audit_kwargs["metadata"]["project_slug"], "landing-page")
        self.assertEqual(audit_kwargs["metadata"]["project_name"], "Landing Page")
        self.assertEqual(audit_kwargs["metadata"]["published_version"], 1)

    def test_successful_publish_returns_updated_project_and_site_contract(self):
        fake_supabase = FakeSupabase()
        fake_supabase.query.base_row = {
            "tenant_id": 1,
            "owner_user_id": 77,
            "name": "Landing Page",
            "slug": "landing-page",
            "draft_schema": {"pages": [{"id": "page-1"}]},
            "status": "draft",
            "published_version": 3,
            "last_published_at": None,
        }
        client = build_client(fake_supabase)
        draft_schema = {"pages": [{"id": "page-1"}]}

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "name": "Landing Page",
                     "slug": "landing-page",
                     "draft_schema": draft_schema,
                     "published_version": 3,
                     "status": "draft",
                 },
             ),              patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ),              patch.object(builder_routes, "record_audit_event"):
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["site"],
            {
                "subdomain": "tenant-site",
                "standard_path_slug": "tenant-site",
                "tenant_id": 1,
                "published_project_id": "project-1",
            },
        )
        self.assertEqual(
            body["project"]["published_schema"],
            {
                "defaultPageId": "page-1",
                "pages": [{
                    "id": "page-1",
                    "slug": "/",
                    "isDefault": True,
                    "showInNavigation": True,
                    "order": 0,
                }],
            },
        )
        self.assertEqual(draft_schema, {"pages": [{"id": "page-1"}]})
        self.assertEqual(body["project"]["published_version"], 4)
        self.assertEqual(body["project"]["status"], "published")
        self.assertTrue(body["project"]["last_published_at"])
        self.assertEqual(body["project"]["owner_user_id"], 77)

    def test_publish_rejects_non_object_draft_schema(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "draft_schema": ["not", "an", "object"],
                     "published_version": 0,
                 },
             ),              patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ):
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "draft_schema must be a JSON object")
        self.assertIsNone(fake_supabase.query.payload)

    def test_repeated_publish_increments_version_and_draft_remains_editable(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)
        project_v0 = {
            "id": "project-1",
            "tenant_id": 1,
            "name": "Landing Page",
            "slug": "landing-page",
            "draft_schema": {"pages": [{"id": "page-1"}]},
            "published_version": 0,
            "status": "draft",
        }
        project_v1 = {
            **project_v0,
            "status": "published",
            "published_schema": {"pages": [{"id": "page-1"}]},
            "published_version": 1,
            "last_published_at": "2026-06-03T13:00:00+00:00",
        }

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 side_effect=[project_v0, project_v1, project_v1],
             ),              patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ),              patch.object(builder_routes, "record_audit_event"):
            first_response = client.post("/builder/projects/project-1/publish")
            first_payload = dict(fake_supabase.query.payload)
            second_response = client.post("/builder/projects/project-1/publish")
            second_payload = dict(fake_supabase.query.payload)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.json()["project"]["published_version"], 1)
        self.assertEqual(second_response.json()["project"]["published_version"], 2)
        self.assertEqual(first_payload["published_version"], 1)
        self.assertEqual(second_payload["published_version"], 2)

        with patch.object(builder_routes, "service_supabase", fake_supabase),              patch.object(builder_routes, "require_builder_write_access", return_value=fake_context()),              patch.object(builder_routes, "get_project_for_tenant", return_value=project_v1):
            update_response = client.put(
                "/builder/projects/project-1",
                json={"draft_schema": {"pages": [{"id": "page-2"}]}} ,
            )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(fake_supabase.query.payload["draft_schema"], {"pages": [{"id": "page-2"}]})

    def test_failed_publish_does_not_record_success_audit_event(self):
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
                     "draft_schema": builder_schema_with_element(
                         {"id": "element-1", "type": "image", "content": "javascript:alert(1)"}
                     ),
                     "published_version": 0,
                 },
             ), \
             patch.object(
                 builder_routes,
                 "require_public_subdomain",
                 return_value={"subdomain": "tenant-site", "tenant_id": 1},
             ), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 400)
        record_audit.assert_not_called()

    def test_successful_archive_records_audit_event(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_admin_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 return_value={
                     "id": "project-1",
                     "tenant_id": 1,
                     "name": "Landing Page",
                     "slug": "landing-page",
                     "status": "published",
                 },
             ), \
             patch.object(builder_routes, "get_website_settings_record", return_value=None), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.delete("/builder/projects/project-1")

        self.assertEqual(response.status_code, 200)
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 1)
        self.assertEqual(audit_kwargs["actor_user_id"], 2)
        self.assertEqual(audit_kwargs["action"], "builder.project_archived")
        self.assertEqual(audit_kwargs["target_type"], "builder_project")
        self.assertEqual(audit_kwargs["target_id"], "project-1")
        self.assertEqual(audit_kwargs["metadata"]["project_slug"], "landing-page")
        self.assertEqual(audit_kwargs["metadata"]["project_name"], "Landing Page")
        self.assertEqual(audit_kwargs["metadata"]["status"], "archived")

    def test_failed_archive_does_not_record_success_audit_event(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_admin_access", return_value=fake_context()), \
             patch.object(
                 builder_routes,
                 "get_project_for_tenant",
                 side_effect=HTTPException(status_code=404, detail="Builder project not found"),
             ), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.delete("/builder/projects/project-1")

        self.assertEqual(response.status_code, 404)
        record_audit.assert_not_called()

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
            response = client.delete("/builder/projects/project-1")

        self.assertEqual(response.status_code, 403)


    def test_builder_compatibility_route_accepts_matching_user_id(self):
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
             ), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.post("/users/2/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 200)

    def test_builder_compatibility_route_rejects_wrong_user_id(self):
        fake_supabase = FakeSupabase()
        client = build_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get("/users/3/builder/projects")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User id does not match session")

    def test_local_environment_file_overrides_stale_shell_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "SUPABASE_URL=https://fresh-project.supabase.co\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "APP_ENV": "development",
                    "SUPABASE_URL": "https://stale-project.supabase.co",
                },
                clear=True,
            ), patch.object(database, "DEFAULT_ENV_PATH", env_path):
                loaded_path = database.load_backend_environment()

                self.assertEqual(loaded_path, env_path.resolve())
                self.assertEqual(
                    os.environ["SUPABASE_URL"],
                    "https://fresh-project.supabase.co",
                )

    def test_production_environment_keeps_deployment_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "SUPABASE_URL=https://local-file.supabase.co\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "APP_ENV": "production",
                    "SUPABASE_URL": "https://deployment.supabase.co",
                },
                clear=True,
            ), patch.object(database, "DEFAULT_ENV_PATH", env_path):
                database.load_backend_environment()

                self.assertEqual(
                    os.environ["SUPABASE_URL"],
                    "https://deployment.supabase.co",
                )


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

class ReservationFormPublishValidationTests(unittest.TestCase):
    def test_accepts_supported_reservation_form_items(self):
        reservation = {
            "formItems": [
                {"id": "intro", "type": "heading", "text": "Tell us more"},
                {"id": "topics", "type": "checkbox", "label": "Topics", "options": ["Design", "Build"], "required": True},
                {"id": "email", "type": "email", "label": "Email", "required": True},
                {"id": "phone", "type": "phone", "label": "Phone", "required": True},
                {"id": "submit", "type": "button", "label": "Book now"},
            ]
        }

        builder_routes.validate_reservation_form_items(reservation)

    def test_validates_reservation_typography_and_direction(self):
        builder_routes.validate_reservation_form_items({
            "formItems": [{
                "id": "intro",
                "type": "heading",
                "text": "احجز موعدك",
                "direction": "rtl",
                "textStyle": {
                    "format": "h2",
                    "fontFamily": "IBM Plex Sans Arabic",
                    "fontSize": 28,
                    "opacity": 0.8,
                    "fontWeight": "700",
                    "fontStyle": "normal",
                    "textDecoration": "none",
                    "textAlign": "right",
                    "color": "#123456",
                },
            }],
        })

        invalid_items = [
            {"id": "direction", "type": "text", "label": "Name", "direction": "sideways"},
            {"id": "size", "type": "heading", "text": "Huge", "textStyle": {"fontSize": 999}},
            {"id": "color", "type": "paragraph", "text": "Unsafe", "textStyle": {"color": "url(javascript:alert(1))"}},
        ]
        for item in invalid_items:
            with self.subTest(item=item), self.assertRaises(HTTPException):
                builder_routes.validate_reservation_form_items({"formItems": [item]})
    def test_rejects_unsupported_and_duplicate_reservation_controls(self):
        invalid_forms = [
            {"formItems": [{"id": "unsafe", "type": "html", "text": "Unsafe"}]},
            {"formItems": [
                {"id": "one", "type": "button", "label": "One"},
                {"id": "two", "type": "button", "label": "Two"},
            ]},
            {"formItems": [{"id": "choice", "type": "radio", "label": "Choice", "options": ["Same", "Same"]}]},
        ]

        for reservation in invalid_forms:
            with self.subTest(reservation=reservation), self.assertRaises(HTTPException) as raised:
                builder_routes.validate_reservation_form_items(reservation)
            self.assertEqual(raised.exception.detail["code"], "publish_validation_failed")