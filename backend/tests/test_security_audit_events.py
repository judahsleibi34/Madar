import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routes import auth_routes, password_routes
from services import rate_limit_service


def build_auth_client():
    app = FastAPI()
    app.include_router(auth_routes.router)
    return TestClient(app)


def build_password_client():
    app = FastAPI()
    app.include_router(password_routes.router)
    return TestClient(app)


class FakeTableQuery:
    def __init__(self, data):
        self.data = data
        self.update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self.update_payload = payload
        if isinstance(self.data, dict):
            self.data.update(payload)
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeSupabaseTableClient:
    def __init__(self, data):
        self.data = data

    def table(self, _name):
        return FakeTableQuery(self.data)


class SecurityAuditEventTests(unittest.TestCase):
    def test_successful_login_records_security_audit_event(self):
        client = build_auth_client()
        auth_response = SimpleNamespace(
            user=SimpleNamespace(id="auth-1", email_confirmed_at="2026-01-01T00:00:00Z"),
            session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )
        local_user = {"id": 5, "tenant_id": 7, "email": "user@example.com", "user_type": "user"}

        with patch.object(auth_routes, "enforce_auth_rate_limit"),              patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=auth_response),              patch.object(auth_routes, "get_local_user_by_auth_id", return_value=local_user),              patch.object(auth_routes, "set_auth_cookies", return_value="csrf"),              patch.object(auth_routes, "record_security_event") as record_security_event:
            response = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})

        self.assertEqual(response.status_code, 200)
        record_security_event.assert_called_once()
        kwargs = record_security_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "auth.login_succeeded")
        self.assertEqual(kwargs["actor_user_id"], 5)
        self.assertEqual(kwargs["tenant_id"], 7)
        self.assertNotIn("password", str(kwargs["metadata"]).lower())

    def test_failed_login_records_security_audit_event_without_password(self):
        client = build_auth_client()
        audit_user = {"id": 5, "tenant_id": 7}

        with patch.object(auth_routes, "enforce_auth_rate_limit"),              patch.object(auth_routes.supabase.auth, "sign_in_with_password", side_effect=RuntimeError("bad credentials")),              patch.object(auth_routes, "get_login_audit_user", return_value=audit_user),              patch.object(auth_routes, "record_security_event") as record_security_event:
            response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong-password"})

        self.assertEqual(response.status_code, 401)
        record_security_event.assert_called_once()
        kwargs = record_security_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "auth.login_failed")
        self.assertEqual(kwargs["actor_user_id"], 5)
        self.assertNotIn("wrong-password", str(kwargs["metadata"]))
        self.assertNotIn("user@example.com", str(kwargs["metadata"]))

    def test_password_reset_request_records_audit_event(self):
        client = build_password_client()
        auth_user = SimpleNamespace(
            id="auth-1",
            email="user@example.com",
            email_confirmed_at="2026-01-01T00:00:00Z",
        )
        local_user = {
            "id": 5,
            "auth_id": "auth-1",
            "tenant_id": 7,
            "account_status": "active",
        }

        with patch.object(password_routes, "enforce_password_rate_limit"), \
             patch.object(password_routes, "find_auth_user_by_email", return_value=auth_user), \
             patch.object(password_routes, "get_local_user_by_auth_id", return_value=local_user), \
             patch.object(password_routes, "create_password_reset_request", return_value="n" * 32), \
             patch.object(password_routes.supabase.auth, "reset_password_email"), \
             patch.object(password_routes, "record_security_event") as record_security_event:
            response = client.post("/auth/forgot-password", json={"email": "user@example.com"})

        self.assertEqual(response.status_code, 200)
        record_security_event.assert_called_once()
        kwargs = record_security_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "auth.password_reset_requested")
        self.assertEqual(kwargs["actor_user_id"], 5)
        self.assertNotIn("user@example.com", str(kwargs["metadata"]))

    def test_password_reset_completion_records_audit_event(self):
        client = build_password_client()
        requested_at = datetime.now(timezone.utc).isoformat()

        with patch.object(password_routes, "enforce_password_rate_limit"),              patch.object(password_routes.supabase.auth, "get_user", return_value=SimpleNamespace(user=SimpleNamespace(id="auth-1", email_confirmed_at="2026-01-01T00:00:00Z"))),              patch.object(password_routes.admin_supabase.auth.admin, "update_user_by_id"),              patch.object(password_routes, "get_local_user_by_auth_id", return_value={"id": 5, "tenant_id": 7, "password_reset_requested_at": requested_at}),              patch.object(password_routes, "claim_password_reset_request", return_value="request-1"),              patch.object(password_routes, "finish_password_reset_request"),              patch.object(password_routes, "clear_password_reset_request"),              patch.object(password_routes, "record_security_event") as record_security_event:
            response = client.post("/auth/password-reset", json={"access_token": "reset-token", "password": "new-password123", "request_token": "n" * 32})

        self.assertEqual(response.status_code, 200)
        record_security_event.assert_called_once()
        kwargs = record_security_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "auth.password_reset_completed")
        self.assertEqual(kwargs["actor_user_id"], 5)
        self.assertNotIn("reset-token", str(kwargs["metadata"]))
        self.assertNotIn("new-password123", str(kwargs["metadata"]))

    def test_password_reset_rejects_links_older_than_ten_minutes(self):
        client = build_password_client()
        requested_at = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()

        with patch.dict("os.environ", {"PASSWORD_RESET_LEGACY_LINKS_ALLOWED_UNTIL": "2099-01-01T00:00:00Z"}),              patch.object(password_routes, "enforce_password_rate_limit"),              patch.object(password_routes.supabase.auth, "get_user", return_value=SimpleNamespace(user=SimpleNamespace(id="auth-1", email_confirmed_at="2026-01-01T00:00:00Z"))),              patch.object(password_routes.admin_supabase.auth.admin, "update_user_by_id") as update_user_by_id,              patch.object(password_routes, "get_local_user_by_auth_id", return_value={"id": 5, "tenant_id": 7, "password_reset_requested_at": requested_at}),              patch.object(password_routes, "record_security_event"):
            response = client.post("/auth/password-reset", json={"access_token": "reset-token", "password": "new-password123"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "password_reset_expired")
        update_user_by_id.assert_not_called()

    def test_password_change_records_audit_event(self):
        client = build_auth_client()
        user_data = {"id": 5, "tenant_id": 7, "email": "user@example.com", "user_type": "user"}
        fake_service = SimpleNamespace(auth=SimpleNamespace(admin=SimpleNamespace(update_user_by_id=Mock())))

        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(SimpleNamespace(id="auth-1", email="user@example.com"), user_data)),              patch.object(auth_routes, "service_supabase", fake_service),              patch.object(auth_routes.supabase.auth, "sign_in_with_password", side_effect=[SimpleNamespace(user=SimpleNamespace(id="auth-1")), SimpleNamespace(session=None)]),              patch.object(auth_routes, "ensure_csrf_token", return_value="csrf"),              patch.object(auth_routes, "record_security_event") as record_security_event:
            response = client.put(
                "/auth/password/change",
                json={"current_password": "old-password123", "new_password": "new-password123"},
            )

        self.assertEqual(response.status_code, 200)
        record_security_event.assert_called_once()
        kwargs = record_security_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "auth.password_changed")
        self.assertEqual(kwargs["actor_user_id"], 5)
        self.assertNotIn("old-password123", str(kwargs["metadata"]))
        self.assertNotIn("new-password123", str(kwargs["metadata"]))

    def test_rate_limit_violation_records_audit_event_before_429(self):
        app = FastAPI()

        @app.get("/limited")
        def limited(request: Request):
            rate_limit_service.enforce_rate_limit(
                request,
                "auth:login",
                identifier="user@example.com",
                limit=1,
                window_seconds=60,
            )
            return {"ok": True}

        class Store:
            def incr_with_ttl(self, _key, _window_seconds):
                return 2

        client = TestClient(app)
        with patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True),              patch.object(rate_limit_service, "get_rate_limit_store", return_value=Store()),              patch("services.audit_service.record_security_event") as record_security_event:
            response = client.get("/limited")

        self.assertEqual(response.status_code, 429)
        record_security_event.assert_called_once()
        kwargs = record_security_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "security.rate_limit_exceeded")
        metadata = kwargs["metadata"]
        self.assertEqual(metadata["scope"], "auth:login")
        self.assertEqual(metadata["limit"], 1)
        self.assertNotIn("user@example.com", str(metadata))


if __name__ == "__main__":
    unittest.main()
