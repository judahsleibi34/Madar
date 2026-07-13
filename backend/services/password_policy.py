from __future__ import annotations

from services.api_errors import api_error


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 1024


def validate_password(password: str | None, *, label: str = "Password") -> str:
    """Apply the shared server-side password policy and return the original value."""
    value = password if isinstance(password, str) else ""

    if not value.strip() or len(value) < MIN_PASSWORD_LENGTH:
        raise api_error(
            400,
            "password_policy_failed",
            f"{label} must be at least {MIN_PASSWORD_LENGTH} characters.",
            context={"minimum_length": MIN_PASSWORD_LENGTH},
        )

    if len(value) > MAX_PASSWORD_LENGTH:
        raise api_error(
            400,
            "password_policy_failed",
            f"{label} is too long.",
            context={"maximum_length": MAX_PASSWORD_LENGTH},
        )

    return value
