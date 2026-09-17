import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import mfa_routes
from services import audit_service


USER_DATA = {
    "id": 5,
    "auth_id": "auth-1",
    "tenant_id": 7,
    "user_type": "admin",
}


def build_client():
    app = FastAPI()
    app.include_router(mfa_routes.router)
    return TestClient(app)


def auth_context():
    return SimpleNamespace(id="auth-1"), USER_DATA


class MfaRoutesTests(unittest.TestCase):
    def setUp(self):
        self.mfa_client = MagicMock()
        factory = patch.object(mfa_routes, "get_request_mfa_client", return_value=self.mfa_client)
        factory.start()
        self.addCleanup(factory.stop)

    def test_status_returns_safe_settings_and_factors(self):
        client = build_client()
        factors_response = SimpleNamespace(
            data=SimpleNamespace(
                all=[
                    {
                        "id": "factor-1",
                        "factor_type": "totp",
                        "status": "verified",
                        "secret": "do-not-return",
                    }
                ]
            )
        )

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True, "last_aal2_at": "now"}), \
             patch.object(self.mfa_client.auth.mfa, "list_factors", return_value=factors_response), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal1"}):
            response = client.get("/auth/mfa/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["mfa_required"])
        self.assertEqual(data["aal"], {"current_level": "aal1"})
        self.assertEqual(data["factors"][0]["id"], "factor-1")
        self.assertNotIn("secret", str(data).lower())

    def test_enroll_returns_qr_uri_and_records_started_event(self):
        client = build_client()
        enroll_response = SimpleNamespace(
            data=SimpleNamespace(
                id="factor-1",
                factor_type="totp",
                status="unverified",
                totp=SimpleNamespace(
                    qr_code="svg-data",
                    uri="otpauth://totp/example",
                    secret="do-not-return",
                ),
            )
        )

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(self.mfa_client.auth.mfa, "enroll", return_value=enroll_response) as enroll, \
             patch.object(mfa_routes, "record_mfa_event") as record_mfa_event:
            response = client.post("/auth/mfa/enroll", json={"friendly_name": "Admin phone"})

        self.assertEqual(response.status_code, 200)
        enroll.assert_called_once_with({"factor_type": "totp", "friendly_name": "Admin phone"})
        data = response.json()
        self.assertEqual(data["factor"]["id"], "factor-1")
        self.assertEqual(data["totp"]["qr_code"], "svg-data")
        self.assertEqual(data["totp"]["uri"], "otpauth://totp/example")
        self.assertNotIn("secret", str(data).lower())
        self.assertEqual(record_mfa_event.call_args.kwargs["action"], audit_service.MFA_ENROLL_STARTED)

    def test_enroll_verify_challenges_verifies_and_records_success_events(self):
        client = build_client()
        challenge_response = SimpleNamespace(data=SimpleNamespace(id="challenge-1"))

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(self.mfa_client.auth.mfa, "challenge", return_value=challenge_response) as challenge, \
             patch.object(self.mfa_client.auth.mfa, "verify", return_value=SimpleNamespace(data={})) as verify, \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal2"}), \
             patch.object(mfa_routes, "mark_aal2_verified") as mark_aal2_verified, \
             patch.object(mfa_routes, "record_mfa_event") as record_mfa_event:
            response = client.post(
                "/auth/mfa/enroll/verify",
                json={"factor_id": "factor-1", "code": "123456"},
            )

        self.assertEqual(response.status_code, 200)
        challenge.assert_called_once_with({"factor_id": "factor-1"})
        verify.assert_called_once_with({"factor_id": "factor-1", "challenge_id": "challenge-1", "code": "123456"})
        mark_aal2_verified.assert_called_once()
        actions = [call.kwargs["action"] for call in record_mfa_event.call_args_list]
        self.assertEqual(actions, [audit_service.MFA_ENROLL_VERIFIED, audit_service.MFA_VERIFIED])

    def test_enroll_verify_sets_refreshed_aal2_auth_cookies_when_session_returned(self):
        client = build_client()
        challenge_response = SimpleNamespace(data=SimpleNamespace(id="challenge-1"))
        verify_response = SimpleNamespace(
            data=SimpleNamespace(
                session=SimpleNamespace(access_token="aal2-access", refresh_token="aal2-refresh")
            )
        )

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(self.mfa_client.auth.mfa, "challenge", return_value=challenge_response), \
             patch.object(self.mfa_client.auth.mfa, "verify", return_value=verify_response), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal2"}), \
             patch.object(mfa_routes, "set_auth_cookies", return_value="csrf") as set_auth_cookies, \
             patch.object(mfa_routes, "mark_aal2_verified"), \
             patch.object(mfa_routes, "record_mfa_event"):
            response = client.post(
                "/auth/mfa/enroll/verify",
                json={"factor_id": "factor-1", "code": "123456"},
            )

        self.assertEqual(response.status_code, 200)
        set_auth_cookies.assert_called_once()
        self.assertEqual(set_auth_cookies.call_args.args[1:], ("aal2-access", "aal2-refresh"))

    def test_enroll_verify_records_challenge_failed_on_error(self):
        client = build_client()

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(self.mfa_client.auth.mfa, "challenge", side_effect=RuntimeError("bad code")), \
             patch.object(mfa_routes, "record_mfa_event") as record_mfa_event:
            response = client.post(
                "/auth/mfa/enroll/verify",
                json={"factor_id": "factor-1", "code": "123456"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(record_mfa_event.call_args.kwargs["action"], audit_service.MFA_CHALLENGE_FAILED)
        self.assertNotIn("123456", str(record_mfa_event.call_args.kwargs["metadata"]))

    def test_enroll_verify_fails_closed_when_provider_does_not_report_aal2(self):
        client = build_client()
        challenge_response = SimpleNamespace(data=SimpleNamespace(id="challenge-1"))
        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(self.mfa_client.auth.mfa, "challenge", return_value=challenge_response), \
             patch.object(self.mfa_client.auth.mfa, "verify", return_value=SimpleNamespace(data={})), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={}), \
             patch.object(mfa_routes, "mark_aal2_verified") as mark_aal2_verified, \
             patch.object(mfa_routes, "record_mfa_event"):
            response = client.post("/auth/mfa/enroll/verify", json={"factor_id": "factor-1", "code": "123456"})
        self.assertEqual(response.status_code, 400)
        mark_aal2_verified.assert_not_called()

    def test_admin_cannot_remove_last_verified_factor(self):
        client = build_client()
        factors = SimpleNamespace(data=SimpleNamespace(totp=[{"id": "factor-1", "status": "verified"}]))
        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal2"}), \
             patch.object(self.mfa_client.auth.mfa, "list_factors", return_value=factors), \
             patch.object(self.mfa_client.auth.mfa, "unenroll") as unenroll:
            response = client.delete("/auth/mfa/factors/factor-1")
        self.assertEqual(response.status_code, 409)
        unenroll.assert_not_called()

    def test_factors_returns_sanitized_factor_list(self):
        client = build_client()
        factors_response = SimpleNamespace(data=SimpleNamespace(totp=[{"id": "factor-1", "factor_type": "totp", "secret": "hidden"}]))

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": False}), \
             patch.object(self.mfa_client.auth.mfa, "list_factors", return_value=factors_response):
            response = client.get("/auth/mfa/factors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["factors"], [{"id": "factor-1", "factor_type": "totp"}])
        self.assertNotIn("hidden", str(response.json()))

    def test_remove_factor_with_aal1_returns_403_and_does_not_unenroll(self):
        client = build_client()

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal1"}), \
             patch.object(self.mfa_client.auth.mfa, "unenroll") as unenroll:
            response = client.delete("/auth/mfa/factors/factor-1")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "MFA verification required before removing this factor")
        unenroll.assert_not_called()

    def test_remove_factor_with_missing_aal_fails_closed(self):
        client = build_client()
        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={}), \
             patch.object(self.mfa_client.auth.mfa, "unenroll") as unenroll:
            response = client.delete("/auth/mfa/factors/factor-1")
        self.assertEqual(response.status_code, 403)
        unenroll.assert_not_called()

    def test_remove_factor_with_aal2_unenrolls_and_records_event(self):
        client = build_client()

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal2"}), \
             patch.object(self.mfa_client.auth.mfa, "list_factors", return_value=SimpleNamespace(data=SimpleNamespace(totp=[{"id": "factor-1", "status": "verified"}, {"id": "factor-2", "status": "verified"}]))), \
             patch.object(self.mfa_client.auth.mfa, "unenroll", return_value=SimpleNamespace(data={})) as unenroll, \
             patch.object(mfa_routes, "record_mfa_event") as record_mfa_event:
            response = client.delete("/auth/mfa/factors/factor-1")

        self.assertEqual(response.status_code, 200)
        unenroll.assert_called_once_with({"factor_id": "factor-1"})
        self.assertEqual(record_mfa_event.call_args.kwargs["action"], audit_service.MFA_FACTOR_REMOVED)
        self.assertEqual(response.json(), {"removed": True, "factor_id": "factor-1"})

    def test_remove_factor_failure_logs_sanitized_error_fields(self):
        client = build_client()

        class SupabaseError(Exception):
            status = 400
            code = "insufficient_aal"
            message = "AAL2 required"

        with patch.object(mfa_routes, "get_authenticated_user_row", return_value=auth_context()), \
             patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": True}), \
             patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal2"}), \
             patch.object(self.mfa_client.auth.mfa, "list_factors", return_value=SimpleNamespace(data=SimpleNamespace(totp=[{"id": "factor-1", "status": "verified"}, {"id": "factor-2", "status": "verified"}]))), \
             patch.object(self.mfa_client.auth.mfa, "unenroll", side_effect=SupabaseError("token should not appear")), \
             patch.object(mfa_routes.logger, "warning") as warning:
            response = client.delete("/auth/mfa/factors/factor-1")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Could not remove MFA factor")
        warning.assert_called_once()
        extra = warning.call_args.kwargs["extra"]
        self.assertEqual(extra["error_type"], "SupabaseError")
        self.assertEqual(extra["status"], "400")
        self.assertNotIn("code", extra)
        self.assertNotIn("message", extra)
        self.assertNotIn("token should not appear", str(extra))


if __name__ == "__main__":
    unittest.main()
