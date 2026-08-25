from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import api_error
from services.identity_service import (
    auth_user_id,
    auth_value,
    canonical_auth_email,
    get_auth_user_by_id,
    normalize_email,
)
from services.audit_service import record_security_event

logger = logging.getLogger(__name__)

PENDING_ACCOUNT_STATUS = "pending_verification"
ACTIVE_ACCOUNT_STATUS = "active"
DISABLED_ACCOUNT_STATUS = "disabled"
EXPIRED_PENDING_ACCOUNT_STATUS = "expired_pending"
DELETION_PENDING_ACCOUNT_STATUS = "deletion_pending"
PLATFORM_ACCOUNT_KIND = "platform"
SITE_VISITOR_ACCOUNT_KIND = "site_visitor"


def auth_email_is_verified(auth_user) -> bool:
    return bool(
        auth_value(auth_user, "email_confirmed_at")
        or auth_value(auth_user, "confirmed_at")
    )


def effective_account_status(user_data: dict) -> str:
    explicit = str(user_data.get("account_status") or "").strip().lower()
    if explicit:
        return explicit
    # Backward compatibility before/while migration 043 is rolled out.
    if user_data.get("tenant_id") is not None or user_data.get("email_verified") is not False:
        return ACTIVE_ACCOUNT_STATUS
    return PENDING_ACCOUNT_STATUS


def is_platform_account(user_data: dict | None) -> bool:
    """Older rows are platform accounts unless explicitly classified as visitors."""
    return str((user_data or {}).get("account_kind") or PLATFORM_ACCOUNT_KIND).strip().lower() != SITE_VISITOR_ACCOUNT_KIND


def _provider_verified_at(auth_user) -> str:
    value = (
        auth_value(auth_user, "email_confirmed_at")
        or auth_value(auth_user, "confirmed_at")
    )
    return str(value or datetime.now(timezone.utc).isoformat())


def _pending_expired(user_data: dict) -> bool:
    value = user_data.get("pending_account_expires_at")
    if not value:
        return False
    try:
        expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at.astimezone(timezone.utc) <= datetime.now(timezone.utc)


def _assert_local_email_available(canonical_email: str, auth_id: str):
    result = (
        service_supabase.table("users")
        .select("id, auth_id")
        .eq("email", canonical_email)
        .limit(1)
        .execute()
    )
    if result.data and str(result.data[0].get("auth_id") or "") != auth_id:
        raise api_error(
            409,
            "canonical_email_conflict",
            "The verified email is already linked to another account.",
        )


def synchronize_verified_account(auth_user, user_data: dict) -> tuple[dict, bool]:
    """Synchronize canonical identity and provision a pending account exactly once.

    Migration 043 supplies the transactional ``provision_verified_account`` RPC.
    Existing active tenants do not need the RPC and remain backward compatible.
    """
    if not auth_email_is_verified(auth_user):
        raise api_error(
            403,
            "email_verification_required",
            "Verify your email before logging in.",
        )

    status = effective_account_status(user_data)
    if status == DISABLED_ACCOUNT_STATUS:
        raise api_error(403, "account_disabled", "This account is disabled.")
    if status == DELETION_PENDING_ACCOUNT_STATUS:
        raise api_error(
            403,
            "account_deletion_pending",
            "This account is closed while deletion is being completed.",
        )
    if status == EXPIRED_PENDING_ACCOUNT_STATUS:
        raise api_error(
            410,
            "pending_account_expired",
            "This pending account has expired. Please sign up again.",
        )
    if status == PENDING_ACCOUNT_STATUS and _pending_expired(user_data):
        try:
            service_supabase.table("users").update(
                {"account_status": EXPIRED_PENDING_ACCOUNT_STATUS}
            ).eq("id", user_data.get("id")).execute()
        except Exception as error:
            logger.warning(
                "auth.account.expiry_mark_failed",
                extra={"error_type": type(error).__name__},
            )
        raise api_error(
            410,
            "pending_account_expired",
            "This pending account has expired. Please sign up again.",
        )

    provider_auth_id = auth_user_id(auth_user)
    if not provider_auth_id or provider_auth_id != str(user_data.get("auth_id") or ""):
        raise api_error(401, "identity_mismatch", "The account identity could not be verified.")

    canonical_email = canonical_auth_email(auth_user)
    if not canonical_email:
        raise api_error(
            503,
            "identity_provider_unavailable",
            "The identity service did not return a canonical email.",
        )

    local_email = normalize_email(user_data.get("email"))
    if local_email != canonical_email:
        _assert_local_email_available(canonical_email, provider_auth_id)

    platform_account = is_platform_account(user_data)
    needs_identity_update = (
        local_email != canonical_email
        or user_data.get("email_verified") is not True
        or not user_data.get("email_verified_at")
        or (
            not platform_account
            and effective_account_status(user_data) != ACTIVE_ACCOUNT_STATUS
        )
    )
    synchronized = user_data

    if needs_identity_update:
        pending_email = normalize_email(user_data.get("pending_email"))
        email_change_completed_at = (
            datetime.now(timezone.utc).isoformat()
            if pending_email and pending_email == canonical_email
            else user_data.get("email_change_completed_at")
        )
        identity_update = {
            "email": canonical_email,
            "email_verified": True,
            "email_verified_at": _provider_verified_at(auth_user),
            "pending_email": None,
            "pending_email_requested_at": None,
            "email_change_completed_at": email_change_completed_at,
        }
        if not platform_account:
            identity_update["account_status"] = ACTIVE_ACCOUNT_STATUS

        update_result = (
            service_supabase.table("users")
            .update(identity_update)
            .eq("auth_id", provider_auth_id)
            .execute()
        )
        if update_result.data:
            synchronized = update_result.data[0]
        else:
            synchronized = {
                **user_data,
                "email": canonical_email,
                "email_verified": True,
                "email_verified_at": _provider_verified_at(auth_user),
                "pending_email": None,
                "pending_email_requested_at": None,
                "email_change_completed_at": email_change_completed_at,
                **(
                    {"account_status": ACTIVE_ACCOUNT_STATUS}
                    if not platform_account
                    else {}
                ),
            }

    was_activated = False
    if platform_account and effective_account_status(synchronized) == PENDING_ACCOUNT_STATUS:
        try:
            provision_result = service_supabase.rpc(
                "provision_verified_account",
                {"p_auth_id": provider_auth_id},
            ).execute()
        except Exception as error:
            logger.warning(
                "auth.account.provision_failed",
                extra={
                    "auth_id": provider_auth_id,
                    "user_id": user_data.get("id"),
                    "error_type": type(error).__name__,
                },
            )
            raise api_error(
                503,
                "account_provisioning_failed",
                "Your email is verified, but account setup could not be completed. Please retry.",
            ) from error

        provisioned = provision_result.data
        if isinstance(provisioned, list):
            provisioned = provisioned[0] if provisioned else None
        if not provisioned:
            raise api_error(
                503,
                "account_provisioning_failed",
                "Your email is verified, but account setup could not be completed. Please retry.",
            )
        synchronized = provisioned
        was_activated = True
    elif not platform_account and effective_account_status(user_data) != ACTIVE_ACCOUNT_STATUS:
        was_activated = True

    return synchronized, was_activated


