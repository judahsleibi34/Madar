from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, UUID4

from services.installation_service import (
    disable_installation_notifications,
    list_user_installations,
    register_installation,
    revoke_user_installation,
)
from services.tenant_service import get_current_tenant_context


router = APIRouter(prefix="/installations", tags=["Installations"])


class InstallationRegistrationRequest(BaseModel):
    installation_id: UUID4
    platform: Literal["ios", "android", "windows", "macos", "linux", "chromeos", "unknown"] = "unknown"
    display_mode: Literal["browser", "standalone", "ios_standalone"] = "browser"
    notification_permission: Literal["default", "granted", "denied", "unknown"] = "unknown"
    installed_confirmed: bool = False


class CurrentInstallationRequest(BaseModel):
    installation_id: UUID4


@router.get("")
def list_installations(
    request: Request,
    response: Response,
    current_installation_id: UUID4 | None = Query(default=None),
):
    context = get_current_tenant_context(
        request, response, allow_admin_account_access=False
    )
    return {
        "installations": list_user_installations(
            user_id=context.user_id,
            current_installation_id=(
                str(current_installation_id) if current_installation_id else None
            ),
        )
    }


@router.delete("/{installation_record_id}")
def revoke_installation(
    installation_record_id: UUID4,
    request: Request,
    response: Response,
):
    context = get_current_tenant_context(
        request, response, allow_admin_account_access=False
    )
    installation = revoke_user_installation(
        user_id=context.user_id,
        installation_record_id=str(installation_record_id),
    )
    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")
    return {"success": True}


@router.post("/current/notifications/disable")
def disable_current_installation_notifications(
    payload: CurrentInstallationRequest,
    request: Request,
    response: Response,
):
    context = get_current_tenant_context(
        request, response, allow_admin_account_access=False
    )
    installation = disable_installation_notifications(
        user_id=context.user_id,
        installation_id=str(payload.installation_id),
    )
    if not installation:
        raise HTTPException(status_code=404, detail="Active installation not found")
    return {"success": True}


@router.post("/register")
def register_current_installation(
    registration: InstallationRegistrationRequest,
    request: Request,
    response: Response,
):
    context = get_current_tenant_context(
        request, response, allow_admin_account_access=False
    )
    installation = register_installation(
        user_id=context.user_id,
        tenant_id=context.tenant_id,
        installation_id=str(registration.installation_id),
        platform=registration.platform,
        display_mode=registration.display_mode,
        notification_permission=registration.notification_permission,
        installed_confirmed=(
            registration.installed_confirmed
            or registration.display_mode in {"standalone", "ios_standalone"}
        ),
    )
    if not installation:
        raise HTTPException(status_code=500, detail="Could not register installation")
    if installation.get("revoked_at"):
        raise HTTPException(status_code=409, detail="Installation is revoked")

    return {
        "success": True,
        "installation": {
            "installation_id": str(installation.get("installation_id")),
            "display_mode": installation.get("display_mode"),
            "installed": bool(installation.get("installed_confirmed_at")),
            "notification_permission": installation.get("notification_permission"),
            "notifications_enabled": bool(installation.get("notifications_enabled")),
        },
    }
