from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import error_detail
from services.user_security_settings_service import set_mfa_required

logger = logging.getLogger(__name__)


USER_SELECT_COLUMNS = (
    "id, auth_id, tenant_id, first_name, last_name, email, phone, avatar, "
    "user_type, email_verified, account_status, subscription_type, payment_status, created_at, updated_at"
)


def _load_admin_target(user_id: int) -> dict[str, Any]:
    try:
        response = (
            service_supabase
            .table("users")
            .select("id, auth_id, tenant_id, email, email_verified, account_status, user_type")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.warning(
            "admin.user.fetch_failed",
            extra={"target_user_id": user_id, "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not load user.")

    if not response.data:
        raise HTTPException(status_code=404, detail="User was not found.")
    return response.data[0]


def _assert_not_last_system_admin(target_user: dict[str, Any]) -> None:
    if str(target_user.get("user_type") or "user").strip().lower() != "admin":
        return
    if str(target_user.get("account_status") or "").strip().lower() != "active":
        return

    try:
        response = (
            service_supabase
            .table("users")
            .select("id", count="exact")
            .eq("user_type", "admin")
            .eq("account_status", "active")
            .neq("id", target_user.get("id"))
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.warning(
            "admin.last_admin_check_failed",
            extra={
                "target_user_id": target_user.get("id"),
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=500, detail="Could not verify system admin safety.")

    remaining_admins = getattr(response, "count", None)
    if remaining_admins is None:
        remaining_admins = len(response.data or [])
    if int(remaining_admins or 0) < 1:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "last_system_admin_required",
                "At least one active system administrator is required.",
            ),
        )


def list_users_with_features(
    *,
    page: int = 1,
    page_size: int = 10,
    limit: int | None = None,
    offset: int | None = None,
    search: str = "",
) -> dict[str, Any]:
    safe_limit = min(max(int(limit or page_size or 20), 1), 100)
    if offset is None:
        safe_page = max(int(page or 1), 1)
        safe_offset = (safe_page - 1) * safe_limit
    else:
        safe_offset = max(int(offset or 0), 0)
        safe_page = (safe_offset // safe_limit) + 1
    end = safe_offset + safe_limit
    normalized_search = str(search or "").strip()

    try:
        query = (
            service_supabase
            .table("users")
            .select(USER_SELECT_COLUMNS)
            .order("created_at", desc=True)
        )

        if normalized_search:
            query = query.ilike("email", f"%{normalized_search}%")

        count_query = service_supabase.table("users").select("id", count="exact")

        if normalized_search:
            count_query = count_query.ilike("email", f"%{normalized_search}%")

        users_response = query.range(safe_offset, end).execute()
        count_response = count_query.range(0, 0).execute()
        fetched_users = users_response.data or []
        total_count = count_response.count or 0
        has_more = len(fetched_users) > safe_limit
        users = fetched_users[:safe_limit]
        tenant_ids = sorted({
            user.get("tenant_id")
            for user in users
            if user.get("tenant_id") is not None
        })

        features_by_tenant: dict[str, list[dict[str, Any]]] = {}

        if tenant_ids:
            features_response = (
                service_supabase
                .table("features")
                .select("id, tenant_id, subscription_type, plan, builder_type, payment_status")
                .in_("tenant_id", tenant_ids)
                .execute()
            )

            for feature in features_response.data or []:
                tenant_key = str(feature.get("tenant_id"))
                features_by_tenant.setdefault(tenant_key, []).append(feature)

    except Exception as error:
        logger.warning("admin.users.list_failed", extra={"error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not load users.")

    enriched_users = [
        {
            **user,
            "user_type": user.get("user_type") or "user",
            "features": features_by_tenant.get(str(user.get("tenant_id")), []),
        }
        for user in users
    ]

    return {
        "users": enriched_users,
        "items": enriched_users,
        "pagination": {
            "limit": safe_limit,
            "offset": safe_offset,
            "count": len(enriched_users),
            "has_more": has_more,
            "page": safe_page,
            "page_size": safe_limit,
            "total_count": total_count,
            "has_next_page": has_more,
            "has_previous_page": safe_offset > 0,
        },
    }


def update_user_type(*, user_id: int, user_type: str) -> dict[str, Any]:
    normalized_user_type = str(user_type or "").strip().lower()

    if normalized_user_type not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Invalid user type.")

    target_user = _load_admin_target(user_id)
    old_user_type = str(target_user.get("user_type") or "user").strip().lower()
    if old_user_type == normalized_user_type:
        return {**target_user, "user_type": normalized_user_type, "old_user_type": old_user_type}

    if normalized_user_type == "user":
        _assert_not_last_system_admin(target_user)
    elif target_user.get("email_verified") is not True:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "email_verification_required",
                "The account email must be verified before admin promotion.",
            ),
        )
    elif target_user.get("account_status") not in {None, "active"}:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "account_inactive",
                "Only an active account can be promoted to system administrator.",
            ),
        )

    required_at = datetime.now(timezone.utc).isoformat()
    rpc = getattr(service_supabase, "rpc", None)
    try:
        if callable(rpc):
            result = rpc(
                "admin_update_user_type_safely",
                {
                    "p_user_id": user_id,
                    "p_new_user_type": normalized_user_type,
                    "p_required_at": required_at,
                },
            ).execute()
        else:
            # Kept for focused unit-test doubles. Deployed Supabase clients use the
            # transaction-safe RPC and database last-admin trigger.
            if normalized_user_type == "admin":
                set_mfa_required(
                    user_id=user_id,
                    auth_id=str(target_user.get("auth_id") or ""),
                    required=True,
                    required_at=required_at,
                )
            result = (
                service_supabase
                .table("users")
                .update({"user_type": normalized_user_type})
                .eq("id", user_id)
                .execute()
            )

    except Exception as error:
        error_text = str(error).lower()
        if "last_system_admin_required" in error_text:
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "last_system_admin_required",
                    "At least one active system administrator is required.",
                ),
            )
        if "email_verification_required" in error_text:
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "email_verification_required",
                    "The account email must be verified before admin promotion.",
                ),
            )
        if "user_not_found" in error_text:
            raise HTTPException(status_code=404, detail="User was not found.")
        logger.warning("admin.user_type.update_failed", extra={"target_user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not update user type.")

    result_data = result.data or []
    if isinstance(result_data, dict):
        updated_row = result_data.get("result") if isinstance(result_data.get("result"), dict) else result_data
    else:
        updated_row = result_data[0] if result_data else None
        if isinstance(updated_row, dict) and isinstance(updated_row.get("result"), dict):
            updated_row = updated_row["result"]

    if not updated_row:
        raise HTTPException(status_code=404, detail="User was not found.")

    updated_user = {
        **updated_row,
        "user_type": updated_row.get("user_type") or "user",
        "old_user_type": old_user_type,
    }
    logger.info(
        "admin.user_type_changed",
        extra={"target_user_id": user_id, "user_type": updated_user.get("user_type")},
    )
    return updated_user


def delete_user_account(*, user_id: int, requesting_user_id: int | None = None) -> dict[str, Any]:
    if requesting_user_id is not None and int(user_id) == int(requesting_user_id):
        raise HTTPException(status_code=400, detail="Admins cannot delete their own account.")

    try:
        user_result = (
            service_supabase
            .table("users")
            .select("id, auth_id, tenant_id, email, first_name, last_name, account_status, user_type")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

    except Exception as error:
        logger.warning("admin.user_delete.fetch_failed", extra={"target_user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not load user for deletion.")

    if not user_result.data:
        raise HTTPException(status_code=404, detail="User was not found.")

    target_user = user_result.data[0]
    _assert_not_last_system_admin(target_user)
    auth_id = str(target_user.get("auth_id") or "").strip()
    tenant_id = target_user.get("tenant_id")
    tenant_should_be_deleted = False

    if tenant_id is not None:
        try:
            remaining_members = (
                service_supabase
                .table("tenant_memberships")
                .select("id")
                .eq("tenant_id", tenant_id)
                .neq("user_id", user_id)
                .limit(1)
                .execute()
            )
            tenant_should_be_deleted = not bool(remaining_members.data)

        except Exception as error:
            logger.warning("admin.user_delete.membership_check_failed", extra={"target_user_id": user_id, "tenant_id": tenant_id, "error_type": type(error).__name__})
            raise HTTPException(status_code=500, detail="Could not verify tenant membership.")

    try:
        if auth_id:
            service_supabase.auth.admin.delete_user(auth_id)
        else:
            (
                service_supabase
                .table("users")
                .delete()
                .eq("id", user_id)
                .execute()
            )

        if tenant_should_be_deleted and tenant_id is not None:
            (
                service_supabase
                .table("tenants")
                .delete()
                .eq("tenant_id", tenant_id)
                .execute()
            )

    except Exception as error:
        if "last_system_admin_required" in str(error).lower():
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "last_system_admin_required",
                    "At least one active system administrator is required.",
                ),
            )
        logger.warning("admin.user_delete.failed", extra={"target_user_id": user_id, "tenant_id": tenant_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not delete user.")

    logger.info(
        "admin.user_deleted",
        extra={
            "target_user_id": target_user.get("id"),
            "tenant_id": tenant_id,
            "tenant_deleted": tenant_should_be_deleted,
            "requesting_user_id": requesting_user_id,
        },
    )

    return {
        "id": target_user.get("id"),
        "auth_id": auth_id,
        "tenant_id": tenant_id,
        "email": target_user.get("email"),
        "user_type": target_user.get("user_type") or "user",
        "tenant_deleted": tenant_should_be_deleted,
    }
