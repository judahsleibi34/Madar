"""Private immutable object storage for Data Sources artifacts.

Production uses the already-supported private Supabase Storage service.  A tiny
loopback HTTP backend exists only for isolated multi-process tests; it is
impossible to enable outside APP_ENV=test.  Callers never provide buckets or
object keys -- both are fixed/generated server-side.
"""
from __future__ import annotations

import hashlib
import os
import re
import socket
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import httpx

from services.supabase_api_key import supabase_api_headers

IMMUTABLE_BUCKET = "madar-data-immutable"
MAX_OBJECT_BYTES = 100 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


class ObjectErrorCategory(str, Enum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    CONFLICT = "conflict"
    MISSING = "missing"
    CORRUPT = "corrupt"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class ImmutableObjectError(RuntimeError):
    def __init__(self, category: ObjectErrorCategory, code: str):
        super().__init__(code)
        self.category = category
        self.code = code

    @property
    def retryable(self) -> bool:
        return self.category in {ObjectErrorCategory.TIMEOUT, ObjectErrorCategory.UNAVAILABLE}


@dataclass(frozen=True)
class ImmutableObject:
    backend: str
    bucket: str
    object_key: str
    size_bytes: int
    sha256: str


def sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_OBJECT_BYTES:
                raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_too_large")
            digest.update(chunk)
    if size <= 0:
        raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_empty")
    return digest.hexdigest(), size


def generated_object_key(*, tenant_id: int, reservation_id: str, sha256: str, suffix: str) -> str:
    reservation = str(reservation_id or "").lower()
    digest = str(sha256 or "").lower()
    normalized_suffix = str(suffix or "").lower()
    if not re.fullmatch(r"[0-9a-f-]{36}", reservation) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_identity_invalid")
    if normalized_suffix not in {".csv", ".xls", ".xlsx"}:
        raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_format_invalid")
    return f"tenant_{int(tenant_id)}/dataset/{reservation}/{digest}{normalized_suffix}"


def validate_object_identity(*, tenant_id: int, descriptor: ImmutableObject) -> None:
    prefix = f"tenant_{int(tenant_id)}/dataset/"
    if descriptor.bucket != IMMUTABLE_BUCKET or not descriptor.object_key.startswith(prefix):
        raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_scope_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", descriptor.sha256) \
            or descriptor.size_bytes <= 0 or descriptor.size_bytes > MAX_OBJECT_BYTES:
        raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_integrity_invalid")


def _classify(error: Exception, *, missing: bool = False) -> ImmutableObjectError:
    if isinstance(error, ImmutableObjectError):
        return error
    text = str(error).lower()
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if isinstance(error, (TimeoutError, socket.timeout, httpx.TimeoutException)) \
            or "timeout" in text:
        category = ObjectErrorCategory.TIMEOUT
    elif isinstance(error, httpx.NetworkError):
        category = ObjectErrorCategory.UNAVAILABLE
    elif missing or (isinstance(error, HTTPError) and error.code == 404) \
            or status_code == 404 or "not found" in text:
        category = ObjectErrorCategory.MISSING
    elif (isinstance(error, HTTPError) and error.code in {409, 412}) \
            or status_code in {409, 412} or "already exists" in text or "duplicate" in text:
        category = ObjectErrorCategory.CONFLICT
    else:
        category = ObjectErrorCategory.UNAVAILABLE
    return ImmutableObjectError(category, f"immutable_object_{category.value}")


def _write_verified_stream(*, chunks, target_path: Path, descriptor: ImmutableObject,
                           cancelled) -> Path:
    """Write one provider response incrementally and publish only verified bytes."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.parent / f".{target_path.name}.{uuid4().hex}.partial"
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary.open("xb") as output:
            os.chmod(temporary, 0o600)
            for chunk in chunks:
                if cancelled():
                    raise ImmutableObjectError(
                        ObjectErrorCategory.CANCELLED, "immutable_object_cancelled",
                    )
                if not chunk:
                    continue
                size += len(chunk)
                if size > descriptor.size_bytes or size > MAX_OBJECT_BYTES:
                    raise ImmutableObjectError(
                        ObjectErrorCategory.CORRUPT, "immutable_object_size_mismatch",
                    )
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        if size != descriptor.size_bytes or digest.hexdigest() != descriptor.sha256:
            raise ImmutableObjectError(
                ObjectErrorCategory.CORRUPT, "immutable_object_integrity_mismatch",
            )
        os.replace(temporary, target_path)
        return target_path
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


class SupabaseImmutableObjectStore:
    backend = "supabase_private"

    def __init__(self, *, client=None, use_streaming_transport: bool = False,
                 http_client_factory=None):
        if client is None:
            from database import service_supabase
            client = service_supabase
        self.client = client
        self.use_streaming_transport = use_streaming_transport
        self.http_client_factory = http_client_factory or (lambda: httpx.Client(
            timeout=httpx.Timeout(30, connect=10, read=60),
            follow_redirects=False, trust_env=False,
        ))

    def _bucket(self):
        try:
            self.client.storage.get_bucket(IMMUTABLE_BUCKET)
        except Exception as error:
            raise _classify(error, missing=True) from error
        return self.client.storage.from_(IMMUTABLE_BUCKET)

    def read(self, *, tenant_id: int, descriptor: ImmutableObject,
             cancelled=lambda: False) -> bytes:
        """Compatibility helper; callers needing bounded memory use download_to_path."""
        validate_object_identity(tenant_id=tenant_id, descriptor=descriptor)
        with tempfile.TemporaryDirectory(prefix="madar-immutable-read-") as root:
            path = self.download_to_path(
                tenant_id=tenant_id, descriptor=descriptor,
                target_path=Path(root) / "object", cancelled=cancelled,
            )
            return path.read_bytes()

    @staticmethod
    def _verify(content: bytes, descriptor: ImmutableObject) -> None:
        if len(content) != descriptor.size_bytes or hashlib.sha256(content).hexdigest() != descriptor.sha256:
            raise ImmutableObjectError(ObjectErrorCategory.CORRUPT, "immutable_object_integrity_mismatch")

    def download_to_path(self, *, tenant_id: int, descriptor: ImmutableObject,
                         target_path: Path, cancelled=lambda: False) -> Path:
        validate_object_identity(tenant_id=tenant_id, descriptor=descriptor)
        if cancelled():
            raise ImmutableObjectError(ObjectErrorCategory.CANCELLED, "immutable_object_cancelled")
        if not self.use_streaming_transport:
            try:
                content = self._bucket().download(descriptor.object_key)
            except Exception as error:
                raise _classify(error) from error
            if not isinstance(content, bytes):
                raise ImmutableObjectError(
                    ObjectErrorCategory.CORRUPT, "immutable_object_invalid_response",
                )
            return _write_verified_stream(
                chunks=(content[offset:offset + CHUNK_BYTES]
                        for offset in range(0, len(content), CHUNK_BYTES)),
                target_path=target_path, descriptor=descriptor, cancelled=cancelled,
            )

        base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if not base_url or not service_key:
            raise ImmutableObjectError(
                ObjectErrorCategory.INVALID, "immutable_object_transport_unconfigured",
            )
        url = (f"{base_url}/storage/v1/object/{quote(descriptor.bucket, safe='')}/"
               f"{quote(descriptor.object_key, safe='/')}")
        headers = {**supabase_api_headers(service_key), "Accept-Encoding": "identity"}
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with self.http_client_factory() as transport, \
                        transport.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ImmutableObjectError(
                            ObjectErrorCategory.CORRUPT,
                            "immutable_object_unexpected_encoding",
                        )
                    length = response.headers.get("content-length")
                    if length is not None:
                        try:
                            length_value = int(length)
                        except ValueError as error:
                            raise ImmutableObjectError(
                                ObjectErrorCategory.CORRUPT,
                                "immutable_object_size_invalid",
                            ) from error
                        if length_value != descriptor.size_bytes:
                            raise ImmutableObjectError(
                                ObjectErrorCategory.CORRUPT,
                                "immutable_object_size_mismatch",
                            )
                    return _write_verified_stream(
                        chunks=response.iter_raw(CHUNK_BYTES), target_path=target_path,
                        descriptor=descriptor, cancelled=cancelled,
                    )
            except (httpx.HTTPError, ImmutableObjectError, ValueError) as error:
                classified = _classify(error)
                last_error = classified
                target_path.unlink(missing_ok=True)
                if classified.category in {
                    ObjectErrorCategory.MISSING, ObjectErrorCategory.INVALID,
                    ObjectErrorCategory.CANCELLED,
                } or attempt == 1:
                    raise classified from error
        raise last_error or ImmutableObjectError(
            ObjectErrorCategory.UNAVAILABLE, "immutable_object_unavailable",
        )

    def verify(self, *, tenant_id: int, descriptor: ImmutableObject,
               cancelled=lambda: False) -> None:
        with tempfile.TemporaryDirectory(prefix="madar-immutable-verify-") as root:
            self.download_to_path(
                tenant_id=tenant_id, descriptor=descriptor,
                target_path=Path(root) / "object", cancelled=cancelled,
            )

    def write(self, *, tenant_id: int, reservation_id: str, source_path: Path,
              suffix: str, cancelled=lambda: False) -> ImmutableObject:
        digest, size = sha256_path(source_path)
        descriptor = ImmutableObject(
            backend=self.backend, bucket=IMMUTABLE_BUCKET,
            object_key=generated_object_key(
                tenant_id=tenant_id, reservation_id=reservation_id,
                sha256=digest, suffix=suffix,
            ),
            size_bytes=size, sha256=digest,
        )
        if cancelled():
            raise ImmutableObjectError(ObjectErrorCategory.CANCELLED, "immutable_object_cancelled")
        try:
            self._bucket().upload(
                path=descriptor.object_key,
                file=source_path,
                file_options={
                    "content-type": "text/csv" if suffix == ".csv" else "application/octet-stream",
                    "cache-control": "31536000",
                    "upsert": "false",
                },
            )
        except Exception as error:
            classified = _classify(error)
            if classified.category != ObjectErrorCategory.CONFLICT:
                raise classified from error
        # A duplicate is successful only when the existing immutable bytes are identical.
        self.verify(tenant_id=tenant_id, descriptor=descriptor, cancelled=cancelled)
        return descriptor

    def delete(self, *, tenant_id: int, descriptor: ImmutableObject) -> None:
        validate_object_identity(tenant_id=tenant_id, descriptor=descriptor)
        try:
            self._bucket().remove([descriptor.object_key])
        except Exception as error:
            raise _classify(error) from error


class LoopbackHttpImmutableObjectStore:
    """Test-only provider used to prove cross-process behavior over HTTP."""
    backend = "test_http"

    def __init__(self, base_url: str):
        parsed = urlsplit(base_url)
        if os.getenv("APP_ENV") != "test" or parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ImmutableObjectError(ObjectErrorCategory.INVALID, "test_object_store_forbidden")
        self.base_url = base_url.rstrip("/")

    def _url(self, descriptor: ImmutableObject) -> str:
        return f"{self.base_url}/{descriptor.bucket}/{descriptor.object_key}"

    def read(self, *, tenant_id: int, descriptor: ImmutableObject, cancelled=lambda: False) -> bytes:
        with tempfile.TemporaryDirectory(prefix="madar-loopback-read-") as root:
            path = self.download_to_path(
                tenant_id=tenant_id, descriptor=descriptor,
                target_path=Path(root) / "object", cancelled=cancelled,
            )
            return path.read_bytes()

    def download_to_path(self, *, tenant_id: int, descriptor: ImmutableObject,
                         target_path: Path, cancelled=lambda: False) -> Path:
        validate_object_identity(tenant_id=tenant_id, descriptor=descriptor)
        if cancelled():
            raise ImmutableObjectError(ObjectErrorCategory.CANCELLED, "immutable_object_cancelled")
        try:
            with urlopen(Request(self._url(descriptor), method="GET"), timeout=5) as response:
                return _write_verified_stream(
                    chunks=iter(lambda: response.read(CHUNK_BYTES), b""),
                    target_path=target_path, descriptor=descriptor, cancelled=cancelled,
                )
        except (HTTPError, URLError, TimeoutError) as error:
            raise _classify(error) from error

    def verify(self, *, tenant_id: int, descriptor: ImmutableObject,
               cancelled=lambda: False) -> None:
        with tempfile.TemporaryDirectory(prefix="madar-loopback-verify-") as root:
            self.download_to_path(
                tenant_id=tenant_id, descriptor=descriptor,
                target_path=Path(root) / "object", cancelled=cancelled,
            )

    def write(self, *, tenant_id: int, reservation_id: str, source_path: Path,
              suffix: str, cancelled=lambda: False) -> ImmutableObject:
        digest, size = sha256_path(source_path)
        descriptor = ImmutableObject(
            backend=self.backend, bucket=IMMUTABLE_BUCKET,
            object_key=generated_object_key(tenant_id=tenant_id, reservation_id=reservation_id,
                                            sha256=digest, suffix=suffix),
            size_bytes=size, sha256=digest,
        )
        if cancelled():
            raise ImmutableObjectError(ObjectErrorCategory.CANCELLED, "immutable_object_cancelled")
        try:
            with source_path.open("rb") as source:
                request = Request(self._url(descriptor), data=source.read(), method="PUT",
                                  headers={"If-None-Match": "*"})
                urlopen(request, timeout=5).close()
        except HTTPError as error:
            if error.code not in {409, 412}:
                raise _classify(error) from error
        except (URLError, TimeoutError) as error:
            raise _classify(error) from error
        self.verify(tenant_id=tenant_id, descriptor=descriptor, cancelled=cancelled)
        return descriptor

    def delete(self, *, tenant_id: int, descriptor: ImmutableObject) -> None:
        validate_object_identity(tenant_id=tenant_id, descriptor=descriptor)
        try:
            urlopen(Request(self._url(descriptor), method="DELETE"), timeout=5).close()
        except (HTTPError, URLError, TimeoutError) as error:
            raise _classify(error) from error


def configured_store(*, client=None):
    backend = os.getenv("DATA_IMMUTABLE_STORAGE_BACKEND", "supabase").strip().lower()
    if backend == "supabase":
        return SupabaseImmutableObjectStore(client=client, use_streaming_transport=True)
    if backend == "test_http":
        return LoopbackHttpImmutableObjectStore(os.getenv("DATA_IMMUTABLE_TEST_URL", ""))
    raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_backend_invalid")


def descriptor_from_row(row: dict) -> ImmutableObject:
    try:
        descriptor = ImmutableObject(
            backend=str(row["storage_backend"]), bucket=str(row["storage_bucket"]),
            object_key=str(row["provider_object_key"]),
            size_bytes=int(row["verified_size_bytes"]),
            sha256=str(row["verified_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ImmutableObjectError(ObjectErrorCategory.INVALID, "immutable_object_metadata_invalid") from error
    return descriptor
