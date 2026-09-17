from __future__ import annotations

import json
import logging
import os
import signal
import socket
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from services.data_deletion_service import (
    claim_deletion_requests,
    get_deletion_metrics,
    process_deletion_request,
)
from services.observability_service import configure_structured_logging


logger = logging.getLogger(__name__)
STOP_EVENT = threading.Event()
STATE = {"healthy": False, "last_poll_at": None, "processed": 0, "failed": 0}


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path not in {"/health", "/metrics"}:
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/health":
            status = 200 if STATE["healthy"] else 503
            body = json.dumps({"status": "ok" if status == 200 else "starting", "last_poll_at": STATE["last_poll_at"]}).encode()
            content_type = "application/json"
        else:
            metrics = get_deletion_metrics()
            body = ("\n".join(f"madar_{key} {int(value)}" for key, value in sorted(metrics.items())) + "\n").encode()
            status = 200
            content_type = "text/plain; version=0.0.4"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_batch(*, worker_id: str, batch_size: int) -> int:
    requests = claim_deletion_requests(worker_id=worker_id, limit=batch_size)
    for request in requests:
        try:
            result = process_deletion_request(request)
            if result.get("state") == "failed_manual_intervention":
                STATE["failed"] += 1
        except Exception as error:
            STATE["failed"] += 1
            logger.error("deletion.worker_request_failed", extra={"error_type": type(error).__name__})
        STATE["processed"] += 1
    STATE["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    STATE["healthy"] = True
    return len(requests)


def main() -> int:
    configure_structured_logging()
    if os.getenv("DATA_DELETION_WORKER_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info("deletion.worker_disabled")
        return 0
    for selected in (signal.SIGINT, signal.SIGTERM):
        signal.signal(selected, lambda *_args: STOP_EVENT.set())
    host = os.getenv("DATA_DELETION_WORKER_HEALTH_HOST", "127.0.0.1").strip()
    port = int(os.getenv("DATA_DELETION_WORKER_HEALTH_PORT", "8094"))
    server = ThreadingHTTPServer((host, port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    batch_size = max(1, min(int(os.getenv("DATA_DELETION_WORKER_BATCH_SIZE", "5")), 25))
    poll = max(1.0, min(float(os.getenv("DATA_DELETION_WORKER_POLL_SECONDS", "10")), 60.0))
    try:
        while not STOP_EVENT.is_set():
            try:
                processed = run_batch(worker_id=worker_id, batch_size=batch_size)
            except Exception as error:
                processed = 0
                STATE["healthy"] = False
                logger.error("deletion.worker_poll_failed", extra={"error_type": type(error).__name__})
            STOP_EVENT.wait(0.25 if processed else poll)
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
