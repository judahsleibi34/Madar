"""Bounded, allow-listed API-provider contract for Data Sources.

This milestone deliberately ships only deterministic non-production fixtures. The
provider registry, credential boundary and pinned HTTP transport are resolved lazily
so the normalization contract stays independent of any named provider.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Protocol, Sequence

MAX_API_PAGES = 10
MAX_API_RECORDS = 10_000
MAX_API_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_API_COLUMNS = 256
MAX_API_CELL_CHARS = 32_768
DEFAULT_API_TIMEOUT_SECONDS = 15.0


class ProviderErrorCategory(str, Enum):
    CANCELLED = "provider_cancelled"
    TIMEOUT = "provider_timeout"
    UNAVAILABLE = "provider_unavailable"
    UNAUTHORIZED = "provider_unauthorized"
    RATE_LIMITED = "provider_rate_limited"
    DESTINATION_FORBIDDEN = "provider_destination_forbidden"
    INVALID_RESPONSE = "provider_payload_invalid"
    PAYLOAD_TOO_LARGE = "provider_payload_too_large"


class ProviderFetchError(Exception):
    def __init__(self, category: ProviderErrorCategory):
        self.category = category
        super().__init__(category.value)


class ProviderNoChanges(Exception):
    """A complete provider snapshot matched the committed dataset exactly."""

    def __init__(self, next_cursor: str):
        self.next_cursor = next_cursor
        super().__init__("provider_no_changes")


Scalar = str | int | float | bool | None


@dataclass(frozen=True)
class ProviderRecord:
    stable_id: str | None
    values: Mapping[str, Scalar]
    operation: str = "upsert"
    source_order: int | None = None
    event_id: str | None = None


@dataclass(frozen=True)
class ProviderPage:
    records: Sequence[ProviderRecord]
    continuation: str | None = None


@dataclass(frozen=True)
class ProviderFetchRequest:
    resource_type: str
    continuation: str | None
    remaining_records: int
    deadline: float
    cancelled: Callable[[], bool]
    sync_cursor: str | None = None


class ApiProviderAdapter(Protocol):
    provider_key: str
    supported_resources: frozenset[str]

    def fetch_page(self, request: ProviderFetchRequest) -> ProviderPage: ...


@dataclass(frozen=True)
class NormalizedProviderBatch:
    csv_bytes: bytes
    record_count: int
    page_count: int
    columns: tuple[str, ...]
    final_continuation: str | None
    changes: tuple[dict, ...]
    schema_fingerprint: str
    next_cursor: str | None


class SyntheticOrdersProvider:
    """Deterministic fixture; it performs no network or credential access."""

    provider_key = "synthetic_orders"
    supported_resources = frozenset({"orders", "customers"})

    def __init__(self, batch_number: int = 1):
        if batch_number not in {1, 2, 3}:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        self.batch_number = batch_number

    def _records(self, resource_type: str) -> tuple[ProviderRecord, ...]:
        if resource_type == "customers":
            return (
                ProviderRecord("customer-A", {"name": "Ada", "segment": "retail"}, source_order=1),
                ProviderRecord("customer-B", {"name": "Basil", "segment": "business"}, source_order=1),
            )
        batches = {
            1: (
                ProviderRecord("A", {"name": "Order A", "amount": 10}, source_order=1),
                ProviderRecord("B", {"name": "Order B", "amount": 20}, source_order=1),
                ProviderRecord("C", {"name": "Order C", "amount": 30}, source_order=1),
            ),
            2: (
                ProviderRecord("B", {"name": "Order B", "amount": 25}, source_order=2),
                ProviderRecord("D", {"name": "Order D", "amount": 40}, source_order=1),
            ),
            3: (
                ProviderRecord("D", {"name": "Order D", "amount": 40}, source_order=1),
                ProviderRecord("A", {}, operation="delete", source_order=2),
                ProviderRecord("B", {"name": "Order B", "amount": 21}, source_order=1),
            ),
        }
        return batches[self.batch_number]

    def fetch_page(self, request: ProviderFetchRequest) -> ProviderPage:
        _check_execution(request)
        if request.resource_type not in self.supported_resources:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        if request.continuation is not None:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        return ProviderPage(self._records(request.resource_type))

    def next_cursor(self, resource_type: str, current_cursor: str | None) -> str:
        return f"{resource_type}:{self.batch_number}"


def _check_execution(request: ProviderFetchRequest) -> None:
    if request.cancelled():
        raise ProviderFetchError(ProviderErrorCategory.CANCELLED)
    if time.monotonic() >= request.deadline:
        raise ProviderFetchError(ProviderErrorCategory.TIMEOUT)


def _normalize_record(record: ProviderRecord) -> tuple[dict[str, Scalar], dict]:
    if not isinstance(record.values, Mapping) or (not record.values and record.operation != "delete"):
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    if record.operation not in {"upsert", "delete"}:
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    if record.operation == "delete" and record.values:
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    if record.source_order is not None and (not isinstance(record.source_order, int) or isinstance(record.source_order, bool)):
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    normalized: dict[str, Scalar] = {}
    for raw_key, value in record.values.items():
        key = str(raw_key or "").strip()
        if not key or len(key) > 128 or key.startswith("_"):
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        if isinstance(value, float) and not math.isfinite(value):
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        if isinstance(value, str) and len(value) > MAX_API_CELL_CHARS:
            raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)
        normalized[key] = value
        if len(normalized) > MAX_API_COLUMNS:
            raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)
    if record.stable_id is None:
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    stable_id = str(record.stable_id).strip()
    if not stable_id or len(stable_id) > 255:
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    event_id = None if record.event_id is None else str(record.event_id).strip()
    if event_id is not None and (not event_id or len(event_id) > 255):
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    canonical = {
        "operation": record.operation,
        "source_record_id": stable_id,
        "payload": normalized if record.operation == "upsert" else None,
    }
    content_hash = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    csv_row = {
        "_change_operation": record.operation,
        "_source_record_id": stable_id,
        "_source_order": record.source_order,
        "_source_event_id": event_id,
        "_payload_json": (
            json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if record.operation == "upsert" else ""
        ),
        "_content_hash": content_hash,
    }
    change = {
        "source_record_id": stable_id,
        "operation": record.operation,
        "source_order": record.source_order,
        "source_event_id": event_id,
        "payload": normalized if record.operation == "upsert" else None,
        "content_hash": content_hash,
    }
    return csv_row, change


def fetch_bounded_records(
    adapter: ApiProviderAdapter,
    *,
    resource_type: str,
    cancelled: Callable[[], bool] = lambda: False,
    timeout_seconds: float = DEFAULT_API_TIMEOUT_SECONDS,
    max_pages: int = MAX_API_PAGES,
    max_records: int = MAX_API_RECORDS,
    max_payload_bytes: int = MAX_API_PAYLOAD_BYTES,
    heartbeat: Callable[[], None] | None = None,
    sync_cursor: str | None = None,
) -> NormalizedProviderBatch:
    if resource_type not in adapter.supported_resources:
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    page_limit = max(1, min(int(max_pages), MAX_API_PAGES))
    record_limit = max(1, min(int(max_records), MAX_API_RECORDS))
    byte_limit = max(1, min(int(max_payload_bytes), MAX_API_PAYLOAD_BYTES))
    deadline = time.monotonic() + max(0.001, min(float(timeout_seconds), DEFAULT_API_TIMEOUT_SECONDS))
    continuation = None
    visited: set[str] = set()
    rows: list[dict[str, Scalar]] = []
    columns: list[str] = []
    stable_ids: set[str] = set()
    changes: list[dict] = []
    normalized_bytes = 0

    for page_number in range(1, page_limit + 1):
        _check_execution(ProviderFetchRequest(resource_type, continuation, record_limit - len(rows), deadline, cancelled, sync_cursor))
        if heartbeat is not None:
            heartbeat()
        page = adapter.fetch_page(ProviderFetchRequest(
            resource_type=resource_type,
            continuation=continuation,
            remaining_records=record_limit - len(rows),
            deadline=deadline,
            cancelled=cancelled,
            sync_cursor=sync_cursor,
        ))
        if not isinstance(page, ProviderPage):
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        for item in page.records:
            if len(rows) >= record_limit:
                raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)
            row, change = _normalize_record(item)
            stable_id = row.get("_source_record_id")
            if isinstance(stable_id, str):
                if stable_id in stable_ids:
                    raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
                stable_ids.add(stable_id)
            for key in row:
                if key not in columns:
                    columns.append(key)
                    if len(columns) > MAX_API_COLUMNS:
                        raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)
            rows.append(row)
            changes.append(change)
            normalized_bytes += len(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if normalized_bytes > byte_limit:
                raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)
        continuation = page.continuation
        if continuation is None:
            break
        if not isinstance(continuation, str) or not continuation or len(continuation) > 512 or continuation in visited:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        visited.add(continuation)
    else:
        if continuation is not None:
            raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)

    if not rows and getattr(adapter, "no_changes", False):
        next_cursor_fn = getattr(adapter, "next_cursor", None)
        next_cursor = next_cursor_fn(resource_type, sync_cursor) if callable(next_cursor_fn) else None
        if not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 1024:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        raise ProviderNoChanges(next_cursor)
    if not rows:
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    upsert_payloads = [change["payload"] for change in changes if change["operation"] == "upsert"]
    payload_columns = sorted({key for payload_item in upsert_payloads for key in payload_item})
    if upsert_payloads and any(sorted(payload_item) != payload_columns for payload_item in upsert_payloads):
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    schema_shape = []
    for key in payload_columns:
        observed = {
            "boolean" if isinstance(payload_item[key], bool)
            else "number" if isinstance(payload_item[key], (int, float))
            else "null" if payload_item[key] is None
            else "string"
            for payload_item in upsert_payloads
            if payload_item[key] is not None
        }
        if len(observed) > 1:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        schema_shape.append((key, next(iter(observed), "null")))
    schema_fingerprint = hashlib.sha256(
        json.dumps(schema_shape, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    for ordinal, change in enumerate(changes, 1):
        change["ordinal"] = ordinal
        change["schema_fingerprint"] = schema_fingerprint
    columns = [
        "_change_operation", "_source_record_id", "_source_order",
        "_source_event_id", "_payload_json", "_content_hash",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = output.getvalue().encode("utf-8")
    if len(payload) > byte_limit:
        raise ProviderFetchError(ProviderErrorCategory.PAYLOAD_TOO_LARGE)
    next_cursor_fn = getattr(adapter, "next_cursor", None)
    next_cursor = next_cursor_fn(resource_type, sync_cursor) if callable(next_cursor_fn) else continuation
    if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 1024):
        raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
    return NormalizedProviderBatch(
        payload, len(rows), page_number, tuple(columns), continuation,
        tuple(changes), schema_fingerprint, next_cursor,
    )


def get_provider(
    provider_key: str,
    *,
    fixture_batch: int = 1,
    cancelled: Callable[[], bool] = lambda: False,
    heartbeat: Callable[[], None] | None = None,
    audit: Callable[[dict[str, object]], None] | None = None,
    source_scope=None,
) -> ApiProviderAdapter:
    if provider_key == SyntheticOrdersProvider.provider_key:
        return SyntheticOrdersProvider(fixture_batch)
    if provider_key == "google_sheets":
        if source_scope is None:
            raise ProviderFetchError(ProviderErrorCategory.UNAVAILABLE)
        try:
            from database import service_supabase
            from services.google_sheets_connector import build_adapter
            return build_adapter(source_scope, database=service_supabase)
        except ProviderFetchError:
            raise
        except Exception as error:
            code = getattr(error, "code", "")
            category = (
                ProviderErrorCategory.UNAUTHORIZED
                if code in {"google_sheets_authorization_invalid", "provider_credentials_revoked",
                            "provider_credentials_invalid"}
                else ProviderErrorCategory.UNAVAILABLE
            )
            raise ProviderFetchError(category) from error
    from services.http_provider_adapter import HttpApiProviderAdapter
    from services.provider_credentials import CredentialError, resolve_credential
    from services.provider_http_transport import (
        ProviderHttpSession, TransportError, validate_destination,
    )
    from services.provider_registry import get_provider_spec

    spec = get_provider_spec(provider_key)
    if spec is None or source_scope is None:
        raise ProviderFetchError(ProviderErrorCategory.UNAVAILABLE)
    try:
        credential_lease = resolve_credential(source_scope, auth=spec.auth)
        destination = validate_destination(
            spec.base_url, test_loopback=spec.test_loopback,
        )
    except CredentialError as error:
        category = (ProviderErrorCategory.UNAUTHORIZED
                    if error.code == "provider_credentials_revoked"
                    else ProviderErrorCategory.UNAVAILABLE)
        raise ProviderFetchError(category) from error
    except TransportError as error:
        category = (
            ProviderErrorCategory.DESTINATION_FORBIDDEN
            if error.code in {"destination_forbidden", "destination_invalid"}
            else ProviderErrorCategory.UNAVAILABLE
        )
        raise ProviderFetchError(category) from error
    session = ProviderHttpSession(
        provider_key=spec.key,
        destination=destination,
        credential=credential_lease.secret,
        credential_validator=credential_lease.validate,
        credential_reference=credential_lease.reference_metadata(),
        auth_scheme=spec.auth,
        min_interval=spec.min_interval_seconds,
        cancelled=cancelled,
        heartbeat=heartbeat,
        audit=audit,
        max_response_bytes=spec.max_response_bytes,
    )
    return HttpApiProviderAdapter(spec, session)
