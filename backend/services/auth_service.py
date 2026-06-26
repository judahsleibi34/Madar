import os
import logging
import base64
import hashlib
import hmac
import time
import threading

from fastapi import HTTPException, Request, Response

from database import service_supabase, supabase
from services.request_security import (
    create_csrf_token,
    delete_csrf_cookie,
    set_csrf_cookie,
)

logger = logging.getLogger(__name__)

_AUTH_REFRESH_LOCK = threading.Lock()
_AUTH_REFRESH_REPLAY = {}
_AUTH_REFRESH_REPLAY_SECONDS = 15


def _refresh_session_once(refresh_token: str):
    token_key = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

    with _AUTH_REFRESH_LOCK:
        now = time.monotonic()
        expired_keys = [
            key
            for key, cached in _AUTH_REFRESH_REPLAY.items()
            if now - cached[0] > _AUTH_REFRESH_REPLAY_SECONDS
        ]
        for key in expired_keys:
            _AUTH_REFRESH_REPLAY.pop(key, None)

        cached = _AUTH_REFRESH_REPLAY.get(token_key)
        if cached:
            return cached[1], cached[2], cached[3]

        auth_response = supabase.auth.refresh_session(refresh_token)
        auth_user = getattr(auth_response, "user", None)
        session = getattr(auth_response, "session", None)
        if not auth_user or not session:
            raise RuntimeError("Session refresh returned no active session")

        result = (auth_user, session.access_token, session.refresh_token)
        _AUTH_REFRESH_REPLAY[token_key] = (time.monotonic(), *result)
        return result

APP_ENV = (
    os.getenv("APP_ENV")
    or os.getenv("ENV")
    or os.getenv("FASTAPI_ENV")
    or "development"
).strip().lower()

IS_PRODUCTION = APP_ENV in {"prod", "production"}

SESSION_ACTIVITY_COOKIE_NAME = "madar_session_activity"
SESSION_INACTIVITY_TIMEOUT_SECONDS = int(
    os.getenv("SESSION_INACTIVITY_TIMEOUT_SECONDS", "3600")
)

COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE",
    "true" if IS_PRODUCTION else "false",
).lower() == "true"

COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()

if COOKIE_SAMESITE not in {"strict", "lax", "none"}:
    raise RuntimeError("COOKIE_SAMESITE must be strict, lax, or none")

if IS_PRODUCTION and not COOKIE_SECURE:
    raise RuntimeError("COOKIE_SECURE must be true in production")

if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("COOKIE_SECURE must be true when COOKIE_SAMESITE is none")


def normalize_user_type(value) -> str:
    return str(value or "user").strip().lower()


def _session_activity_secret() -> str:
    secret = (
        os.getenv("SESSION_ACTIVITY_SECRET")
        or os.getenv("CSRF_SECRET")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SECRET_KEY")
    )

    if secret:
        return secret

    if IS_PRODUCTION:
        raise RuntimeError("A server-side session activity secret is required")

    return "madar-development-session-activity-secret"


