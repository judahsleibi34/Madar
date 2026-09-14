import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_production_config.py"


def load_module():
    spec = importlib.util.spec_from_file_location("production_config_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ProductionConfigValidatorTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def complete_production(self):
        return {
            "SUPABASE_URL": "https://project.supabase.co",
            "SUPABASE_ANON_KEY": "a" * 20,
            "SUPABASE_SERVICE_KEY": "s" * 20,
            "SUPABASE_DB_URL": "postgresql://db.invalid/madar",
            "VITE_API_URL": "https://api.madarportal.com",
            "PUBLIC_API_URL": "https://api.madarportal.com",
            "FRONTEND_PRIMARY_URL": "https://madarportal.com",
            "FRONTEND_URLS": "https://madarportal.com,https://www.madarportal.com",
            "MADAR_STORAGE_ROOT": "/var/lib/madar/storage",
            "COOKIE_SECURE": "true",
            "COOKIE_SAMESITE": "none",
            "CSRF_TRUSTED_ORIGINS": "https://madarportal.com",
            "CSRF_SECRET": "x" * 32,
            "MADAR_CSP_CONNECT_SRC": "https://api.madarportal.com",
            "REDIS_URL": "redis://redis:6379/0",
            "ADMIN_MFA_LOGIN_ENFORCEMENT": "true",
            "PYGWALKER_TELEMETRY_ENABLED": "false",
        }

    def complete_e2e(self):
        return {
            "TEST_USER_EMAIL": "qa@example.test",
            "TEST_USER_PASSWORD": "not-printed",
            "PUBLISHED_FORM_PATH": "/forms/fixture",
            "MADAR_E2E_CONFIRM_ISOLATED": "YES",
            "MADAR_E2E_BASE_URL": "http://127.0.0.1:18000",
            "MADAR_E2E_DATABASE_ID": "madar_e2e_fixture",
            "MADAR_E2E_RUN_ID": "fixture_20260914",
            "MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN": "YES",
            "MADAR_E2E_EXTERNAL_DELIVERY_DISABLED": "YES",
        }

    def test_complete_configuration_passes(self):
        checks = self.module.classify(self.complete_production(), self.complete_e2e())
        self.assertTrue(all(status == "PASS" for _, status in checks))

    def test_missing_and_invalid_are_distinct_and_values_are_not_printed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            production = root / "production.env"
            e2e = root / "e2e.env"
            production.write_text("SUPABASE_SERVICE_KEY=secret-do-not-print\nCOOKIE_SECURE=false\n", encoding="utf-8")
            e2e.write_text("TEST_USER_PASSWORD=another-secret\nPUBLISHED_FORM_PATH=relative\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = self.module.main(["--production-env", str(production), "--e2e-env", str(e2e)])
        rendered = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("MISSING SUPABASE_URL", rendered)
        self.assertIn("INVALID COOKIE_SECURE", rendered)
        self.assertIn("INVALID PUBLISHED_FORM_PATH", rendered)
        self.assertNotIn("secret-do-not-print", rendered)
        self.assertNotIn("another-secret", rendered)

    def test_reverse_proxy_api_origin_must_match_frontend_api_origin(self):
        production = self.complete_production()
        production["MADAR_CSP_CONNECT_SRC"] = "https://other.example.test"
        checks = dict(self.module.classify(production, self.complete_e2e()))
        self.assertEqual(checks["MADAR_CSP_CONNECT_SRC"], "INVALID")


if __name__ == "__main__":
    unittest.main()
