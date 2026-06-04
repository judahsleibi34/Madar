import os
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from classes import UserProfileUpdate
from database import service_supabase
from services.billing_service import get_billing_summary_for_tenant
from services.auth_service import build_user_payload, get_authenticated_user_row

router = APIRouter(prefix="/user", tags=["User"])

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
        print("AVATAR STORAGE UPLOAD ERROR:", type(storage_error).__name__)
        raise HTTPException(
            status_code=500,
            detail="Could not upload profile photo.",
        )


def delete_old_avatar_if_storage_url(old_avatar: str, auth_id: str):
    if not old_avatar:
        return

    marker = f"/storage/v1/object/public/{AVATAR_BUCKET}/"

    if marker not in old_avatar:
        return

    try:
        storage_path = old_avatar.split(marker, 1)[1].split("?", 1)[0]

        if not storage_path.startswith(f"users/{auth_id}/"):
            return

        service_supabase.storage.from_(AVATAR_BUCKET).remove([storage_path])

    except Exception as cleanup_error:
        print("OLD AVATAR CLEANUP ERROR:", type(cleanup_error).__name__)


def is_duplicate_error(error: Exception) -> bool:
    raw_message = str(error).lower()

    return (
        "duplicate" in raw_message
        or "unique" in raw_message
        or "already exists" in raw_message
    )


@router.post("/info")
def user_info(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)
        user_payload = build_user_payload(user_data)
        user_payload.update(get_billing_summary_for_tenant(user_data.get("tenant_id")))

        return {
            "success": True,
            "user": user_payload,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("USER INFO ERROR:", type(e).__name__)
        raise HTTPException(status_code=500, detail="Could not fetch user info")


@router.put("/profile")
def update_user_profile(
    profile: UserProfileUpdate,
    request: Request,
    response: Response,
):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        update_payload = {}

        if profile.first_name is not None:
            update_payload["first_name"] = profile.first_name.strip()

        if profile.last_name is not None:
            update_payload["last_name"] = profile.last_name.strip()

        if profile.email is not None:
            clean_email = normalize_email(str(profile.email))

            if not clean_email:
                raise HTTPException(status_code=400, detail="Email is required")

            existing_user = (
                service_supabase.table("users")
                .select("id, auth_id, email")
                .eq("email", clean_email)
                .limit(1)
                .execute()
            )

            if existing_user.data:
                existing = existing_user.data[0]

                if str(existing.get("auth_id")) != str(user_data.get("auth_id")):
                    raise HTTPException(
                        status_code=409,
                        detail="Email is already registered",
                    )

            update_payload["email"] = clean_email

        if profile.phone is not None:
            update_payload["phone"] = profile.phone.strip()

        if profile.avatar is not None:
            update_payload["avatar"] = profile.avatar.strip()

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
            print("USER PROFILE UPDATE DB ERROR:", type(update_error).__name__)

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
        print("USER PROFILE UPDATE ERROR:", type(e).__name__)
        raise HTTPException(status_code=500, detail="Could not update user profile")


@router.post("/avatar")
async def upload_user_avatar(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    try:
        _, user_data = get_authenticated_user_row(request, response)

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

        upload_avatar_to_storage(
            storage_path=storage_path,
            content=content,
            content_type=content_type,
        )

        avatar_url = get_storage_public_url(AVATAR_BUCKET, storage_path)

        try:
            update_response = (
                service_supabase.table("users")
                .update(
                    {
                        "avatar": avatar_url,
                    }
                )
                .eq("auth_id", auth_id)
                .execute()
            )

        except Exception as db_error:
            print("AVATAR DB UPDATE ERROR:", type(db_error).__name__)

            try:
                service_supabase.storage.from_(AVATAR_BUCKET).remove([storage_path])
            except Exception as cleanup_error:
                print("AVATAR STORAGE ROLLBACK ERROR:", type(cleanup_error).__name__)

            raise HTTPException(
                status_code=500,
                detail="Could not save profile photo",
            )

        updated_user = (
            update_response.data[0]
            if update_response.data
            else {
                **user_data,
                "avatar": avatar_url,
            }
        )

        delete_old_avatar_if_storage_url(
            old_avatar=str(user_data.get("avatar") or ""),
            auth_id=auth_id,
        )

        return {
            "success": True,
            "avatar": avatar_url,
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise

    except Exception as e:
        print("USER AVATAR UPLOAD ERROR:", type(e).__name__)
        raise HTTPException(status_code=500, detail="Could not upload profile photo")
