import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from routes import auth_routes
from services import rate_limit_service
from services.rate_limit_service import InMemoryRateLimitStore, enforce_rate_limit
from services.auth_service import (
    SESSION_ACTIVITY_COOKIE_NAME,
    create_session_activity_value,
    delete_auth_cookies,
    is_session_activity_valid,
    set_auth_cookies,
)
from services.request_security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    add_cors_headers_for_allowed_origin,
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
        frontend_urls = ["https://app.example.com"]
        allowed_origins = get_allowed_origins(frontend_urls)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=frontend_urls,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[CSRF_HEADER_NAME],
        )

        @app.middleware("http")
        async def csrf_middleware(request: Request, call_next):
            blocked_response = validate_cookie_write_origin(request, allowed_origins)
            if blocked_response is not None:
                return add_cors_headers_for_allowed_origin(
                    blocked_response,
                    request,
                    allowed_origins,
                )
            blocked_response = validate_csrf_token(request)
            if blocked_response is not None:
                return add_cors_headers_for_allowed_origin(
                    blocked_response,
                    request,
                    allowed_origins,
                )
            return await call_next(request)

        @app.post("/protected-write")
        def protected_write():
            return {"ok": True}

        @app.put("/builder/projects/{project_id}")
        def update_builder_project(project_id: str):
            return {"ok": True, "project_id": project_id}

        @app.patch("/builder/reservations/{reservation_id}/status")
        def update_builder_reservation_status(reservation_id: str):
            return {"ok": True, "reservation_id": reservation_id}

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

        @app.post("/public/sites/example/auth/{action}")
        def public_tenant_auth(action: str):
            return {"ok": True}

        @app.post("/public/sites/example/events")
        def public_site_event():
            return {"ok": True}

        @app.post("/public/reservations/33333333-3333-4333-8333-333333333333/cancel")
        def public_reservation_cancel():
            return {"ok": True}

        @app.post("/auth/email-verification/resend")
        def resend_email_verification():
            return {"ok": True}

        @app.post("/public/sites/example/not-events")
        def unrelated_public_site_post():
            return {"ok": True}

        @app.post("/issue-cookies")
        def issue_cookies(response: Response):
            csrf_token = set_auth_cookies(response, "access-token", "refresh-token")
            return {"csrf_token": csrf_token}

        @app.post("/clear-cookies")
        def clear_cookies(response: Response):
            delete_auth_cookies(response)
            return {"ok": True}

        @app.post("/auth/log_out")
        def log_out(response: Response):
            delete_auth_cookies(response)
            return {"message": "Logged out successfully"}

        @app.post("/auth/refresh")
        def refresh():
            return {"logged_in": True}

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

    def test_builder_put_preflight_allows_frontend_origin_and_csrf_header(self):
        client = self.build_origin_client()

        response = client.options(
            "/builder/projects/project-1",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://app.example.com",
        )
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")
        self.assertIn("PUT", response.headers.get("access-control-allow-methods", ""))
        self.assertIn("x-csrf-token", response.headers.get("access-control-allow-headers", "").lower())

    def test_builder_put_missing_csrf_rejects_with_cors_headers(self):
        client = self.build_origin_client()

        response = client.put(
            "/builder/projects/project-1",
            headers={
                "Origin": "https://app.example.com",
                "Content-Type": "application/json",
            },
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
            },
            json={"draft_schema": {}},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid CSRF token")
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://app.example.com",
        )
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_builder_put_valid_csrf_reaches_route_logic(self):
        client = self.build_origin_client()
        request_parts = self.build_csrf_request_parts()

        response = client.put(
            "/builder/projects/project-1",
            headers={
                **request_parts["headers"],
                "Content-Type": "application/json",
            },
            cookies=request_parts["cookies"],
            json={"draft_schema": {}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "project_id": "project-1"})

    def test_builder_reservation_status_patch_requires_csrf(self):
        client = self.build_origin_client()

        response = client.patch(
            "/builder/reservations/reservation-1/status",
            headers={"Origin": "https://app.example.com"},
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
            },
            json={"status": "confirmed"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid CSRF token")

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
            "/public/sites/example/auth/register",
            "/public/sites/example/auth/login",
            "/public/sites/example/auth/logout",
            "/public/sites/example/events",
            "/public/reservations/33333333-3333-4333-8333-333333333333/cancel",
            "/auth/email-verification/resend",
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

    def test_unrelated_public_site_post_is_not_csrf_exempt(self):
        client = self.build_origin_client()

        response = client.post(
            "/public/sites/example/not-events",
            headers={"Origin": "https://app.example.com"},
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid CSRF token")

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
            or header.startswith(f"{SESSION_ACTIVITY_COOKIE_NAME}=")
        ]
        self.assertEqual(len(session_cookie_headers), 4)
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
        self.assertTrue(
            any(
                header.startswith(f"{SESSION_ACTIVITY_COOKIE_NAME}=")
                for header in set_cookie_headers
            )
        )

    def test_session_activity_is_valid_for_one_hour(self):
        activity = create_session_activity_value(now=1_000)

        self.assertTrue(is_session_activity_valid(activity, now=4_600))
        self.assertFalse(is_session_activity_valid(activity, now=4_601))

    def test_session_activity_rejects_tampering(self):
        activity = create_session_activity_value(now=1_000)
        timestamp, _ = activity.split(".", 1)

        self.assertFalse(
            is_session_activity_valid(f"{timestamp}.invalid-signature", now=1_001)
        )

    def test_logout_route_is_csrf_exempt_with_auth_cookies_and_missing_header(self):
        client = self.build_origin_client()

        response = client.post(
            "/auth/log_out",
            headers={"Origin": "https://app.example.com"},
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
                CSRF_COOKIE_NAME: "stale-token",
            },
        )
        set_cookie_headers = response.headers.get_list("set-cookie")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Logged out successfully"})
        self.assertTrue(
            any(header.startswith("madar_access_token=") for header in set_cookie_headers)
        )
        self.assertTrue(
            any(header.startswith("madar_refresh_token=") for header in set_cookie_headers)
        )
        self.assertTrue(
            any(header.startswith(f"{CSRF_COOKIE_NAME}=") for header in set_cookie_headers)
        )

    def test_logout_route_is_csrf_exempt_with_auth_cookies_and_invalid_header(self):
        client = self.build_origin_client()

        response = client.post(
            "/auth/log_out",
            headers={
                "Origin": "https://app.example.com",
                CSRF_HEADER_NAME: "bad-token",
            },
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
                CSRF_COOKIE_NAME: "stale-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Logged out successfully"})

    def test_refresh_route_is_csrf_exempt_with_auth_cookies_and_missing_header(self):
        client = self.build_origin_client()

        response = client.post(
            "/auth/refresh",
            headers={"Origin": "https://app.example.com"},
            cookies={
                "madar_access_token": "access-token",
                "madar_refresh_token": "refresh-token",
                CSRF_COOKIE_NAME: "stale-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"logged_in": True})

    def test_user_status_failure_does_not_clear_auth_cookies(self):
        app = FastAPI()
        app.include_router(auth_routes.router)
        client = TestClient(app)

        with patch.object(
            auth_routes,
            "get_authenticated_user_row",
            side_effect=HTTPException(status_code=401, detail="Invalid session"),
        ):
            response = client.get(
                "/auth/user_status",
                cookies={
                    "madar_access_token": "stale-access-token",
                    "madar_refresh_token": "stale-refresh-token",
                },
            )

        set_cookie_headers = response.headers.get_list("set-cookie")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"logged_in": False, "user": None})
        self.assertFalse(
            any(header.startswith("madar_access_token=") for header in set_cookie_headers)
        )
        self.assertFalse(
            any(header.startswith("madar_refresh_token=") for header in set_cookie_headers)
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
             patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "127.0.0.1,::1"), \
             patch("services.audit_service.record_security_event"):
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

        with patch.object(rate_limit_service, "_store", store), \
             patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True), \
             patch("services.audit_service.record_security_event"):
            self.assertEqual(client.post("/limited").status_code, 200)
            self.assertEqual(client.post("/limited").status_code, 200)
            response = client.post("/limited")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many requests. Please try again later.")

    def get_migrations_dir(self):
        candidates = []
        configured_dir = os.getenv("MADAR_MIGRATIONS_DIR")
        if configured_dir:
            candidates.append(Path(configured_dir))

        test_path = Path(__file__).resolve()
        for parent in test_path.parents:
            candidates.append(parent / "database" / "migrations")

        cwd = Path.cwd().resolve()
        candidates.append(cwd / "database" / "migrations")
        for parent in cwd.parents:
            candidates.append(parent / "database" / "migrations")

        checked = []
        seen = set()
        for candidate in candidates:
            resolved = candidate.resolve(strict=False)
            if resolved in seen:
                continue
            seen.add(resolved)
            checked.append(str(resolved))
            if resolved.is_dir():
                return resolved

        self.fail(
            "database migrations are required for security tests; checked: "
            + ", ".join(checked)
        )

    def read_migration_by_suffix(self, migrations_dir: Path, suffix: str) -> str:
        matches = sorted(migrations_dir.glob(f"*_{suffix}"))
        if not matches:
            self.fail(f"missing migration matching *_{suffix} in {migrations_dir}")
        if len(matches) > 1:
            self.fail(
                f"multiple migrations match *_{suffix} in {migrations_dir}: "
                + ", ".join(match.name for match in matches)
            )
        return matches[0].read_text().lower()

    def test_builder_rls_migrations_are_tenant_scoped(self):
        migrations_dir = self.get_migrations_dir()
        builder_projects_sql = self.read_migration_by_suffix(
            migrations_dir,
            "create_builder_projects.sql",
        )
        submissions_sql = self.read_migration_by_suffix(
            migrations_dir,
            "create_builder_form_submissions.sql",
        )

        self.assertIn("alter table public.builder_projects enable row level security", builder_projects_sql)
        self.assertIn("alter table public.builder_form_submissions enable row level security", submissions_sql)
        self.assertIn("tenant_memberships", builder_projects_sql)
        self.assertIn("tenant_memberships", submissions_sql)
        self.assertIn("auth.uid()", builder_projects_sql)
        self.assertIn("auth.uid()", submissions_sql)
        self.assertIn("role in ('owner', 'admin')", builder_projects_sql)
        self.assertNotIn("for insert", submissions_sql.split("create policy", 1)[-1])
        self.assertNotIn("for update", submissions_sql.split("create policy", 1)[-1])

    def test_website_settings_rls_cleanup_removes_user_id_compatibility(self):
        migrations_dir = self.get_migrations_dir()
        website_settings_sql = self.read_migration_by_suffix(
            migrations_dir,
            "harden_website_settings_rls_tenant_only.sql",
        )

        self.assertIn("alter table public.website_settings enable row level security", website_settings_sql)
        self.assertIn("create policy website_settings_select_member", website_settings_sql)
        self.assertIn("create policy website_settings_insert_member", website_settings_sql)
        self.assertIn("create policy website_settings_update_member", website_settings_sql)
        self.assertIn("tenant_memberships", website_settings_sql)
        self.assertIn("auth.uid()", website_settings_sql)
        self.assertIn("website_settings.tenant_id is not null", website_settings_sql)
        self.assertNotIn("where u.id = website_settings.user_id", website_settings_sql)
        self.assertNotIn("tenant_id is null", website_settings_sql)



    def test_audit_logs_migration_is_backend_only(self):
        migrations_dir = self.get_migrations_dir()
        audit_sql = self.read_migration_by_suffix(migrations_dir, "create_audit_logs.sql")

        self.assertIn("create table if not exists public.audit_logs", audit_sql)
        self.assertIn("tenant_id integer references public.tenants", audit_sql)
        self.assertIn("actor_user_id integer references public.users", audit_sql)
        self.assertIn("metadata jsonb not null default '{}'::jsonb", audit_sql)
        self.assertIn("alter table public.audit_logs enable row level security", audit_sql)
        self.assertIn("revoke all on table public.audit_logs from anon", audit_sql)
        self.assertIn("revoke all on table public.audit_logs from authenticated", audit_sql)
        self.assertIn("to service_role", audit_sql)
        self.assertNotIn("to anon", audit_sql.split("revoke", 1)[0])
        self.assertNotIn("create policy", audit_sql)
        self.assertIn("audit_logs_tenant_created_idx", audit_sql)
        self.assertIn("audit_logs_actor_created_idx", audit_sql)
        self.assertIn("audit_logs_action_created_idx", audit_sql)
        self.assertIn("audit_logs_target_idx", audit_sql)

    def test_features_rls_migration_is_tenant_scoped_and_read_only(self):
        migrations_dir = self.get_migrations_dir()
        features_sql = self.read_migration_by_suffix(
            migrations_dir,
            "harden_features_rls.sql",
        )

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
