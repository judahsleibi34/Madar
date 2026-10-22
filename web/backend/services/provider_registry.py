"""Operator-controlled allowlist of API providers (C2).

A provider definition is code, reviewed like any other change: its base URL,
resources, request parameters and record mapping are fixed here. Users choose only a
registered ``provider_key`` and ``resource_type``; they can never supply a URL,
header, path or query parameter.

No production provider is registered yet. A deterministic HTTP fixture is
registered only when ``APP_ENV`` is exactly ``test`` and
``MADAR_TEST_HTTP_PROVIDER_URL`` points at a loopback address.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
TEST_FIXTURE_PROVIDER = "http_fixture"
TEST_FIXTURE_URL_ENV = "MADAR_TEST_HTTP_PROVIDER_URL"


@dataclass(frozen=True)
class ResourceSpec:
    """How one resource is requested and mapped to provider-independent records."""

    key: str
    path: str
    records_field: str
    id_field: str
    data_field: str
    order_field: str | None = None
    deleted_field: str | None = None
    event_field: str | None = None
    page_param: str = "page_token"
    next_page_field: str = "next_page_token"
    cursor_param: str = "since"
    next_cursor_field: str = "sync_cursor"
    limit_param: str | None = "limit"
    page_size: int = 100

    def __post_init__(self):
        if not KEY_PATTERN.fullmatch(self.key) or not self.path.startswith("/"):
            raise ValueError("invalid resource spec")
        for name in (self.records_field, self.id_field, self.data_field, self.order_field,
                     self.deleted_field, self.event_field, self.page_param,
                     self.next_page_field, self.cursor_param, self.next_cursor_field,
                     self.limit_param):
            if name is not None and not FIELD_PATTERN.fullmatch(name):
                raise ValueError("invalid resource spec")
        if not 1 <= self.page_size <= 1000:
            raise ValueError("invalid resource spec")


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    base_url: str
    resources: Mapping[str, ResourceSpec]
    auth: str = "bearer"
    min_interval_seconds: float = 0.2
    max_response_bytes: int = 1024 * 1024
    test_loopback: bool = False
    description: str = ""
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not KEY_PATTERN.fullmatch(self.key) or self.auth not in {"bearer", "none"}:
            raise ValueError("invalid provider spec")
        if not self.resources or any(key != spec.key for key, spec in self.resources.items()):
            raise ValueError("invalid provider spec")
        parsed = urlsplit(self.base_url)
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("invalid provider spec")
        if parsed.scheme != "https" and not (self.test_loopback and parsed.scheme == "http"):
            raise ValueError("invalid provider spec")


# Reviewed production providers. Intentionally empty in C2 (fixture only).
PRODUCTION_PROVIDERS: Mapping[str, ProviderSpec] = MappingProxyType({})


def _test_fixture_spec() -> ProviderSpec | None:
    if os.environ.get("APP_ENV") != "test":
        return None
    url = os.environ.get(TEST_FIXTURE_URL_ENV, "").strip()
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        return None
    return ProviderSpec(
        key=TEST_FIXTURE_PROVIDER,
        base_url=url.rstrip("/"),
        resources={"records": ResourceSpec(
            key="records", path="/v1/records", records_field="records", id_field="id",
            data_field="data", order_field="version", deleted_field="deleted",
            event_field="event_id", page_size=2,
        )},
        auth="bearer",
        min_interval_seconds=0.0,
        test_loopback=True,
        description="Deterministic local HTTP business-data fixture (test only).",
    )


def get_provider_spec(provider_key: str) -> ProviderSpec | None:
    if provider_key in PRODUCTION_PROVIDERS:
        return PRODUCTION_PROVIDERS[provider_key]
    fixture = _test_fixture_spec()
    if fixture is not None and fixture.key == provider_key:
        return fixture
    return None


def resource_supported(provider_key: str, resource_type: str) -> bool:
    spec = get_provider_spec(provider_key)
    return spec is not None and resource_type in spec.resources


def public_provider_capabilities() -> list[dict[str, object]]:
    """Return the browser-safe, operator-controlled provider catalogue.

    Network destinations, request paths, field mappings, headers and credentials
    deliberately remain server-only. The test fixture is visible only under the
    same exact test-only conditions that make it executable.
    """
    providers = list(PRODUCTION_PROVIDERS.values())
    fixture = _test_fixture_spec()
    if fixture is not None:
        providers.append(fixture)
    return [
        {
            "key": spec.key,
            "label": str(spec.labels.get("name") or spec.key.replace("_", " ").title()),
            "description": spec.description,
            "credential_type": spec.auth,
            "resources": [
                {
                    "key": resource.key,
                    "label": str(spec.labels.get(resource.key) or resource.key.replace("_", " ").title()),
                }
                for resource in spec.resources.values()
            ],
        }
        for spec in providers
    ]
