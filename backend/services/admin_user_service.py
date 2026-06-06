from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from database import service_supabase


USER_SELECT_COLUMNS = (
    "id, auth_id, tenant_id, first_name, last_name, email, phone, avatar, "
    "user_type, subscription_type, payment_status, created_at, updated_at"
)


def list_users_with_features(
    *,
    page: int = 1,
    page_size: int = 10,
    search: str = "",
) -> dict[str, Any]:
    safe_page = max(int(page or 1), 1)
    safe_page_size = min(max(int(page_size or 10), 1), 50)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
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

        users_response = query.range(start, end).execute()
        count_response = count_query.range(0, 0).execute()
        fetched_users = users_response.data or []
        total_count = count_response.count or 0
        has_next_page = len(fetched_users) > safe_page_size
        users = fetched_users[:safe_page_size]
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
        print("ADMIN USER LIST ERROR:", type(error).__name__)
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
        "pagination": {
            "page": safe_page,
            "page_size": safe_page_size,
            "total_count": total_count,
            "has_next_page": has_next_page,
            "has_previous_page": safe_page > 1,
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
        print("ADMIN USER TYPE UPDATE ERROR:", type(error).__name__)
        raise HTTPException(status_code=500, detail="Could not update user type.")

    if not result.data:
        raise HTTPException(status_code=404, detail="User was not found.")

    return {
        **result.data[0],
        "user_type": result.data[0].get("user_type") or "user",
    }


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
        print("ADMIN USER DELETE FETCH ERROR:", type(error).__name__)
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
            print("ADMIN USER DELETE MEMBERSHIP CHECK ERROR:", type(error).__name__)
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
        print("ADMIN USER DELETE ERROR:", type(error).__name__)
        raise HTTPException(status_code=500, detail="Could not delete user.")

    return {
        "id": target_user.get("id"),
        "auth_id": auth_id,
        "tenant_id": tenant_id,
        "email": target_user.get("email"),
        "tenant_deleted": tenant_should_be_deleted,
    }
