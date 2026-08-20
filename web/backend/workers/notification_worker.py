from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from services.notification_delivery_service import DeliveryError, deliver_notification
from services.notification_delivery_queue_service import (
    claim_deliveries,
    cleanup_delivery_data,
    finish_delivery,
    get_delivery_metrics,
    resolve_outbox_notification,
)
from services.notification_outbox_service import claim_notifications, get_queue_metrics, mark_notification_result
from services.calendar_reminder_service import (
    enqueue_due_calendar_reminders,
    finalize_calendar_reminder_deliveries,
    mark_calendar_reminder_delivery,
)
from services.calendar_task_archive_service import archive_ended_calendar_tasks
from services.observability_service import configure_structured_logging

logger = logging.getLogger(__name__)
STOP_EVENT = threading.Event()
STATE: dict[str, Any] = {"healthy": False, "last_poll_at": None, "processed": 0, "resolved": 0, "sent": 0, "failed": 0, "dead": 0, "queue_depth": 0, "oldest_pending_age_seconds": 0}


def retry_delay(row: dict[str, Any], *, base: int = 30, maximum: int = 3600) -> int:
    attempts = max(1, int(row.get("attempts") or 1))
    exponential = min(maximum, base * (2 ** min(attempts - 1, 10)))
    seed = int(hashlib.sha256(str(row.get("id") or "").encode()).hexdigest()[:8], 16)
    jitter = random.Random(seed + attempts).uniform(0.85, 1.15)
    return max(1, min(maximum, int(exponential * jitter)))


