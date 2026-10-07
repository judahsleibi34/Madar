import os
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
import app as app_module
from services import provider_recovery as recovery


class RecoveryFenceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"MADAR_RECOVERY_PROFILE": recovery.PROFILE})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app_module.app)

    def test_all_registered_unapproved_routes_are_denied_before_dependencies(self):
        checked = 0
        for route in app_module.app.routes:
            path = getattr(route, "path", "")
            if not path:
                continue
            concrete = __import__("re").sub(r"\{[^}]+\}", "123", path)
            for method in getattr(route, "methods", []) or []:
                if recovery.request_allowed(method, concrete):
                    continue
                with self.subTest(method=method, path=path):
                    response = self.client.request(method, concrete, follow_redirects=False)
                    self.assertEqual(response.status_code, 503)
                    if method != "HEAD":
                        self.assertEqual(response.json()["detail"]["code"], "provider_recovery_read_only")
                    self.assertEqual(response.headers["cache-control"], "no-store")
                checked += 1
        self.assertGreater(checked, 250)

    def test_unknown_routes_and_side_effect_gets_are_denied(self):
        for path in ("/new-module/write", "/public/contact", "/auth/email-verification/status", "/admin/users", "/screen-time/heartbeat"):
            for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                self.assertEqual(self.client.request(method, path).status_code, 503)

    def test_core_health_and_public_recovery_status(self):
        self.assertEqual(self.client.get("/health/live").status_code, 200)
        self.assertEqual(self.client.get("/health/recovery").json(),
                         {"restricted": True, "business_writes_enabled": False})

    def test_auth_maintenance_does_not_disable_csrf(self):
        response = self.client.post("/auth/log_out", headers={"Origin": "https://untrusted.example"}, cookies={"madar_access_token": "fixture"})
        self.assertEqual(response.status_code, 403)

    def test_login_is_admitted_but_signup_and_mfa_enrollment_never_are(self):
        self.assertNotEqual(self.client.post("/auth/login", json={}).status_code, 503)
        for path in ("/auth/signup", "/auth/mfa/enroll", "/auth/mfa/login/enroll", "/password/forgot"):
            self.assertEqual(self.client.post(path).status_code, 503)

    def test_provider_fence_denies_all_business_writes_and_rpc_reads(self):
        marker = recovery.REQUEST_OPERATION.set(("POST", "/auth/login"))
        self.addCleanup(recovery.REQUEST_OPERATION.reset, marker)
        for path in ("/rest/v1/users", "/rest/v1/tenants", "/rest/v1/builder_projects", "/rest/v1/reservations", "/rest/v1/forms", "/rest/v1/calendar_events", "/rest/v1/notifications", "/storage/v1/object/builder-assets/file", "/auth/v1/signup", "/auth/v1/admin/users"):
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                self.assertFalse(recovery.provider_request_allowed(httpx.Request(method, "http://madar-supabase:8000" + path, json={"fixture": True})))
        self.assertFalse(recovery.provider_request_allowed(httpx.Request("GET", "http://madar-supabase:8000/rest/v1/rpc/unknown")))

    def test_provider_auth_allowlist_and_security_payload_constraints(self):
        marker = recovery.REQUEST_OPERATION.set(("POST", "/auth/mfa/login/verify"))
        self.addCleanup(recovery.REQUEST_OPERATION.reset, marker)
        for path in ("/auth/v1/token?grant_type=password", "/auth/v1/token?grant_type=refresh_token", "/auth/v1/logout", "/auth/v1/factors/" + "a" * 36 + "/verify"):
            self.assertTrue(recovery.provider_request_allowed(httpx.Request("POST", "http://madar-supabase:8000" + path)))
        self.assertFalse(recovery.provider_request_allowed(httpx.Request("POST", "http://madar-supabase:8000/auth/v1/token?grant_type=unknown")))
        for payload, allowed in (({"user_id": 1, "auth_id": "fixture", "last_aal2_at": "fixture"}, True), ({"user_id": 1, "auth_id": "fixture", "mfa_required": False}, False)):
            self.assertEqual(recovery.provider_request_allowed(httpx.Request("POST", "http://madar-supabase:8000/rest/v1/user_security_settings", json=payload)), allowed)
        recovery.REQUEST_OPERATION.set(None)
        self.assertFalse(recovery.provider_request_allowed(httpx.Request("POST", "http://madar-supabase:8000/auth/v1/logout")))

    def test_account_lifecycle_and_worker_start_fail_closed(self):
        for user, active, same in (({"email_verified": False}, True, True), ({"email_verified": True}, False, True), ({"email_verified": True}, True, False)):
            with self.assertRaises(HTTPException):
                recovery.require_existing_account(user, active=active, email_matches=same)
        recovery.require_existing_account({"email_verified": True}, active=True, email_matches=True)
        with self.assertRaises(RuntimeError):
            recovery.prohibit_worker_start()

    def test_normal_profile_is_unchanged_and_unknown_mode_rejected(self):
        with patch.dict(os.environ, {"MADAR_RECOVERY_PROFILE": ""}):
            self.assertFalse(recovery.enabled())
            self.assertEqual(self.client.get("/health/recovery").json()["restricted"], False)
        with patch.dict(os.environ, {"MADAR_RECOVERY_PROFILE": "unknown"}):
            with self.assertRaises(RuntimeError):
                recovery.enabled()

    def test_asset_authorization_reuses_full_legacy_path_without_rpc(self):
        from starlette.requests import Request
        from starlette.responses import Response
        request = Request({"type": "http", "method": "GET", "path": "/uploads/tenant_1/builder_assets/fixture.png", "headers": []})
        with patch.object(app_module, "_legacy_asset_visibility", return_value=(False, False)) as legacy:
            self.assertEqual(app_module._asset_visibility(tenant_id=1, storage_key="fixture", request=request, response=Response()), (False, False))
            legacy.assert_called_once()
