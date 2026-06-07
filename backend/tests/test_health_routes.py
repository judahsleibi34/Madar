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

    def test_ready_returns_ok_when_configured(self):
        client = build_client()

        with patch.object(
            health_routes,
            "get_config_readiness",
            return_value={
                "supabase_url": True,
                "supabase_anon_key": True,
                "supabase_service_key": True,
                "service_key_is_distinct": True,
            },
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_ready_returns_degraded_when_config_missing(self):
        client = build_client()

        with patch.object(
            health_routes,
            "get_config_readiness",
            return_value={
                "supabase_url": True,
                "supabase_anon_key": True,
                "supabase_service_key": False,
                "service_key_is_distinct": False,
            },
        ):
            response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
