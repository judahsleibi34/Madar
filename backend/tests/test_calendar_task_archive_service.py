import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from services import calendar_task_archive_service


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.values = None
    def select(self, *_args): return self
    def eq(self, field, value): self.filters.append(("eq", field, value)); return self
    def in_(self, field, values): self.filters.append(("in", field, set(values))); return self
    def is_(self, field, value): self.filters.append(("eq", field, None if value == "null" else value)); return self
    def lte(self, field, value): self.filters.append(("lte", field, value)); return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, count): self.limit_value = count; return self
    def update(self, values): self.values = dict(values); return self
    def execute(self):
        def matches(row):
            for operation, field, value in self.filters:
                if operation == "eq" and row.get(field) != value:
                    return False
                if operation == "in" and row.get(field) not in value:
                    return False
                if operation == "lte" and (not row.get(field) or row.get(field) > value):
                    return False
            return True
        selected = [row for row in self.client.tables[self.table] if matches(row)]
        if self.values is not None:
            for row in selected:
                row.update(self.values)
        return SimpleNamespace(data=[dict(row) for row in selected[:getattr(self, "limit_value", len(selected))]])


class Client:
    def __init__(self):
        self.tables = {
            "calendar_tasks": [
                {"id": "ended", "tenant_id": 7, "status": "todo", "version": 2, "scheduled_end": "2026-08-10T11:00:00+00:00", "recurrence_rule": None},
                {"id": "future", "tenant_id": 7, "status": "todo", "version": 1, "scheduled_end": "2026-08-10T13:00:00+00:00", "recurrence_rule": None},
                {"id": "recurring", "tenant_id": 7, "status": "todo", "version": 1, "scheduled_end": "2026-08-10T11:00:00+00:00", "recurrence_rule": "FREQ=DAILY"},
                {"id": "unscheduled", "tenant_id": 7, "status": "todo", "version": 1, "scheduled_end": None, "recurrence_rule": None},
            ],
            "calendar_task_reminders": [
                {"id": "reminder", "task_id": "ended", "tenant_id": 7, "delivery_status": "scheduled", "failure_code": None},
            ],
        }
    def table(self, name): return Query(self, name)


class CalendarTaskArchiveServiceTests(unittest.TestCase):
    def test_only_ended_non_recurring_tasks_are_archived(self):
        client = Client()
        with patch.object(calendar_task_archive_service, "invalidate_calendar_workspace_cache") as invalidate:
            count = calendar_task_archive_service.archive_ended_calendar_tasks(
                now=datetime(2026, 8, 10, 12, tzinfo=timezone.utc), client=client
            )

        self.assertEqual(count, 1)
        tasks = {task["id"]: task for task in client.tables["calendar_tasks"]}
        self.assertEqual(tasks["ended"]["status"], "cancelled")
        self.assertEqual(tasks["ended"]["version"], 3)
        self.assertEqual(tasks["future"]["status"], "todo")
        self.assertEqual(tasks["recurring"]["status"], "todo")
        self.assertEqual(tasks["unscheduled"]["status"], "todo")
        self.assertEqual(client.tables["calendar_task_reminders"][0]["delivery_status"], "cancelled")
        invalidate.assert_called_once_with(7)
