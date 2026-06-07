from fastapi import HTTPException

from database import service_supabase


def _rows(response):
    return getattr(response, "data", None) or []


def first_row(response):
    rows = _rows(response)
    return rows[0] if rows else None


def get_settings_for_tenant(tenant_id: int, user_id: int | None = None):
    tenant_response = (
        service_supabase.table("website_settings")
        .select("*")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )

    settings = first_row(tenant_response)

    if settings:
        return settings

    if user_id is None:
        return None

    user_response = (
        service_supabase.table("website_settings")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    settings = first_row(user_response)

    if not settings:
        return None

    if settings.get("tenant_id") is None:
        update_response = (
            service_supabase.table("website_settings")
            .update({"tenant_id": tenant_id})
            .eq("id", settings["id"])
            .execute()
        )
        return first_row(update_response) or {**settings, "tenant_id": tenant_id}

    if settings.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=409, detail="Website settings belong to another tenant")

    return settings


def ensure_settings_for_tenant(tenant_id: int, user_id: int):
    settings = get_settings_for_tenant(tenant_id, user_id)

    if settings:
        return settings

    insert_payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
    }

    try:
        insert_response = service_supabase.table("website_settings").insert(insert_payload).execute()
        return first_row(insert_response) or insert_payload
    except Exception as error:
        if "duplicate" not in str(error).lower() and "unique" not in str(error).lower():
            raise

        settings = get_settings_for_tenant(tenant_id, user_id)
        if settings:
            return settings

        raise


def save_settings_for_tenant(tenant_id: int, user_id: int, update_payload: dict):
    update_payload = {
        **update_payload,
        "tenant_id": tenant_id,
    }
    existing_website = get_settings_for_tenant(tenant_id, user_id)

    if existing_website:
        save_response = (
            service_supabase.table("website_settings")
            .update(update_payload)
            .eq("id", existing_website["id"])
            .execute()
        )
    else:
        insert_payload = {
            **update_payload,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

        save_response = (
            service_supabase.table("website_settings")
            .insert(insert_payload)
            .execute()
        )

    return (
        first_row(save_response)
        or {
            **(existing_website or {}),
            **update_payload,
        }
    )


def require_public_subdomain(tenant_id: int, user_id: int):
    settings = ensure_settings_for_tenant(tenant_id, user_id)
    subdomain = (settings.get("subdomain") or "").strip().lower()

    if not subdomain:
        raise HTTPException(
            status_code=400,
            detail="Configure a website subdomain before going live.",
        )

    return settings
