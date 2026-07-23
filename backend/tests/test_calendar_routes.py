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
    reservation_payload,
    truncated_recurrence_rule,
    validate_timezone,
)
from services.calendar_reminder_service import next_task_reminder_time


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
    def lt(self, *_args): return self
    def gt(self, *_args): return self
    def limit(self, count):
        self.rows = self.rows[:count]
        return self
    def execute(self): return SimpleNamespace(data=self.rows)


class CalendarRouteTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
