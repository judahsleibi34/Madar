from __future__ import annotations

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
    "draft_schema",
    "published_schema",
    "answers",
    "raw_body",
}
MAX_USER_AGENT_LENGTH = 1000


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
