from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

from database import service_supabase, supabase
from services.audit_service import get_client_ip, hash_audit_identifier
from services.identity_service import canonical_auth_email, normalize_email

logger = logging.getLogger(__name__)

VERIFICATION_RESEND_COOLDOWN_SECONDS = int(
    os.getenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "60")
)
VERIFICATION_RESEND_HOURLY_LIMIT = int(
    os.getenv("EMAIL_VERIFICATION_RESEND_HOURLY_LIMIT", "5")
)
VERIFICATION_RESEND_DAILY_LIMIT = int(
    os.getenv("EMAIL_VERIFICATION_RESEND_DAILY_LIMIT", "10")
)
GENERIC_RESEND_MESSAGE = (
    "If the account is awaiting verification, a new email has been sent."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash_secret() -> bytes:
    value = (
        os.getenv("VERIFICATION_HASH_SECRET")
        or os.getenv("CSRF_SECRET")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SECRET_KEY")
        or "madar-development-verification-hash-secret"
    )
    return value.encode("utf-8")


def hash_verification_identifier(value: str | None) -> str:
    normalized = normalize_email(value)
    return hmac.new(_hash_secret(), normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def mask_email(value: str | None) -> str:
    clean = normalize_email(value)
    if "@" not in clean:
        return ""
    local, domain = clean.rsplit("@", 1)
    if not local or not domain:
        return ""
    visible = local[:1]
    return f"{visible}{'*' * max(2, min(len(local) - 1, 8))}@{domain}"


def resend_available_after(user_data: dict | None, *, now: datetime | None = None) -> int:
    sent_at = _parse_datetime((user_data or {}).get("email_verification_sent_at"))
    if not sent_at:
        return 0
    current = now or _utc_now()
    elapsed = int((current - sent_at).total_seconds())
    return max(0, VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed)


def pending_account_is_expired(user_data: dict | None, *, now: datetime | None = None) -> bool:
    expires_at = _parse_datetime((user_data or {}).get("pending_account_expires_at"))
    return bool(expires_at and expires_at <= (now or _utc_now()))


def _attempt_count(email_hash: str, since: datetime) -> int:
    result = (
        service_supabase.table("email_verification_attempts")
        .select("id")
        .eq("email_hash", email_hash)
        .in_("status", ["sent", "failed"])
        .gte("requested_at", since.isoformat())
        .execute()
    )
    return len(result.data or [])


def _record_attempt(
    *,
    user_data: dict | None,
    auth_id: str | None,
    email_hash: str,
    status: str,
    failure_code: str | None,
    provider_message_id: str | None = None,
    request,
):
    try:
        service_supabase.table("email_verification_attempts").insert(
            {
                "user_id": (user_data or {}).get("id"),
                "auth_id": auth_id or None,
                "email_hash": email_hash,
                "provider": "supabase",
                "status": status,
                "failure_code": failure_code,
                "provider_message_id": provider_message_id,
                "requester_ip_hash": hash_audit_identifier(
                    get_client_ip(request) if request is not None else None
                ),
            }
        ).execute()
    except Exception as error:
        logger.warning(
            "auth.email_verification.attempt_record_failed",
            extra={"error_type": type(error).__name__, "status": status},
        )


def _update_delivery_state(user_data: dict, *, sent_at: datetime):
    try:
        service_supabase.table("users").update(
            {
                "email_verification_sent_at": sent_at.isoformat(),
                "email_verification_resend_count": int(
                    user_data.get("email_verification_resend_count") or 0
                )
                + 1,
            }
        ).eq("id", user_data.get("id")).execute()
    except Exception as error:
        logger.warning(
            "auth.email_verification.delivery_state_update_failed",
            extra={"user_id": user_data.get("id"), "error_type": type(error).__name__},
        )


def send_verification_email(
    *,
    auth_user,
    user_data: dict,
    request,
    frontend_url: str,
) -> dict:
    """Send through Supabase while enforcing durable cooldown/window limits."""
    email = canonical_auth_email(auth_user)
    auth_id = str(getattr(auth_user, "id", None) or (auth_user.get("id") if isinstance(auth_user, dict) else ""))
    email_hash = hash_verification_identifier(email)
    now = _utc_now()

    if not email or not auth_id:
        return {"sent": False, "failure_code": "identity_unavailable", "retry_after": 0}

    retry_after = resend_available_after(user_data, now=now)
    hourly_count = _attempt_count(email_hash, now - timedelta(hours=1))
    daily_count = _attempt_count(email_hash, now - timedelta(days=1))

    if (
        retry_after > 0
        or hourly_count >= VERIFICATION_RESEND_HOURLY_LIMIT
        or daily_count >= VERIFICATION_RESEND_DAILY_LIMIT
    ):
        if retry_after <= 0:
            retry_after = 3600 if hourly_count >= VERIFICATION_RESEND_HOURLY_LIMIT else 86400
        _record_attempt(
            user_data=user_data,
            auth_id=auth_id,
            email_hash=email_hash,
            status="limited",
            failure_code="email_verification_resend_limited",
            request=request,
        )
        return {
            "sent": False,
            "limited": True,
            "failure_code": "email_verification_resend_limited",
            "retry_after": retry_after,
        }

    _record_attempt(
        user_data=user_data,
        auth_id=auth_id,
        email_hash=email_hash,
        status="requested",
        failure_code=None,
        request=request,
    )

    try:
        response = supabase.auth.resend(
            {
                "type": "signup",
                "email": email,
                "options": {"email_redirect_to": f"{frontend_url}/verify-email"},
            }
        )
    except Exception as error:
        logger.warning(
            "auth.email_verification.provider_send_failed",
            extra={"auth_id": auth_id, "error_type": type(error).__name__},
        )
        _record_attempt(
            user_data=user_data,
            auth_id=auth_id,
            email_hash=email_hash,
            status="failed",
            failure_code="provider_unavailable",
            request=request,
        )
        return {"sent": False, "failure_code": "provider_unavailable", "retry_after": 0}

    provider_message_id = getattr(response, "message_id", None)
    _update_delivery_state(user_data, sent_at=now)
    _record_attempt(
        user_data=user_data,
        auth_id=auth_id,
        email_hash=email_hash,
        status="sent",
        failure_code=None,
        provider_message_id=str(provider_message_id) if provider_message_id else None,
        request=request,
    )
    return {
        "sent": True,
        "provider_message_id": provider_message_id,
        "retry_after": VERIFICATION_RESEND_COOLDOWN_SECONDS,
    }


def record_verification_result(
    *,
    auth_user,
    user_data: dict,
    request,
    succeeded: bool,
    failure_code: str | None = None,
) -> None:
    email = canonical_auth_email(auth_user)
    auth_id = str(
        getattr(auth_user, "id", None)
        or (auth_user.get("id") if isinstance(auth_user, dict) else "")
    )
    if not email or not auth_id:
        return
    _record_attempt(
        user_data=user_data,
        auth_id=auth_id,
        email_hash=hash_verification_identifier(email),
        status="verified" if succeeded else "failed",
        failure_code=None if succeeded else (failure_code or "verification_failed"),
        request=request,
    )
