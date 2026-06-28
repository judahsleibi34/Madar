from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from classes import (
    MfaEnrollRequest,
    MfaEnrollVerifyRequest,
    MfaLoginChallengeRequest,
    MfaLoginVerifyRequest,
)
from database import service_supabase, supabase
from services.auth_service import (
    build_user_payload,
    get_authenticated_user_row,
    normalize_user_type,
    set_auth_cookies,
)
from services.audit_service import (
    MFA_CHALLENGE_FAILED,
    MFA_ENROLL_STARTED,
    MFA_ENROLL_VERIFIED,
    MFA_FACTOR_REMOVED,
    MFA_LOGIN_CHALLENGE_STARTED,
    MFA_LOGIN_FAILED,
    MFA_LOGIN_VERIFIED,
    MFA_VERIFIED,
    record_mfa_event,
    record_security_event,
)
from services.mfa_login_service import (
    aal_payload_from_response as login_aal_payload_from_response,
    clear_pending_mfa_cookie,
    create_pending_mfa_client,
    get_session_from_verify_response,
    read_pending_mfa_cookie,
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


def session_tokens_from_response(response: Any) -> tuple[str | None, str | None]:
    session = get_session_from_verify_response(response)

    if not session:
        return None, None

    access_token = read_value(session, "access_token")
    refresh_token = read_value(session, "refresh_token")

    return access_token, refresh_token


def sanitized_exception_metadata(error: Exception) -> dict[str, Any]:
    metadata = {"error_type": type(error).__name__}

    for attr in ("status", "code", "message"):
        value = getattr(error, attr, None)

        if value is not None:
            metadata[attr] = str(value)

    if "message" not in metadata:
        message = str(error).strip()

        if message:
            metadata["message"] = message

    return metadata


def get_local_user_for_pending_mfa(pending_payload: dict[str, Any]):
    user_id = pending_payload.get("user_id")
    auth_id = str(pending_payload.get("auth_id") or "")
    query = service_supabase.table("users").select("*")

    if user_id is not None:
        result = query.eq("id", user_id).limit(1).execute()
    else:
        result = query.eq("auth_id", auth_id).limit(1).execute()

    if result.data:
        return result.data[0]

    return None


def require_pending_mfa_payload(request: Request, response: Response) -> dict[str, Any]:
    pending_payload = read_pending_mfa_cookie(request)

    if not pending_payload:
        clear_pending_mfa_cookie(response)
        raise HTTPException(status_code=401, detail="MFA login session expired")

    return pending_payload


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

        verify_response = supabase.auth.mfa.verify(
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

    access_token, refresh_token = session_tokens_from_response(verify_response)

    if access_token and refresh_token:
        set_auth_cookies(response, access_token, refresh_token)

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

    aal = get_authenticator_assurance_level()
    current_level = aal.get("current_level")

    if current_level and current_level != "aal2":
        raise HTTPException(
            status_code=403,
            detail="MFA verification required before removing this factor",
        )

    try:
        supabase.auth.mfa.unenroll({"factor_id": clean_factor_id})
    except Exception as error:
        logger.warning(
            "auth.mfa.factor_remove_failed",
            extra={
                "user_id": user_data.get("id"),
                **sanitized_exception_metadata(error),
            },
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


@router.post("/login/challenge")
def mfa_login_challenge(
    payload: MfaLoginChallengeRequest,
    request: Request,
    response: Response,
):
    pending_payload = require_pending_mfa_payload(request, response)
    factor_id = payload.factor_id.strip()

    try:
        mfa_client = create_pending_mfa_client(pending_payload)
        challenge_response = mfa_client.auth.mfa.challenge({"factor_id": factor_id})
        challenge_id = challenge_id_from_response(challenge_response)

        if not challenge_id:
            raise ValueError("Missing MFA challenge id")

    except Exception as error:
        logger.warning(
            "auth.mfa.login_challenge_failed",
            extra={"user_id": pending_payload.get("user_id"), "error_type": type(error).__name__},
        )
        clear_pending_mfa_cookie(response)
        record_mfa_event(
            request=request,
            tenant_id=pending_payload.get("tenant_id"),
            actor_user_id=pending_payload.get("user_id"),
            action=MFA_CHALLENGE_FAILED,
            target_user_id=pending_payload.get("user_id"),
            factor_id=factor_id,
            metadata={"factor_type": "totp", "stage": "login_challenge"},
        )
        raise HTTPException(status_code=400, detail="Could not start MFA challenge")

    record_mfa_event(
        request=request,
        tenant_id=pending_payload.get("tenant_id"),
        actor_user_id=pending_payload.get("user_id"),
        action=MFA_LOGIN_CHALLENGE_STARTED,
        target_user_id=pending_payload.get("user_id"),
        factor_id=factor_id,
        metadata={"factor_type": "totp"},
    )

    return {"challenge_id": challenge_id}


@router.post("/login/verify")
def mfa_login_verify(
    payload: MfaLoginVerifyRequest,
    request: Request,
    response: Response,
):
    pending_payload = require_pending_mfa_payload(request, response)
    factor_id = payload.factor_id.strip()

    try:
        mfa_client = create_pending_mfa_client(pending_payload)

        if payload.challenge_id:
            verify_response = mfa_client.auth.mfa.verify(
                {
                    "factor_id": factor_id,
                    "challenge_id": payload.challenge_id.strip(),
                    "code": payload.code.strip(),
                }
            )
        else:
            verify_response = mfa_client.auth.mfa.challenge_and_verify(
                {"factor_id": factor_id, "code": payload.code.strip()}
            )

        aal = {}
        get_aal = getattr(mfa_client.auth.mfa, "get_authenticator_assurance_level", None)

        if get_aal:
            aal = login_aal_payload_from_response(get_aal())
            if aal.get("current_level") and aal.get("current_level") != "aal2":
                raise ValueError("MFA verification did not produce aal2")

        session = get_session_from_verify_response(verify_response)

        if not session:
            session_response = mfa_client.auth.get_session()
            session = getattr(session_response, "session", None) or session_response

        access_token = getattr(session, "access_token", None) or (
            session.get("access_token") if isinstance(session, dict) else None
        )
        refresh_token = getattr(session, "refresh_token", None) or (
            session.get("refresh_token") if isinstance(session, dict) else None
        )

        if not access_token or not refresh_token:
            raise ValueError("MFA verification did not return a session")

        local_user = get_local_user_for_pending_mfa(pending_payload)

        if not local_user:
            raise HTTPException(status_code=404, detail="User not found")

        csrf_token = set_auth_cookies(response, access_token, refresh_token)
        clear_pending_mfa_cookie(response)

        try:
            mark_aal2_verified(
                user_id=local_user.get("id"),
                auth_id=str(local_user.get("auth_id") or pending_payload.get("auth_id") or ""),
                verified_at=current_utc_iso(),
            )
        except Exception as error:
            logger.warning(
                "auth.mfa.login_aal2_tracking_failed",
                extra={"user_id": local_user.get("id"), "error_type": type(error).__name__},
            )

        record_security_event(
            request=request,
            tenant_id=local_user.get("tenant_id"),
            actor_user_id=local_user.get("id"),
            action="auth.login_succeeded",
            target_type="user",
            target_id=local_user.get("id"),
            metadata={"login_method": "credentials_mfa"},
        )
        record_mfa_event(
            request=request,
            tenant_id=local_user.get("tenant_id"),
            actor_user_id=local_user.get("id"),
            action=MFA_LOGIN_VERIFIED,
            target_user_id=local_user.get("id"),
            factor_id=factor_id,
            metadata={"factor_type": "totp", "aal": aal},
        )
        record_mfa_event(
            request=request,
            tenant_id=local_user.get("tenant_id"),
            actor_user_id=local_user.get("id"),
            action=MFA_VERIFIED,
            target_user_id=local_user.get("id"),
            factor_id=factor_id,
            metadata={"factor_type": "totp", "stage": "login"},
        )

        return {
            "message": "User is logged in",
            "user": build_user_payload(local_user),
            "csrf_token": csrf_token,
        }

    except HTTPException:
        clear_pending_mfa_cookie(response)
        raise

    except Exception as error:
        logger.warning(
            "auth.mfa.login_verify_failed",
            extra={"user_id": pending_payload.get("user_id"), "error_type": type(error).__name__},
        )
        clear_pending_mfa_cookie(response)
        record_mfa_event(
            request=request,
            tenant_id=pending_payload.get("tenant_id"),
            actor_user_id=pending_payload.get("user_id"),
            action=MFA_LOGIN_FAILED,
            target_user_id=pending_payload.get("user_id"),
            factor_id=factor_id,
            metadata={"factor_type": "totp", "stage": "login_verify"},
        )
        record_mfa_event(
            request=request,
            tenant_id=pending_payload.get("tenant_id"),
            actor_user_id=pending_payload.get("user_id"),
            action=MFA_CHALLENGE_FAILED,
            target_user_id=pending_payload.get("user_id"),
            factor_id=factor_id,
            metadata={"factor_type": "totp", "stage": "login_verify"},
        )
        raise HTTPException(status_code=400, detail="Could not verify MFA code")
