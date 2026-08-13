from fastapi import APIRouter, Request, Response

from classes import AdminAccountAccessGenerateRequest, AdminAccountAccessVerifyRequest
from services.admin_account_access_service import (
    end_admin_account_access_session,
    generate_permission_code,
    verify_permission_code,
)
from services.auth_service import require_system_admin


router = APIRouter(prefix="/admin/account-access", tags=["Admin Account Access"])


@router.post("/generate")
def generate_account_access_code(
    payload: AdminAccountAccessGenerateRequest,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response, require_aal2=True)
    return generate_permission_code(
        request=request,
        admin_user=admin_user,
        target_email=str(payload.email),
    )


@router.post("/verify")
def verify_account_access_code(
    payload: AdminAccountAccessVerifyRequest,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response, require_aal2=True)
    return verify_permission_code(
        request=request,
        response=response,
        admin_user=admin_user,
        target_email=str(payload.email),
        code=payload.code,
    )


@router.post("/end")
def end_account_access(
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(
        request,
        response,
        reject_admin_account_access=False,
    )
    return end_admin_account_access_session(
        request=request,
        response=response,
        admin_user=admin_user,
    )
