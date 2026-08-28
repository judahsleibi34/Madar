from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
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
PRODUCT_IMAGE_ASSET_PATTERN = re.compile(
    r"^/uploads/(?P<key>tenant_(?P<tenant>[1-9][0-9]*)/builder_assets/[a-f0-9]{32}\.(?:png|jpg|webp))$"
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
    images: list[str] = Field(default_factory=list, max_length=4)
    weight: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    weight_unit: Literal["g", "kg", "lb", "oz"] = "kg"
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
            is_managed_image = bool(PRODUCT_IMAGE_ASSET_PATTERN.fullmatch(url))
            is_secure_external_image = bool(re.match(r"^https://", url, re.IGNORECASE)) and not re.search(r"\.svgz?(?:[?#]|$)", url, re.IGNORECASE)
            if not (is_managed_image or is_secure_external_image) or len(url) > 2048:
                raise ValueError("Product images must be secure uploaded images")
            cleaned.append(url)
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def validate_pricing(self):
        if self.compare_at_price is not None and self.compare_at_price <= self.price:
            raise ValueError("Discounted price must be lower than the regular price")
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
        match = PRODUCT_IMAGE_ASSET_PATTERN.fullmatch(str(image or "").strip())
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
    data = payload.model_dump(mode="json", exclude={"tag_ids"})
    data.update(
        tenant_id=context.tenant_id,
        category_id=category_id,
        slug=slug,
        sku=payload.sku or _generate_sku(slug),
        barcode=str(payload.barcode or "").strip() or None,
    )
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


def _catalog_for_tenant(tenant_id: int) -> dict[str, list[dict[str, Any]]]:
    tags = _rows(service_supabase.table("ecommerce_tags").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True))
    categories = _rows(service_supabase.table("ecommerce_categories").select("*").eq("tenant_id", tenant_id).order("sort_order").order("created_at"))
    products = _rows(service_supabase.table("ecommerce_products").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True))
    return {"tags": tags, "categories": categories, "products": _attach_product_tags(products, tenant_id)}


def _store_theme_for_tenant(tenant_id: int) -> dict[str, str]:
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


@router.get("/theme")
def get_store_theme(request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    return {"theme": _store_theme_for_tenant(context.tenant_id)}


@router.put("/theme")
def update_store_theme(payload: StoreThemePayload, request: Request, response: Response):
    context = _require_ecommerce_access(request, response)
    _require_role(context)
    theme = payload.model_dump()
    rows = _rows(
        service_supabase.table("website_settings")
        .update({"ecommerce_theme": theme})
        .eq("tenant_id", int(context.tenant_id))
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Website settings not found")
    invalidate_ecommerce_cache(context.tenant_id)
    return {"theme": theme}

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
