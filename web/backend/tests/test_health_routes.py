import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import health_routes


def build_client():
    app = FastAPI()
    app.include_router(health_routes.router)
    return TestClient(app)


class HealthRouteTests(unittest.TestCase):
    def test_live_returns_ok(self):
        response = build_client().get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_version_exposes_nonsecret_release_slot_identity(self):
        with patch.dict(os.environ, {
            "MADAR_RELEASE_SHA": "a" * 40,
            "MADAR_RELEASE_SLOT": "green",
        }, clear=False):
            response = build_client().get("/health/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["release_sha"], "a" * 40)
        self.assertEqual(response.json()["release_slot"], "green")

    def test_ready_returns_ok_when_configured(self):
        client = build_client()

        with patch.object(
            health_routes,
            "get_readiness",
            return_value={
                "ready": True,
                "components": {
                    "database": "ok",
                    "redis": "ok",
                    "auth": "ok",
                    "storage": "ok",
                    "schema": "ok",
                    "admin_mfa_policy": "not_required",
                },
            },
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["ready"], True)
        self.assertIn("commercial_entitlements_enforced", response.json())

    def test_ready_returns_degraded_when_config_missing(self):
        client = build_client()

        with patch.object(
            health_routes,
            "get_readiness",
            return_value={
                "ready": False,
                "components": {
                    "database": "ok",
                    "redis": "unavailable",
                    "auth": "ok",
                    "storage": "ok",
                    "schema": "ok",
                    "admin_mfa_policy": "ok",
                },
            },
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertIs(response.json()["ready"], False)
        self.assertEqual(response.json()["components"]["redis"], "unavailable")

    def test_metrics_endpoint_is_hidden_when_token_is_wrong(self):
        client = build_client()
        with patch.dict("os.environ", {"METRICS_TOKEN": "correct-token"}, clear=False):
            response = client.get("/health/metrics", headers={"Authorization": "Bearer wrong-token"})
        self.assertEqual(response.status_code, 404)

    def test_metrics_endpoint_returns_prometheus_with_token(self):
        client = build_client()
        with patch.dict("os.environ", {"METRICS_TOKEN": "correct-token"}, clear=False), patch.object(
            health_routes, "prometheus_metrics", return_value="madar_http_requests_total 1\n"
        ):
            response = client.get("/health/metrics", headers={"Authorization": "Bearer correct-token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("madar_http_requests_total", response.text)


if __name__ == "__main__":
    unittest.main()
