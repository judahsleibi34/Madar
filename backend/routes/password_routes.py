import os
import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from supabase import create_client

from classes import PasswordReset
from database import service_supabase, supabase
from services.rate_limit_service import enforce_password_rate_limit
from services.audit_service import record_security_event
from services.frontend_url import resolve_frontend_url_for_request
from services.account_lifecycle_service import auth_email_is_verified, effective_account_status
from services.api_errors import api_error
from services.identity_service import (
    auth_value,
    canonical_auth_email,
    find_auth_user_by_email,
    normalize_email,
)
from services.password_policy import validate_password

router = APIRouter(prefix="/auth", tags=["Password"])
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
RESET_MESSAGE = "If that email is registered, a password reset link has been sent."
PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "10"))


def get_local_user_by_auth_id(auth_id: str):
    if not auth_id:
        return None

    result = (
        service_supabase.table("users")
        .select("id, auth_id, tenant_id, email, account_status, password_reset_requested_at")
        .eq("auth_id", str(auth_id))
        .limit(1)
        .execute()
    )

    if isinstance(result.data, dict):
        return result.data
    return result.data[0] if result.data else None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def mark_password_reset_requested(user_id: int):
    service_supabase.table("users").update(
        {"password_reset_requested_at": _iso(_utc_now())}
    ).eq("id", user_id).execute()


def assert_password_reset_window(local_user: dict | None):
    requested_at = _parse_datetime((local_user or {}).get("password_reset_requested_at"))
    expires_at = requested_at + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES) if requested_at else None

    if not expires_at or expires_at <= _utc_now():
        code = "password_reset_replayed" if not requested_at else "password_reset_expired"
        raise api_error(
            409 if not requested_at else 401,
            code,
            "This password reset link was already used."
            if not requested_at
            else "Password reset link expired. Request a new link.",
        )


def clear_password_reset_request(user_id: int):
    service_supabase.table("users").update(
        {"password_reset_requested_at": None}
    ).eq("id", user_id).execute()


def _reset_nonce_hash(raw_nonce: str) -> str:
    return hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()


