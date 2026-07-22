import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from services import calendar_sync_service
from services.calendar_sync_service import CalendarSyncError
from routes import calendar_routes


class Query:
    def __init__(self, client): self.client = client
    def insert(self, value): self.client.inserted.append(value); return self
    def update(self, value): self.client.updated.append(value); return self
    def eq(self, *_args): return self
    def execute(self): return SimpleNamespace(data=[{"id": "ok"}])


class Client:
    def __init__(self, rpc_result=True):
        self.inserted = []
        self.updated = []
        self.rpc_result = rpc_result
        self.rpc_args = None
    def table(self, _name): return Query(self)
    def rpc(self, name, args):
        self.rpc_args = (name, args)
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.rpc_result))


BASE_ENV = {
    "APP_ENV": "test",
    "CALENDAR_FEATURE_ENABLED": "true",
    "CALENDAR_CREDENTIALS_SECRET": "calendar-test-secret-that-is-not-real",
    "GOOGLE_CALENDAR_CLIENT_ID": "test-google-client",
    "GOOGLE_CALENDAR_CLIENT_SECRET": "test-google-secret",
    "MICROSOFT_CALENDAR_CLIENT_ID": "test-microsoft-client",
    "MICROSOFT_CALENDAR_CLIENT_SECRET": "test-microsoft-secret",
    "PUBLIC_API_URL": "http://127.0.0.1:8000",
    "FRONTEND_PRIMARY_URL": "http://127.0.0.1:5173",
}


