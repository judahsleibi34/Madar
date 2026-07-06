from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, Response

from database import service_supabase
from services.audit_service import hash_audit_identifier, record_security_event
from services.auth_service import COOKIE_SAMESITE, COOKIE_SECURE, build_user_payload, normalize_user_type
from services.email_service import send_permission_code_email
from services.rate_limit_service import enforce_rate_limit

logger = logging.getLogger(__name__)

ADMIN_ACCOUNT_ACCESS_COOKIE_NAME = "madar_admin_access_session"
ACCOUNT_ACCESS_SETUP_DETAIL = (
    "Account access is temporarily unavailable. Please try again later."
)
CODE_TTL_MINUTES = int(os.getenv("ADMIN_ACCOUNT_ACCESS_CODE_TTL_MINUTES", "10"))
SESSION_TTL_MINUTES = int(os.getenv("ADMIN_ACCOUNT_ACCESS_SESSION_TTL_MINUTES", "30"))
MAX_CODE_ATTEMPTS = int(os.getenv("ADMIN_ACCOUNT_ACCESS_MAX_CODE_ATTEMPTS", "5"))
ACCESS_CODE_LENGTH = 6
ACCESS_CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ACCESS_CODE_NUMBERS = "23456789"
ACCESS_CODE_SYMBOLS = "!@#$%&*?"
ACCESS_CODE_ALPHABET = ACCESS_CODE_LETTERS + ACCESS_CODE_NUMBERS + ACCESS_CODE_SYMBOLS


def _is_account_access_schema_error(error: Exception) -> bool:
    raw = str(error).lower()

    return (
        "pgrst205" in raw
        or "schema cache" in raw
        or "admin_account_access_requests" in raw
        or "admin_account_access_sessions" in raw
    ) and (
        "could not find the table" in raw
        or "schema cache" in raw
        or "not found" in raw
    )


def _execute_account_access_query(query):
    try:
        return query.execute()
    except Exception as error:
        if _is_account_access_schema_error(error):
            logger.error(
                "admin.account_access.schema_missing",
                extra={
                    "error_type": type(error).__name__,
                    "setup_hint": "Run migration 033_create_admin_account_access.sql and reload the Supabase schema.",
                },
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "admin_account_access_not_ready",
                    "message": ACCOUNT_ACCESS_SETUP_DETAIL,
                },
            ) from error

        raise


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _secret() -> str:
    secret = (
        os.getenv("ADMIN_ACCOUNT_ACCESS_SECRET")
        or os.getenv("SESSION_ACTIVITY_SECRET")
        or os.getenv("CSRF_SECRET")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SECRET_KEY")
    )

    if secret:
        return secret

    if os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}:
        raise RuntimeError("ADMIN_ACCOUNT_ACCESS_SECRET is required in production")

    return "madar-development-admin-account-access-secret"


def _hash_code(code: str, request_id: str) -> str:
    material = f"{request_id}:{code}".encode("utf-8")
    return hmac.new(_secret().encode("utf-8"), material, hashlib.sha256).hexdigest()


def _generate_permission_code() -> str:
    code_chars = [
        secrets.choice(ACCESS_CODE_LETTERS),
        secrets.choice(ACCESS_CODE_NUMBERS),
        secrets.choice(ACCESS_CODE_SYMBOLS),
    ]
    code_chars.extend(
        secrets.choice(ACCESS_CODE_ALPHABET)
        for _ in range(ACCESS_CODE_LENGTH - len(code_chars))
    )

    secure_random = secrets.SystemRandom()
    secure_random.shuffle(code_chars)
    return "".join(code_chars)


def _is_valid_permission_code(code: str) -> bool:
    return (
        len(code) == ACCESS_CODE_LENGTH
        and all(character in ACCESS_CODE_ALPHABET for character in code)
    )


def _hash_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    user_agent = request.headers.get("user-agent", "")
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


