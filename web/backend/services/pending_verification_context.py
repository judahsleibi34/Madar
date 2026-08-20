from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Request, Response

from services.auth_service import COOKIE_SAMESITE, COOKIE_SECURE, IS_PRODUCTION


PENDING_VERIFICATION_COOKIE_NAME = "madar_pending_verification"
PENDING_VERIFICATION_TTL_SECONDS = int(
    os.getenv("PENDING_VERIFICATION_TTL_SECONDS", str(14 * 24 * 60 * 60))
)


def _secret() -> str:
    value = (
        os.getenv("PENDING_VERIFICATION_SECRET")
        or os.getenv("SESSION_ACTIVITY_SECRET")
        or os.getenv("CSRF_SECRET")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SECRET_KEY")
    )
    if value:
        return value
    if IS_PRODUCTION:
        raise RuntimeError("A pending-verification signing secret is required")
    return "madar-development-pending-verification-secret"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def create_pending_verification_value(
    *,
    auth_id: str,
    user_id: int | str,
    now: int | None = None,
) -> str:
    current = int(time.time()) if now is None else int(now)
    payload = {
        "v": 1,
        "auth_id": str(auth_id),
        "user_id": int(user_id),
        "exp": current + PENDING_VERIFICATION_TTL_SECONDS,
    }
    encoded = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64encode(
        hmac.new(_secret().encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}"


def read_pending_verification_value(value: str | None, *, now: int | None = None) -> dict | None:
    if not value:
        return None

    try:
        encoded, supplied_signature = value.split(".", 1)
        expected_signature = _b64encode(
            hmac.new(_secret().encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
        current = int(time.time()) if now is None else int(now)
        if payload.get("v") != 1 or int(payload.get("exp") or 0) <= current:
            return None
        if not payload.get("auth_id") or not payload.get("user_id"):
            return None
        return payload
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def read_pending_verification_context(request: Request) -> dict | None:
    return read_pending_verification_value(
        request.cookies.get(PENDING_VERIFICATION_COOKIE_NAME)
    )


def set_pending_verification_cookie(
    response: Response,
    *,
    auth_id: str,
    user_id: int | str,
):
    response.set_cookie(
        key=PENDING_VERIFICATION_COOKIE_NAME,
        value=create_pending_verification_value(auth_id=auth_id, user_id=user_id),
        max_age=PENDING_VERIFICATION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def delete_pending_verification_cookie(response: Response):
    response.delete_cookie(
        key=PENDING_VERIFICATION_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
