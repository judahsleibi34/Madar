from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from classes import ContactMessage, SignUpRequest, LogIn
from database import supabase

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://madar-judah-sleibis-projects.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def madar_health():
    return {"message": "All working"}


@app.post("/contact")
def create_contact_message(contact: ContactMessage):
    return {
        "status": "received",
        "data": contact
    }


@app.post("/signup")
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
    

@app.post("/login")
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

@app.post("/forgot-password")
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