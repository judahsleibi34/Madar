import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from app import app


class AppMiddlewareTests(unittest.TestCase):
    def test_gzip_middleware_is_registered(self):
        gzip_middlewares = [
            middleware
            for middleware in app.user_middleware
            if middleware.cls is GZipMiddleware
        ]

        self.assertTrue(gzip_middlewares)
        self.assertEqual(gzip_middlewares[0].kwargs.get("minimum_size"), 1000)

    def test_request_correlation_is_validated_and_returned(self):
        response = TestClient(app).get("/", headers={"X-Request-ID": "unsafe id containing spaces"})
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.headers["X-Request-ID"], r"^[a-f0-9]{32}$")

    def test_unhandled_exception_returns_sanitized_json_with_cors_and_request_id(self):
        async def explode():
            raise RuntimeError("private database detail")

        app.add_api_route("/__test_unhandled", explode, methods=["GET"])
        try:
            with patch("app.logger.error") as logged:
                response = TestClient(app, raise_server_exceptions=False).get(
                    "/__test_unhandled",
                    headers={"Origin": "http://localhost:3000", "X-Request-ID": "request-1234"},
                )
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json(), {
                "error": "internal_server_error",
                "message": "An unexpected server error occurred.",
                "request_id": "request-1234",
            })
            self.assertEqual(response.headers["X-Request-ID"], "request-1234")
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:3000")
            self.assertNotIn("private database detail", response.text)
            logged.assert_called_once()
        finally:
            app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", "") != "/__test_unhandled"]

    def test_http_exception_contract_is_unchanged(self):
        async def expected_error():
            raise HTTPException(status_code=409, detail="expected conflict")

        app.add_api_route("/__test_http_exception", expected_error, methods=["GET"])
        try:
            response = TestClient(app, raise_server_exceptions=False).get("/__test_http_exception")
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json(), {"detail": "expected conflict"})
        finally:
            app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", "") != "/__test_http_exception"]


if __name__ == "__main__":
    unittest.main()
