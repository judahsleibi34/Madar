from fastapi import APIRouter, HTTPException, Response, Request
from database import supabase
from classes import SignUpRequest, LogIn, UserProfileUpdate
import os

router = APIRouter()

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
        raise HTTPException(
            status_code=401,
            detail="Not logged in"
        )

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
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )

    if not auth_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )

    user_response = supabase.table("users").select("*").eq(
        "auth_id", auth_user.id
    ).single().execute()

    if not user_response.data:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return auth_user, user_response.data


@router.post("/signup")
def signup(user: SignUpRequest):
    try:
        clean_email = user.email.strip().lower()

        response = supabase.auth.sign_up({
            "email": clean_email,
            "password": user.password,
            "options": {
                "data": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
            },
        })

        if not response.user:
            raise HTTPException(status_code=400, detail="Could not create user")

        user_insert = supabase.table("users").insert({
            "auth_id": str(response.user.id),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": clean_email,
        }).execute()

        return {
            "message": "Signup request sent successfully",
            "user": {
                "auth_id": response.user.id,
                "local_id": user_insert.data[0]["id"] if user_insert.data else None,
                "email": clean_email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }

    except Exception as e:
        print("SIGNUP ERROR:", repr(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(user: LogIn, response: Response):
    try:
        clean_email = user.email.strip().lower()

        auth_response = supabase.auth.sign_in_with_password({
            "email": clean_email,
            "password": user.password,
        })

        if not auth_response.user or not auth_response.session:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        user_response = supabase.table("users").select(
            "*"
        ).eq(
            "auth_id", auth_response.user.id
        ).single().execute()

        access_token = auth_response.session.access_token
        refresh_token = auth_response.session.refresh_token

        set_auth_cookies(response, access_token, refresh_token)

        return {
            "message": "User is logged in",
            "user": build_user_payload(user_response.data)
        }

    except HTTPException:
        raise
    except Exception as e:
        print("LOGIN ERROR:", repr(e))
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )


@router.get("/user_status")
def user_status(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        return {
            "logged_in": True,
            "user": build_user_payload(user_data)
        }

    except Exception as e:
        print("ME ERROR:", repr(e))
        return {
            "logged_in": False,
            "user": None
        }


@router.post("/log_out")
def log_out(response: Response):
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

    return {
        "message": "Logged out successfully"
    }

@router.post("/user_info")
def user_info(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        return {
            "success": True,
            "user": build_user_payload(user_data)
        }

    except HTTPException:
        raise

    except Exception as e:
        print("USER INFO ERROR:", repr(e))
        raise HTTPException(
            status_code=500,
            detail="Could not fetch user info"
        )


@router.put("/user_profile")
def update_user_profile(profile: UserProfileUpdate, request: Request, response: Response):
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
                "user": build_user_payload(user_data)
            }

        update_response = supabase.table("users").update(update_payload).eq(
            "auth_id", user_data.get("auth_id")
        ).execute()

        updated_user = update_response.data[0] if update_response.data else {
            **user_data,
            **update_payload,
        }

        return {
            "success": True,
            "message": "User profile updated",
            "user": build_user_payload(updated_user)
        }

    except HTTPException:
        raise

    except Exception as e:
        print("USER PROFILE UPDATE ERROR:", repr(e))
        raise HTTPException(
            status_code=500,
            detail="Could not update user profile"
        )

