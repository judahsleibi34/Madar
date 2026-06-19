import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from services import rate_limit_service
from services.rate_limit_service import InMemoryRateLimitStore, enforce_rate_limit
from services.auth_service import delete_auth_cookies, set_auth_cookies
from services.request_security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    create_csrf_token,
    get_allowed_origins,
    validate_cookie_write_origin,
    validate_csrf_token,
)


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
            blocked_response = validate_csrf_token(request)
            if blocked_response is not None:
                return blocked_response
            return await call_next(request)

        @app.post("/protected-write")
        def protected_write():
            return {"ok": True}

        @app.get("/safe-read")
        def safe_read():
            return {"ok": True}

        @app.post("/public/contact")
        def public_contact():
            return {"ok": True}

        @app.post("/billing/webhook")
        def billing_webhook():
            return {"ok": True}

        @app.post("/public/sites/example/forms/form-1/submissions")
        def public_form_submission():
            return {"ok": True}

        @app.post("/issue-cookies")
        def issue_cookies(response: Response):
            csrf_token = set_auth_cookies(response, "access-token", "refresh-token")
            return {"csrf_token": csrf_token}

        @app.post("/clear-cookies")
        def clear_cookies(response: Response):
            delete_auth_cookies(response)
            return {"ok": True}

        return TestClient(app)

    def build_csrf_request_parts(self):
        csrf_token = create_csrf_token(
            access_token="access-token",
            refresh_token="refresh-token",
        )
        return {
            "headers": {
                "Origin": "https://app.example.com",
                CSRF_HEADER_NAME: csrf_token,
            },
            "cookies": {
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
                CSRF_COOKIE_NAME: csrf_token,
            },
        }

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
        request_parts = self.build_csrf_request_parts()

        response = client.post(
            "/protected-write",
            headers=request_parts["headers"],
            cookies=request_parts["cookies"],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_missing_csrf_rejected_for_cookie_authenticated_write(self):
        client = self.build_origin_client()

        response = client.post(
            "/protected-write",
            headers={"Origin": "https://app.example.com"},
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid CSRF token")

    def test_bad_csrf_rejected_for_cookie_authenticated_write(self):
        client = self.build_origin_client()
        request_parts = self.build_csrf_request_parts()
        request_parts["headers"][CSRF_HEADER_NAME] = "bad-token"

        response = client.post(
            "/protected-write",
            headers=request_parts["headers"],
            cookies=request_parts["cookies"],
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid CSRF token")

    def test_invalid_origin_rejected_before_csrf(self):
        client = self.build_origin_client()
        request_parts = self.build_csrf_request_parts()
        request_parts["headers"]["Origin"] = "https://evil.example.com"

        response = client.post(
            "/protected-write",
            headers=request_parts["headers"],
            cookies=request_parts["cookies"],
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid request origin")

    def test_safe_get_routes_do_not_require_csrf(self):
        client = self.build_origin_client()

        response = client.get(
            "/safe-read",
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_public_routes_remain_csrf_exempt(self):
        client = self.build_origin_client()

        for path in [
            "/public/contact",
            "/billing/webhook",
            "/public/sites/example/forms/form-1/submissions",
        ]:
            with self.subTest(path=path):
                response = client.post(
                    path,
                    headers={"Origin": "https://app.example.com"},
                    cookies={
                        "madar_access_token": "access-token",
                        "madar_refresh_token": "refresh-token",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"ok": True})

    def test_auth_cookies_issue_csrf_token(self):
        client = self.build_origin_client()

        response = client.post("/issue-cookies")

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrf_token", response.json())
        self.assertIn(CSRF_HEADER_NAME, response.headers)
        self.assertIn(CSRF_COOKIE_NAME, response.cookies)

        set_cookie_headers = response.headers.get_list("set-cookie")
        session_cookie_headers = [
            header
            for header in set_cookie_headers
            if header.startswith("madar_access_token=")
            or header.startswith("madar_refresh_token=")
            or header.startswith(f"{CSRF_COOKIE_NAME}=")
        ]
        self.assertEqual(len(session_cookie_headers), 3)
        for header in session_cookie_headers:
            self.assertNotIn("Max-Age=", header)
            self.assertNotIn("Expires=", header)

    def test_logout_cookie_helper_clears_csrf_cookie(self):
        client = self.build_origin_client()

        response = client.post("/clear-cookies")
        set_cookie_headers = response.headers.get_list("set-cookie")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(header.startswith(f"{CSRF_COOKIE_NAME}=") for header in set_cookie_headers)
        )

    def build_rate_limit_request(self, host="198.51.100.10", headers=None):
        return SimpleNamespace(
            headers=headers or {},
            client=SimpleNamespace(host=host),
        )

    def test_client_ip_without_forwarded_header_uses_request_client_host(self):
        request = self.build_rate_limit_request(host="198.51.100.10")

        self.assertEqual(rate_limit_service.get_client_ip(request), "198.51.100.10")

    def test_untrusted_client_spoofed_forwarded_header_is_ignored(self):
        request = self.build_rate_limit_request(
            host="198.51.100.10",
            headers={
                "x-forwarded-for": "203.0.113.77",
                "x-real-ip": "203.0.113.88",
            },
        )

        with patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "127.0.0.1,::1"):
            self.assertEqual(rate_limit_service.get_client_ip(request), "198.51.100.10")

    def test_trusted_proxy_uses_original_forwarded_client_ip(self):
        request = self.build_rate_limit_request(
            host="10.0.0.2",
            headers={"x-forwarded-for": "198.51.100.25, 10.0.0.1"},
        )

        with patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "10.0.0.1,10.0.0.2"):
            self.assertEqual(rate_limit_service.get_client_ip(request), "198.51.100.25")

    def test_malformed_forwarded_header_falls_back_to_proxy_peer(self):
        request = self.build_rate_limit_request(
            host="10.0.0.2",
            headers={"x-forwarded-for": "not-an-ip"},
        )

        with patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "10.0.0.2"):
            self.assertEqual(rate_limit_service.get_client_ip(request), "10.0.0.2")

    def test_cidr_trusted_proxy_config_is_supported(self):
        request = self.build_rate_limit_request(
            host="10.0.0.42",
            headers={"x-forwarded-for": "198.51.100.30"},
        )

        with patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "10.0.0.0/24"):
            self.assertEqual(rate_limit_service.get_client_ip(request), "198.51.100.30")

    def test_untrusted_spoofed_forwarded_headers_do_not_bypass_rate_limit(self):
        app = FastAPI()
        store = InMemoryRateLimitStore()

        @app.post("/limited")
        def limited(request: Request):
            enforce_rate_limit(request, "test", limit=2, window_seconds=60)
            return {"ok": True}

        client = TestClient(app)

        with patch.object(rate_limit_service, "_store", store), \
             patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True), \
             patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "127.0.0.1,::1"):
            first = client.post("/limited", headers={"x-forwarded-for": "203.0.113.1"})
            second = client.post("/limited", headers={"x-forwarded-for": "203.0.113.2"})
            response = client.post("/limited", headers={"x-forwarded-for": "203.0.113.3"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(response.status_code, 429)

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
