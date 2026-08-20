from __future__ import annotations

import logging

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import api_error

logger = logging.getLogger(__name__)


def auth_value(source, key: str):
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def canonical_auth_email(auth_user) -> str:
    return normalize_email(auth_value(auth_user, "email"))


def auth_user_id(auth_user) -> str:
    return str(auth_value(auth_user, "id") or "")


def get_auth_user_by_id(auth_id: str):
    if not auth_id:
        return None

    response = service_supabase.auth.admin.get_user_by_id(str(auth_id))
    return auth_value(response, "user") or response


def find_auth_user_by_email(clean_email: str):
    """Resolve the canonical provider identity without trusting local profile email."""
    clean_email = normalize_email(clean_email)
    if not clean_email:
        return None

    page = 1
    per_page = 1000

    while True:
        try:
            response = service_supabase.auth.admin.list_users(
                page=page,
                per_page=per_page,
            )
        except Exception as error:
            logger.warning(
                "auth.identity.provider_lookup_failed",
                extra={"error_type": type(error).__name__},
            )
            raise api_error(
                503,
                "identity_provider_unavailable",
                "The identity service is temporarily unavailable.",
            ) from error

        users = auth_value(response, "users") or response or []
        if not isinstance(users, (list, tuple)):
            try:
                users = list(users)
            except TypeError:
                users = []

        for auth_user in users:
            if canonical_auth_email(auth_user) == clean_email:
                return auth_user

        if len(users) < per_page:
            return None

        page += 1


def assert_canonical_email_available(
    clean_email: str,
    *,
    allowed_auth_id: str | None = None,
):
    clean_email = normalize_email(clean_email)
    if not clean_email:
        raise api_error(400, "email_required", "Email is required.")

    local_result = (
        service_supabase.table("users")
        .select("id, auth_id, email")
        .eq("email", clean_email)
        .limit(1)
        .execute()
    )
    local_user = local_result.data[0] if local_result.data else None

    if local_user and str(local_user.get("auth_id") or "") != str(allowed_auth_id or ""):
        raise api_error(409, "email_already_registered", "Email is already registered.")

    provider_user = find_auth_user_by_email(clean_email)
    provider_auth_id = auth_user_id(provider_user)

    if provider_user and provider_auth_id != str(allowed_auth_id or ""):
        raise api_error(409, "email_already_registered", "Email is already registered.")

    return provider_user or local_user


def canonical_email_for_local_user(local_user: dict | None) -> str:
    if not local_user or not local_user.get("auth_id"):
        return ""

    try:
        auth_user = get_auth_user_by_id(str(local_user["auth_id"]))
    except HTTPException:
        raise
    except Exception as error:
        logger.warning(
            "auth.identity.provider_user_lookup_failed",
            extra={"error_type": type(error).__name__},
        )
        raise api_error(
            503,
            "identity_provider_unavailable",
            "The identity service is temporarily unavailable.",
        ) from error

    return canonical_auth_email(auth_user)
