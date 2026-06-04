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
    exclude_user_id: int | None = None,
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

        if exclude_user_id is not None:
            query = query.neq("id", exclude_user_id)

        users_response = query.range(start, end).execute()
        fetched_users = users_response.data or []
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
