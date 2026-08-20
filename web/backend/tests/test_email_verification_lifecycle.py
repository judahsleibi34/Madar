import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import auth_routes
from services.pending_verification_context import (
    create_pending_verification_value,
    read_pending_verification_value,
)


def build_client():
    app = FastAPI()
    app.include_router(auth_routes.router)
    return TestClient(app)


def pending_user():
    return {
        "id": 7,
        "auth_id": "auth-7",
        "tenant_id": None,
        "email": "owner@example.com",
        "email_verified": False,
        "account_status": "pending_verification",
        "email_verification_sent_at": None,
    }


def provider_user(*, verified=False):
    return SimpleNamespace(
        id="auth-7",
        email="owner@example.com",
        email_confirmed_at="2026-01-01T00:00:00Z" if verified else None,
        confirmed_at=None,
    )


class PendingVerificationContextTests(unittest.TestCase):
    def test_signed_context_round_trips_and_rejects_tampering(self):
        token = create_pending_verification_value(auth_id="auth-7", user_id=7, now=100)
        payload = read_pending_verification_value(token, now=101)

        self.assertEqual(payload["auth_id"], "auth-7")
        self.assertEqual(payload["user_id"], 7)
        self.assertIsNone(read_pending_verification_value(token + "tampered", now=101))
        self.assertIsNone(read_pending_verification_value(token, now=10**10))


class EmailVerificationRouteTests(unittest.TestCase):
    def test_status_without_signed_context_does_not_enumerate(self):
        response = build_client().get("/auth/email-verification/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "unknown")

    def test_pending_context_returns_masked_status(self):
        client = build_client()
        with patch.object(
            auth_routes,
            "read_pending_verification_context",
            return_value={"auth_id": "auth-7", "user_id": 7},
        ), patch.object(
            auth_routes,
            "get_auth_user_by_id",
            return_value=provider_user(verified=False),
        ), patch.object(
            auth_routes,
            "get_local_user_by_auth_id",
            return_value=pending_user(),
        ):
            response = client.get("/auth/email-verification/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "pending")
        self.assertEqual(response.json()["masked_email"], "o****@example.com")
        self.assertNotIn("owner@example.com", response.text)

    def test_provider_bearer_confirmation_activates_once(self):
        client = build_client()
        active = {**pending_user(), "tenant_id": 3, "account_status": "active", "email_verified": True}
        with patch.object(
            auth_routes.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(user=provider_user(verified=True)),
        ), patch.object(
            auth_routes,
            "get_local_user_by_auth_id",
            return_value=pending_user(),
        ), patch.object(
            auth_routes,
            "synchronize_verified_account",
            return_value=(active, True),
        ) as synchronize, patch.object(
            auth_routes,
            "delete_pending_verification_cookie",
        ), patch.object(
            auth_routes,
            "record_security_event",
        ) as audit, patch.object(
            auth_routes,
            "record_verification_result",
        ) as verification_record:
            response = client.get(
                "/auth/email-verification/status",
                headers={"Authorization": "Bearer provider-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "verified")
        self.assertEqual(response.json()["account_status"], "active")
        synchronize.assert_called_once()
        verification_record.assert_called_once()
        self.assertEqual(audit.call_args.kwargs["action"], "auth.email_verification_succeeded")

    def test_unknown_resend_has_same_generic_response_without_delivery(self):
        client = build_client()
        with patch.object(auth_routes, "enforce_auth_rate_limit"), patch.object(
            auth_routes,
            "read_pending_verification_context",
            return_value=None,
        ), patch.object(
            auth_routes,
            "get_local_user_by_email",
            return_value=None,
        ), patch.object(auth_routes, "send_verification_email") as send:
            response = client.post(
                "/auth/email-verification/resend",
                json={"email": "unknown@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], auth_routes.GENERIC_RESEND_MESSAGE)
        self.assertEqual(response.json()["state"], "pending")
        send.assert_not_called()

    def test_signed_context_resend_reports_cooldown_without_email(self):
        client = build_client()
        with patch.object(auth_routes, "enforce_auth_rate_limit"), patch.object(
            auth_routes,
            "read_pending_verification_context",
            return_value={"auth_id": "auth-7", "user_id": 7},
        ), patch.object(
            auth_routes,
            "get_local_user_by_auth_id",
            return_value=pending_user(),
        ), patch.object(
            auth_routes,
            "get_auth_user_by_id",
            return_value=provider_user(verified=False),
        ), patch.object(
            auth_routes,
            "send_verification_email",
            return_value={
                "sent": False,
                "limited": True,
                "failure_code": "email_verification_resend_limited",
                "retry_after": 42,
            },
        ), patch.object(auth_routes, "record_security_event"):
            response = client.post("/auth/email-verification/resend", json={})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.json()["detail"]["code"],
            "email_verification_resend_limited",
        )
        self.assertEqual(
            response.json()["detail"]["context"]["resend_available_after"],
            42,
        )
        self.assertNotIn("owner@example.com", response.text)

    def test_clear_context_only_deletes_pending_cookie(self):
        client = build_client()
        with patch.object(
            auth_routes,
            "delete_pending_verification_cookie",
        ) as delete_cookie:
            response = client.post("/auth/email-verification/clear-context", json={})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        delete_cookie.assert_called_once()


if __name__ == "__main__":
    unittest.main()
