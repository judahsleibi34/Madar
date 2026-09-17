from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from database import service_supabase

logger = logging.getLogger(__name__)

SECURITY_SETTINGS_COLUMNS = (
    "user_id, auth_id, mfa_required, mfa_required_at, mfa_grace_until, "
    "last_aal2_at, created_at, updated_at"
)


def normalize_security_settings(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None

    return {
        "user_id": row.get("user_id"),
        "auth_id": str(row.get("auth_id")) if row.get("auth_id") is not None else None,
        "mfa_required": bool(row.get("mfa_required")),
        "mfa_required_at": row.get("mfa_required_at"),
        "mfa_grace_until": row.get("mfa_grace_until"),
        "last_aal2_at": row.get("last_aal2_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_user_security_settings(user_id: int) -> dict[str, Any] | None:
    try:
        response = (
            service_supabase
            .table("user_security_settings")
            .select(SECURITY_SETTINGS_COLUMNS)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.warning(
            "user_security_settings.fetch_failed",
            extra={"user_id": user_id, "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not load user security settings")

    return normalize_security_settings(response.data[0] if response.data else None)


def get_user_security_settings_by_auth_id(auth_id: str) -> dict[str, Any] | None:
    clean_auth_id = str(auth_id or "").strip()

    if not clean_auth_id:
        return None

    try:
        response = (
            service_supabase
            .table("user_security_settings")
            .select(SECURITY_SETTINGS_COLUMNS)
            .eq("auth_id", clean_auth_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.warning(
            "user_security_settings.fetch_by_auth_id_failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not load user security settings")

    return normalize_security_settings(response.data[0] if response.data else None)


def upsert_user_security_settings(
    *,
    user_id: int,
    auth_id: str,
    mfa_required: bool | None = None,
    mfa_required_at: str | None = None,
    mfa_grace_until: str | None = None,
    last_aal2_at: str | None = None,
) -> dict[str, Any]:
    clean_auth_id = str(auth_id or "").strip()

    if not clean_auth_id:
        raise HTTPException(status_code=400, detail="Auth id is required")

    payload: dict[str, Any] = {
        "user_id": user_id,
        "auth_id": clean_auth_id,
    }

    if mfa_required is not None:
        payload["mfa_required"] = bool(mfa_required)

    if mfa_required_at is not None:
        payload["mfa_required_at"] = mfa_required_at

    if mfa_grace_until is not None:
        payload["mfa_grace_until"] = mfa_grace_until

    if last_aal2_at is not None:
        payload["last_aal2_at"] = last_aal2_at

    try:
        response = (
            service_supabase
            .table("user_security_settings")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
    except Exception as error:
        logger.warning(
            "user_security_settings.upsert_failed",
            extra={"user_id": user_id, "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not update user security settings")

    return normalize_security_settings(response.data[0] if response.data else payload) or payload


def set_mfa_required(
    *,
    user_id: int,
    auth_id: str,
    required: bool,
    required_at: str | None = None,
    grace_until: str | None = None,
) -> dict[str, Any]:
    return upsert_user_security_settings(
        user_id=user_id,
        auth_id=auth_id,
        mfa_required=required,
        mfa_required_at=required_at,
        mfa_grace_until=grace_until,
    )


def mark_aal2_verified(
    *,
    user_id: int,
    auth_id: str,
    verified_at: str,
) -> dict[str, Any]:
    return upsert_user_security_settings(
        user_id=user_id,
        auth_id=auth_id,
        last_aal2_at=verified_at,
    )
