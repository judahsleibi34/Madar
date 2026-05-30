from fastapi import APIRouter, HTTPException, Request, Response

from database import service_supabase, supabase
from classes import SignUpRequest, LogIn, UpdatePassword
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

        auth_response = service_supabase.auth.admin.create_user(
            {
                "email": clean_email,
                "password": user.password,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                },
            }
        )

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Could not create user")

        auth_user_id = str(auth_response.user.id)

        tenant_insert = (
            service_supabase.table("tenants")
            .insert(
                {
                    "brand_name": "",
                    "owner_name": owner_name,
                }
            )
            .execute()
        )

        if not tenant_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")

        tenant_id = tenant_insert.data[0]["tenant_id"]

        user_insert = (
            service_supabase.table("users")
            .insert(
                {
                    "auth_id": auth_user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": clean_email,
                    "tenant_id": tenant_id,
                }
            )
            .execute()
        )

        if not user_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")

        local_user = user_insert.data[0]

        service_supabase.table("tenant_memberships").insert(
            {
                "tenant_id": tenant_id,
                "user_id": local_user["id"],
                "auth_id": auth_user_id,
                "role": "owner",
                "status": "active",
            }
        ).execute()

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

        auth_response = supabase.auth.sign_in_with_password(
            {
                "email": clean_email,
                "password": user.password,
            }
        )

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_response = (
            service_supabase.table("users")
            .select("*")
            .eq("auth_id", auth_response.user.id)
            .single()
            .execute()
        )

        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

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

    except HTTPException:
        return {
            "logged_in": False,
            "user": None,
        }

    except Exception as e:
        print("USER STATUS ERROR:", repr(e))
        return {
            "logged_in": False,
            "user": None,
        }


@router.put("/password/change")
def change_password(
    payload: UpdatePassword,
    request: Request,
    response: Response,
):
    try:
        auth_user, user_data = get_authenticated_user_row(request, response)

        clean_email = (user_data.get("email") or "").strip().lower()
        current_password = payload.current_password.strip()
        new_password = payload.new_password.strip()

        if not clean_email:
            raise HTTPException(status_code=400, detail="User email not found")

        if not current_password or not new_password:
            raise HTTPException(
                status_code=400,
                detail="Current password and new password are required",
            )

        if len(new_password) < 8:
            raise HTTPException(
                status_code=400,
                detail="New password must be at least 8 characters",
            )

        if current_password == new_password:
            raise HTTPException(
                status_code=400,
                detail="New password must be different from current password",
            )

        try:
            verify_response = supabase.auth.sign_in_with_password(
                {
                    "email": clean_email,
                    "password": current_password,
                }
            )

            if not verify_response.user:
                raise HTTPException(
                    status_code=401,
                    detail="Current password is incorrect",
                )

        except HTTPException:
            raise

        except Exception as verify_error:
            print("PASSWORD VERIFY ERROR:", repr(verify_error))
            raise HTTPException(
                status_code=401,
                detail="Current password is incorrect",
            )

        try:
            service_supabase.auth.admin.update_user_by_id(
                str(auth_user.id),
                {
                    "password": new_password,
                },
            )

        except Exception as update_error:
            print("PASSWORD UPDATE ERROR:", repr(update_error))
            raise HTTPException(
                status_code=500,
                detail="Could not update password",
            )

        try:
            new_session = supabase.auth.sign_in_with_password(
                {
                    "email": clean_email,
                    "password": new_password,
                }
            )

            if new_session.session:
                set_auth_cookies(
                    response,
                    new_session.session.access_token,
                    new_session.session.refresh_token,
                )

        except Exception as session_error:
            print("PASSWORD SESSION REFRESH ERROR:", repr(session_error))

        return {
            "message": "Password updated successfully",
        }

    except HTTPException:
        raise

    except Exception as e:
        print("CHANGE PASSWORD ERROR:", repr(e))
        raise HTTPException(
            status_code=500,
            detail="Could not update password",
        )


@router.post("/log_out")
def log_out(response: Response):
    delete_auth_cookies(response)

    return {
        "message": "Logged out successfully",
    }