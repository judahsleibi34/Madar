import logging
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from classes import UserProfileUpdate
from database import service_supabase
from services.audit_service import record_security_event
from services.auth_service import build_user_payload, require_system_admin
from services.api_errors import api_error
from services.identity_service import canonical_auth_email, normalize_email
from services.rate_limit_service import enforce_avatar_upload_rate_limit
from services.url_validation import validate_public_url
from routes.user_routes import (
    AVATAR_BUCKET,
    AVATAR_EXTENSIONS,
    AVATAR_MAX_BYTES,
    delete_old_avatar_if_storage_url,
    detect_image_content_type,
    get_storage_public_url,
    upload_avatar_to_storage,
)

router = APIRouter(prefix="/admin/profile", tags=["Admin Profile"])
logger = logging.getLogger(__name__)


@router.post("/info")
def admin_profile_info(request: Request, response: Response):
    try:
        _, admin_user = require_system_admin(request, response)

        return {
            "success": True,
            "user": build_user_payload(admin_user),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("admin.profile.info_failed", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail="Could not fetch admin profile")


@router.put("/profile")
def update_admin_profile(
    profile: UserProfileUpdate,
    request: Request,
    response: Response,
):
    try:
        auth_user, admin_user = require_system_admin(request, response, require_aal2=True)

        if profile.email is not None:
            clean_email = normalize_email(str(profile.email))
            current_email = canonical_auth_email(auth_user) or normalize_email(
                admin_user.get("email")
            )
            if clean_email != current_email:
                # Reject before building the update so names/avatar cannot be
                # partially saved alongside an unverified identity change.
                raise api_error(
                    409,
                    "email_change_requires_verification_flow",
                    "Email changes require a verified email-change flow.",
                )

        update_payload = {}

        if profile.first_name is not None:
            update_payload["first_name"] = profile.first_name.strip()

        if profile.last_name is not None:
            update_payload["last_name"] = profile.last_name.strip()

        if profile.phone is not None:
            update_payload["phone"] = profile.phone.strip()

        if profile.avatar is not None:
            update_payload["avatar"] = validate_public_url(
                profile.avatar,
                field_name="Avatar URL",
                allow_relative=True,
            )

        if not update_payload:
            return {
                "success": True,
                "user": build_user_payload(admin_user),
            }

        try:
            update_response = (
                service_supabase.table("users")
                .update(update_payload)
                .eq("auth_id", admin_user.get("auth_id"))
                .execute()
            )

        except Exception as update_error:
            logger.warning(
                "admin.profile.db_update_failed",
                extra={
                    "admin_user_id": admin_user.get("id"),
                    "error_type": type(update_error).__name__,
                },
            )

            raise HTTPException(
                status_code=500,
                detail="Could not update admin profile",
            )

        updated_user = (
            update_response.data[0]
            if update_response.data
            else {
                **admin_user,
                **update_payload,
            }
        )

        record_security_event(
            request=request,
            tenant_id=admin_user.get("tenant_id"),
            actor_user_id=admin_user.get("id"),
            action="admin.profile_updated",
            target_type="user",
            target_id=admin_user.get("id"),
            metadata={"source": "admin_settings"},
        )

        return {
            "success": True,
            "message": "Admin profile updated",
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning(
            "admin.profile.update_failed",
            extra={"admin_user_id": admin_user.get("id") if "admin_user" in locals() else None, "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not update admin profile")


@router.post("/avatar")
async def upload_admin_avatar(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    try:
        _, admin_user = require_system_admin(request, response, require_aal2=True)
        enforce_avatar_upload_rate_limit(
            request,
            admin_user.get("id"),
            admin_user.get("tenant_id"),
        )

        auth_id = str(admin_user.get("auth_id") or "").strip()

        if not auth_id:
            raise HTTPException(status_code=400, detail="Admin auth id not found")

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Please upload a valid image file.",
            )

        if len(content) > AVATAR_MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Profile photo must be 5MB or smaller.",
            )

        content_type = detect_image_content_type(
            content=content,
            uploaded_content_type=file.content_type or "",
        )

        if not content_type:
            raise HTTPException(
                status_code=400,
                detail="Please upload a PNG, JPG, or WebP image.",
            )

        extension = AVATAR_EXTENSIONS[content_type]
        filename = f"{uuid4().hex}{extension}"
        storage_path = f"users/{auth_id}/{filename}"

        upload_avatar_to_storage(
            storage_path=storage_path,
            content=content,
            content_type=content_type,
        )

        avatar_url = get_storage_public_url(AVATAR_BUCKET, storage_path)

        try:
            update_response = (
                service_supabase.table("users")
                .update({"avatar": avatar_url})
                .eq("auth_id", auth_id)
                .execute()
            )

        except Exception as db_error:
            logger.warning(
                "admin.avatar.db_update_failed",
                extra={
                    "admin_user_id": admin_user.get("id"),
                    "error_type": type(db_error).__name__,
                },
            )

            try:
                service_supabase.storage.from_(AVATAR_BUCKET).remove([storage_path])
            except Exception as cleanup_error:
                logger.warning(
                    "admin.avatar.storage_rollback_failed",
                    extra={
                        "admin_user_id": admin_user.get("id"),
                        "error_type": type(cleanup_error).__name__,
                    },
                )

            raise HTTPException(
                status_code=500,
                detail="Could not save profile photo",
            )

        updated_user = (
            update_response.data[0]
            if update_response.data
            else {
                **admin_user,
                "avatar": avatar_url,
            }
        )

        delete_old_avatar_if_storage_url(
            old_avatar=str(admin_user.get("avatar") or ""),
            auth_id=auth_id,
        )

        record_security_event(
            request=request,
            tenant_id=admin_user.get("tenant_id"),
            actor_user_id=admin_user.get("id"),
            action="admin.avatar_updated",
            target_type="user",
            target_id=admin_user.get("id"),
            metadata={"source": "admin_settings"},
        )

        return {
            "success": True,
            "message": "Profile photo updated",
            "avatar": avatar_url,
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning(
            "admin.avatar.upload_failed",
            extra={"admin_user_id": admin_user.get("id") if "admin_user" in locals() else None, "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not upload profile photo")
