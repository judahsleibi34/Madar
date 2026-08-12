import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from routes import calendar_routes
from services import calendar_connection_sync_queue_service as queue_service
from services import calendar_sync_service
from services.calendar_sync_service import CalendarSyncError
from workers import calendar_sync_worker


class Query:
    def __init__(self, database, name):
        self.database = database
        self.name = name
        self.rows = list(database.tables.setdefault(name, []))
        self.operation = "select"
        self.values = None

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def in_(self, field, values):
        self.rows = [row for row in self.rows if row.get(field) in values]
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def insert(self, values):
        self.operation = "insert"
        self.values = values
        return self

    def update(self, values):
        self.operation = "update"
        self.values = values
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        table = self.database.tables[self.name]
        if self.operation == "insert":
            values = self.values if isinstance(self.values, list) else [self.values]
            created = []
            for value in values:
                row = deepcopy(value)
                row.setdefault("id", f"{self.name}-{len(table) + 1}")
                table.append(row)
                created.append(deepcopy(row))
            return SimpleNamespace(data=created)
        if self.operation == "update":
            for row in self.rows:
                row.update(deepcopy(self.values))
            return SimpleNamespace(data=deepcopy(self.rows))
        if self.operation == "delete":
            selected = {id(row) for row in self.rows}
            self.database.tables[self.name] = [
                row for row in table if id(row) not in selected
            ]
            return SimpleNamespace(data=deepcopy(self.rows))
        return SimpleNamespace(data=deepcopy(self.rows))


class Database:
    def __init__(self, **tables):
        self.tables = {name: [deepcopy(row) for row in rows] for name, rows in tables.items()}
        self.rpc_calls = []
        self.rpc_result = [{"id": "job", "status": "pending"}]

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(data=deepcopy(self.rpc_result))
        )


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return deepcopy(self.payload)


class HttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, deepcopy(kwargs)))
        return self.responses.pop(0)


def google_event(remote_id="provider-event", **overrides):
    value = {
        "id": remote_id,
        "summary": "Synthetic fixture",
        "etag": "version-1",
        "updated": "2026-07-23T10:00:00Z",
        "start": {"dateTime": "2026-07-23T10:00:00Z", "timeZone": "UTC"},
        "end": {"dateTime": "2026-07-23T11:00:00Z", "timeZone": "UTC"},
    }
    value.update(overrides)
    return value


