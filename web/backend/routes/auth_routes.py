import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, UUID4

from database import service_supabase, supabase
from classes import EmailVerificationResendRequest, SignUpRequest, LogIn, UpdatePassword
from services.rate_limit_service import enforce_auth_rate_limit
from services.auth_service import (
    set_auth_cookies,
    delete_auth_cookies,
    build_user_payload,
    get_authenticated_user_row,
    auth_user_email_is_verified,
    mark_local_email_verified,
    normalize_user_type,
    SessionRefreshUnavailable,
    revoke_verified_auth_session,
)
from services.account_lifecycle_service import (
    ACTIVE_ACCOUNT_STATUS,
    EXPIRED_PENDING_ACCOUNT_STATUS,
    PENDING_ACCOUNT_STATUS,
    effective_account_status,
    is_platform_account,
    synchronize_verified_account,
)
from services.api_errors import api_error, error_detail
from services.billing_service import get_billing_summary_for_tenant
from services.onboarding_service import (
    ensure_subdomain_available,
    validate_onboarding_subdomain,
    validate_optional_business_text,
    validate_person_name,
)
from services.request_security import CSRF_HEADER_NAME, create_csrf_token, set_csrf_cookie
from services.mfa_login_service import (
    create_pending_mfa_client,
    is_admin_mfa_login_enforcement_enabled,
    set_pending_mfa_cookie,
    verified_totp_factors_for_client,
)
from services.audit_service import record_security_event
from services.user_security_settings_service import get_user_security_settings
from services.frontend_url import resolve_frontend_url
from services.identity_service import auth_value, canonical_auth_email
from services.password_policy import validate_password
from services.pending_verification_context import (
    delete_pending_verification_cookie,
    read_pending_verification_context,
    set_pending_verification_cookie,
)
from services.notification_service import (
    revoke_all_web_push_subscriptions,
    revoke_web_push_subscription,
)
from services.installation_service import revoke_installation_push_bindings
from services.email_verification_service import (
    GENERIC_RESEND_MESSAGE,
    mask_email,
    pending_account_is_expired,
    record_verification_result,
    resend_available_after,
    send_verification_email,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)
FRONTEND_URL = resolve_frontend_url()
CURRENT_TERMS_VERSION = "2026-07-13"


class LogoutRequest(BaseModel):
    installation_id: UUID4 | None = None
    push_endpoint: str | None = Field(default=None, max_length=2000)


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


def get_auth_user_by_email(clean_email: str):
    if not clean_email:
        return None

    page = 1
    per_page = 1000

    while True:
        try:
            users = service_supabase.auth.admin.list_users(page=page, per_page=per_page)
        except Exception as error:
            logger.warning(
                "auth.signup.auth_email_lookup_failed",
                extra={"error_type": type(error).__name__},
            )
            raise HTTPException(
                status_code=500,
                detail="Could not verify email availability",
            ) from error

        for auth_user in users:
            user_email = normalize_email(getattr(auth_user, "email", ""))

            if user_email == clean_email:
                return auth_user

        if len(users) < per_page:
            return None

        page += 1


def get_auth_user_by_id(auth_id: str):
    if not auth_id:
        return None
    response = service_supabase.auth.admin.get_user_by_id(str(auth_id))
    return auth_value(response, "user") or response


def get_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def get_login_audit_user(clean_email: str):
    try:
        return get_local_user_by_email(clean_email)
    except Exception as audit_lookup_error:
        logger.warning(
            "auth.login.audit_user_lookup_failed",
            extra={"error_type": type(audit_lookup_error).__name__},
        )
        return None


def assert_email_is_available(clean_email: str, allowed_auth_id: str | None = None):
    existing_user = get_local_user_by_email(clean_email)

    if existing_user:
        existing_auth_id = str(existing_user.get("auth_id") or "")

        if allowed_auth_id and existing_auth_id == str(allowed_auth_id):
            return

        raise HTTPException(
            status_code=409,
            detail="Email is already registered",
        )

    existing_auth_user = get_auth_user_by_email(clean_email)

    if not existing_auth_user:
        return

    existing_auth_user_id = str(getattr(existing_auth_user, "id", "") or "")

    if allowed_auth_id and existing_auth_user_id == str(allowed_auth_id):
        return

    raise HTTPException(
        status_code=409,
        detail="Email is already registered",
    )


