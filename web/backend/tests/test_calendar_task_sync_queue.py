import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from services import calendar_task_sync_queue_service as queue_service
from services.calendar_sync_service import CalendarSyncError
from workers import calendar_sync_worker


class RpcClient:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.data))


class CalendarTaskSyncQueueTests(unittest.TestCase):
    def setUp(self):
        calendar_sync_worker.STATE.update(
            {
                "healthy": False,
                "last_poll_at": None,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "reconciliation_required": 0,
                "queue_depth": 0,
            }
        )

    def test_enqueue_uses_atomic_durable_rpc(self):
        client = RpcClient([{"id": "job", "status": "pending"}])
        result = queue_service.enqueue_task_sync(
            tenant_id=7,
            task_id="task",
            connection_id="connection",
            operation="update",
            task_version=4,
            client=client,
        )
        self.assertEqual(result["status"], "pending")
        self.assertEqual(
            client.calls[0][0], "enqueue_calendar_task_sync_job"
        )
        self.assertEqual(client.calls[0][1]["p_task_version"], 4)

    def test_marker_is_deterministic_and_does_not_contain_ids(self):
        with patch.dict(
            os.environ,
            {"CALENDAR_CREDENTIALS_SECRET": "calendar-test-secret-with-enough-entropy"},
            clear=False,
        ):
            first = queue_service._marker(
                {"id": "private-task-id"},
                {"tenant_id": 7, "id": "private-connection-id"},
            )
            second = queue_service._marker(
                {"id": "private-task-id"},
                {"tenant_id": 7, "id": "private-connection-id"},
            )
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{64}$")
        self.assertNotIn("private", first)

    def test_provider_timeout_is_structured_and_retryable(self):
        request = httpx.Request("GET", "https://www.googleapis.com/calendar/v3")

        class TimeoutClient:
            def request(self, *_args, **_kwargs):
                raise httpx.ReadTimeout("slow", request=request)

        with self.assertRaises(CalendarSyncError) as raised:
            queue_service._request(
                TimeoutClient(), "GET", str(request.url)
            )
        self.assertEqual(raised.exception.code, "provider_read_timeout")
        self.assertIn(raised.exception.code, queue_service.TRANSIENT_CODES)

    def test_worker_retry_is_bounded_and_keeps_content_out_of_logs(self):
        job = {
            "id": "job",
            "task_id": "task",
            "tenant_id": 7,
            "attempts": 1,
            "max_attempts": 6,
        }
        finished = []
        with patch.object(
            calendar_sync_worker,
            "process_task_sync_job",
            side_effect=CalendarSyncError(
                "provider_read_timeout", "private task content"
            ),
        ), patch.object(
            calendar_sync_worker,
            "finish_task_sync_job",
            side_effect=lambda *_args, **kwargs: finished.append(kwargs),
        ):
            result = calendar_sync_worker.process_job(job)
        self.assertEqual(result, "retry")
        self.assertEqual(finished[0]["status"], "failed")
        self.assertGreater(finished[0]["retry_after_seconds"], 0)
        self.assertLessEqual(finished[0]["retry_after_seconds"], 900)

    def test_worker_invalid_authorization_is_terminal(self):
        job = {
            "id": "job",
            "task_id": "task",
            "tenant_id": 7,
            "attempts": 1,
            "max_attempts": 6,
        }
        finished = []
        with patch.object(
            calendar_sync_worker,
            "process_task_sync_job",
            side_effect=CalendarSyncError(
                "provider_authorization_failed", "reconnect"
            ),
        ), patch.object(
            calendar_sync_worker, "_set_task_failure"
        ) as task_failure, patch.object(
            calendar_sync_worker,
            "finish_task_sync_job",
            side_effect=lambda *_args, **kwargs: finished.append(kwargs),
        ), self.assertLogs(calendar_sync_worker.logger, level="WARNING") as logs:
            result = calendar_sync_worker.process_job(job)
        self.assertEqual(result, "failed")
        task_failure.assert_called_once()
        self.assertNotIn("reconnect", " ".join(logs.output))

    def test_worker_marks_multiple_matches_for_manual_reconciliation(self):
        job = {"id": "job", "task_id": "task", "tenant_id": 7}
        finished = []
        with patch.object(
            calendar_sync_worker,
            "process_task_sync_job",
            return_value="reconciliation_required",
        ), patch.object(
            calendar_sync_worker,
            "finish_task_sync_job",
            side_effect=lambda *_args, **kwargs: finished.append(kwargs),
        ):
            result = calendar_sync_worker.process_job(job)
        self.assertEqual(result, "reconciliation_required")
        self.assertEqual(finished[0]["status"], "reconciliation_required")

    def test_disabled_worker_never_claims(self):
        with patch.dict(
            os.environ, {"CALENDAR_SYNC_WORKER_ENABLED": "false"}, clear=False
        ):
            self.assertEqual(calendar_sync_worker.main(), 0)


if __name__ == "__main__":
    unittest.main()
