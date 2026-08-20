import json
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import observability_service


class ObservabilityServiceTests(unittest.TestCase):
    def test_correlation_id_accepts_bounded_safe_values(self):
        self.assertEqual(observability_service.correlation_id("request-1234"), "request-1234")
        generated = observability_service.correlation_id("bad value with spaces")
        self.assertRegex(generated, r"^[a-f0-9]{32}$")

    def test_metrics_use_bounded_route_labels(self):
        observability_service.record_request(
            method="GET",
            route="https://untrusted.example/user@example.com",
            status_code=503,
            elapsed_seconds=0.25,
        )
        with patch.object(observability_service, "operational_snapshot", return_value={}):
            rendered = observability_service.prometheus_metrics()
        self.assertIn('route="unmatched"', rendered)
        self.assertNotIn("user@example.com", rendered)

    def test_metrics_token_is_constant_time_bearer_policy(self):
        with patch.dict("os.environ", {"METRICS_TOKEN": "metrics-secret"}, clear=False):
            self.assertTrue(observability_service.metrics_access_allowed(client_host="10.0.0.2", authorization="Bearer metrics-secret"))
            self.assertFalse(observability_service.metrics_access_allowed(client_host="127.0.0.1", authorization=None))

    def test_json_logs_only_emit_allowlisted_context(self):
        record = logging.LogRecord("test", logging.WARNING, __file__, 1, "security.denied", (), None)
        record.error_code = "access_denied"
        record.recipient = "private@example.com"
        payload = json.loads(observability_service.JsonFormatter().format(record))
        self.assertEqual(payload["error_code"], "access_denied")
        self.assertNotIn("recipient", payload)
        self.assertNotIn("private@example.com", str(payload))

    def test_http_client_info_logging_is_suppressed(self):
        observability_service.configure_structured_logging()
        self.assertEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertEqual(logging.getLogger("httpcore").level, logging.WARNING)
        self.assertFalse(logging.getLogger("httpx").isEnabledFor(logging.INFO))
        self.assertTrue(logging.getLogger("httpx").isEnabledFor(logging.WARNING))

    def test_access_filter_removes_queries_and_successful_liveness_noise(self):
        access_filter = observability_service.SafeAccessLogFilter()
        successful_health = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1", "GET", "/health/live?code=secret", "1.1", 200), None,
        )
        self.assertFalse(access_filter.filter(successful_health))
        self.assertEqual(successful_health.args[2], "/health/live")

        failed_health = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1", "GET", "/health/live?state=secret", "1.1", 500), None,
        )
        self.assertTrue(access_filter.filter(failed_health))
        self.assertEqual(failed_health.args[2], "/health/live")

        callback = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1", "GET", "/calendar/oauth/google/callback?code=private&state=private", "1.1", 303), None,
        )
        self.assertTrue(access_filter.filter(callback))
        self.assertEqual(callback.args[2], "/calendar/oauth/google/callback")
        self.assertNotIn("private", callback.getMessage())

    def test_operational_snapshot_includes_cleanup_and_reservations(self):
        class Query:
            def __init__(self, rows): self.rows = rows
            def select(self, *_args): return self
            def eq(self, field, value):
                self.rows = [row for row in self.rows if row.get(field) == value]
                return self
            def lte(self, *_args): return self
            def limit(self, count):
                self.rows = self.rows[:count]
                return self
            def execute(self): return SimpleNamespace(data=self.rows)

        class Client:
            tables = {
                "builder_assets": [{"id": "asset", "status": "unreferenced"}],
                "storage_reservations": [{"id": "reservation", "status": "reserved"}],
            }
            def table(self, name): return Query([dict(row) for row in self.tables[name]])

        with patch.object(observability_service, "service_supabase", Client()), patch.object(
            observability_service, "get_queue_metrics", return_value={"queue_depth": 2}
        ), patch.object(
            observability_service, "disk_usage", return_value=SimpleNamespace(free=10, used=20)
        ), patch.dict("os.environ", {"BACKUP_FRESHNESS_MARKER": ""}, clear=False):
            snapshot = observability_service.operational_snapshot()

        self.assertEqual(snapshot["notification_queue_depth"], 2)
        self.assertEqual(snapshot["asset_cleanup_backlog"], 1)
        self.assertEqual(snapshot["quota_reservations"], 1)


if __name__ == "__main__":
    unittest.main()