class CalendarOAuthTests(unittest.TestCase):
    def connection(self, provider="google", direction="read"):
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            "local_calendar_id": "22222222-2222-2222-2222-222222222222",
            "tenant_id": 7, "user_id": 12, "provider": provider, "direction": direction,
        }

    def test_authorization_state_is_bound_expiring_and_persisted_by_hash(self):
        client = Client()
        with patch.dict(os.environ, BASE_ENV, clear=False), patch.object(
            calendar_sync_service.secrets, "token_urlsafe", return_value="deterministic-nonce"
        ):
            url = calendar_sync_service.authorization_url(self.connection(), client=client, now=1_800_000_000)
            state = parse_qs(urlparse(url).query)["state"][0]
            with patch.object(calendar_sync_service.time, "time", return_value=1_800_000_001):
                decoded = calendar_sync_service.decode_oauth_state(state)
        self.assertEqual(decoded["tenant_id"], 7)
        self.assertEqual(decoded["user_id"], 12)
        self.assertEqual(decoded["calendar_id"], self.connection()["local_calendar_id"])
        self.assertEqual(decoded["provider"], "google")
        self.assertEqual(decoded["exp"] - decoded["iat"], 600)
        self.assertNotEqual(client.inserted[0]["nonce_hash"], "deterministic-nonce")
        self.assertNotIn(state, str(client.inserted))

    def test_modified_and_expired_state_are_rejected(self):
        with patch.dict(os.environ, BASE_ENV, clear=False):
            encoded = calendar_sync_service._encode_state({
                "connection_id": "c", "calendar_id": "k", "tenant_id": 7, "user_id": 12,
                "provider": "google", "nonce": "n", "iat": 10, "exp": 20,
            })
            with patch.object(calendar_sync_service.time, "time", return_value=21), self.assertRaises(CalendarSyncError):
                calendar_sync_service.decode_oauth_state(encoded)
            with self.assertRaises(CalendarSyncError):
                calendar_sync_service.decode_oauth_state(encoded + "tampered")

    def test_state_consumption_is_atomic_and_replay_fails(self):
        payload = {
            "connection_id": "c", "calendar_id": "k", "tenant_id": 7,
            "user_id": 12, "provider": "google", "nonce": "n",
        }
        client = Client(rpc_result=True)
        calendar_sync_service.consume_oauth_state(payload, client=client)
        self.assertEqual(client.rpc_args[0], "consume_calendar_oauth_state")
        with self.assertRaisesRegex(CalendarSyncError, "already used"):
            calendar_sync_service.consume_oauth_state(payload, client=Client(rpc_result=False))

    def test_provider_scopes_are_calendar_only(self):
        for provider, expected in (("google", "calendar.readonly"), ("microsoft", "Calendars.Read")):
            with self.subTest(provider=provider), patch.dict(os.environ, BASE_ENV, clear=False):
                url = calendar_sync_service.authorization_url(self.connection(provider), client=Client(), now=1_800_000_000)
                scope = parse_qs(urlparse(url).query)["scope"][0]
                self.assertIn(expected, scope)
                self.assertNotIn("User.Read", scope)
                self.assertNotIn("contacts", scope.lower())

    def test_production_redirects_require_exact_https_origins(self):
        for value in ("", "http://localhost:8000", "https://api.example.test/path", "https://api.example.test?x=1"):
            env = {**BASE_ENV, "APP_ENV": "production", "PUBLIC_API_URL": value}
            with self.subTest(value=value), patch.dict(os.environ, env, clear=False), self.assertRaises(CalendarSyncError):
                calendar_sync_service._redirect_uri("google")
        with patch.dict(os.environ, {**BASE_ENV, "APP_ENV": "production", "PUBLIC_API_URL": "https://api.example.test"}, clear=False):
            self.assertEqual(calendar_sync_service._redirect_uri("google"), "https://api.example.test/calendar/oauth/google/callback")

    def test_token_response_is_reduced_to_required_fields(self):
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "id_token": "must-not-store", "profile": {"email": "private@example.test"}},
        )
        client = SimpleNamespace(post=lambda *_args, **_kwargs: response)
        with patch.dict(os.environ, BASE_ENV, clear=False):
            credentials = calendar_sync_service.exchange_authorization_code("google", "test-code", http_client=client)
        self.assertEqual(set(credentials), {"access_token", "refresh_token", "token_type", "scope", "expires_at"})
        self.assertNotIn("id_token", credentials)
        self.assertNotIn("profile", credentials)

    def test_callback_consumes_bound_state_before_storing_encrypted_credentials(self):
        context = SimpleNamespace(tenant_id=7, user_id=12, membership_status="active", role="member")
        connection = self.connection()
        state = {
            "connection_id": connection["id"], "calendar_id": connection["local_calendar_id"],
            "tenant_id": 7, "user_id": 12, "provider": "google", "nonce": "nonce",
        }
        client = Client()
        with patch.dict(os.environ, BASE_ENV, clear=False), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(calendar_routes, "decode_oauth_state", return_value=state), patch.object(
            calendar_routes, "tenant_connection", return_value=connection
        ), patch.object(calendar_routes, "require_calendar_access"), patch.object(
            calendar_routes, "consume_oauth_state"
        ) as consume, patch.object(
            calendar_routes, "exchange_authorization_code", return_value={"access_token": "private"}
        ), patch.object(calendar_routes, "encrypt_credentials", return_value="encrypted"), patch.object(
            calendar_routes, "service_supabase", client
        ), patch.object(calendar_routes, "record_calendar_audit"):
            response = calendar_routes.calendar_oauth_callback("google", object(), object(), code="private-code", state="private-state")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "http://127.0.0.1:5173/calendar?sync=connected")
        consume.assert_called_once_with(state)
        self.assertNotIn("private-code", str(response.headers))
        self.assertNotIn("private-state", str(response.headers))

    def test_callback_rejects_cross_tenant_state_without_exchange_or_sensitive_logging(self):
        context = SimpleNamespace(tenant_id=7, user_id=12, membership_status="active", role="member")
        state = {
            "connection_id": "connection", "calendar_id": "calendar",
            "tenant_id": 8, "user_id": 12, "provider": "google", "nonce": "private-state",
        }
        with patch.dict(os.environ, BASE_ENV, clear=False), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(calendar_routes, "decode_oauth_state", return_value=state), patch.object(
            calendar_routes, "exchange_authorization_code"
        ) as exchange, patch.object(calendar_routes.logger, "warning") as warning:
            response = calendar_routes.calendar_oauth_callback("google", object(), object(), code="private-code", state="private-state")
        self.assertEqual(response.headers["location"], "http://127.0.0.1:5173/calendar?sync=error")
        exchange.assert_not_called()
        warning.assert_called_once()
        self.assertNotIn("private-code", str(warning.call_args))
        self.assertNotIn("private-state", str(warning.call_args))

    def test_disconnect_removes_credentials_and_attempts_google_revocation(self):
        client = Client()
        provider = SimpleNamespace(post=lambda *_args, **_kwargs: SimpleNamespace(status_code=200))
        connection = {**self.connection(), "encrypted_credentials": "encrypted"}
        with patch.object(
            calendar_sync_service, "decrypt_credentials",
            return_value={"refresh_token": "private-refresh"},
        ):
            revoked = calendar_sync_service.disconnect_connection(
                connection, http_client=provider, client=client
            )
        self.assertTrue(revoked)
        self.assertIsNone(client.updated[0]["encrypted_credentials"])
        self.assertEqual(client.updated[0]["status"], "disconnected")
        self.assertNotIn("private-refresh", str(client.updated))


if __name__ == "__main__":
    unittest.main()
