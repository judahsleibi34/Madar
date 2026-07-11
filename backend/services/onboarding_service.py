from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import HTTPException

from services.billing_service import validate_billing_plan

logger = logging.getLogger(__name__)

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
RESERVED_SUBDOMAINS = {
    "admin",
    "api",
    "app",
    "auth",
    "billing",
    "cdn",
    "dashboard",
    "docs",
    "help",
    "login",
    "mail",
    "public",
    "root",
    "settings",
    "signup",
    "support",
    "www",
}
NAME_PUNCTUATION = {" ", "-", "'", "’", "."}
BUSINESS_TEXT_PUNCTUATION = NAME_PUNCTUATION | {"&", "/", ",", "(", ")"}


def normalize_email(email: str | None) -> str:
    return str(email or "").strip().lower()


def normalize_subdomain(subdomain: str | None) -> str:
    return str(subdomain or "").strip().lower()


def validate_text_value(
    value: str | None,
    *,
    field_label: str,
    allowed_punctuation: set[str],
    required: bool = True,
) -> str:
    clean_value = str(value or "").strip()

    if not clean_value:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_label} is required")
        return ""

    if any(character.isdigit() for character in clean_value):
        raise HTTPException(status_code=400, detail=f"{field_label} can only contain letters")

    if not any(character.isalpha() for character in clean_value):
        raise HTTPException(status_code=400, detail=f"{field_label} must include letters")

    if any(
        not character.isalpha()
        and not character.isspace()
        and character not in allowed_punctuation
        for character in clean_value
    ):
        raise HTTPException(status_code=400, detail=f"{field_label} contains invalid characters")

    return clean_value


def validate_person_name(value: str | None, field_label: str) -> str:
    return validate_text_value(
        value,
        field_label=field_label,
        allowed_punctuation=NAME_PUNCTUATION,
    )


def validate_optional_business_text(value: str | None, field_label: str) -> str:
    return validate_text_value(
        value,
        field_label=field_label,
        allowed_punctuation=BUSINESS_TEXT_PUNCTUATION,
        required=False,
    )


def validate_onboarding_subdomain(subdomain: str | None) -> str:
    normalized = normalize_subdomain(subdomain)

    if len(normalized) < 3:
        raise HTTPException(status_code=400, detail="Subdomain must be at least 3 characters.")

    if normalized in RESERVED_SUBDOMAINS:
        raise HTTPException(status_code=400, detail="This subdomain is reserved.")

    if not SUBDOMAIN_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Invalid subdomain.")

    return normalized


def ensure_subdomain_available(supabase_client: Any, subdomain: str) -> None:
    result = (
        supabase_client.table("website_settings")
        .select("id")
        .eq("subdomain", subdomain)
        .limit(1)
        .execute()
    )

    if result.data:
        raise HTTPException(status_code=409, detail="Subdomain is already taken.")


def default_builder_schema(business_name: str) -> dict[str, Any]:
    title = business_name.strip() or "New Site"
    return {
        "name": "Untitled Site",
        "status": "draft",
        "activePageId": "home",
        "activeFormId": "",
        "activeCollectionId": "",
        "activeWorkflowId": "",
        "activeRoleId": "",
        "siteChrome": {
            "brand": title,
            "subdomain": "",
        },
        "theme": {},
        "pages": [
            {
                "id": "home",
                "name": "Home",
                "slug": "/",
                "backgroundColor": "#ffffff",
                "visibility": "public",
                "showInNavigation": True,
                "pageType": "main",
                "sections": [
                    {
                        "id": "page-canvas",
                        "name": "Page Canvas",
                        "mode": "direct",
                        "isPageCanvas": True,
                        "layout": {
                            "width": "full",
                            "paddingY": "none",
                            "background": "transparent",
                            "minHeight": 720,
                            "minHeightByViewport": {
                                "desktop": 720,
                                "tablet": 720,
                                "mobile": 720,
                            },
                        },
                        "rows": [],
                        "freeElements": [],
                    }
                ],
            }
        ],
        "forms": [],
        "collections": [],
        "workflows": [],
        "roles": [],
        "users": [],
        "publish": {
            "environment": "local",
            "lastSavedAt": "",
            "lastPublishedAt": "",
        },
    }

def split_owner_name(first_name: str, last_name: str) -> str:
    return f"{first_name.strip()} {last_name.strip()}".strip()


def cleanup_onboarding_rows(
    *,
    supabase_client: Any,
    auth_user_id: str | None,
    tenant_id: int | None,
) -> None:
    if auth_user_id:
        for table_name in (
            "features",
            "builder_projects",
            "website_settings",
            "tenant_memberships",
            "users",
        ):
            try:
                if table_name in {"tenant_memberships", "users"}:
                    supabase_client.table(table_name).delete().eq("auth_id", auth_user_id).execute()
                elif tenant_id is not None:
                    supabase_client.table(table_name).delete().eq("tenant_id", tenant_id).execute()
            except Exception as error:
                logger.warning(
                    "onboarding.cleanup_failed",
                    extra={"table": table_name, "error_type": type(error).__name__},
                )

    if tenant_id is not None:
        try:
            supabase_client.table("tenants").delete().eq("tenant_id", tenant_id).execute()
        except Exception as error:
            logger.warning(
                "onboarding.tenant_cleanup_failed",
                extra={"tenant_id": tenant_id, "error_type": type(error).__name__},
            )

    if auth_user_id:
        try:
            supabase_client.auth.admin.delete_user(auth_user_id)
        except Exception as error:
            logger.warning(
                "onboarding.auth_cleanup_failed",
                extra={"auth_id": auth_user_id, "error_type": type(error).__name__},
            )


