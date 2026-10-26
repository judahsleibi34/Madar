import os
import unittest
from unittest.mock import patch

from fastapi import Request, Response

from services import request_security


class CsrfOriginHardeningTests(unittest.TestCase):
    def request(self, headers):
        return Request({
            "type": "http", "method": "POST", "path": "/auth/refresh",
            "headers": [(key.encode(), value.encode()) for key, value in {
                "cookie": "madar_refresh_token=fixture",
                "referer": "https://app.example/dashboard?private=value",
                **headers,
            }.items()],
        })

    def test_explicit_untrusted_or_malformed_origin_never_uses_trusted_referer(self):
        origins = (
            "null", "", "https://untrusted.example", "https://[broken",
            "https://app.example:broken", "https://user:password@app.example",
            "https://app.example/path", "https://app.example?private=value",
            "https://app.example#fragment", "https://app.example\\evil",
        )
        for origin in origins:
            with self.subTest(origin=origin):
                blocked = request_security.validate_cookie_write_origin(
                    self.request({"origin": origin}), {"https://app.example"},
                )
                self.assertIsNotNone(blocked)
                self.assertEqual(blocked.status_code, 403)

    def test_absent_origin_retains_referer_compatibility(self):
        self.assertIsNone(request_security.validate_cookie_write_origin(
            self.request({}), {"https://app.example"},
        ))

    def test_valid_origin_is_accepted(self):
        self.assertIsNone(request_security.validate_cookie_write_origin(
            self.request({"origin": "https://app.example"}), {"https://app.example"},
        ))

    def test_secure_cookie_defaults_match_production_like_startup_policy(self):
        for environment, secure in (("test", False), ("development", False),
                                    ("staging", True), ("prod", True), ("production", True)):
            with self.subTest(environment=environment), patch.dict(
                os.environ, {"APP_ENV": environment}, clear=True,
            ):
                response = Response()
                request_security.set_csrf_cookie(response, "fixture")
                self.assertEqual("; Secure" in response.headers["set-cookie"], secure)

    def test_secure_cookie_boolean_spellings_match_startup_validation(self):
        for value in ("true", "1", "yes", "on", " TRUE "):
            with self.subTest(value=value), patch.dict(os.environ, {"COOKIE_SECURE": value}):
                self.assertTrue(request_security._cookie_secure())
