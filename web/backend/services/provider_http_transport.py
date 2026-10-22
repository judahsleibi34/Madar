"""Server-controlled outbound HTTP transport for allow-listed API providers (C2).

Security contract:

* Destinations come only from the operator provider registry; no user-supplied URL,
  header or credential ever reaches this module.
* HTTPS destinations are validated with the remote-ingestion worker's
  ``validate_target`` (DNS resolution, public-address-only answers, port 443) and the
  connection is pinned to the validated address for the whole session, so a DNS
  rebinding between validation and connect cannot redirect traffic.
* Only idempotent GET requests exist. Redirects are never followed.
* Response bytes, decompressed bytes, JSON depth and elapsed time are bounded.
* Retries apply only to rate limits (bounded Retry-After), 5xx and transport errors,
  with exponential backoff and jitter, inside the run deadline.
* Plain-HTTP loopback is a test-only exception: ``APP_ENV`` must be exactly ``test``
  and the host must be 127.0.0.1/localhost. Every other environment fails closed.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import os
import random
import socket
import ssl
import threading
import time
import zlib
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import quote, urlencode, urlsplit

from workers.remote_ingestion_worker import RemoteFetchError, validate_target


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_DECOMPRESSED_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 24
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0
USER_AGENT = "Madar-Provider-Connector/1"
LOOPBACK_HOSTS = {"127.0.0.1": "127.0.0.1", "localhost": "127.0.0.1"}


class TransportError(Exception):
    """Classified transport failure. ``code`` is safe to log; nothing else is kept."""

    def __init__(self, code: str, *, retryable: bool = False, retry_after: float | None = None):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


class SecretValue:
    """Credential material. Never rendered by repr/str/format or serialized."""

    __slots__ = ("_value",)

    def __init__(self, value: str):
        if not isinstance(value, str) or not value or len(value) > 4096 or any(
            ord(character) < 33 or ord(character) == 127 for character in value
        ):
            raise ValueError("invalid secret")
        self._value = value

    def reveal_for_request(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return "<redacted>"

    def __reduce__(self):
        raise TypeError("SecretValue cannot be serialized")


@dataclass(frozen=True)
class Destination:
    scheme: str
    hostname: str
    port: int
    address: str
    base_path: str


def _test_loopback_allowed() -> bool:
    # Exact match on the raw variable: a missing APP_ENV never enables loopback.
    return os.environ.get("APP_ENV") == "test"


def validate_destination(
    base_url: str,
    *,
    test_loopback: bool = False,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
) -> Destination:
    """Validate an operator-registered base URL and pin it to one address."""
    try:
        parsed = urlsplit(base_url)
    except ValueError as error:
        raise TransportError("destination_invalid") from error
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise TransportError("destination_invalid")
    base_path = (parsed.path or "/").rstrip("/") or ""
    if any(segment in {".", ".."} for segment in base_path.split("/")):
        raise TransportError("destination_invalid")

    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower()
        if not (test_loopback and _test_loopback_allowed() and host in LOOPBACK_HOSTS):
            raise TransportError("destination_forbidden")
        port = parsed.port
        if port is None or not 1024 <= port <= 65535:
            raise TransportError("destination_invalid")
        return Destination("http", host, port, LOOPBACK_HOSTS[host], base_path)

    if parsed.scheme != "https":
        raise TransportError("destination_forbidden")
    try:
        target = validate_target(f"https://{parsed.netloc}/", resolver=resolver)
    except RemoteFetchError as error:
        code = "destination_forbidden" if error.code == "remote_dns_disallowed" else (
            "provider_unreachable" if error.code == "remote_unreachable" else "destination_invalid")
        raise TransportError(code) from error
    return Destination("https", target.hostname, 443, target.addresses[0], base_path)


def build_target(destination: Destination, path: str, params: dict[str, str]) -> str:
    """Request target from a registry path template and allow-listed parameters."""
    if not path.startswith("/") or "//" in path or ".." in path or "?" in path or "#" in path:
        raise TransportError("request_invalid")
    for name, value in params.items():
        if (
            not isinstance(name, str) or not name.replace("_", "").isalnum()
            or not isinstance(value, str) or len(value) > 1024
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise TransportError("request_invalid")
    target = quote(destination.base_path + path, safe="/-_.~")
    if params:
        target += "?" + urlencode(sorted(params.items()))
    if len(target) > 4096:
        raise TransportError("request_invalid")
    return target


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to the validated address with SNI and certificate checks for the name."""

    def __init__(self, destination: Destination, timeout: float):
        super().__init__(destination.hostname, destination.port, timeout=timeout)
        self._address = destination.address

    def connect(self):
        sock = socket.create_connection((self._address, self.port), self.timeout)
        context = self._context
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            sock.close()
            raise TransportError("tls_invalid")
        self.sock = context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, destination: Destination, timeout: float):
        super().__init__(destination.hostname, destination.port, timeout=timeout)
        self._address = destination.address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class ProviderRateLimiter:
    """Process-local minimum interval between requests per provider."""

    def __init__(self):
        self._lock = threading.Lock()
        self._next: dict[str, float] = {}

    def wait(self, provider_key: str, min_interval: float, *, deadline: float,
             clock=time.monotonic, sleep=time.sleep) -> None:
        with self._lock:
            now = clock()
            start = max(now, self._next.get(provider_key, now))
            if start > deadline:
                raise TransportError("rate_limited")
            self._next[provider_key] = start + max(0.0, min_interval)
        if start > now:
            sleep(start - now)


