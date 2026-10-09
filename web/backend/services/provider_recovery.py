"""Positive request and provider egress fences for explicitly enabled recovery.

No generic GET exemption: previously reviewed reads only. The provider fence
also covers privileged SDK clients and prevents writes from read handlers.
"""
from __future__ import annotations

from contextvars import ContextVar
import json
import os
import re

import httpx
from fastapi import HTTPException
from starlette.responses import JSONResponse

PROFILE = "provider402-signin"
REQUEST_OPERATION = ContextVar("recovery_operation", default=None)
AUTH_PATHS = frozenset({
    ("POST", "/auth/login"), ("POST", "/auth/log_out"),
    ("POST", "/auth/refresh"), ("POST", "/auth/mfa/login/challenge"),
    ("POST", "/auth/mfa/login/verify"), ("POST", "/auth/mfa/login/cancel"),
})
READ_PATHS = (
    r"/", r"/health/(?:live|version|ready|recovery)",
    r"/auth/(?:user_status|mfa/status|mfa/factors)",
    r"/admin/profile/info", r"/users/[1-9][0-9]*/info", r"/(?:users/[1-9][0-9]*/)?website/settings",
    r"/(?:users/[1-9][0-9]*/)?builder/projects(?:/[A-Za-z0-9-]+)?",
    r"/assets/avatars/[^\\]+", r"/uploads/tenant_[1-9][0-9]*/builder_assets/[A-Za-z0-9_.-]+",
)
# Reviewed normal-candidate reads only; the narrower sign-in recovery profile
# does not inherit these. Provider writes/RPCs remain fenced for every handler.
TRANSITION_READ_PATHS = (
    r"/notifications", r"/calendar/bootstrap",
    r"/builder/reservations(?:/[A-Za-z0-9-]+)?",
    r"/(?:users/[1-9][0-9]*/)?builder/projects/[A-Za-z0-9-]+/form-submissions",
    r"/ecommerce/(?:catalog|orders(?:/[0-9a-fA-F-]{36})?)",
)
AUDIT_ACTIONS = frozenset({
    "auth.login_succeeded", "auth.login_failed", "auth.mfa_login_challenge_started",
    "auth.mfa_login_verified", "auth.mfa_login_failed", "auth.mfa_verified",
    "auth.mfa_challenge_failed", "auth.mfa_enrollment_required",
})
DETAIL = {"code": "provider_recovery_read_only", "message":
          "Madar is temporarily in restricted recovery mode. Business changes are unavailable."}


def enabled() -> bool:
    value = os.getenv("MADAR_RECOVERY_PROFILE", "").strip()
    if value not in {"", PROFILE}:
        raise RuntimeError("recovery_profile_invalid")
    return value == PROFILE


def restricted() -> bool:
    from services.business_write_authority import restricted as transition_restricted
    # Validate an installed transition authority even while recovery is enabled.
    return transition_restricted() or enabled()


def require_existing_account(user: dict, *, active: bool, email_matches: bool) -> None:
    if restricted() and (not active or not email_matches or user.get("email_verified") is False):
        raise HTTPException(status_code=503, detail=DETAIL)


def request_allowed(method: str, path: str) -> bool:
    if "\\" in path or "//" in path or any(p in {".", ".."} for p in path.split("/")):
        return False
    if (method, path) in AUTH_PATHS:
        return True
    patterns = READ_PATHS
    if not enabled():
        from services.business_write_authority import restricted as transition_restricted
        if transition_restricted():
            patterns += TRANSITION_READ_PATHS
    return method in {"GET", "HEAD"} and any(re.fullmatch(p, path) for p in patterns)


class RecoveryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        try:
            fenced = restricted()
        except (RuntimeError, OSError, ValueError):
            return await JSONResponse({"detail": DETAIL}, status_code=503,
                headers={"Cache-Control": "no-store", "Retry-After": "300"})(scope, receive, send)
        if not fenced:
            return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        if not request_allowed(method, path):
            return await JSONResponse({"detail": DETAIL}, status_code=503,
                headers={"Cache-Control": "no-store", "Retry-After": "300",
                         "X-Madar-Recovery": PROFILE})(scope, receive, send)
        marker = REQUEST_OPERATION.set((method, path))
        try:
            await self.app(scope, receive, send)
        finally:
            REQUEST_OPERATION.reset(marker)


