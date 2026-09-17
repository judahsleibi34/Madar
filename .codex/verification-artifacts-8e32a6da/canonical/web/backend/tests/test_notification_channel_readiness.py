import os
import unittest
from unittest.mock import patch

from services import notification_delivery_service, readiness_service


class NotificationChannelReadinessTests(unittest.TestCase):
    def test_disabled_email_is_terminal_revoked_not_retrying(self):
        with patch.dict(os.environ, {"EMAIL_CHANNEL_ENABLED": "false"}, clear=True):
            with self.assertRaises(notification_delivery_service.DeliveryError) as context:
                notification_delivery_service._smtp_settings()
        self.assertEqual(context.exception.code, "email_channel_disabled")
        self.assertFalse(context.exception.retryable)
        self.assertEqual(context.exception.terminal_outcome, "revoked")

    def test_enabled_but_unconfigured_email_is_unavailable(self):
        with patch.dict(os.environ, {"EMAIL_CHANNEL_ENABLED": "true"}, clear=True):
            self.assertEqual(readiness_service.check_notification_email(), "unavailable")

    def test_configured_email_reports_dead_accumulation_as_degraded(self):
        environment = {"EMAIL_CHANNEL_ENABLED": "true", "SMTP_HOST": "smtp.invalid", "SMTP_FROM_EMAIL": "sender@example.invalid"}
        with patch.dict(os.environ, environment, clear=True), patch.object(
            readiness_service, "get_delivery_channel_metrics", return_value={"email": {"dead": 1}}
        ):
            self.assertEqual(readiness_service.check_notification_email(), "degraded")


if __name__ == "__main__":
    unittest.main()
