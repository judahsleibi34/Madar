import os
import time
import ipaddress
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

DEFAULT_TRUSTED_PROXY_IPS = "127.0.0.1,::1"
TRUSTED_PROXY_IPS = os.getenv("TRUSTED_PROXY_IPS", DEFAULT_TRUSTED_PROXY_IPS)
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


def parse_ip_address(value: str | None):
    candidate = str(value or "").strip().strip('"\'')

    if not candidate or candidate.lower() == "unknown":
        return None

    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]

    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def parse_trusted_proxy_networks(value: str | None = None) -> tuple:
    raw_value = TRUSTED_PROXY_IPS if value is None else value
    networks = []

    for item in str(raw_value or "").split(","):
        candidate = item.strip()

        if not candidate:
            continue

        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            logger.warning("rate_limit.invalid_trusted_proxy", extra={"proxy": candidate})

    return tuple(networks)


def ip_is_trusted_proxy(ip_address, trusted_networks: tuple | None = None) -> bool:
    networks = trusted_networks if trusted_networks is not None else parse_trusted_proxy_networks()
    return any(ip_address in network for network in networks)


def parse_forwarded_for(value: str | None):
    if not value:
        return []

    addresses = []

    for item in value.split(","):
        candidate = item.strip()
        parsed_ip = parse_ip_address(candidate)

        if parsed_ip is None:
            return []

        addresses.append(parsed_ip)

    return addresses


def get_forwarded_client_ip(request: Request, peer_ip) -> str | None:
    trusted_networks = parse_trusted_proxy_networks()
    forwarded_addresses = parse_forwarded_for(request.headers.get("x-forwarded-for", ""))

    if forwarded_addresses:
        chain = [*forwarded_addresses, peer_ip]

        for address in reversed(chain):
            if not ip_is_trusted_proxy(address, trusted_networks):
                return str(address)

        return str(forwarded_addresses[0])

    real_ip = parse_ip_address(request.headers.get("x-real-ip", ""))

    if real_ip is not None:
        return str(real_ip)

    return None


def get_client_ip(request: Request) -> str:
    peer_host = request.client.host if request.client and request.client.host else ""
    peer_ip = parse_ip_address(peer_host)

    if peer_ip is not None and ip_is_trusted_proxy(peer_ip):
        forwarded_client_ip = get_forwarded_client_ip(request, peer_ip)

        if forwarded_client_ip:
            return forwarded_client_ip

    if peer_host:
        return peer_host

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
