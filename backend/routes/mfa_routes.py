from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from classes import MfaEnrollRequest, MfaEnrollVerifyRequest
from database import supabase
from services.auth_service import get_authenticated_user_row, normalize_user_type
from services.audit_service import (
    MFA_CHALLENGE_FAILED,
    MFA_ENROLL_STARTED,
    MFA_ENROLL_VERIFIED,
    MFA_FACTOR_REMOVED,
    MFA_VERIFIED,
    record_mfa_event,
)
from services.user_security_settings_service import (
    get_user_security_settings,
    mark_aal2_verified,
)

router = APIRouter(prefix="/auth/mfa", tags=["MFA"])
logger = logging.getLogger(__name__)


def read_value(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]

        if hasattr(value, name):
            return getattr(value, name)

    return None


def response_data(response: Any) -> Any:
    return read_value(response, "data") or response


def normalize_factor(factor: Any) -> dict[str, Any]:
    return {
        "id": read_value(factor, "id", "factor_id"),
        "factor_type": read_value(factor, "factor_type", "type"),
        "status": read_value(factor, "status"),
        "friendly_name": read_value(factor, "friendly_name"),
        "created_at": read_value(factor, "created_at"),
        "updated_at": read_value(factor, "updated_at"),
        "last_challenged_at": read_value(factor, "last_challenged_at"),
    }


def compact_factor(factor: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in factor.items() if value is not None}


def factor_list_from_response(response: Any) -> list[dict[str, Any]]:
    data = response_data(response)
    raw_factors = read_value(data, "all")

    if raw_factors is None:
        raw_factors = read_value(data, "totp")

    if raw_factors is None and isinstance(data, list):
        raw_factors = data

    if raw_factors is None:
        raw_factors = []

    return [compact_factor(normalize_factor(factor)) for factor in raw_factors]


