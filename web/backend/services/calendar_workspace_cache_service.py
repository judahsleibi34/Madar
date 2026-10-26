"""Bounded private cache for authenticated calendar bootstrap payloads."""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


def _bounded_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


CALENDAR_WORKSPACE_CACHE_TTL_SECONDS = _bounded_int(
    os.getenv("CALENDAR_WORKSPACE_CACHE_TTL_SECONDS"),
    15,
    1,
    120,
)
CALENDAR_WORKSPACE_CACHE_MAX_ENTRIES = _bounded_int(
    os.getenv("CALENDAR_WORKSPACE_CACHE_MAX_ENTRIES"),
    256,
    16,
    2000,
)


@dataclass
class _CacheEntry:
    tenant_id: int
    expires_at: float
    value: Any


_cache: OrderedDict[str, _CacheEntry] = OrderedDict()
_cache_lock = threading.RLock()
_inflight: dict[int, set[object]] = {}


def calendar_workspace_cache_key(
    *,
    tenant_id: int,
    user_id: int | str,
    role: str,
    start: Any,
    end: Any,
) -> str:
    parts = json.dumps(
        {
            "user_id": str(user_id),
            "role": str(role or "").lower(),
            "start": str(start),
            "end": str(end),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{int(tenant_id)}:workspace:{parts}"


def read_calendar_workspace_cache(key: str, tenant_id: int | None = None) -> Any | None:
    current_time = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if tenant_id is not None and entry.tenant_id != int(tenant_id):
            return None
        if entry.expires_at <= current_time:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return copy.deepcopy(entry.value)


def write_calendar_workspace_cache(
    key: str,
    tenant_id: int,
    value: Any,
    *,
    ttl_seconds: int | None = None,
) -> Any:
    ttl = _bounded_int(
        str(ttl_seconds) if ttl_seconds is not None else None,
        CALENDAR_WORKSPACE_CACHE_TTL_SECONDS,
        1,
        120,
    )
    with _cache_lock:
        _cache[key] = _CacheEntry(
            tenant_id=int(tenant_id),
            expires_at=time.monotonic() + ttl,
            value=copy.deepcopy(value),
        )
        _cache.move_to_end(key)
        while len(_cache) > CALENDAR_WORKSPACE_CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return value


def get_or_create_calendar_workspace(
    key: str,
    tenant_id: int,
    factory: Callable[[], Any],
) -> tuple[Any, bool]:
    target_tenant = int(tenant_id)
    token = object()
    with _cache_lock:
        cached = read_calendar_workspace_cache(key, target_tenant)
        if cached is not None:
            return cached, True
        fills = _inflight.setdefault(target_tenant, set())
        fills.add(token)
    try:
        created = factory()
        with _cache_lock:
            if _inflight.get(target_tenant) is fills:
                write_calendar_workspace_cache(key, target_tenant, created)
        return created, False
    finally:
        with _cache_lock:
            fills.discard(token)
            if not fills and _inflight.get(target_tenant) is fills:
                _inflight.pop(target_tenant, None)


def invalidate_calendar_workspace_cache(tenant_id: int) -> int:
    target = int(tenant_id)
    with _cache_lock:
        _inflight.pop(target, None)
        keys = [key for key, entry in _cache.items() if entry.tenant_id == target]
        for key in keys:
            _cache.pop(key, None)
    return len(keys)


def clear_calendar_workspace_cache() -> None:
    with _cache_lock:
        _cache.clear()
        _inflight.clear()


def calendar_workspace_cache_size() -> int:
    with _cache_lock:
        return len(_cache)
