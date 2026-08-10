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


class AppInstallationTests(unittest.TestCase):
    INSTALLATION_ID = "123e4567-e89b-42d3-a456-426614174000"

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


if __name__ == "__main__":
    unittest.main()
