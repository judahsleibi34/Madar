import os

from fastapi import HTTPException, Request, Response

from database import service_supabase, supabase

APP_ENV = (
    os.getenv("APP_ENV")
    or os.getenv("ENV")
    or os.getenv("FASTAPI_ENV")
    or "development"
).strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}

COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE",
    "true" if IS_PRODUCTION else "false",
).lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()

if COOKIE_SAMESITE not in {"strict", "lax", "none"}:
    raise RuntimeError("COOKIE_SAMESITE must be strict, lax, or none")

if IS_PRODUCTION and not COOKIE_SECURE:
    raise RuntimeError("COOKIE_SECURE must be true in production")

if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("COOKIE_SECURE must be true when COOKIE_SAMESITE is none")

# 15 minutes
ACCESS_COOKIE_MAX_AGE = 60 * 15
REFRESH_COOKIE_MAX_AGE = 60 * 15


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="madar_access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_COOKIE_MAX_AGE,
        path="/",
    )

    response.set_cookie(
        key="madar_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path="/",
    )


def delete_auth_cookies(response: Response):
    response.delete_cookie(
        key="madar_access_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )

    response.delete_cookie(
        key="madar_refresh_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def build_user_payload(user_data):
    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or "Admin User"

    return {
        "id": user_data.get("id"),
        "auth_id": user_data.get("auth_id"),
        "tenant_id": user_data.get("tenant_id"),
        "first_name": first_name,
        "last_name": last_name,
        "name": full_name,
        "email": user_data.get("email"),
        "phone": user_data.get("phone") or "",
        "avatar": user_data.get("avatar") or user_data.get("avatar_url") or "",
        "subscription_type": user_data.get("subscription_type") or "",
        "payment_status": user_data.get("payment_status") or "",
        "user_type": user_data.get("user_type") or "user",
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at"),
    }


def get_authenticated_user_row(request: Request, response: Response | None = None):
    access_token = request.cookies.get("madar_access_token")
    refresh_token = request.cookies.get("madar_refresh_token")

    if not access_token and not refresh_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    auth_user = None
    next_access_token = access_token
    next_refresh_token = refresh_token

    try:
        if access_token and refresh_token:
            try:
                auth_response = supabase.auth.set_session(
                    access_token,
                    refresh_token,
                )

                auth_user = getattr(auth_response, "user", None)

                if getattr(auth_response, "session", None):
                    next_access_token = auth_response.session.access_token
                    next_refresh_token = auth_response.session.refresh_token

            except Exception as session_error:
                print("AUTH SET SESSION ERROR:", type(session_error).__name__)

                auth_response = supabase.auth.refresh_session(refresh_token)
                auth_user = getattr(auth_response, "user", None)

                if getattr(auth_response, "session", None):
                    next_access_token = auth_response.session.access_token
                    next_refresh_token = auth_response.session.refresh_token

        elif refresh_token:
            auth_response = supabase.auth.refresh_session(refresh_token)
            auth_user = getattr(auth_response, "user", None)

            if getattr(auth_response, "session", None):
                next_access_token = auth_response.session.access_token
                next_refresh_token = auth_response.session.refresh_token

        elif access_token:
            auth_response = supabase.auth.get_user(access_token)
            auth_user = getattr(auth_response, "user", None)

    except Exception as e:
        print("AUTH SESSION ERROR:", type(e).__name__)
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if not auth_user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if response and next_access_token and next_refresh_token:
        set_auth_cookies(
            response,
            next_access_token,
            next_refresh_token,
        )

    user_response = (
        service_supabase.table("users")
        .select("*")
        .eq("auth_id", auth_user.id)
        .single()
        .execute()
    )

    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    return auth_user, user_response.data


def require_system_admin(request: Request, response: Response | None = None):
    auth_user, user_data = get_authenticated_user_row(request, response)
    user_type = str(user_data.get("user_type") or "user").strip().lower()

    if user_type != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required")

    return auth_user, user_data
