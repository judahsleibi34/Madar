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
        }
    def table(self, name): return Query(self, name)


class CalendarReminderServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