class CalendarInboundSyncTests(unittest.TestCase):
    def connection(self, **overrides):
        value = {
            "id": "connection",
            "tenant_id": 7,
            "user_id": 12,
            "local_calendar_id": "calendar",
            "provider": "google",
            "provider_calendar_id": "primary",
            "status": "connected",
            "direction": "read",
            "encrypted_credentials": "encrypted",
            "inbound_sync_enabled": True,
            "cursor_data": {},
        }
        value.update(overrides)
        return value

    def test_initial_sync_paginates_and_persists_only_final_sync_token(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        client = HttpClient(
            [
                Response(200, {"items": [google_event("one")], "nextPageToken": "page-2"}),
                Response(200, {"items": [google_event("two")], "nextSyncToken": "final-token"}),
            ]
        )
        with patch.object(calendar_sync_service, "service_supabase", database):
            counts, cursor = calendar_sync_service._google_sync(
                self.connection(), {"access_token": "redacted"}, client
            )
        self.assertEqual(counts["created"], 2)
        self.assertEqual(len(database.tables["calendar_events"]), 2)
        self.assertEqual(cursor, {"sync_token": "final-token"})
        self.assertEqual(client.calls[1][1]["params"]["pageToken"], "page-2")

    def test_repeated_incremental_event_updates_one_local_row(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        connection = self.connection()
        with patch.object(calendar_sync_service, "service_supabase", database):
            self.assertEqual(
                calendar_sync_service._upsert_external_event(
                    connection, google_event(), "google", None
                ),
                "created",
            )
            self.assertEqual(
                calendar_sync_service._upsert_external_event(
                    connection,
                    google_event(
                        etag="version-2",
                        start={"dateTime": "2026-07-23T12:00:00Z", "timeZone": "UTC"},
                        end={"dateTime": "2026-07-23T13:00:00Z", "timeZone": "UTC"},
                    ),
                    "google",
                    None,
                ),
                "updated",
            )
        self.assertEqual(len(database.tables["calendar_events"]), 1)
        self.assertEqual(
            database.tables["calendar_events"][0]["starts_at"],
            "2026-07-23T12:00:00+00:00",
        )

    def test_same_provider_identifier_is_isolated_by_connection_and_tenant(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        first = self.connection(id="connection-a", tenant_id=7, local_calendar_id="calendar-a")
        second = self.connection(id="connection-b", tenant_id=8, local_calendar_id="calendar-b")
        with patch.object(calendar_sync_service, "service_supabase", database):
            self.assertEqual(
                calendar_sync_service._upsert_external_event(first, google_event("shared"), "google", None),
                "created",
            )
            self.assertEqual(
                calendar_sync_service._upsert_external_event(second, google_event("shared"), "google", None),
                "created",
            )
        self.assertEqual(len(database.tables["calendar_events"]), 2)
        self.assertEqual({row["tenant_id"] for row in database.tables["calendar_events"]}, {7, 8})
        self.assertEqual(len({row["source_id"] for row in database.tables["calendar_events"]}), 2)


    def test_cancelled_provider_event_is_soft_deleted_not_duplicated(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        connection = self.connection()
        with patch.object(calendar_sync_service, "service_supabase", database):
            calendar_sync_service._upsert_external_event(
                connection, google_event(), "google", None
            )
            result = calendar_sync_service._upsert_external_event(
                connection,
                google_event(status="cancelled"),
                "google",
                None,
            )
        self.assertEqual(result, "deleted")
        self.assertEqual(len(database.tables["calendar_events"]), 1)
        self.assertIsNotNone(database.tables["calendar_events"][0]["deleted_at"])

    def test_all_day_timezone_and_attendees_are_normalized(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        with patch.object(calendar_sync_service, "service_supabase", database):
            calendar_sync_service._upsert_external_event(
                self.connection(),
                google_event(
                    start={"date": "2026-07-23"},
                    end={"date": "2026-07-24"},
                    attendees=[
                        {
                            "email": "fixture@example.test",
                            "responseStatus": "accepted",
                        }
                    ],
                ),
                "google",
                None,
            )
        event = database.tables["calendar_events"][0]
        self.assertTrue(event["all_day"])
        self.assertEqual(event["timezone"], "UTC")
        self.assertEqual(
            database.tables["calendar_event_attendees"][0]["response_status"],
            "accepted",
        )

    def test_invalid_sync_token_falls_back_to_bounded_full_sync(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        client = HttpClient(
            [
                Response(410, {}),
                Response(200, {"items": [], "nextSyncToken": "replacement"}),
            ]
        )
        with patch.object(calendar_sync_service, "service_supabase", database):
            _, cursor = calendar_sync_service._google_sync(
                self.connection(cursor_data={"sync_token": "expired"}),
                {"access_token": "redacted"},
                client,
            )
        self.assertEqual(cursor["sync_token"], "replacement")
        self.assertNotIn("syncToken", client.calls[1][1]["params"])
        self.assertIn("timeMin", client.calls[1][1]["params"])

    def test_partial_page_failure_keeps_imported_rows_without_advancing_cursor(self):
        database = Database(calendar_events=[], calendar_event_attendees=[])
        client = HttpClient(
            [
                Response(200, {"items": [google_event()], "nextPageToken": "page-2"}),
                Response(503, {}),
            ]
        )
        with patch.object(calendar_sync_service, "service_supabase", database):
            with self.assertRaises(CalendarSyncError) as raised:
                calendar_sync_service._google_sync(
                    self.connection(), {"access_token": "redacted"}, client
                )
        self.assertEqual(raised.exception.code, "provider_unavailable")
        self.assertEqual(len(database.tables["calendar_events"]), 1)

    def test_queue_enqueue_is_durable_and_marks_connection_pending(self):
        database = Database(calendar_sync_connections=[self.connection()])
        job = queue_service.enqueue_connection_sync(
            tenant_id=7, connection_id="connection", client=database
        )
        self.assertEqual(job["status"], "pending")
        self.assertEqual(
            database.rpc_calls[0][0], "enqueue_calendar_connection_sync_job"
        )
        self.assertEqual(
            database.tables["calendar_sync_connections"][0]["inbound_sync_status"],
            "pending",
        )

    def test_connection_worker_success_sets_aggregate_status(self):
        database = Database(calendar_sync_connections=[self.connection()])
        with patch.object(queue_service, "service_supabase", database), patch.object(
            queue_service,
            "sync_connection",
            return_value={"created": 1, "updated": 0},
        ):
            counts = queue_service.process_connection_sync_job(
                {"connection_id": "connection", "tenant_id": 7}
            )
        self.assertEqual(counts["created"], 1)
        self.assertEqual(
            database.tables["calendar_sync_connections"][0]["inbound_sync_status"],
            "synced",
        )

    def test_worker_retries_transient_failure_without_logging_content(self):
        job = {
            "id": "job",
            "connection_id": "connection",
            "tenant_id": 7,
            "attempts": 1,
            "max_attempts": 6,
        }
        finished = []
        with patch.object(
            calendar_sync_worker,
            "process_connection_sync_job",
            side_effect=CalendarSyncError(
                "provider_read_timeout", "private event content"
            ),
        ), patch.object(
            calendar_sync_worker,
            "mark_connection_sync_failed",
        ), patch.object(
            calendar_sync_worker,
            "finish_connection_sync_job",
            side_effect=lambda *_args, **kwargs: finished.append(kwargs),
        ):
            result = calendar_sync_worker.process_connection_job(job)
        self.assertEqual(result, "retry")
        self.assertGreater(finished[0]["retry_after_seconds"], 0)

    def test_manual_sync_enqueues_and_returns_without_provider_work(self):
        context = SimpleNamespace(tenant_id=7, user_id=12)
        connection = self.connection()
        with patch.dict(
            "os.environ", {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
        ), patch.object(
            calendar_routes, "require_active_tenant_member", return_value=context
        ), patch.object(
            calendar_routes, "tenant_connection", return_value=connection
        ), patch.object(
            calendar_routes, "require_calendar_access"
        ), patch.object(
            calendar_routes, "enqueue_connection_sync"
        ) as enqueue, patch.object(
            calendar_routes, "record_calendar_audit"
        ), patch.object(
            calendar_routes, "sync_connection"
        ) as provider_sync:
            result = calendar_routes.run_connection_sync(
                "connection", object(), object()
            )
        self.assertEqual(result["status"], "queued")
        enqueue.assert_called_once()
        provider_sync.assert_not_called()

    def test_manual_sync_rejects_incomplete_or_disabled_connection(self):
        context = SimpleNamespace(tenant_id=7, user_id=12)
        for connection in (
            self.connection(status="setup_required"),
            self.connection(inbound_sync_enabled=False),
        ):
            with self.subTest(connection=connection), patch.dict(
                "os.environ", {"CALENDAR_FEATURE_ENABLED": "true"}, clear=False
            ), patch.object(
                calendar_routes,
                "require_active_tenant_member",
                return_value=context,
            ), patch.object(
                calendar_routes, "tenant_connection", return_value=connection
            ), patch.object(calendar_routes, "require_calendar_access"):
                with self.assertRaises(HTTPException) as raised:
                    calendar_routes.run_connection_sync(
                        "connection", object(), object()
                    )
            self.assertEqual(raised.exception.status_code, 409)

    def test_event_payload_does_not_expose_provider_identity(self):
        payload = calendar_routes.event_payload(
            {
                "id": "local-event",
                "source_type": "google",
                "source_id": "connection:provider-event",
                "external_etag": "provider-version",
            }
        )
        self.assertNotIn("source_id", payload)
        self.assertNotIn("external_etag", payload)
        self.assertEqual(payload["source_label"], "Google")


if __name__ == "__main__":
    unittest.main()
