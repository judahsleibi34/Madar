import logging

from fastapi import APIRouter, HTTPException, Request, Response, File, UploadFile
from services.tenant_service import require_active_tenant_member
from services.elearning_access_service import authorize_elearning_context
from services.audit_service import record_audit_event
from services import elearning_settings_service as service
from services.elearning_academy_service import member_profile
from services.academy_builder_service import management_profile

router = APIRouter(prefix="/elearning", tags=["E-Learning"])
logger = logging.getLogger(__name__)


def require_settings_admin(request, response):
    context = require_active_tenant_member(request, response, allow_admin_account_access=False)
    return authorize_elearning_context(context, "elearning.manage")


@router.get("/settings")
def get_settings(request: Request, response: Response):
    context = require_settings_admin(request, response)
    try:
        available = service.settings_available()
        settings = service.get_settings(context.tenant_id) if available else service.ELearningSettings().model_dump()
        return {"success": True, "settings": settings, "available": available, "referrals_available": service.settings_available(136), "academy": member_profile(context.tenant_id) if settings.get("academy_enabled") else None, "academy_management": management_profile(context.tenant_id) if available else None}
    except HTTPException:
        raise
    except Exception:
        logger.exception("elearning.settings.read_failed")
        raise HTTPException(status_code=500, detail="Could not load E-Learning settings")


@router.put("/settings")
def save_settings(settings: service.ELearningSettings, request: Request, response: Response):
    context = require_settings_admin(request, response)
    try:
        if not service.settings_available():
            raise HTTPException(status_code=503, detail={"code": "elearning_upgrade_required", "message": "E-Learning settings are unavailable until the database upgrade completes."})
        saved = service.save_settings(context.tenant_id, settings)
        record_audit_event(request=request, actor_user_id=context.user_id, tenant_id=context.tenant_id,
                           action="elearning.settings_updated", target_type="elearning_settings", target_id=context.tenant_id)
        return {"success": True, "settings": saved, "available": True, "academy": member_profile(context.tenant_id) if saved.get("academy_enabled") else None}
    except HTTPException:
        raise
    except Exception:
        logger.exception("elearning.settings.save_failed")
        raise HTTPException(status_code=500, detail="Could not save E-Learning settings")


@router.post("/logo/upload")
async def upload_logo(request: Request, response: Response, file: UploadFile = File(...)):
    # Share content validation, storage quotas, rate limiting and cleanup with
    # managed uploads, while retaining E-Learning owner/admin authorization.
    from routes.builder_routes import upload_builder_asset
    request.scope["madar_asset_usage"] = "elearning_logo"
    return await upload_builder_asset(request=request, response=response, file=file)
