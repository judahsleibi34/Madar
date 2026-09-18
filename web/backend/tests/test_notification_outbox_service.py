import unittest
from datetime import datetime, timezone

from services import notification_outbox_service


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.payload = None
        self.update_payload = None
        self.filters = []

    def insert(self, payload):
        self.payload = dict(payload)
        return self

    def select(self, *_args):
        return self

    def update(self, payload):
        self.update_payload = dict(payload)
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def is_(self, key, value):
        self.filters.append((key, None if value == "null" else value))
        return self

    def in_(self, key, values):
        self.filters.append((key, tuple(values)))
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        if self.payload is not None:
            duplicate = next(
                (
                    row
                    for row in self.client.rows
                    if row.get("tenant_id") == self.payload.get("tenant_id")
                    and row.get("channel") == self.payload.get("channel")
                    and row.get("deduplication_key")
                    == self.payload.get("deduplication_key")
                ),
                None,
            )
            if duplicate:
                raise RuntimeError("duplicate unique key")
            row = {"id": f"outbox-{len(self.client.rows) + 1}", **self.payload}
            self.client.rows.append(row)
            return FakeResponse([dict(row)])

        rows = list(
            self.client.rows
            if self.table == "notification_outbox"
            else self.client.deliveries
        )
        for key, value in self.filters:
            if isinstance(value, tuple):
                rows = [row for row in rows if row.get(key) in value]
            else:
                rows = [row for row in rows if row.get(key) == value]
        if self.update_payload is not None:
            for row in rows:
                row.update(self.update_payload)
        return FakeResponse([dict(row) for row in rows])


class FakeClient:
    def __init__(self):
        self.rows = []
        self.deliveries = []

    def table(self, name):
        if name not in {"notification_outbox", "notification_deliveries"}:
            raise AssertionError(name)
        return FakeQuery(self, name)


class NotificationOutboxServiceTests(unittest.TestCase):
    def test_queue_metrics_include_backlog_age_and_terminal_counts(self):
        client = FakeClient()
        client.rows.extend([
            {"status": "pending", "created_at": "2026-07-20T00:00:00+00:00"},
            {"status": "failed", "created_at": "2026-07-20T00:01:00+00:00"},
            {"status": "dead", "created_at": "2026-07-20T00:02:00+00:00"},
            {"status": "sent", "created_at": "2026-07-20T00:03:00+00:00"},
        ])
        metrics = notification_outbox_service.get_queue_metrics(
            client=client,
            now=datetime(2026, 7, 20, 0, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(metrics["queue_depth"], 2)
        self.assertEqual(metrics["oldest_pending_age_seconds"], 300)
        self.assertEqual(metrics["dead"], 1)
        self.assertEqual(metrics["sent"], 1)

    def test_dead_readiness_separates_terminal_and_historical_delivery_telemetry(self):
        client = FakeClient()
        client.deliveries.extend([
            {
                "status": "dead",
                "channel": "web_push",
                "last_error_code": "web_push_subscription_revoked",
                "updated_at": "2026-07-20T00:04:30+00:00",
            },
            {
                "status": "dead",
                "channel": "web_push",
                "last_error_code": "web_push_provider_unauthorized",
                "updated_at": "2026-07-20T00:04:40+00:00",
            },
            {
                "status": "dead",
                "channel": "web_push",
                "last_error_code": "web_push_provider_rejected",
                "updated_at": "2026-07-18T00:00:00+00:00",
            },
        ])
        metrics = notification_outbox_service.get_queue_metrics(
            client=client,
            now=datetime(2026, 7, 20, 0, 5, tzinfo=timezone.utc),
            dead_readiness_window_seconds=3600,
        )
        self.assertEqual(metrics["delivery_web_push_dead"], 3)
        self.assertEqual(metrics["delivery_dead_terminal"], 1)
        self.assertEqual(metrics["delivery_web_push_dead_actionable"], 1)

    def test_enqueue_is_deduplicated_and_tenant_scoped(self):
        client = FakeClient()
        first = notification_outbox_service.enqueue_notification(
            channel="internal",
            template="tenant_event",
            tenant_id=7,
            deduplication_key="event-1",
            payload={"event_type": "builder.form_submitted"},
            client=client,
        )
        second = notification_outbox_service.enqueue_notification(
            channel="internal",
            template="tenant_event",
            tenant_id=7,
            deduplication_key="event-1",
            payload={"event_type": "builder.form_submitted"},
            client=client,
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(client.rows), 1)
        self.assertEqual(client.rows[0]["tenant_id"], 7)

        third = notification_outbox_service.enqueue_notification(
            channel="internal",
            template="tenant_event",
            tenant_id=8,
            deduplication_key="event-1",
            payload={"event_type": "builder.form_submitted"},
            client=client,
        )
        self.assertNotEqual(first["id"], third["id"])
        self.assertEqual(len(client.rows), 2)

    def test_global_deduplication_never_returns_a_tenant_row(self):
        client = FakeClient()
        tenant_row = notification_outbox_service.enqueue_notification(
            channel="email",
            template="reservation_confirmation",
            tenant_id=7,
            deduplication_key="shared-key",
            payload={"reservation_id": "tenant-reservation"},
            client=client,
        )
        global_row = notification_outbox_service.enqueue_notification(
            channel="email",
            template="system_notice",
            deduplication_key="shared-key",
            payload={"notice": "global"},
            client=client,
        )
        global_retry = notification_outbox_service.enqueue_notification(
            channel="email",
            template="system_notice",
            deduplication_key="shared-key",
            payload={"notice": "global"},
            client=client,
        )

        self.assertNotEqual(tenant_row["id"], global_row["id"])
        self.assertEqual(global_retry["id"], global_row["id"])
        self.assertIsNone(global_retry["tenant_id"])

    def test_failure_state_sanitizes_provider_error(self):
        client = FakeClient()
        row = notification_outbox_service.enqueue_notification(
            channel="email",
            template="reservation_confirmation",
            tenant_id=7,
            user_id=4,
            recipient_hash="a" * 64,
            payload={"reservation_id": "reservation-1"},
            client=client,
        )

        updated = notification_outbox_service.mark_notification_result(
            row["id"],
            succeeded=False,
            failure_code="SMTP password=secret connection failed",
            client=client,
        )

        self.assertTrue(updated)
        self.assertEqual(client.rows[0]["status"], "failed")
        self.assertEqual(client.rows[0]["last_error_code"], "delivery_failed")
        self.assertNotIn("secret", str(client.rows[0]))


if __name__ == "__main__":
    unittest.main()
