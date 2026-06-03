import os
from urllib.parse import urlparse

from fastapi import Request
from starlette.responses import JSONResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
AUTH_COOKIE_NAMES = {"madar_access_token", "madar_refresh_token"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


CSRF_ORIGIN_CHECK_ENABLED = _env_bool("CSRF_ORIGIN_CHECK_ENABLED", True)
CSRF_ALLOW_MISSING_ORIGIN = _env_bool("CSRF_ALLOW_MISSING_ORIGIN", False)


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
