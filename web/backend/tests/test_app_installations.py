from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import installation_routes
from services import installation_service


class Response:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class RpcClient:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return Response(self.data)


class FailingRpcClient:
    def __init__(self, error):
        self.error = error

    def rpc(self, _name, _payload):
        class Failure:
            def __init__(self, error):
                self.error = error

            def execute(self):
                raise self.error

        return Failure(self.error)


class FakeApiError(Exception):
    def __init__(self, *, message, code="P0001"):
        super().__init__("redacted test database error")
        self.message = message
        self.code = code


class TableQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.null_filters = []
        self.in_filters = []
        self.values = None

    def select(self, *_args): return self
    def eq(self, field, value): self.filters.append((field, value)); return self
    def is_(self, field, value): self.null_filters.append((field, value)); return self
    def in_(self, field, values): self.in_filters.append((field, set(values))); return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, *_args): return self
    def update(self, values): self.values = values; return self

    def execute(self):
        rows = [
            row for row in self.client.tables.get(self.table, [])
            if all(row.get(field) == value for field, value in self.filters)
            and all((row.get(field) is None) == (value == "null") for field, value in self.null_filters)
            and all(row.get(field) in values for field, values in self.in_filters)
        ]
        if self.values is not None:
            for row in rows:
                row.update(self.values)
        return Response([dict(row) for row in rows])


class TableClient:
    def __init__(self, installations=None, subscriptions=None):
        self.tables = {
            "app_installations": installations or [],
            "web_push_subscriptions": subscriptions or [],
        }

    def table(self, name):
        return TableQuery(self, name)


