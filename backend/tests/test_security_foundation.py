import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services import rate_limit_service
from services.rate_limit_service import InMemoryRateLimitStore, enforce_rate_limit
from services.request_security import get_allowed_origins, validate_cookie_write_origin


class SecurityFoundationTests(unittest.TestCase):
    def setUp(self):
        rate_limit_service._store = None
        rate_limit_service._memory_store = InMemoryRateLimitStore()

    def tearDown(self):
        rate_limit_service._store = None
        rate_limit_service._memory_store = InMemoryRateLimitStore()

    def build_origin_client(self):
        app = FastAPI()
        allowed_origins = get_allowed_origins(["https://app.example.com"])

        @app.middleware("http")
        async def csrf_middleware(request: Request, call_next):
            blocked_response = validate_cookie_write_origin(request, allowed_origins)
            if blocked_response is not None:
                return blocked_response
            return await call_next(request)

        @app.post("/protected-write")
        def protected_write():
            return {"ok": True}

        return TestClient(app)

    def test_invalid_origin_rejected_for_cookie_authenticated_write(self):
        client = self.build_origin_client()

        response = client.post(
            "/protected-write",
            headers={"Origin": "https://evil.example.com"},
            cookies={"madar_access_token": "token"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid request origin")

    def test_valid_origin_accepted_for_cookie_authenticated_write(self):
        client = self.build_origin_client()

        response = client.post(
            "/protected-write",
            headers={"Origin": "https://app.example.com"},
            cookies={"madar_access_token": "token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_rate_limit_rejects_after_limit(self):
        app = FastAPI()
        store = InMemoryRateLimitStore()

        @app.post("/limited")
        def limited(request: Request):
            enforce_rate_limit(
                request,
                "test",
                identifier="user@example.com",
                limit=2,
                window_seconds=60,
            )
            return {"ok": True}

        client = TestClient(app)

        with patch.object(rate_limit_service, "_store", store),              patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True):
            self.assertEqual(client.post("/limited").status_code, 200)
            self.assertEqual(client.post("/limited").status_code, 200)
            response = client.post("/limited")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many requests. Please try again later.")


if __name__ == "__main__":
    unittest.main()
