from fastapi import APIRouter, HTTPException, Request, Response

from database import service_supabase, supabase
from classes import SignUpRequest, LogIn, UpdatePassword
from services.rate_limit_service import enforce_auth_rate_limit
from services.auth_service import (
    set_auth_cookies,
    delete_auth_cookies,
    build_user_payload,
    get_authenticated_user_row,
)
from services.billing_service import get_billing_summary_for_tenant

router = APIRouter(prefix="/auth", tags=["Auth"])


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def get_local_user_by_email(clean_email: str):
    if not clean_email:
        return None

    result = (
        service_supabase.table("users")
        .select("*")
        .eq("email", clean_email)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def get_local_user_by_auth_id(auth_id: str):
    if not auth_id:
        return None

    result = (
        service_supabase.table("users")
        .select("*")
        .eq("auth_id", str(auth_id))
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def assert_email_is_available(clean_email: str, allowed_auth_id: str | None = None):
    existing_user = get_local_user_by_email(clean_email)

    if not existing_user:
        return

    existing_auth_id = str(existing_user.get("auth_id") or "")

    if allowed_auth_id and existing_auth_id == str(allowed_auth_id):
        return

    raise HTTPException(
        status_code=409,
        detail="Email is already registered",
    )


def get_auth_error_message(error: Exception) -> str:
    raw_message = str(error).lower()

    if "already" in raw_message and "registered" in raw_message:
        return "Email is already registered"

    if "already" in raw_message and "exists" in raw_message:
        return "Email is already registered"

    if "duplicate" in raw_message:
        return "Email is already registered"

    if "unique" in raw_message:
        return "Email is already registered"

    return ""


@router.post("/signup")
def signup(user: SignUpRequest, request: Request):
    auth_user_id = None
    tenant_id = None
    signup_complete = False

    try:
        clean_email = normalize_email(user.email)
        first_name = user.first_name.strip()
        last_name = user.last_name.strip()
        owner_name = f"{first_name} {last_name}".strip()

        if not clean_email:
            raise HTTPException(status_code=400, detail="Email is required")

        enforce_auth_rate_limit(request, "signup", clean_email)

        if not first_name or not last_name:
            raise HTTPException(
                status_code=400,
                detail="First name and last name are required",
            )

        if not user.password or len(user.password.strip()) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters",
            )

        assert_email_is_available(clean_email)

        try:
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

        except Exception as auth_create_error:
            print("SIGNUP AUTH CREATE ERROR:", repr(auth_create_error))
            friendly_message = get_auth_error_message(auth_create_error)

            if friendly_message:
                raise HTTPException(status_code=409, detail=friendly_message)

            raise HTTPException(status_code=400, detail="Could not create user")

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Could not create user")

        auth_user_id = str(auth_response.user.id)

        assert_email_is_available(clean_email, allowed_auth_id=auth_user_id)

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

        try:
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

        except Exception as user_insert_error:
            print("SIGNUP USER INSERT ERROR:", repr(user_insert_error))
            friendly_message = get_auth_error_message(user_insert_error)

            if friendly_message:
                raise HTTPException(status_code=409, detail=friendly_message)

            raise HTTPException(status_code=400, detail="Could not create account")

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
def login(user: LogIn, response: Response, request: Request):
    try:
        clean_email = normalize_email(user.email)

        if not clean_email:
            raise HTTPException(status_code=400, detail="Email is required")

        enforce_auth_rate_limit(request, "login", clean_email)

        auth_response = supabase.auth.sign_in_with_password(
            {
                "email": clean_email,
                "password": user.password,
            }
        )

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        auth_user_id = str(auth_response.user.id)
        local_user = get_local_user_by_auth_id(auth_user_id)

        if not local_user:
            raise HTTPException(
                status_code=404,
                detail="Local user profile not found",
            )

        local_email = normalize_email(local_user.get("email"))

        if local_email != clean_email:
            existing_email_user = get_local_user_by_email(clean_email)

            if (
                existing_email_user
                and str(existing_email_user.get("auth_id")) != auth_user_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Email is already linked to another user",
                )

            try:
                update_response = (
                    service_supabase.table("users")
                    .update({"email": clean_email})
                    .eq("auth_id", auth_user_id)
                    .execute()
                )

            except Exception as email_sync_error:
                print("LOGIN EMAIL SYNC ERROR:", repr(email_sync_error))
                raise HTTPException(
                    status_code=409,
                    detail="Could not sync login email",
                )

            if not update_response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Could not sync user email",
                )

            local_user = update_response.data[0]

        set_auth_cookies(
            response,
            auth_response.session.access_token,
            auth_response.session.refresh_token,
        )

        return {
            "message": "User is logged in",
            "user": build_user_payload(local_user),
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
        user_payload = build_user_payload(user_data)
        user_payload.update(get_billing_summary_for_tenant(user_data.get("tenant_id")))

        return {
            "logged_in": True,
            "user": user_payload,
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

        clean_email = normalize_email(user_data.get("email"))
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
