import os
from fastapi import HTTPException, Response, Request
from database import service_supabase, supabase

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
ACCESS_COOKIE_MAX_AGE = 60 * 60 * 24 * 7
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="madar_access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_COOKIE_MAX_AGE,
    )

    response.set_cookie(
        key="madar_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def delete_auth_cookies(response: Response):
    response.delete_cookie(
        key="madar_access_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )

    response.delete_cookie(
        key="madar_refresh_token",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )


def build_user_payload(user_data):
    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or "Admin User"

    return {
        "id": user_data.get("id"),
        "auth_id": user_data.get("auth_id"),
        "first_name": first_name,
        "last_name": last_name,
        "name": full_name,
        "email": user_data.get("email"),
        "phone": user_data.get("phone") or "",
        "avatar": user_data.get("avatar") or user_data.get("avatar_url") or "",
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at"),
    }


def get_authenticated_user_row(request: Request, response: Response | None = None):
    access_token = request.cookies.get("madar_access_token")
    refresh_token = request.cookies.get("madar_refresh_token")

    if not access_token and not refresh_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    try:
        if access_token and refresh_token:
            auth_response = supabase.auth.set_session(access_token, refresh_token)
            auth_user = auth_response.user

            if response and auth_response.session:
                set_auth_cookies(
                    response,
                    auth_response.session.access_token,
                    auth_response.session.refresh_token,
                )

        elif refresh_token:
            auth_response = supabase.auth.refresh_session(refresh_token)
            auth_user = auth_response.user

            if response and auth_response.session:
                set_auth_cookies(
                    response,
                    auth_response.session.access_token,
                    auth_response.session.refresh_token,
                )

        else:
            auth_response = supabase.auth.get_user(access_token)
            auth_user = getattr(auth_response, "user", None)

    except Exception as e:
        print("AUTH SESSION ERROR:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if not auth_user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user_response = service_supabase.table("users").select("*").eq(
        "auth_id", auth_user.id
    ).single().execute()

    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    return auth_user, user_response.data
