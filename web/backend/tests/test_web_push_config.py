import os
import unittest
from unittest.mock import patch

from services import (
    notification_delivery_queue_service,
    notification_delivery_service,
    notification_service,
    readiness_service,
)
from services.web_push_config import get_web_push_configuration


class _Response:
    data = 0

    def execute(self):
        return self


class _RpcClient:
    def __init__(self):
        self.payload = None

    def rpc(self, _name, payload):
        self.payload = payload
        return _Response()


class WebPushConfigurationTests(unittest.TestCase):
    COMPLETE = {
        "WEB_PUSH_ENABLED": "true",
        "WEB_PUSH_VAPID_PUBLIC_KEY": "public",
        "WEB_PUSH_VAPID_PRIVATE_KEY": "private",
        "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.invalid",
    }

    def test_administratively_disabled_is_not_public_or_queued(self):
        client = _RpcClient()
        with patch.dict(os.environ, {**self.COMPLETE, "WEB_PUSH_ENABLED": "false"}, clear=True):
            config = get_web_push_configuration()
            public = notification_service.get_web_push_public_config()
            readiness = readiness_service.check_notification_push()
            notification_delivery_queue_service.resolve_outbox_notification(
                {"id": "00000000-0000-0000-0000-000000000001"}, client=client
            )
        self.assertFalse(config.operational)
        self.assertEqual(public, {"enabled": False, "status": "disabled", "public_key": ""})
        self.assertEqual(readiness, "disabled")
        self.assertFalse(client.payload["p_web_push_enabled"])

    def test_enabled_complete_configuration_agrees_everywhere(self):
        client = _RpcClient()
        with patch.dict(os.environ, self.COMPLETE, clear=True):
            public = notification_service.get_web_push_public_config()
            readiness = readiness_service.check_notification_push()
            notification_delivery_queue_service.resolve_outbox_notification(
                {"id": "00000000-0000-0000-0000-000000000001"}, client=client
            )
        self.assertEqual(public, {"enabled": True, "status": "configured", "public_key": "public"})
        self.assertEqual(readiness, "configured")
        self.assertTrue(client.payload["p_web_push_enabled"])

    def test_each_missing_vapid_field_is_misconfigured(self):
        for missing in (
            "WEB_PUSH_VAPID_PUBLIC_KEY",
            "WEB_PUSH_VAPID_PRIVATE_KEY",
            "WEB_PUSH_VAPID_SUBJECT",
        ):
            environment = {**self.COMPLETE, missing: ""}
            client = _RpcClient()
            with self.subTest(missing=missing), patch.dict(os.environ, environment, clear=True):
                public = notification_service.get_web_push_public_config()
                readiness = readiness_service.check_notification_push()
                notification_delivery_queue_service.resolve_outbox_notification(
                    {"id": "00000000-0000-0000-0000-000000000001"}, client=client
                )
            self.assertEqual(public["status"], "misconfigured")
            self.assertFalse(public["enabled"])
            self.assertEqual(public["public_key"], "")
            self.assertEqual(readiness, "misconfigured")
            self.assertFalse(client.payload["p_web_push_enabled"])

    def test_deprecated_private_key_alone_cannot_make_push_healthy(self):
        with patch.dict(
            os.environ,
            {"WEB_PUSH_ENABLED": "true", "VAPID_PRIVATE_KEY": "deprecated-only"},
            clear=True,
        ):
            config = get_web_push_configuration()
            readiness = readiness_service.check_notification_push()
        self.assertFalse(config.operational)
        self.assertIn("WEB_PUSH_VAPID_PRIVATE_KEY", config.missing_fields)
        self.assertEqual(readiness, "misconfigured")

    def test_disabled_delivery_is_terminal_without_dead_letter_noise(self):
        with patch.dict(os.environ, {"WEB_PUSH_ENABLED": "false"}, clear=True):
            with self.assertRaises(notification_delivery_service.DeliveryError) as raised:
                notification_delivery_service._deliver_web_push({})
        self.assertEqual(raised.exception.code, "web_push_disabled")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.terminal_outcome, "revoked")


if __name__ == "__main__":
    unittest.main()
