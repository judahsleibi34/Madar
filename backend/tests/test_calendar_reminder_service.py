import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import calendar_reminder_service


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.values = None
    def select(self, *_args): return self
    def eq(self, field, value): self.filters.append((field, value)); return self
    def lte(self, *_args): return self
    def is_(self, *_args): return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, *_args): return self
    def update(self, values): self.values = values; return self
    def execute(self):
        rows = self.client.tables[self.table]
        selected = [row for row in rows if all(row.get(field) == value for field, value in self.filters)]
        if self.values is not None:
            for row in selected:
                row.update(self.values)
        return SimpleNamespace(data=[dict(row) for row in selected])


class Client:
    def __init__(self):
        self.tables = {
            "calendar_event_reminders": [],
            "calendar_events": [],
            "calendar_task_reminders": [
                {"id": "bad", "task_id": "task-bad", "tenant_id": 7, "channel": "in_app", "minutes_before": 10, "scheduled_for": "invalid", "delivery_status": "scheduled"},
                {"id": "good", "task_id": "task-good", "tenant_id": 7, "channel": "in_app", "minutes_before": 10, "scheduled_for": "2026-07-22T08:50:00+00:00", "delivery_status": "scheduled"},
            ],
            "calendar_tasks": [
                {"id": "task-bad", "tenant_id": 7, "owner_user_id": 12, "status": "todo", "title": "Bad", "scheduled_start": "2026-07-22T09:00:00+00:00"},
                {"id": "task-good", "tenant_id": 7, "owner_user_id": 12, "status": "todo", "title": "Good", "scheduled_start": "2026-07-22T09:00:00+00:00"},
            ],
            "tenant_memberships": [{"tenant_id": 7, "user_id": 12, "status": "active"}],
            "notification_deliveries": [],
            "notification_outbox": [],
        }
    def table(self, name): return Query(self, name)


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(data=[{"id": "outbox"}])
        )


class CalendarReminderServiceTests(unittest.TestCase):
    def test_due_reminder_enqueue_uses_transactional_rpc(self):
        client = RpcClient()
        queued = calendar_reminder_service._enqueue_reminder_notification(
            reminder_source="event",
            reminder={
                "id": "00000000-0000-0000-0000-000000000001",
                "tenant_id": 7,
                "scheduled_for": "2026-07-22T08:50:00+00:00",
            },
            channel="email",
            user_id=12,
            recipient_reference="user:12",
            deduplication_key="calendar-reminder:one",
            payload={"reminder_id": "one"},
            client=client,
        )
        self.assertEqual(queued["id"], "outbox")
        self.assertEqual(
            client.calls[0][0], "enqueue_calendar_reminder_notification"
        )
        self.assertEqual(client.calls[0][1]["p_user_id"], 12)

    def test_inactive_event_creator_is_cancelled_without_enqueue(self):
        client = Client()
        client.tables["calendar_task_reminders"] = []
        client.tables["calendar_event_reminders"] = [
            {"id": "event-reminder", "event_id": "event-1", "tenant_id": 7, "channel": "web_push", "minutes_before": 10, "scheduled_for": "2026-07-22T08:50:00+00:00", "delivery_status": "scheduled"}
        ]
        client.tables["calendar_events"] = [
            {"id": "event-1", "tenant_id": 7, "created_by": 99, "status": "confirmed", "title": "Private event", "starts_at": "2026-07-22T09:00:00+00:00", "deleted_at": None}
        ]
        with patch.object(calendar_reminder_service, "enqueue_notification") as enqueue:
            self.assertEqual(calendar_reminder_service.enqueue_due_calendar_reminders(client=client), 0)
        enqueue.assert_not_called()
        reminder = client.tables["calendar_event_reminders"][0]
        self.assertEqual(reminder["delivery_status"], "cancelled")
        self.assertEqual(reminder["failure_code"], "owner_inactive")

    def test_task_only_batch_uses_current_reminder_and_continues_after_malformed_row(self):
        client = Client()
        payloads = []
        with patch.object(
            calendar_reminder_service,
            "enqueue_notification",
            side_effect=lambda **kwargs: payloads.append(kwargs["payload"]) or {"id": "outbox"},
        ):
            queued = calendar_reminder_service.enqueue_due_calendar_reminders(client=client)

        self.assertEqual(queued, 1)
        self.assertEqual(payloads[0]["data"]["scheduled_start"], "2026-07-22T09:00:00+00:00")
        bad = next(row for row in client.tables["calendar_task_reminders"] if row["id"] == "bad")
        good = next(row for row in client.tables["calendar_task_reminders"] if row["id"] == "good")
        self.assertEqual(bad["delivery_status"], "failed")
        self.assertEqual(bad["failure_code"], "reminder_time_invalid")
        self.assertEqual(good["delivery_status"], "queued")

    def test_inactive_owner_is_cancelled_without_enqueue(self):
        client = Client()
        client.tables["calendar_task_reminders"] = [client.tables["calendar_task_reminders"][1]]
        client.tables["tenant_memberships"] = []
        with patch.object(calendar_reminder_service, "enqueue_notification") as enqueue:
            self.assertEqual(calendar_reminder_service.enqueue_due_calendar_reminders(client=client), 0)
        enqueue.assert_not_called()
        self.assertEqual(client.tables["calendar_task_reminders"][0]["failure_code"], "owner_inactive")

    def test_reminder_waits_for_all_independent_deliveries(self):
        client = Client()
        client.tables["calendar_task_reminders"] = []
        client.tables["calendar_event_reminders"] = [
            {"id": "reminder", "delivery_status": "queued"}
        ]
        client.tables["notification_outbox"] = [
            {
                "id": "outbox",
                "template": "calendar_reminder",
                "payload": {"reminder_id": "reminder"},
            }
        ]
        client.tables["notification_deliveries"] = [
            {"outbox_id": "outbox", "status": "sent", "last_error_code": None},
            {"outbox_id": "outbox", "status": "pending", "last_error_code": None},
        ]
        self.assertFalse(
            calendar_reminder_service.finalize_calendar_reminder_deliveries(
                "outbox", client=client
            )
        )
        self.assertEqual(
            client.tables["calendar_event_reminders"][0]["delivery_status"],
            "queued",
        )

        client.tables["notification_deliveries"][1].update(
            {"status": "dead", "last_error_code": "subscription_revoked"}
        )
        self.assertTrue(
            calendar_reminder_service.finalize_calendar_reminder_deliveries(
                "outbox", client=client
            )
        )
        self.assertEqual(
            client.tables["calendar_event_reminders"][0]["delivery_status"],
            "delivered",
        )


if __name__ == "__main__":
    unittest.main()
