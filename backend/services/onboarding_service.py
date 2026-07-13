from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from services.api_errors import api_error

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
RESERVED_SUBDOMAINS = {
    "admin",
    "api",
    "app",
    "auth",
    "billing",
    "cdn",
    "dashboard",
    "docs",
    "help",
    "login",
    "mail",
    "public",
    "root",
    "settings",
    "signup",
    "support",
    "www",
}
NAME_PUNCTUATION = {" ", "-", "'", "’", "."}
BUSINESS_TEXT_PUNCTUATION = NAME_PUNCTUATION | {"&", "/", ",", "(", ")"}


def normalize_subdomain(subdomain: str | None) -> str:
    return str(subdomain or "").strip().lower()


def validate_text_value(
    value: str | None,
    *,
    field_label: str,
    allowed_punctuation: set[str],
    required: bool = True,
) -> str:
    clean_value = str(value or "").strip()

    if not clean_value:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_label} is required")
        return ""

    if any(character.isdigit() for character in clean_value):
        raise HTTPException(status_code=400, detail=f"{field_label} can only contain letters")

    if not any(character.isalpha() for character in clean_value):
        raise HTTPException(status_code=400, detail=f"{field_label} must include letters")

    if any(
        not character.isalpha()
        and not character.isspace()
        and character not in allowed_punctuation
        for character in clean_value
    ):
        raise HTTPException(status_code=400, detail=f"{field_label} contains invalid characters")

    return clean_value


def validate_person_name(value: str | None, field_label: str) -> str:
    return validate_text_value(
        value,
        field_label=field_label,
        allowed_punctuation=NAME_PUNCTUATION,
    )


def validate_optional_business_text(value: str | None, field_label: str) -> str:
    return validate_text_value(
        value,
        field_label=field_label,
        allowed_punctuation=BUSINESS_TEXT_PUNCTUATION,
        required=False,
    )


def validate_onboarding_subdomain(subdomain: str | None) -> str:
    normalized = normalize_subdomain(subdomain)

    if len(normalized) < 3:
        raise HTTPException(status_code=400, detail="Subdomain must be at least 3 characters.")

    if normalized in RESERVED_SUBDOMAINS:
        raise HTTPException(status_code=400, detail="This subdomain is reserved.")

    if not SUBDOMAIN_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Invalid subdomain.")

    return normalized


def ensure_subdomain_available(supabase_client: Any, subdomain: str) -> None:
    result = (
        supabase_client.table("website_settings")
        .select("id")
        .eq("subdomain", subdomain)
        .limit(1)
        .execute()
    )

    if result.data:
        raise HTTPException(status_code=409, detail="Subdomain is already taken.")


def create_onboarded_tenant(*, supabase_client: Any, payload: Any) -> dict[str, Any]:
    # Historical callers provisioned a confirmed identity and tenant in one step.
    # Keep the symbol for compatibility, but make the unsafe path impossible to
    # invoke while signup uses the pending-verification lifecycle.
    raise api_error(
        409,
        "pending_verification_flow_required",
        "Create the pending account through /auth/signup and verify its email first.",
    )
