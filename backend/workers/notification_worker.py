from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from services.notification_delivery_service import DeliveryError, deliver_notification
from services.notification_outbox_service import claim_notifications, get_queue_metrics, mark_notification_result
from services.calendar_reminder_service import enqueue_due_calendar_reminders, mark_calendar_reminder_delivery
from services.observability_service import configure_structured_logging

logger = logging.getLogger(__name__)
STOP_EVENT = threading.Event()
STATE: dict[str, Any] = {"healthy": False, "last_poll_at": None, "processed": 0, "sent": 0, "failed": 0, "dead": 0, "queue_depth": 0, "oldest_pending_age_seconds": 0}


def retry_delay(row: dict[str, Any], *, base: int = 30, maximum: int = 3600) -> int:
    attempts = max(1, int(row.get("attempts") or 1))
    exponential = min(maximum, base * (2 ** min(attempts - 1, 10)))
    seed = int(hashlib.sha256(str(row.get("id") or "").encode()).hexdigest()[:8], 16)
    jitter = random.Random(seed + attempts).uniform(0.85, 1.15)
    return max(1, min(maximum, int(exponential * jitter)))


def process_batch(
    *,
    limit: int,
    claim: Callable[..., list[dict[str, Any]]] = claim_notifications,
    deliver: Callable[[dict[str, Any]], None] = deliver_notification,
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
            deliver(row)
        except DeliveryError as error:
            code = error.code if error.retryable else f"permanent.{error.code}"
            finish(outbox_id, succeeded=False, failure_code=code, retry_after_seconds=retry_delay(row))
            mark_calendar_reminder_delivery(row, succeeded=False, failure_code=code)
            STATE["failed"] += 1
            if int(row.get("attempts") or 0) >= int(row.get("max_attempts") or 5):
                STATE["dead"] += 1
            logger.warning("notification_worker.delivery_failed", extra={"outbox_id": outbox_id, "channel": row.get("channel"), "error_code": code})
        except Exception as error:
            finish(outbox_id, succeeded=False, failure_code="delivery_unexpected", retry_after_seconds=retry_delay(row))
            mark_calendar_reminder_delivery(row, succeeded=False, failure_code="delivery_unexpected")
            STATE["failed"] += 1
            logger.error("notification_worker.delivery_failed", extra={"outbox_id": outbox_id, "channel": row.get("channel"), "error_code": "delivery_unexpected", "error_type": type(error).__name__})
        else:
            if finish(outbox_id, succeeded=True):
                STATE["sent"] += 1
                mark_calendar_reminder_delivery(row, succeeded=True)
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
    try:
        while not STOP_EVENT.is_set():
            try:
                enqueue_due_calendar_reminders(limit=batch_size)
            except Exception as error:
                logger.error("calendar_reminders.enqueue_failed", extra={"error_type": type(error).__name__})
            processed = process_batch(limit=batch_size, concurrency=concurrency)
            try:
                STATE.update(get_queue_metrics())
            except Exception as error:
                STATE["healthy"] = False
                logger.error("notification_worker.metrics_failed", extra={"error_type": type(error).__name__})
            if not processed:
                STOP_EVENT.wait(poll_seconds)
    finally:
        STATE["healthy"] = False
        server.shutdown()
        server.server_close()
        logger.info("notification_worker.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
