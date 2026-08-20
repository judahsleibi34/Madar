import unittest
from unittest.mock import patch

from services.frontend_url import resolve_frontend_url, resolve_frontend_url_for_request


class FrontendUrlTests(unittest.TestCase):
    def test_resolve_frontend_url_prefers_explicit_frontend_url(self):
        with patch.dict(
            "os.environ",
            {
                "FRONTEND_URL": "https://madar.example.com/",
                "FRONTEND_URLS": "http://localhost:5173,https://fallback.example.com",
            },
            clear=False,
        ):
            self.assertEqual(resolve_frontend_url(), "https://madar.example.com")

    def test_resolve_frontend_url_skips_localhost_when_public_url_exists(self):
        with patch.dict(
            "os.environ",
            {
                "FRONTEND_URL": "",
                "FRONTEND_URLS": (
                    "http://localhost:3000,http://localhost:5173,"
                    "https://madar.example.com"
                ),
            },
            clear=False,
        ):
            self.assertEqual(resolve_frontend_url(), "https://madar.example.com")

    def test_resolve_frontend_url_allows_localhost_for_development(self):
        with patch.dict(
            "os.environ",
            {
                "FRONTEND_URL": "",
                "FRONTEND_URLS": "http://localhost:5173",
            },
            clear=False,
        ):
            self.assertEqual(resolve_frontend_url(), "http://localhost:5173")

    def test_request_origin_uses_exact_allowlisted_development_frontend(self):
        with patch.dict(
            "os.environ",
            {
                "FRONTEND_URL": "https://madarportal.com",
                "FRONTEND_URLS": "http://127.0.0.1:3001,http://localhost:3001",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_frontend_url_for_request("http://127.0.0.1:3001"),
                "http://127.0.0.1:3001",
            )

    def test_untrusted_request_origin_falls_back_to_canonical_frontend(self):
        with patch.dict(
            "os.environ",
            {
                "FRONTEND_URL": "https://madarportal.com",
                "FRONTEND_URLS": "http://127.0.0.1:3001,http://localhost:3001",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_frontend_url_for_request("https://evil.example"),
                "https://madarportal.com",
            )
