from __future__ import annotations

import base64
from dataclasses import dataclass
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
import multiprocessing
import os
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit


logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 16 * 1024
MAX_REMOTE_BYTES = 10 * 1024 * 1024
MAX_RESULT_BYTES = 14 * 1024 * 1024 + 64 * 1024
MAX_REDIRECTS = 5
FETCH_SLOT = threading.BoundedSemaphore(value=2)
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


class RemoteFetchError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    hostname: str
    port: int
    request_target: str
    addresses: tuple[str, ...]


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RemoteFetchError("remote_timeout")
    return remaining


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_unspecified
        and address not in CGNAT_NETWORK
    )


def validate_target(
    url: str,
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
) -> ValidatedTarget:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise RemoteFetchError("remote_url_invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in url):
        raise RemoteFetchError("remote_url_invalid")

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise RemoteFetchError("remote_url_invalid") from error

    if parsed.scheme.lower() != "https" or not hostname:
        raise RemoteFetchError("remote_url_invalid")
    if parsed.username is not None or parsed.password is not None:
        raise RemoteFetchError("remote_url_invalid")
    if port not in (None, 443):
        raise RemoteFetchError("remote_url_invalid")
    if any(character.isspace() for character in hostname):
        raise RemoteFetchError("remote_url_invalid")

    try:
        ascii_hostname = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise RemoteFetchError("remote_url_invalid") from error
    if not ascii_hostname or len(ascii_hostname) > 253:
        raise RemoteFetchError("remote_url_invalid")

    try:
        resolved = resolver(ascii_hostname, 443, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as error:
        raise RemoteFetchError("remote_unreachable") from error

    addresses: list[str] = []
    for item in resolved:
        try:
            address = str(ipaddress.ip_address(item[4][0]))
        except (IndexError, TypeError, ValueError) as error:
            raise RemoteFetchError("remote_dns_disallowed") from error
        if address not in addresses:
            addresses.append(address)

    # Fail closed for mixed answers. A connection is pinned below, but rejecting
    # any non-public answer also prevents ambiguous split-horizon DNS policy.
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise RemoteFetchError("remote_dns_disallowed")

    request_target = parsed.path or "/"
    if parsed.query:
        request_target = f"{request_target}?{parsed.query}"
    try:
        request_target.encode("ascii")
    except UnicodeEncodeError as error:
        raise RemoteFetchError("remote_url_invalid") from error

    canonical_netloc = f"[{ascii_hostname}]" if ":" in ascii_hostname else ascii_hostname
    canonical = urlunsplit(("https", canonical_netloc, parsed.path or "/", parsed.query, ""))
    return ValidatedTarget(
        url=canonical,
        hostname=ascii_hostname,
        port=443,
        request_target=request_target,
        addresses=tuple(addresses),
    )


def _pinned_https_request(
    target: ValidatedTarget,
    *,
    deadline: float,
    connection_factory: Callable[..., socket.socket] = socket.create_connection,
    ssl_context: ssl.SSLContext | None = None,
) -> tuple[int, dict[str, str], bytes]:
    raw_socket = None
    tls_socket = None
    response = None
    try:
        # The connection target is the validated numeric address. No hostname
        # resolution occurs after validation.
        raw_socket = connection_factory(
            (target.addresses[0], target.port), timeout=_remaining(deadline)
        )
        context = ssl_context or ssl.create_default_context()
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise RemoteFetchError("remote_tls_error")
        raw_socket.settimeout(_remaining(deadline))
        tls_socket = context.wrap_socket(raw_socket, server_hostname=target.hostname)
        raw_socket = None
        tls_socket.settimeout(_remaining(deadline))

        host_header = f"[{target.hostname}]" if ":" in target.hostname else target.hostname
        request = (
            f"GET {target.request_target} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "User-Agent: Madar-Remote-Ingestion/1\r\n"
            "Accept: text/csv,application/json,application/vnd.ms-excel,"
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.1\r\n"
            "Accept-Encoding: identity\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        tls_socket.sendall(request)
        tls_socket.settimeout(_remaining(deadline))
        response = HTTPResponse(tls_socket)
        response.begin()

        headers = {name.lower(): value.strip() for name, value in response.getheaders()}
        encoding = headers.get("content-encoding", "").lower()
        if encoding not in {"", "identity"}:
            raise RemoteFetchError("remote_content_invalid")
        content_length = headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError as error:
                raise RemoteFetchError("remote_content_invalid") from error
            if declared_length < 0 or declared_length > MAX_REMOTE_BYTES:
                raise RemoteFetchError("remote_too_large")

        chunks: list[bytes] = []
        total = 0
        while True:
            tls_socket.settimeout(_remaining(deadline))
            chunk = response.read(min(64 * 1024, MAX_REMOTE_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_REMOTE_BYTES:
                raise RemoteFetchError("remote_too_large")
            chunks.append(chunk)
        return response.status, headers, b"".join(chunks)
    except RemoteFetchError:
        raise
    except (ssl.SSLError, ssl.CertificateError) as error:
        raise RemoteFetchError("remote_tls_error") from error
    except (TimeoutError, socket.timeout) as error:
        raise RemoteFetchError("remote_timeout") from error
    except OSError as error:
        raise RemoteFetchError("remote_unreachable") from error
    finally:
        if response is not None:
            response.close()
        elif tls_socket is not None:
            tls_socket.close()
        elif raw_socket is not None:
            raw_socket.close()


def fetch_remote(
    payload: dict[str, Any],
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    request_target: Callable[..., tuple[int, dict[str, str], bytes]] = _pinned_https_request,
    deadline_seconds: float | None = None,
) -> dict[str, Any]:
    if set(payload) - {"url", "tenant_id", "user_id", "request_id"}:
        raise RemoteFetchError("remote_request_invalid")
    url = payload.get("url")
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    request_id = payload.get("request_id")
    if (
        not isinstance(url, str)
        or tenant_id in (None, "")
        or user_id in (None, "")
        or not isinstance(request_id, str)
        or not request_id
        or len(str(tenant_id)) > 128
        or len(str(user_id)) > 128
        or len(request_id) > 128
    ):
        raise RemoteFetchError("remote_request_invalid")

    configured = deadline_seconds
    if configured is None:
        configured = float(os.getenv("REMOTE_INGESTION_DEADLINE_SECONDS", "35"))
    deadline = time.monotonic() + max(1.0, min(configured, 55.0))
    current_url = url
    seen: set[str] = set()

    for redirect_count in range(MAX_REDIRECTS + 1):
        _remaining(deadline)
        target = validate_target(current_url, resolver=resolver)
        if target.url in seen:
            raise RemoteFetchError("remote_redirect_disallowed")
        seen.add(target.url)
        status, headers, content = request_target(target, deadline=deadline)
        if status in {301, 302, 303, 307, 308}:
            if redirect_count >= MAX_REDIRECTS:
                raise RemoteFetchError("remote_redirect_disallowed")
            location = headers.get("location")
            if not location:
                raise RemoteFetchError("remote_redirect_disallowed")
            current_url = urljoin(target.url, location)
            continue
        if status < 200 or status >= 300:
            raise RemoteFetchError("remote_unreachable")
        result = {
            "status": "ok",
            "request_id": request_id,
            "final_url": target.url,
            "content_type": headers.get("content-type", "")[:512],
            "content_b64": base64.b64encode(content).decode("ascii"),
        }
        if len(json.dumps(result, separators=(",", ":")).encode("utf-8")) > MAX_RESULT_BYTES:
            raise RemoteFetchError("remote_too_large")
        return result

    raise RemoteFetchError("remote_redirect_disallowed")


def _fetch_child(payload: dict[str, Any], result_path: str) -> None:
    try:
        result = fetch_remote(payload)
        envelope = {"ok": True, "result": result}
    except RemoteFetchError as error:
        envelope = {"ok": False, "error_code": error.code}
    except Exception as error:
        envelope = {"ok": False, "error_code": "remote_internal_error", "error_type": type(error).__name__}
    encoded = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        encoded = b'{"ok":false,"error_code":"remote_too_large"}'
    Path(result_path).write_bytes(encoded)


def fetch_remote_with_timeout(payload: dict[str, Any]) -> dict[str, Any]:
    timeout = max(
        1.0,
        min(float(os.getenv("REMOTE_INGESTION_HARD_TIMEOUT_SECONDS", "40")), 60.0),
    )
    result_path = ""
    process = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="madar-egress-result-", suffix=".json", delete=False
        ) as result_file:
            result_path = result_file.name
        context = multiprocessing.get_context("spawn")
        process = context.Process(target=_fetch_child, args=(payload, result_path), daemon=True)
        process.start()
        process.join(timeout)
        if process.is_alive():
            process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill()
                process.join(2)
            raise RemoteFetchError("remote_timeout")
        if process.exitcode != 0:
            raise RemoteFetchError("remote_internal_error")
        result_file = Path(result_path)
        if not result_file.is_file() or result_file.stat().st_size > MAX_RESULT_BYTES:
            raise RemoteFetchError("remote_internal_error")
        envelope = json.loads(result_file.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict):
            raise RemoteFetchError("remote_internal_error")
        if envelope.get("ok") is not True:
            raise RemoteFetchError(str(envelope.get("error_code") or "remote_internal_error"))
        result = envelope.get("result")
        if not isinstance(result, dict):
            raise RemoteFetchError("remote_internal_error")
        return result
    finally:
        if process is not None and process.is_alive():
            process.kill()
            process.join(2)
        if result_path:
            Path(result_path).unlink(missing_ok=True)


class RemoteIngestionHandler(BaseHTTPRequestHandler):
    server_version = "MadarRemoteIngestion/1"

    def log_message(self, _format: str, *_args) -> None:
        return

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._write_json(404, {"status": "not_found"})
            return
        self._write_json(
            200,
            {"status": "ok", "isolation": "remote_ingestion_worker", "policy": "pinned_https_v1"},
        )

    def do_POST(self) -> None:
        if self.path != "/fetch":
            self._write_json(404, {"status": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._write_json(413, {"status": "remote_request_invalid"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise RemoteFetchError("remote_request_invalid")
            if not FETCH_SLOT.acquire(blocking=False):
                self._write_json(503, {"status": "remote_busy"})
                return
            try:
                result = fetch_remote_with_timeout(payload)
            finally:
                FETCH_SLOT.release()
        except RemoteFetchError as error:
            status = 413 if error.code == "remote_too_large" else 504 if error.code == "remote_timeout" else 422
            logger.warning("remote_ingestion.rejected", extra={"error_code": error.code})
            self._write_json(status, {"status": error.code})
            return
        except Exception as error:
            logger.error("remote_ingestion.failed", extra={"error_type": type(error).__name__})
            self._write_json(500, {"status": "remote_internal_error"})
            return
        self._write_json(200, result)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    host = os.getenv("REMOTE_INGESTION_WORKER_HOST", "0.0.0.0").strip()
    port = int(os.getenv("REMOTE_INGESTION_WORKER_PORT", "8093"))
    server = ThreadingHTTPServer((host, port), RemoteIngestionHandler)
    logger.info("remote_ingestion_worker.started", extra={"port": port})
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
