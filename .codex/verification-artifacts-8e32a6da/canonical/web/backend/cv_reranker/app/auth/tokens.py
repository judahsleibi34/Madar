from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import Settings
from app.core.errors import ApiError, unauthorized


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    expires_in: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> AccessToken:
    now = utc_now()
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return AccessToken(token=token, expires_in=int((expires_at - now).total_seconds()))


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "iat", "exp", "jti", "iss", "aud", "type"]},
        )
        if payload.get("type") != "access":
            raise unauthorized()
        return uuid.UUID(str(payload["sub"]))
    except ApiError:
        raise
    except (jwt.PyJWTError, ValueError, TypeError) as error:
        raise unauthorized() from error


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
