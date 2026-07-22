from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
import routes.calendar_routes as calendar_routes

from routes.calendar_routes import (
    TaskWrite,
    event_payload,
    expand_events,
    ics_escape,
    is_calendar_schema_missing_error,
    parse_range,
    parse_ics_events,
    parse_ics_datetime,
    reservation_payload,
    truncated_recurrence_rule,
    validate_timezone,
)
from services.calendar_reminder_service import next_task_reminder_time


def test_calendar_schema_missing_error_is_detected_without_masking_other_failures():
    assert is_calendar_schema_missing_error(
        RuntimeError("PGRST205: Could not find the table 'public.calendars' in the schema cache")
    )
    assert not is_calendar_schema_missing_error(RuntimeError("database connection timed out"))


def test_calendar_bootstrap_falls_back_to_reservations_when_schema_is_missing(monkeypatch):
    class Query:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: self

        def execute(self):
            return SimpleNamespace(data=[])

    class Supabase:
        def table(self, name):
            assert name == "builder_reservations"
            return Query()

    context = SimpleNamespace(
        tenant_id=7,
        user_id=12,
        user={"timezone": "Asia/Jerusalem"},
    )
    monkeypatch.setattr(calendar_routes, "service_supabase", Supabase())
    monkeypatch.setattr(
        calendar_routes,
        "require_active_tenant_member",
        lambda _request, _response: context,
    )

    def raise_missing_schema(_context, _start, _end):
        raise RuntimeError(
            "PGRST205: Could not find the table 'public.calendars' in the schema cache"
        )

    monkeypatch.setattr(calendar_routes, "_calendar_workspace_payload", raise_missing_schema)
    payload = calendar_routes.calendar_bootstrap(
        object(),
        object(),
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 8, tzinfo=timezone.utc),
    )

    assert payload["success"] is True
    assert payload["calendar_features_available"] is False
    assert payload["events"] == []
    assert payload["viewer_timezone"] == "Asia/Jerusalem"


def test_calendar_range_requires_ordered_bounded_timezone_aware_values():
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 8, tzinfo=timezone.utc)
    assert parse_range(start, end) == (start, end)

    with pytest.raises(HTTPException):
        parse_range(end, start)

    with pytest.raises(HTTPException):
        parse_range(datetime(2026, 7, 1), datetime(2026, 7, 2))


def test_timezone_validation_uses_iana_names():
    assert validate_timezone("Asia/Jerusalem") == "Asia/Jerusalem"
    with pytest.raises(HTTPException):
        validate_timezone("Definitely/Not-A-Timezone")


def test_recurring_events_expand_and_respect_exclusions():
    row = {
        "id": "event-1",
        "starts_at": "2026-07-20T09:00:00+00:00",
        "ends_at": "2026-07-20T10:00:00+00:00",
        "recurrence_rule": "FREQ=DAILY;COUNT=4",
        "recurrence_exclusions": ["2026-07-22T09:00:00+00:00"],
    }
    events = expand_events(
        [row],
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert [event["occurrence_start"] for event in events] == [
        "2026-07-20T09:00:00+00:00",
        "2026-07-21T09:00:00+00:00",
        "2026-07-23T09:00:00+00:00",
    ]
    assert all(event["series_id"] == "event-1" for event in events)


def test_reservations_are_read_only_calendar_projections():
    event = reservation_payload({
        "id": "reservation-1",
        "reservation_title": "Consultation",
        "starts_at": "2026-07-22T08:00:00+00:00",
        "ends_at": "2026-07-22T09:00:00+00:00",
        "status": "confirmed",
    })
    assert event["id"] == "reservation::reservation-1"
    assert event["calendar_id"] == "reservations"
    assert event["read_only"] is True


def test_ics_text_is_escaped_without_leaking_delimiters():
    assert ics_escape("One, two; three\\four\nfive") == "One\\, two\\; three\\\\four\\nfive"


def test_event_payload_keeps_non_recurring_identity():
    row = {"id": "event-1", "title": "Planning"}
    assert event_payload(row)["id"] == "event-1"
    assert event_payload(row)["source_label"] == "Madar"


def test_future_recurring_edit_replaces_count_with_safe_until_boundary():
    boundary = datetime(2026, 8, 1, 8, 59, 59, tzinfo=timezone.utc)
    assert truncated_recurrence_rule("FREQ=WEEKLY;COUNT=12", boundary) == (
        "FREQ=WEEKLY;UNTIL=20260801T085959Z"
    )


def test_ics_parser_unfolds_lines_and_reads_utc_dates():
    content = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:test-1\r\n"
        "DTSTART:20260722T090000Z\r\nDTEND:20260722T100000Z\r\n"
        "SUMMARY:Long planning \r\n session\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    events = parse_ics_events(content)
    assert events[0]["SUMMARY"] == "Long planning session"
    assert parse_ics_datetime(events[0]["DTSTART"]) == datetime(
        2026, 7, 22, 9, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("FREQ=DAILY", "FREQ=DAILY"),
        ("freq=weekly", "FREQ=WEEKLY"),
        ("FREQ=MONTHLY", "FREQ=MONTHLY"),
    ],
)
def test_task_recurrence_accepts_supported_rules(value, expected):
    assert TaskWrite(title="Review", recurrence_rule=value).recurrence_rule == expected


def test_task_recurrence_rejects_unsupported_rules():
    with pytest.raises(ValueError):
        TaskWrite(title="Review", recurrence_rule="FREQ=YEARLY")


def test_recurring_task_reminder_rolls_forward_after_delivery():
    next_time = next_task_reminder_time({
        "task_recurrence_rule": "FREQ=WEEKLY",
        "task_recurrence_start": "2026-07-22T09:00:00+00:00",
        "scheduled_for": "2026-07-22T08:50:00+00:00",
        "minutes_before": 10,
    })
    assert next_time == "2026-07-29T08:50:00+00:00"
