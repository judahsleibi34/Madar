from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from database import service_supabase
from services.ecommerce_cache_service import (
    ecommerce_cache_key,
    get_or_create_ecommerce_cache,
    invalidate_ecommerce_cache,
)
from services.tenant_service import require_active_tenant_member


router = APIRouter(prefix="/ecommerce", tags=["Ecommerce"])
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCALE_PATTERN = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
PRODUCT_MEDIA_ASSET_PATTERN = re.compile(
    r"^/uploads/(?P<key>tenant_(?P<tenant>[1-9][0-9]*)/builder_assets/[a-f0-9]{32}\.(?:png|jpg|webp|mp4|webm))$"
)
DEFAULT_STORE_THEME = {
    "accent": "#852c21",
    "background": "#ffffff",
    "surface": "#f5f1eb",
    "text": "#162033",
    "muted": "#667085",
}
LEGACY_DEFAULT_STORE_THEME = {
    "accent": "#2463eb",
    "background": "#ffffff",
    "surface": "#f7f8fa",
    "text": "#151821",
    "muted": "#697181",
}
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
CATALOG_TABLES = (
    "ecommerce_tags",
    "ecommerce_categories",
    "ecommerce_products",
    "ecommerce_product_tags",
)


def _clean_slug(value: str | None, translations: dict[str, dict[str, str]]) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        first_name = next(
            (str(item.get("name") or "").strip() for item in translations.values() if item.get("name")),
            "",
        )
        candidate = re.sub(r"[^a-z0-9]+", "-", first_name.lower()).strip("-")
    if not candidate or not SLUG_PATTERN.fullmatch(candidate):
        raise HTTPException(status_code=400, detail="Slug must use lowercase letters, numbers, and hyphens")
    if len(candidate) > 160:
        raise HTTPException(status_code=400, detail="Slug must be 160 characters or less")
    return candidate