def plan_items_from_payload(payload: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    selected_plan = getattr(payload, "selected_plan", None) or getattr(payload, "selected_base_plan", None)
    selected_features = getattr(payload, "selected_features", None) or []

    if selected_plan:
        items.append(dict(selected_plan))

    for feature in selected_features:
        items.append(dict(feature))

    return items


def create_pending_feature_rows(
    *,
    supabase_client: Any,
    tenant_id: int,
    payload: Any,
) -> None:
    for item in plan_items_from_payload(payload):
        normalized = validate_billing_plan(
            subscription_type=item.get("subscription_type"),
            plan=item.get("plan"),
            builder_type=item.get("builder_type"),
        )
        supabase_client.table("features").insert(
            {
                "tenant_id": tenant_id,
                "subscription_type": normalized["subscription_type"],
                "plan": normalized["plan"],
                "builder_type": normalized["builder_type"],
                "payment_status": "pending",
            }
        ).execute()


def create_onboarded_tenant(*, supabase_client: Any, payload: Any) -> dict[str, Any]:
    auth_user_id: str | None = None
    tenant_id: int | None = None
    onboarding_complete = False

    clean_email = normalize_email(payload.email)
    first_name = validate_person_name(payload.first_name, "First name")
    last_name = validate_person_name(payload.last_name, "Last name")
    business_name = validate_optional_business_text(payload.business_name, "Business name")
    business_type = validate_optional_business_text(payload.business_type, "Business type")
    requested_subdomain = normalize_subdomain(payload.subdomain)
    subdomain = validate_onboarding_subdomain(requested_subdomain) if requested_subdomain else ""
    owner_name = split_owner_name(first_name, last_name)
    display_business_name = business_name or owner_name or clean_email.split("@")[0] or "New Business"

    if not clean_email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not payload.password or len(payload.password.strip()) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if subdomain:
        ensure_subdomain_available(supabase_client, subdomain)

    try:
        auth_response = supabase_client.auth.admin.create_user(
            {
                "email": clean_email,
                "password": payload.password,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                },
            }
        )

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Could not create user")

        auth_user_id = str(auth_response.user.id)

        tenant_insert = (
            supabase_client.table("tenants")
            .insert(
                {
                    "brand_name": display_business_name,
                    "business_type": business_type,
                    "owner_name": owner_name,
                }
            )
            .execute()
        )
        if not tenant_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")
        tenant_id = tenant_insert.data[0]["tenant_id"]

        user_insert = (
            supabase_client.table("users")
            .insert(
                {
                    "auth_id": auth_user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": clean_email,
                    "tenant_id": tenant_id,
                }
            )
            .execute()
        )
        if not user_insert.data:
            raise HTTPException(status_code=400, detail="Could not create account")
        local_user = user_insert.data[0]

        supabase_client.table("tenant_memberships").insert(
            {
                "tenant_id": tenant_id,
                "user_id": local_user["id"],
                "auth_id": auth_user_id,
                "role": "owner",
                "status": "active",
            }
        ).execute()

        supabase_client.table("website_settings").insert(
            {
                "tenant_id": tenant_id,
                "user_id": local_user["id"],
                "subdomain": subdomain or None,
                "brand": display_business_name,
                "footer_store_name": display_business_name,
                "contact_email": clean_email,
            }
        ).execute()

        project_insert = (
            supabase_client.table("builder_projects")
            .insert(
                {
                    "tenant_id": tenant_id,
                    "owner_user_id": local_user["id"],
                    "name": f"{display_business_name} Website",
                    "slug": subdomain or f"site-{tenant_id}",
                    "status": "draft",
                    "draft_schema": default_builder_schema(display_business_name),
                    "published_schema": None,
                    "published_version": 0,
                }
            )
            .execute()
        )
        if not project_insert.data:
            raise HTTPException(status_code=400, detail="Could not create default site")

        create_pending_feature_rows(
            supabase_client=supabase_client,
            tenant_id=tenant_id,
            payload=payload,
        )

        onboarding_complete = True
        return {
            "user_id": local_user["id"],
            "tenant_id": tenant_id,
            "subdomain": subdomain or None,
            "requires_login": True,
        }

    except HTTPException:
        raise
    except Exception as error:
        logger.warning("onboarding.failed", extra={"error_type": type(error).__name__})
        raise HTTPException(status_code=400, detail="Could not create account")
    finally:
        if not onboarding_complete:
            cleanup_onboarding_rows(
                supabase_client=supabase_client,
                auth_user_id=auth_user_id,
                tenant_id=tenant_id,
            )
