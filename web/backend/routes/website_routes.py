import logging

from fastapi import APIRouter, HTTPException, Request, Response

from classes import WebsiteSettingsUpdate
from services.audit_service import record_audit_event
from services.tenant_service import require_active_tenant_member
from services.url_validation import validate_public_url
from services.website_settings_service import get_settings_for_tenant, ensure_settings_for_tenant, save_settings_for_tenant
from services.entitlement_service import (
    require_any_entitlement,
    require_branded_subdomain,
)
from services.hosted_address_service import validate_hosted_address

router = APIRouter(tags=["Website"])
logger = logging.getLogger(__name__)

def clean_string(value):
    if value is None:
        return None

    return str(value).strip()


def validate_subdomain(value: str):
    return validate_hosted_address(value, label="Subdomain name")


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


def get_website_tenant_context(request: Request, response: Response):
    context = require_active_tenant_member(request, response)
    path_user_id = request.path_params.get("user_id")

    if path_user_id is not None:
        try:
            if int(context.user_id) != int(path_user_id):
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(status_code=403, detail="User id does not match session")

    return context


def build_settings_update_payload(settings: WebsiteSettingsUpdate):
    update_payload = {}

    if settings.subdomain is not None:
        update_payload["subdomain"] = validate_subdomain(settings.subdomain)

    if settings.standard_path_slug is not None:
        update_payload["standard_path_slug"] = validate_subdomain(
            settings.standard_path_slug
        )

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
        context = get_website_tenant_context(request, response)
        update_payload = build_settings_update_payload(settings)

        if not update_payload:
            return {
                "success": True,
                "message": "No website settings changed",
                "website": None,
            }

        tenant_id = context.tenant_id
        authenticated_user_id = context.user_id
        existing_website = get_settings_for_tenant(tenant_id, authenticated_user_id)
        if "standard_path_slug" in update_payload:
            require_any_entitlement(
                tenant_id,
                {"standard_hosted_address", "public_form_links"},
                message="An active website or public-form plan is required to configure a hosted identifier.",
            )
        if (
            "subdomain" in update_payload
            and update_payload["subdomain"] != (existing_website or {}).get("subdomain")
        ):
            require_branded_subdomain(existing_website or {"tenant_id": tenant_id})

        updated_website = save_settings_for_tenant(
            tenant_id=tenant_id,
            user_id=authenticated_user_id,
            update_payload=update_payload,
        )

        audit_metadata = {
            "changed_fields": sorted(update_payload.keys()),
        }
        old_subdomain = (existing_website or {}).get("subdomain")
        new_subdomain = updated_website.get("subdomain") if isinstance(updated_website, dict) else None

        if "subdomain" in update_payload and old_subdomain != new_subdomain:
            audit_metadata["old_subdomain"] = old_subdomain
            audit_metadata["new_subdomain"] = new_subdomain

        record_audit_event(
            request=request,
            tenant_id=tenant_id,
            actor_user_id=authenticated_user_id,
            action="website.settings_updated",
            target_type="website_settings",
            target_id=(
                updated_website.get("id")
                if isinstance(updated_website, dict) and updated_website.get("id") is not None
                else tenant_id
            ),
            metadata=audit_metadata,
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
        context = get_website_tenant_context(request, response)
        tenant_id = context.tenant_id
        authenticated_user_id = context.user_id

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
