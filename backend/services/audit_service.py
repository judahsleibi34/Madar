from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import Request

from database import service_supabase
from services.rate_limit_service import get_client_ip

logger = logging.getLogger(__name__)

SENSITIVE_METADATA_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "authorization",
    "secret",
    "session",
    "session_id",
    "session_token",
    "draft_schema",
    "published_schema",
    "answers",
    "raw_body",
}
MAX_USER_AGENT_LENGTH = 1000

MFA_ENROLL_STARTED = "auth.mfa_enroll_started"
MFA_ENROLL_VERIFIED = "auth.mfa_enroll_verified"
MFA_CHALLENGE_FAILED = "auth.mfa_challenge_failed"
MFA_VERIFIED = "auth.mfa_verified"
MFA_FACTOR_REMOVED = "auth.mfa_factor_removed"
MFA_REQUIRED_CHANGED = "auth.mfa_required_changed"


def normalize_metadata_key(key: Any) -> str:
    return str(key or "").strip().lower().replace("-", "_")


def sanitize_metadata_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_metadata(value)

    if isinstance(value, list):
        return [sanitize_metadata_value(item) for item in value]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def sanitize_metadata(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}

    sanitized = {}

    for key, value in metadata.items():
        clean_key = str(key)
        if normalize_metadata_key(clean_key) in SENSITIVE_METADATA_KEYS:
            continue

        sanitized[clean_key] = sanitize_metadata_value(value)

    return sanitized


def hash_audit_identifier(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()

    if not normalized or normalized == "anonymous":
        return None

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def record_audit_event(
    *,
    request: Request | None = None,
    tenant_id: int | None,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    metadata: dict | None = None,
) -> None:
    payload = {
        "tenant_id": tenant_id,
        "actor_user_id": actor_user_id,
        "action": str(action or "").strip(),
        "target_type": str(target_type or "").strip(),
        "target_id": str(target_id) if target_id is not None else None,
        "metadata": sanitize_metadata(metadata),
        "ip": get_client_ip(request) if request is not None else None,
        "user_agent": (request.headers.get("user-agent", "")[:MAX_USER_AGENT_LENGTH] if request is not None else None),
    }

    if not payload["action"] or not payload["target_type"]:
        logger.warning(
            "audit.event_invalid",
            extra={"action": payload["action"], "target_type": payload["target_type"]},
        )
        return

    try:
        service_supabase.table("audit_logs").insert(payload).execute()
    except Exception as error:
        logger.warning(
            "audit.event_insert_failed",
            extra={
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "action": payload["action"],
                "target_type": payload["target_type"],
                "target_id": payload["target_id"],
                "error_type": type(error).__name__,
            },
        )


def record_security_event(
    *,
    request: Request | None = None,
    action: str,
    actor_user_id: int | None = None,
    tenant_id: int | None = None,
    target_type: str = "security_event",
    target_id: str | int | None = None,
    metadata: dict | None = None,
) -> None:
    record_audit_event(
        request=request,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
    )


def record_tenant_role_change(
    *,
    request: Request | None = None,
    tenant_id: int | None,
    actor_user_id: int | None,
    target_user_id: int | None,
    old_role: str | None,
    new_role: str | None,
    source: str = "tenant_admin",
) -> None:
    record_security_event(
        request=request,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="tenant.role_changed",
        target_type="tenant_membership",
        target_id=target_user_id,
        metadata={
            "affected_user_id": target_user_id,
            "old_role": old_role,
            "new_role": new_role,
            "source": source,
        },
    )


def record_user_restoration(
    *,
    request: Request | None = None,
    tenant_id: int | None,
    actor_user_id: int | None,
    restored_user_id: int | None,
    source: str = "admin",
) -> None:
    record_security_event(
        request=request,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="admin.user_restored",
        target_type="user",
        target_id=restored_user_id,
        metadata={
            "restored_user_id": restored_user_id,
            "source": source,
        },
    )


def record_mfa_event(
    *,
    request: Request | None = None,
    action: str,
    tenant_id: int | None = None,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    factor_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    clean_metadata = dict(metadata or {})

    if factor_id:
        clean_metadata["factor_id"] = factor_id

    record_security_event(
        request=request,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type="mfa_factor" if factor_id else "user",
        target_id=factor_id or target_user_id or actor_user_id,
        metadata=clean_metadata,
    )


def record_mfa_required_changed(
    *,
    request: Request | None = None,
    tenant_id: int | None = None,
    actor_user_id: int | None = None,
    target_user_id: int | None,
    required: bool,
    source: str = "admin",
) -> None:
    record_mfa_event(
        request=request,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=MFA_REQUIRED_CHANGED,
        target_user_id=target_user_id,
        metadata={
            "required": required,
            "source": source,
        },
    )
