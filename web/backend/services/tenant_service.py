from dataclasses import dataclass

from fastapi import HTTPException, Request, Response

from database import service_supabase
from services.auth_service import require_regular_user
from services.tenant_lifecycle_service import tenant_is_active


@dataclass(frozen=True)
class TenantContext:
    tenant_id: int
    user_id: int
    auth_id: str
    role: str
    membership_status: str
    user: dict
    membership: dict


def _as_int(value, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"User {field_name} is invalid")


def get_current_tenant_context(
    request: Request,
    response: Response | None = None,
    *,
    allow_admin_account_access: bool = True,
) -> TenantContext:
    auth_user, user_data = require_regular_user(
        request,
        response,
        allow_admin_account_access=allow_admin_account_access,
    )

    tenant_id = user_data.get("tenant_id")
    user_id = user_data.get("id")
    auth_id = str(user_data.get("auth_id") or getattr(auth_user, "id", "") or "")

    if tenant_id is None:
        raise HTTPException(status_code=403, detail="User does not belong to a tenant")

    if user_id is None:
        raise HTTPException(status_code=403, detail="User profile is missing an id")

    if not auth_id:
        raise HTTPException(status_code=403, detail="User profile is missing an auth id")

    tenant_id = _as_int(tenant_id, "tenant_id")
    user_id = _as_int(user_id, "id")

    membership_response = (
        service_supabase.table("tenant_memberships")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("user_id", user_id)
        .eq("auth_id", auth_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )

    membership_rows = getattr(membership_response, "data", None) or []
    membership = membership_rows[0] if membership_rows else None

    if not membership:
        raise HTTPException(status_code=403, detail="Active tenant membership required")

    if not tenant_is_active(tenant_id):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "tenant_deletion_pending",
                "message": "This workspace is closed while deletion is being completed.",
            },
        )

    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        auth_id=auth_id,
        role=str(membership.get("role") or ""),
        membership_status=str(membership.get("status") or ""),
        user=user_data,
        membership=membership,
    )


def require_active_tenant_member(
    request: Request,
    response: Response | None = None,
    *,
    allow_admin_account_access: bool = True,
) -> TenantContext:
    return get_current_tenant_context(
        request,
        response,
        allow_admin_account_access=allow_admin_account_access,
    )


def require_active_tenant_user_id(
    user_id: int,
    request: Request,
    response: Response | None = None,
    *,
    allow_admin_account_access: bool = True,
) -> TenantContext:
    """Authorize a path-scoped user and require a current tenant membership."""
    context = require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=allow_admin_account_access,
    )

    try:
        path_user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="User id is invalid")

    if context.user_id != path_user_id:
        raise HTTPException(status_code=403, detail="User id does not match session")

    return context


def require_builder_write_access(
    request: Request,
    response: Response | None = None,
) -> TenantContext:
    context = get_current_tenant_context(
        request,
        response,
        allow_admin_account_access=False,
    )

    if context.role not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=403, detail="Builder write access required")

    return context


def require_builder_admin_access(
    request: Request,
    response: Response | None = None,
) -> TenantContext:
    context = get_current_tenant_context(
        request,
        response,
        allow_admin_account_access=False,
    )

    if context.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Builder admin access required")

    return context
