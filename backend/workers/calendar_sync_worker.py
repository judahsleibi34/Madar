from __future__ import annotations

import logging
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from database import service_supabase
from services.calendar_sync_service import CalendarSyncError, sync_connection
from services.observability_service import configure_structured_logging


logger = logging.getLogger(__name__)
STOP_EVENT = threading.Event()


def eligible_connections(*, limit: int, interval_seconds: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=interval_seconds)).isoformat()
    return getattr(
        service_supabase.table("calendar_sync_connections")
        .select("*")
        .in_("provider", ["google", "microsoft"])
        .in_("status", ["connected", "degraded"])
        .not_.is_("encrypted_credentials", "null")
        .or_(f"last_attempt_at.is.null,last_attempt_at.lt.{cutoff}")
        .order("last_attempt_at")
        .limit(limit)
        .execute(),
        "data",
        None,
    ) or []


def process_sync_batch(*, limit: int = 10, interval_seconds: int = 300, concurrency: int = 2) -> int:
    connections = eligible_connections(limit=limit, interval_seconds=interval_seconds)

    def process(connection: dict) -> None:
        try:
            sync_connection(connection)
        except CalendarSyncError as error:
            logger.warning("calendar_sync.failed", extra={"connection_id": connection.get("id"), "provider": connection.get("provider"), "error_code": error.code})
        except Exception as error:
            logger.error("calendar_sync.unexpected", extra={"connection_id": connection.get("id"), "provider": connection.get("provider"), "error_type": type(error).__name__})

    with ThreadPoolExecutor(max_workers=max(1, min(int(concurrency), 8))) as executor:
        list(executor.map(process, connections))
    return len(connections)


def main() -> int:
    configure_structured_logging()
    if os.getenv("CALENDAR_SYNC_WORKER_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info("calendar_sync_worker.disabled")
        return 0
    for selected_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(selected_signal, lambda *_args: STOP_EVENT.set())
    batch_size = max(1, min(int(os.getenv("CALENDAR_SYNC_BATCH_SIZE", "10")), 100))
    concurrency = max(1, min(int(os.getenv("CALENDAR_SYNC_CONCURRENCY", "2")), 8))
    interval = max(60, min(int(os.getenv("CALENDAR_SYNC_INTERVAL_SECONDS", "300")), 86400))
    while not STOP_EVENT.is_set():
        processed = process_sync_batch(limit=batch_size, interval_seconds=interval, concurrency=concurrency)
        STOP_EVENT.wait(5 if processed else min(interval, 60))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
