import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import auth_routes, password_routes


def password_client():
    app = FastAPI()
    app.include_router(password_routes.router)
    return TestClient(app)


def auth_client():
    app = FastAPI()
    app.include_router(auth_routes.router)
    return TestClient(app)


def confirmed_auth_user(email="owner@example.com"):
    return SimpleNamespace(
        id="auth-1",
        email=email,
        email_confirmed_at="2026-01-01T00:00:00Z",
    )


def local_user(email="owner@example.com"):
    return {
        "id": 4,
        "auth_id": "auth-1",
        "tenant_id": 9,
        "email": email,
        "account_status": "active",
        "password_reset_requested_at": datetime.now(timezone.utc).isoformat(),
    }


class PasswordLifecycleTests(unittest.TestCase):
    def test_expired_rpc_claim_is_persisted_and_reported_as_expired(self):
        rpc_result = SimpleNamespace(
            data={"id": "request-1", "status": "expired"}
        )
        rpc_call = SimpleNamespace(execute=Mock(return_value=rpc_result))
        service = SimpleNamespace(rpc=Mock(return_value=rpc_call))

        with patch.object(password_routes, "service_supabase", service):
            with self.assertRaises(password_routes.HTTPException) as raised:
                password_routes.claim_password_reset_request("auth-1", "n" * 32)

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.detail["code"], "password_reset_expired")

    def test_reset_password_uses_shared_minimum_policy(self):
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes.supabase.auth,
            "get_user",
        ) as get_user:
            response = password_client().post(
                "/auth/password-reset",
                json={"access_token": "provider-token", "password": "short"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "password_policy_failed")
        get_user.assert_not_called()

    def test_durable_request_token_is_claimed_and_finished_around_password_update(self):
        provider = SimpleNamespace(user=confirmed_auth_user())
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes.supabase.auth,
            "get_user",
            return_value=provider,
        ), patch.object(
            password_routes,
            "get_local_user_by_auth_id",
            return_value=local_user(),
        ), patch.object(
            password_routes,
            "claim_password_reset_request",
            return_value="request-1",
        ) as claim, patch.object(
            password_routes,
            "finish_password_reset_request",
        ) as finish, patch.object(
            password_routes.admin_supabase.auth.admin,
            "update_user_by_id",
        ) as update, patch.object(
            password_routes,
            "clear_password_reset_request",
        ), patch.object(password_routes, "record_security_event"):
            response = password_client().post(
                "/auth/password-reset",
                json={
                    "access_token": "provider-token",
                    "password": "strong-password",
                    "request_token": "n" * 32,
                },
            )

        self.assertEqual(response.status_code, 200)
        claim.assert_called_once_with("auth-1", "n" * 32)
        update.assert_called_once_with("auth-1", {"password": "strong-password"})
        finish.assert_called_once_with("request-1", succeeded=True)

    def test_provider_failure_revokes_claim_and_returns_dependency_unavailable(self):
        provider = SimpleNamespace(user=confirmed_auth_user())
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes.supabase.auth,
            "get_user",
            return_value=provider,
        ), patch.object(
            password_routes,
            "get_local_user_by_auth_id",
            return_value=local_user(),
        ), patch.object(
            password_routes,
            "claim_password_reset_request",
            return_value="request-1",
        ), patch.object(
            password_routes,
            "finish_password_reset_request",
        ) as finish, patch.object(
            password_routes.admin_supabase.auth.admin,
            "update_user_by_id",
            side_effect=RuntimeError("provider unavailable"),
        ), patch.object(password_routes, "record_security_event"):
            response = password_client().post(
                "/auth/password-reset",
                json={
                    "access_token": "provider-token",
                    "password": "strong-password",
                    "request_token": "n" * 32,
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "dependency_unavailable")
        finish.assert_called_once_with("request-1", succeeded=False)

    def test_legacy_cleanup_failure_does_not_report_reset_failure(self):
        provider = SimpleNamespace(user=confirmed_auth_user())
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes.supabase.auth,
            "get_user",
            return_value=provider,
        ), patch.object(
            password_routes,
            "get_local_user_by_auth_id",
            return_value=local_user(),
        ), patch.object(
            password_routes,
            "claim_password_reset_request",
            return_value="request-1",
        ), patch.object(
            password_routes,
            "finish_password_reset_request",
        ), patch.object(
            password_routes.admin_supabase.auth.admin,
            "update_user_by_id",
        ), patch.object(
            password_routes,
            "clear_password_reset_request",
            side_effect=RuntimeError("legacy column unavailable"),
        ), patch.object(password_routes, "record_security_event"):
            response = password_client().post(
                "/auth/password-reset",
                json={
                    "access_token": "provider-token",
                    "password": "strong-password",
                    "request_token": "n" * 32,
                },
            )

        self.assertEqual(response.status_code, 200)

    def test_unverified_recovery_session_does_not_verify_or_reset_account(self):
        provider = SimpleNamespace(
            user=SimpleNamespace(
                id="auth-1",
                email="owner@example.com",
                email_confirmed_at=None,
                confirmed_at=None,
            )
        )
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes.supabase.auth,
            "get_user",
            return_value=provider,
        ), patch.object(
            password_routes.admin_supabase.auth.admin,
            "update_user_by_id",
        ) as update:
            response = password_client().post(
                "/auth/password-reset",
                json={"access_token": "provider-token", "password": "strong-password"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "email_verification_required")
        update.assert_not_called()

    def test_forgot_password_sends_only_to_matching_canonical_auth_email(self):
        reset = Mock()
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes,
            "find_auth_user_by_email",
            return_value=confirmed_auth_user(),
        ), patch.object(
            password_routes,
            "get_local_user_by_auth_id",
            return_value=local_user(email="legacy-local@example.com"),
        ), patch.object(
            password_routes,
            "create_password_reset_request",
            return_value="n" * 32,
        ), patch.object(
            password_routes.supabase.auth,
            "reset_password_email",
            reset,
        ), patch.object(password_routes, "record_security_event"):
            response = password_client().post(
                "/auth/forgot-password",
                json={"email": "Owner@Example.COM"},
                headers={"Origin": "http://127.0.0.1:3001"},
            )

        self.assertEqual(response.status_code, 200)
        reset.assert_called_once()
        self.assertEqual(reset.call_args.args[0], "owner@example.com")
        self.assertIn("request_token=", reset.call_args.kwargs["options"]["redirect_to"])
        self.assertTrue(
            reset.call_args.kwargs["options"]["redirect_to"].startswith(
                "http://127.0.0.1:3001/reset-password?"
            )
        )

    def test_forgot_password_does_not_send_without_durable_request_record(self):
        reset = Mock()
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes,
            "find_auth_user_by_email",
            return_value=confirmed_auth_user(),
        ), patch.object(
            password_routes,
            "get_local_user_by_auth_id",
            return_value=local_user(),
        ), patch.object(
            password_routes,
            "create_password_reset_request",
            return_value=None,
        ), patch.object(
            password_routes.supabase.auth,
            "reset_password_email",
            reset,
        ), patch.object(password_routes, "record_security_event"):
            response = password_client().post(
                "/auth/forgot-password",
                json={"email": "owner@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        reset.assert_not_called()

    def test_reset_without_durable_nonce_is_rejected_by_default(self):
        provider = SimpleNamespace(user=confirmed_auth_user())
        with patch.dict("os.environ", {"PASSWORD_RESET_LEGACY_LINKS_ALLOWED_UNTIL": ""}), patch.object(
            password_routes,
            "enforce_password_rate_limit",
        ), patch.object(
            password_routes.supabase.auth,
            "get_user",
            return_value=provider,
        ), patch.object(
            password_routes,
            "get_local_user_by_auth_id",
            return_value=local_user(),
        ), patch.object(
            password_routes.admin_supabase.auth.admin,
            "update_user_by_id",
        ) as update:
            response = password_client().post(
                "/auth/password-reset",
                json={"access_token": "provider-token", "password": "strong-password"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "password_reset_invalid")
        update.assert_not_called()

    def test_forgot_password_does_not_send_to_divergent_local_email(self):
        reset = Mock()
        with patch.object(password_routes, "enforce_password_rate_limit"), patch.object(
            password_routes,
            "find_auth_user_by_email",
            return_value=None,
        ), patch.object(
            password_routes.supabase.auth,
            "reset_password_email",
            reset,
        ), patch.object(password_routes, "record_security_event"):
            response = password_client().post(
                "/auth/forgot-password",
                json={"email": "unowned@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        reset.assert_not_called()

    def test_change_password_authenticates_with_provider_canonical_email(self):
        user_data = local_user(email="legacy-local@example.com")
        service = SimpleNamespace(
            auth=SimpleNamespace(admin=SimpleNamespace(update_user_by_id=Mock()))
        )
        verify = SimpleNamespace(user=confirmed_auth_user("canonical@example.com"), session=None)
        with patch.object(
            auth_routes,
            "get_authenticated_user_row",
            return_value=(confirmed_auth_user("canonical@example.com"), user_data),
        ), patch.object(auth_routes, "service_supabase", service), patch.object(
            auth_routes.supabase.auth,
            "sign_in_with_password",
            side_effect=[verify, SimpleNamespace(session=None)],
        ) as sign_in, patch.object(auth_routes, "record_security_event"), patch.object(
            auth_routes,
            "ensure_csrf_token",
            return_value="csrf",
        ):
            response = auth_client().put(
                "/auth/password/change",
                json={"current_password": "old-password", "new_password": "new-password"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sign_in.call_args_list[0].args[0]["email"], "canonical@example.com")


if __name__ == "__main__":
    unittest.main()
