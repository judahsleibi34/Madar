from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from functools import lru_cache
from typing import Any

import redis

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, Response
from database import SUPABASE_ANON_KEY, create_supabase_client
from services.auth_service import COOKIE_SAMESITE, COOKIE_SECURE
from services.request_security import get_csrf_secret

ADMIN_MFA_LOGIN_ENFORCEMENT_ENV = "ADMIN_MFA_LOGIN_ENFORCEMENT"
PENDING_MFA_COOKIE_NAME = "madar_mfa_pending"
# The public /api proxy strips its prefix before FastAPI. Root scope also
# allows logout to revoke the pending session. Only MFA endpoints accept it;
# ordinary authentication never reads this opaque identifier.
PENDING_MFA_COOKIE_PATH = "/"
PENDING_MFA_MAX_OPERATIONS = 20
PENDING_MFA_MAX_AGE_SECONDS = 300


@lru_cache(maxsize=1)
def pending_mfa_store():
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
    )


def _store_call(operation, *args, **kwargs):
    try:
        return getattr(pending_mfa_store(), operation)(*args, **kwargs)
    except redis.RedisError as error:
        raise HTTPException(status_code=503, detail="MFA login session storage is unavailable") from error


def _session_key(sid):
    return "madar:mfa-login:v2:" + sid


def is_admin_mfa_login_enforcement_enabled() -> bool:
    return os.getenv(ADMIN_MFA_LOGIN_ENFORCEMENT_ENV, "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _pending_cookie_fernet() -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(get_csrf_secret().encode("utf-8")).digest()
    )
    return Fernet(key)


def read_value(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return None


def response_data(response: Any) -> Any:
    return read_value(response, "data") or response


def encode_pending_mfa_payload(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _pending_cookie_fernet().encrypt(payload_json).decode("ascii")


def decode_pending_mfa_payload(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None

    try:
        payload_json = _pending_cookie_fernet().decrypt(
            value.encode("ascii"),
            ttl=PENDING_MFA_MAX_AGE_SECONDS,
        )
        payload = json.loads(payload_json.decode("utf-8"))
    except (InvalidToken, json.JSONDecodeError, UnicodeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError):
        return None

    if expires_at < int(time.time()):
        return None

    if (payload.get("v") != 2 or not isinstance(payload.get("sid"), str)
            or len(payload["sid"]) != 43):
        return None

    return payload


def set_pending_mfa_cookie(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    auth_id: str,
    user_id: int,
    tenant_id: int | None = None,
) -> None:
    sid = secrets.token_urlsafe(32)
    payload = {
        "v": 2,
        "sid": sid,
        "exp": int(time.time()) + PENDING_MFA_MAX_AGE_SECONDS,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "auth_id": str(auth_id),
        "user_id": user_id,
        "tenant_id": tenant_id,
    }
    # Tokens stay encrypted in the shared, short-lived server store, not in
    # the browser. GETDEL consumes this record exactly once before admission.
    _store_call("set", _session_key(sid), encode_pending_mfa_payload(payload), ex=PENDING_MFA_MAX_AGE_SECONDS)
    for legacy_path in ("/auth/mfa/login", "/api/auth/mfa/login"):
        response.delete_cookie(PENDING_MFA_COOKIE_NAME, path=legacy_path,
                               secure=COOKIE_SECURE, httponly=True, samesite=COOKIE_SAMESITE)
    response.set_cookie(
        key=PENDING_MFA_COOKIE_NAME,
        value=encode_pending_mfa_payload({"v": 2, "sid": sid, "exp": payload["exp"]}),
        max_age=PENDING_MFA_MAX_AGE_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path=PENDING_MFA_COOKIE_PATH,
    )


def clear_pending_mfa_cookie(response: Response) -> None:
    response.delete_cookie(
        key=PENDING_MFA_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path=PENDING_MFA_COOKIE_PATH,
    )


def read_pending_mfa_cookie(request: Request) -> dict[str, Any] | None:
    reference = decode_pending_mfa_payload(request.cookies.get(PENDING_MFA_COOKIE_NAME))
    if not reference:
        return None
    stored = _store_call("get", _session_key(reference["sid"]))
    payload = decode_pending_mfa_payload(stored)
    if (not payload or payload["sid"] != reference["sid"] or not payload.get("auth_id")
            or not payload.get("user_id") or not payload.get("access_token") or not payload.get("refresh_token")):
        return None
    return payload


def reserve_pending_mfa_operation(payload):
    key = _session_key(payload["sid"]) + ":operations"
    attempts = _store_call("incr", key)
    if attempts == 1:
        _store_call("expire", key, PENDING_MFA_MAX_AGE_SECONDS)
    return attempts <= PENDING_MFA_MAX_OPERATIONS


def consume_pending_mfa_payload(payload):
    stored = _store_call("getdel", _session_key(payload["sid"]))
    current = decode_pending_mfa_payload(stored)
    return bool(current and current["sid"] == payload["sid"] and current.get("auth_id") == payload.get("auth_id"))


def revoke_pending_mfa_cookie(request):
    reference = decode_pending_mfa_payload(request.cookies.get(PENDING_MFA_COOKIE_NAME))
    if reference:
        _store_call("delete", _session_key(reference["sid"]))


def create_pending_mfa_client(pending_payload: dict[str, Any]):
    client = create_supabase_client(SUPABASE_ANON_KEY)
    client.auth.set_session(pending_payload["access_token"], pending_payload["refresh_token"])
    return client


def normalize_mfa_factor(factor: Any) -> dict[str, Any]:
    normalized = {
        "id": read_value(factor, "id", "factor_id"),
        "factor_type": read_value(factor, "factor_type", "type"),
        "status": read_value(factor, "status"),
        "friendly_name": read_value(factor, "friendly_name"),
        "created_at": read_value(factor, "created_at"),
        "updated_at": read_value(factor, "updated_at"),
        "last_challenged_at": read_value(factor, "last_challenged_at"),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def factor_list_from_response(response: Any) -> list[dict[str, Any]]:
    data = response_data(response)
    raw_factors = read_value(data, "all")
    if raw_factors is None:
        raw_factors = read_value(data, "totp")
    if raw_factors is None and isinstance(data, list):
        raw_factors = data
    return [normalize_mfa_factor(factor) for factor in (raw_factors or [])]


def verified_totp_factors_for_client(supabase_client) -> list[dict[str, Any]]:
    return [
        factor
        for factor in factor_list_from_response(supabase_client.auth.mfa.list_factors())
        if factor.get("factor_type") == "totp" and factor.get("status") == "verified"
    ]


def get_session_from_verify_response(response: Any):
    data = response_data(response)
    return read_value(response, "session") or read_value(data, "session")


def aal_payload_from_response(response: Any) -> dict[str, Any]:
    data = response_data(response)
    return {
        "current_level": read_value(data, "current_level", "currentLevel", "aal"),
        "next_level": read_value(data, "next_level", "nextLevel"),
    }
