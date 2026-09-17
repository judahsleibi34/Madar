import os
import logging
import hashlib
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from classes import UserProfileUpdate
from database import service_supabase
from services.billing_service import get_billing_summary_for_tenant
from services.rate_limit_service import enforce_avatar_upload_rate_limit
from services.auth_service import (
    build_user_payload,
    get_authenticated_user_row,
    require_regular_user,
    require_regular_user_id,
)
from services.api_errors import api_error
from services.identity_service import canonical_auth_email
from services.url_validation import validate_public_url
from services.storage_quota_service import finish_storage, release_storage, reserve_storage

router = APIRouter(prefix="/users/{user_id}", tags=["User"])
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")

AVATAR_BUCKET = "avatars"
AVATAR_MAX_BYTES = 5 * 1024 * 1024

AVATAR_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def detect_image_content_type(content: bytes, uploaded_content_type: str = "") -> str:
    uploaded_content_type = (uploaded_content_type or "").strip().lower()

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if len(content) >= 12 and content[0:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"

    return ""


def get_storage_public_url(bucket: str, path: str) -> str:
    if not SUPABASE_URL:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL is not configured",
        )

    clean_path = path.strip().lstrip("/")
    encoded_path = quote(clean_path, safe="/")

    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{encoded_path}"


def upload_avatar_to_storage(storage_path: str, content: bytes, content_type: str):
    try:
        result = service_supabase.storage.from_(AVATAR_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "true",
            },
        )

        return result

    except Exception as storage_error:
        logger.warning("user.avatar.storage_upload_failed", extra={"error_type": type(storage_error).__name__})
        raise HTTPException(
            status_code=500,
            detail="Could not upload profile photo.",
        )


def delete_old_avatar_if_storage_url(old_avatar: str, auth_id: str) -> str | None:
    if not old_avatar:
        return None

    marker = f"/storage/v1/object/public/{AVATAR_BUCKET}/"

    if marker not in old_avatar:
        return None

    try:
        storage_path = old_avatar.split(marker, 1)[1].split("?", 1)[0]

        if not storage_path.startswith(f"users/{auth_id}/"):
            return None

        service_supabase.storage.from_(AVATAR_BUCKET).remove([storage_path])
        return storage_path

    except Exception as cleanup_error:
        logger.warning("user.avatar.old_cleanup_failed", extra={"auth_id": auth_id, "error_type": type(cleanup_error).__name__})
        return None


def is_duplicate_error(error: Exception) -> bool:
    raw_message = str(error).lower()

    return (
        "duplicate" in raw_message
        or "unique" in raw_message
        or "already exists" in raw_message
    )