def _validate_translations(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or not value or len(value) > 10:
        raise ValueError("Translations must contain between 1 and 10 locales")
    cleaned: dict[str, dict[str, str]] = {}
    has_name = False
    for locale, translation in value.items():
        locale_key = str(locale or "").strip()
        if not LOCALE_PATTERN.fullmatch(locale_key):
            raise ValueError("Translation locale must look like en or en-US")
        if not isinstance(translation, dict):
            raise ValueError("Each translation must be an object")
        name = str(translation.get("name") or "").strip()
        description = str(translation.get("description") or "").strip()
        if len(name) > 200 or len(description) > 10000:
            raise ValueError("Translation text is too long")
        if name:
            has_name = True
        cleaned[locale_key] = {"name": name, "description": description}
    if not has_name:
        raise ValueError("At least one translated name is required")
    return cleaned


class CatalogItemPayload(BaseModel):
    slug: str | None = Field(default=None, max_length=160)
    translations: dict[str, dict[str, str]]
    status: Literal["draft", "active", "inactive", "archived"] = "active"

    @field_validator("translations", mode="before")
    @classmethod
    def validate_translations(cls, value):
        return _validate_translations(value)


class CategoryPayload(CatalogItemPayload):
    parent_id: UUID | None = None
    sort_order: int = Field(default=0, ge=0, le=1_000_000)


class StoreThemePayload(BaseModel):
    accent: str = DEFAULT_STORE_THEME["accent"]
    background: str = DEFAULT_STORE_THEME["background"]
    surface: str = DEFAULT_STORE_THEME["surface"]
    text: str = DEFAULT_STORE_THEME["text"]
    muted: str = DEFAULT_STORE_THEME["muted"]

    @field_validator("accent", "background", "surface", "text", "muted")
    @classmethod
    def validate_color(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower()
        if not HEX_COLOR_PATTERN.fullmatch(cleaned):
            raise ValueError("Choose a valid six-digit color")
        return cleaned


class StoreGrowthPayload(BaseModel):
    seo_title_en: str = Field(default="", max_length=120)
    seo_title_ar: str = Field(default="", max_length=120)
    seo_description_en: str = Field(default="", max_length=320)
    seo_description_ar: str = Field(default="", max_length=320)
    announcement_enabled: bool = False
    announcement_text_en: str = Field(default="", max_length=240)
    announcement_text_ar: str = Field(default="", max_length=240)
    announcement_link: str = Field(default="", max_length=500)
    featured_product_ids: list[UUID] = Field(default_factory=list, max_length=12)
    featured_category_ids: list[UUID] = Field(default_factory=list, max_length=6)

    @field_validator(
        "seo_title_en", "seo_title_ar", "seo_description_en", "seo_description_ar",
        "announcement_text_en", "announcement_text_ar", "announcement_link",
    )
    @classmethod
    def strip_growth_text(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("announcement_link")
    @classmethod
    def validate_announcement_link(cls, value: str) -> str:
        if not value:
            return ""
        if any(character in value for character in ("\\", "\r", "\n", "\x00")):
            raise ValueError("Announcement link is invalid")
        if value.startswith("/") and not value.startswith("//"):
            return value
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Announcement link must be a relative path or HTTPS URL")
        return value

    @field_validator("featured_product_ids", "featured_category_ids")
    @classmethod
    def unique_feature_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Featured selections cannot contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_announcement_copy(self):
        if self.announcement_enabled and not (self.announcement_text_en or self.announcement_text_ar):
            raise ValueError("An enabled announcement needs English or Arabic text")
        return self


class StoreCurrencyPayload(BaseModel):
    currency: str = Field(..., min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        cleaned = str(value or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", cleaned):
            raise ValueError("Currency must be a three-letter ISO code")
        return cleaned


class DeliveryAreasUpdate(BaseModel):
    enabled_service_area_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("enabled_service_area_ids")
    @classmethod
    def unique_area_ids(cls, value):
        return list(dict.fromkeys(value))


class OrderStatusUpdate(BaseModel):
    status: Literal["confirmed", "preparing", "out_for_delivery", "delivered", "cancelled", "rejected"]
    note: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(..., min_length=16, max_length=128)


class LoyaltyRulePayload(BaseModel):
    enabled: bool = False
    earning_rate_basis_points: int = Field(default=500, ge=1, le=10000)
    threshold_points: int = Field(..., ge=1, le=10_000_000_000)
    reward_product_id: UUID
    validity_mode: Literal["fixed_period", "lifetime"] = "lifetime"
    validity_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def validate_validity(self):
        if self.validity_mode == "fixed_period" and self.validity_days is None:
            raise ValueError("Validity days are required for a fixed period")
        if self.validity_mode == "lifetime" and self.validity_days is not None:
            raise ValueError("Lifetime rewards cannot have validity days")
        return self


def _rpc_data(response) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise HTTPException(status_code=503, detail="Ecommerce operation returned no result")
    return data

def _validate_localized_label(value: Any, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value or len(value) > 10:
        raise ValueError(f"{field_name} must contain between 1 and 10 locales")
    cleaned = {}
    for locale, label in value.items():
        locale_key, text = str(locale or "").strip(), str(label or "").strip()
        if not LOCALE_PATTERN.fullmatch(locale_key) or not text or len(text) > 200:
            raise ValueError(f"{field_name} contains an invalid locale or value")
        cleaned[locale_key] = text
    return cleaned


class ProductAttributePayload(BaseModel):
    id: UUID
    name_translations: dict[str, str]
    value_translations: dict[str, str]
    sort_order: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("name_translations", "value_translations", mode="before")
    @classmethod
    def validate_labels(cls, value, info):
        return _validate_localized_label(value, info.field_name)


class ProductOptionValuePayload(BaseModel):
    id: UUID
    code: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    value_translations: dict[str, str]
    sort_order: int = Field(default=0, ge=0, le=1_000_000)
    active: bool = True
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("value_translations", mode="before")
    @classmethod
    def validate_labels(cls, value):
        return _validate_localized_label(value, "value_translations")


class ProductOptionPayload(BaseModel):
    id: UUID
    code: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name_translations: dict[str, str]
    required: bool = True
    display_type: Literal["text", "color"] = "text"
    sort_order: int = Field(default=0, ge=0, le=1_000_000)
    values: list[ProductOptionValuePayload] = Field(default_factory=list, max_length=50)

    @field_validator("name_translations", mode="before")
    @classmethod
    def validate_labels(cls, value):
        return _validate_localized_label(value, "name_translations")

    @model_validator(mode="after")
    def validate_presentation(self):
        for value in self.values:
            if self.display_type == "color" and value.active and not value.color_hex:
                raise ValueError("Active color values require a hexadecimal swatch")
            if self.display_type == "text" and value.color_hex is not None:
                raise ValueError("Text values cannot contain a color swatch")
        return self


class ProductVariantPayload(BaseModel):
    id: UUID
    sku: str = Field(..., min_length=1, max_length=120)
    barcode: str | None = Field(default=None, max_length=120)
    price_override: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    compare_at_price_override: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    track_inventory: bool = True
    inventory_quantity: int = Field(default=0, ge=0, le=2_000_000_000)

    low_stock_threshold: int = Field(default=5, ge=0, le=2_000_000_000)
    allow_backorder: bool = False
    images: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("images")
    @classmethod
    def validate_images(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            url = str(value or "").strip()
            managed = bool(PRODUCT_MEDIA_ASSET_PATTERN.fullmatch(url))
            external = bool(re.match(r"^https://", url, re.IGNORECASE)) and not re.search(r"\.svgz?(?:[?#]|$)", url, re.IGNORECASE)
            if not (managed or external) or len(url) > 2048:
                raise ValueError("Variant media must be secure uploaded media")
            cleaned.append(url)
        return list(dict.fromkeys(cleaned))
    active: bool = True
    option_value_ids: list[UUID] = Field(..., min_length=1, max_length=5)

    @field_validator("option_value_ids")
    @classmethod
    def unique_values(cls, value):
        if len(value) != len(set(value)): raise ValueError("A variant cannot repeat an option value")
        return value

class ProductPayload(CatalogItemPayload):
    sku: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=120)
    category_id: UUID | None = None
    tag_ids: list[UUID] = Field(default_factory=list, max_length=100)
    product_type: Literal["physical", "digital", "service"] = "physical"
    brand: str = Field(default="", max_length=160)
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    compare_at_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    track_inventory: bool = True
    inventory_quantity: int = Field(default=0, ge=0, le=2_000_000_000)
    low_stock_threshold: int = Field(default=5, ge=0, le=2_000_000_000)
    allow_backorder: bool = False
    images: list[str] = Field(default_factory=list, max_length=10)
    weight: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    weight_unit: Literal["g", "kg", "lb", "oz"] = "kg"
    attributes: list[ProductAttributePayload] | None = Field(default=None, max_length=50)
    options: list[ProductOptionPayload] | None = Field(default=None, max_length=5)
    variants: list[ProductVariantPayload] | None = Field(default=None, max_length=500)
    requires_shipping: bool = True
    taxable: bool = True
    seo_title: str = Field(default="", max_length=200)
    seo_description: str = Field(default="", max_length=500)

    @field_validator("sku", mode="before")
    @classmethod
    def clean_sku(cls, value: Any) -> str | None:
        return str(value or "").strip() or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", cleaned):
            raise ValueError("Currency must be a three-letter ISO code")
        return cleaned

    @field_validator("images")
    @classmethod
    def validate_images(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            url = str(value or "").strip()
            is_managed_media = bool(PRODUCT_MEDIA_ASSET_PATTERN.fullmatch(url))
            is_secure_external_media = bool(re.match(r"^https://", url, re.IGNORECASE)) and not re.search(r"\.svgz?(?:[?#]|$)", url, re.IGNORECASE)
            if not (is_managed_media or is_secure_external_media) or len(url) > 2048:
                raise ValueError("Product media must be secure uploaded media")
            cleaned.append(url)
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def validate_pricing(self):
        if self.compare_at_price is not None and self.compare_at_price <= self.price:
            raise ValueError("Discounted price must be lower than the regular price")
        option_ids = {option.id for option in (self.options or [])}
        value_ids = {value.id for option in (self.options or []) for value in option.values}
        if len(option_ids) != len(self.options or []) or len(value_ids) != sum(len(option.values) for option in (self.options or [])):
            raise ValueError("Option and value identifiers must be unique")
        normalized_options = [next(iter(option.name_translations.values())).casefold() for option in (self.options or [])]
        if len(normalized_options) != len(set(normalized_options)):
            raise ValueError("Option names must be unique within a product")
        for option in (self.options or []):
            normalized_values = [next(iter(value.value_translations.values())).casefold() for value in option.values]
            if len(normalized_values) != len(set(normalized_values)):
                raise ValueError("Option values must be unique within an option")
        if any(set(variant.option_value_ids) - value_ids for variant in (self.variants or [])):
            raise ValueError("Every variant value must belong to this product")
        if self.variants and not self.options:
            raise ValueError("Variants require at least one product option")
        value_option = {value.id: option.id for option in (self.options or []) for value in option.values}
        required_options = {option.id for option in (self.options or []) if option.required}
        for variant in (self.variants or []):
            selected_options = {value_option[value_id] for value_id in variant.option_value_ids}
            if len(selected_options) != len(variant.option_value_ids):
                raise ValueError("A variant must select at most one value from each option")
            if variant.active and not required_options.issubset(selected_options):
                raise ValueError("Every active variant must select all required options")
            effective_price = variant.price_override if variant.price_override is not None else self.price
            effective_compare = variant.compare_at_price_override if variant.compare_at_price_override is not None else self.compare_at_price
            if effective_compare is not None and effective_compare <= effective_price:
                raise ValueError("Variant compare-at price must exceed its effective price")
        return self


def _rows(query) -> list[dict[str, Any]]:
    return getattr(query.execute(), "data", None) or []


def _tenant_row(table: str, item_id: UUID | str, tenant_id: int) -> dict[str, Any]:
    rows = _rows(
        service_supabase.table(table)
        .select("*")
        .eq("id", str(item_id))
        .eq("tenant_id", tenant_id)
        .limit(1)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Catalog item was not found")
    return rows[0]


def _handle_catalog_error(error: Exception) -> None:
    raw = str(error).lower()
    if "pgrst205" in raw or "could not find the table" in raw or "schema cache" in raw:
        raise HTTPException(status_code=503, detail="Ecommerce catalog migration is not installed") from error
    if "23505" in raw or "duplicate key" in raw:
        raise HTTPException(status_code=409, detail="Slug or SKU already exists") from error
    if "23503" in raw or "foreign key" in raw:
        raise HTTPException(status_code=409, detail="This item is still used by another catalog record") from error
    raise error



def _require_ecommerce_access(request: Request, response: Response):
    """Resolve ecommerce access only from the authenticated tenant membership."""
    context = require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=False,
    )
    if str(context.role or "").lower() not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=403, detail="Ecommerce access required")
    return context

def _require_role(context) -> None:
    if str(context.role or "").lower() not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=403, detail="Catalog write access required")


def _validate_category_parent(context, parent_id: UUID | None, category_id: UUID | None = None) -> str | None:
    if parent_id is None:
        return None
    parent_value = str(parent_id)
    if category_id is not None and parent_value == str(category_id):
        raise HTTPException(status_code=400, detail="A category cannot be its own parent")
    parent = _tenant_row("ecommerce_categories", parent_value, context.tenant_id)
    seen = {str(category_id)} if category_id else set()
    while parent:
        parent_key = str(parent.get("id"))
        if parent_key in seen:
            raise HTTPException(status_code=400, detail="Category hierarchy cannot contain a cycle")
        seen.add(parent_key)
        ancestor_id = parent.get("parent_id")
        if not ancestor_id:
            break
        parent = _tenant_row("ecommerce_categories", ancestor_id, context.tenant_id)
    return parent_value


def _validate_product_links(context, category_id: UUID | None, tag_ids: list[UUID]) -> tuple[str | None, list[str]]:
    category_value = None
    if category_id is not None:
        category_value = str(category_id)
        _tenant_row("ecommerce_categories", category_value, context.tenant_id)
    unique_tags = list(dict.fromkeys(str(item) for item in tag_ids))
    for tag_id in unique_tags:
        _tenant_row("ecommerce_tags", tag_id, context.tenant_id)
    return category_value, unique_tags


def _managed_product_asset_keys(images: list[str], tenant_id: int) -> set[str]:
    keys: set[str] = set()
    for image in images:
        match = PRODUCT_MEDIA_ASSET_PATTERN.fullmatch(str(image or "").strip())
        if not match:
            continue
        if int(match.group("tenant")) != int(tenant_id):
            raise HTTPException(status_code=400, detail="Product images must belong to this workspace")
        keys.add(match.group("key"))
    return keys


def _sync_product_image_assets(*, tenant_id: int, previous_images: list[str], current_images: list[str]) -> None:
    previous_keys = _managed_product_asset_keys(previous_images, tenant_id)
    current_keys = _managed_product_asset_keys(current_images, tenant_id)
    now = datetime.now(timezone.utc)
    for storage_key in current_keys:
        service_supabase.table("builder_assets").update({
            "status": "active",
            "reference_count": 1,
            "last_referenced_at": now.isoformat(),
            "retention_until": None,
            "deleted_at": None,
            "metadata": {"usage": "ecommerce_product"},
        }).eq("tenant_id", int(tenant_id)).eq("storage_key", storage_key).execute()

    removed_keys = previous_keys - current_keys
    if not removed_keys:
        return
    product_rows = _rows(
        service_supabase.table("ecommerce_products")
        .select("images")
        .eq("tenant_id", int(tenant_id))
    )
    still_referenced = set().union(*(
        _managed_product_asset_keys(row.get("images") or [], tenant_id)
        for row in product_rows
    )) if product_rows else set()
    retention_until = (now + timedelta(days=7)).isoformat()
    for storage_key in removed_keys - still_referenced:
        asset_rows = _rows(
            service_supabase.table("builder_assets")
            .select("id")
            .eq("tenant_id", int(tenant_id))
            .eq("storage_key", storage_key)
            .limit(1)
        )
        if asset_rows:
            builder_references = _rows(
                service_supabase.table("builder_asset_references")
                .select("asset_id")
                .eq("asset_id", asset_rows[0]["id"])
                .limit(1)
            )
            if builder_references:
                continue
        service_supabase.table("builder_assets").update({
            "status": "unreferenced",
            "reference_count": 0,
            "last_referenced_at": None,
            "retention_until": retention_until,
        }).eq("tenant_id", int(tenant_id)).eq("storage_key", storage_key).execute()


def _generate_sku(slug: str) -> str:
    readable_prefix = re.sub(r"[^A-Z0-9]+", "-", slug.upper()).strip("-")[:100] or "PRODUCT"
    return f"{readable_prefix}-{uuid4().hex[:8].upper()}"


def _product_data(payload: ProductPayload, context) -> tuple[dict[str, Any], list[str]]:
    category_id, tag_ids = _validate_product_links(context, payload.category_id, payload.tag_ids)
    slug = _clean_slug(payload.slug, payload.translations)
    _managed_product_asset_keys(payload.images, context.tenant_id)
    data = payload.model_dump(mode="json", exclude={"tag_ids", "attributes", "options", "variants"})
    data.update(
        tenant_id=context.tenant_id,
        category_id=category_id,
        slug=slug,
        sku=payload.sku or _generate_sku(slug),
        barcode=str(payload.barcode or "").strip() or None,
    )
    store_currency = _store_currency_for_tenant(context.tenant_id)
    if store_currency:
        data["currency"] = store_currency
    return data, tag_ids


def _attach_product_tags(products: list[dict[str, Any]], tenant_id: int) -> list[dict[str, Any]]:
    links = _rows(
        service_supabase.table("ecommerce_product_tags")
        .select("product_id,tag_id")
        .eq("tenant_id", tenant_id)
    )
    by_product: dict[str, list[str]] = {}
    for link in links:
        by_product.setdefault(str(link.get("product_id")), []).append(str(link.get("tag_id")))
    for product in products:
        product["tag_ids"] = by_product.get(str(product.get("id")), [])
    return products

def _product_aggregate_payload(payload: ProductPayload) -> dict[str, Any]:
    attributes = []
    for item in (payload.attributes or []):
        data = item.model_dump(mode="json")
        data["normalized_name"] = next(iter(item.name_translations.values())).strip().casefold()
        attributes.append(data)
    options = []
    for option in (payload.options or []):
        data = option.model_dump(mode="json")
        data["client_id"] = str(option.id)
        data["normalized_name"] = next(iter(option.name_translations.values())).strip().casefold()
        for value, value_data in zip(option.values, data["values"]):
            value_data["normalized_value"] = next(iter(value.value_translations.values())).strip().casefold()
        options.append(data)
    return {"attributes": attributes, "options": options, "variants": [item.model_dump(mode="json") for item in (payload.variants or [])]}


def _save_product_aggregate(tenant_id: int, product_id: str, payload: ProductPayload) -> None:
    if payload.attributes is None and payload.options is None and payload.variants is None:
        return
    aggregate = _product_aggregate_payload(payload)
    params = {"p_tenant_id": tenant_id, "p_product_id": product_id, "p_attributes": aggregate["attributes"], "p_options": aggregate["options"], "p_variants": aggregate["variants"]}
    try:
        service_supabase.rpc("save_ecommerce_product_aggregate_v2_safe", params).execute()
    except Exception as error:
        message = str(error).lower()
        missing_v2 = "save_ecommerce_product_aggregate_v2_safe" in message or "pgrst202" in message or "schema cache" in message
        uses_color = any(option.display_type == "color" for option in (payload.options or []))
        if not missing_v2:
            raise
        if uses_color:
            raise HTTPException(status_code=503, detail="Color variant attributes require database migration 099") from error
        service_supabase.rpc("save_ecommerce_product_aggregate_safe", params).execute()


def _attach_product_aggregates(products: list[dict[str, Any]], tenant_id: int) -> list[dict[str, Any]]:
    try:
        attributes = _rows(service_supabase.table("ecommerce_product_attributes").select("*").eq("tenant_id", tenant_id).order("sort_order"))
        options = _rows(service_supabase.table("ecommerce_product_options").select("*").eq("tenant_id", tenant_id).order("sort_order"))
        values = _rows(service_supabase.table("ecommerce_product_option_values").select("*").eq("tenant_id", tenant_id).order("sort_order"))
        links = _rows(service_supabase.table("ecommerce_variant_option_values").select("variant_id,option_value_id").eq("tenant_id", tenant_id))
        variants = _rows(service_supabase.table("ecommerce_product_variants").select("*").eq("tenant_id", tenant_id).order("created_at"))
    except Exception as error:
        if "pgrst205" in str(error).lower() or "schema cache" in str(error).lower():
            for product in products: product.update(attributes=[], options=[], variants=[])
            return products
        raise
    values_by_option, value_ids_by_variant = {}, {}
    for value in values: values_by_option.setdefault(str(value["option_id"]), []).append(value)
    for link in links: value_ids_by_variant.setdefault(str(link["variant_id"]), []).append(str(link["option_value_id"]))
    for option in options: option["values"] = values_by_option.get(str(option["id"]), [])
    for variant in variants: variant["option_value_ids"] = value_ids_by_variant.get(str(variant["id"]), [])
    for product in products:
        product_id = str(product["id"])
        product["attributes"] = [item for item in attributes if str(item["product_id"]) == product_id]
        product["options"] = [item for item in options if str(item["product_id"]) == product_id]
        product["variants"] = [item for item in variants if str(item["product_id"]) == product_id]
        active_variants = [item for item in product["variants"] if item.get("active")]
        inventory_items = active_variants if product["options"] else [product]
        states = [_inventory_state(item) for item in inventory_items]
        product["low_stock_count"] = states.count("low_stock")
        product["out_of_stock_count"] = states.count("out_of_stock")
        product["has_low_stock"] = product["low_stock_count"] > 0
        product["has_out_of_stock"] = product["out_of_stock_count"] > 0
        if product["options"] and not active_variants:
            product["inventory_status"] = "out_of_stock"
        elif states and all(state == "out_of_stock" for state in states):
            product["inventory_status"] = "out_of_stock"
        elif product["has_low_stock"] or product["has_out_of_stock"]:
            product["inventory_status"] = "low_stock"
        else:
            product["inventory_status"] = states[0] if len(states) == 1 else "healthy"
    return products


def _catalog_for_tenant(tenant_id: int) -> dict[str, list[dict[str, Any]]]:
    tags = _rows(service_supabase.table("ecommerce_tags").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True))
    categories = _rows(service_supabase.table("ecommerce_categories").select("*").eq("tenant_id", tenant_id).order("sort_order").order("created_at"))
    products = _rows(service_supabase.table("ecommerce_products").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True))
    products = _attach_product_aggregates(_attach_product_tags(products, tenant_id), tenant_id)
    return {
        "tags": tags,
        "categories": categories,
        "products": products,
        "stock_summary": {
            "low_stock": sum(int(product.get("low_stock_count") or 0) for product in products),
            "out_of_stock": sum(int(product.get("out_of_stock_count") or 0) for product in products),
        },
        "commerce_currency": _store_currency_for_tenant(tenant_id),
    }


def _store_theme_for_tenant(tenant_id: int) -> dict[str, Any]:
    rows = _rows(
        service_supabase.table("website_settings")
        .select("ecommerce_theme")
        .eq("tenant_id", int(tenant_id))
        .limit(1)
    )
    saved = rows[0].get("ecommerce_theme") if rows else {}
    if saved == LEGACY_DEFAULT_STORE_THEME:
        saved = {}
    return {**DEFAULT_STORE_THEME, **(saved if isinstance(saved, dict) else {})}


def _store_growth_for_tenant(tenant_id: int) -> dict[str, Any]:
    growth = _store_theme_for_tenant(tenant_id).get("growth")
    try:
        return StoreGrowthPayload.model_validate(growth or {}).model_dump(mode="json")
    except Exception:
        return StoreGrowthPayload().model_dump(mode="json")


def _validate_featured_rows(tenant_id: int, table: str, selected_ids: list[UUID]) -> None:
    if not selected_ids:
        return
    found = _rows(service_supabase.table(table).select("id").eq("tenant_id", tenant_id).eq("status", "active").in_("id", [str(value) for value in selected_ids]))
    found_ids = {str(row.get("id")) for row in found}
    if found_ids != {str(value) for value in selected_ids}:
        raise HTTPException(status_code=400, detail="Featured selections must be active items from this store")


def _store_currency_for_tenant(tenant_id: int) -> str | None:
    try:
        settings = _rows(
            service_supabase.table("website_settings")
            .select("ecommerce_currency")
            .eq("tenant_id", int(tenant_id))
            .limit(1)
        )
    except Exception as error:
        message = str(error).lower()
        if "ecommerce_currency" in message or "pgrst204" in message or "schema cache" in message:
            return None
        raise
    currency = str(settings[0].get("ecommerce_currency") or "").strip().upper() if settings else ""
    return currency or None


def _store_currency_locked(tenant_id: int) -> bool:
    return bool(_rows(
        service_supabase.table("ecommerce_orders")
        .select("id")
        .eq("tenant_id", int(tenant_id))
        .limit(1)
    ))


@router.get("/theme")
def get_store_theme(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    return {"theme": _store_theme_for_tenant(context.tenant_id)}


@router.put("/theme")
def update_store_theme(payload: StoreThemePayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    theme = {**_store_theme_for_tenant(context.tenant_id), **payload.model_dump()}
    rows = _rows(
        service_supabase.table("website_settings")
        .update({"ecommerce_theme": theme})
        .eq("tenant_id", int(context.tenant_id))
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Website settings not found")
    invalidate_ecommerce_cache(context.tenant_id)
    return {"theme": theme}


@router.get("/growth")
def get_store_growth(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    return {"growth": _store_growth_for_tenant(context.tenant_id)}


@router.put("/growth")
def update_store_growth(payload: StoreGrowthPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    _validate_featured_rows(context.tenant_id, "ecommerce_products", payload.featured_product_ids)
    _validate_featured_rows(context.tenant_id, "ecommerce_categories", payload.featured_category_ids)
    growth = payload.model_dump(mode="json")
    theme = {**_store_theme_for_tenant(context.tenant_id), "growth": growth}
    rows = _rows(
        service_supabase.table("website_settings")
        .update({"ecommerce_theme": theme})
        .eq("tenant_id", int(context.tenant_id))
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Website settings not found")
    invalidate_ecommerce_cache(context.tenant_id)
    return {"growth": growth}


@router.get("/settings")
def get_store_settings(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    return {
        "currency": _store_currency_for_tenant(context.tenant_id),
        "currency_locked": _store_currency_locked(context.tenant_id),
    }


@router.put("/settings")
def update_store_settings(payload: StoreCurrencyPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    try:
        result = service_supabase.rpc("set_ecommerce_currency_safe", {
            "p_tenant_id": int(context.tenant_id),
            "p_currency": payload.currency,
        }).execute()
        data = getattr(result, "data", None)
        if isinstance(data, list):
            data = data[0] if data else None
        settings = data
        if not isinstance(settings, dict):
            raise RuntimeError("ecommerce_currency_rpc_empty_result")
    except Exception as error:
        message = str(error).lower()
        if "ecommerce_currency_locked" in message:
            raise HTTPException(status_code=409, detail="Store currency is locked after the first order") from error
        if "ecommerce_currency_order_mismatch" in message:
            raise HTTPException(status_code=409, detail="Existing orders use a different store currency") from error
        if "ecommerce_currency_product_mismatch" in message:
            raise HTTPException(status_code=409, detail="Active products must use the selected store currency") from error
        if "set_ecommerce_currency_safe" in message or "schema cache" in message or "pgrst202" in message:
            raise HTTPException(status_code=503, detail="Store currency settings require the latest database migration") from error
        raise
    invalidate_ecommerce_cache(context.tenant_id)
    return {"currency": settings.get("ecommerce_currency"), "currency_locked": _store_currency_locked(context.tenant_id)}


@router.get("/delivery-areas")
def get_delivery_areas(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    areas = _rows(service_supabase.table("ecommerce_service_areas").select("id,code,name_en,name_ar,active,sort_order").eq("active", True).order("sort_order"))
    enabled_rows = _rows(service_supabase.table("ecommerce_tenant_service_areas").select("service_area_id").eq("tenant_id", context.tenant_id).eq("enabled", True))
    enabled = {str(row.get("service_area_id")) for row in enabled_rows}
    return {"areas": [{**area, "enabled": str(area.get("id")) in enabled} for area in areas], "enabled_count": len(enabled)}


@router.put("/delivery-areas")
def update_delivery_areas(payload: DeliveryAreasUpdate, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    try:
        result = _rpc_data(service_supabase.rpc("set_ecommerce_delivery_areas_safe", {
            "p_tenant_id": int(context.tenant_id),
            "p_service_area_ids": [str(area_id) for area_id in payload.enabled_service_area_ids],
        }).execute())
    except HTTPException:
        raise
    except Exception as error:
        message = str(error).lower()
        if "ecommerce_service_area_invalid" in message:
            raise HTTPException(status_code=400, detail="One or more delivery areas are unavailable") from error
        if "set_ecommerce_delivery_areas_safe" in message or "schema cache" in message or "pgrst202" in message:
            raise HTTPException(status_code=503, detail="Delivery configuration requires the latest database migration") from error
        raise
    invalidate_ecommerce_cache(context.tenant_id)
    return result


ORDER_STATUSES = {"pending", "confirmed", "preparing", "out_for_delivery", "delivered", "fulfilled", "cancelled", "rejected"}
PAYMENT_STATUSES = {"unpaid", "collected", "paid", "refunded"}


@router.get("/loyalty")
def get_loyalty_rule(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    rules = _rows(service_supabase.table("ecommerce_loyalty_rules").select("*").eq("tenant_id", context.tenant_id).eq("is_current", True).limit(1))
    entitlements = _rows(service_supabase.table("ecommerce_loyalty_entitlements").select("*").eq("tenant_id", context.tenant_id).order("created_at", desc=True).limit(100))
    return {
        "rule": rules[0] if rules else None,
        "defaults": {"enabled": False, "earning_rate_basis_points": 500, "reward_discount_basis_points": 1000, "validity_mode": "lifetime"},
        "currency": _store_currency_for_tenant(context.tenant_id),
        "recent_entitlements": entitlements,
    }


@router.put("/loyalty")
def update_loyalty_rule(payload: LoyaltyRulePayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    try:
        rule = _rpc_data(service_supabase.rpc("save_ecommerce_loyalty_rule_safe", {
            "p_tenant_id": int(context.tenant_id), "p_actor_id": int(context.user_id),
            "p_enabled": payload.enabled, "p_earning_rate_basis_points": payload.earning_rate_basis_points,
            "p_threshold_points": payload.threshold_points, "p_reward_product_id": str(payload.reward_product_id),
            "p_validity_mode": payload.validity_mode, "p_validity_days": payload.validity_days,
        }).execute())
    except HTTPException:
        raise
    except Exception as error:
        message = str(error).lower()
        if "reward_product_invalid" in message or "rule_invalid" in message:
            raise HTTPException(status_code=400, detail="The loyalty rule is invalid") from error
        raise HTTPException(status_code=503, detail="Loyalty settings require database migration 097") from error
    return {"rule": rule}


@router.post("/loyalty/entitlements/{entitlement_id}/revoke")
def revoke_loyalty_entitlement(entitlement_id: UUID, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    try:
        return _rpc_data(service_supabase.rpc("revoke_ecommerce_loyalty_entitlement_safe", {
            "p_tenant_id": int(context.tenant_id),
            "p_entitlement_id": str(entitlement_id),
            "p_actor_id": int(context.user_id),
        }).execute())
    except Exception as error:
        message = str(error).lower()
        if "entitlement_not_found" in message:
            raise HTTPException(status_code=404, detail="Loyalty entitlement not found") from error
        if "entitlement_not_active" in message:
            raise HTTPException(status_code=409, detail="Only an active entitlement can be revoked") from error
        raise HTTPException(status_code=503, detail="The loyalty entitlement could not be revoked") from error


@router.get("/orders")
def list_orders(
    request: Request,
    response: Response,
    order_number: str = "",
    customer_name: str = "",
    phone: str = "",
    status: str = "",
    payment_status: str = "",
    service_area_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
):
    context = _require_ecommerce_access(request, response)
    if status and status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid order status")
    if payment_status and payment_status not in PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid payment status")
    query = service_supabase.table("ecommerce_orders").select(
        "id,order_number,created_at,customer_name,customer_phone,service_area_id,service_area_name_en,service_area_name_ar,total,currency,payment_method,payment_status,status",
        count="exact",
    ).eq("tenant_id", context.tenant_id)
    if order_number.strip(): query = query.ilike("order_number", f"%{order_number.strip()}%")
    if customer_name.strip(): query = query.ilike("customer_name", f"%{customer_name.strip()}%")
    if phone.strip(): query = query.ilike("customer_phone", f"%{phone.strip()}%")
    if status: query = query.eq("status", status)
    if payment_status: query = query.eq("payment_status", payment_status)
    if service_area_id: query = query.eq("service_area_id", str(service_area_id))
    if date_from: query = query.gte("created_at", datetime.combine(date_from, time.min, timezone.utc).isoformat())
    if date_to: query = query.lt("created_at", datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc).isoformat())
    result = query.order("created_at", desc=True).range((page - 1) * limit, page * limit - 1).execute()
    return {"orders": getattr(result, "data", None) or [], "page": page, "limit": limit, "total": int(getattr(result, "count", 0) or 0)}


def _merchant_order_detail(tenant_id: int, order_id: UUID) -> dict[str, Any]:
    orders = _rows(service_supabase.table("ecommerce_orders").select("*").eq("tenant_id", tenant_id).eq("id", str(order_id)).limit(1))
    if not orders:
        raise HTTPException(status_code=404, detail="Order not found")
    items = _rows(service_supabase.table("ecommerce_order_items").select("*").eq("tenant_id", tenant_id).eq("order_id", str(order_id)).order("created_at"))
    history = _rows(service_supabase.table("ecommerce_order_status_history").select("id,previous_status,new_status,actor_id,note,created_at").eq("tenant_id", tenant_id).eq("order_id", str(order_id)).order("created_at"))
    return {"order": orders[0], "items": items, "status_history": history}


@router.get("/orders/{order_id}")
def get_order(order_id: UUID, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    return _merchant_order_detail(context.tenant_id, order_id)


def _order_operation_error(error: Exception) -> HTTPException:
    message = str(error).lower()
    if "ecommerce_order_not_found" in message:
        return HTTPException(status_code=404, detail="Order not found")
    if "ecommerce_order_transition_invalid" in message:
        return HTTPException(status_code=409, detail="That order status transition is not allowed")
    if "idempotency_conflict" in message:
        return HTTPException(status_code=409, detail="This operation key was already used differently")
    if "ecommerce_cod_required" in message or "ecommerce_payment_transition_invalid" in message:
        return HTTPException(status_code=409, detail="COD collection is not available for this order")
    return HTTPException(status_code=503, detail="The order operation could not be completed")


@router.post("/orders/{order_id}/status")
def transition_order_status(order_id: UUID, payload: OrderStatusUpdate, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    key_hash = hashlib.sha256(f"{context.tenant_id}:{order_id}:status:{payload.idempotency_key}".encode()).hexdigest()
    try:
        result = _rpc_data(service_supabase.rpc("transition_ecommerce_order_status_safe", {
            "p_tenant_id": int(context.tenant_id),
            "p_order_id": str(order_id),
            "p_new_status": payload.status,
            "p_actor_id": int(context.user_id),
            "p_note": payload.note.strip(),
            "p_idempotency_key_hash": key_hash,
        }).execute())
    except HTTPException:
        raise
    except Exception as error:
        raise _order_operation_error(error) from error
    return {**result, **_merchant_order_detail(context.tenant_id, order_id)}


@router.post("/orders/{order_id}/collect-payment")
def collect_order_payment(order_id: UUID, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    try:
        result = _rpc_data(service_supabase.rpc("collect_ecommerce_cod_payment_safe", {
            "p_tenant_id": int(context.tenant_id),
            "p_order_id": str(order_id),
            "p_actor_id": int(context.user_id),
        }).execute())
    except HTTPException:
        raise
    except Exception as error:
        raise _order_operation_error(error) from error
    return {**result, **_merchant_order_detail(context.tenant_id, order_id)}

@router.get("/catalog")
def get_catalog(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    try:
        cache_key = ecommerce_cache_key(context.tenant_id, "authenticated-catalog-v2")
        catalog, _cache_hit = get_or_create_ecommerce_cache(
            cache_key,
            context.tenant_id,
            lambda: _catalog_for_tenant(context.tenant_id),
        )
        return catalog
    except Exception as error:
        _handle_catalog_error(error)


@router.post("/tags", status_code=201)
def create_tag(payload: CatalogItemPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    data = payload.model_dump(mode="json")
    data.update(tenant_id=context.tenant_id, created_by=context.user_id, slug=_clean_slug(payload.slug, payload.translations))
    try:
        rows = _rows(service_supabase.table("ecommerce_tags").insert(data))
        invalidate_ecommerce_cache(context.tenant_id)
        return {"tag": rows[0]}
    except Exception as error:
        _handle_catalog_error(error)


@router.put("/tags/{tag_id}")
def update_tag(tag_id: UUID, payload: CatalogItemPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    _tenant_row("ecommerce_tags", tag_id, context.tenant_id)
    data = payload.model_dump(mode="json")
    data["slug"] = _clean_slug(payload.slug, payload.translations)
    try:
        rows = _rows(service_supabase.table("ecommerce_tags").update(data).eq("id", str(tag_id)).eq("tenant_id", context.tenant_id))
        invalidate_ecommerce_cache(context.tenant_id)
        return {"tag": rows[0]}
    except Exception as error:
        _handle_catalog_error(error)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: UUID, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    _tenant_row("ecommerce_tags", tag_id, context.tenant_id)
    service_supabase.table("ecommerce_tags").delete().eq("id", str(tag_id)).eq("tenant_id", context.tenant_id).execute()
    invalidate_ecommerce_cache(context.tenant_id)
    return Response(status_code=204)


@router.post("/categories", status_code=201)
def create_category(payload: CategoryPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    data = payload.model_dump(mode="json")
    data.update(
        tenant_id=context.tenant_id,
        created_by=context.user_id,
        parent_id=_validate_category_parent(context, payload.parent_id),
        slug=_clean_slug(payload.slug, payload.translations),
    )
    try:
        rows = _rows(service_supabase.table("ecommerce_categories").insert(data))
        invalidate_ecommerce_cache(context.tenant_id)
        return {"category": rows[0]}
    except Exception as error:
        _handle_catalog_error(error)


@router.put("/categories/{category_id}")
def update_category(category_id: UUID, payload: CategoryPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    _tenant_row("ecommerce_categories", category_id, context.tenant_id)
    data = payload.model_dump(mode="json")
    data.update(
        parent_id=_validate_category_parent(context, payload.parent_id, category_id),
        slug=_clean_slug(payload.slug, payload.translations),
    )
    try:
        rows = _rows(service_supabase.table("ecommerce_categories").update(data).eq("id", str(category_id)).eq("tenant_id", context.tenant_id))
        invalidate_ecommerce_cache(context.tenant_id)
        return {"category": rows[0]}
    except Exception as error:
        _handle_catalog_error(error)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: UUID, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    _tenant_row("ecommerce_categories", category_id, context.tenant_id)
    try:
        service_supabase.table("ecommerce_categories").delete().eq("id", str(category_id)).eq("tenant_id", context.tenant_id).execute()
    except Exception as error:
        _handle_catalog_error(error)
    invalidate_ecommerce_cache(context.tenant_id)
    return Response(status_code=204)


def _replace_product_tags(context, product_id: str, tag_ids: list[str]) -> None:
    service_supabase.table("ecommerce_product_tags").delete().eq("product_id", product_id).eq("tenant_id", context.tenant_id).execute()
    if tag_ids:
        service_supabase.table("ecommerce_product_tags").insert([
            {"tenant_id": context.tenant_id, "product_id": product_id, "tag_id": tag_id}
            for tag_id in tag_ids
        ]).execute()


@router.post("/products", status_code=201)
def create_product(payload: ProductPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    data, tag_ids = _product_data(payload, context)
    data["created_by"] = context.user_id
    desired_status = data["status"]
    if payload.options:
        data["status"] = "draft"
    try:
        rows = _rows(service_supabase.table("ecommerce_products").insert(data))
        product = rows[0]
        _replace_product_tags(context, str(product["id"]), tag_ids)
        product["tag_ids"] = tag_ids
        _sync_product_image_assets(
            tenant_id=context.tenant_id,
            previous_images=[],
            current_images=product.get("images") or [],
        )
        _save_product_aggregate(context.tenant_id, str(product["id"]), payload)
        if payload.options and desired_status != "draft":
            product = _rows(service_supabase.table("ecommerce_products").update({"status": desired_status}).eq("id", str(product["id"])).eq("tenant_id", context.tenant_id))[0]
            product["tag_ids"] = tag_ids
        invalidate_ecommerce_cache(context.tenant_id)
        return {"product": product}
    except Exception as error:
        _handle_catalog_error(error)


@router.put("/products/{product_id}")
def update_product(product_id: UUID, payload: ProductPayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    existing_product = _tenant_row("ecommerce_products", product_id, context.tenant_id)
    data, tag_ids = _product_data(payload, context)
    data.pop("tenant_id", None)
    desired_status = data["status"]
    if payload.options:
        data["status"] = "draft"
    try:
        rows = _rows(service_supabase.table("ecommerce_products").update(data).eq("id", str(product_id)).eq("tenant_id", context.tenant_id))
        product = rows[0]
        _replace_product_tags(context, str(product_id), tag_ids)
        product["tag_ids"] = tag_ids
        _sync_product_image_assets(
            tenant_id=context.tenant_id,
            previous_images=existing_product.get("images") or [],
            current_images=product.get("images") or [],
        )
        _save_product_aggregate(context.tenant_id, str(product_id), payload)
        if payload.options and desired_status != "draft":
            product = _rows(service_supabase.table("ecommerce_products").update({"status": desired_status}).eq("id", str(product_id)).eq("tenant_id", context.tenant_id))[0]
            product["tag_ids"] = tag_ids
        invalidate_ecommerce_cache(context.tenant_id)
        return {"product": product}
    except Exception as error:
        _handle_catalog_error(error)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: UUID, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    existing_product = _tenant_row("ecommerce_products", product_id, context.tenant_id)
    service_supabase.table("ecommerce_products").delete().eq("id", str(product_id)).eq("tenant_id", context.tenant_id).execute()
    _sync_product_image_assets(
        tenant_id=context.tenant_id,
        previous_images=existing_product.get("images") or [],
        current_images=[],
    )
    invalidate_ecommerce_cache(context.tenant_id)
    return Response(status_code=204)


def _inventory_state(item: dict[str, Any]) -> str:
    if not bool(item.get("track_inventory")):
        return "untracked"
    quantity = int(item.get("inventory_quantity") or 0)
    if quantity <= 0:
        return "backorder" if bool(item.get("allow_backorder")) else "out_of_stock"
    threshold = item.get("low_stock_threshold")
    if threshold is not None and quantity <= int(threshold):
        return "low_stock"
    return "healthy"
