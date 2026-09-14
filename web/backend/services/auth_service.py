import os
import logging
import base64
import hashlib
import hmac
import time
import threading

import jwt
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Response
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthInvalidJwtError,
    AuthRetryableError,
    AuthSessionMissingError,
)

from database import service_supabase, supabase, create_session_supabase_client
from services.account_lifecycle_service import (
    ACTIVE_ACCOUNT_STATUS,
    effective_account_status,
    is_platform_account,
    synchronize_verified_account,
)
from services.identity_service import canonical_auth_email, normalize_email
from services.api_errors import api_error, error_detail
from services.request_security import (
    create_csrf_token,
    delete_csrf_cookie,
    set_csrf_cookie,
)

logger = logging.getLogger(__name__)

_AUTH_REFRESH_LOCK = threading.Lock()
_AUTH_REFRESH_REPLAY = {}
_AUTH_REFRESH_REPLAY_SECONDS = 15


class SessionRefreshUnavailable(HTTPException):
    """The identity provider could not verify the session temporarily."""

    def __init__(self, _message: str = "Authentication service is temporarily unavailable"):
        super().__init__(
            status_code=503,
            detail=error_detail(
                "auth_temporarily_unavailable",
                "Authentication is temporarily unavailable. Please try again.",
            ),
            headers={"Retry-After": "5"},
        )


def is_definitive_auth_failure(error: Exception) -> bool:
    if isinstance(error, AuthRetryableError):
        return False
    if isinstance(
        error,
        (AuthInvalidCredentialsError, AuthInvalidJwtError, AuthSessionMissingError),
    ):
        return True
    if isinstance(error, AuthApiError):
        status = int(getattr(error, "status", 0) or 0)
        return 400 <= status < 500 and status not in {408, 429}
    return False


def _get_auth_value(source, key: str):
    if source is None:
        return None

    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)


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
        auth_user = _get_auth_value(auth_response, "user")
        session = _get_auth_value(auth_response, "session")

        if not session:
            raise RuntimeError("Session refresh returned no active session")

        access_token = _get_auth_value(session, "access_token")
        next_refresh_token = _get_auth_value(session, "refresh_token") or refresh_token

        if not access_token:
            raise RuntimeError("Session refresh returned no access token")

        if not auth_user:
            auth_user_response = supabase.auth.get_user(access_token)
            auth_user = _get_auth_value(auth_user_response, "user")

        if not auth_user:
            raise RuntimeError("Session refresh returned no authenticated user")

        result = (auth_user, access_token, next_refresh_token)
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
    os.getenv("SESSION_INACTIVITY_TIMEOUT_SECONDS", "0")
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

    if age < 0:
        return False

    # Authentication cookies are session cookies, so the browser owns the
    # lifetime of the signed-in session. A zero timeout keeps the session alive
    # while the browser is open; deployments that require an inactivity policy
    # can still opt in with a positive timeout.
    return (
        SESSION_INACTIVITY_TIMEOUT_SECONDS <= 0
        or age <= SESSION_INACTIVITY_TIMEOUT_SECONDS
    )


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
    try:
        from services.admin_account_access_service import delete_admin_account_access_cookie

        delete_admin_account_access_cookie(response)
    except Exception as error:
        logger.warning(
            "auth.admin_access_cookie_delete_failed",
            extra={"error_type": type(error).__name__},
        )


def revoke_verified_auth_session(request: Request) -> bool:
    """Revoke only the provider session already verified for this request."""
    verified = getattr(request.state, "verified_auth_session", None)
    if not isinstance(verified, dict):
        return False

    access_token = verified.get("access_token")
    refresh_token = verified.get("refresh_token")
    if not access_token or not refresh_token:
        return False

    client = create_session_supabase_client()
    client.auth.set_session(access_token, refresh_token)
    client.auth.sign_out({"scope": "local"})
    request.state.verified_auth_session = None
    request.state.verified_session_assurance = None
    request.state.mfa_client = None
    return True


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
        "email_verified": user_data.get("email_verified") is not False,
        "email_verified_at": user_data.get("email_verified_at"),
        "account_status": effective_account_status(user_data),
        "account_kind": user_data.get("account_kind") or "platform",
        "pending_email": user_data.get("pending_email"),
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at"),
    }


