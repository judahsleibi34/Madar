import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient

from app import app


class AppMiddlewareTests(unittest.TestCase):
    @contextmanager
    def cors_origins(self, origins):
        middleware = next(item for item in app.user_middleware if item.cls.__name__ == "CORSMiddleware")
        original = list(middleware.kwargs["allow_origins"])
        middleware.kwargs["allow_origins"] = list(origins)
        app.middleware_stack = None
        try:
            yield
        finally:
            middleware.kwargs["allow_origins"] = original
            app.middleware_stack = None

    def unhandled_response(self, *, origin=None, request_id="request-1234", suffix="default"):
        async def explode():
            raise RuntimeError("private database detail")

        path = f"/__test_unhandled_{suffix}"
        app.add_api_route(path, explode, methods=["GET"])
        headers = {"X-Request-ID": request_id}
        if origin is not None:
            headers["Origin"] = origin
        try:
            with patch("app.logger.error") as logged:
                response = TestClient(app, raise_server_exceptions=False).get(path, headers=headers)
            logged.assert_called_once()
            return response
        finally:
            app.router.routes[:] = [
                route for route in app.router.routes
                if getattr(route, "path", "") != path
            ]

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
        with self.cors_origins(["http://localhost:3000"]):
            response = self.unhandled_response(origin="http://localhost:3000")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {
            "error": "internal_server_error",
            "message": "An unexpected server error occurred.",
            "request_id": "request-1234",
        })
        self.assertEqual(response.headers["X-Request-ID"], "request-1234")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        self.assertEqual(response.headers["Access-Control-Allow-Credentials"], "true")
        self.assertNotIn("private database detail", response.text)

    def test_unhandled_exception_uses_exact_canonical_origin_policy(self):
        production_origin = "https://madarportal.com"
        with self.cors_origins([production_origin]):
            allowed = self.unhandled_response(origin=production_origin, suffix="production")
            disallowed = self.unhandled_response(origin="https://attacker.invalid", suffix="disallowed")
            no_origin = self.unhandled_response(origin=None, suffix="no_origin")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), production_origin)
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertNotIn("Access-Control-Allow-Origin", disallowed.headers)
        self.assertNotIn("Access-Control-Allow-Origin", no_origin.headers)

    def test_normal_preflight_contract_is_unchanged(self):
        with self.cors_origins(["http://localhost:3000"]):
            response = TestClient(app).options(
                "/",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "X-CSRF-Token",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost:3000")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

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
