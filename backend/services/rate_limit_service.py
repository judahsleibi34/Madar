import os
import time
import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request

try:
    import redis
except ImportError:  # pragma: no cover - dependency is installed in Docker
    redis = None

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


RATE_LIMIT_ENABLED = _env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_FAIL_OPEN = _env_bool("RATE_LIMIT_FAIL_OPEN", True)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

AUTH_RATE_LIMIT_LIMIT = int(os.getenv("AUTH_RATE_LIMIT_LIMIT", "20"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))
PASSWORD_RATE_LIMIT_LIMIT = int(os.getenv("PASSWORD_RATE_LIMIT_LIMIT", "10"))
PASSWORD_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("PASSWORD_RATE_LIMIT_WINDOW_SECONDS", "300"))
PUBLIC_RATE_LIMIT_LIMIT = int(os.getenv("PUBLIC_RATE_LIMIT_LIMIT", "120"))
PUBLIC_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("PUBLIC_RATE_LIMIT_WINDOW_SECONDS", "60"))
PUBLIC_FORM_SUBMISSION_RATE_LIMIT_LIMIT = int(os.getenv("PUBLIC_FORM_SUBMISSION_RATE_LIMIT_LIMIT", "20"))
PUBLIC_FORM_SUBMISSION_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("PUBLIC_FORM_SUBMISSION_RATE_LIMIT_WINDOW_SECONDS", "300"))
PUBLIC_CONTACT_RATE_LIMIT_LIMIT = int(os.getenv("PUBLIC_CONTACT_RATE_LIMIT_LIMIT", "10"))
PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SECONDS", "300"))


@dataclass
class RateLimitResult:
    key: str
    count: int
    limit: int
    window_seconds: int


class InMemoryRateLimitStore:
    def __init__(self):
        self._values = {}

    def incr_with_ttl(self, key: str, window_seconds: int) -> int:
        now = time.time()
        count, expires_at = self._values.get(key, (0, now + window_seconds))

        if expires_at <= now:
            count = 0
            expires_at = now + window_seconds

        count += 1
        self._values[key] = (count, expires_at)
        return count


class RedisRateLimitStore:
    def __init__(self, redis_url: str):
        if redis is None:
            raise RuntimeError("redis package is required for Redis-backed rate limiting")
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def incr_with_ttl(self, key: str, window_seconds: int) -> int:
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
        return int(count)


_store = None
_memory_store = InMemoryRateLimitStore()


def get_rate_limit_store():
    global _store

    if _store is not None:
        return _store

    if not RATE_LIMIT_ENABLED:
        return None

    try:
        _store = RedisRateLimitStore(REDIS_URL)
    except Exception as exc:
        if not RATE_LIMIT_FAIL_OPEN:
            raise RuntimeError(f"Rate limiter Redis unavailable: {exc}") from exc
        logger.warning("rate_limit.redis_unavailable", extra={"error_type": type(exc).__name__})
        _store = _memory_store

    return _store


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def normalize_identifier(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    return cleaned or "anonymous"


def enforce_rate_limit(
    request: Request,
    scope: str,
    *,
    identifier: str | None = None,
    limit: int,
    window_seconds: int,
) -> RateLimitResult | None:
    if not RATE_LIMIT_ENABLED:
        return None

    store = get_rate_limit_store()
    if store is None:
        return None

    client_ip = get_client_ip(request)
    identity = normalize_identifier(identifier)
    key = f"rl:{scope}:{client_ip}:{identity}"

    try:
        count = store.incr_with_ttl(key, window_seconds)
    except Exception as exc:
        if not RATE_LIMIT_FAIL_OPEN:
            raise RuntimeError(f"Rate limiter Redis unavailable: {exc}") from exc

        logger.warning("rate_limit.fallback_used", extra={"error_type": type(exc).__name__})
        fallback_store = _memory_store
        count = fallback_store.incr_with_ttl(key, window_seconds)

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
        )

    return RateLimitResult(
        key=key,
        count=count,
        limit=limit,
        window_seconds=window_seconds,
    )


def enforce_auth_rate_limit(request: Request, scope: str, identifier: str | None = None):
    return enforce_rate_limit(
        request,
        f"auth:{scope}",
        identifier=identifier,
        limit=AUTH_RATE_LIMIT_LIMIT,
        window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )


def enforce_password_rate_limit(request: Request, scope: str, identifier: str | None = None):
    return enforce_rate_limit(
        request,
        f"password:{scope}",
        identifier=identifier,
        limit=PASSWORD_RATE_LIMIT_LIMIT,
        window_seconds=PASSWORD_RATE_LIMIT_WINDOW_SECONDS,
    )


def enforce_public_rate_limit(request: Request, scope: str, identifier: str | None = None):
    return enforce_rate_limit(
        request,
        f"public:{scope}",
        identifier=identifier,
        limit=PUBLIC_RATE_LIMIT_LIMIT,
        window_seconds=PUBLIC_RATE_LIMIT_WINDOW_SECONDS,
    )


def enforce_public_form_submission_rate_limit(
    request: Request,
    scope: str,
    identifier: str | None = None,
):
    return enforce_rate_limit(
        request,
        f"public_form_submission:{scope}",
        identifier=identifier,
        limit=PUBLIC_FORM_SUBMISSION_RATE_LIMIT_LIMIT,
        window_seconds=PUBLIC_FORM_SUBMISSION_RATE_LIMIT_WINDOW_SECONDS,
    )


def enforce_public_contact_rate_limit(request: Request, identifier: str | None = None):
    return enforce_rate_limit(
        request,
        "public_contact:submit",
        identifier=identifier,
        limit=PUBLIC_CONTACT_RATE_LIMIT_LIMIT,
        window_seconds=PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SECONDS,
    )
