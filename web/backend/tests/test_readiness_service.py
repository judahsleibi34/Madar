import unittest
import tempfile
import os
import time
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services import readiness_service


class ReadinessServiceTests(unittest.TestCase):
    def test_backup_missing_fresh_stale_and_atomic_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'latest.json'
            with patch.dict(os.environ, {'BACKUP_FRESHNESS_REQUIRED':'true', 'BACKUP_FRESHNESS_MARKER':str(marker), 'BACKUP_MAX_AGE_SECONDS':'3600'}):
                self.assertEqual(readiness_service.check_backup_freshness(), 'missing')
                now = datetime.now(timezone.utc)
                def publish(created):
                    timestamp = created.strftime('%Y%m%dT%H%M%SZ')
                    temp = marker.with_suffix('.tmp')
                    temp.write_text(json.dumps({'format':1,'verified':True,'created_at':timestamp,
                                               'backup_id':'madar-'+timestamp,'manifest_sha256':'a'*64}))
                    temp.chmod(0o644)
                    os.replace(temp, marker)
                publish(now - timedelta(days=3))
                self.assertEqual(readiness_service.check_backup_freshness(), 'stale')
                with marker.open() as old_inode:
                    publish(now)
                    self.assertNotEqual(os.fstat(old_inode.fileno()).st_ino, marker.stat().st_ino)
                    self.assertEqual(readiness_service.check_backup_freshness(), 'ok')
                marker.write_text(json.dumps({'verified':False}))
                self.assertEqual(readiness_service.check_backup_freshness(), 'invalid')

    def tearDown(self):
        readiness_service.clear_readiness_cache()

    def test_supabase_readiness_uses_apikey_only_for_opaque_server_secret(self):
        with patch.dict(
            os.environ,
            {"SUPABASE_SERVICE_KEY": "sb_secret_synthetic_fixture_not_a_credential"},
            clear=False,
        ):
            headers = readiness_service._supabase_headers()
        self.assertEqual({name.lower() for name in headers}, {"apikey"})

    def test_supabase_readiness_retains_legacy_service_role_bearer(self):
        with patch.dict(
            os.environ,
            {"SUPABASE_SERVICE_KEY": "synthetic-legacy-service-role-jwt"},
            clear=False,
        ):
            headers = readiness_service._supabase_headers()
        self.assertEqual(
            {name.lower() for name in headers},
            {"apikey", "authorization"},
        )

    def test_generated_execution_requires_isolated_worker(self):
        with patch.dict("os.environ", {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "false"}, clear=False):
            self.assertEqual(readiness_service.check_ai_execution_guard(), "insecure")
        with patch.dict("os.environ", {"AI_ALLOW_LOCAL_EXEC": "true", "AI_ISOLATED_WORKER_ENABLED": "true"}, clear=False):
            self.assertEqual(readiness_service.check_ai_execution_guard(), "ok")

    def test_remote_ingestion_requires_enforced_egress(self):
        healthy = SimpleNamespace(
            status_code=200,
            json=lambda: {
                "status": "ok",
                "isolation": "remote_ingestion_worker",
                "policy": "pinned_https_v1",
            },
        )
        environment = {
            "ALLOW_REMOTE_DATASET_URLS": "true",
            "REMOTE_INGESTION_WORKER_URL": "http://remote-ingestion-worker:8093/fetch",
            "REMOTE_INGESTION_WORKER_HEALTH_URL": "http://remote-ingestion-worker:8093/health",
            "REMOTE_INGESTION_EGRESS_ENFORCED": "false",
        }
        with patch.dict("os.environ", environment, clear=False), patch.object(
            readiness_service.requests, "get", return_value=healthy
        ):
            self.assertEqual(readiness_service.check_remote_ingestion_guard(), "ok")

    def test_remote_ingestion_cannot_be_declared_secure_without_worker_identity(self):
        wrong = SimpleNamespace(
            status_code=200,
            json=lambda: {"status": "ok", "isolation": "other", "policy": "pinned_https_v1"},
        )
        environment = {
            "ALLOW_REMOTE_DATASET_URLS": "true",
            "REMOTE_INGESTION_WORKER_URL": "http://remote-ingestion-worker:8093/fetch",
            "REMOTE_INGESTION_WORKER_HEALTH_URL": "http://remote-ingestion-worker:8093/health",
            "REMOTE_INGESTION_EGRESS_ENFORCED": "true",
        }
        with patch.dict("os.environ", environment, clear=False), patch.object(
            readiness_service.requests, "get", return_value=wrong
        ):
            self.assertEqual(readiness_service.check_remote_ingestion_guard(), "unavailable")

    def test_notification_worker_required_without_health_target_fails_closed(self):
        with patch.dict("os.environ", {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_WORKER_ENABLED": "true",
            "NOTIFICATION_WORKER_HEALTH_URL": "",
        }, clear=False):
            self.assertEqual(readiness_service.check_notification_worker(), "misconfigured")

    def test_notification_queue_backlog_is_degraded(self):
        with patch.dict("os.environ", {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "10",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "60",
            "NOTIFICATION_QUEUE_MAX_DEAD": "0",
        }, clear=False), patch.object(
            readiness_service,
            "get_queue_metrics",
            return_value={"queue_depth": 11, "oldest_pending_age_seconds": 30, "dead": 0},
        ):
            self.assertEqual(readiness_service.check_notification_queue(), "backlogged")

    def test_stale_backup_marker_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "last-backup"
            marker.write_text("fixture", encoding="utf-8")
            old = time.time() - 5
            os.utime(marker, (old, old))
            with patch.dict("os.environ", {
                "BACKUP_FRESHNESS_REQUIRED": "true",
                "BACKUP_FRESHNESS_MARKER": str(marker),
                "BACKUP_MAX_AGE_SECONDS": "1",
            }, clear=False):
                self.assertEqual(readiness_service.check_backup_freshness(), "stale")

    def test_production_parser_stays_gated_until_isolated(self):
        with patch.dict("os.environ", {"APP_ENV": "production", "PARSER_ISOLATED_WORKER_ENABLED": "false"}, clear=False):
            self.assertEqual(readiness_service.check_parser_isolation(), "in_process")

    def test_parser_isolation_requires_worker_identity_and_health(self):
        healthy = SimpleNamespace(
            status_code=200,
            json=lambda: {"status": "ok", "isolation": "parser_worker"},
        )
        wrong_identity = SimpleNamespace(
            status_code=200,
            json=lambda: {"status": "ok", "isolation": "other"},
        )
        environment = {
            "APP_ENV": "production",
            "PARSER_ISOLATED_WORKER_ENABLED": "true",
            "PARSER_WORKER_HEALTH_URL": "http://parser-worker:8092/health",
        }
        with patch.dict("os.environ", environment, clear=False), patch.object(
            readiness_service.requests, "get", return_value=healthy
        ):
            self.assertEqual(readiness_service.check_parser_isolation(), "ok")
        with patch.dict("os.environ", environment, clear=False), patch.object(
            readiness_service.requests, "get", return_value=wrong_identity
        ):
            self.assertEqual(readiness_service.check_parser_isolation(), "unavailable")

    def test_environment_name_must_be_explicit_and_known(self):
        for value, expected in (("production", "ok"), ("staging", "ok"), ("development", "ok"), ("test", "ok"), ("unknown", "misconfigured"), ("", "misconfigured")):
            with self.subTest(value=value), patch.dict(os.environ, {"APP_ENV": value}, clear=False):
                self.assertEqual(readiness_service.check_environment(), expected)

    def test_schema_readiness_uses_one_authoritative_contract_probe(self):
        observed = []

        def response_for(url, **_kwargs):
            observed.append(url)
            return SimpleNamespace(
                status_code=200,
                json=lambda: [{"schema_version": readiness_service.DEFAULT_SCHEMA_COMPATIBLE_MAX}],
            )

        with patch.dict(os.environ, {
            "CALENDAR_FEATURE_ENABLED": "true",
            "SUPABASE_URL": "https://supabase.example",
            "SUPABASE_SERVICE_KEY": "test-service-key",
        }, clear=False), patch.object(readiness_service.requests, "get", side_effect=response_for):
            self.assertEqual(readiness_service.check_schema(), "ok")
        self.assertEqual(len(observed), 1)
        self.assertIn("application_schema_state", observed[0])
        self.assertNotIn("calendar", observed[0])

    def test_schema_readiness_fails_closed_on_old_or_missing_contract(self):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://supabase.example",
            "SUPABASE_SERVICE_KEY": "test-service-key",
        }, clear=False), patch.object(
            readiness_service.requests,
            "get",
            return_value=SimpleNamespace(
                status_code=200,
                json=lambda: [{"schema_version": readiness_service.DEFAULT_SCHEMA_COMPATIBLE_MIN - 1}],
            ),
        ):
            self.assertEqual(readiness_service.check_schema(), "incompatible")

        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://supabase.example",
            "SUPABASE_SERVICE_KEY": "test-service-key",
        }, clear=False), patch.object(
            readiness_service.requests,
            "get",
            return_value=SimpleNamespace(status_code=404, json=lambda: {}),
        ):
            self.assertEqual(readiness_service.check_schema(), "missing")

    def test_schema_contract_migration_is_mirrored_and_service_role_only(self):
        root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "database/migrations").is_dir()
        )
        name = "081_create_application_schema_state.sql"
        database_sql = (root / "database/migrations" / name).read_text(encoding="utf-8")
        supabase_sql = (root / "supabase/migrations" / name).read_text(encoding="utf-8")
        self.assertEqual(database_sql, supabase_sql)
        normalized = " ".join(database_sql.lower().split())
        self.assertIn("values ('core', 81, now())", normalized)
        self.assertIn(
            "revoke all on public.application_schema_state from public, anon, authenticated",
            normalized,
        )
        self.assertIn(
            "revoke all on public.application_schema_state from service_role",
            normalized,
        )
        self.assertIn(
            "grant select on public.application_schema_state to service_role",
            normalized,
        )
        self.assertNotIn("grant insert", normalized)
        self.assertNotIn("grant update", normalized)
        self.assertNotIn("grant delete", normalized)

    def test_calendar_sync_configuration_fails_closed_when_required(self):
        with patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "false"}, clear=False):
            self.assertEqual(readiness_service.check_calendar_configuration(), "disabled")
        with patch.dict(os.environ, {
            "CALENDAR_FEATURE_ENABLED": "true", "CALENDAR_SYNC_REQUIRED": "true",
            "CALENDAR_SYNC_WORKER_ENABLED": "false",
        }, clear=False):
            self.assertEqual(readiness_service.check_calendar_configuration(), "misconfigured")
        with patch.dict(os.environ, {
            "CALENDAR_FEATURE_ENABLED": "true", "CALENDAR_SYNC_REQUIRED": "true",
            "CALENDAR_SYNC_WORKER_ENABLED": "true",
            "CALENDAR_CREDENTIALS_SECRET": "long-calendar-secret-for-tests",
            "PUBLIC_API_URL": "https://api.example.test",
            "FRONTEND_PRIMARY_URL": "https://app.example.test",
            "GOOGLE_CALENDAR_CLIENT_ID": "test-client",
            "GOOGLE_CALENDAR_CLIENT_SECRET": "test-secret",
        }, clear=False):
            self.assertEqual(readiness_service.check_calendar_configuration(), "ok")

    def test_calendar_task_sync_worker_and_queue_fail_closed(self):
        with patch.dict(os.environ, {
            "CALENDAR_FEATURE_ENABLED": "true",
            "CALENDAR_SYNC_REQUIRED": "true",
            "CALENDAR_SYNC_WORKER_HEALTH_URL": "",
        }, clear=False):
            self.assertEqual(
                readiness_service.check_calendar_sync_worker(), "misconfigured"
            )
        with patch.dict(os.environ, {
            "CALENDAR_FEATURE_ENABLED": "true",
            "CALENDAR_SYNC_REQUIRED": "true",
        }, clear=False), patch.object(
            readiness_service,
            "get_task_sync_queue_metrics",
            return_value={
                "queue_depth": 1,
                "failed": 0,
                "reconciliation_required": 1,
            },
        ), patch.object(
            readiness_service,
            "get_connection_sync_queue_metrics",
            return_value={"queue_depth": 0, "failed": 0},
        ):
            self.assertEqual(
                readiness_service.check_calendar_sync_queue(), "backlogged"
            )

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