def totp_payload_from_enroll_response(response: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    data = response_data(response)
    factor = compact_factor(normalize_factor(data))
    totp = read_value(data, "totp") or {}

    safe_totp = {
        "qr_code": read_value(totp, "qr_code", "qrCode"),
        "uri": read_value(totp, "uri"),
    }
    safe_totp = {key: value for key, value in safe_totp.items() if value}

    return factor, safe_totp


def challenge_id_from_response(response: Any) -> str | None:
    data = response_data(response)
    challenge_id = read_value(data, "id", "challenge_id")
    return str(challenge_id) if challenge_id else None


def aal_payload_from_response(response: Any) -> dict[str, Any]:
    data = response_data(response)
    current_level = read_value(data, "current_level", "currentLevel", "aal")
    next_level = read_value(data, "next_level", "nextLevel")

    return {
        "current_level": current_level,
        "next_level": next_level,
    }


def authenticated_mfa_context(request: Request, response: Response):
    auth_user, user_data = get_authenticated_user_row(request, response)
    settings = get_user_security_settings(user_data.get("id"))

    return auth_user, user_data, settings


def current_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_authenticator_assurance_level() -> dict[str, Any]:
    try:
        get_aal = getattr(supabase.auth.mfa, "get_authenticator_assurance_level", None)

        if not get_aal:
            return {}

        return aal_payload_from_response(get_aal())

    except Exception as error:
        logger.warning(
            "auth.mfa.aal_lookup_failed",
            extra={"error_type": type(error).__name__},
        )
        return {}


@router.get("/status")
def mfa_status(request: Request, response: Response):
    _, user_data, settings = authenticated_mfa_context(request, response)
    factors = factor_list_from_response(supabase.auth.mfa.list_factors())
    aal = get_authenticator_assurance_level()

    return {
        "mfa_required": bool((settings or {}).get("mfa_required")),
        "mfa_required_at": (settings or {}).get("mfa_required_at"),
        "mfa_grace_until": (settings or {}).get("mfa_grace_until"),
        "last_aal2_at": (settings or {}).get("last_aal2_at"),
        "user_type": normalize_user_type(user_data.get("user_type")),
        "aal": aal,
        "factors": factors,
    }


@router.post("/enroll")
def mfa_enroll(payload: MfaEnrollRequest, request: Request, response: Response):
    _, user_data, _ = authenticated_mfa_context(request, response)
    enroll_payload = {"factor_type": "totp"}

    friendly_name = (payload.friendly_name or "").strip()

    if friendly_name:
        enroll_payload["friendly_name"] = friendly_name

    try:
        enroll_response = supabase.auth.mfa.enroll(enroll_payload)
    except Exception as error:
        logger.warning(
            "auth.mfa.enroll_failed",
            extra={"user_id": user_data.get("id"), "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=400, detail="Could not start MFA enrollment")

    factor, totp = totp_payload_from_enroll_response(enroll_response)
    factor_id = factor.get("id")

    record_mfa_event(
        request=request,
        tenant_id=user_data.get("tenant_id"),
        actor_user_id=user_data.get("id"),
        action=MFA_ENROLL_STARTED,
        target_user_id=user_data.get("id"),
        factor_id=factor_id,
        metadata={"factor_type": "totp"},
    )

    return {
        "factor": factor,
        "totp": totp,
    }


@router.post("/enroll/verify")
def mfa_enroll_verify(payload: MfaEnrollVerifyRequest, request: Request, response: Response):
    _, user_data, _ = authenticated_mfa_context(request, response)
    factor_id = payload.factor_id.strip()

    try:
        challenge_response = supabase.auth.mfa.challenge({"factor_id": factor_id})
        challenge_id = challenge_id_from_response(challenge_response)

        if not challenge_id:
            raise ValueError("Missing MFA challenge id")

        supabase.auth.mfa.verify(
            {
                "factor_id": factor_id,
                "challenge_id": challenge_id,
                "code": payload.code.strip(),
            }
        )

    except Exception as error:
        logger.warning(
            "auth.mfa.enroll_verify_failed",
            extra={"user_id": user_data.get("id"), "error_type": type(error).__name__},
        )
        record_mfa_event(
            request=request,
            tenant_id=user_data.get("tenant_id"),
            actor_user_id=user_data.get("id"),
            action=MFA_CHALLENGE_FAILED,
            target_user_id=user_data.get("id"),
            factor_id=factor_id,
            metadata={"factor_type": "totp", "stage": "enroll_verify"},
        )
        raise HTTPException(status_code=400, detail="Could not verify MFA code")

    record_mfa_event(
        request=request,
        tenant_id=user_data.get("tenant_id"),
        actor_user_id=user_data.get("id"),
        action=MFA_ENROLL_VERIFIED,
        target_user_id=user_data.get("id"),
        factor_id=factor_id,
        metadata={"factor_type": "totp"},
    )
    record_mfa_event(
        request=request,
        tenant_id=user_data.get("tenant_id"),
        actor_user_id=user_data.get("id"),
        action=MFA_VERIFIED,
        target_user_id=user_data.get("id"),
        factor_id=factor_id,
        metadata={"factor_type": "totp", "stage": "enroll_verify"},
    )

    try:
        mark_aal2_verified(
            user_id=user_data.get("id"),
            auth_id=str(user_data.get("auth_id") or ""),
            verified_at=current_utc_iso(),
        )
    except Exception as error:
        logger.warning(
            "auth.mfa.aal2_tracking_failed",
            extra={"user_id": user_data.get("id"), "error_type": type(error).__name__},
        )

    return {
        "verified": True,
        "factor_id": factor_id,
    }


@router.get("/factors")
def mfa_factors(request: Request, response: Response):
    authenticated_mfa_context(request, response)
    return {"factors": factor_list_from_response(supabase.auth.mfa.list_factors())}


@router.delete("/factors/{factor_id}")
def mfa_remove_factor(factor_id: str, request: Request, response: Response):
    _, user_data, _ = authenticated_mfa_context(request, response)
    clean_factor_id = str(factor_id or "").strip()

    if not clean_factor_id:
        raise HTTPException(status_code=400, detail="MFA factor id is required")

    try:
        supabase.auth.mfa.unenroll({"factor_id": clean_factor_id})
    except Exception as error:
        logger.warning(
            "auth.mfa.factor_remove_failed",
            extra={"user_id": user_data.get("id"), "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=400, detail="Could not remove MFA factor")

    record_mfa_event(
        request=request,
        tenant_id=user_data.get("tenant_id"),
        actor_user_id=user_data.get("id"),
        action=MFA_FACTOR_REMOVED,
        target_user_id=user_data.get("id"),
        factor_id=clean_factor_id,
        metadata={"factor_type": "totp"},
    )

    return {
        "removed": True,
        "factor_id": clean_factor_id,
    }