def provider_request_allowed(request: httpx.Request) -> bool:
    """Inspect method/path and narrowly scoped payload keys, never log bodies."""
    method, path = request.method, request.url.path
    if method in {"GET", "HEAD"}:
        # RPCs can mutate even with GET. No RPC is approved for this profile.
        return (bool(re.fullmatch(r"/rest/v1/[a-z_]+", path))
                or path in {"/auth/v1/health", "/auth/v1/user", "/auth/v1/factors"}
                or bool(re.fullmatch(r"/storage/v1/object/(?:public/)?(?:avatars|builder-assets)/.+", path)))
    operation = REQUEST_OPERATION.get()
    if (not enabled() and method == "POST" and path == "/rest/v1/rpc/resolve_commercial_access"
            and operation is not None and operation[0] in {"GET", "HEAD"}
            and request_allowed(*operation)):
        # Schema115 defines this exact SQL function STABLE, containing only
        # SELECTs. Commercial authorization remains active during fenced reads.
        try:
            data = json.loads(request.content)
        except (ValueError, UnicodeError):
            return False
        return (isinstance(data, dict) and set(data) == {"p_tenant_id"}
                and type(data["p_tenant_id"]) is int and data["p_tenant_id"] > 0)
    if (method == "POST" and path == "/auth/v1/token"
            and request.url.params.get("grant_type") == "refresh_token"
            and operation is not None and operation[0] == "GET"
            and request_allowed(*operation)
            and operation[1] not in {"/", "/health/live", "/health/version", "/health/ready", "/health/recovery"}
            and not operation[1].startswith("/assets/avatars/")):
        # Authenticated read helpers may rotate an expired session. This is
        # session activity, not permission to write from a business GET.
        return True
    if operation not in AUTH_PATHS:
        return False
    if method == "POST" and path == "/auth/v1/token":
        return request.url.params.get("grant_type") in {"password", "refresh_token"}
    if method == "POST" and (path == "/auth/v1/logout" or re.fullmatch(
            r"/auth/v1/factors/[0-9a-f-]{36}/(?:challenge|verify)", path)):
        return True
    try:
        data = json.loads(request.content)
    except (ValueError, UnicodeError):
        return False
    rows = data if isinstance(data, list) else [data]
    if method == "POST" and path == "/rest/v1/audit_logs":
        return bool(rows) and all(isinstance(row, dict) and row.get("action") in AUDIT_ACTIONS for row in rows)
    if method == "POST" and path == "/rest/v1/user_security_settings":
        # Existing-factor AAL2 completion records only. Enrollment/policy changes
        # never pass this fence, even if invoked through a read route.
        return bool(rows) and all(isinstance(row, dict) and
            set(row) == {"user_id", "auth_id", "last_aal2_at"} for row in rows)
    return False


class RecoveryTransport(httpx.BaseTransport):
    def __init__(self, transport):
        self.transport = transport

    def handle_request(self, request):
        if restricted() and not provider_request_allowed(request):
            raise HTTPException(status_code=503, detail=DETAIL)
        return self.transport.handle_request(request)

    def close(self):
        self.transport.close()


def validate_configuration() -> None:
    from services.business_write_authority import read_authority
    authority = read_authority()
    if authority is not None and (
            os.getenv("SUPABASE_URL") != "http://madar-supabase:8000" or
            os.getenv("MADAR_SUPABASE_CLIENT_NETWORK") != "madar-supabase-client" or
            os.getenv("SCHEMA_COMPATIBLE_MIN") != "115" or
            os.getenv("SCHEMA_COMPATIBLE_MAX") != "115"):
        raise RuntimeError("business_write_authority_runtime_contract_invalid")
    if not enabled():
        return
    if (os.getenv("SUPABASE_URL") != "http://madar-supabase:8000" or
            os.getenv("MADAR_SUPABASE_CLIENT_NETWORK") != "madar-supabase-client" or
            os.getenv("SCHEMA_COMPATIBLE_MIN") != "115" or
            os.getenv("SCHEMA_COMPATIBLE_MAX") != "115"):
        raise RuntimeError("recovery_runtime_contract_invalid")
    for name in ("NOTIFICATION_WORKER_ENABLED", "CALENDAR_SYNC_WORKER_ENABLED", "DATA_DELETION_WORKER_ENABLED"):
        if os.getenv(name, "false").lower() not in {"false", "0", "off"}:
            raise RuntimeError("recovery_workers_must_be_off")


def prohibit_worker_start() -> None:
    if enabled():
        raise RuntimeError("recovery_queue_consumers_prohibited")


def worker_consumption_status() -> tuple[bool, bool]:
    """Standby may be healthy, but it cannot claim jobs without write authority.

    Re-read the root authority on each poll. Invalid/missing installed authority
    fails closed; ordinary workers keep their existing deployment policy.
    """
    try:
        return not restricted(), True
    except (RuntimeError, OSError, ValueError):
        return False, False


def worker_consumption_allowed() -> bool:
    return worker_consumption_status()[0]
