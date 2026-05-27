from fastapi import APIRouter, HTTPException, Response, Request
from database import service_supabase
from classes import UserProfileUpdate
from services.auth_service import get_authenticated_user_row, build_user_payload

router = APIRouter(prefix="/user", tags=["User"])


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
