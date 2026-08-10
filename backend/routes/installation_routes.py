from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, UUID4

from services.installation_service import register_installation
from services.tenant_service import get_current_tenant_context


router = APIRouter(prefix="/installations", tags=["Installations"])


class InstallationRegistrationRequest(BaseModel):
    installation_id: UUID4
    platform: Literal["ios", "android", "windows", "macos", "linux", "chromeos", "unknown"] = "unknown"
    display_mode: Literal["browser", "standalone", "ios_standalone"] = "browser"
    notification_permission: Literal["default", "granted", "denied", "unknown"] = "unknown"
    installed_confirmed: bool = False


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