def auth_user_email_is_verified(auth_user) -> bool:
    return bool(
        _get_auth_value(auth_user, "email_confirmed_at")
        or _get_auth_value(auth_user, "confirmed_at")
    )


def mark_local_email_verified(user_data):
    if user_data.get("email_verified") is not False:
        return user_data

    verified_at = datetime.now(timezone.utc).isoformat()
    update_response = (
        service_supabase.table("users")
        .update(
            {
                "email_verified": True,
                "email_verified_at": verified_at,
            }
        )
        .eq("id", user_data.get("id"))
        .execute()
    )

    if update_response.data:
        return update_response.data[0]

    return {
        **user_data,
        "email_verified": True,
        "email_verified_at": verified_at,
    }


def get_authenticated_user_row(
    request: Request,
    response: Response | None = None,
    *,
    allow_refresh: bool = True,
    allow_admin_account_access: bool = True,
    reject_admin_account_access: bool = True,
):
    # A failed/repeated authentication must not retain assurance from an earlier call.
    request.state.verified_session_assurance = None
    request.state.verified_auth_session = None
    request.state.mfa_client = None
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
                auth_user = _get_auth_value(auth_response, "user")
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

    except Exception as error:
        if is_definitive_auth_failure(error):
            logger.warning(
                "auth.session.invalid",
                extra={"error_type": type(error).__name__},
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session",
            ) from error

        logger.warning(
            "auth.session.temporarily_unavailable",
            extra={"error_type": type(error).__name__},
        )
        raise SessionRefreshUnavailable(
            "Authentication service is temporarily unavailable"
        ) from error

    if not auth_user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    auth_user_id = _get_auth_value(auth_user, "id")

    if not auth_user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    request.state.verified_auth_session = {
        "access_token": next_access_token,
        "refresh_token": next_refresh_token or "",
        "auth_id": str(auth_user_id),
    }
    request.state.verified_session_assurance = _verified_token_assurance(
        next_access_token, str(auth_user_id), auth_user
    )

    if response and next_access_token and next_refresh_token:
        set_auth_cookies(
            response,
            next_access_token,
            next_refresh_token,
        )

    user_response = (
        service_supabase.table("users")
        .select("*")
        .eq("auth_id", auth_user_id)
        .single()
        .execute()
    )

    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_response.data

    if auth_user_email_is_verified(auth_user):
        provider_email = canonical_auth_email(auth_user)
        if (
            effective_account_status(user_data) != ACTIVE_ACCOUNT_STATUS
            or (
                provider_email
                and normalize_email(user_data.get("email")) != provider_email
            )
        ):
            user_data, _ = synchronize_verified_account(auth_user, user_data)
        else:
            user_data = mark_local_email_verified(user_data)
    else:
        if response:
            delete_auth_cookies(response)
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_verification_required",
                "message": "Verify your email before logging in.",
            },
        )

    if normalize_user_type(user_data.get("user_type")) == "admin":
        try:
            from services.admin_account_access_service import resolve_admin_account_access_user

            target_user = resolve_admin_account_access_user(
                request=request,
                response=response,
                admin_user=user_data,
            )

            if target_user:
                if not allow_admin_account_access:
                    if reject_admin_account_access:
                        raise HTTPException(
                            status_code=403,
                            detail="Admin account access is not allowed for this route",
                        )

                    return auth_user, user_data

                if response is not None:
                    response.headers["X-Madar-Admin-Account-Access"] = "true"

                return auth_user, target_user

        except HTTPException:
            raise
        except Exception as error:
            logger.warning(
                "auth.admin_access_session_resolve_failed",
                extra={"admin_user_id": user_data.get("id"), "error_type": type(error).__name__},
            )

    return auth_user, user_data


def require_system_admin(
    request: Request,
    response: Response | None = None,
    *,
    reject_admin_account_access: bool = True,
    require_aal2: bool = False,
):
    auth_user, user_data = get_authenticated_user_row(
        request,
        response,
        allow_admin_account_access=False,
        reject_admin_account_access=reject_admin_account_access,
    )
    user_type = normalize_user_type(user_data.get("user_type"))

    if user_type != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")

    if require_aal2:
        require_current_session_aal2(request)

    return auth_user, user_data