def process_resolution_batch(
    *,
    limit: int,
    claim: Callable[..., list[dict[str, Any]]] = claim_notifications,
    resolve: Callable[[dict[str, Any]], int] = resolve_outbox_notification,
    finish: Callable[..., bool] = mark_notification_result,
    concurrency: int = 1,
) -> int:
    rows = claim(limit=limit)
    def process(row: dict[str, Any]) -> None:
        outbox_id = str(row.get("id") or "")
        if not outbox_id:
            logger.error("notification_worker.row_invalid", extra={"error_code": "outbox_id_missing"})
            return
        try:
            delivery_count = resolve(row)
        except Exception as error:
            try:
                finish(outbox_id, succeeded=False, failure_code="resolution_failed", retry_after_seconds=retry_delay(row))
            except Exception as finish_error:
                logger.error(
                    "notification_worker.resolution_result_persist_failed",
                    extra={
                        "outbox_id": outbox_id,
                        "error_type": type(finish_error).__name__,
                    },
                )
            STATE["failed"] += 1
            logger.error("notification_worker.resolution_failed", extra={"outbox_id": outbox_id, "channel": row.get("channel"), "error_code": "resolution_failed", "error_type": type(error).__name__})
        else:
            STATE["resolved"] += 1
            if delivery_count == 0 and str(row.get("template") or "") == "calendar_reminder":
                mark_calendar_reminder_delivery(row, succeeded=False, failure_code="recipient_unavailable")
        STATE["processed"] += 1
    with ThreadPoolExecutor(max_workers=max(1, min(int(concurrency), 16))) as executor:
        list(executor.map(process, rows))
    STATE["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    STATE["healthy"] = True
    return len(rows)


def process_batch(
    *,
    limit: int,
    claim: Callable[..., list[dict[str, Any]]] = claim_deliveries,
    deliver: Callable[[dict[str, Any]], None] = deliver_notification,
    finish: Callable[..., dict[str, Any] | None] = finish_delivery,
    concurrency: int = 1,
) -> int:
    """Process independently retryable delivery rows, never broad outbox rows."""
    rows = claim(limit=limit)

    def process(row: dict[str, Any]) -> None:
        delivery_id = str(row.get("id") or "")
        if not delivery_id:
            logger.error("notification_worker.row_invalid", extra={"error_code": "delivery_id_missing"})
            return
        outcome = "sent"
        error_code = None
        selected_retry_delay = retry_delay(row)
        try:
            deliver(row)
        except DeliveryError as error:
            error_code = error.code
            outcome = "retry" if error.retryable else error.terminal_outcome
            if error.retry_after_seconds is not None:
                selected_retry_delay = max(
                    selected_retry_delay,
                    max(1, min(int(error.retry_after_seconds), 86400)),
                )
        except Exception as error:
            error_code = "delivery_unexpected"
            outcome = "retry"
            logger.error(
                "notification_worker.delivery_failed",
                extra={
                    "delivery_id": delivery_id,
                    "tenant_id": row.get("tenant_id"),
                    "user_id": row.get("user_id"),
                    "channel": row.get("channel"),
                    "attempt": row.get("attempts"),
                    "error_code": error_code,
                    "error_type": type(error).__name__,
                },
            )
        try:
            result = finish(
                delivery_id,
                outcome=outcome,
                error_code=error_code,
                retry_after_seconds=selected_retry_delay,
            )
        except Exception as error:
            STATE["failed"] += 1
            STATE["processed"] += 1
            logger.error(
                "notification_worker.delivery_result_persist_failed",
                extra={
                    "delivery_id": delivery_id,
                    "tenant_id": row.get("tenant_id"),
                    "user_id": row.get("user_id"),
                    "channel": row.get("channel"),
                    "attempt": row.get("attempts"),
                    "error_type": type(error).__name__,
                },
            )
            return
        final_status = (result or {}).get("status")
        if final_status == "sent":
            STATE["sent"] += 1
        elif final_status == "dead":
            STATE["dead"] += 1
            STATE["failed"] += 1
        elif outcome != "sent":
            STATE["failed"] += 1
        logger.info(
            "notification_worker.delivery_result",
            extra={
                "delivery_id": delivery_id,
                "tenant_id": row.get("tenant_id"),
                "user_id": row.get("user_id"),
                "channel": row.get("channel"),
                "attempt": row.get("attempts"),
                "result": final_status or outcome,
                "error_code": error_code,
            },
        )
        if row.get("outbox_id") and final_status in {"sent", "dead"}:
            try:
                finalize_calendar_reminder_deliveries(str(row["outbox_id"]))
            except Exception as error:
                logger.error(
                    "notification_worker.reminder_finalize_failed",
                    extra={
                        "delivery_id": delivery_id,
                        "outbox_id": row.get("outbox_id"),
                        "error_type": type(error).__name__,
                    },
                )
        STATE["processed"] += 1

    with ThreadPoolExecutor(max_workers=max(1, min(int(concurrency), 16))) as executor:
        list(executor.map(process, rows))
    STATE["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    STATE["healthy"] = True
    return len(rows)


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path == "/health":
            status = 200 if STATE["healthy"] else 503
            body = json.dumps({"status": "ok" if status == 200 else "starting", "last_poll_at": STATE["last_poll_at"]}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/metrics":
            lines = [f"madar_notification_worker_{key} {int(value)}" for key, value in STATE.items() if key in {"processed", "sent", "failed", "dead", "queue_depth", "oldest_pending_age_seconds"}]
            body = ("\n".join(lines) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def main() -> int:
    configure_structured_logging()
    if os.getenv("NOTIFICATION_WORKER_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info("notification_worker.disabled")
        return 0
    for selected_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(selected_signal, lambda *_args: STOP_EVENT.set())
    port = int(os.getenv("NOTIFICATION_WORKER_HEALTH_PORT", "8090"))
    host = os.getenv("NOTIFICATION_WORKER_HEALTH_HOST", "127.0.0.1").strip()
    server = ThreadingHTTPServer((host, port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    batch_size = max(1, min(int(os.getenv("NOTIFICATION_WORKER_BATCH_SIZE", "25")), 100))
    concurrency = max(1, min(int(os.getenv("NOTIFICATION_WORKER_CONCURRENCY", "2")), 16))
    poll_seconds = max(0.25, min(float(os.getenv("NOTIFICATION_WORKER_POLL_SECONDS", "5")), 60.0))
    cleanup_due_at = time.monotonic()
    try:
        while not STOP_EVENT.is_set():
            try:
                archive_ended_calendar_tasks(limit=batch_size)
            except Exception as error:
                logger.error("calendar_tasks.auto_archive_failed", extra={"error_type": type(error).__name__})
            try:
                enqueue_due_calendar_reminders(limit=batch_size)
            except Exception as error:
                logger.error("calendar_reminders.enqueue_failed", extra={"error_type": type(error).__name__})
            try:
                resolved = process_resolution_batch(limit=batch_size, concurrency=concurrency)
            except Exception as error:
                resolved = 0
                STATE["healthy"] = False
                logger.error(
                    "notification_worker.resolution_batch_failed",
                    extra={"error_type": type(error).__name__},
                )
            try:
                processed = process_batch(limit=batch_size, concurrency=concurrency)
            except Exception as error:
                processed = 0
                STATE["healthy"] = False
                logger.error(
                    "notification_worker.delivery_batch_failed",
                    extra={"error_type": type(error).__name__},
                )
            try:
                STATE.update(get_queue_metrics())
                STATE.update(get_delivery_metrics())
            except Exception as error:
                STATE["healthy"] = False
                logger.error("notification_worker.metrics_failed", extra={"error_type": type(error).__name__})
            if not resolved and not processed:
                STOP_EVENT.wait(poll_seconds)
            if time.monotonic() >= cleanup_due_at:
                try:
                    cleanup_delivery_data(limit=1000)
                except Exception as error:
                    logger.warning(
                        "notification_worker.cleanup_failed",
                        extra={"error_type": type(error).__name__},
                    )
                cleanup_due_at = time.monotonic() + 3600
    finally:
        STATE["healthy"] = False
        server.shutdown()
        server.server_close()
        logger.info("notification_worker.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
