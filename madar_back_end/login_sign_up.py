from fastapi import APIRouter, HTTPException
from database import supabase
from classes import SignUpRequest, LogIn
router = APIRouter()


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
def login(user: LogIn):
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

        return {
            "message": "User is logged in",
            "user": {
                "id": user_response.data["id"],
                "auth_id": user_response.data["auth_id"],
                "email": user_response.data["email"],
                "first_name": user_response.data["first_name"],
                "last_name": user_response.data["last_name"],
            },
            "session": {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "expires_at": auth_response.session.expires_at,
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