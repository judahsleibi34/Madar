from fastapi import APIRouter, HTTPException
from database import supabase
from supabase import create_client
from classes import PasswordReset
import os

router = APIRouter()
FRONTEND_URL = os.getenv("FRONTEND_URLS", "http://localhost:5173")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

@router.post("/forgot-password")
def forgot_password(payload: dict):
    try:
        email = payload.get("email", "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        user = supabase.table("users").select("id").eq("email", email).single().execute()

        if not user.data:
            raise HTTPException(status_code=404, detail="This email is not registered. Please sign up first.")

        supabase.auth.reset_password_email(
            email,
            options={"redirect_to": f"{FRONTEND_URL}/reset-password"}
        )

        return {"message": "Password reset email sent"}

    except HTTPException:
        raise
    except Exception as e:
        print("FORGOT PASSWORD ERROR:", repr(e))
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/password_rest")
def password_rest(payload: PasswordReset): 
    try: 
        user = supabase.auth.get_user(payload.access_token)

        if not user.user: 
            raise HTTPException(status_code= 401, detail= "Invalid user or expired token")
        
        admin_supabase.auth.admin.update_user_by_id(
            str(user.user.id),
            {"password": payload.password}
        )

        return {"message": "Password updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print("RESET PASSWORD ERROR:", repr(e))
        raise HTTPException(status_code=400, detail=str(e))