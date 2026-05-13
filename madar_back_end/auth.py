from fastapi import APIRouter, HTTPException, Response, Request
from database import supabase
from classes import SignUpRequest, LogIn
import os

router = APIRouter()

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")


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
            "id, auth_id, first_name, last_name, email"
        ).eq(
            "auth_id", auth_response.user.id
        ).single().execute()

        access_token = auth_response.session.access_token
        refresh_token = auth_response.session.refresh_token

        response.set_cookie(
            key="madar_access_token",
            value=access_token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=60 * 60 * 24 * 7,
        )

        response.set_cookie(
            key="madar_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=60 * 60 * 24 * 30,
        )

        return {
            "message": "User is logged in",
            "user": {
                "id": user_response.data["id"],
                "auth_id": user_response.data["auth_id"],
                "email": user_response.data["email"],
                "first_name": user_response.data["first_name"],
                "last_name": user_response.data["last_name"],
            }
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
def user_status(request: Request):
    access_token = request.cookies.get("madar_access_token")

    if not access_token:
        return {
            "logged_in": False,
            "user": None
        }

    try:
        auth_user = supabase.auth.get_user(access_token)

        if not auth_user or not getattr(auth_user, "user", None):
            return {
                "logged_in": False,
                "user": None
            }

        user_response = supabase.table("users").select(
            "id, auth_id, first_name, last_name, email"
        ).eq(
            "auth_id", auth_user.user.id
        ).single().execute()

        return {
            "logged_in": True,
            "user": {
                "id": user_response.data["id"],
                "auth_id": user_response.data["auth_id"],
                "email": user_response.data["email"],
                "first_name": user_response.data["first_name"],
                "last_name": user_response.data["last_name"],
            }
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