def _sign_session_activity(timestamp: str) -> str:
    digest = hmac.new(
        _session_activity_secret().encode("utf-8"),
        timestamp.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_session_activity_value(now: int | None = None) -> str:
    timestamp = str(int(time.time()) if now is None else int(now))
    return f"{timestamp}.{_sign_session_activity(timestamp)}"


def is_session_activity_valid(value: str | None, now: int | None = None) -> bool:
    if not value:
        # Allows existing sessions to receive the new activity cookie once after deployment.
        return True

    try:
        timestamp, supplied_signature = value.split(".", 1)
        last_activity_at = int(timestamp)
    except (TypeError, ValueError):
        return False

    if not hmac.compare_digest(
        supplied_signature,
        _sign_session_activity(timestamp),
    ):
        return False

    current_time = int(time.time()) if now is None else int(now)
    age = current_time - last_activity_at
    return 0 <= age <= SESSION_INACTIVITY_TIMEOUT_SECONDS


def set_session_activity_cookie(response: Response):
    response.set_cookie(
        key=SESSION_ACTIVITY_COOKIE_NAME,
        value=create_session_activity_value(),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def delete_session_activity_cookie(response: Response):
    response.delete_cookie(
        key=SESSION_ACTIVITY_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="madar_access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )

    response.set_cookie(
        key="madar_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )

    csrf_token = create_csrf_token(
        access_token=access_token,
        refresh_token=refresh_token,
    )
    set_csrf_cookie(response, csrf_token)
    set_session_activity_cookie(response)
    return csrf_token


def delete_auth_cookies(response: Response):
    response.delete_cookie(
        key="madar_access_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )

    response.delete_cookie(
        key="madar_refresh_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    delete_csrf_cookie(response)
    delete_session_activity_cookie(response)


def build_user_payload(user_data):
    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or "User"

    return {
        "id": user_data.get("id"),
        "auth_id": user_data.get("auth_id"),
        "tenant_id": user_data.get("tenant_id"),
        "first_name": first_name,
        "last_name": last_name,
        "name": full_name,
        "email": user_data.get("email"),
        "phone": user_data.get("phone") or "",
        "avatar": user_data.get("avatar") or user_data.get("avatar_url") or "",
        "subscription_type": user_data.get("subscription_type") or "",
        "payment_status": user_data.get("payment_status") or "",
        "user_type": normalize_user_type(user_data.get("user_type")),
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at"),
    }


def get_authenticated_user_row(
    request: Request,
    response: Response | None = None,
    *,
    allow_refresh: bool = True,
):
    access_token = request.cookies.get("madar_access_token")
    refresh_token = request.cookies.get("madar_refresh_token")

    if not access_token and not refresh_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    activity_value = request.cookies.get(SESSION_ACTIVITY_COOKIE_NAME)

    if not is_session_activity_valid(activity_value):
        if response:
            delete_auth_cookies(response)
        raise HTTPException(
            status_code=401,
            detail="Session expired due to inactivity",
        )

    auth_user = None
    next_access_token = access_token
    next_refresh_token = refresh_token

    try:
        if access_token:
            try:
                auth_response = supabase.auth.get_user(access_token)
                auth_user = getattr(auth_response, "user", None)
            except Exception as access_error:
                if not refresh_token or not allow_refresh:
                    raise
                logger.warning(
                    "auth.session.access_expired",
                    extra={"error_type": type(access_error).__name__},
                )
                auth_user, next_access_token, next_refresh_token = _refresh_session_once(
                    refresh_token
                )

        elif refresh_token and allow_refresh:
            auth_user, next_access_token, next_refresh_token = _refresh_session_once(
                refresh_token
            )

    except Exception as e:
        logger.warning(
            "auth.session.invalid",
            extra={"error_type": type(e).__name__},
        )
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if not auth_user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if response and next_access_token and next_refresh_token:
        set_auth_cookies(
            response,
            next_access_token,
            next_refresh_token,
        )

    user_response = (
        service_supabase.table("users")
        .select("*")
        .eq("auth_id", auth_user.id)
        .single()
        .execute()
    )

    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    return auth_user, user_response.data


def require_system_admin(request: Request, response: Response | None = None):
    auth_user, user_data = get_authenticated_user_row(request, response)
    user_type = normalize_user_type(user_data.get("user_type"))

    if user_type != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")

    return auth_user, user_data


def require_regular_user(request: Request, response: Response | None = None):
    auth_user, user_data = get_authenticated_user_row(request, response)
    user_type = normalize_user_type(user_data.get("user_type"))

    if user_type == "admin":
        raise HTTPException(status_code=403, detail="User access is required")

    return auth_user, user_data


def require_regular_user_id(
    user_id: int,
    request: Request,
    response: Response | None = None,
):
    auth_user, user_data = require_regular_user(request, response)

    try:
        path_user_id = int(user_id)
        authenticated_user_id = int(user_data.get("id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="User id is invalid")

    if authenticated_user_id != path_user_id:
        raise HTTPException(status_code=403, detail="User id does not match session")

    return auth_user, user_data
