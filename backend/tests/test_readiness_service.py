import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import readiness_service


class ReadinessServiceTests(unittest.TestCase):
    def tearDown(self):
        readiness_service.clear_readiness_cache()

    def test_generated_execution_requires_isolated_worker(self):
        with patch.dict("os.environ", {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "false"}, clear=False):
            self.assertEqual(readiness_service.check_ai_execution_guard(), "insecure")
        with patch.dict("os.environ", {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            self.assertEqual(readiness_service.check_ai_execution_guard(), "ok")

    def test_remote_ingestion_requires_enforced_egress(self):
        with patch.dict("os.environ", {"ALLOW_REMOTE_DATASET_URLS": "true", "REMOTE_INGESTION_EGRESS_ENFORCED": "false"}, clear=False):
            self.assertEqual(readiness_service.check_remote_ingestion_guard(), "insecure")

    def test_production_parser_stays_gated_until_isolated(self):
        with patch.dict("os.environ", {"APP_ENV": "production"}, clear=False):
            self.assertEqual(readiness_service.check_parser_isolation(), "in_process")

    def test_all_required_components_ready(self):
        with patch.object(readiness_service, "check_database", return_value="ok"), patch.object(
            readiness_service, "check_redis", return_value="ok"
        ), patch.object(readiness_service, "check_auth", return_value="ok"), patch.object(
            readiness_service, "check_storage", return_value="ok"
        ), patch.object(readiness_service, "check_schema", return_value="ok"):
            with patch.object(
                readiness_service,
                "check_admin_mfa_policy",
                return_value="not_required",
            ), patch.object(
                readiness_service, "check_ai_execution_guard", return_value="disabled"
            ), patch.object(
                readiness_service, "check_remote_ingestion_guard", return_value="disabled"
            ):
                result = readiness_service.get_readiness(use_cache=False)

        self.assertIs(result["ready"], True)

    def test_required_component_outage_fails_readiness(self):
        with patch.object(readiness_service, "check_database", return_value="ok"), patch.object(
            readiness_service, "check_redis", return_value="unavailable"
        ), patch.object(readiness_service, "check_auth", return_value="ok"), patch.object(
            readiness_service, "check_storage", return_value="ok"
        ), patch.object(readiness_service, "check_schema", return_value="ok"):
            with patch.object(readiness_service, "check_admin_mfa_policy", return_value="ok"), patch.object(
                readiness_service, "check_ai_execution_guard", return_value="disabled"
            ), patch.object(
                readiness_service, "check_remote_ingestion_guard", return_value="disabled"
            ):
                result = readiness_service.get_readiness(use_cache=False)

        self.assertIs(result["ready"], False)

    def test_explicit_optional_redis_outage_is_ready(self):
        with patch.object(readiness_service, "check_database", return_value="ok"), patch.object(
            readiness_service, "check_redis", return_value="optional_unavailable"
        ), patch.object(readiness_service, "check_auth", return_value="ok"), patch.object(
            readiness_service, "check_storage", return_value="ok"
        ), patch.object(readiness_service, "check_schema", return_value="ok"):
            with patch.object(readiness_service, "check_admin_mfa_policy", return_value="ok"), patch.object(
                readiness_service, "check_ai_execution_guard", return_value="disabled"
            ), patch.object(
                readiness_service, "check_remote_ingestion_guard", return_value="disabled"
            ):
                result = readiness_service.get_readiness(use_cache=False)

        self.assertIs(result["ready"], True)

    def test_missing_schema_fails_readiness_without_details(self):
        with patch.object(readiness_service, "check_database", return_value="ok"), patch.object(
            readiness_service, "check_redis", return_value="ok"
        ), patch.object(readiness_service, "check_auth", return_value="ok"), patch.object(
            readiness_service, "check_storage", return_value="ok"
        ), patch.object(readiness_service, "check_schema", return_value="missing"):
            with patch.object(readiness_service, "check_admin_mfa_policy", return_value="ok"):
                result = readiness_service.get_readiness(use_cache=False)

        self.assertEqual(result["components"]["schema"], "missing")
        self.assertNotIn("error", result)
        self.assertIs(result["ready"], False)

    def test_insecure_production_admin_mfa_policy_fails_readiness(self):
        with patch.object(readiness_service, "check_database", return_value="ok"), patch.object(
            readiness_service, "check_redis", return_value="ok"
        ), patch.object(readiness_service, "check_auth", return_value="ok"), patch.object(
            readiness_service, "check_storage", return_value="ok"
        ), patch.object(readiness_service, "check_schema", return_value="ok"), patch.object(
            readiness_service, "check_admin_mfa_policy", return_value="insecure"
        ):
            result = readiness_service.get_readiness(use_cache=False)

        self.assertIs(result["ready"], False)
        self.assertEqual(result["components"]["admin_mfa_policy"], "insecure")

    def test_production_rate_limiting_cannot_be_disabled_or_fail_open(self):
        for override in (
            {"APP_ENV": "production", "RATE_LIMIT_ENABLED": "false"},
            {
                "APP_ENV": "production",
                "RATE_LIMIT_ENABLED": "true",
                "RATE_LIMIT_FAIL_OPEN": "true",
            },
        ):
            with self.subTest(override=override), patch.dict(
                "os.environ", override, clear=False
            ):
                self.assertEqual(readiness_service.check_redis(), "insecure")

    def test_service_key_probe_rejects_redirects_without_following_them(self):
        with patch.dict(
            "os.environ",
            {"SUPABASE_URL": "https://supabase.example", "SUPABASE_SERVICE_KEY": "secret"},
            clear=False,
        ), patch.object(
            readiness_service.requests,
            "get",
            return_value=SimpleNamespace(status_code=302),
        ) as get:
            self.assertEqual(readiness_service.check_database(), "unavailable")

        self.assertIs(get.call_args.kwargs["allow_redirects"], False)


if __name__ == "__main__":
    unittest.main()
