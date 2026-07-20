import unittest

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


if __name__ == "__main__":
    unittest.main()
