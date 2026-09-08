from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from services.auth_service import (
    delete_auth_cookies,
    require_current_session_aal2,
    require_regular_user,
    require_system_admin,
)
from services.data_deletion_service import (
    cancel_deletion_request,
    get_deletion_request,
    list_deletion_requests,
    public_request_status,
    request_tenant_deletion,
    request_user_deletion,
)
from services.tenant_service import get_current_tenant_context


router = APIRouter(tags=["Data Deletion"])


@router.post("/account/deletion", status_code=status.HTTP_202_ACCEPTED)
def close_own_account(request: Request, response: Response):
    _, user = require_regular_user(
        request, response, allow_admin_account_access=False
    )
    result = request_user_deletion(
        target_user_id=int(user["id"]), requested_by_user_id=int(user["id"])
    )
    delete_auth_cookies(response)
    return {"success": True, "deletion_request": result}


@router.post("/tenant/deletion", status_code=status.HTTP_202_ACCEPTED)
def close_current_tenant(request: Request, response: Response):
    context = get_current_tenant_context(
        request, response, allow_admin_account_access=False
    )
    if context.role != "owner":
        raise HTTPException(status_code=403, detail="Tenant owner access is required")
    require_current_session_aal2(request)
    result = request_tenant_deletion(
        target_tenant_id=context.tenant_id,
        requested_by_user_id=context.user_id,
    )
    delete_auth_cookies(response)
    return {"success": True, "deletion_request": result}


@router.get("/account/deletion/{request_id}")
def own_deletion_status(request_id: str, request: Request, response: Response):
    _, user = require_regular_user(request, response, allow_admin_account_access=False)
    row = get_deletion_request(request_id)
    if not row or int(row.get("requested_by_user_id") or -1) != int(user["id"]):
        raise HTTPException(status_code=404, detail="Deletion request was not found")
    return {"success": True, "deletion_request": public_request_status(row)}


@router.get("/admin/data-deletions")
def admin_deletion_list(request: Request, response: Response, limit: int = 100):
    require_system_admin(request, response, require_aal2=True)
    return {"success": True, "deletion_requests": list_deletion_requests(limit=limit)}


@router.get("/admin/data-deletions/{request_id}")
def admin_deletion_status(request_id: str, request: Request, response: Response):
    require_system_admin(request, response, require_aal2=True)
    row = get_deletion_request(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Deletion request was not found")
    return {"success": True, "deletion_request": public_request_status(row, include_target=True)}


@router.post("/admin/data-deletions/{request_id}/cancel")
def admin_cancel_deletion(request_id: str, request: Request, response: Response):
    require_system_admin(request, response, require_aal2=True)
    return {"success": True, "deletion_request": cancel_deletion_request(request_id)}