def _b64encode_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode_json(value: str) -> dict[str, Any]:
    padded = value + ("=" * (-len(value) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid token payload")
    return data


def _sign_payload(payload: str) -> str:
    digest = hmac.new(_secret().encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_session_token(payload: dict[str, Any]) -> str:
    encoded_payload = _b64encode_json(payload)
    return f"{encoded_payload}.{_sign_payload(encoded_payload)}"


def _read_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None

    encoded_payload, supplied_signature = token.split(".", 1)
    expected_signature = _sign_payload(encoded_payload)

    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None

    try:
        payload = _b64decode_json(encoded_payload)
    except Exception:
        return None

    expires_at = int(payload.get("exp") or 0)
    if expires_at < int(time.time()):
        return None

    return payload


def set_admin_account_access_cookie(
    response: Response,
    *,
    session_id: str,
    admin_user_id: int,
    target_user_id: int,
    expires_at: datetime,
) -> str:
    token = _create_session_token(
        {
            "sid": str(session_id),
            "aid": int(admin_user_id),
            "tid": int(target_user_id),
            "exp": int(expires_at.timestamp()),
            "jti": secrets.token_urlsafe(32),
        }
    )
    response.set_cookie(
        key=ADMIN_ACCOUNT_ACCESS_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=max(1, int((expires_at - _utc_now()).total_seconds())),
    )
    return token


def delete_admin_account_access_cookie(response: Response):
    response.delete_cookie(
        key=ADMIN_ACCOUNT_ACCESS_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def normalize_email(email: str | None) -> str:
    return str(email or "").strip().lower()


def get_user_by_email(email: str) -> dict[str, Any] | None:
    result = (
        service_supabase.table("users")
        .select("*")
        .eq("email", normalize_email(email))
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_user_by_id(user_id: int | str) -> dict[str, Any] | None:
    result = (
        service_supabase.table("users")
        .select("*")
        .eq("id", int(user_id))
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _code_rate_limit(request: Request, admin_user_id: int | str, target_email: str, scope: str):
    return enforce_rate_limit(
        request,
        f"admin_account_access:{scope}",
        identifier=f"admin:{admin_user_id}:target:{hash_audit_identifier(target_email)}",
        limit=8,
        window_seconds=300,
    )


def generate_permission_code(
    *,
    request: Request,
    admin_user: dict[str, Any],
    target_email: str,
) -> dict[str, Any]:
    clean_email = normalize_email(target_email)

    if not clean_email:
        raise HTTPException(status_code=400, detail="Email is required")

    _code_rate_limit(request, admin_user.get("id"), clean_email, "generate")

    target_user = get_user_by_email(clean_email)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if int(target_user.get("id")) == int(admin_user.get("id")):
        raise HTTPException(status_code=400, detail="You cannot access your own account this way")

    if normalize_user_type(target_user.get("user_type")) == "admin":
        raise HTTPException(status_code=403, detail="Admin accounts cannot be accessed with permission codes")

    expires_at = _utc_now() + timedelta(minutes=CODE_TTL_MINUTES)
    insert_result = _execute_account_access_query(
        service_supabase.table("admin_account_access_requests")
        .insert(
            {
                "admin_user_id": admin_user.get("id"),
                "target_user_id": target_user.get("id"),
                "target_email": clean_email,
                "expires_at": _iso(expires_at),
                "user_agent_hash": _hash_user_agent(request),
            }
        )
    )

    if not insert_result.data:
        raise HTTPException(status_code=500, detail="Could not create access request")

    access_request = insert_result.data[0]
    code = _generate_permission_code()
    request_id = str(access_request["id"])

    _execute_account_access_query(
        service_supabase.table("admin_account_access_requests").update(
            {"code_hash": _hash_code(code, request_id)}
        ).eq("id", request_id)
    )

    try:
        delivery = send_permission_code_email(
            recipient_email=clean_email,
            code=code,
            expires_minutes=CODE_TTL_MINUTES,
        )
    except Exception as error:
        logger.warning(
            "admin.account_access.email_failed",
            extra={"target_user_id": target_user.get("id"), "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=503, detail="Could not send permission code") from error

    record_security_event(
        request=request,
        tenant_id=target_user.get("tenant_id"),
        actor_user_id=admin_user.get("id"),
        action="admin.account_access_code_requested",
        target_type="user",
        target_id=target_user.get("id"),
        metadata={
            "target_user_id": target_user.get("id"),
            "target_email_hash": hash_audit_identifier(clean_email),
            "expires_at": _iso(expires_at),
            "delivery": delivery,
        },
    )

    return {
        "success": True,
        "request_id": request_id,
        "target_user": {
            "id": target_user.get("id"),
            "email": target_user.get("email"),
            "name": build_user_payload(target_user).get("name"),
        },
        "expires_at": _iso(expires_at),
        "delivery": delivery,
    }


def _candidate_requests(admin_user_id: int, target_user_id: int) -> list[dict[str, Any]]:
    result = _execute_account_access_query(
        service_supabase.table("admin_account_access_requests")
        .select("*")
        .eq("admin_user_id", admin_user_id)
        .eq("target_user_id", target_user_id)
        .order("created_at", desc=True)
        .limit(10)
    )
    return result.data or []


def verify_permission_code(
    *,
    request: Request,
    response: Response,
    admin_user: dict[str, Any],
    target_email: str,
    code: str,
) -> dict[str, Any]:
    clean_email = normalize_email(target_email)
    clean_code = str(code or "").strip()

    if not _is_valid_permission_code(clean_code):
        raise HTTPException(
            status_code=400,
            detail="Permission code must be 6 characters using letters, numbers, or symbols",
        )

    _code_rate_limit(request, admin_user.get("id"), clean_email, "verify")

    target_user = get_user_by_email(clean_email)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if normalize_user_type(target_user.get("user_type")) == "admin":
        raise HTTPException(status_code=403, detail="Admin accounts cannot be accessed with permission codes")

    now = _utc_now()
    selected_request = None

    for access_request in _candidate_requests(int(admin_user.get("id")), int(target_user.get("id"))):
        if access_request.get("used_at") or access_request.get("revoked_at"):
            continue

        expires_at = _parse_datetime(access_request.get("expires_at"))
        if not expires_at or expires_at <= now:
            continue

        if int(access_request.get("attempts") or 0) >= MAX_CODE_ATTEMPTS:
            continue

        selected_request = access_request
        break

    if not selected_request:
        raise HTTPException(status_code=400, detail="No active permission code found")

    request_id = str(selected_request.get("id"))
    attempts = int(selected_request.get("attempts") or 0) + 1
    code_matches = hmac.compare_digest(
        str(selected_request.get("code_hash") or ""),
        _hash_code(clean_code, request_id),
    )

    update_payload: dict[str, Any] = {"attempts": attempts}

    if not code_matches:
        if attempts >= MAX_CODE_ATTEMPTS:
            update_payload["revoked_at"] = _iso(now)
            update_payload["revoked_reason"] = "too_many_attempts"

        _execute_account_access_query(
            service_supabase.table("admin_account_access_requests").update(update_payload).eq(
                "id", request_id
            )
        )

        record_security_event(
            request=request,
            tenant_id=target_user.get("tenant_id"),
            actor_user_id=admin_user.get("id"),
            action="admin.account_access_code_failed",
            target_type="user",
            target_id=target_user.get("id"),
            metadata={
                "target_user_id": target_user.get("id"),
                "attempts": attempts,
            },
        )
        raise HTTPException(status_code=401, detail="Invalid or expired permission code")

    _execute_account_access_query(
        service_supabase.table("admin_account_access_requests").update(
            {
                "attempts": attempts,
                "used_at": _iso(now),
            }
        ).eq("id", request_id)
    )

    expires_at = now + timedelta(minutes=SESSION_TTL_MINUTES)
    session_result = _execute_account_access_query(
        service_supabase.table("admin_account_access_sessions")
        .insert(
            {
                "access_request_id": request_id,
                "admin_user_id": admin_user.get("id"),
                "target_user_id": target_user.get("id"),
                "expires_at": _iso(expires_at),
                "user_agent_hash": _hash_user_agent(request),
            }
        )
    )

    if not session_result.data:
        raise HTTPException(status_code=500, detail="Could not create access session")

    session = session_result.data[0]
    session_token = set_admin_account_access_cookie(
        response,
        session_id=str(session["id"]),
        admin_user_id=int(admin_user.get("id")),
        target_user_id=int(target_user.get("id")),
        expires_at=expires_at,
    )
    _execute_account_access_query(
        service_supabase.table("admin_account_access_sessions").update(
            {"session_token_hash": _hash_session_token(session_token)}
        ).eq("id", str(session["id"]))
    )

    record_security_event(
        request=request,
        tenant_id=target_user.get("tenant_id"),
        actor_user_id=admin_user.get("id"),
        action="admin.account_access_started",
        target_type="user",
        target_id=target_user.get("id"),
        metadata={
            "target_user_id": target_user.get("id"),
            "target_email_hash": hash_audit_identifier(clean_email),
            "expires_at": _iso(expires_at),
        },
    )

    return {
        "success": True,
        "user": build_user_payload(target_user),
        "expires_at": _iso(expires_at),
        "redirect_to": "/dashboard",
    }


def resolve_admin_account_access_user(
    *,
    request: Request,
    response: Response | None,
    admin_user: dict[str, Any],
) -> dict[str, Any] | None:
    token = request.cookies.get(ADMIN_ACCOUNT_ACCESS_COOKIE_NAME)
    payload = _read_session_token(token)

    if not payload:
        if token and response is not None:
            delete_admin_account_access_cookie(response)
        return None

    if int(payload.get("aid") or 0) != int(admin_user.get("id") or 0):
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    session_id = str(payload.get("sid") or "")
    target_user_id = int(payload.get("tid") or 0)

    if not session_id or not target_user_id:
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    session_result = _execute_account_access_query(
        service_supabase.table("admin_account_access_sessions")
        .select("*")
        .eq("id", session_id)
        .limit(1)
    )

    if not session_result.data:
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    session = session_result.data[0]
    session_token_hash = session.get("session_token_hash")
    expires_at = _parse_datetime(session.get("expires_at"))

    if (
        session.get("ended_at")
        or int(session.get("admin_user_id") or 0) != int(admin_user.get("id") or 0)
        or int(session.get("target_user_id") or 0) != target_user_id
        or not expires_at
        or expires_at <= _utc_now()
    ):
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    if session_token_hash and not hmac.compare_digest(
        str(session_token_hash),
        _hash_session_token(token),
    ):
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    expected_user_agent_hash = session.get("user_agent_hash")
    current_user_agent_hash = _hash_user_agent(request)

    if expected_user_agent_hash and current_user_agent_hash and expected_user_agent_hash != current_user_agent_hash:
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    target_user = get_user_by_id(target_user_id)

    if not target_user or normalize_user_type(target_user.get("user_type")) == "admin":
        if response is not None:
            delete_admin_account_access_cookie(response)
        return None

    return target_user


def end_admin_account_access_session(
    *,
    request: Request,
    response: Response,
    admin_user: dict[str, Any],
) -> dict[str, Any]:
    token = request.cookies.get(ADMIN_ACCOUNT_ACCESS_COOKIE_NAME)
    payload = _read_session_token(token)

    if payload and int(payload.get("aid") or 0) == int(admin_user.get("id") or 0):
        session_id = str(payload.get("sid") or "")

        if session_id:
            _execute_account_access_query(
                service_supabase.table("admin_account_access_sessions").update(
                    {
                        "ended_at": _iso(_utc_now()),
                        "ended_reason": "admin_exit",
                    }
                ).eq("id", session_id)
            )

            record_security_event(
                request=request,
                tenant_id=admin_user.get("tenant_id"),
                actor_user_id=admin_user.get("id"),
                action="admin.account_access_ended",
                target_type="admin_account_access_session",
                target_id=session_id,
                metadata={"reason": "admin_exit"},
            )

    delete_admin_account_access_cookie(response)
    return {"success": True}