def create_password_reset_request(local_user: dict, auth_id: str) -> str | None:
    """Create a provider-link-bound nonce before asking the provider to send."""
    raw_nonce = secrets.token_urlsafe(32)
    now = _utc_now()
    expires_at = now + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
    try:
        service_supabase.table("password_reset_requests").update(
            {"status": "revoked"}
        ).eq("auth_id", str(auth_id)).in_("status", ["pending", "processing"]).execute()
        result = service_supabase.table("password_reset_requests").insert(
            {
                "user_id": local_user["id"],
                "auth_id": str(auth_id),
                "nonce_hash": _reset_nonce_hash(raw_nonce),
                "status": "pending",
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        ).execute()
        if result.data:
            return raw_nonce
    except Exception as error:
        logger.warning(
            "auth.password_reset.request_record_failed",
            extra={"user_id": local_user.get("id"), "error_type": type(error).__name__},
        )
    return None


def legacy_password_reset_link_is_allowed(*, now: datetime | None = None) -> bool:
    """Allow old timestamp-only links only during an explicit bounded rollout."""
    cutoff = os.getenv("PASSWORD_RESET_LEGACY_LINKS_ALLOWED_UNTIL", "").strip()
    if not cutoff:
        return False
    try:
        parsed = _parse_datetime(cutoff)
    except ValueError:
        return False
    return bool(parsed and parsed > (now or _utc_now()))


def claim_password_reset_request(auth_id: str, raw_nonce: str) -> str:
    nonce_hash = _reset_nonce_hash(raw_nonce)
    rpc = getattr(service_supabase, "rpc", None)
    if callable(rpc):
        try:
            response = rpc(
                "claim_password_reset_request",
                {
                    "p_auth_id": str(auth_id),
                    "p_nonce_hash": nonce_hash,
                    "p_now": _iso(_utc_now()),
                },
            ).execute()
        except Exception as error:
            text = str(error).lower()
            if "password_reset_replayed" in text:
                raise api_error(409, "password_reset_replayed", "This password reset link was already used.")
            if "password_reset_expired" in text:
                raise api_error(401, "password_reset_expired", "Password reset link expired. Request a new link.")
            if "password_reset_in_progress" in text:
                raise api_error(409, "password_reset_in_progress", "This password reset is already being processed.")
            if "password_reset_invalid" in text:
                raise api_error(401, "password_reset_invalid", "Password reset link is invalid.")
            logger.warning(
                "auth.password_reset.claim_failed",
                extra={"error_type": type(error).__name__},
            )
            raise api_error(503, "dependency_unavailable", "Password reset is temporarily unavailable.")

        record = response.data
        if isinstance(record, list):
            record = record[0] if record else None
        if isinstance(record, dict) and isinstance(record.get("result"), dict):
            record = record["result"]
        if not isinstance(record, dict) or not record.get("id"):
            raise api_error(503, "dependency_unavailable", "Password reset is temporarily unavailable.")
        if record.get("status") == "expired":
            raise api_error(
                401,
                "password_reset_expired",
                "Password reset link expired. Request a new link.",
            )
        return str(record["id"])

    # Compatibility for focused in-memory test doubles. Deployed clients use the
    # transaction-safe RPC above.
    result = (
        service_supabase.table("password_reset_requests")
        .select("id, status, expires_at, consumed_at, processing_started_at")
        .eq("auth_id", str(auth_id))
        .eq("nonce_hash", nonce_hash)
        .limit(1)
        .execute()
    )
    record = result.data[0] if result.data else None
    if not record:
        raise api_error(401, "password_reset_invalid", "Password reset link is invalid.")
    if record.get("status") == "consumed" or record.get("consumed_at"):
        raise api_error(409, "password_reset_replayed", "This password reset link was already used.")
    if record.get("status") != "pending":
        raise api_error(401, "password_reset_invalid", "Password reset link is invalid.")

    expires_at = _parse_datetime(record.get("expires_at"))
    if not expires_at or expires_at <= _utc_now():
        service_supabase.table("password_reset_requests").update(
            {"status": "expired"}
        ).eq("id", record.get("id")).eq("status", "pending").execute()
        raise api_error(
            401,
            "password_reset_expired",
            "Password reset link expired. Request a new link.",
        )

    claimed = (
        service_supabase.table("password_reset_requests")
        .update({"status": "processing", "processing_started_at": _iso(_utc_now())})
        .eq("id", record.get("id"))
        .eq("status", "pending")
        .execute()
    )
    if not claimed.data:
        raise api_error(409, "password_reset_replayed", "This password reset link was already used.")
    return str(record["id"])


def finish_password_reset_request(request_id: str, *, succeeded: bool) -> None:
    rpc = getattr(service_supabase, "rpc", None)
    if callable(rpc):
        response = rpc(
            "finish_password_reset_request",
            {
                "p_request_id": request_id,
                "p_succeeded": bool(succeeded),
                "p_finished_at": _iso(_utc_now()),
            },
        ).execute()
        if not getattr(response, "data", None):
            raise RuntimeError("password_reset_finish_empty")
        return

    payload = {
        # A provider call can succeed even when its response is lost. Never
        # reopen that link after an ambiguous failure; the user must request a
        # fresh recovery link instead.
        "status": "consumed" if succeeded else "revoked",
        "consumed_at": _iso(_utc_now()) if succeeded else None,
        "processing_started_at": None,
    }
    result = (
        service_supabase.table("password_reset_requests")
        .update(payload)
        .eq("id", request_id)
        .eq("status", "processing")
        .execute()
    )
    if not result.data:
        raise RuntimeError("password_reset_finish_conflict")


admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@router.post("/forgot-password")
def forgot_password(payload: dict, request: Request):
    audit_recorded = False

    try:
        email = normalize_email(payload.get("email", ""))

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        enforce_password_rate_limit(request, "forgot_password_ip")
        enforce_password_rate_limit(request, "forgot_password", email)

        try:
            auth_user = find_auth_user_by_email(email)
        except HTTPException:
            auth_user = None

        canonical_email = canonical_auth_email(auth_user)
        auth_id = str(auth_value(auth_user, "id") or "")
        user_row = get_local_user_by_auth_id(auth_id) if auth_id else None

        record_security_event(
            request=request,
            tenant_id=(user_row or {}).get("tenant_id"),
            actor_user_id=(user_row or {}).get("id"),
            action="auth.password_reset_requested",
            target_type="user" if user_row else "auth",
            target_id=(user_row or {}).get("id"),
            metadata={"user_found": bool(user_row)},
        )
        audit_recorded = True

        if (
            not auth_user
            or not user_row
            or not user_row.get("auth_id")
            or canonical_email != email
            or not auth_email_is_verified(auth_user)
        ):
            return {"message": RESET_MESSAGE}

        request_token = create_password_reset_request(
            user_row,
            str(user_row["auth_id"]),
        )
        # Do not issue a provider recovery link that is not bound to a durable,
        # one-time request record. The response stays generic for enumeration
        # resistance when storage is unavailable.
        if not request_token:
            return {"message": RESET_MESSAGE}
        frontend_url = resolve_frontend_url_for_request(request.headers.get("origin"))
        redirect_to = f"{frontend_url}/reset-password"
        redirect_to = f"{redirect_to}?request_token={quote(request_token, safe='')}"

        supabase.auth.reset_password_email(
            canonical_email,
            options={"redirect_to": redirect_to},
        )

        return {"message": RESET_MESSAGE}

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("auth.forgot_password.failed", extra={"error_type": type(e).__name__})

        if not audit_recorded:
            record_security_event(
                request=request,
                action="auth.password_reset_requested",
                target_type="auth",
                metadata={"user_found": False, "lookup_failed": True},
            )

        return {"message": RESET_MESSAGE}


@router.post("/password-reset")
def password_reset(payload: PasswordReset, request: Request):
    try:
        enforce_password_rate_limit(request, "password_reset")
        password = validate_password(payload.password)

        try:
            user = supabase.auth.get_user(payload.access_token)
        except Exception as provider_error:
            logger.warning(
                "auth.password_reset.token_validation_failed",
                extra={"error_type": type(provider_error).__name__},
            )
            raise api_error(
                401,
                "password_reset_invalid",
                "Password reset link is invalid or expired.",
            ) from provider_error

        if not user.user:
            raise api_error(
                401,
                "password_reset_invalid",
                "Password reset link is invalid or expired.",
            )

        if not auth_email_is_verified(user.user):
            raise api_error(
                403,
                "email_verification_required",
                "Verify your email before resetting your password.",
            )

        local_user = get_local_user_by_auth_id(str(user.user.id))
        if not local_user:
            raise api_error(401, "password_reset_invalid", "Password reset link is invalid.")
        if effective_account_status(local_user) in {"disabled", "expired_pending"}:
            raise api_error(403, "account_unavailable", "This account is not available.")

        claimed_request_id = None
        if payload.request_token:
            claimed_request_id = claim_password_reset_request(
                str(user.user.id),
                payload.request_token,
            )
        else:
            if not legacy_password_reset_link_is_allowed():
                raise api_error(
                    401,
                    "password_reset_invalid",
                    "Password reset link is invalid or expired.",
                )
            # Optional, time-bounded compatibility for links issued before
            # migration 043. It is disabled unless operators set a cutoff.
            assert_password_reset_window(local_user)

        try:
            admin_supabase.auth.admin.update_user_by_id(
                str(user.user.id),
                {"password": password},
            )
        except Exception:
            if claimed_request_id:
                try:
                    finish_password_reset_request(claimed_request_id, succeeded=False)
                except Exception as release_error:
                    logger.warning(
                        "auth.password_reset.claim_release_failed",
                        extra={"error_type": type(release_error).__name__},
                    )
            raise api_error(
                503,
                "dependency_unavailable",
                "Password service is temporarily unavailable. Request a new reset link and try again.",
            )

        if claimed_request_id:
            try:
                finish_password_reset_request(claimed_request_id, succeeded=True)
            except Exception as finish_error:
                logger.error(
                    "auth.password_reset.finish_failed",
                    extra={"error_type": type(finish_error).__name__},
                )

        if local_user:
            try:
                clear_password_reset_request(local_user.get("id"))
            except Exception as cleanup_error:
                logger.warning(
                    "auth.password_reset.legacy_cleanup_failed",
                    extra={"error_type": type(cleanup_error).__name__},
                )

        record_security_event(
            request=request,
            tenant_id=(local_user or {}).get("tenant_id"),
            actor_user_id=(local_user or {}).get("id"),
            action="auth.password_reset_completed",
            target_type="user" if local_user else "auth",
            target_id=(local_user or {}).get("id"),
            metadata={"method": "reset_token"},
        )

        return {
            "message": "Password updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("auth.password_reset.failed", extra={"error_type": type(e).__name__})
        raise api_error(
            400,
            "password_reset_invalid",
            "Could not reset password.",
        )
