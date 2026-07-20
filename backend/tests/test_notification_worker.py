import unittest
from unittest.mock import patch

from services.notification_delivery_service import DeliveryError
from workers import notification_worker


class NotificationWorkerTests(unittest.TestCase):
    def setUp(self):
        notification_worker.STATE.update({"healthy": False, "last_poll_at": None, "processed": 0, "sent": 0, "failed": 0, "dead": 0, "queue_depth": 0, "oldest_pending_age_seconds": 0})

    def test_claim_success_and_deduplicated_row_processed_once(self):
        rows = [{"id": "one", "channel": "internal", "attempts": 1, "max_attempts": 5}]
        delivered, finished = [], []
        count = notification_worker.process_batch(
            limit=5,
            claim=lambda **_kwargs: rows,
            deliver=delivered.append,
            finish=lambda outbox_id, **kwargs: finished.append((outbox_id, kwargs)) or True,
        )
        self.assertEqual(count, 1)
        self.assertEqual(delivered, rows)
        self.assertTrue(finished[0][1]["succeeded"])
        self.assertEqual(notification_worker.STATE["sent"], 1)

    def test_retry_dead_letter_and_structured_failure(self):
        rows = [{"id": "last", "channel": "email", "attempts": 5, "max_attempts": 5}]
        finished = []
        notification_worker.process_batch(
            limit=1,
            claim=lambda **_kwargs: rows,
            deliver=lambda _row: (_ for _ in ()).throw(DeliveryError("smtp_not_configured")),
            finish=lambda outbox_id, **kwargs: finished.append((outbox_id, kwargs)) or True,
        )
        self.assertEqual(finished[0][1]["failure_code"], "smtp_not_configured")
        self.assertGreater(finished[0][1]["retry_after_seconds"], 0)
        self.assertEqual(notification_worker.STATE["dead"], 1)

    def test_unsupported_channel_is_permanent_and_logs_no_payload(self):
        row = {"id": "bad", "channel": "sms", "payload": {"password": "secret"}, "attempts": 1}
        finished = []
        with self.assertLogs(notification_worker.logger, level="WARNING") as logs:
            notification_worker.process_batch(
                limit=1,
                claim=lambda **_kwargs: [row],
                deliver=lambda _row: (_ for _ in ()).throw(DeliveryError("notification_channel_unsupported", retryable=False)),
                finish=lambda outbox_id, **kwargs: finished.append(kwargs) or True,
            )
        self.assertEqual(finished[0]["failure_code"], "permanent.notification_channel_unsupported")
        self.assertNotIn("secret", " ".join(logs.output))

    def test_unexpected_push_failure_is_retryable(self):
        finished = []
        with self.assertLogs(notification_worker.logger, level="ERROR") as logs:
            notification_worker.process_batch(
                limit=1,
                claim=lambda **_kwargs: [{"id": "push", "channel": "web_push", "attempts": 1}],
                deliver=lambda _row: (_ for _ in ()).throw(RuntimeError("provider token secret")),
                finish=lambda _outbox_id, **kwargs: finished.append(kwargs) or True,
            )
        self.assertEqual(finished[0]["failure_code"], "delivery_unexpected")
        self.assertNotIn("secret", " ".join(logs.output))

    def test_disabled_worker_never_claims(self):
        with patch.dict("os.environ", {"NOTIFICATION_WORKER_ENABLED": "false"}, clear=False):
            self.assertEqual(notification_worker.main(), 0)

    def test_retry_delay_is_bounded_and_deterministic(self):
        row = {"id": "stable", "attempts": 20}
        self.assertEqual(notification_worker.retry_delay(row), notification_worker.retry_delay(row))
        self.assertLessEqual(notification_worker.retry_delay(row), 3600)
