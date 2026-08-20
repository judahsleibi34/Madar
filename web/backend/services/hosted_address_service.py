"""Canonical validation rules for Madar-hosted site identifiers."""

from __future__ import annotations

import re

from fastapi import HTTPException


HOSTED_ADDRESS_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
RESERVED_HOSTED_NAMES = frozenset(
    {
        "admin",
        "api",
        "auth",
        "billing",
        "dashboard",
        "forms",
        "health",
        "login",
        "logout",
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
