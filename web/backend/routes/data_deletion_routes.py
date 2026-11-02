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


@router.post("/admin/data-deletions/{request_id}/recover",include_in_schema=False)
@router.post("/admin/account-actions/{request_id}/reactivate")
def recover_account(request_id: str, request: Request, response: Response):
    from database import service_supabase
    from services.account_erasure_service import reactivate,action_status
    _, actor = require_system_admin(request, response, require_aal2=True)
    try:
        row = reactivate(request_id=request_id, actor_id=int(actor["id"]), client=service_supabase)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=409, detail="Account reactivation could not be authorized safely.") from None
    return {"success": True, "account_action":action_status(row)}


@router.post("/account/deactivation",status_code=status.HTTP_202_ACCEPTED)
def deactivate_own_account(request:Request,response:Response):
    from database import service_supabase
    from services.account_erasure_service import request_action,action_status
    _,user=require_regular_user(request,response,allow_admin_account_access=False)
    require_current_session_aal2(request,response)
    row=request_action(user_id=int(user["id"]),actor_id=int(user["id"]),action="deactivate",client=service_supabase,request=request)
    delete_auth_cookies(response)
    return {"success":True,"account_action":action_status(row)}


@router.post("/account/deletion", status_code=status.HTTP_202_ACCEPTED)
def close_own_account(request: Request, response: Response):
    _, user = require_regular_user(
        request, response, allow_admin_account_access=False
    )
    require_current_session_aal2(request,response)
    result = request_user_deletion(
        target_user_id=int(user["id"]), requested_by_user_id=int(user["id"]), request=request
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
    require_current_session_aal2(request, response)
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


@router.get("/admin/account-actions/{request_id}")
def account_action_status(request_id: str, request: Request, response: Response):
    from database import service_supabase
    from services.account_erasure_service import action_status, capability
    require_system_admin(request, response, require_aal2=True)
    capability(service_supabase)
    rows=service_supabase.table("account_lifecycles167").select("*").eq("id",request_id).limit(1).execute().data
    if not rows: raise HTTPException(status_code=404,detail="Account action was not found.")
    return {"success":True,"account_action":action_status(rows[0])}
