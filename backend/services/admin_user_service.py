from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from database import service_supabase

logger = logging.getLogger(__name__)


USER_SELECT_COLUMNS = (
    "id, auth_id, tenant_id, first_name, last_name, email, phone, avatar, "
    "user_type, subscription_type, payment_status, created_at, updated_at"
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

    try:
        result = (
            service_supabase
            .table("users")
            .update({"user_type": normalized_user_type})
            .eq("id", user_id)
            .execute()
        )

    except Exception as error:
        logger.warning("admin.user_type.update_failed", extra={"target_user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not update user type.")

    if not result.data:
        raise HTTPException(status_code=404, detail="User was not found.")

    updated_user = {
        **result.data[0],
        "user_type": result.data[0].get("user_type") or "user",
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
            .select("id, auth_id, tenant_id, email, first_name, last_name")
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
        "tenant_deleted": tenant_should_be_deleted,
    }
