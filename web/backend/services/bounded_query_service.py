from __future__ import annotations

import contextvars
import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


def _configured_workers() -> int:
    try:
        configured = int(os.getenv("MADAR_DB_PARALLEL_WORKERS", "8"))
    except (TypeError, ValueError):
        configured = 8
    return max(1, min(configured, 16))


DB_PARALLEL_WORKERS = _configured_workers()

# This executor is shared by all request-local fan-out. Its process-wide cap
# prevents concurrent requests from multiplying private thread pools and leaves
# headroom in the service Supabase client's 50-connection HTTP pool.
_DB_EXECUTOR = ThreadPoolExecutor(
    max_workers=DB_PARALLEL_WORKERS,
    thread_name_prefix="madar-db-read",
)


def submit_db_read(function: Callable[..., Any], /, *args, **kwargs) -> Future:
    """Submit an independent read with a copied observability context.

    Callers construct query builders inside ``function``. Passing mutable
    query/session objects between tasks is intentionally unsupported.
    """

    context = contextvars.copy_context()
    return _DB_EXECUTOR.submit(context.run, function, *args, **kwargs)
