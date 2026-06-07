import unittest

from fastapi.middleware.gzip import GZipMiddleware

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


if __name__ == "__main__":
    unittest.main()