RATE_LIMITER = ProviderRateLimiter()


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TransportError("payload_invalid")
        result[key] = value
    return result


def _reject_constant(_value):
    raise TransportError("payload_invalid")


def _depth(value, limit: int) -> None:
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > limit:
            raise TransportError("payload_invalid")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)


def parse_json(body: bytes) -> object:
    try:
        text = body.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys,
                           parse_constant=_reject_constant)
    except TransportError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise TransportError("payload_invalid") from error
    _depth(value, MAX_JSON_DEPTH)
    return value


def _decompress(body: bytes, encoding: str) -> bytes:
    if encoding in ("", "identity"):
        return body
    if encoding != "gzip":
        raise TransportError("payload_invalid")
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        output = decompressor.decompress(body, MAX_DECOMPRESSED_BYTES + 1)
    except zlib.error as error:
        raise TransportError("payload_invalid") from error
    if len(output) > MAX_DECOMPRESSED_BYTES or decompressor.unconsumed_tail:
        raise TransportError("payload_too_large")
    if not decompressor.eof:
        raise TransportError("payload_invalid")
    return output


@dataclass
class ProviderHttpSession:
    """One run's connection to one destination (keep-alive, pinned address)."""

    provider_key: str
    destination: Destination
    credential: SecretValue | None = None
    credential_validator: Callable[[], None] | None = None
    credential_reference: dict[str, object] | None = None
    auth_scheme: str = "bearer"
    min_interval: float = 0.0
    cancelled: Callable[[], bool] = lambda: False
    heartbeat: Callable[[], None] | None = None
    audit: Callable[[dict[str, object]], None] | None = None
    max_response_bytes: int = MAX_RESPONSE_BYTES
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    rng: random.Random = field(default_factory=random.Random)
    limiter: ProviderRateLimiter = RATE_LIMITER
    attempts: int = 0
    _connection: object = None

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    def _open(self, timeout: float):
        if self._connection is None:
            factory = _PinnedHTTPSConnection if self.destination.scheme == "https" \
                else _PinnedHTTPConnection
            self._connection = factory(self.destination, timeout)
        self._connection.timeout = timeout
        if getattr(self._connection, "sock", None) is not None:
            self._connection.sock.settimeout(timeout)
        return self._connection

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, identity",
            "Connection": "keep-alive",
        }
        if self.credential is not None:
            if self.auth_scheme != "bearer":
                raise TransportError("request_invalid")
            headers["Authorization"] = "Bearer " + self.credential.reveal_for_request()
        return headers

    def get_json(self, path: str, params: dict[str, str], *, deadline: float) -> object:
        target = build_target(self.destination, path, params)
        last: TransportError | None = None
        for attempt in range(MAX_ATTEMPTS):
            if self.cancelled():
                raise TransportError("cancelled")
            if self.heartbeat is not None:
                self.heartbeat()
            if self.credential_validator is not None:
                try:
                    self.credential_validator()
                except Exception as error:
                    raise TransportError("unauthorized") from error
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise TransportError("timeout")
            self.limiter.wait(self.provider_key, self.min_interval, deadline=deadline,
                              clock=self.clock, sleep=self.sleep)
            try:
                self.attempts += 1
                started = self.clock()
                value, status, response_bytes = self._once(
                    target, min(REQUEST_TIMEOUT_SECONDS, remaining), deadline=deadline,
                )
                self._audit({
                    "event": "provider_http_request",
                    "provider_key": self.provider_key,
                    "outcome": "succeeded",
                    "status": status,
                    "attempt": attempt + 1,
                    "response_bytes": response_bytes,
                    "elapsed_ms": max(0, int((self.clock() - started) * 1000)),
                })
                return value
            except TransportError as error:
                self._audit({
                    "event": "provider_http_request",
                    "provider_key": self.provider_key,
                    "outcome": "failed",
                    "error_code": error.code,
                    "attempt": attempt + 1,
                })
                if not error.retryable:
                    self.close()
                    raise
                last = error
                self.close()
                if attempt == MAX_ATTEMPTS - 1:
                    break
                delay = error.retry_after if error.retry_after is not None else (
                    0.2 * (2 ** attempt) * (1 + self.rng.random()))
                if self.clock() + delay >= deadline or self.cancelled():
                    break
                self.sleep(delay)
        assert last is not None
        raise TransportError(last.code)

    def _audit(self, metadata: dict[str, object]) -> None:
        if self.audit is not None:
            # Callers receive only the fixed provider identity and bounded result
            # metadata. Request targets, response bodies and credentials are never
            # included in transport audit events.
            self.audit(metadata)

    def _once(self, target: str, timeout: float, *, deadline: float) -> tuple[object, int, int]:
        try:
            connection = self._open(timeout)
            connection.request("GET", target, headers=self._headers())
            response = connection.getresponse()
            status = response.status
            headers = {name.lower(): value.strip() for name, value in response.getheaders()}
            declared = headers.get("content-length")
            if declared is not None:
                try:
                    if int(declared) > self.max_response_bytes or int(declared) < 0:
                        raise TransportError("payload_too_large")
                except ValueError as error:
                    raise TransportError("payload_invalid") from error
            chunks: list[bytes] = []
            total = 0
            while True:
                if self.cancelled():
                    raise TransportError("cancelled")
                if self.clock() >= deadline:
                    raise TransportError("timeout")
                if self.heartbeat is not None:
                    self.heartbeat()
                active_socket = getattr(connection, "sock", None)
                if active_socket is not None:
                    active_socket.settimeout(max(0.001, min(timeout, deadline - self.clock())))
                chunk = response.read(min(64 * 1024, self.max_response_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > self.max_response_bytes:
                    raise TransportError("payload_too_large")
                chunks.append(chunk)
            body = b"".join(chunks)
            if headers.get("connection", "").lower() == "close" or response.will_close:
                self.close()
        except TransportError:
            self.close()
            raise
        except (socket.timeout, TimeoutError) as error:
            raise TransportError("timeout", retryable=True) from error
        except (OSError, http.client.HTTPException) as error:
            raise TransportError("provider_unreachable", retryable=True) from error

        if 300 <= status < 400:
            raise TransportError("redirect_refused")
        if status in (401, 403):
            raise TransportError("unauthorized")
        if status == 429:
            retry_after = None
            try:
                retry_after = float(headers.get("retry-after", ""))
            except ValueError:
                pass
            if retry_after is None or not 0 <= retry_after <= MAX_RETRY_AFTER_SECONDS:
                raise TransportError("rate_limited")
            raise TransportError("rate_limited", retryable=True, retry_after=retry_after)
        if 500 <= status < 600:
            raise TransportError("provider_unavailable", retryable=True)
        if status != 200:
            raise TransportError("request_rejected")
        content_type = headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            raise TransportError("payload_invalid")
        return (
            parse_json(_decompress(body, headers.get("content-encoding", "").lower())),
            status,
            len(body),
        )


def is_public_address(value: str) -> bool:
    """Re-exported check used by tests and documentation of the address policy."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    from workers.remote_ingestion_worker import _is_public_address

    return _is_public_address(str(address))


__all__ = [
    "Destination", "ProviderHttpSession", "ProviderRateLimiter", "SecretValue",
    "TransportError", "build_target", "is_public_address", "parse_json",
    "validate_destination",
]
