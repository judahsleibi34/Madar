import re

from fastapi import APIRouter, HTTPException, Request

from database import service_supabase
from services.rate_limit_service import enforce_public_rate_limit

router = APIRouter(prefix="/public", tags=["Public Sites"])

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_subdomain(value: str) -> str:
    subdomain = (value or "").strip().lower()

    if not subdomain or not SUBDOMAIN_PATTERN.match(subdomain):
        raise HTTPException(status_code=404, detail="Published site not found")

    return subdomain


def resolve_website_settings(subdomain: str):
    settings_response = (
        service_supabase.table("website_settings")
        .select("*")
        .eq("subdomain", subdomain)
        .limit(1)
        .execute()
    )

    settings_rows = getattr(settings_response, "data", None) or []

    if not settings_rows:
        raise HTTPException(status_code=404, detail="Published site not found")

    return settings_rows[0]


def resolve_tenant_id(settings: dict):
    tenant_id = settings.get("tenant_id")

    if tenant_id is not None:
        return tenant_id

    user_id = settings.get("user_id")

    if user_id is None:
        raise HTTPException(status_code=404, detail="Published site not found")

    user_response = (
        service_supabase.table("users")
        .select("tenant_id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    user_rows = getattr(user_response, "data", None) or []
    tenant_id = (user_rows[0] if user_rows else {}).get("tenant_id")

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Published site not found")

    return tenant_id


@router.get("/sites/{subdomain}")
def get_public_site(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "site_lookup", clean_subdomain)
    settings = resolve_website_settings(clean_subdomain)
    tenant_id = resolve_tenant_id(settings)

    project_response = (
        service_supabase.table("builder_projects")
        .select(
            "id, tenant_id, name, slug, status, published_schema, "
            "published_version, last_published_at, updated_at"
        )
        .eq("tenant_id", tenant_id)
        .eq("status", "published")
        .not_.is_("published_schema", "null")
        .order("last_published_at", desc=True)
        .limit(1)
        .execute()
    )

    if not project_response.data:
        raise HTTPException(status_code=404, detail="Published site not found")

    project = project_response.data[0]

    return {
        "success": True,
        "site": {
            "subdomain": clean_subdomain,
            "tenant_id": tenant_id,
            "brand": settings.get("brand"),
            "footer_store_name": settings.get("footer_store_name"),
            "logo_url": settings.get("logo_url"),
            "contact_email": settings.get("contact_email"),
            "phone": settings.get("phone"),
            "description": settings.get("description"),
        },
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "slug": project.get("slug"),
            "status": project.get("status"),
            "published_version": project.get("published_version"),
            "last_published_at": project.get("last_published_at"),
            "published_schema": project.get("published_schema") or {},
        },
    }
