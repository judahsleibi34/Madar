"""Authoritative, versioned Madar commercial catalog.

Money is stored in USD minor units. Quantities are exact integers. This module is
the only application source for product definitions; clients consume its public
representation through ``GET /billing/catalog``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any


CATALOG_VERSION = "2026-07-30"
CATALOG_CURRENCY = "USD"
CATALOG_EFFECTIVE_DATE = date(2026, 7, 30).isoformat()
GIB = 1024 * 1024 * 1024

BASE_PLAN_IDS = ("forms", "website", "business", "business_plus")
ADD_ON_IDS = (
    "branded_madar_subdomain",
    "additional_storage_5gb",
    "additional_workspace_seat",
    "workspace_seat_pack_5",
    "ai_analytics_starter",
    "ai_analytics_plus",
    "ai_token_pack_750k",
    "google_drive_private",
    "ocr",
    "hosted_email_mailbox",
    "custom_domain",
)

CAPABILITIES = (
    "forms",
    "public_form_links",
    "response_management",
    "response_overview",
    "data_import",
    "standard_data_analysis",
    "page_builder",
    "website_publish",
    "image_uploads",
    "expanded_data_analysis",
    "data_cleaning",
    "charts",
    "data_exports",
    "reservations",
    "reservation_management",
    "internal_calendar",
    "reservation_analytics",
    "priority_support",
    "standard_hosted_address",
    "branded_madar_subdomain",
    "ai_analytics",
    "private_google_drive",
    "ocr",
    "hosted_email_mailbox",
    "custom_domain",
)

_FORMS_CAPABILITIES = {
    "forms",
    "public_form_links",
    "response_management",
    "response_overview",
    "data_import",
    "standard_data_analysis",
}
_WEBSITE_CAPABILITIES = {
    "forms",
    "public_form_links",
    "response_management",
    "response_overview",
    "page_builder",
    "website_publish",
    "image_uploads",
    "standard_hosted_address",
}
_BUSINESS_CAPABILITIES = _WEBSITE_CAPABILITIES | {
    "data_import",
    "standard_data_analysis",
    "expanded_data_analysis",
    "data_cleaning",
    "charts",
    "data_exports",
}
_BUSINESS_PLUS_CAPABILITIES = _BUSINESS_CAPABILITIES | {
    "reservations",
    "reservation_management",
    "internal_calendar",
    "reservation_analytics",
    "priority_support",
}


def _plan(
    product_id: str,
    name: str,
    price_minor: int,
    storage_bytes: int,
    capabilities: set[str],
    display_order: int,
    summary: str,
    public_feature_keys: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "id": product_id,
        "type": "base_plan",
        "name": name,
        "summary": summary,
        "public_feature_keys": list(public_feature_keys),
        "price_minor": price_minor,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": True,
        "coming_soon": False,
        "deprecated": False,
        "display_order": display_order,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": sorted(capabilities),
        "allowances": {
            "storage_bytes": storage_bytes,
            "included_workspace_operators": 1,
            "published_websites": 1 if "website_publish" in capabilities else 0,
            # Project limits are deliberately unmetered until approved.
            "active_builder_projects": None,
            "forms": None,
            "form_submissions": None,
            "reservation_requests": None,
        },
    }


PRODUCTS: dict[str, dict[str, Any]] = {
    "forms": _plan(
        "forms",
        "Forms",
        1500,
        GIB,
        _FORMS_CAPABILITIES,
        10,
        "Public forms, response management, and standard data analysis.",
        (
            "unlimited_forms_submissions",
            "hosted_public_form_links",
            "response_management_overview",
            "data_import_standard_analysis",
        ),
    ),
    "website": _plan(
        "website",
        "Website",
        2000,
        2 * GIB,
        _WEBSITE_CAPABILITIES,
        20,
        "A visual website builder with one standard Madar-hosted address.",
        (
            "visual_page_builder",
            "one_published_website",
            "standard_hosted_address",
            "unlimited_forms_submissions",
            "image_uploads_response_management",
        ),
    ),
    "business": _plan(
        "business",
        "Business",
        2500,
        5 * GIB,
        _BUSINESS_CAPABILITIES,
        30,
        "Website publishing plus expanded data analysis, charts, and exports.",
        (
            "everything_website",
            "expanded_analytics",
            "data_cleaning",
            "charts_data_exports",
        ),
    ),
    "business_plus": _plan(
        "business_plus",
        "Business Plus",
        3000,
        5 * GIB,
        _BUSINESS_PLUS_CAPABILITIES,
        40,
        "Business tools plus reservations, internal calendar, and priority support.",
        (
            "everything_business",
            "unlimited_reservation_requests",
            "reservation_management_analytics",
            "internal_calendar",
            "priority_support",
        ),
    ),
    "branded_madar_subdomain": {
        "id": "branded_madar_subdomain",
        "type": "add_on",
        "name": "Branded Madar subdomain",
        "summary": "Use business-name.madarportal.com for one published site.",
        "price_minor": 500,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": True,
        "coming_soon": False,
        "deprecated": False,
        "display_order": 100,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "requires_capability": "page_builder",
        "capabilities": ["branded_madar_subdomain"],
        "allowances": {"branded_madar_subdomains": 1},
    },
    "additional_storage_5gb": {
        "id": "additional_storage_5gb",
        "type": "add_on",
        "name": "Additional hosted storage",
        "summary": "Add 5 GiB of Madar-hosted storage.",
        "price_minor": 500,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": True,
        "coming_soon": False,
        "deprecated": False,
        "display_order": 110,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": [],
        "allowances": {"storage_bytes": 5 * GIB},
    },
    "additional_workspace_seat": {
        "id": "additional_workspace_seat",
        "type": "add_on",
        "name": "Additional workspace member",
        "summary": "Add one workspace member.",
        "price_minor": 300,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": False,
        "coming_soon": True,
        "administratively_assignable": True,
        "availability_note": "The customer invitation workflow is not yet available.",
        "deprecated": False,
        "display_order": 120,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": [],
        "allowances": {"workspace_seats": 1},
    },
    "workspace_seat_pack_5": {
        "id": "workspace_seat_pack_5",
        "type": "add_on",
        "name": "Five-member workspace pack",
        "summary": "Add five workspace members.",
        "price_minor": 1000,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": False,
        "coming_soon": True,
        "administratively_assignable": True,
        "availability_note": "The customer invitation workflow is not yet available.",
        "deprecated": False,
        "display_order": 130,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": [],
        "allowances": {"workspace_seats": 5},
    },
    "ai_analytics_starter": {
        "id": "ai_analytics_starter",
        "type": "add_on",
        "name": "AI Analytics Starter",
        "summary": "500,000 standard AI tokens per UTC billing period.",
        "price_minor": 500,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": True,
        "coming_soon": False,
        "deprecated": False,
        "display_order": 140,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": ["ai_analytics"],
        "allowances": {"standard_tokens": 500_000},
    },
    "ai_analytics_plus": {
        "id": "ai_analytics_plus",
        "type": "add_on",
        "name": "AI Analytics Plus",
        "summary": "1,500,000 standard AI tokens per UTC billing period.",
        "price_minor": 1000,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": True,
        "coming_soon": False,
        "deprecated": False,
        "display_order": 150,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": ["ai_analytics"],
        "allowances": {"standard_tokens": 1_500_000},
    },
    "ai_token_pack_750k": {
        "id": "ai_token_pack_750k",
        "type": "token_pack",
        "name": "Additional AI token pack",
        "summary": "750,000 standard AI tokens for the assigned billing period.",
        "price_minor": 500,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "one_time",
        "publicly_available": True,
        "coming_soon": False,
        "deprecated": False,
        "display_order": 160,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "requires_capability": "ai_analytics",
        "capabilities": [],
        "allowances": {"standard_tokens": 750_000},
    },
}


def _future(
    product_id: str,
    name: str,
    summary: str,
    capability: str,
    display_order: int,
) -> dict[str, Any]:
    return {
        "id": product_id,
        "type": "add_on",
        "name": name,
        "summary": summary,
        "price_minor": None,
        "currency": CATALOG_CURRENCY,
        "billing_interval": "month",
        "publicly_available": False,
        "coming_soon": True,
        "deprecated": False,
        "display_order": display_order,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "capabilities": [capability],
        "allowances": {},
    }


PRODUCTS.update(
    {
        "google_drive_private": _future(
            "google_drive_private",
            "Private Google Drive connection",
            "Private Drive access is planned and is not currently available.",
            "private_google_drive",
            200,
        ),
        "ocr": _future(
            "ocr",
            "OCR",
            "Arabic, English, and Hebrew OCR is planned; per-page pricing is not finalized.",
            "ocr",
            210,
        ),
        "hosted_email_mailbox": _future(
            "hosted_email_mailbox",
            "Hosted business email mailbox",
            "Hosted mailboxes are planned and are not included in base plans.",
            "hosted_email_mailbox",
            220,
        ),
        "custom_domain": _future(
            "custom_domain",
            "Customer-owned custom domain",
            "Customer-owned domains are planned and are not currently available.",
            "custom_domain",
            230,
        ),
    }
)


def validate_catalog() -> None:
    expected_ids = set(BASE_PLAN_IDS) | set(ADD_ON_IDS)
    if set(PRODUCTS) != expected_ids:
        raise RuntimeError("Commercial catalog identifiers are incomplete or unexpected.")
    for product_id, product in PRODUCTS.items():
        if product.get("id") != product_id:
            raise RuntimeError(f"Catalog id mismatch: {product_id}")
        price = product.get("price_minor")
        if price is not None and (not isinstance(price, int) or price < 0):
            raise RuntimeError(f"Invalid minor-unit price: {product_id}")
        unknown = set(product.get("capabilities") or []) - set(CAPABILITIES)
        if unknown:
            raise RuntimeError(f"Unknown catalog capabilities for {product_id}: {unknown}")
    if "whatsapp" in " ".join(PRODUCTS).lower():
        raise RuntimeError("WhatsApp must not be present in the commercial catalog.")


def get_product(product_id: str) -> dict[str, Any] | None:
    product = PRODUCTS.get(str(product_id or "").strip().lower())
    return deepcopy(product) if product else None


def get_catalog(*, public_only: bool = False) -> dict[str, Any]:
    validate_catalog()
    products = [
        deepcopy(product)
        for product in PRODUCTS.values()
        if not public_only or not product.get("deprecated")
    ]
    products.sort(key=lambda item: (int(item.get("display_order") or 0), item["id"]))
    return {
        "version": CATALOG_VERSION,
        "currency": CATALOG_CURRENCY,
        "effective_date": CATALOG_EFFECTIVE_DATE,
        "manual_activation": True,
        "products": products,
    }


validate_catalog()
