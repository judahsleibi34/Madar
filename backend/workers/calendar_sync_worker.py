from __future__ import annotations

import json
import logging
import os
import signal
import socket
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from database import service_supabase
from services.calendar_sync_service import CalendarSyncError
from services.calendar_task_sync_queue_service import (
    TRANSIENT_CODES,
    claim_task_sync_jobs,
    complete_task_sync_delete,
    enqueue_task_sync,
    finish_task_sync_job,
    get_task_sync_queue_metrics,
    process_task_sync_job,
    retry_delay,
)
from services.observability_service import configure_structured_logging


logger = logging.getLogger(__name__)
STOP_EVENT = threading.Event()
STATE: dict[str, Any] = {
    "healthy": False,
    "last_poll_at": None,
    "processed": 0,
    "succeeded": 0,
    "failed": 0,
    "reconciliation_required": 0,
    "queue_depth": 0,
}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        status = 200 if STATE["healthy"] else 503
        body = json.dumps(
            {
                key: value
                for key, value in STATE.items()
                if key != "last_error"
            },
            separators=(",", ":"),
        ).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


def _start_health_server() -> ThreadingHTTPServer:
    host = os.getenv("CALENDAR_SYNC_WORKER_HEALTH_HOST", "0.0.0.0")
    port = max(
        1024,
        min(int(os.getenv("CALENDAR_SYNC_WORKER_HEALTH_PORT", "8091")), 65535),
    )
    server = ThreadingHTTPServer((host, port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _set_task_failure(job: dict[str, Any], code: str) -> None:
    service_supabase.table("calendar_tasks").update(
        {"sync_status": "failed", "sync_error_code": str(code)[:100]}
    ).eq("id", job["task_id"]).eq("tenant_id", job["tenant_id"]).execute()


def process_job(job: dict[str, Any]) -> str:
    try:
        result = process_task_sync_job(job)
        if result == "provider_deleted":
            complete_task_sync_delete(str(job["id"]))
            return "succeeded"
        finish_task_sync_job(
            str(job["id"]),
            status=result,
            error_code="multiple_provider_matches"
            if result == "reconciliation_required"
            else None,
        )
        return result
    except CalendarSyncError as error:
        if error.code == "sync_job_superseded":
            finish_task_sync_job(
                str(job["id"]), status="superseded", error_code=error.code
            )
            rows = getattr(
                service_supabase.table("calendar_tasks")
                .select("version")
                .eq("id", job["task_id"])
                .eq("tenant_id", job["tenant_id"])
                .limit(1)
                .execute(),
                "data",
                None,
            ) or []
            if rows:
                enqueue_task_sync(
                    tenant_id=int(job["tenant_id"]),
                    task_id=str(job["task_id"]),
                    connection_id=str(job["connection_id"]),
                    operation=str(job.get("operation") or "update"),
                    task_version=int(rows[0].get("version") or 1),
                )
            return "superseded"
        retryable = error.code in TRANSIENT_CODES
        attempts = int(job.get("attempts") or 1)
        max_attempts = int(job.get("max_attempts") or 6)
        if retryable and attempts < max_attempts:
            finish_task_sync_job(
                str(job["id"]),
                status="failed",
                error_code=error.code,
                retry_after_seconds=retry_delay(attempts),
            )
            return "retry"
        _set_task_failure(job, error.code)
        finish_task_sync_job(
            str(job["id"]), status="failed", error_code=error.code
        )
        logger.warning(
            "calendar_task_sync.failed",
            extra={"error_code": error.code, "attempts": attempts},
        )
        return "failed"
    except Exception as error:
        attempts = int(job.get("attempts") or 1)
        max_attempts = int(job.get("max_attempts") or 6)
        code = "worker_unexpected"
        if attempts < max_attempts:
            finish_task_sync_job(
                str(job["id"]),
                status="failed",
                error_code=code,
                retry_after_seconds=retry_delay(attempts),
            )
            return "retry"
        _set_task_failure(job, code)
        finish_task_sync_job(str(job["id"]), status="failed", error_code=code)
        logger.error(
            "calendar_task_sync.unexpected",
            extra={"error_type": type(error).__name__, "attempts": attempts},
        )
        return "failed"


def process_sync_batch(*, limit: int = 10, worker_id: str | None = None) -> int:
    selected_worker = worker_id or f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"
    jobs = claim_task_sync_jobs(worker_id=selected_worker, limit=limit)
    for job in jobs:
        result = process_job(job)
        STATE["processed"] += 1
        if result in STATE:
            STATE[result] += 1
    metrics = get_task_sync_queue_metrics()
    STATE.update(metrics)
    STATE["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    STATE["healthy"] = True
    return len(jobs)


def main() -> int:
    configure_structured_logging()
    if os.getenv("CALENDAR_SYNC_WORKER_ENABLED", "false").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        logger.info("calendar_sync_worker.disabled")
        return 0
    for selected_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(selected_signal, lambda *_args: STOP_EVENT.set())
    health_server = _start_health_server()
    batch_size = max(
        1, min(int(os.getenv("CALENDAR_SYNC_BATCH_SIZE", "10")), 50)
    )
    poll_seconds = max(
        1, min(int(os.getenv("CALENDAR_SYNC_POLL_SECONDS", "5")), 60)
    )
    worker_id = f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"
    try:
        STATE["healthy"] = True
        while not STOP_EVENT.is_set():
            try:
                processed = process_sync_batch(
                    limit=batch_size, worker_id=worker_id
                )
            except Exception as error:
                STATE["healthy"] = False
                logger.error(
                    "calendar_task_sync.poll_failed",
                    extra={"error_type": type(error).__name__},
                )
                processed = 0
            STOP_EVENT.wait(0.25 if processed else poll_seconds)
    finally:
        STATE["healthy"] = False
        health_server.shutdown()
        health_server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
