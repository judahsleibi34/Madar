"""Tenant-scoped continuations around existing Madar authentication."""
import os
from urllib.parse import quote, unquote, urlsplit
from fastapi import HTTPException


def verification_redirect(identifier, request, target):
    """Keep verification in its academy, including allowlisted local previews."""
    from services.frontend_url import resolve_frontend_url_for_request
    from services.hosted_address_service import canonical_tenant_url

    main_base = f"/academy/{identifier}"
    origin = (request.headers.get("origin") or "").rstrip("/")
    frontend = resolve_frontend_url_for_request(origin)
    if (os.getenv("APP_ENV") == "development" and origin == frontend
            and urlsplit(frontend).hostname in {"localhost", "127.0.0.1", "::1"}):
        local_target = safe_return_path(target, main_base)
        return f"{frontend}{main_base}/login?returnTo={quote(local_target, safe='')}"
    hosted_target = target
    if target == main_base or target.startswith(main_base + "/"):
        hosted_target = "/academy" + target[len(main_base):]
    return canonical_tenant_url(identifier, f"/academy/login?returnTo={quote(hosted_target, safe='')}")


def safe_return_path(requested, base):
    if not isinstance(requested, str) or not requested.startswith("/") or requested.startswith("//"):
        return base
    decoded = requested
    for _ in range(4):
        decoded = unquote(decoded)
    if any(char in decoded for char in ("\\", "\r", "\n", "\x00")) or decoded.startswith("//"):
        return base
    parsed = urlsplit(decoded)
    if parsed.scheme or parsed.netloc or any(part in {".", ".."} for part in parsed.path.split("/")):
        return base
    if parsed.path == base or parsed.path.startswith(base + "/"):
        return requested
    if parsed.path == "/my-learning" or parsed.path.startswith("/my-learning/"):
        return requested
    return base


def academy_auth_settings(identifier, request):
    from routes.public_site_routes import resolve_website_settings, resolve_tenant_id
    from services.elearning_settings_service import get_settings, settings_available
    website = resolve_website_settings(identifier, request=request)
    tenant_id = resolve_tenant_id(website)
    settings = get_settings(tenant_id)
    if not settings_available(132) or not settings["enabled"] or not settings["academy_enabled"]:
        raise HTTPException(404, "Academy unavailable")
    return website, tenant_id, settings
