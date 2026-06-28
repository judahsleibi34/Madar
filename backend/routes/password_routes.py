import os
import logging

from fastapi import APIRouter, HTTPException, Request
from supabase import create_client

from classes import PasswordReset
from database import service_supabase, supabase
from services.rate_limit_service import enforce_password_rate_limit
from services.audit_service import record_security_event

router = APIRouter(prefix="/auth", tags=["Password"])
logger = logging.getLogger(__name__)

FRONTEND_URL = (
    os.getenv("FRONTEND_URL")
    or os.getenv("FRONTEND_URLS", "http://localhost:5173").split(",")[0].strip()
)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
RESET_MESSAGE = "If that email is registered, a password reset link has been sent."


def get_local_user_by_auth_id(auth_id: str):
    if not auth_id:
        return None

    result = (
        service_supabase.table("users")
        .select("id, tenant_id")
        .eq("auth_id", str(auth_id))
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@router.post("/forgot-password")
def forgot_password(payload: dict, request: Request):
    audit_recorded = False

    try:
        email = payload.get("email", "").strip().lower()

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        enforce_password_rate_limit(request, "forgot_password", email)

        user = service_supabase.table("users").select("id, tenant_id").eq("email", email).single().execute()
        user_row = user.data if isinstance(user.data, dict) else (user.data[0] if user.data else None)

        record_security_event(
            request=request,
            tenant_id=(user_row or {}).get("tenant_id"),
            actor_user_id=(user_row or {}).get("id"),
            action="auth.password_reset_requested",
            target_type="user" if user_row else "auth",
            target_id=(user_row or {}).get("id"),
            metadata={"user_found": bool(user_row)},
        )
        audit_recorded = True

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
        logger.warning("auth.forgot_password.failed", extra={"error_type": type(e).__name__})

        if not audit_recorded:
            record_security_event(
                request=request,
                action="auth.password_reset_requested",
                target_type="auth",
                metadata={"user_found": False, "lookup_failed": True},
            )

        return {"message": RESET_MESSAGE}


@router.post("/password-reset")
def password_reset(payload: PasswordReset, request: Request):
    try:
        enforce_password_rate_limit(request, "password_reset")

        user = supabase.auth.get_user(payload.access_token)

        if not user.user:
            raise HTTPException(status_code=401, detail="Invalid user or expired token")

        admin_supabase.auth.admin.update_user_by_id(
            str(user.user.id),
            {"password": payload.password},
        )

        local_user = get_local_user_by_auth_id(str(user.user.id))
        record_security_event(
            request=request,
            tenant_id=(local_user or {}).get("tenant_id"),
            actor_user_id=(local_user or {}).get("id"),
            action="auth.password_reset_completed",
            target_type="user" if local_user else "auth",
            target_id=(local_user or {}).get("id"),
            metadata={"method": "reset_token"},
        )

        return {
            "message": "Password updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("auth.password_reset.failed", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=400, detail="Could not reset password")
