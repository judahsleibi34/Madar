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
        response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {
                "data": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
            },
        })

        if not response.user:
            raise HTTPException(
                status_code=400,
                detail="Could not create user"
            )

        return {
            "message": "Signup request sent successfully",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.post("/login")
def login(user: LogIn):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password,
        })

        if not response.user or not response.session:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        return {
            "message": "User is logged in",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
            },
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
            }
        }

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )