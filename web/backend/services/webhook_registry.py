"""Operator-controlled, provider-neutral inbound webhook adapter registry.

Adapters are reviewed code.  No request can supply an implementation, verification
algorithm, callback, provider identity, or resource mapping.  C4 ships only a
deterministic HMAC fixture which is available in exact test environments.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol


MAX_WEBHOOK_BODY_BYTES = 64 * 1024
MAX_WEBHOOK_HEADER_BYTES = 16 * 1024
MAX_WEBHOOK_AGE_SECONDS = 300
TEST_WEBHOOK_PROVIDER = "webhook_fixture"
TEST_WEBHOOK_RESOURCE = "records"
SIGNATURE_HEADER = "x-madar-signature"
TIMESTAMP_HEADER = "x-madar-timestamp"
EVENT_ID_HEADER = "x-madar-event-id"
_EVENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,254}$")
_RECORD_ID = re.compile(r"^[^\x00-\x1f\x7f]{1,255}$")


class WebhookAdapterError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True)
class WebhookAdapterSpec:
    key: str
    resource_types: frozenset[str]
    event_types: frozenset[str]
    verification_strategy: str
    timestamp_required: bool
    provider_event_id_required: bool
    ordering: str
    authoritative_events: frozenset[str]
    notification_events: frozenset[str]
    deletion_events: frozenset[str]
    credential_type: str = "webhook_hmac"
    description: str = ""


@dataclass(frozen=True)
class NormalizedWebhookEvent:
    provider_event_id: str
    event_type: str
    resource_type: str
    occurred_at_epoch: int
    delivery_kind: str
    normalized_payload: Mapping[str, object]
    record_id: str | None = None
    operation: str | None = None
    source_order: int | None = None


class WebhookAdapter(Protocol):
    spec: WebhookAdapterSpec

    def verify_and_normalize(
        self, *, raw_body: bytes, headers: Mapping[str, str], secret: str,
        received_at_epoch: int | None = None,
    ) -> NormalizedWebhookEvent: ...


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
        value[key] = item
    return value


def _bounded_json(value, *, depth: int = 0) -> None:
    if depth > 8:
        raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
    if isinstance(value, dict):
        if len(value) > 128:
            raise WebhookAdapterError("webhook_payload_too_large", status_code=413)
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128 or key.startswith("_"):
                raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
            _bounded_json(item, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > 256:
            raise WebhookAdapterError("webhook_payload_too_large", status_code=413)
        for item in value:
            _bounded_json(item, depth=depth + 1)
        return
    if isinstance(value, str) and len(value) > 32_768:
        raise WebhookAdapterError("webhook_payload_too_large", status_code=413)
    if isinstance(value, float) and not math.isfinite(value):
        raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise WebhookAdapterError("webhook_payload_invalid", status_code=422)


class SyntheticHmacWebhookAdapter:
    """Exact test adapter for authoritative upserts and change notifications."""

    spec = WebhookAdapterSpec(
        key=TEST_WEBHOOK_PROVIDER,
        resource_types=frozenset({TEST_WEBHOOK_RESOURCE}),
        event_types=frozenset({"record.upsert", "resource.changed"}),
        verification_strategy="hmac_sha256_timestamped_v1",
        timestamp_required=True,
        provider_event_id_required=True,
        ordering="per_record_monotonic_integer",
        authoritative_events=frozenset({"record.upsert"}),
        notification_events=frozenset({"resource.changed"}),
        deletion_events=frozenset(),
        description="Deterministic signed webhook fixture (test only).",
    )

    def verify_and_normalize(
        self, *, raw_body: bytes, headers: Mapping[str, str], secret: str,
        received_at_epoch: int | None = None,
    ) -> NormalizedWebhookEvent:
        if not isinstance(raw_body, bytes) or not raw_body or len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            raise WebhookAdapterError("webhook_payload_too_large", status_code=413)
        lowered = {str(key).lower(): str(value) for key, value in headers.items()}
        supplied = lowered.get(SIGNATURE_HEADER, "")
        timestamp_value = lowered.get(TIMESTAMP_HEADER, "")
        event_id = lowered.get(EVENT_ID_HEADER, "")
        if not re.fullmatch(r"v1=[0-9a-f]{64}", supplied):
            raise WebhookAdapterError("webhook_signature_invalid", status_code=401)
        if not timestamp_value.isdigit() or len(timestamp_value) > 12:
            raise WebhookAdapterError("webhook_timestamp_invalid", status_code=401)
        timestamp = int(timestamp_value)
        now = int(time.time()) if received_at_epoch is None else int(received_at_epoch)
        if abs(now - timestamp) > MAX_WEBHOOK_AGE_SECONDS:
            raise WebhookAdapterError("webhook_timestamp_expired", status_code=401)
        if not _EVENT_ID.fullmatch(event_id):
            raise WebhookAdapterError("webhook_event_id_invalid", status_code=422)
        expected = hmac.new(
            secret.encode("utf-8"), timestamp_value.encode("ascii") + b"." + raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(supplied[3:], expected):
            raise WebhookAdapterError("webhook_signature_invalid", status_code=401)
        try:
            payload = json.loads(raw_body.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except WebhookAdapterError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WebhookAdapterError("webhook_payload_invalid", status_code=422) from error
        if not isinstance(payload, dict):
            raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
        _bounded_json(payload)
        event_type = payload.get("event_type")
        resource = payload.get("resource")
        if event_type == "record.deleted":
            raise WebhookAdapterError("webhook_deletion_unsupported", status_code=422)
        if event_type not in self.spec.event_types:
            raise WebhookAdapterError("webhook_event_type_unsupported", status_code=422)
        if resource not in self.spec.resource_types:
            raise WebhookAdapterError("webhook_resource_unsupported", status_code=422)
        if event_type == "resource.changed":
            if set(payload) - {"event_type", "resource", "notification"}:
                raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
            notification = payload.get("notification", {})
            if not isinstance(notification, dict):
                raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
            return NormalizedWebhookEvent(
                event_id, event_type, resource, timestamp, "change_notification",
                MappingProxyType({"notification": dict(notification)}),
            )
        if set(payload) != {"event_type", "resource", "record"}:
            raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
        record = payload.get("record")
        if not isinstance(record, dict) or set(record) != {"id", "version", "data"}:
            raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
        record_id = record.get("id")
        version = record.get("version")
        data = record.get("data")
        if not isinstance(record_id, str) or not _RECORD_ID.fullmatch(record_id):
            raise WebhookAdapterError("webhook_record_identity_invalid", status_code=422)
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise WebhookAdapterError("webhook_order_invalid", status_code=422)
        if not isinstance(data, dict) or not data:
            raise WebhookAdapterError("webhook_payload_invalid", status_code=422)
        _bounded_json(data)
        return NormalizedWebhookEvent(
            event_id, event_type, resource, timestamp, "authoritative_record",
            MappingProxyType({"record": {"id": record_id, "version": version, "data": dict(data)}}),
            record_id=record_id, operation="upsert", source_order=version,
        )


PRODUCTION_WEBHOOK_ADAPTERS: Mapping[str, WebhookAdapter] = MappingProxyType({})


def _fixture_adapter() -> WebhookAdapter | None:
    if os.getenv("APP_ENV", "").strip().lower() != "test":
        return None
    if os.getenv("MADAR_TEST_WEBHOOK_ADAPTER_ENABLED", "").strip().lower() != "true":
        return None
    return SyntheticHmacWebhookAdapter()


def get_webhook_adapter(provider_key: str) -> WebhookAdapter | None:
    adapter = PRODUCTION_WEBHOOK_ADAPTERS.get(str(provider_key))
    if adapter is not None:
        return adapter
    fixture = _fixture_adapter()
    return fixture if fixture is not None and fixture.spec.key == provider_key else None


def webhook_capability(provider_key: str, resource_type: str) -> dict[str, object] | None:
    adapter = get_webhook_adapter(provider_key)
    if adapter is None or resource_type not in adapter.spec.resource_types:
        return None
    spec = adapter.spec
    return {
        "supported": True,
        "credential_type": spec.credential_type,
        "verification_strategy": spec.verification_strategy,
        "timestamp_required": spec.timestamp_required,
        "event_types": sorted(spec.event_types),
        "authoritative_event_types": sorted(spec.authoritative_events),
        "notification_event_types": sorted(spec.notification_events),
        "deletion_supported": bool(spec.deletion_events),
        "ordering": spec.ordering,
    }


def public_webhook_providers() -> list[dict[str, object]]:
    adapters = list(PRODUCTION_WEBHOOK_ADAPTERS.values())
    fixture = _fixture_adapter()
    if fixture is not None:
        adapters.append(fixture)
    return [{
        "key": adapter.spec.key,
        "label": "Signed webhook fixture" if adapter.spec.key == TEST_WEBHOOK_PROVIDER else adapter.spec.key,
        "description": adapter.spec.description,
        "credential_type": adapter.spec.credential_type,
        "webhook": webhook_capability(adapter.spec.key, next(iter(adapter.spec.resource_types))),
        "resources": [{"key": key, "label": key.replace("_", " ").title()}
                      for key in sorted(adapter.spec.resource_types)],
    } for adapter in adapters]
