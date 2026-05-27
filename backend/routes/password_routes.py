import os

from fastapi import APIRouter, HTTPException
from supabase import create_client

from classes import PasswordReset
from database import service_supabase, supabase

router = APIRouter(prefix="/auth", tags=["Password"])

FRONTEND_URL = (
    os.getenv("FRONTEND_URL")
    or os.getenv("FRONTEND_URLS", "http://localhost:5173").split(",")[0].strip()
)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
RESET_MESSAGE = "If that email is registered, a password reset link has been sent."

admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@router.post("/forgot-password")
def forgot_password(payload: dict):
    try:
        email = payload.get("email", "").strip().lower()

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        user = service_supabase.table("users").select("id").eq("email", email).single().execute()

        if not user.data:
            return {"message": RESET_MESSAGE}

        supabase.auth.reset_password_email(
            email,
            options={"redirect_to": f"{FRONTEND_URL}/reset-password"},
        )

        return {"message": RESET_MESSAGE}

    except HTTPException:
        raise
    except Exception as e:
        print("FORGOT PASSWORD ERROR:", repr(e))
        return {"message": RESET_MESSAGE}


@router.post("/password-reset")
def password_reset(payload: PasswordReset):
    try:
        user = supabase.auth.get_user(payload.access_token)

        if not user.user:
            raise HTTPException(status_code=401, detail="Invalid user or expired token")

        admin_supabase.auth.admin.update_user_by_id(
            str(user.user.id),
            {"password": payload.password},
        )

        return {
            "message": "Password updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        print("RESET PASSWORD ERROR:", repr(e))
        raise HTTPException(status_code=400, detail="Could not reset password")
