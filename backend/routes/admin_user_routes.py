from fastapi import APIRouter, Query, Request, Response

from classes import AdminUserTypeUpdateRequest
from services.audit_service import hash_audit_identifier, record_audit_event
from services.admin_user_service import (
    delete_user_account,
    list_users_with_features,
    update_user_type,
)
from services.auth_service import require_system_admin


router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


@router.get("")
def list_users(
    request: Request,
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
    search: str = Query(default=""),
):
    require_system_admin(request, response, require_aal2=True)

    result = list_users_with_features(
        page=page,
        page_size=page_size,
        limit=limit,
        offset=offset,
        search=search,
    )

    return {
        "success": True,
        "items": result["items"],
        "users": result["users"],
        "pagination": result["pagination"],
    }


@router.patch("/{user_id}/user-type")
def change_user_type(
    user_id: int,
    update: AdminUserTypeUpdateRequest,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response, require_aal2=True)
    updated_user = update_user_type(user_id=user_id, user_type=update.user_type)

    metadata = {
        "new_user_type": updated_user.get("user_type"),
        "affected_user_id": updated_user.get("id") or user_id,
        "source": "admin",
    }

    if updated_user.get("old_user_type") is not None:
        metadata["old_user_type"] = updated_user.get("old_user_type")

    if updated_user.get("email") is not None:
        metadata["affected_user_email_hash"] = hash_audit_identifier(
            updated_user.get("email")
        )

    record_audit_event(
        request=request,
        tenant_id=updated_user.get("tenant_id"),
        actor_user_id=admin_user.get("id"),
        action="admin.permission_changed",
        target_type="user",
        target_id=user_id,
        metadata=metadata,
    )

    return {
        "success": True,
        "user": updated_user,
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response, require_aal2=True)

    deleted_user = delete_user_account(
        user_id=user_id,
        requesting_user_id=admin_user.get("id"),
    )

    metadata = {
        "deleted_user_id": deleted_user.get("id") or user_id,
        "source": "admin",
    }

    if deleted_user.get("email") is not None:
        metadata["deleted_user_email_hash"] = hash_audit_identifier(
            deleted_user.get("email")
        )

    if deleted_user.get("user_type") is not None:
        metadata["deleted_user_type"] = deleted_user.get("user_type")

    record_audit_event(
        request=request,
        tenant_id=deleted_user.get("tenant_id"),
        actor_user_id=admin_user.get("id"),
        action="admin.user_deleted",
        target_type="user",
        target_id=user_id,
        metadata=metadata,
    )

    return {
        "success": True,
        "deleted_user": deleted_user,
    }
