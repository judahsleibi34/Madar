import os
import unittest
from unittest.mock import patch

from services.runtime_config import redacted_configuration_inventory, validate_runtime_configuration


class RuntimeConfigurationTests(unittest.TestCase):
    def test_development_accepts_optional_provider_absence(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            config = validate_runtime_configuration()
        self.assertFalse(config.email_channel_enabled)

    def test_production_requires_security_controls_without_printing_values(self):
        environment = {
            "APP_ENV": "production", "SUPABASE_URL": "https://example.invalid",
            "SUPABASE_ANON_KEY": "anon", "SUPABASE_SERVICE_KEY": "service-secret-value",
            "CSRF_SECRET": "x" * 40, "FRONTEND_URLS": "https://app.example",
            "REDIS_URL": "redis://redis:6379/0", "COOKIE_SECURE": "true",
            "RATE_LIMIT_FAIL_OPEN": "false", "ADMIN_MFA_LOGIN_ENFORCEMENT": "true",
            "MADAR_RELEASE_SHA": "a" * 40,
        }
        with patch.dict(os.environ, environment, clear=True):
            config = validate_runtime_configuration()
            inventory = redacted_configuration_inventory()
        self.assertEqual(config.release_sha, "a" * 40)
        self.assertNotIn("service-secret-value", str(inventory))

    def test_enabled_email_without_smtp_fails_startup(self):
        environment = {
            "APP_ENV": "production", "SUPABASE_URL": "https://example.invalid",
            "SUPABASE_ANON_KEY": "anon", "SUPABASE_SERVICE_KEY": "secret",
            "CSRF_SECRET": "x" * 40, "FRONTEND_URLS": "https://app.example",
            "REDIS_URL": "redis://redis:6379/0", "COOKIE_SECURE": "true",
            "RATE_LIMIT_FAIL_OPEN": "false", "ADMIN_MFA_LOGIN_ENFORCEMENT": "true",
            "MADAR_RELEASE_SHA": "a" * 40, "EMAIL_CHANNEL_ENABLED": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SMTP"):
                validate_runtime_configuration()

    def test_observed_inventory_marks_unclassified_keys_unknown_without_values(self):
        with patch.dict(os.environ, {"UNCLASSIFIED_FIXTURE": "private-value"}, clear=True):
            inventory = redacted_configuration_inventory({"UNCLASSIFIED_FIXTURE"})
        row = next(item for item in inventory if item["name"] == "UNCLASSIFIED_FIXTURE")
        self.assertEqual(row["classification"], "unknown")
        self.assertTrue(row["configured"])
        self.assertNotIn("private-value", str(inventory))

    def test_production_rejects_unsafe_origin_rate_limit_and_remote_ingestion(self):
        base = {
            "APP_ENV": "production", "SUPABASE_URL": "https://example.invalid",
            "SUPABASE_ANON_KEY": "anon", "SUPABASE_SERVICE_KEY": "service",
            "CSRF_SECRET": "x" * 40, "FRONTEND_URLS": "https://app.example",
            "REDIS_URL": "redis://redis:6379/0", "COOKIE_SECURE": "true",
            "RATE_LIMIT_ENABLED": "true", "RATE_LIMIT_FAIL_OPEN": "false",
            "ADMIN_MFA_LOGIN_ENFORCEMENT": "true", "MADAR_RELEASE_SHA": "a" * 40,
        }
        for changes, message in (
            ({"FRONTEND_URLS": "*"}, "origin"),
            ({"RATE_LIMIT_ENABLED": "false"}, "rate limiting"),
            ({"ALLOW_REMOTE_DATASET_URLS": "true"}, "isolated worker"),
        ):
            with self.subTest(changes=changes), patch.dict(os.environ, {**base, **changes}, clear=True):
                with self.assertRaisesRegex(RuntimeError, message):
                    validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
