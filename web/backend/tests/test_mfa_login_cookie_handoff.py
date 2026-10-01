import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import redis
from services import mfa_login_service
from routes import mfa_routes
from mfa_cookie_fixture import UserStore
from mfa_cookie_fixture import ADMIN, cookie_fixture


class MfaCookieHandoffTests(unittest.TestCase):
    def setUp(self):
        self.app, self.provider, self.store, stack = cookie_fixture(secure=True)
        self.addCleanup(stack.close)
        self.client = TestClient(self.app, base_url="https://testserver")
        self.addCleanup(self.client.close)
    def login(self, prefix="/api"):
        return self.client.post(prefix + "/auth/login", json={"email": ADMIN["email"], "password": "synthetic-password"}, headers={"Origin": "https://testserver"})
    def challenge(self, prefix="/api"):
        return self.client.post(prefix + "/auth/mfa/login/challenge", json={"factor_id": "synthetic-factor"}, headers={"Origin": "https://testserver"})
    def verify(self, challenge, code="123456"):
        return self.client.post("/api/auth/mfa/login/verify", json={"factor_id": "synthetic-factor", "challenge_id": challenge, "code": code}, headers={"Origin": "https://testserver"})
    def test_real_response_preserves_cookie_and_jar_reaches_prefixed_challenge(self):
        result = self.login()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["mfa_required"])
        header = next(h for h in result.headers.get_list("set-cookie") if "Max-Age=300" in h)
        for attribute in ["HttpOnly", "Secure", "SameSite=lax", "Path=/"]: self.assertIn(attribute, header)
        self.assertNotIn("Domain=", header)
        self.assertNotIn("madar_access_token", result.cookies)
        self.assertNotIn("madar_refresh_token", result.cookies)
        self.assertLess(len(header), 1024)
        self.assertEqual(self.challenge().status_code, 200)
    def test_direct_backend_cookie_jar_also_works(self):
        self.assertEqual(self.login(prefix="").status_code, 200)
        self.assertEqual(self.challenge(prefix="").status_code, 200)
    def test_missing_tampered_expired_and_wrong_key_cookies_are_rejected(self):
        self.assertEqual(self.challenge().status_code, 401)
        self.login()
        captured = self.client.cookies.get("madar_mfa_pending")
        self.client.cookies.set("madar_mfa_pending", "tampered", domain="testserver.local", path="/")
        self.assertEqual(self.challenge().status_code, 401)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        self.login()
        with patch.object(mfa_login_service.time, "time", return_value=time.time() + 301):
            self.assertEqual(self.challenge().status_code, 401)
        self.client.cookies.set("madar_mfa_pending", captured, domain="testserver.local", path="/")
        with patch.object(mfa_login_service, "get_csrf_secret", return_value="wrong-key"):
            self.assertEqual(self.challenge().status_code, 401)
    def test_success_requires_aal2_issues_cookies_and_consumes_pending_session(self):
        self.login()
        captured = self.client.cookies.get("madar_mfa_pending")
        challenge = self.challenge().json()["challenge_id"]
        verified = self.verify(challenge)
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(self.provider.level, "aal2")
        self.assertEqual(self.client.cookies.get("madar_access_token"), "synthetic-aal2-access")
        self.assertEqual(self.client.cookies.get("madar_refresh_token"), "synthetic-aal2-refresh")
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        for header in verified.headers.get_list("set-cookie"):
            if "madar_access_token=" in header or "madar_refresh_token=" in header:
                self.assertIn("Secure", header); self.assertIn("HttpOnly", header)
        self.client.cookies.clear()
        self.client.cookies.set("madar_mfa_pending", captured, domain="testserver.local", path="/")
        self.assertEqual(self.challenge().status_code, 401)
        self.assertEqual(self.verify(challenge).status_code, 401)
    def test_failed_code_can_retry_without_any_ordinary_cookie(self):
        self.login()
        challenge = self.challenge().json()["challenge_id"]
        self.assertEqual(self.verify(challenge, "000000").status_code, 400)
        self.assertNotIn("madar_access_token", self.client.cookies)
        self.assertIn("madar_mfa_pending", self.client.cookies)
        self.assertEqual(self.challenge().status_code, 200)
        self.assertEqual(self.verify(challenge).status_code, 200)
    def test_bounded_attempts_revoke_record(self):
        self.login()
        captured = self.client.cookies.get("madar_mfa_pending")
        with patch.object(mfa_login_service, "PENDING_MFA_MAX_OPERATIONS", 2):
            self.assertEqual(self.challenge().status_code, 200)
            self.assertEqual(self.challenge().status_code, 200)
            self.assertEqual(self.challenge().status_code, 401)
        self.client.cookies.set("madar_mfa_pending", captured, domain="testserver.local", path="/")
        self.assertEqual(self.challenge().status_code, 401)
    def test_cancellation_revokes_record_and_clears_real_cookie(self):
        self.login()
        captured = self.client.cookies.get("madar_mfa_pending")
        result = self.client.post("/api/auth/mfa/login/cancel", headers={"Origin": "https://testserver"})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        self.client.cookies.set("madar_mfa_pending", captured, domain="testserver.local", path="/")
        self.assertEqual(self.challenge().status_code, 401)
    def test_provider_aal1_after_verify_never_issues_session(self):
        self.login(); challenge = self.challenge().json()["challenge_id"]
        with patch.object(self.provider, "get_authenticator_assurance_level", return_value={"current_level": "aal1"}):
            self.assertEqual(self.verify(challenge).status_code, 400)
        self.assertNotIn("madar_access_token", self.client.cookies)
    def test_ordinary_user_login_behavior_unchanged(self):
        app, _provider, _store, stack = cookie_fixture(normal=True)
        with stack, TestClient(app) as client:
            result = client.post("/auth/login", json={"email": ADMIN["email"], "password": "synthetic-password"})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("mfa_required", result.json())
        self.assertIn("madar_access_token", result.cookies)
        self.assertNotIn("madar_mfa_pending", result.cookies)
    def test_invalid_primary_password_never_issues_pending_cookie(self):
        result = self.client.post("/auth/login", json={"email": ADMIN["email"], "password": "invalid"})
        self.assertGreaterEqual(result.status_code, 400)
        self.assertNotIn("madar_mfa_pending", result.cookies)

    def test_logout_revokes_pending_cookie_without_ordinary_session(self):
        self.login()
        captured = self.client.cookies.get("madar_mfa_pending")
        result = self.client.post("/api/auth/log_out", headers={"Origin": "https://testserver"})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        self.client.cookies.set("madar_mfa_pending", captured, domain="testserver.local", path="/")
        self.assertEqual(self.challenge().status_code, 401)

    def test_wrong_account_binding_revokes_pending_session(self):
        self.login()
        challenge = self.challenge().json()["challenge_id"]
        with patch.object(mfa_routes, "service_supabase", UserStore({**ADMIN, "auth_id": "another-account"})):
            result = self.verify(challenge)
        self.assertEqual(result.status_code, 401)
        self.assertNotIn("madar_access_token", self.client.cookies)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)

    def test_store_failure_fails_closed_before_cookie_issuance(self):
        with patch.object(self.store, "set", side_effect=redis.ConnectionError("synthetic outage")):
            result = self.login()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("madar_mfa_pending", result.cookies)
        self.assertNotIn("madar_access_token", result.cookies)

    def test_factor_id_alone_and_foreign_factor_cannot_identify_account(self):
        self.assertEqual(self.challenge().status_code, 401)
        self.login()
        result = self.client.post("/api/auth/mfa/login/challenge", json={"factor_id": "foreign-factor"}, headers={"Origin": "https://testserver"})
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        self.assertNotIn("madar_access_token", self.client.cookies)

    def test_pending_cookie_does_not_authenticate_ordinary_status(self):
        self.login()
        result = self.client.get("/api/auth/user_status")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["logged_in"])

    def test_new_primary_login_revokes_old_pending_reference(self):
        self.login()
        captured = self.client.cookies.get("madar_mfa_pending")
        self.login()
        self.client.cookies.set("madar_mfa_pending", captured, domain="testserver.local", path="/")
        self.assertEqual(self.challenge().status_code, 401)

    def test_invalid_provider_session_revokes_and_clears_pending_cookie(self):
        self.login()
        with patch.object(self.provider, "set_session", side_effect=ValueError("Invalid provider session")):
            self.assertEqual(self.challenge().status_code, 401)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        self.assertNotIn("madar_access_token", self.client.cookies)

    def test_store_read_outage_does_not_authenticate(self):
        self.login()
        with patch.object(self.store, "get", side_effect=redis.ConnectionError("synthetic outage")):
            self.assertEqual(self.challenge().status_code, 503)
        self.assertNotIn("madar_access_token", self.client.cookies)

    def test_malformed_encrypted_payload_is_not_a_server_error(self):
        for payload in [[], {"v": 2, "sid": "too-short", "exp": int(time.time()) + 300}]:
            self.client.cookies.set("madar_mfa_pending", mfa_login_service.encode_pending_mfa_payload(payload), domain="testserver.local", path="/")
            self.assertEqual(self.challenge().status_code, 401)

    def test_pending_cookie_write_requires_trusted_origin(self):
        self.login()
        for endpoint in ["challenge", "verify", "enroll", "enroll/verify", "cancel"]:
            result = self.client.post("/api/auth/mfa/login/" + endpoint, json={}, headers={"Origin": "https://attacker.invalid"})
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.json()["detail"], "Invalid request origin")
        self.assertIn("madar_mfa_pending", self.client.cookies)
        self.assertEqual(self.challenge().status_code, 200)
