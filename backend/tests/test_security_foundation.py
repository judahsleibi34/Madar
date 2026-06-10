import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services import rate_limit_service
from services.rate_limit_service import InMemoryRateLimitStore, enforce_rate_limit
from services.request_security import get_allowed_origins, validate_cookie_write_origin


class SecurityFoundationTests(unittest.TestCase):
    def setUp(self):
        rate_limit_service._store = None
        rate_limit_service._memory_store = InMemoryRateLimitStore()

    def tearDown(self):
        rate_limit_service._store = None
        rate_limit_service._memory_store = InMemoryRateLimitStore()

    def build_origin_client(self):
        app = FastAPI()
        allowed_origins = get_allowed_origins(["https://app.example.com"])

        @app.middleware("http")
        async def csrf_middleware(request: Request, call_next):
            blocked_response = validate_cookie_write_origin(request, allowed_origins)
            if blocked_response is not None:
                return blocked_response
            return await call_next(request)

        @app.post("/protected-write")
        def protected_write():
            return {"ok": True}

        return TestClient(app)

    def test_invalid_origin_rejected_for_cookie_authenticated_write(self):
        client = self.build_origin_client()

        response = client.post(
            "/protected-write",
            headers={"Origin": "https://evil.example.com"},
            cookies={"madar_access_token": "token"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid request origin")

    def test_valid_origin_accepted_for_cookie_authenticated_write(self):
        client = self.build_origin_client()

        response = client.post(
            "/protected-write",
            headers={"Origin": "https://app.example.com"},
            cookies={"madar_access_token": "token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_rate_limit_rejects_after_limit(self):
        app = FastAPI()
        store = InMemoryRateLimitStore()

        @app.post("/limited")
        def limited(request: Request):
            enforce_rate_limit(
                request,
                "test",
                identifier="user@example.com",
                limit=2,
                window_seconds=60,
            )
            return {"ok": True}

        client = TestClient(app)

        with patch.object(rate_limit_service, "_store", store),              patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True):
            self.assertEqual(client.post("/limited").status_code, 200)
            self.assertEqual(client.post("/limited").status_code, 200)
            response = client.post("/limited")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many requests. Please try again later.")

    def get_migrations_dir(self):
        candidates = [
            Path(__file__).resolve().parents[2] / "database" / "migrations",
            Path(__file__).resolve().parents[1] / "database" / "migrations",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        self.skipTest("database migrations are not available in this test environment")

    def test_builder_rls_migrations_are_tenant_scoped(self):
        migrations_dir = self.get_migrations_dir()
        builder_projects_sql = (migrations_dir / "023_create_builder_projects.sql").read_text().lower()
        submissions_sql = (migrations_dir / "025_create_builder_form_submissions.sql").read_text().lower()

        self.assertIn("alter table public.builder_projects enable row level security", builder_projects_sql)
        self.assertIn("alter table public.builder_form_submissions enable row level security", submissions_sql)
        self.assertIn("tenant_memberships", builder_projects_sql)
        self.assertIn("tenant_memberships", submissions_sql)
        self.assertIn("auth.uid()", builder_projects_sql)
        self.assertIn("auth.uid()", submissions_sql)
        self.assertIn("role in ('owner', 'admin')", builder_projects_sql)
        self.assertNotIn("for insert", submissions_sql.split("create policy", 1)[-1])
        self.assertNotIn("for update", submissions_sql.split("create policy", 1)[-1])

    def test_website_settings_rls_keeps_documented_user_id_compatibility(self):
        migrations_dir = self.get_migrations_dir()
        website_settings_sql = (migrations_dir / "024_harden_website_settings_rls.sql").read_text().lower()

        self.assertIn("alter table public.website_settings enable row level security", website_settings_sql)
        self.assertIn("tenant_memberships", website_settings_sql)
        self.assertIn("auth.uid()", website_settings_sql)
        self.assertIn("where u.id = website_settings.user_id", website_settings_sql)


    def test_features_rls_migration_is_tenant_scoped_and_read_only(self):
        migrations_dir = self.get_migrations_dir()
        features_sql = (migrations_dir / "027_harden_features_rls.sql").read_text().lower()

        self.assertIn("alter table public.features enable row level security", features_sql)
        self.assertIn("revoke all on table public.features from anon", features_sql)
        self.assertIn("revoke all on table public.features from authenticated", features_sql)
        self.assertIn("grant select on table public.features to authenticated", features_sql)
        self.assertIn("grant all privileges on table public.features to service_role", features_sql)
        self.assertIn("create policy features_select_tenant_member", features_sql)
        self.assertIn("for select", features_sql)
        self.assertIn("to authenticated", features_sql)
        self.assertIn("tenant_memberships", features_sql)
        self.assertIn("tm.tenant_id = features.tenant_id", features_sql)
        self.assertIn("tm.auth_id = auth.uid()", features_sql)
        self.assertIn("tm.status = 'active'", features_sql)
        self.assertIn("revoke select on table public.tenants from anon", features_sql)
        self.assertNotIn("for insert", features_sql)
        self.assertNotIn("for update", features_sql)
        self.assertNotIn("for delete", features_sql)
        self.assertNotIn("grant insert", features_sql)
        self.assertNotIn("grant update", features_sql)
        self.assertNotIn("grant delete", features_sql)



if __name__ == "__main__":
    unittest.main()
