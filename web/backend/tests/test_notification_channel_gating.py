import os
import base64
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid

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
    def valid_push_environment():
        vapid = Vapid()
        vapid.generate_keys()
        return {
            "WEB_PUSH_ENABLED": "true",
            "WEB_PUSH_VAPID_PUBLIC_KEY": base64.urlsafe_b64encode(
                vapid.public_key.public_bytes(
                    Encoding.X962, PublicFormat.UncompressedPoint
                )
            ).rstrip(b"=").decode("ascii"),
            "WEB_PUSH_VAPID_PRIVATE_KEY": base64.urlsafe_b64encode(
                vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
            ).rstrip(b"=").decode("ascii"),
            "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.invalid",
        }

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
                **self.valid_push_environment(),
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

    def test_terminal_web_push_outcomes_remain_telemetry_without_poisoning_readiness(self):
        environment = {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "1000",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "900",
            "NOTIFICATION_QUEUE_MAX_DEAD": "3",
            "NOTIFICATION_DEAD_READINESS_WINDOW_SECONDS": "86400",
            "WEB_PUSH_ENABLED": "true",
            "WEB_PUSH_VAPID_PUBLIC_KEY": "public",
            "WEB_PUSH_VAPID_PRIVATE_KEY": "private",
            "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.invalid",
        }
        metrics = {
            "queue_depth": 0,
            "oldest_pending_age_seconds": 0,
            "outbox_dead": 0,
            "outbox_dead_actionable": 0,
            "delivery_internal_dead": 0,
            "delivery_internal_dead_actionable": 0,
            "delivery_email_dead": 0,
            "delivery_email_dead_actionable": 0,
            "delivery_web_push_dead": 4,
            "delivery_web_push_dead_actionable": 0,
            "delivery_dead_terminal": 4,
        }
        with patch.dict(os.environ, environment, clear=False), patch.object(
            readiness_service, "get_queue_metrics", return_value=metrics
        ):
            self.assertEqual(readiness_service.check_notification_queue(), "ok")

    def test_web_push_provider_credentials_remain_readiness_actionable(self):
        environment = {
            "NOTIFICATION_WORKER_REQUIRED": "true",
            "NOTIFICATION_QUEUE_MAX_DEPTH": "1000",
            "NOTIFICATION_QUEUE_MAX_AGE_SECONDS": "900",
            "NOTIFICATION_QUEUE_MAX_DEAD": "3",
            "NOTIFICATION_DEAD_READINESS_WINDOW_SECONDS": "86400",
            **self.valid_push_environment(),
        }
        metrics = {
            "queue_depth": 0,
            "oldest_pending_age_seconds": 0,
            "outbox_dead": 0,
            "outbox_dead_actionable": 0,
            "delivery_internal_dead_actionable": 0,
            "delivery_email_dead_actionable": 0,
            "delivery_web_push_dead": 4,
            "delivery_web_push_dead_actionable": 4,
        }
        with patch.dict(os.environ, environment, clear=False), patch.object(
            readiness_service, "get_queue_metrics", return_value=metrics
        ):
            self.assertEqual(
                readiness_service.check_notification_queue(), "backlogged"
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