def _verified_token_assurance(access_token: str | None, auth_id: str, auth_user) -> dict:
    """Read claims only AFTER Auth has verified this exact token and subject.

    get_user(token), or the verified refresh response, is the authentication
    boundary. This helper is not a JWT verifier and must never be called on an
    unverified cookie. No shared client's cached session is authorization.
    """
    try:
        claims = jwt.decode(access_token or "", options={"verify_signature": False})
        expires_at = claims.get("exp")
        if (
            claims.get("sub") != auth_id
            or type(expires_at) is not int
            or expires_at <= time.time()
            or claims.get("aal") not in {"aal1", "aal2"}
        ):
            return {}
        factors = _get_auth_value(auth_user, "factors") or []
        next_level = "aal2" if any(
            _get_auth_value(factor, "status") == "verified" for factor in factors
        ) else claims["aal"]
        return {"current_level": claims["aal"], "next_level": next_level, "expires_at": expires_at}
    except (jwt.PyJWTError, TypeError, ValueError):
        return {}


def get_request_mfa_client(request: Request, response: Response):
    """Create Auth state for the authenticated request, never another user."""
    existing = getattr(request.state, "mfa_client", None)
    if existing is not None:
        return existing
    verified = getattr(request.state, "verified_auth_session", None)
    if not verified or not verified.get("access_token"):
        raise HTTPException(status_code=401, detail="Verified session required")
    client = create_session_supabase_client()
    try:
        client.auth.set_session(verified["access_token"], verified["refresh_token"])
        session = client.auth.get_session()
        if not session or str(_get_auth_value(session.user, "id")) != verified["auth_id"]:
            raise ValueError("session_subject_mismatch")
        if session.access_token != verified["access_token"] and session.refresh_token:
            set_auth_cookies(response, session.access_token, session.refresh_token)
        request.state.mfa_client = client
        return client
    except Exception as error:
        logger.warning("auth.mfa.session_unavailable", extra={"error_type": type(error).__name__})
        raise SessionRefreshUnavailable() from error


def get_current_aal(request: Request | None = None) -> dict:
    """Return only this request's provider-verified assurance, or fail closed."""
    assurance = getattr(request.state, "verified_session_assurance", None) if request else None
    if not isinstance(assurance, dict) or assurance.get("expires_at", 0) <= time.time():
        return {}
    return {key: assurance[key] for key in ("current_level", "next_level")}


def require_current_session_aal2(request: Request | None = None) -> dict:
    aal = get_current_aal(request)
    if aal.get("current_level") != "aal2":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "aal2_required",
                "message": "MFA verification is required for this admin action",
            },
        )
    return aal


def get_admin_account_access_context(request: Request) -> dict | None:
    return getattr(request.state, "admin_account_access_context", None)


def require_regular_user(
    request: Request,
    response: Response | None = None,
    *,
    allow_admin_account_access: bool = True,
):
    auth_user, user_data = get_authenticated_user_row(
        request,
        response,
        allow_admin_account_access=allow_admin_account_access,
    )
    user_type = normalize_user_type(user_data.get("user_type"))

    if user_type != "user":
        raise HTTPException(status_code=403, detail="User access is required")
    if not is_platform_account(user_data):
        raise api_error(
            403,
            "platform_account_required",
            "This account is limited to the website where it was created.",
        )

    return auth_user, user_data


def require_regular_user_id(
    user_id: int,
    request: Request,
    response: Response | None = None,
    *,
    allow_admin_account_access: bool = True,
):
    auth_user, user_data = require_regular_user(
        request,
        response,
        allow_admin_account_access=allow_admin_account_access,
    )

    try:
        path_user_id = int(user_id)
        authenticated_user_id = int(user_data.get("id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="User id is invalid")

    if authenticated_user_id != path_user_id:
        raise HTTPException(status_code=403, detail="User id does not match session")

    return auth_user, user_data