def recover_or_remove_orphaned_auth_user(clean_email: str, password: str):
    """Resolve an Auth identity left without an application profile.

    Unverified identities can be safely recreated. Verified identities are
    reused only after the supplied password proves ownership.
    """
    if get_local_user_by_email(clean_email):
        return None

    auth_user = get_auth_user_by_email(clean_email)

    if not auth_user:
        return None

    # Supabase User objects expose email_confirmed_at. Do not make assumptions
    # for unknown response shapes, and never recycle a verified identity.
    missing = object()
    email_confirmed_at = getattr(auth_user, "email_confirmed_at", missing)

    auth_user_id = str(getattr(auth_user, "id", "") or "")

    if not auth_user_id:
        return None

    if email_confirmed_at is missing or email_confirmed_at is not None:
        try:
            auth_response = supabase.auth.sign_in_with_password(
                {"email": clean_email, "password": password}
            )
            authenticated_user = getattr(auth_response, "user", None)
            authenticated_user_id = str(getattr(authenticated_user, "id", "") or "")
        except Exception:
            authenticated_user_id = ""

        if authenticated_user_id != auth_user_id:
            raise HTTPException(
                status_code=409,
                detail="Email is already registered",
            )

        logger.info(
            "auth.signup.orphaned_verified_auth_user_recovered",
            extra={"auth_id": auth_user_id},
        )
        return auth_user

    try:
        service_supabase.auth.admin.delete_user(auth_user_id)
        logger.info(
            "auth.signup.orphaned_auth_user_removed",
            extra={"auth_id": auth_user_id},
        )
    except Exception as error:
        logger.warning(
            "auth.signup.orphaned_auth_user_cleanup_failed",
            extra={"auth_id": auth_user_id, "error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=500,
            detail="Could not prepare account registration",
        ) from error

    return None


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
def signup(user: SignUpRequest, request: Request, response: Response):
    auth_user_id = None
    auth_user_created_this_request = False
    recovered_verified_auth_user = False
    signup_complete = False

    try:
        clean_email = normalize_email(user.email)
        first_name = validate_person_name(user.first_name, "First name")
        last_name = validate_person_name(user.last_name, "Last name")
        business_name = validate_optional_business_text(
            user.business_name,
            "Business name",
        )
        business_type = validate_optional_business_text(
            user.business_type,
            "Business type",
        )
        requested_subdomain = (
            validate_onboarding_subdomain(user.subdomain)
            if str(user.subdomain or "").strip()
            else ""
        )

        if user.terms_accepted is not True:
            raise api_error(
                400,
                "terms_acceptance_required",
                "You must agree to the Terms and Conditions to create an account.",
            )

        if not clean_email:
            raise HTTPException(status_code=400, detail="Email is required")

        enforce_auth_rate_limit(request, "signup_ip")
        enforce_auth_rate_limit(request, "signup", clean_email)

        password = validate_password(user.password)

        auth_user = recover_or_remove_orphaned_auth_user(clean_email, password)
        recovered_verified_auth_user = bool(auth_user)
        auth_user_id = (
            str(getattr(auth_user, "id", "") or "")
            if recovered_verified_auth_user
            else None
        )
        assert_email_is_available(clean_email, allowed_auth_id=auth_user_id)
        if requested_subdomain:
            ensure_subdomain_available(service_supabase, requested_subdomain)

        if not recovered_verified_auth_user:
            try:
                # Create the provider identity without triggering an early email. The
                # confirmation is sent only after local pending state is durable.
                auth_response = service_supabase.auth.admin.create_user(
                    {
                        "email": clean_email,
                        "password": password,
                        "email_confirm": False,
                        "user_metadata": {
                            "first_name": first_name,
                            "last_name": last_name,
                        },
                    }
                )

            except Exception as auth_create_error:
                logger.warning(
                    "auth.signup.auth_create_failed",
                    extra={"error_type": type(auth_create_error).__name__},
                )
                friendly_message = get_auth_error_message(auth_create_error)

                if friendly_message:
                    raise HTTPException(status_code=409, detail=friendly_message)

                raise HTTPException(status_code=400, detail="Could not create user")

            if not auth_response.user:
                raise HTTPException(status_code=400, detail="Could not create user")

            auth_user = auth_response.user
            auth_user_id = str(auth_response.user.id)
            auth_user_created_this_request = True

        assert_email_is_available(clean_email, allowed_auth_id=auth_user_id)

        try:
            user_insert = (
                service_supabase.table("users")
                .insert(
                    {
                        "auth_id": auth_user_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": clean_email,
                        "tenant_id": None,
                        "account_kind": "platform",
                        "email_verified": False,
                        "email_verified_at": None,
                        "account_status": PENDING_ACCOUNT_STATUS,
                        "verification_required_at": datetime.now(timezone.utc).isoformat(),
                        "pending_account_expires_at": (
                            datetime.now(timezone.utc) + timedelta(days=14)
                        ).isoformat(),
                        "terms_accepted_at": datetime.now(timezone.utc).isoformat(),
                        "terms_version": CURRENT_TERMS_VERSION,
                    }
                )
                .execute()
            )

        except Exception as user_insert_error:
            logger.warning(
                "auth.signup.user_insert_failed",
                extra={"auth_id": auth_user_id, "error_type": type(user_insert_error).__name__},
            )
            friendly_message = get_auth_error_message(user_insert_error)

            if friendly_message:
                raise HTTPException(status_code=409, detail=friendly_message)

            raise HTTPException(status_code=400, detail="Could not create account")

        if not user_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")

        local_user = user_insert.data[0]

        service_supabase.table("pending_account_onboarding").insert(
            {
                "user_id": local_user["id"],
                "auth_id": auth_user_id,
                "business_name": business_name or None,
                "business_type": business_type or None,
                "requested_subdomain": requested_subdomain or None,
                "selected_plan": user.selected_plan,
                "status": "pending",
            }
        ).execute()

        delivery = {"retry_after": 0}
        if recovered_verified_auth_user:
            local_user, activated = synchronize_verified_account(auth_user, local_user)
            record_verification_result(
                auth_user=auth_user,
                user_data=local_user,
                request=request,
                succeeded=True,
            )
            record_security_event(
                request=request,
                tenant_id=local_user.get("tenant_id"),
                actor_user_id=local_user["id"],
                action="auth.email_verification_succeeded",
                target_type="user",
                target_id=local_user["id"],
                metadata={"provisioned": activated, "reason": "orphan_recovery"},
            )
        else:
            delivery = send_verification_email(
                auth_user=auth_user,
                user_data=local_user,
                request=request,
                frontend_url=FRONTEND_URL,
            )
            if not delivery.get("sent"):
                raise api_error(
                    503,
                    "email_verification_delivery_failed",
                    "The account could not be created because the verification email was not sent.",
                )

            set_pending_verification_cookie(
                response,
                auth_id=auth_user_id,
                user_id=local_user["id"],
            )
            record_security_event(
                request=request,
                actor_user_id=local_user["id"],
                action="auth.email_verification_sent",
                target_type="user",
                target_id=local_user["id"],
                metadata={"reason": "signup"},
            )

        signup_complete = True

        return {
            "message": (
                "Account created. You can now log in."
                if recovered_verified_auth_user
                else "Account created. Please verify your email before logging in."
            ),
            "requires_email_verification": not recovered_verified_auth_user,
            "user": {
                "auth_id": auth_user_id,
                "local_id": local_user["id"],
                "tenant_id": local_user.get("tenant_id"),
                "email": clean_email,
                "first_name": first_name,
                "last_name": last_name,
                "account_status": effective_account_status(local_user),
            },
            "resend_available_after": delivery.get("retry_after", 60),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("auth.signup.failed", extra={"error_type": type(e).__name__})
        raise HTTPException(status_code=400, detail="Could not create account")

    finally:
        if not signup_complete and auth_user_id:
            try:
                service_supabase.table("pending_account_onboarding").delete().eq(
                    "auth_id", auth_user_id
                ).execute()
            except Exception as cleanup_error:
                logger.warning("auth.signup.pending_cleanup_failed", extra={"auth_id": auth_user_id, "error_type": type(cleanup_error).__name__})

            try:
                service_supabase.table("users").delete().eq(
                    "auth_id", auth_user_id
                ).execute()
            except Exception as cleanup_error:
                logger.warning("auth.signup.user_cleanup_failed", extra={"auth_id": auth_user_id, "error_type": type(cleanup_error).__name__})

        if not signup_complete and auth_user_id and auth_user_created_this_request:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception as cleanup_error:
                logger.warning("auth.signup.auth_cleanup_failed", extra={"auth_id": auth_user_id, "error_type": type(cleanup_error).__name__})


@router.get("/email-verification/status")
def email_verification_status(request: Request, response: Response):
    """Resolve only a signed pending context or provider access token."""
    context = read_pending_verification_context(request)
    bearer_token = get_bearer_token(request)

    if not context and not bearer_token:
        return {
            "state": "unknown",
            "account_status": None,
            "resend_available_after": 0,
        }

    try:
        if bearer_token:
            auth_response = supabase.auth.get_user(bearer_token)
            auth_user = auth_value(auth_response, "user")
        else:
            auth_user = get_auth_user_by_id(str(context["auth_id"]))

        auth_id = str(auth_value(auth_user, "id") or "")
        if not auth_user or not auth_id:
            return {
                "state": "unknown",
                "account_status": None,
                "resend_available_after": 0,
            }
        if context and auth_id != str(context.get("auth_id")):
            return {
                "state": "unknown",
                "account_status": None,
                "resend_available_after": 0,
            }

        local_user = get_local_user_by_auth_id(auth_id)
        if not local_user:
            return {
                "state": "unknown",
                "account_status": None,
                "resend_available_after": 0,
            }
        if context and int(local_user.get("id")) != int(context.get("user_id")):
            return {
                "state": "unknown",
                "account_status": None,
                "resend_available_after": 0,
            }

        if not auth_user_email_is_verified(auth_user):
            if (
                effective_account_status(local_user) == EXPIRED_PENDING_ACCOUNT_STATUS
                or pending_account_is_expired(local_user)
            ):
                if effective_account_status(local_user) != EXPIRED_PENDING_ACCOUNT_STATUS:
                    service_supabase.table("users").update(
                        {"account_status": EXPIRED_PENDING_ACCOUNT_STATUS}
                    ).eq("id", local_user.get("id")).execute()
                    record_security_event(
                        request=request,
                        actor_user_id=local_user.get("id"),
                        action="auth.pending_account_expired",
                        target_type="user",
                        target_id=local_user.get("id"),
                        metadata={"source": "verification_status"},
                    )
                    record_verification_result(
                        auth_user=auth_user,
                        user_data=local_user,
                        request=request,
                        succeeded=False,
                        failure_code="pending_account_expired",
                    )
                return {
                    "state": "expired",
                    "account_status": EXPIRED_PENDING_ACCOUNT_STATUS,
                    "masked_email": mask_email(canonical_auth_email(auth_user)),
                    "resend_available_after": 0,
                }

            return {
                "state": "pending",
                "account_status": effective_account_status(local_user),
                "masked_email": mask_email(canonical_auth_email(auth_user)),
                "resend_available_after": resend_available_after(local_user),
            }

        synchronized, activated = synchronize_verified_account(auth_user, local_user)
        delete_pending_verification_cookie(response)
        if activated or local_user.get("email_verified") is not True:
            record_verification_result(
                auth_user=auth_user,
                user_data=synchronized,
                request=request,
                succeeded=True,
            )
            record_security_event(
                request=request,
                tenant_id=synchronized.get("tenant_id"),
                actor_user_id=synchronized.get("id"),
                action="auth.email_verification_succeeded",
                target_type="user",
                target_id=synchronized.get("id"),
                metadata={"provisioned": activated},
            )
        return {
            "state": "verified",
            "account_status": effective_account_status(synchronized),
            "masked_email": mask_email(canonical_auth_email(auth_user)),
            "resend_available_after": 0,
            "continue_to": "/login",
        }

    except HTTPException:
        raise
    except Exception as error:
        logger.warning(
            "auth.email_verification.status_failed",
            extra={"error_type": type(error).__name__},
        )
        return {
            "state": "provider_unavailable",
            "account_status": None,
            "resend_available_after": 0,
        }


@router.post("/email-verification/resend")
def resend_email_verification(
    payload: EmailVerificationResendRequest,
    request: Request,
):
    context = read_pending_verification_context(request)
    clean_email = normalize_email(str(payload.email or ""))
    identifier = str((context or {}).get("auth_id") or clean_email or "anonymous")

    try:
        enforce_auth_rate_limit(request, "email_verification_resend_ip")
        enforce_auth_rate_limit(request, "email_verification_resend", identifier)
    except HTTPException as error:
        if error.status_code == 429:
            raise api_error(
                429,
                "email_verification_resend_limited",
                "Too many verification email requests. Please try again later.",
            ) from error
        raise

    known_context = bool(context)
    local_user = None
    auth_user = None

    try:
        if context:
            local_user = get_local_user_by_auth_id(str(context["auth_id"]))
            if local_user and int(local_user.get("id")) == int(context.get("user_id")):
                auth_user = get_auth_user_by_id(str(context["auth_id"]))
            else:
                local_user = None
        elif clean_email:
            local_user = get_local_user_by_email(clean_email)
            if local_user and local_user.get("auth_id"):
                auth_user = get_auth_user_by_id(str(local_user["auth_id"]))
                if canonical_auth_email(auth_user) != clean_email:
                    local_user = None
                    auth_user = None

        if (
            not local_user
            or not auth_user
            or auth_user_email_is_verified(auth_user)
            or effective_account_status(local_user) in {
                ACTIVE_ACCOUNT_STATUS,
                EXPIRED_PENDING_ACCOUNT_STATUS,
            }
        ):
            return {
                "message": GENERIC_RESEND_MESSAGE,
                "state": "pending",
                "resend_available_after": 0,
            }

        delivery = send_verification_email(
            auth_user=auth_user,
            user_data=local_user,
            request=request,
            frontend_url=FRONTEND_URL,
        )
        action = (
            "auth.email_verification_resend_limited"
            if delivery.get("limited")
            else "auth.email_verification_sent"
            if delivery.get("sent")
            else "auth.email_verification_failed"
        )
        record_security_event(
            request=request,
            actor_user_id=local_user.get("id"),
            action=action,
            target_type="user",
            target_id=local_user.get("id"),
            metadata={
                "reason": "resend",
                "delivery_status": (
                    "limited" if delivery.get("limited") else "sent" if delivery.get("sent") else "failed"
                ),
            },
        )

        if known_context and delivery.get("limited"):
            raise api_error(
                429,
                "email_verification_resend_limited",
                "Please wait before requesting another verification email.",
                context={
                    "resend_available_after": int(delivery.get("retry_after") or 0),
                },
            )

        response_payload = {
            "message": GENERIC_RESEND_MESSAGE,
            "state": "pending",
            "resend_available_after": (
                delivery.get("retry_after", 0) if known_context else 0
            ),
        }
        if known_context and delivery.get("failure_code") == "provider_unavailable":
            response_payload["state"] = "provider_unavailable"
        return response_payload

    except HTTPException:
        raise
    except Exception as error:
        logger.warning(
            "auth.email_verification.resend_failed",
            extra={"error_type": type(error).__name__},
        )
        return {
            "message": GENERIC_RESEND_MESSAGE,
            "state": "provider_unavailable" if known_context else "pending",
            "resend_available_after": 0,
        }


@router.post("/email-verification/clear-context")
def clear_email_verification_context(response: Response):
    """Forget only the signed pending-browser context; no account is deleted."""
    delete_pending_verification_cookie(response)
    return {"success": True}


@router.post("/login")
def login(user: LogIn, response: Response, request: Request):
    clean_email = ""
    local_user = None

    try:
        clean_email = normalize_email(user.email)

        if not clean_email:
            raise HTTPException(status_code=400, detail="Email is required")

        enforce_auth_rate_limit(request, "login_ip")
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

        if not is_platform_account(local_user):
            raise api_error(
                403,
                "platform_account_required",
                "Use the login page for the website where this account was created.",
            )

        if not auth_user_email_is_verified(auth_response.user):
            set_pending_verification_cookie(
                response,
                auth_id=auth_user_id,
                user_id=local_user["id"],
            )
            raise api_error(
                403,
                "email_verification_required",
                "Verify your email before logging in.",
                context={
                    "resend_available_after": resend_available_after(local_user),
                },
            )

        provider_email = canonical_auth_email(auth_response.user)
        requires_lifecycle_sync = (
            effective_account_status(local_user) != ACTIVE_ACCOUNT_STATUS
            or (provider_email and normalize_email(local_user.get("email")) != provider_email)
        )
        if requires_lifecycle_sync:
            local_user, activated = synchronize_verified_account(
                auth_response.user,
                local_user,
            )
            if activated:
                record_verification_result(
                    auth_user=auth_response.user,
                    user_data=local_user,
                    request=request,
                    succeeded=True,
                )
                record_security_event(
                    request=request,
                    tenant_id=local_user.get("tenant_id"),
                    actor_user_id=local_user.get("id"),
                    action="auth.email_verification_succeeded",
                    target_type="user",
                    target_id=local_user.get("id"),
                    metadata={"provisioned": True},
                )
        else:
            local_user = mark_local_email_verified(local_user)

        delete_pending_verification_cookie(response)

        mfa_enrollment_recommended = False

        if (
            is_admin_mfa_login_enforcement_enabled()
            and normalize_user_type(local_user.get("user_type")) == "admin"
        ):
            security_settings = get_user_security_settings(local_user.get("id"))

            if security_settings and security_settings.get("mfa_required"):
                try:
                    mfa_client = create_pending_mfa_client(
                        {
                            "access_token": auth_response.session.access_token,
                            "refresh_token": auth_response.session.refresh_token,
                        }
                    )
                    verified_factors = verified_totp_factors_for_client(mfa_client)

                except Exception as mfa_lookup_error:
                    logger.warning(
                        "auth.login.mfa_factor_lookup_failed",
                        extra={
                            "user_id": local_user.get("id"),
                            "error_type": type(mfa_lookup_error).__name__,
                        },
                    )
                    raise api_error(
                        503,
                        "mfa_provider_unavailable",
                        "Multi-factor authentication could not be verified. Try again shortly.",
                    ) from mfa_lookup_error

                if verified_factors:
                    set_pending_mfa_cookie(
                        response,
                        access_token=auth_response.session.access_token,
                        refresh_token=auth_response.session.refresh_token,
                        auth_id=auth_user_id,
                        user_id=local_user.get("id"),
                        tenant_id=local_user.get("tenant_id"),
                    )
                    return {
                        "mfa_required": True,
                        "factors": verified_factors,
                    }

                # A password-only provider session must never become an ordinary
                # admin application session.  Keep the tokens solely in the
                # encrypted, short-lived pending cookie used by the deliberately
                # restricted MFA login/enrollment endpoints.
                set_pending_mfa_cookie(
                    response,
                    access_token=auth_response.session.access_token,
                    refresh_token=auth_response.session.refresh_token,
                    auth_id=auth_user_id,
                    user_id=local_user.get("id"),
                    tenant_id=local_user.get("tenant_id"),
                )
                record_security_event(
                    request=request,
                    tenant_id=local_user.get("tenant_id"),
                    actor_user_id=local_user.get("id"),
                    action="auth.mfa_enrollment_required",
                    target_type="user",
                    target_id=local_user.get("id"),
                    metadata={"login_method": "credentials"},
                )
                return {
                    "mfa_enrollment_required": True,
                    "restricted_session": "mfa_enrollment_only",
                }

        csrf_token = set_auth_cookies(
            response,
            auth_response.session.access_token,
            auth_response.session.refresh_token,
        )

        logger.info(
            "auth.login.success",
            extra={"user_id": local_user.get("id"), "tenant_id": local_user.get("tenant_id")},
        )
        record_security_event(
            request=request,
            tenant_id=local_user.get("tenant_id"),
            actor_user_id=local_user.get("id"),
            action="auth.login_succeeded",
            target_type="user",
            target_id=local_user.get("id"),
            metadata={"login_method": "credentials"},
        )

        login_payload = {
            "message": "User is logged in",
            "user": build_user_payload(local_user),
            "csrf_token": csrf_token,
        }

        if mfa_enrollment_recommended:
            login_payload["mfa_enrollment_recommended"] = True

        return login_payload

    except HTTPException as error:
        audit_user = local_user or get_login_audit_user(clean_email)
        record_security_event(
            request=request,
            tenant_id=(audit_user or {}).get("tenant_id"),
            actor_user_id=(audit_user or {}).get("id"),
            action="auth.login_failed",
            target_type="user" if audit_user else "auth",
            target_id=(audit_user or {}).get("id"),
            metadata={
                "method": "password",
                "status_code": error.status_code,
                "reason": "login_rejected",
            },
        )
        raise

    except Exception as e:
        audit_user = local_user or get_login_audit_user(clean_email)
        logger.warning("auth.login.failed", extra={"error_type": type(e).__name__})
        raw_message = str(e).lower()
        if "email" in raw_message and ("confirm" in raw_message or "verified" in raw_message):
            if audit_user and pending_account_is_expired(audit_user):
                try:
                    service_supabase.table("users").update(
                        {"account_status": EXPIRED_PENDING_ACCOUNT_STATUS}
                    ).eq("id", audit_user.get("id")).execute()
                except Exception as expiry_error:
                    logger.warning(
                        "auth.login.expiry_mark_failed",
                        extra={"error_type": type(expiry_error).__name__},
                    )
                record_security_event(
                    request=request,
                    actor_user_id=audit_user.get("id"),
                    action="auth.pending_account_expired",
                    target_type="user",
                    target_id=audit_user.get("id"),
                    metadata={"source": "login"},
                )
                raise api_error(
                    410,
                    "pending_account_expired",
                    "This pending account has expired. Please sign up again.",
                )
            if audit_user and audit_user.get("auth_id") and audit_user.get("id"):
                set_pending_verification_cookie(
                    response,
                    auth_id=str(audit_user["auth_id"]),
                    user_id=audit_user["id"],
                )
            record_security_event(
                request=request,
                tenant_id=(audit_user or {}).get("tenant_id"),
                actor_user_id=(audit_user or {}).get("id"),
                action="auth.login_failed",
                target_type="user" if audit_user else "auth",
                target_id=(audit_user or {}).get("id"),
                metadata={
                    "method": "password",
                    "reason": "email_not_verified",
                    "error_type": type(e).__name__,
                },
            )
            raise api_error(
                403,
                "email_verification_required",
                "Verify your email before logging in.",
                context={
                    "resend_available_after": resend_available_after(audit_user),
                },
            )

        record_security_event(
            request=request,
            tenant_id=(audit_user or {}).get("tenant_id"),
            actor_user_id=(audit_user or {}).get("id"),
            action="auth.login_failed",
            target_type="user" if audit_user else "auth",
            target_id=(audit_user or {}).get("id"),
            metadata={
                "method": "password",
                "reason": "invalid_credentials",
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")


@router.get("/user_status")
def user_status(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response, allow_refresh=False)
        if not is_platform_account(user_data):
            raise api_error(
                403,
                "platform_account_required",
                "This account is limited to the website where it was created.",
            )
        user_payload = build_user_payload(user_data)
        user_payload.update(get_billing_summary_for_tenant(user_data.get("tenant_id")))
        csrf_token = ensure_csrf_token(request, response)

        return {
            "logged_in": True,
            "user": user_payload,
            "csrf_token": csrf_token,
        }

    except HTTPException as error:
        if error.status_code >= 500 or error.status_code in {408, 429}:
            raise api_error(
                503,
                "auth_temporarily_unavailable",
                "Authentication is temporarily unavailable. Please try again.",
                headers={"Retry-After": "5"},
            ) from error

        # Keep definitive status failures non-destructive. A delayed background
        # probe must never erase newer cookies from a successful refresh/login.
        payload = {
            "logged_in": False,
            "user": None,
        }
        if isinstance(error.detail, dict) and error.detail.get("code"):
            payload["account_state"] = error.detail["code"]
        return payload

    except Exception as error:
        logger.warning(
            "auth.user_status.temporarily_unavailable",
            extra={"error_type": type(error).__name__},
        )
        raise api_error(
            503,
            "auth_temporarily_unavailable",
            "Authentication is temporarily unavailable. Please try again.",
            headers={"Retry-After": "5"},
        ) from error


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
        if error.status_code < 500 and error.status_code not in {408, 429}:
            expired_response = JSONResponse(
                status_code=401,
                content={
                    "detail": error_detail(
                        "auth_session_expired",
                        "Session expired. Please log in again.",
                    )
                },
            )
            delete_auth_cookies(expired_response)
            return expired_response

        logger.warning(
            "auth.refresh.temporarily_unavailable",
            extra={"error_type": type(error).__name__},
        )
        raise api_error(
            503,
            "auth_temporarily_unavailable",
            "Authentication is temporarily unavailable. Please try again.",
            headers={"Retry-After": "5"},
        ) from error

    except Exception as error:
        logger.warning(
            "auth.refresh.temporarily_unavailable",
            extra={"error_type": type(error).__name__},
        )
        raise api_error(
            503,
            "auth_temporarily_unavailable",
            "Authentication is temporarily unavailable. Please try again.",
            headers={"Retry-After": "5"},
        ) from error


@router.put("/password/change")
def change_password(
    payload: UpdatePassword,
    request: Request,
    response: Response,
):
    try:
        auth_user, user_data = get_authenticated_user_row(
            request,
            response,
            allow_admin_account_access=False,
        )

        clean_email = canonical_auth_email(auth_user)
        current_password = payload.current_password
        new_password = validate_password(payload.new_password, label="New password")

        if not clean_email:
            raise HTTPException(status_code=400, detail="User email not found")

        if not current_password:
            raise HTTPException(
                status_code=400,
                detail="Current password is required",
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

        record_security_event(
            request=request,
            tenant_id=user_data.get("tenant_id"),
            actor_user_id=user_data.get("id"),
            action="auth.password_changed",
            target_type="user",
            target_id=user_data.get("id"),
            metadata={"method": "current_password"},
        )

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
def log_out(
    request: Request,
    response: Response,
    logout: LogoutRequest | None = None,
):
    authenticated = False
    provider_revocation_failed = False
    try:
        _, user = get_authenticated_user_row(
            request,
            response,
            allow_admin_account_access=False,
        )
        authenticated = True
        if user.get("id") is not None:
            cleanup_scoped = bool(
                logout and (logout.installation_id or logout.push_endpoint)
            )
            if logout and logout.installation_id:
                try:
                    revoke_installation_push_bindings(
                        user_id=user["id"],
                        installation_id=str(logout.installation_id),
                    )
                except Exception as error:
                    logger.warning(
                        "auth.logout.push_revocation_failed",
                        extra={"error_type": type(error).__name__, "scope": "installation"},
                    )
            if logout and logout.push_endpoint:
                try:
                    revoke_web_push_subscription(
                        user_id=user["id"], endpoint=logout.push_endpoint
                    )
                except Exception as error:
                    logger.warning(
                        "auth.logout.push_revocation_failed",
                        extra={"error_type": type(error).__name__, "scope": "endpoint"},
                    )
            if not cleanup_scoped:
                # Compatibility for older clients which cannot identify the
                # current browser safely: fail closed by revoking all bindings.
                revoke_all_web_push_subscriptions(user_id=user["id"])
    except HTTPException:
        # Logout must still clear local authentication when the session is
        # already invalid or expired.
        pass
    except Exception as error:
        logger.warning(
            "auth.logout.push_revocation_failed",
            extra={"error_type": type(error).__name__},
        )

    if authenticated:
        try:
            revoke_verified_auth_session(request)
        except Exception as error:
            provider_revocation_failed = True
            logger.warning(
                "auth.logout.session_revocation_failed",
                extra={"error_type": type(error).__name__},
            )

    delete_auth_cookies(response)

    if provider_revocation_failed:
        unavailable = JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "session_revocation_unavailable",
                    "message": "The session could not be revoked. Sign in again before retrying.",
                }
            },
        )
        delete_auth_cookies(unavailable)
        return unavailable

    return {
        "message": "Logged out successfully",
    }