class AppInstallationTests(unittest.TestCase):
    INSTALLATION_ID = "123e4567-e89b-42d3-a456-426614174000"
    SERVER_ID = "223e4567-e89b-42d3-a456-426614174000"

    @staticmethod
    def repository_root() -> Path:
        local = Path(__file__).resolve().parents[2]
        return local if (local / "database/migrations").is_dir() else Path("/workspace")

    def test_registration_uses_authoritative_user_and_tenant(self):
        app = FastAPI()
        app.include_router(installation_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(user_id=7, tenant_id=22)
        saved = {
            "installation_id": self.INSTALLATION_ID,
            "display_mode": "browser",
            "installed_confirmed_at": None,
            "revoked_at": None,
        }
        payload = {
            "installation_id": self.INSTALLATION_ID,
            "platform": "linux",
            "display_mode": "browser",
            "notification_permission": "default",
            "installed_confirmed": False,
            "user_id": 999,
            "tenant_id": 999,
        }
        with patch.object(installation_routes, "get_current_tenant_context", return_value=context), patch.object(installation_routes, "register_installation", return_value=saved) as register:
            response = client.post("/installations/register", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(register.call_args.kwargs["user_id"], 7)
        self.assertEqual(register.call_args.kwargs["tenant_id"], 22)

    def test_invalid_installation_ids_fail_validation(self):
        app = FastAPI()
        app.include_router(installation_routes.router)
        client = TestClient(app)
        for value in ("", "not-a-uuid", "x" * 500):
            with self.subTest(value=value):
                response = client.post("/installations/register", json={"installation_id": value})
                self.assertEqual(response.status_code, 422)

    def test_standard_registration_does_not_reactivate_revoked_installation(self):
        app = FastAPI()
        app.include_router(installation_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(user_id=7, tenant_id=22)
        revoked = {"installation_id": self.INSTALLATION_ID, "revoked_at": "2026-08-11T00:00:00Z"}
        with patch.object(installation_routes, "get_current_tenant_context", return_value=context), patch.object(installation_routes, "register_installation", return_value=revoked):
            response = client.post("/installations/register", json={"installation_id": self.INSTALLATION_ID})
        self.assertEqual(response.status_code, 409)

    def test_service_registration_is_rpc_backed_and_idempotent_by_identity(self):
        row = {"id": "server-installation", "installation_id": self.INSTALLATION_ID}
        client = RpcClient([row])
        with patch.object(installation_service, "service_supabase", client):
            first = installation_service.register_installation(
                user_id=7, tenant_id=22, installation_id=self.INSTALLATION_ID,
                platform="linux", display_mode="browser",
                notification_permission="default", installed_confirmed=False,
            )
            second = installation_service.register_installation(
                user_id=7, tenant_id=22, installation_id=self.INSTALLATION_ID,
                platform="linux", display_mode="standalone",
                notification_permission="granted", installed_confirmed=True,
            )
        self.assertEqual(first["id"], second["id"])
        self.assertEqual([call[0] for call in client.calls], ["register_app_installation"] * 2)
        self.assertEqual(client.calls[0][1]["p_user_id"], 7)

    def test_push_binding_resolves_client_id_under_authenticated_user(self):
        client = RpcClient([{"id": "subscription"}])
        with patch.object(installation_service, "service_supabase", client):
            installation_service.bind_push_subscription(
                user_id=8, tenant_id=30, installation_id=self.INSTALLATION_ID,
                endpoint="https://push.example/send", p256dh="key", auth="auth",
            )
        name, payload = client.calls[0]
        self.assertEqual(name, "bind_web_push_subscription_to_installation")
        self.assertEqual(payload["p_user_id"], 8)
        self.assertNotIn("p_app_installation_id", payload)

    def test_push_binding_maps_expected_rpc_states_without_exposing_database_details(self):
        cases = (
            ("active_tenant_membership_required", 403, "active_tenant_membership_required"),
            ("app_installation_not_available", 409, "installation_unavailable"),
            ("unexpected_internal_detail", 503, "push_subscription_unavailable"),
        )
        for message, status, code in cases:
            error = FakeApiError(message=message)
            with self.subTest(message=message), patch.object(
                installation_service, "APIError", FakeApiError
            ), patch.object(
                installation_service,
                "service_supabase",
                FailingRpcClient(error),
            ), self.assertLogs(installation_service.logger, level="WARNING") as captured:
                with self.assertRaises(installation_service.PushSubscriptionBindingError) as raised:
                    installation_service.bind_push_subscription(
                        user_id=8,
                        tenant_id=30,
                        installation_id=self.INSTALLATION_ID,
                        endpoint="https://push.example/send",
                        p256dh="key",
                        auth="auth",
                    )
            self.assertEqual(raised.exception.status_code, status)
            self.assertEqual(raised.exception.code, code)
            self.assertNotIn(message, " ".join(captured.output))

    def test_migration_defines_shared_browser_and_legacy_compatibility_invariants(self):
        root = self.repository_root()
        sql = (root / "database/migrations/074_create_app_installations.sql").read_text()
        normalized = " ".join(sql.lower().split())
        self.assertIn("unique (user_id, installation_id)", normalized)
        self.assertNotIn("unique (installation_id)", normalized)
        self.assertIn("add column if not exists app_installation_id uuid", normalized)
        self.assertIn("subscription.app_installation_id is null or", normalized)
        self.assertIn("installation.revoked_at is null", normalized)
        self.assertIn("installation.notifications_enabled = true", normalized)
        self.assertIn("enable row level security", normalized)
        self.assertIn("revoke all on public.app_installations from anon, authenticated", normalized)

    def test_schema_093_qualifies_pgcrypto_without_widening_definer_search_path(self):
        root = self.repository_root()
        sql = (
            root / "database/migrations/093_harden_public_ownership_and_web_push.sql"
        ).read_text()
        mirrored = (
            root / "supabase/migrations/093_harden_public_ownership_and_web_push.sql"
        ).read_text()
        normalized = " ".join(sql.lower().split())
        self.assertEqual(sql, mirrored)
        self.assertIn("extensions.digest(existing_subscription.endpoint", normalized)
        self.assertIn("security definer set search_path = public", normalized)
        self.assertNotIn("set search_path = public, extensions", normalized)
        self.assertIn(
            "revoke all on function public.bind_web_push_subscription_to_installation",
            normalized,
        )

    def test_list_route_is_authenticated_user_scoped_and_marks_current(self):
        app = FastAPI()
        app.include_router(installation_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(user_id=7, tenant_id=22)
        rows = [{"id": self.SERVER_ID, "is_current": True}]
        with patch.object(installation_routes, "get_current_tenant_context", return_value=context), patch.object(installation_routes, "list_user_installations", return_value=rows) as listing:
            response = client.get(f"/installations?current_installation_id={self.INSTALLATION_ID}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["installations"], rows)
        listing.assert_called_once_with(user_id=7, current_installation_id=self.INSTALLATION_ID)

    def test_revoke_route_derives_owner_and_hides_foreign_device(self):
        app = FastAPI()
        app.include_router(installation_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(user_id=7, tenant_id=22)
        with patch.object(installation_routes, "get_current_tenant_context", return_value=context), patch.object(installation_routes, "revoke_user_installation", return_value=None) as revoke:
            response = client.delete(f"/installations/{self.SERVER_ID}")
        self.assertEqual(response.status_code, 404)
        revoke.assert_called_once_with(user_id=7, installation_record_id=self.SERVER_ID)

    def test_revoke_is_device_scoped_and_preserves_sibling(self):
        installation_a = {"id": self.SERVER_ID, "installation_id": self.INSTALLATION_ID, "user_id": 7, "revoked_at": None, "notifications_enabled": True}
        installation_b = {"id": "323e4567-e89b-42d3-a456-426614174000", "installation_id": "423e4567-e89b-42d3-a456-426614174000", "user_id": 7, "revoked_at": None, "notifications_enabled": True}
        subscription_a = {"id": "push-a", "app_installation_id": installation_a["id"], "revoked_at": None}
        subscription_b = {"id": "push-b", "app_installation_id": installation_b["id"], "revoked_at": None}
        client = TableClient([installation_a, installation_b], [subscription_a, subscription_b])
        with patch.object(installation_service, "service_supabase", client):
            result = installation_service.revoke_user_installation(user_id=7, installation_record_id=installation_a["id"])
        self.assertIsNotNone(result)
        self.assertIsNotNone(installation_a["revoked_at"])
        self.assertFalse(installation_a["notifications_enabled"])
        self.assertIsNotNone(subscription_a["revoked_at"])
        self.assertIsNone(installation_b["revoked_at"])
        self.assertTrue(installation_b["notifications_enabled"])
        self.assertIsNone(subscription_b["revoked_at"])

    def test_same_client_uuid_under_other_user_cannot_be_revoked(self):
        foreign = {"id": self.SERVER_ID, "installation_id": self.INSTALLATION_ID, "user_id": 8, "revoked_at": None, "notifications_enabled": True}
        client = TableClient([foreign], [])
        with patch.object(installation_service, "service_supabase", client):
            result = installation_service.revoke_user_installation(user_id=7, installation_record_id=self.SERVER_ID)
        self.assertIsNone(result)
        self.assertIsNone(foreign["revoked_at"])

    def test_list_omits_client_uuid_and_foreign_installations(self):
        own = {"id": self.SERVER_ID, "installation_id": self.INSTALLATION_ID, "user_id": 7, "platform": "linux", "display_mode": "browser", "notification_permission": "granted", "notifications_enabled": True, "revoked_at": None}
        foreign = {**own, "id": "323e4567-e89b-42d3-a456-426614174000", "user_id": 8}
        subscription = {"app_installation_id": self.SERVER_ID, "revoked_at": None}
        client = TableClient([own, foreign], [subscription])
        with patch.object(installation_service, "service_supabase", client):
            rows = installation_service.list_user_installations(user_id=7, current_installation_id=self.INSTALLATION_ID)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["is_current"])
        self.assertTrue(rows[0]["has_active_push_subscription"])
        self.assertNotIn("installation_id", rows[0])

    def test_disable_notifications_only_affects_current_user_installation(self):
        own = {"id": self.SERVER_ID, "installation_id": self.INSTALLATION_ID, "user_id": 7, "revoked_at": None, "notifications_enabled": True}
        sibling = {"id": "323e4567-e89b-42d3-a456-426614174000", "installation_id": "423e4567-e89b-42d3-a456-426614174000", "user_id": 7, "revoked_at": None, "notifications_enabled": True}
        subscriptions = [
            {"id": "a", "app_installation_id": own["id"], "revoked_at": None},
            {"id": "b", "app_installation_id": sibling["id"], "revoked_at": None},
        ]
        client = TableClient([own, sibling], subscriptions)
        with patch.object(installation_service, "service_supabase", client):
            result = installation_service.disable_installation_notifications(user_id=7, installation_id=self.INSTALLATION_ID)
        self.assertIsNotNone(result)
        self.assertFalse(own["notifications_enabled"])
        self.assertTrue(sibling["notifications_enabled"])
        self.assertIsNotNone(subscriptions[0]["revoked_at"])
        self.assertIsNone(subscriptions[1]["revoked_at"])


if __name__ == "__main__":
    unittest.main()