@router.get("/info")
def user_info(user_id: int, request: Request, response: Response):
    try:
        _, user_data = require_regular_user_id(user_id, request, response)
        user_payload = build_user_payload(user_data)
        user_payload.update(get_billing_summary_for_tenant(user_data.get("tenant_id")))

        return {
            "success": True,
            "user": user_payload,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("user.info.failed", extra={"user_id": user_id, "error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail="Could not fetch user info")


@router.post("/info", include_in_schema=False)
def user_info_legacy(user_id: int, request: Request, response: Response):
    """Compatibility alias for older clients; account reads are otherwise GET-only."""
    return user_info(user_id, request, response)


@router.put("/profile")
def update_user_profile(
    user_id: int,
    profile: UserProfileUpdate,
    request: Request,
    response: Response,
):
    try:
        auth_user, user_data = require_regular_user_id(
            user_id,
            request,
            response,
            allow_admin_account_access=False,
        )

        if profile.email is not None:
            clean_email = normalize_email(str(profile.email))
            current_email = canonical_auth_email(auth_user) or normalize_email(
                user_data.get("email")
            )

            if clean_email != current_email:
                # Reject before constructing or issuing any update so a request
                # cannot partially change names/avatar alongside an unsafe email.
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
                "user": build_user_payload(user_data),
            }

        try:
            update_response = (
                service_supabase.table("users")
                .update(update_payload)
                .eq("auth_id", user_data.get("auth_id"))
                .execute()
            )

        except Exception as update_error:
            logger.warning("user.profile.db_update_failed", extra={"user_id": user_id, "error_type": type(update_error).__name__})

            if is_duplicate_error(update_error):
                raise HTTPException(
                    status_code=409,
                    detail="Email is already registered",
                )

            raise HTTPException(
                status_code=500,
                detail="Could not update user profile",
            )

        updated_user = (
            update_response.data[0]
            if update_response.data
            else {
                **user_data,
                **update_payload,
            }
        )

        return {
            "success": True,
            "message": "User profile updated",
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("user.profile.update_failed", extra={"user_id": user_id, "error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail="Could not update user profile")


@router.post("/avatar")
async def upload_user_avatar(
    user_id: int,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    try:
        _, user_data = require_regular_user_id(
            user_id,
            request,
            response,
            allow_admin_account_access=False,
        )
        enforce_avatar_upload_rate_limit(request, user_id, user_data.get("tenant_id"))

        auth_id = str(user_data.get("auth_id") or "").strip()

        if not auth_id:
            raise HTTPException(status_code=400, detail="User auth id not found")

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
        tenant_id = int(user_data.get("tenant_id"))
        reservation_id = reserve_storage(
            tenant_id=tenant_id,
            user_id=int(user_data.get("id")),
            category="avatar",
            size_bytes=len(content),
            storage_root=Path(os.getenv("AVATAR_UPLOAD_DIR", "avatar_uploads")),
        )
        try:
            upload_avatar_to_storage(
                storage_path=storage_path,
                content=content,
                content_type=content_type,
            )
        except Exception:
            finish_storage(reservation_id=reservation_id, succeeded=False)
            raise

        avatar_url = get_storage_public_url(AVATAR_BUCKET, storage_path)

        try:
            update_query = service_supabase.table("users").update({"avatar": avatar_url}).eq("auth_id", auth_id)
            old_avatar = str(user_data.get("avatar") or "")
            update_query = update_query.eq("avatar", old_avatar) if old_avatar else update_query.is_("avatar", "null")
            update_response = update_query.execute()
            if not getattr(update_response, "data", None):
                raise RuntimeError("avatar_replacement_conflict")

        except Exception as db_error:
            logger.warning("user.avatar.db_update_failed", extra={"user_id": user_id, "error_type": type(db_error).__name__})

            try:
                service_supabase.storage.from_(AVATAR_BUCKET).remove([storage_path])
            except Exception as cleanup_error:
                logger.warning("user.avatar.storage_rollback_failed", extra={"user_id": user_id, "error_type": type(cleanup_error).__name__})

            finish_storage(reservation_id=reservation_id, succeeded=False)
            status_code = 409 if str(db_error) == "avatar_replacement_conflict" else 500
            raise HTTPException(status_code=status_code, detail="Profile photo changed; retry the upload" if status_code == 409 else "Could not save profile photo")

        try:
            finish_storage(
                reservation_id=reservation_id,
                succeeded=True,
                storage_key=storage_path,
                sha256_hex=hashlib.sha256(content).hexdigest(),
            )
        except Exception as accounting_error:
            service_supabase.table("users").update({"avatar": user_data.get("avatar")}).eq("auth_id", auth_id).eq("avatar", avatar_url).execute()
            service_supabase.storage.from_(AVATAR_BUCKET).remove([storage_path])
            try:
                finish_storage(reservation_id=reservation_id, succeeded=False)
            except Exception:
                pass
            logger.error("user.avatar.accounting_finalize_failed", extra={"user_id": user_id, "error_type": type(accounting_error).__name__})
            raise HTTPException(status_code=503, detail="Profile photo storage accounting is unavailable")

        updated_user = (
            update_response.data[0]
            if update_response.data
            else {
                **user_data,
                "avatar": avatar_url,
            }
        )

        deleted_storage_key = delete_old_avatar_if_storage_url(
            old_avatar=str(user_data.get("avatar") or ""),
            auth_id=auth_id,
        )
        if deleted_storage_key:
            release_storage(tenant_id=tenant_id, category="avatar", storage_key=deleted_storage_key)

        return {
            "success": True,
            "avatar": avatar_url,
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("user.avatar.upload_failed", extra={"user_id": user_id, "error_type": type(e).__name__})
        raise HTTPException(status_code=500, detail="Could not upload profile photo")
