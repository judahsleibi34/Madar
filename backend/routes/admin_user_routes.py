from fastapi import APIRouter, Query, Request, Response

from classes import AdminUserTypeUpdateRequest
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
    page_size: int = Query(default=10, ge=1, le=50),
    search: str = Query(default=""),
):
    require_system_admin(request, response)

    result = list_users_with_features(
        page=page,
        page_size=page_size,
        search=search,
    )

    return {
        "success": True,
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
    require_system_admin(request, response)

    return {
        "success": True,
        "user": update_user_type(user_id=user_id, user_type=update.user_type),
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response)

    return {
        "success": True,
        "deleted_user": delete_user_account(
            user_id=user_id,
            requesting_user_id=admin_user.get("id"),
        ),
    }