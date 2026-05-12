from fastapi import APIRouter, HTTPException
from database import supabase

router = APIRouter()
@router.post("/forgot-password")
def forgot_password(payload: dict):
    try:
        email = payload.get("email", "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        supabase.auth.reset_password_email(email)

        return {"message": "Password reset email sent"}

    except Exception as e:
        print("FORGOT PASSWORD ERROR:", repr(e))
        raise HTTPException(status_code=400, detail=str(e))