def get_local_user_by_auth_id(auth_id: str) -> dict | None:
    if not auth_id:
        return None
    result = (
        service_supabase.table("users")
        .select("*")
        .eq("auth_id", str(auth_id))
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def cleanup_stale_pending_accounts(
    *,
    dry_run: bool = True,
    limit: int = 100,
    now: datetime | None = None,
) -> dict:
    """Inspect or remove expired, unverified, resource-free pending accounts.

    The command is deliberately dry-run by default and skips any account linked
    to a tenant. Provider confirmation is checked immediately before deletion.
    """
    current = now or datetime.now(timezone.utc)
    safe_limit = max(1, min(int(limit), 1000))
    response = (
        service_supabase.table("pending_account_onboarding")
        .select("id, auth_id, user_id, tenant_id, status, expires_at")
        .in_("status", ["pending", "failed"])
        .lte("expires_at", current.isoformat())
        .order("expires_at")
        .limit(safe_limit)
        .execute()
    )
    summary = {
        "dry_run": bool(dry_run),
        "examined": 0,
        "eligible": 0,
        "deleted": 0,
        "skipped_verified": 0,
        "skipped_resources": 0,
        "failed": 0,
        "eligible_user_ids": [],
    }

    for pending in response.data or []:
        summary["examined"] += 1
        auth_id = str(pending.get("auth_id") or "")
        local_user = get_local_user_by_auth_id(auth_id)
        if (
            pending.get("tenant_id") is not None
            or (local_user or {}).get("tenant_id") is not None
        ):
            summary["skipped_resources"] += 1
            continue
        try:
            auth_user = get_auth_user_by_id(auth_id)
        except Exception as error:
            logger.warning(
                "auth.pending_cleanup.provider_lookup_failed",
                extra={"error_type": type(error).__name__},
            )
            summary["failed"] += 1
            continue
        if auth_user and auth_email_is_verified(auth_user):
            summary["skipped_verified"] += 1
            continue

        user_id = (local_user or {}).get("id") or pending.get("user_id")
        summary["eligible"] += 1
        summary["eligible_user_ids"].append(user_id)
        if dry_run:
            continue

        record_security_event(
            action="auth.pending_account_expired",
            actor_user_id=user_id,
            target_type="user",
            target_id=user_id,
            metadata={"source": "pending_cleanup", "dry_run": False},
        )
        try:
            if auth_id:
                service_supabase.auth.admin.delete_user(auth_id)
            elif user_id is not None:
                service_supabase.table("users").delete().eq("id", user_id).execute()
            summary["deleted"] += 1
        except Exception as error:
            logger.warning(
                "auth.pending_cleanup.delete_failed",
                extra={"error_type": type(error).__name__},
            )
            summary["failed"] += 1
            try:
                if user_id is not None:
                    service_supabase.table("users").update(
                        {"account_status": EXPIRED_PENDING_ACCOUNT_STATUS}
                    ).eq("id", user_id).execute()
                service_supabase.table("pending_account_onboarding").update(
                    {"status": "expired", "last_error_code": "cleanup_failed"}
                ).eq("id", pending.get("id")).execute()
            except Exception as mark_error:
                logger.warning(
                    "auth.pending_cleanup.mark_failed",
                    extra={"error_type": type(mark_error).__name__},
                )

    return summary
