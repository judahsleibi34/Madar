"""Small bounded in-process cache for public ecommerce catalog reads."""

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


CATALOG_CACHE_TTL_SECONDS = _bounded_int(
    os.getenv("ECOMMERCE_CATALOG_CACHE_TTL_SECONDS"),
    60,
    5,
    900,
)
CATALOG_CACHE_MAX_ENTRIES = _bounded_int(
    os.getenv("ECOMMERCE_CATALOG_CACHE_MAX_ENTRIES"),
    512,
    32,
    5000,
)


@dataclass
class _CacheEntry:
    tenant_id: int
    expires_at: float
    value: Any


_cache: OrderedDict[str, _CacheEntry] = OrderedDict()
_cache_lock = threading.RLock()


def ecommerce_cache_key(tenant_id: int, namespace: str, **parts: Any) -> str:
    normalized = json.dumps(
        parts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"{int(tenant_id)}:{namespace}:{normalized}"


def read_ecommerce_cache(key: str) -> Any | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return copy.deepcopy(entry.value)


def write_ecommerce_cache(
    key: str,
    tenant_id: int,
    value: Any,
    *,
    ttl_seconds: int | None = None,
) -> Any:
    ttl = _bounded_int(
        str(ttl_seconds) if ttl_seconds is not None else None,
        CATALOG_CACHE_TTL_SECONDS,
        1,
        900,
    )
    with _cache_lock:
        _cache[key] = _CacheEntry(
            tenant_id=int(tenant_id),
            expires_at=time.monotonic() + ttl,
            value=copy.deepcopy(value),
        )
        _cache.move_to_end(key)
        while len(_cache) > CATALOG_CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return value


def get_or_create_ecommerce_cache(
    key: str,
    tenant_id: int,
    factory: Callable[[], Any],
    *,
    ttl_seconds: int | None = None,
) -> tuple[Any, bool]:
    cached = read_ecommerce_cache(key)
    if cached is not None:
        return cached, True
    created = factory()
    write_ecommerce_cache(
        key,
        tenant_id,
        created,
        ttl_seconds=ttl_seconds,
    )
    return created, False


def invalidate_ecommerce_cache(tenant_id: int) -> int:
    target = int(tenant_id)
    with _cache_lock:
        keys = [key for key, entry in _cache.items() if entry.tenant_id == target]
        for key in keys:
            _cache.pop(key, None)
    return len(keys)


def clear_ecommerce_cache() -> None:
    with _cache_lock:
        _cache.clear()


def ecommerce_cache_size() -> int:
    with _cache_lock:
        return len(_cache)
