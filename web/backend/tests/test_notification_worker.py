import unittest
from unittest.mock import patch

from services.notification_delivery_service import DeliveryError
from workers import notification_worker


class NotificationWorkerTests(unittest.TestCase):
    def setUp(self):
        notification_worker.STATE.update({"healthy": False, "last_poll_at": None, "processed": 0, "resolved": 0, "sent": 0, "failed": 0, "dead": 0, "queue_depth": 0, "oldest_pending_age_seconds": 0})

    def test_claim_success_and_deduplicated_row_processed_once(self):
        rows = [{"id": "one", "channel": "internal", "attempts": 1, "max_attempts": 5}]
        delivered, finished = [], []
        count = notification_worker.process_batch(
            limit=5,
            claim=lambda **_kwargs: rows,
            deliver=delivered.append,
            finish=lambda delivery_id, **kwargs: finished.append((delivery_id, kwargs)) or {"status": "sent"},
        )
        self.assertEqual(count, 1)
        self.assertEqual(delivered, rows)
        self.assertEqual(finished[0][1]["outcome"], "sent")
        self.assertEqual(notification_worker.STATE["sent"], 1)

    def test_retry_dead_letter_and_structured_failure(self):
        rows = [{"id": "last", "channel": "email", "attempts": 5, "max_attempts": 5}]
        finished = []
        notification_worker.process_batch(
            limit=1,
            claim=lambda **_kwargs: rows,
            deliver=lambda _row: (_ for _ in ()).throw(DeliveryError("smtp_not_configured")),
            finish=lambda delivery_id, **kwargs: finished.append((delivery_id, kwargs)) or {"status": "dead"},
        )
        self.assertEqual(finished[0][1]["error_code"], "smtp_not_configured")
        self.assertGreater(finished[0][1]["retry_after_seconds"], 0)
        self.assertEqual(notification_worker.STATE["dead"], 1)

    def test_unsupported_channel_is_permanent_and_logs_no_payload(self):
        row = {"id": "bad", "channel": "sms", "payload": {"password": "secret"}, "attempts": 1}
        finished = []
        with self.assertLogs(notification_worker.logger, level="INFO") as logs:
            notification_worker.process_batch(
                limit=1,
                claim=lambda **_kwargs: [row],
                deliver=lambda _row: (_ for _ in ()).throw(DeliveryError("notification_channel_unsupported", retryable=False)),
                finish=lambda delivery_id, **kwargs: finished.append(kwargs) or {"status": "dead"},
            )
        self.assertEqual(finished[0]["outcome"], "dead")
        self.assertEqual(finished[0]["error_code"], "notification_channel_unsupported")
        self.assertNotIn("secret", " ".join(logs.output))

    def test_unexpected_push_failure_is_retryable(self):
        finished = []
        with self.assertLogs(notification_worker.logger, level="ERROR") as logs:
            notification_worker.process_batch(
                limit=1,
                claim=lambda **_kwargs: [{"id": "push", "channel": "web_push", "attempts": 1}],
                deliver=lambda _row: (_ for _ in ()).throw(RuntimeError("provider token secret")),
                finish=lambda _delivery_id, **kwargs: finished.append(kwargs) or {"status": "pending"},
            )
        self.assertEqual(finished[0]["error_code"], "delivery_unexpected")
        self.assertNotIn("secret", " ".join(logs.output))

    def test_disabled_worker_never_claims(self):
        with patch.dict("os.environ", {"NOTIFICATION_WORKER_ENABLED": "false"}, clear=False):
            self.assertEqual(notification_worker.main(), 0)

    def test_retry_delay_is_bounded_and_deterministic(self):
        row = {"id": "stable", "attempts": 20}
        self.assertEqual(notification_worker.retry_delay(row), notification_worker.retry_delay(row))
        self.assertLessEqual(notification_worker.retry_delay(row), 3600)

    def test_provider_retry_after_is_honored_by_persisted_retry(self):
        finished = []
        notification_worker.process_batch(
            limit=1,
            claim=lambda **_kwargs: [
                {"id": "rate-limited", "channel": "web_push", "attempts": 1}
            ],
            deliver=lambda _row: (_ for _ in ()).throw(
                DeliveryError(
                    "web_push_rate_limited",
                    retry_after_seconds=120,
                )
            ),
            finish=lambda _delivery_id, **kwargs: finished.append(kwargs)
            or {"status": "pending"},
        )
        self.assertEqual(finished[0]["outcome"], "retry")
        self.assertGreaterEqual(finished[0]["retry_after_seconds"], 120)

    def test_resolution_creates_deliveries_before_outbox_completion(self):
        rows = [{"id": "outbox", "channel": "internal", "attempts": 1}]
        resolved = []
        count = notification_worker.process_resolution_batch(
            limit=1,
            claim=lambda **_kwargs: rows,
            resolve=lambda row: resolved.append(row["id"]) or 4,
        )
        self.assertEqual(count, 1)
        self.assertEqual(resolved, ["outbox"])
        self.assertEqual(notification_worker.STATE["resolved"], 1)

    def test_partial_push_retry_only_reprocesses_failed_subscription(self):
        first_claim = [
            {"id": "A", "channel": "web_push", "subscription_id": "A", "attempts": 1},
            {"id": "B", "channel": "web_push", "subscription_id": "B", "attempts": 1},
            {"id": "C", "channel": "web_push", "subscription_id": "C", "attempts": 1},
        ]
        calls = []
        statuses = {}

        def deliver(row):
            calls.append(row["subscription_id"])
            if row["subscription_id"] == "B":
                raise DeliveryError("provider_unavailable")
            if row["subscription_id"] == "C":
                raise DeliveryError(
                    "web_push_subscription_revoked",
                    retryable=False,
                    terminal_outcome="revoked",
                )

        def finish(delivery_id, **kwargs):
            status = {
                "sent": "sent",
                "retry": "pending",
                "dead": "dead",
                "revoked": "dead",
            }[kwargs["outcome"]]
            statuses[delivery_id] = status
            return {"status": status}

        notification_worker.process_batch(
            limit=3,
            claim=lambda **_kwargs: first_claim,
            deliver=deliver,
            finish=finish,
        )
        self.assertEqual(statuses, {"A": "sent", "B": "pending", "C": "dead"})

        notification_worker.process_batch(
            limit=1,
            claim=lambda **_kwargs: [{**first_claim[1], "attempts": 2}],
            deliver=lambda row: calls.append(row["subscription_id"]),
            finish=finish,
        )
        self.assertEqual(calls, ["A", "B", "C", "B"])

    def test_provider_success_with_result_persistence_failure_does_not_crash_batch(self):
        with self.assertLogs(notification_worker.logger, level="ERROR") as logs:
            count = notification_worker.process_batch(
                limit=1,
                claim=lambda **_kwargs: [
                    {"id": "delivery", "channel": "email", "attempts": 1}
                ],
                deliver=lambda _row: None,
                finish=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("database unavailable")
                ),
            )
        self.assertEqual(count, 1)
        self.assertIn("delivery_result_persist_failed", " ".join(logs.output))
