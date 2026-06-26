import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import re
from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.responses import JSONResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
AUTH_COOKIE_NAMES = {"madar_access_token", "madar_refresh_token"}
CSRF_COOKIE_NAME = "madar_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_MAX_AGE_SECONDS = int(os.getenv("CSRF_TOKEN_MAX_AGE_SECONDS", "900"))
CSRF_EXEMPT_PATHS = {
    ("POST", "/auth/login"),
    ("POST", "/auth/signup"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/password-reset"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/log_out"),
    ("POST", "/billing/webhook"),
    ("POST", "/public/contact"),
}
CSRF_EXEMPT_PATTERNS = (
    re.compile(r"^/public/sites/[^/]+/forms/[^/]+/submissions$"),
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


CSRF_ORIGIN_CHECK_ENABLED = _env_bool("CSRF_ORIGIN_CHECK_ENABLED", True)
CSRF_ALLOW_MISSING_ORIGIN = _env_bool("CSRF_ALLOW_MISSING_ORIGIN", False)


def _env_name(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _app_env() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("FASTAPI_ENV")
        or "development"
    ).strip().lower()


def _cookie_secure() -> bool:
    default = "true" if _app_env() in {"prod", "production"} else "false"
    return os.getenv("COOKIE_SECURE", default).lower() == "true"


def _cookie_samesite() -> str:
    return os.getenv("COOKIE_SAMESITE", "lax").strip().lower()


def get_csrf_secret() -> str:
    secret = _env_name("CSRF_SECRET", "SUPABASE_SERVICE_KEY", "SECRET_KEY")

    if secret:
        return secret

    if _app_env() in {"prod", "production"}:
        raise RuntimeError("CSRF_SECRET or another server-side secret is required")

    return "madar-development-csrf-secret"


def normalize_origin(value: str | None) -> str | None:
    if not value:
        return None

    parsed = urlparse(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def get_allowed_origins(frontend_urls: list[str] | None = None) -> set[str]:
    configured = list(frontend_urls or [])
    extra = os.getenv("CSRF_TRUSTED_ORIGINS", "")
    configured.extend(origin.strip() for origin in extra.split(",") if origin.strip())

    origins = {origin for origin in (normalize_origin(item) for item in configured) if origin}
    return origins


def request_has_auth_cookie(request: Request) -> bool:
    return any(request.cookies.get(cookie_name) for cookie_name in AUTH_COOKIE_NAMES)


def get_session_token(request: Request) -> str:
    return (
        request.cookies.get("madar_refresh_token")
        or request.cookies.get("madar_access_token")
        or ""
    )


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _sign(value: str) -> str:
    return _b64encode(
        hmac.new(
            get_csrf_secret().encode("utf-8"),
            value.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )


def _session_fingerprint(session_token: str) -> str:
    return _b64encode(
        hmac.new(
            get_csrf_secret().encode("utf-8"),
            session_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )


def create_csrf_token(
    *,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> str:
    session_token = refresh_token or access_token or ""

    payload = {
        "v": 1,
        "exp": int(time.time()) + CSRF_TOKEN_MAX_AGE_SECONDS,
        "nonce": secrets.token_urlsafe(24),
        "session": _session_fingerprint(session_token),
    }
    encoded_payload = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )

    return f"{encoded_payload}.{_sign(encoded_payload)}"


def set_csrf_cookie(response: Response, csrf_token: str):
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path="/",
    )
    response.headers[CSRF_HEADER_NAME] = csrf_token


def delete_csrf_cookie(response: Response):
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path="/",
    )


def is_csrf_exempt(request: Request) -> bool:
    method = request.method.upper()
    path = request.url.path

    if method in SAFE_METHODS:
        return True

    if (method, path) in CSRF_EXEMPT_PATHS:
        return True

    if method == "POST" and any(pattern.match(path) for pattern in CSRF_EXEMPT_PATTERNS):
        return True

    return False


def validate_csrf_token_value(token: str, session_token: str) -> bool:
    try:
        encoded_payload, supplied_signature = token.split(".", 1)
    except ValueError:
        return False

    expected_signature = _sign(encoded_payload)

    if not hmac.compare_digest(supplied_signature, expected_signature):
        return False

    try:
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return False

    try:
        expires_at = int(payload.get("exp") or 0)
    except (TypeError, ValueError):
        return False

    if expires_at < int(time.time()):
        return False

    expected_session = _session_fingerprint(session_token)
    supplied_session = str(payload.get("session") or "")

    if not supplied_session or not hmac.compare_digest(supplied_session, expected_session):
        return False

    return True


def origin_from_request(request: Request) -> str | None:
    origin = normalize_origin(request.headers.get("origin"))
    if origin:
        return origin

    referer = normalize_origin(request.headers.get("referer"))
    if referer:
        return referer

    return None


def validate_cookie_write_origin(request: Request, allowed_origins: set[str]) -> JSONResponse | None:
    if not CSRF_ORIGIN_CHECK_ENABLED:
        return None

    if request.method.upper() in SAFE_METHODS:
        return None

    if not request_has_auth_cookie(request):
        return None

    request_origin = origin_from_request(request)

    if request_origin is None and CSRF_ALLOW_MISSING_ORIGIN:
        return None

    if request_origin and request_origin in allowed_origins:
        return None

    return JSONResponse(
        status_code=403,
        content={"detail": "Invalid request origin"},
    )


def validate_csrf_token(request: Request) -> JSONResponse | None:
    if is_csrf_exempt(request):
        return None

    if not request_has_auth_cookie(request):
        return None

    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not header_token or not cookie_token:
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid CSRF token"},
        )

    if not hmac.compare_digest(header_token, cookie_token):
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid CSRF token"},
        )

    if not validate_csrf_token_value(header_token, get_session_token(request)):
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid CSRF token"},
        )

    return None
