"""Canonical validation rules for Madar-hosted site identifiers."""

from __future__ import annotations

import re
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


HOSTED_ADDRESS_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
PUBLIC_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
RESERVED_HOSTED_NAMES = frozenset(
    {
        "admin",
        "api",
        "app",
        "auth",
        "billing",
        "dashboard",
        "cdn",
        "forms",
        "health",
        "login",
        "logout",
        "mail",
        "pricing",
        "privacy-policy",
        "public",
        "signup",
        "site",
        "static",
        "terms-and-conditions",
        "www",
    }
)


def public_site_domain() -> str:
    domain = str(os.getenv("PUBLIC_SITE_DOMAIN", "madarportal.com") or "").strip().lower()
    domain = domain.strip(".")
    if not PUBLIC_DOMAIN_PATTERN.fullmatch(domain):
        raise RuntimeError("PUBLIC_SITE_DOMAIN must be a valid DNS name")
    return domain


def normalize_hostname(value: object) -> str:
    raw = str(value or "").split(",", 1)[0].strip().lower().rstrip(".")
    if not raw:
        return ""
    try:
        parsed = urlsplit(f"//{raw}")
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return ""
        parsed.port  # Validate a supplied port even though identity ignores it.
        return (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def hosted_tenant_from_hostname(value: object, *, public_domain: str | None = None) -> str:
    hostname = normalize_hostname(value)
    domain = (public_domain or public_site_domain()).strip().lower().strip(".")
    if not hostname or hostname == domain:
        return ""
    suffix = f".{domain}"
    if not hostname.endswith(suffix):
        return ""
    label = hostname[: -len(suffix)]
    return label if hosted_address_is_valid(label) else ""


def _malformed_public_hostname(value: object, domain: str) -> bool:
    raw = str(value or "").split(",", 1)[0].strip().lower()
    hostname = normalize_hostname(value)
    if not hostname:
        return bool(re.search(rf"(?:^|\.){re.escape(domain)}\.?(?::.*)?$", raw))
    if hostname == domain or not hostname.endswith(f".{domain}"):
        return False
    label = hostname[: -(len(domain) + 1)]
    return label not in RESERVED_HOSTED_NAMES and not hosted_address_is_valid(label)


def request_hosted_tenant(request: Request) -> str:
    """Return the verified tenant label carried by Host, failing closed on ambiguity."""
    domain = public_site_domain()
    host_header = request.headers.get("host") or ""
    host_tenant = hosted_tenant_from_hostname(host_header, public_domain=domain)
    if _malformed_public_hostname(host_header, domain):
        raise HTTPException(status_code=400, detail="Invalid hosted site hostname")

    forwarded = request.headers.get("x-forwarded-host") or ""
    forwarded_tenant = ""
    if forwarded:
        # The application proxy overwrites Host with the original public host.
        # Only consult X-Forwarded-Host when the immediate peer is trusted.
        from services.rate_limit_service import ip_is_trusted_proxy

        peer = getattr(request.client, "host", None) if request.client else None
        if peer and ip_is_trusted_proxy(peer):
            forwarded_tenant = hosted_tenant_from_hostname(forwarded, public_domain=domain)
            if _malformed_public_hostname(forwarded, domain):
                raise HTTPException(status_code=400, detail="Invalid forwarded hosted site hostname")

    if host_tenant and forwarded_tenant and host_tenant != forwarded_tenant:
        raise HTTPException(status_code=400, detail="Ambiguous hosted site hostname")
    return host_tenant or forwarded_tenant


def enforce_request_tenant_identity(request: Request, requested_identifier: object) -> str:
    requested = normalize_hosted_address(requested_identifier)
    if not hosted_address_is_valid(requested):
        raise HTTPException(status_code=404, detail="Published site not found")
    hosted = request_hosted_tenant(request)
    if hosted and hosted != requested:
        raise HTTPException(status_code=404, detail="Published site not found")
    return hosted or requested


def canonical_tenant_url(tenant: object, path: str = "/") -> str:
    label = validate_hosted_address(tenant, label="Tenant hostname")
    clean_path = str(path or "/")
    if not clean_path.startswith("/") or clean_path.startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid canonical path")
    return f"https://{label}.{public_site_domain()}{clean_path}"


def normalize_hosted_address(value: object) -> str:
    return str(value or "").strip().lower()


def hosted_address_is_valid(value: object) -> bool:
    normalized = normalize_hosted_address(value)
    return bool(
        normalized
        and HOSTED_ADDRESS_PATTERN.fullmatch(normalized)
        and normalized not in RESERVED_HOSTED_NAMES
    )


def validate_hosted_address(value: object, *, label: str = "Hosted address") -> str:
    normalized = normalize_hosted_address(value)
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{label} is required")
    if not HOSTED_ADDRESS_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail=f"{label} can only contain lowercase letters, numbers, and hyphens",
        )
    if normalized in RESERVED_HOSTED_NAMES:
        raise HTTPException(status_code=400, detail=f"{label} is reserved")
    return normalized
