from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def error_detail(
    code: str,
    message: str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "code": str(code).strip(),
        "message": str(message).strip(),
    }

    if context:
        detail["context"] = context

    return detail


def api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    context: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """Build a safe, machine-readable API error without provider details."""
    return HTTPException(
        status_code=status_code,
        detail=error_detail(code, message, context=context),
        headers=headers,
    )
