import re
import logging

from fastapi import APIRouter, HTTPException, Request, Response

from classes import WebsiteSettingsUpdate
from services.auth_service import require_regular_user, require_regular_user_id
from services.url_validation import validate_public_url
from services.website_settings_service import ensure_settings_for_tenant, save_settings_for_tenant

router = APIRouter(tags=["Website"])
logger = logging.getLogger(__name__)

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def clean_string(value):
    if value is None:
        return None

    return str(value).strip()


def validate_subdomain(value: str):
    clean_value = clean_string(value).lower()

    if not clean_value:
        raise HTTPException(status_code=400, detail="Subdomain name is required")

    if not SUBDOMAIN_PATTERN.match(clean_value):
        raise HTTPException(
            status_code=400,
            detail="Subdomain can only contain lowercase letters, numbers, and hyphens",
        )

    return clean_value


def validate_brand(value: str):
    clean_value = clean_string(value)

    if not clean_value:
        raise HTTPException(status_code=400, detail="Brand name is required")

    if len(clean_value) > 80:
        raise HTTPException(
            status_code=400,
            detail="Brand name must be 80 characters or less",
        )

    return clean_value


def validate_footer_name(value: str):
    clean_value = clean_string(value)

    if not clean_value:
        return ""

    if len(clean_value) > 80:
        raise HTTPException(
            status_code=400,
            detail="Footer name must be 80 characters or less",
        )

    return clean_value


def validate_logo_url(value: str):
    return validate_public_url(
        value,
        field_name="Logo URL",
        allow_relative=True,
    )


def validate_contact_email(value: str):
    clean_value = clean_string(value).lower()

    if not clean_value:
        return ""

    if "@" not in clean_value or "." not in clean_value.split("@")[-1]:
        raise HTTPException(
            status_code=400,
            detail="Contact email must be valid",
        )

    return clean_value


def validate_phone(value: str):
    clean_value = clean_string(value)

    if not clean_value:
        return ""

    if len(clean_value) > 30:
        raise HTTPException(
            status_code=400,
            detail="Contact phone must be 30 characters or less",
        )

    return clean_value


def validate_description(value: str):
    clean_value = clean_string(value)

    if not clean_value:
        return ""

    if len(clean_value) > 500:
        raise HTTPException(
            status_code=400,
            detail="Website description must be 500 characters or less",
        )

    return clean_value


def get_website_user_context(request: Request, response: Response):
    path_user_id = request.path_params.get("user_id")

    if path_user_id is None:
        return require_regular_user(request, response)

    return require_regular_user_id(path_user_id, request, response)


def get_tenant_context(user_data):
    user_id = user_data["id"]
    tenant_id = user_data.get("tenant_id")

    if tenant_id is None:
        raise HTTPException(status_code=403, detail="User does not belong to a tenant")

    return tenant_id, user_id


def build_settings_update_payload(settings: WebsiteSettingsUpdate):
    update_payload = {}

    if settings.subdomain is not None:
        update_payload["subdomain"] = validate_subdomain(settings.subdomain)

    if settings.brand is not None:
        update_payload["brand"] = validate_brand(settings.brand)

    if settings.footer_store_name is not None:
        update_payload["footer_store_name"] = validate_footer_name(
            settings.footer_store_name
        )

    if settings.logo_url is not None:
        update_payload["logo_url"] = validate_logo_url(settings.logo_url)

    if settings.contact_email is not None:
        update_payload["contact_email"] = validate_contact_email(
            settings.contact_email
        )

    if settings.phone is not None:
        update_payload["phone"] = validate_phone(settings.phone)

    if settings.description is not None:
        update_payload["description"] = validate_description(settings.description)

    return update_payload


@router.put("/users/{user_id}/website/settings")
@router.put("/website/settings")
def update_website_settings(
    settings: WebsiteSettingsUpdate,
    request: Request,
    response: Response,
    user_id: int | None = None,
):
    try:
        _, user_data = get_website_user_context(request, response)
        update_payload = build_settings_update_payload(settings)

        if not update_payload:
            return {
                "success": True,
                "message": "No website settings changed",
                "website": None,
            }

        tenant_id, authenticated_user_id = get_tenant_context(user_data)

        updated_website = save_settings_for_tenant(
            tenant_id=tenant_id,
            user_id=authenticated_user_id,
            update_payload=update_payload,
        )

        return {
            "success": True,
            "message": "Website settings updated successfully",
            "website": updated_website,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("website.settings.update_failed", extra={"user_id": user_id, "error_type": type(e).__name__})
        raise HTTPException(
            status_code=500,
            detail="Could not update website settings",
        )


@router.get("/users/{user_id}/website/settings")
@router.get("/website/settings")
def get_website_settings(
    request: Request,
    response: Response,
    user_id: int | None = None,
):
    try:
        _, user_data = get_website_user_context(request, response)
        tenant_id, authenticated_user_id = get_tenant_context(user_data)

        website = ensure_settings_for_tenant(tenant_id, authenticated_user_id)

        return {
            "success": True,
            "message": "Website settings fetched successfully",
            "website": website,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.warning("website.settings.fetch_failed", extra={"user_id": user_id, "error_type": type(e).__name__})
        raise HTTPException(
            status_code=500,
            detail="Could not fetch website settings",
        )
