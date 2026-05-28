import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Response, Request, UploadFile
from database import service_supabase
from classes import UserProfileUpdate
from services.auth_service import get_authenticated_user_row, build_user_payload

router = APIRouter(prefix="/user", tags=["User"])

AVATAR_UPLOAD_DIR = Path(os.getenv("AVATAR_UPLOAD_DIR", "avatar_uploads"))
AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


@router.post("/info")
def user_info(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        return {
            "success": True,
            "user": build_user_payload(user_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        print("USER INFO ERROR:", repr(e))
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
            update_payload["email"] = str(profile.email).strip().lower()
        if profile.phone is not None:
            update_payload["phone"] = profile.phone.strip()
        if profile.avatar is not None:
            update_payload["avatar"] = profile.avatar.strip()
        if profile.subscription_type is not None: 
            update_payload["subscription_type"] = profile.subscription_type.strip()
        if profile.payment_status is not None: 
            update_payload["payment_status"] = profile.payment_status.strip()

        if not update_payload:
            return {
                "success": True,
                "user": build_user_payload(user_data),
            }

        update_response = service_supabase.table("users").update(update_payload).eq(
            "auth_id", user_data.get("auth_id")
        ).execute()

        updated_user = update_response.data[0] if update_response.data else {
            **user_data,
            **update_payload,
        }

        return {
            "success": True,
            "message": "User profile updated",
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise
    except Exception as e:
        print("USER PROFILE UPDATE ERROR:", repr(e))
        raise HTTPException(status_code=500, detail="Could not update user profile")


@router.post("/avatar")
async def upload_user_avatar(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        extension = AVATAR_EXTENSIONS.get(file.content_type or "")
        if not extension:
            raise HTTPException(
                status_code=400,
                detail="Please upload a PNG, JPG, or WebP image.",
            )

        content = await file.read()
        if len(content) > AVATAR_MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Profile photo must be 5MB or smaller.",
            )

        filename = f"{user_data.get('auth_id')}-{uuid4().hex}{extension}"
        avatar_path = AVATAR_UPLOAD_DIR / filename
        avatar_path.write_bytes(content)

        avatar_url = f"/avatar_uploads/{filename}"
        update_response = service_supabase.table("users").update({
            "avatar": avatar_url,
        }).eq("auth_id", user_data.get("auth_id")).execute()

        updated_user = update_response.data[0] if update_response.data else {
            **user_data,
            "avatar": avatar_url,
        }

        return {
            "success": True,
            "avatar": avatar_url,
            "user": build_user_payload(updated_user),
        }

    except HTTPException:
        raise
    except Exception as e:
        print("USER AVATAR UPLOAD ERROR:", repr(e))
        raise HTTPException(status_code=500, detail="Could not upload profile photo")
