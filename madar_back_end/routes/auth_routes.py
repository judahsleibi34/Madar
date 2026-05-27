from fastapi import APIRouter, HTTPException, Response, Request
from database import supabase
from classes import SignUpRequest, LogIn
from services.auth_service import (
    set_auth_cookies,
    delete_auth_cookies,
    build_user_payload,
    get_authenticated_user_row,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


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
            },
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
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_response = supabase.table("users").select("*").eq(
            "auth_id", auth_response.user.id
        ).single().execute()

        set_auth_cookies(
            response,
            auth_response.session.access_token,
            auth_response.session.refresh_token,
        )

        return {
            "message": "User is logged in",
            "user": build_user_payload(user_response.data),
        }

    except HTTPException:
        raise
    except Exception as e:
        print("LOGIN ERROR:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid email or password")


@router.get("/user_status")
def user_status(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        return {
            "logged_in": True,
            "user": build_user_payload(user_data),
        }

    except Exception as e:
        print("ME ERROR:", repr(e))
        return {
            "logged_in": False,
            "user": None,
        }


@router.post("/log_out")
def log_out(response: Response):
    delete_auth_cookies(response)

    return {
        "message": "Logged out successfully"
    }