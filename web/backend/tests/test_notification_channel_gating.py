import os
from pathlib import Path
import unittest
from unittest.mock import patch

from services import notification_delivery_queue_service
from services import readiness_service


class Response:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return Response(0)


class NotificationChannelGatingTests(unittest.TestCase):
    @staticmethod
    def repository_root() -> Path:
        local = Path(__file__).resolve().parents[2]
        return local if (local / "database/migrations").is_dir() else Path("/workspace")

    def test_resolution_passes_runtime_channel_capabilities(self):
        client = RpcClient()

        with patch.dict(
            os.environ,
            {
                "EMAIL_CHANNEL_ENABLED": "false",
                "WEB_PUSH_ENABLED": "true",
            },
            clear=False,
        ):
            notification_delivery_queue_service.resolve_outbox_notification(
                {"id": "00000000-0000-0000-0000-000000000001"},
                client=client,
            )

        self.assertEqual(client.calls[0][0], "resolve_notification_outbox_v2")
        payload = client.calls[0][1]
        self.assertFalse(payload["p_email_enabled"])
        self.assertTrue(payload["p_web_push_enabled"])

    def test_channel_delivery_dead_letters_do_not_poison_generic_queue(self):
        environment = {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "1000",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "900",
            "NOTIFICATION_QUEUE_MAX_DEAD": "3",
            "EMAIL_CHANNEL_ENABLED": "false",
            "WEB_PUSH_ENABLED": "false",
        }

        metrics = {
            "queue_depth": 0,
            "oldest_pending_age_seconds": 0,
            "outbox_dead": 0,
            "delivery_dead": 11,
            "delivery_internal_dead": 0,
            "delivery_email_dead": 11,
            "delivery_web_push_dead": 0,
            "dead": 11,
        }

        with patch.dict(os.environ, environment, clear=False), patch.object(
            readiness_service,
            "get_queue_metrics",
            return_value=metrics,
        ):
            self.assertEqual(
                readiness_service.check_notification_queue(),
                "ok",
            )

    def test_internal_delivery_dead_letters_still_fail_generic_queue(self):
        environment = {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "1000",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "900",
            "NOTIFICATION_QUEUE_MAX_DEAD": "3",
            "EMAIL_CHANNEL_ENABLED": "false",
            "WEB_PUSH_ENABLED": "false",
        }

        metrics = {
            "queue_depth": 0,
            "oldest_pending_age_seconds": 0,
            "outbox_dead": 0,
            "delivery_dead": 4,
            "delivery_internal_dead": 4,
            "delivery_email_dead": 0,
            "delivery_web_push_dead": 0,
            "dead": 4,
        }

        with patch.dict(os.environ, environment, clear=False), patch.object(
            readiness_service,
            "get_queue_metrics",
            return_value=metrics,
        ):
            self.assertEqual(
                readiness_service.check_notification_queue(),
                "backlogged",
            )

    def test_enabled_email_dead_letters_still_fail_generic_queue(self):
        environment = {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "1000",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "900",
            "NOTIFICATION_QUEUE_MAX_DEAD": "3",
            "EMAIL_CHANNEL_ENABLED": "true",
            "WEB_PUSH_ENABLED": "false",
        }

        metrics = {
            "queue_depth": 0,
            "oldest_pending_age_seconds": 0,
            "outbox_dead": 0,
            "delivery_dead": 4,
            "delivery_internal_dead": 0,
            "delivery_email_dead": 4,
            "delivery_web_push_dead": 0,
            "dead": 4,
        }

        with patch.dict(os.environ, environment, clear=False), patch.object(
            readiness_service,
            "get_queue_metrics",
            return_value=metrics,
        ):
            self.assertEqual(
                readiness_service.check_notification_queue(),
                "backlogged",
            )

    def test_real_outbox_dead_letters_still_fail_generic_queue(self):
        environment = {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "1000",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "900",
            "NOTIFICATION_QUEUE_MAX_DEAD": "3",
        }

        metrics = {
            "queue_depth": 0,
            "oldest_pending_age_seconds": 0,
            "outbox_dead": 4,
            "delivery_dead": 0,
            "dead": 4,
        }

        with patch.dict(os.environ, environment, clear=False), patch.object(
            readiness_service,
            "get_queue_metrics",
            return_value=metrics,
        ):
            self.assertEqual(
                readiness_service.check_notification_queue(),
                "backlogged",
            )

    def test_migration_preserves_legacy_rpc_and_adds_capability_gated_v2(self):
        root = self.repository_root()

        migration = (
            root / "database/migrations/085_filter_disabled_notification_channels.sql"
        ).read_text()

        normalized = " ".join(migration.lower().split())

        self.assertIn(
            "resolve_notification_outbox_v2",
            normalized,
        )
        self.assertIn(
            "p_email_enabled boolean",
            normalized,
        )
        self.assertIn(
            "p_web_push_enabled boolean",
            normalized,
        )
        self.assertIn(
            "work.template = 'tenant_event' and p_web_push_enabled",
            normalized,
        )
        self.assertIn(
            "if p_email_enabled then",
            normalized,
        )

        legacy = (
            root / "database/migrations/073_create_notification_deliveries.sql"
        ).read_text()

        self.assertIn(
            "resolve_notification_outbox(",
            legacy,
        )


if __name__ == "__main__":
    unittest.main()
