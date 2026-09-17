import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import auth_routes, mfa_routes


ADMIN_USER = {
    "id": 5,
    "auth_id": "auth-1",
    "tenant_id": 7,
    "email": "admin@example.com",
    "user_type": "admin",
}

REGULAR_USER = {
    "id": 6,
    "auth_id": "auth-2",
    "tenant_id": 7,
    "email": "user@example.com",
    "user_type": "user",
}


def build_auth_client():
    app = FastAPI()
    app.include_router(auth_routes.router)
    return TestClient(app)


def build_mfa_client():
    app = FastAPI()
    app.include_router(mfa_routes.router)
    return TestClient(app)


def auth_response(auth_id="auth-1"):
    return SimpleNamespace(
        user=SimpleNamespace(id=auth_id, email_confirmed_at="2026-01-01T00:00:00Z"),
        session=SimpleNamespace(access_token="aal1-access", refresh_token="aal1-refresh"),
    )


class AdminMfaLoginEnforcementTests(unittest.TestCase):
    def test_flag_off_preserves_existing_login_behavior(self):
        client = build_auth_client()

        with patch.object(auth_routes, "enforce_auth_rate_limit"), \
             patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=auth_response()), \
             patch.object(auth_routes, "get_local_user_by_auth_id", return_value=ADMIN_USER), \
             patch.object(auth_routes, "is_admin_mfa_login_enforcement_enabled", return_value=False), \
             patch.object(auth_routes, "set_auth_cookies", return_value="csrf") as set_auth_cookies, \
             patch.object(auth_routes, "set_pending_mfa_cookie") as set_pending_mfa_cookie, \
             patch.object(auth_routes, "record_security_event"):
            response = client.post(
                "/auth/login",
                json={"email": "admin@example.com", "password": "password123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mfa_required", response.json())
        set_auth_cookies.assert_called_once()
        self.assertEqual(set_auth_cookies.call_args.args[1:], ("aal1-access", "aal1-refresh"))
        set_pending_mfa_cookie.assert_not_called()

    def test_regular_user_unchanged_when_flag_enabled(self):
        client = build_auth_client()

        with patch.object(auth_routes, "enforce_auth_rate_limit"), \
             patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=auth_response("auth-2")), \
             patch.object(auth_routes, "get_local_user_by_auth_id", return_value=REGULAR_USER), \
             patch.object(auth_routes, "is_admin_mfa_login_enforcement_enabled", return_value=True), \
             patch.object(auth_routes, "get_user_security_settings") as get_user_security_settings, \
             patch.object(auth_routes, "set_auth_cookies", return_value="csrf"), \
             patch.object(auth_routes, "record_security_event"):
            response = client.post(
                "/auth/login",
                json={"email": "user@example.com", "password": "password123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mfa_required", response.json())
        get_user_security_settings.assert_not_called()

    def test_admin_with_required_mfa_and_verified_factor_gets_pending_cookie_only(self):
        client = build_auth_client()
        factors = [{"id": "factor-1", "factor_type": "totp", "status": "verified"}]

        with patch.object(auth_routes, "enforce_auth_rate_limit"), \
             patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=auth_response()), \
             patch.object(auth_routes, "get_local_user_by_auth_id", return_value=ADMIN_USER), \
             patch.object(auth_routes, "is_admin_mfa_login_enforcement_enabled", return_value=True), \
             patch.object(auth_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(auth_routes, "create_pending_mfa_client", return_value=SimpleNamespace()), \
             patch.object(auth_routes, "verified_totp_factors_for_client", return_value=factors), \
             patch.object(auth_routes, "set_pending_mfa_cookie") as set_pending_mfa_cookie, \
             patch.object(auth_routes, "set_auth_cookies") as set_auth_cookies:
            response = client.post(
                "/auth/login",
                json={"email": "admin@example.com", "password": "password123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"mfa_required": True, "factors": factors})
        set_pending_mfa_cookie.assert_called_once()
        set_auth_cookies.assert_not_called()

    def test_admin_with_no_verified_factor_gets_enrollment_only_session(self):
        client = build_auth_client()

        with patch.object(auth_routes, "enforce_auth_rate_limit"), \
             patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=auth_response()), \
             patch.object(auth_routes, "get_local_user_by_auth_id", return_value=ADMIN_USER), \
             patch.object(auth_routes, "is_admin_mfa_login_enforcement_enabled", return_value=True), \
             patch.object(auth_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(auth_routes, "create_pending_mfa_client", return_value=SimpleNamespace()), \
             patch.object(auth_routes, "verified_totp_factors_for_client", return_value=[]), \
             patch.object(auth_routes, "set_auth_cookies", return_value="csrf") as set_auth_cookies, \
             patch.object(auth_routes, "set_pending_mfa_cookie") as set_pending_mfa_cookie, \
             patch.object(auth_routes, "record_security_event"):
            response = client.post(
                "/auth/login",
                json={"email": "admin@example.com", "password": "password123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["restricted_session"], "mfa_enrollment_only")
        self.assertTrue(response.json()["mfa_enrollment_required"])
        set_pending_mfa_cookie.assert_called_once()
        set_auth_cookies.assert_not_called()

    def test_admin_factor_lookup_error_fails_closed(self):
        client = build_auth_client()
        with patch.object(auth_routes, "enforce_auth_rate_limit"), \
             patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=auth_response()), \
             patch.object(auth_routes, "get_local_user_by_auth_id", return_value=ADMIN_USER), \
             patch.object(auth_routes, "is_admin_mfa_login_enforcement_enabled", return_value=True), \
             patch.object(auth_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(auth_routes, "create_pending_mfa_client", return_value=SimpleNamespace()), \
             patch.object(auth_routes, "verified_totp_factors_for_client", side_effect=TimeoutError()), \
             patch.object(auth_routes, "set_auth_cookies") as set_auth_cookies, \
             patch.object(auth_routes, "set_pending_mfa_cookie") as set_pending_mfa_cookie, \
             patch.object(auth_routes, "record_security_event"):
            response = client.post("/auth/login", json={"email": "admin@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "mfa_provider_unavailable")
        set_auth_cookies.assert_not_called()
        set_pending_mfa_cookie.assert_not_called()

    def test_mfa_verify_success_sets_normal_cookies_and_clears_pending_cookie(self):
        client = build_mfa_client()
        mfa_client = SimpleNamespace(
            auth=SimpleNamespace(
                mfa=SimpleNamespace(
                    verify=lambda _payload: SimpleNamespace(
                        data=SimpleNamespace(
                            session=SimpleNamespace(access_token="aal2-access", refresh_token="aal2-refresh")
                        )
                    ),
                    get_authenticator_assurance_level=lambda: SimpleNamespace(
                        data=SimpleNamespace(current_level="aal2")
                    ),
                ),
                get_session=lambda: SimpleNamespace(
                    session=SimpleNamespace(access_token="fallback-access", refresh_token="fallback-refresh")
                ),
            )
        )

        with patch.object(mfa_routes, "read_pending_mfa_cookie", return_value={"user_id": 5, "auth_id": "auth-1", "tenant_id": 7}), \
             patch.object(mfa_routes, "create_pending_mfa_client", return_value=mfa_client), \
             patch.object(mfa_routes, "get_local_user_for_pending_mfa", return_value=ADMIN_USER), \
             patch.object(mfa_routes, "set_auth_cookies", return_value="csrf") as set_auth_cookies, \
             patch.object(mfa_routes, "clear_pending_mfa_cookie") as clear_pending_mfa_cookie, \
             patch.object(mfa_routes, "mark_aal2_verified"), \
             patch.object(mfa_routes, "record_security_event"), \
             patch.object(mfa_routes, "record_mfa_event"):
            response = client.post(
                "/auth/mfa/login/verify",
                json={"factor_id": "factor-1", "challenge_id": "challenge-1", "code": "123456"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["csrf_token"], "csrf")
        set_auth_cookies.assert_called_once()
        self.assertEqual(set_auth_cookies.call_args.args[1:], ("aal2-access", "aal2-refresh"))
        clear_pending_mfa_cookie.assert_called_once()

    def test_mfa_verify_failure_does_not_set_normal_cookies(self):
        client = build_mfa_client()
        mfa_client = SimpleNamespace(
            auth=SimpleNamespace(
                mfa=SimpleNamespace(verify=lambda _payload: (_ for _ in ()).throw(RuntimeError("bad code")))
            )
        )

        with patch.object(mfa_routes, "read_pending_mfa_cookie", return_value={"user_id": 5, "auth_id": "auth-1", "tenant_id": 7}), \
             patch.object(mfa_routes, "create_pending_mfa_client", return_value=mfa_client), \
             patch.object(mfa_routes, "set_auth_cookies") as set_auth_cookies, \
             patch.object(mfa_routes, "clear_pending_mfa_cookie") as clear_pending_mfa_cookie, \
             patch.object(mfa_routes, "record_mfa_event"):
            response = client.post(
                "/auth/mfa/login/verify",
                json={"factor_id": "factor-1", "challenge_id": "challenge-1", "code": "123456"},
            )

        self.assertEqual(response.status_code, 400)
        set_auth_cookies.assert_not_called()
        clear_pending_mfa_cookie.assert_called_once()


if __name__ == "__main__":
    unittest.main()
