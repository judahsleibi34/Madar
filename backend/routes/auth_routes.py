import logging

from fastapi import APIRouter, HTTPException, Request, Response

from database import service_supabase, supabase
from classes import SignUpRequest, OnboardingSignupRequest, LogIn, UpdatePassword
from services.rate_limit_service import enforce_auth_rate_limit
from services.auth_service import (
    set_auth_cookies,
    delete_auth_cookies,
    build_user_payload,
    get_authenticated_user_row,
)
from services.billing_service import get_billing_summary_for_tenant
from services.onboarding_service import create_onboarded_tenant
from services.request_security import CSRF_HEADER_NAME, create_csrf_token, set_csrf_cookie

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


def ensure_csrf_token(request: Request, response: Response) -> str:
    csrf_token = response.headers.get(CSRF_HEADER_NAME)

    if csrf_token:
        return csrf_token

    csrf_token = create_csrf_token(
        access_token=request.cookies.get("madar_access_token"),
        refresh_token=request.cookies.get("madar_refresh_token"),
    )
    set_csrf_cookie(response, csrf_token)
    return csrf_token


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
            logger.warning(
                "auth.signup.auth_create_failed",
                extra={"email": clean_email, "error_type": type(auth_create_error).__name__},
            )
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
            logger.warning(
                "auth.signup.user_insert_failed",
                extra={"auth_id": auth_user_id, "tenant_id": tenant_id, "error_type": type(user_insert_error).__name__},
            )
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
        logger.warning("auth.signup.failed", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=400, detail="Could not create account")

    finally:
        if not signup_complete and auth_user_id:
            try:
                service_supabase.table("tenant_memberships").delete().eq(
                    "auth_id", auth_user_id
                ).execute()
            except Exception as cleanup_error:
                logger.warning("auth.signup.membership_cleanup_failed", extra={"auth_id": auth_user_id, "error_type": type(cleanup_error).__name__})

            try:
                service_supabase.table("users").delete().eq(
                    "auth_id", auth_user_id
                ).execute()
            except Exception as cleanup_error:
                logger.warning("auth.signup.user_cleanup_failed", extra={"auth_id": auth_user_id, "error_type": type(cleanup_error).__name__})

        if not signup_complete and tenant_id is not None:
            try:
                service_supabase.table("tenants").delete().eq(
                    "tenant_id", tenant_id
                ).execute()
            except Exception as cleanup_error:
                logger.warning("auth.signup.tenant_cleanup_failed", extra={"tenant_id": tenant_id, "error_type": type(cleanup_error).__name__})

        if not signup_complete and auth_user_id:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception as cleanup_error:
                logger.warning("auth.signup.auth_cleanup_failed", extra={"auth_id": auth_user_id, "error_type": type(cleanup_error).__name__})


@router.post("/signup/onboard")
def signup_onboard(payload: OnboardingSignupRequest, request: Request):
    clean_email = normalize_email(payload.email)

    if not clean_email:
        raise HTTPException(status_code=400, detail="Email is required")

    enforce_auth_rate_limit(request, "signup", clean_email)
    assert_email_is_available(clean_email)

    return create_onboarded_tenant(
        supabase_client=service_supabase,
        payload=payload,
    )


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
                logger.warning(
                    "auth.login.email_sync_failed",
                    extra={"auth_id": auth_user_id, "error_type": type(email_sync_error).__name__},
                )
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

        csrf_token = set_auth_cookies(
            response,
            auth_response.session.access_token,
            auth_response.session.refresh_token,
        )

        logger.info(
            "auth.login.success",
            extra={"user_id": local_user.get("id"), "tenant_id": local_user.get("tenant_id")},
        )

        return {
            "message": "User is logged in",
            "user": build_user_payload(local_user),
            "csrf_token": csrf_token,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("auth.login.failed", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=401, detail="Invalid email or password")


@router.get("/user_status")
def user_status(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)
        user_payload = build_user_payload(user_data)
        user_payload.update(get_billing_summary_for_tenant(user_data.get("tenant_id")))
        csrf_token = ensure_csrf_token(request, response)

        return {
            "logged_in": True,
            "user": user_payload,
            "csrf_token": csrf_token,
        }

    except HTTPException:
        return {
            "logged_in": False,
            "user": None,
        }

    except Exception as e:
        logger.warning("auth.user_status.failed", extra={"error_type": type(e).__name__})
        return {
            "logged_in": False,
            "user": None,
        }


@router.post("/refresh")
def refresh_session(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)
        user_payload = build_user_payload(user_data)
        user_payload.update(get_billing_summary_for_tenant(user_data.get("tenant_id")))

        return {
            "logged_in": True,
            "user": user_payload,
        }

    except HTTPException as error:
        delete_auth_cookies(response)
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again.",
        ) from error

    except Exception as error:
        logger.warning("auth.refresh.failed", extra={"error_type": type(error).__name__})
        delete_auth_cookies(response)
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again.",
        )


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
            logger.warning("auth.password.verify_failed", extra={"user_id": user_data.get("id"), "error_type": type(verify_error).__name__})
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
            logger.warning("auth.password.update_failed", extra={"user_id": user_data.get("id"), "error_type": type(update_error).__name__})
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
            logger.warning("auth.password.session_refresh_failed", extra={"user_id": user_data.get("id"), "error_type": type(session_error).__name__})

        return {
            "message": "Password updated successfully",
            "csrf_token": ensure_csrf_token(request, response),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("auth.password.change_failed", extra={"error_type": type(e).__name__})
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
