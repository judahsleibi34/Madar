from fastapi import APIRouter, HTTPException, Response, Request
from database import service_supabase, supabase
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
    auth_user_id = None
    tenant_id = None
    signup_complete = False

    try:
        clean_email = user.email.strip().lower()
        first_name = user.first_name.strip()
        last_name = user.last_name.strip()
        owner_name = f"{first_name} {last_name}".strip()

        auth_response = service_supabase.auth.admin.create_user({
            "email": clean_email,
            "password": user.password,
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
            },
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Could not create user")

        auth_user_id = str(auth_response.user.id)

        tenant_insert = service_supabase.table("tenants").insert({
            "brand_name": "",
            "owner_name": owner_name,
        }).execute()

        if not tenant_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")

        tenant_id = tenant_insert.data[0]["tenant_id"]

        user_insert = service_supabase.table("users").insert({
            "auth_id": auth_user_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": clean_email,
            "tenant_id": tenant_id,
        }).execute()

        if not user_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")

        local_user = user_insert.data[0]

        service_supabase.table("tenant_memberships").insert({
            "tenant_id": tenant_id,
            "user_id": local_user["id"],
            "auth_id": auth_user_id,
            "role": "owner",
            "status": "active",
        }).execute()

        signup_complete = True

        return {
            "message": "Signup request sent successfully",
            "user": {
                "auth_id": auth_user_id,
                "local_id": local_user["id"],
                "tenant_id": tenant_id,
                "email": clean_email,
                "first_name": first_name,
                "last_name": last_name,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        print("SIGNUP ERROR:", repr(e))
        raise HTTPException(status_code=400, detail="Could not create account")
    finally:
        if not signup_complete and auth_user_id:
            try:
                service_supabase.table("tenant_memberships").delete().eq(
                    "auth_id", auth_user_id
                ).execute()
            except Exception as cleanup_error:
                print("SIGNUP MEMBERSHIP CLEANUP ERROR:", repr(cleanup_error))

            try:
                service_supabase.table("users").delete().eq(
                    "auth_id", auth_user_id
                ).execute()
            except Exception as cleanup_error:
                print("SIGNUP USER CLEANUP ERROR:", repr(cleanup_error))

        if not signup_complete and tenant_id is not None:
            try:
                service_supabase.table("tenants").delete().eq(
                    "tenant_id", tenant_id
                ).execute()
            except Exception as cleanup_error:
                print("SIGNUP TENANT CLEANUP ERROR:", repr(cleanup_error))

        if not signup_complete and auth_user_id:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception as cleanup_error:
                print("SIGNUP AUTH CLEANUP ERROR:", repr(cleanup_error))


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

        user_response = service_supabase.table("users").select("*").eq(
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
