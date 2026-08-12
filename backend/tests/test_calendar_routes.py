import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import routes.calendar_routes as calendar_routes
from routes.calendar_routes import (
    TaskWrite,
    dependency_would_cycle,
    event_payload,
    expand_events,
    ics_escape,
    is_calendar_schema_missing_error,
    parse_ics_datetime,
    parse_ics_events,
    parse_range,
    reservation_events_for_range,
    reservation_payload,
    truncated_recurrence_rule,
    validate_timezone,
)
from services.calendar_reminder_service import next_task_reminder_time
from services.calendar_workspace_cache_service import clear_calendar_workspace_cache


class Query:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]

    def select(self, *_args): return self
    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self
    def in_(self, field, values):
        self.rows = [row for row in self.rows if row.get(field) in values]
        return self
    def neq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) != value]
        return self
    def is_(self, field, value):
        expected = None if value == "null" else value
        self.rows = [row for row in self.rows if row.get(field) is expected]
        return self
    @property
    def not_(self):
        return NegatedQuery(self)
    def order(self, field, desc=False):
        self.rows.sort(key=lambda row: (row.get(field) is None, row.get(field)), reverse=desc)
        return self
    def lt(self, *_args): return self
    def gt(self, *_args): return self
    def gte(self, field, value):
        self.rows = [row for row in self.rows if str(row.get(field) or "") >= str(value)]
        return self
    def limit(self, count):
        self.rows = self.rows[:count]
        return self
    def execute(self): return SimpleNamespace(data=self.rows)


class NegatedQuery:
    def __init__(self, query):
        self.query = query

    def is_(self, field, value):
        expected = None if value == "null" else value
        self.query.rows = [row for row in self.query.rows if row.get(field) is not expected]
        return self.query


class CalendarRouteTests(unittest.TestCase):
    def tearDown(self):
        clear_calendar_workspace_cache()

    def test_calendar_schema_missing_error_is_detected_without_masking_other_failures(self):
        self.assertTrue(is_calendar_schema_missing_error(
            RuntimeError("PGRST205: Could not find the table 'public.calendars' in the schema cache")
        ))
        self.assertFalse(is_calendar_schema_missing_error(RuntimeError("database connection timed out")))

    def test_disabled_calendar_falls_back_to_reservations(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active",
            user={"timezone": "Asia/Jerusalem"},
        )
        client = SimpleNamespace(table=lambda name: Query([]))
        with patch.object(calendar_routes, "service_supabase", client), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "false"}, clear=False):
            payload = calendar_routes.calendar_bootstrap(
                object(), object(),
                datetime(2026, 7, 1, tzinfo=timezone.utc),
                datetime(2026, 7, 8, tzinfo=timezone.utc),
            )
        self.assertTrue(payload["success"])
        self.assertFalse(payload["calendar_features_available"])
        self.assertEqual(payload["events"], [])

    def test_disabled_calendar_rejects_direct_feature_routes(self):
        with patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "false"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                calendar_routes.require_calendar_feature()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["code"], "calendar_feature_disabled")

    def test_enabled_calendar_missing_schema_returns_controlled_503(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active",
            user={"timezone": "UTC"},
        )
        with patch.object(calendar_routes, "require_active_tenant_member", return_value=context), patch.object(
            calendar_routes, "_calendar_workspace_payload",
            side_effect=RuntimeError("PGRST205: Could not find the table public.calendars in the schema cache"),
        ), patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                calendar_routes.calendar_bootstrap(
                    object(), object(),
                    datetime(2026, 7, 1, tzinfo=timezone.utc),
                    datetime(2026, 7, 8, tzinfo=timezone.utc),
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["code"], "calendar_schema_unavailable")

    def test_enabled_calendar_bootstrap_reuses_private_user_range_cache(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active",
            user={"timezone": "UTC"},
        )
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        end = datetime(2026, 7, 8, tzinfo=timezone.utc)
        payload = {
            "success": True,
            "calendars": [],
            "events": [],
            "tasks": [],
            "connections": [],
        }
        first_response = SimpleNamespace(headers={})
        second_response = SimpleNamespace(headers={})
        with patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "_calendar_workspace_payload", return_value=payload
        ) as loader, patch.object(
            calendar_routes, "reservation_events_for_range", return_value=[]
        ), patch.dict(
            os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
        ):
            first = calendar_routes.calendar_bootstrap(object(), first_response, start, end)
            second = calendar_routes.calendar_bootstrap(object(), second_response, start, end)

        self.assertEqual(first, second)
        self.assertEqual(loader.call_count, 1)
        self.assertEqual(first_response.headers["X-Calendar-Cache"], "miss")
        self.assertEqual(second_response.headers["X-Calendar-Cache"], "hit")
        self.assertEqual(second_response.headers["Cache-Control"], "private, no-store")

    def test_cached_bootstrap_refreshes_reservations_on_every_request(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active",
            user={"timezone": "UTC"},
        )
        start = datetime(2026, 8, 1, tzinfo=timezone.utc)
        end = datetime(2026, 9, 1, tzinfo=timezone.utc)
        payload = {
            "success": True, "calendars": [], "events": [], "tasks": [],
            "connections": [],
        }
        reservation = {
            "id": "reservation::booking-1",
            "source_type": "reservation",
            "calendar_id": "reservations",
            "title": "New reservation request",
            "starts_at": "2026-08-12T07:30:00+00:00",
            "ends_at": "2026-08-12T08:00:00+00:00",
        }
        with patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "_calendar_workspace_payload", return_value=payload
        ) as loader, patch.object(
            calendar_routes, "reservation_events_for_range",
            side_effect=[[], [reservation]],
        ), patch.dict(
            os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
        ):
            first = calendar_routes.calendar_bootstrap(
                object(), SimpleNamespace(headers={}), start, end
            )
            second_response = SimpleNamespace(headers={})
            second = calendar_routes.calendar_bootstrap(
                object(), second_response, start, end
            )

        self.assertEqual(first["events"], [])
        self.assertEqual(second["events"], [reservation])
        self.assertEqual(loader.call_count, 1)
        self.assertEqual(second_response.headers["X-Calendar-Cache"], "hit")

        bypass_response = SimpleNamespace(headers={})
        bypass_request = SimpleNamespace(
            headers={"X-Calendar-Cache-Bypass": "1"}
        )
        with patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "_calendar_workspace_payload", return_value=payload
        ) as bypass_loader, patch.object(
            calendar_routes, "reservation_events_for_range", return_value=[reservation]
        ), patch.dict(
            os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
        ):
            calendar_routes.calendar_bootstrap(
                bypass_request, bypass_response, start, end
            )
        self.assertEqual(bypass_loader.call_count, 1)
        self.assertEqual(bypass_response.headers["X-Calendar-Cache"], "miss")

    def test_calendar_range_requires_ordered_bounded_timezone_aware_values(self):
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        end = datetime(2026, 7, 8, tzinfo=timezone.utc)
        self.assertEqual(parse_range(start, end), (start, end))
        for invalid in ((end, start), (datetime(2026, 7, 1), datetime(2026, 7, 2))):
            with self.subTest(invalid=invalid), self.assertRaises(HTTPException):
                parse_range(*invalid)

    def test_timezone_validation_uses_iana_names(self):
        self.assertEqual(validate_timezone("Asia/Jerusalem"), "Asia/Jerusalem")
        with self.assertRaises(HTTPException):
            validate_timezone("Definitely/Not-A-Timezone")

    def test_recurring_events_expand_and_respect_exclusions(self):
        row = {
            "id": "event-1", "starts_at": "2026-07-20T09:00:00+00:00",
            "ends_at": "2026-07-20T10:00:00+00:00", "recurrence_rule": "FREQ=DAILY;COUNT=4",
            "recurrence_exclusions": ["2026-07-22T09:00:00+00:00"],
        }
        events = expand_events([row], datetime(2026, 7, 20, tzinfo=timezone.utc), datetime(2026, 7, 25, tzinfo=timezone.utc))
        self.assertEqual([event["occurrence_start"] for event in events], [
            "2026-07-20T09:00:00+00:00", "2026-07-21T09:00:00+00:00", "2026-07-23T09:00:00+00:00",
        ])

    def test_reservations_are_read_only_calendar_projections(self):
        event = reservation_payload({
            "id": "reservation-1", "reservation_title": "Consultation",
            "starts_at": "2026-07-22T08:00:00+00:00", "ends_at": "2026-07-22T09:00:00+00:00",
            "status": "confirmed",
        })
        self.assertEqual(event["id"], "reservation::reservation-1")
        self.assertTrue(event["read_only"])

    def test_start_only_reservations_receive_a_visible_calendar_duration(self):
        event = reservation_payload({
            "id": "reservation-legacy",
            "starts_at": "2026-07-22T08:00:00+00:00",
            "ends_at": None,
        })

        self.assertEqual(event["ends_at"], "2026-07-22T08:30:00+00:00")

    def test_legacy_reservation_payload_is_projected_into_calendar_range(self):
        context = SimpleNamespace(tenant_id=7, role="owner")
        rows = [{
            "id": "reservation-legacy",
            "tenant_id": 7,
            "reservation_title": "Existing consultation",
            "starts_at": None,
            "ends_at": None,
            "timezone": None,
            "created_at": "2026-07-20T08:00:00+00:00",
            "payload": {
                "date": "2026-07-22",
                "time": "11:00",
                "timezone": "Asia/Jerusalem",
            },
        }]
        client = SimpleNamespace(table=lambda _name: Query(rows))

        with patch.object(calendar_routes, "service_supabase", client):
            events = reservation_events_for_range(
                context,
                datetime(2026, 7, 22, tzinfo=timezone.utc),
                datetime(2026, 7, 23, tzinfo=timezone.utc),
            )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "Existing consultation")
        self.assertEqual(events[0]["calendar_id"], "reservations")
        self.assertEqual(events[0]["starts_at"], "2026-07-22T11:00:00+03:00")
        self.assertEqual(events[0]["ends_at"], "2026-07-22T11:30:00+03:00")

    def test_ics_text_is_escaped_without_leaking_delimiters(self):
        self.assertEqual(ics_escape("One, two; three\\four\nfive"), "One\\, two\\; three\\\\four\\nfive")

    def test_event_payload_keeps_non_recurring_identity(self):
        row = {"id": "event-1", "title": "Planning"}
        self.assertEqual(event_payload(row)["id"], "event-1")
        self.assertEqual(event_payload(row)["source_label"], "Madar")

    def test_future_recurring_edit_replaces_count_with_safe_until_boundary(self):
        boundary = datetime(2026, 8, 1, 8, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(truncated_recurrence_rule("FREQ=WEEKLY;COUNT=12", boundary), "FREQ=WEEKLY;UNTIL=20260801T085959Z")

    def test_ics_parser_unfolds_lines_and_reads_utc_dates(self):
        content = (
            "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:test-1\r\n"
            "DTSTART:20260722T090000Z\r\nDTEND:20260722T100000Z\r\n"
            "SUMMARY:Long planning \r\n session\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        events = parse_ics_events(content)
        self.assertEqual(events[0]["SUMMARY"], "Long planning session")
        self.assertEqual(parse_ics_datetime(events[0]["DTSTART"]), datetime(2026, 7, 22, 9, tzinfo=timezone.utc))

    def test_task_recurrence_accepts_supported_rules(self):
        for value, expected in (("FREQ=DAILY", "FREQ=DAILY"), ("freq=weekly", "FREQ=WEEKLY"), ("FREQ=MONTHLY", "FREQ=MONTHLY")):
            with self.subTest(value=value):
                self.assertEqual(TaskWrite(title="Review", recurrence_rule=value).recurrence_rule, expected)

    def test_task_recurrence_rejects_unsupported_rules(self):
        with self.assertRaises(ValueError):
            TaskWrite(title="Review", recurrence_rule="FREQ=YEARLY")

    def test_task_schedule_requires_timezone_and_ordered_values(self):
        scheduled_start = datetime(2026, 7, 23, 9, tzinfo=timezone.utc)
        scheduled_end = datetime(2026, 7, 23, 10, tzinfo=timezone.utc)
        task = TaskWrite(
            title="Review",
            due_at=scheduled_end,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
        self.assertEqual(task.scheduled_start, scheduled_start)
        for values in (
            {"scheduled_start": datetime(2026, 7, 23, 9)},
            {"scheduled_end": scheduled_end},
            {"scheduled_start": scheduled_end, "scheduled_end": scheduled_start},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                TaskWrite(title="Review", **values)

    def test_task_create_uses_default_calendar_and_preserves_schedule(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active"
        )
        inserted = []

        class InsertQuery:
            def insert(self, row):
                inserted.append(dict(row))
                return self
            def execute(self):
                return SimpleNamespace(data=[{"id": "task-created", **inserted[-1]}])

        payload = TaskWrite(
            title="Review",
            scheduled_start=datetime(2026, 7, 23, 9, tzinfo=timezone.utc),
            scheduled_end=datetime(2026, 7, 23, 10, tzinfo=timezone.utc),
        )
        client = SimpleNamespace(table=lambda _name: InsertQuery())
        with patch.object(calendar_routes, "service_supabase", client), patch.object(
            calendar_routes, "require_calendar_feature"
        ), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "ensure_default_calendar",
            return_value={"id": "calendar-default"},
        ), patch.object(
            calendar_routes, "require_calendar_access"
        ) as require_access, patch.object(
            calendar_routes, "validate_active_task_owner", return_value=12
        ), patch.object(
            calendar_routes, "validate_project_reference", return_value=None
        ), patch.object(
            calendar_routes, "sync_task_reminder"
        ), patch.object(
            calendar_routes, "record_calendar_audit"
        ):
            result = calendar_routes.create_task(payload, object(), object())

        self.assertTrue(result["success"])
        self.assertEqual(inserted[0]["calendar_id"], "calendar-default")
        self.assertEqual(inserted[0]["scheduled_start"], "2026-07-23T09:00:00Z")
        require_access.assert_called_once_with(context, "calendar-default", "manage_tasks")

    def test_workspace_tasks_include_only_authorized_unassigned_work(self):
        rows = [
            {
                "id": "calendar-task", "tenant_id": 7, "calendar_id": "calendar-1",
                "owner_user_id": 20, "status": "todo", "due_at": None,
            },
            {
                "id": "own-unassigned", "tenant_id": 7, "calendar_id": None,
                "owner_user_id": 12, "status": "todo", "due_at": None,
            },
            {
                "id": "other-unassigned", "tenant_id": 7, "calendar_id": None,
                "owner_user_id": 20, "status": "todo", "due_at": None,
            },
            {
                "id": "cross-tenant", "tenant_id": 8, "calendar_id": None,
                "owner_user_id": 12, "status": "todo", "due_at": None,
            },
            {
                "id": "cancelled", "tenant_id": 7, "calendar_id": None,
                "owner_user_id": 12, "status": "cancelled", "due_at": None,
            },
            {
                "id": "linked-cancelled", "tenant_id": 7, "calendar_id": "calendar-1",
                "owner_user_id": 12, "status": "cancelled", "due_at": None,
                "sync_event_id": "provider-event-1",
            },
        ]
        client = SimpleNamespace(table=lambda _name: Query(rows))
        member = SimpleNamespace(tenant_id=7, user_id=12, role="member")
        admin = SimpleNamespace(tenant_id=7, user_id=99, role="admin")
        with patch.object(calendar_routes, "service_supabase", client):
            member_rows = calendar_routes.workspace_task_rows(member, ["calendar-1"])
            admin_rows = calendar_routes.workspace_task_rows(admin, ["calendar-1"])
            linked_event_ids = calendar_routes.workspace_linked_task_event_ids(
                member, ["calendar-1"]
            )

        self.assertEqual(
            {row["id"] for row in member_rows},
            {"calendar-task", "own-unassigned"},
        )
        self.assertEqual(
            {row["id"] for row in admin_rows},
            {"calendar-task", "own-unassigned", "other-unassigned"},
        )
        self.assertEqual(linked_event_ids, {"provider-event-1"})

    def test_archive_task_preserves_workflow_status(self):
        context = SimpleNamespace(tenant_id=7, user_id=12, role="member")
        existing = {
            "id": "task-1", "tenant_id": 7, "calendar_id": "calendar-1",
            "owner_user_id": 12, "status": "todo", "version": 3,
        }

        class UpdateQuery:
            def __init__(self):
                self.values = {}
            def update(self, values):
                self.values = dict(values)
                return self
            def eq(self, *_args):
                return self
            def is_(self, *_args):
                return self
            def execute(self):
                return SimpleNamespace(data=[{**existing, **self.values}])

        query = UpdateQuery()
        client = SimpleNamespace(table=lambda _name: query)
        with patch.object(calendar_routes, "service_supabase", client), patch.object(
            calendar_routes, "require_calendar_feature"
        ), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "tenant_task", return_value=existing
        ), patch.object(
            calendar_routes, "require_task_access"
        ), patch.object(
            calendar_routes, "sync_task_reminder"
        ) as sync_reminder, patch.object(
            calendar_routes, "record_calendar_audit"
        ) as audit:
            result = calendar_routes.archive_task(
                "task-1", object(), object(), expected_version=3
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["status"], "todo")
        self.assertIsNotNone(result["task"]["archived_at"])
        self.assertEqual(result["task"]["version"], 4)
        sync_reminder.assert_called_once()
        self.assertEqual(sync_reminder.call_args.args[0]["status"], "todo")
        self.assertIsNotNone(sync_reminder.call_args.args[0]["archived_at"])
        self.assertIsNone(sync_reminder.call_args.args[1])
        self.assertEqual(audit.call_args.args[2], "calendar.task_archived")

    def test_archived_task_api_uses_archive_state_and_tenant_scope(self):
        rows = [
            {"id": "linked", "tenant_id": 7, "calendar_id": "calendar-1", "owner_user_id": 12, "status": "done", "archived_at": "2026-08-10T12:00:00Z"},
            {"id": "own-unassigned", "tenant_id": 7, "calendar_id": None, "owner_user_id": 12, "status": "in_progress", "archived_at": "2026-08-10T11:00:00Z"},
            {"id": "other-unassigned", "tenant_id": 7, "calendar_id": None, "owner_user_id": 20, "status": "done", "archived_at": "2026-08-10T10:00:00Z"},
            {"id": "cancelled-only", "tenant_id": 7, "calendar_id": "calendar-1", "owner_user_id": 12, "status": "cancelled", "archived_at": None},
            {"id": "cross-tenant", "tenant_id": 8, "calendar_id": "calendar-1", "owner_user_id": 12, "status": "done", "archived_at": "2026-08-10T13:00:00Z"},
        ]
        context = SimpleNamespace(tenant_id=7, user_id=12, role="member")
        client = SimpleNamespace(table=lambda _name: Query(rows))
        accessible = [SimpleNamespace(role="viewer", calendar={"id": "calendar-1"})]
        with patch.object(calendar_routes, "service_supabase", client), patch.object(
            calendar_routes, "require_calendar_feature"
        ), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "list_accessible_calendars", return_value=accessible
        ):
            result = calendar_routes.list_archived_tasks(object(), object())

        tasks = {task["id"]: task for task in result["tasks"]}
        self.assertEqual(set(tasks), {"linked", "own-unassigned"})
        self.assertEqual(tasks["linked"]["status"], "done")
        self.assertEqual(tasks["own-unassigned"]["status"], "in_progress")

    def test_recurring_task_reminder_rolls_forward_after_delivery(self):
        next_time = next_task_reminder_time({
            "task_recurrence_rule": "FREQ=WEEKLY", "task_recurrence_start": "2026-07-22T09:00:00+00:00",
            "scheduled_for": "2026-07-22T08:50:00+00:00", "minutes_before": 10,
        })
        self.assertEqual(next_time, "2026-07-29T08:50:00+00:00")

    def test_indirect_dependency_cycles_are_detected(self):
        rows = [
            {"task_id": "a", "depends_on_task_id": "b", "tenant_id": 7},
            {"task_id": "b", "depends_on_task_id": "c", "tenant_id": 7},
            {"task_id": "c", "depends_on_task_id": "d", "tenant_id": 7},
            {"task_id": "d", "depends_on_task_id": "e", "tenant_id": 7},
        ]
        client = SimpleNamespace(table=lambda _name: Query(rows))
        with patch.object(calendar_routes, "service_supabase", client):
            self.assertTrue(dependency_would_cycle(7, "a", "a"))
            self.assertTrue(dependency_would_cycle(7, "b", "a"))
            self.assertTrue(dependency_would_cycle(7, "c", "a"))
            self.assertTrue(dependency_would_cycle(7, "e", "a"))
            self.assertFalse(dependency_would_cycle(7, "f", "a"))

    def test_task_owner_must_be_active_in_current_tenant(self):
        tables = {
            "tenant_memberships": [{"tenant_id": 7, "user_id": 20, "status": "active"}],
            "users": [{"id": 20, "account_status": "active"}],
        }
        client = SimpleNamespace(table=lambda name: Query(tables[name]))
        context = SimpleNamespace(tenant_id=7, user_id=12)
        with patch.object(calendar_routes, "service_supabase", client):
            self.assertEqual(calendar_routes.validate_active_task_owner(context, 20), 20)
            with self.assertRaises(HTTPException):
                calendar_routes.validate_active_task_owner(context, 21)

    def test_project_reference_is_tenant_bound_and_not_archived(self):
        tables = {"builder_projects": [
            {"id": "project-active", "tenant_id": 7, "status": "draft"},
            {"id": "project-archived", "tenant_id": 7, "status": "archived"},
            {"id": "project-cross", "tenant_id": 8, "status": "published"},
        ]}
        client = SimpleNamespace(table=lambda name: Query(tables[name]))
        context = SimpleNamespace(tenant_id=7)
        with patch.object(calendar_routes, "service_supabase", client):
            self.assertEqual(calendar_routes.validate_project_reference(context, "project-active"), "project-active")
            for project_id in ("project-archived", "project-cross", "missing"):
                with self.subTest(project_id=project_id), self.assertRaises(HTTPException):
                    calendar_routes.validate_project_reference(context, project_id)

    def test_repeated_oauth_connection_creation_reuses_pending_record(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active",
            user={"timezone": "UTC"},
        )
        existing = {
            "id": "connection-pending",
            "local_calendar_id": "calendar-pending",
            "tenant_id": 7,
            "user_id": 12,
            "provider": "google",
            "account_label": "Google Calendar",
            "direction": "read",
            "status": "setup_required",
            "created_at": "2026-07-23T10:00:00+00:00",
        }
        with patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(calendar_routes, "require_calendar_creator"), patch.object(
            calendar_routes, "reusable_pending_connection", return_value=existing
        ), patch.object(calendar_routes, "record_calendar_audit") as audit:
            result = calendar_routes.create_sync_connection(
                calendar_routes.ConnectionWrite(provider="google"),
                object(),
                object(),
            )
        self.assertTrue(result["reused"])
        self.assertEqual(result["connection"]["id"], existing["id"])
        audit.assert_called_once()

    def test_pending_reuse_removes_only_bounded_stale_credential_free_rows(self):
        rows = [
            {
                "id": "fresh",
                "tenant_id": 7,
                "user_id": 12,
                "provider": "google",
                "direction": "read",
                "status": "setup_required",
                "encrypted_credentials": None,
                "created_at": "2026-07-23T11:55:00+00:00",
            },
            {
                "id": "stale",
                "tenant_id": 7,
                "user_id": 12,
                "provider": "google",
                "direction": "read",
                "status": "setup_required",
                "encrypted_credentials": None,
                "created_at": "2026-07-23T10:00:00+00:00",
            },
        ]

        class PendingQuery:
            def __init__(self, client):
                self.client = client
                self.operation = "select"
                self.selected = list(client.rows)
                self.filters = {}
            def select(self, *_args): return self
            def delete(self): self.operation = "delete"; return self
            def eq(self, field, value):
                self.filters[field] = value
                self.selected = [row for row in self.selected if row.get(field) == value]
                return self
            def is_(self, field, value):
                if value == "null":
                    self.selected = [row for row in self.selected if row.get(field) is None]
                return self
            def lt(self, field, value):
                self.selected = [
                    row for row in self.selected
                    if str(row.get(field) or "") < str(value)
                ]
                return self
            def order(self, *_args, **_kwargs): return self
            def limit(self, count): self.selected = self.selected[:count]; return self
            def execute(self):
                if self.operation == "delete":
                    deleted = list(self.selected)
                    self.client.deleted.extend(row["id"] for row in deleted)
                    return SimpleNamespace(data=deleted)
                return SimpleNamespace(data=list(self.selected))

        client = SimpleNamespace(rows=rows, deleted=[])
        client.table = lambda _name: PendingQuery(client)
        context = SimpleNamespace(tenant_id=7, user_id=12)
        with patch.object(calendar_routes, "service_supabase", client), patch.object(
            calendar_routes,
            "utc_now",
            return_value=datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
        ), patch.object(
            calendar_routes, "remove_empty_connection_calendar", return_value=True
        ), patch.object(calendar_routes, "record_calendar_audit") as audit:
            reusable = calendar_routes.reusable_pending_connection(
                context,
                calendar_routes.ConnectionWrite(provider="google", direction="read"),
                object(),
            )
        self.assertEqual(reusable["id"], "fresh")
        self.assertEqual(client.deleted, ["stale"])
        audit.assert_called_once()

    def test_incomplete_connection_removal_is_separate_from_disconnect(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="owner", membership_status="active",
        )
        incomplete = {
            "id": "connection-pending",
            "tenant_id": 7,
            "local_calendar_id": "calendar-pending",
            "provider": "google",
            "status": "setup_required",
            "encrypted_credentials": None,
        }

        class DeleteQuery:
            def delete(self): return self
            def eq(self, *_args): return self
            def in_(self, *_args): return self
            def is_(self, *_args): return self
            def execute(self): return SimpleNamespace(data=[{"id": "connection-pending"}])

        client = SimpleNamespace(table=lambda _name: DeleteQuery())
        with patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(calendar_routes, "tenant_connection", return_value=incomplete), patch.object(
            calendar_routes, "require_calendar_access"
        ), patch.object(calendar_routes, "service_supabase", client), patch.object(
            calendar_routes, "remove_empty_connection_calendar", return_value=True
        ), patch.object(
            calendar_routes, "record_calendar_audit"
        ) as audit:
            result = calendar_routes.remove_incomplete_sync_connection(
                incomplete["id"], object(), object()
            )
        self.assertEqual(result, {"success": True, "removed": True})
        audit.assert_called_once()

    def test_connected_connection_cannot_use_incomplete_removal(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="owner", membership_status="active",
        )
        connected = {
            "id": "connection-connected",
            "tenant_id": 7,
            "local_calendar_id": "calendar-connected",
            "provider": "google",
            "status": "connected",
            "encrypted_credentials": "encrypted",
        }
        with patch.dict(os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(calendar_routes, "tenant_connection", return_value=connected), patch.object(
            calendar_routes, "require_calendar_access"
        ):
            with self.assertRaises(HTTPException) as raised:
                calendar_routes.remove_incomplete_sync_connection(
                    connected["id"], object(), object()
                )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"], "calendar_connection_requires_disconnect"
        )

    def test_empty_connection_calendar_cleanup_preserves_any_calendar_with_content(self):
        connection = {
            "tenant_id": 7,
            "user_id": 12,
            "local_calendar_id": "calendar-pending",
        }

        class TableQuery:
            def __init__(self, client, table_name):
                self.client = client
                self.table_name = table_name
                self.rows = list(client.rows.get(table_name, []))
                self.operation = "select"
            def select(self, *_args): return self
            def delete(self): self.operation = "delete"; return self
            def eq(self, field, value):
                self.rows = [row for row in self.rows if row.get(field) == value]
                return self
            def limit(self, count): self.rows = self.rows[:count]; return self
            def execute(self):
                if self.operation == "delete":
                    self.client.deleted.extend((self.table_name, row["id"]) for row in self.rows)
                return SimpleNamespace(data=list(self.rows))

        rows = {
            "calendars": [{
                "id": "calendar-pending", "tenant_id": 7,
                "owner_user_id": 12, "is_default": False,
            }],
            "calendar_events": [{"id": "event", "tenant_id": 7, "calendar_id": "calendar-pending"}],
            "calendar_tasks": [],
            "calendar_sync_connections": [],
        }
        client = SimpleNamespace(rows=rows, deleted=[])
        client.table = lambda name: TableQuery(client, name)
        with patch.object(calendar_routes, "service_supabase", client):
            self.assertFalse(calendar_routes.remove_empty_connection_calendar(connection))
        self.assertEqual(client.deleted, [])

        client.rows["calendar_events"] = []
        with patch.object(calendar_routes, "service_supabase", client):
            self.assertTrue(calendar_routes.remove_empty_connection_calendar(connection))
        self.assertEqual(client.deleted, [("calendars", "calendar-pending")])

    def test_read_only_connection_rejects_task_provider_sync(self):
        context = SimpleNamespace(tenant_id=7, user_id=12)
        task = {
            "id": "task",
            "tenant_id": 7,
            "scheduled_start": "2026-07-23T09:00:00+00:00",
        }
        connection = {
            "id": "connection",
            "tenant_id": 7,
            "local_calendar_id": "calendar",
            "provider": "google",
            "direction": "read",
            "status": "connected",
            "encrypted_credentials": "encrypted",
        }
        with patch.object(
            calendar_routes, "tenant_connection", return_value=connection
        ), patch.object(calendar_routes, "require_calendar_access"):
            with self.assertRaises(HTTPException) as raised:
                calendar_routes.task_sync_connection(
                    context, task, connection["id"]
                )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"], "calendar_write_access_required"
        )

    def test_task_sync_prepares_local_event_and_enqueues_without_provider_call(self):
        context = SimpleNamespace(
            tenant_id=7,
            user_id=12,
            user={"timezone": "UTC"},
        )
        task = {
            "id": "task",
            "tenant_id": 7,
            "calendar_id": "calendar",
            "title": "Synthetic",
            "description": "",
            "scheduled_start": "2026-07-23T09:00:00+00:00",
            "scheduled_end": "2026-07-23T10:00:00+00:00",
            "version": 3,
            "sync_event_id": None,
        }
        connection = {
            "id": "connection",
            "tenant_id": 7,
            "local_calendar_id": "calendar",
            "provider": "google",
        }

        class Query:
            def __init__(self, table):
                self.table = table
                self.action = "select"
                self.payload = None
            def select(self, *_args): self.action = "select"; return self
            def eq(self, *_args): return self
            def is_(self, *_args): return self
            def limit(self, *_args): return self
            def insert(self, payload): self.action = "insert"; self.payload = payload; return self
            def update(self, payload): self.action = "update"; self.payload = payload; return self
            def execute(self):
                if self.table == "calendar_events" and self.action == "insert":
                    return SimpleNamespace(data=[{"id": "event", **self.payload}])
                if self.table == "calendar_tasks" and self.action == "update":
                    return SimpleNamespace(data=[{**task, **self.payload}])
                return SimpleNamespace(data=[])

        client = SimpleNamespace(table=lambda table: Query(table))
        with patch.object(
            calendar_routes, "service_supabase", client
        ), patch.object(
            calendar_routes, "enqueue_task_sync", return_value={"id": "job"}
        ) as enqueue, patch.object(
            calendar_routes, "sync_connection"
        ) as provider_sync:
            result = calendar_routes.queue_task_to_provider(
                context, task, connection
            )
        self.assertEqual(result["sync_status"], "pending")
        enqueue.assert_called_once()
        provider_sync.assert_not_called()

    def test_unsynchronized_task_deletion_is_authorized_audited_and_controlled(self):
        context = SimpleNamespace(
            tenant_id=7, user_id=12, role="member", membership_status="active"
        )
        task = {
            "id": "task",
            "tenant_id": 7,
            "calendar_id": "calendar",
            "owner_user_id": 12,
            "sync_connection_id": None,
            "sync_event_id": None,
        }

        class DeleteQuery:
            def delete(self): return self
            def eq(self, *_args): return self
            def execute(self): return SimpleNamespace(data=[{"id": "task"}])

        client = SimpleNamespace(table=lambda _name: DeleteQuery())
        with patch.dict(
            os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
        ), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "tenant_task", return_value=task
        ), patch.object(
            calendar_routes, "require_task_access"
        ) as require_access, patch.object(
            calendar_routes, "service_supabase", client
        ), patch.object(
            calendar_routes, "record_calendar_audit"
        ) as audit:
            result = calendar_routes.delete_task(
                task["id"], object(), object(), mode="local_only"
            )
        self.assertTrue(result["success"])
        self.assertFalse(result["provider_event_deleted"])
        require_access.assert_called_once_with(context, task)
        audit.assert_called_once()

    def test_synchronized_task_requires_explicit_remote_delete_mode(self):
        context = SimpleNamespace(tenant_id=7, user_id=12, role="owner")
        task = {
            "id": "task",
            "tenant_id": 7,
            "calendar_id": "calendar",
            "sync_connection_id": "connection",
            "sync_event_id": "event",
        }

        class DeleteQuery:
            def delete(self): return self
            def eq(self, *_args): return self
            def execute(self): return SimpleNamespace(data=[{"id": "task"}])

        with patch.dict(
            os.environ, {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
        ), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "tenant_task", return_value=task
        ), patch.object(
            calendar_routes, "require_task_access"
        ), patch.object(
            calendar_routes, "service_supabase",
            SimpleNamespace(table=lambda _name: DeleteQuery()),
        ), patch.object(
            calendar_routes, "enqueue_task_sync"
        ) as enqueue, patch.object(
            calendar_routes, "record_calendar_audit"
        ):
            result = calendar_routes.delete_task(
                task["id"], object(), object(), mode="local_only"
            )
        self.assertTrue(result["success"])
        enqueue.assert_not_called()

    def test_task_payload_hides_internal_event_link(self):
        payload = calendar_routes.safe_task_payload({
            "id": "task",
            "sync_connection_id": "connection",
            "sync_event_id": "internal-event",
            "sync_status": "synced",
            "sync_error_code": "private-provider-detail",
        })
        self.assertTrue(payload["is_synchronized"])
        self.assertNotIn("sync_event_id", payload)
        self.assertNotIn("sync_error_code", payload)


if __name__ == "__main__":
    unittest.main()
