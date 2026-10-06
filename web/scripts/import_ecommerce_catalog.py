#!/usr/bin/env python3
"""Validate and import a declarative ecommerce catalog.

Catalog content lives in JSON. This module only validates the schema, expands
option matrices, resolves asset URLs, and performs tenant-scoped upserts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from itertools import product as combinations
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import UUID, uuid5


WEB_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WEB_ROOT / "backend"
DEFAULT_CATALOG = WEB_ROOT / "demo-data" / "clothing-store.json"
LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost", "supabase", "db"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _stable_id(namespace: UUID, kind: str, key: str) -> str:
    return str(uuid5(namespace, f"{kind}:{key}"))


def _localized(name: str, name_ar: str, description: str = "", description_ar: str = "") -> dict:
    return {
        "en": {"name": name, "description": description},
        "ar": {"name": name_ar, "description": description_ar},
    }


def _asset_url(asset_origin: str, asset_path: str) -> str:
    parsed = urlparse(asset_origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("asset_origin must be a public HTTPS origin")
    path = str(asset_path or "").strip()
    if not path.startswith("/") or ".." in Path(path).parts:
        raise ValueError(f"Invalid catalog asset path: {path!r}")
    return urljoin(asset_origin.rstrip("/") + "/", path.lstrip("/"))


def _require_unique(rows: list[dict], field: str, label: str) -> set[str]:
    values = [str(row.get(field) or "").strip() for row in rows]
    if any(not value for value in values) or len(values) != len(set(values)):
        raise ValueError(f"{label} {field} values must be present and unique")
    return set(values)


def load_catalog(path: Path, asset_origin: str) -> dict:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("Unsupported ecommerce catalog schema_version")
    namespace = UUID(str(source["namespace"]))
    brands_source = source.get("brands") or []
    categories_source = source.get("categories") or []
    tags_source = source.get("tags") or []
    products_source = source.get("products") or []
    brand_slugs = _require_unique(brands_source, "slug", "Brand")
    category_slugs = _require_unique(categories_source, "slug", "Category")
    tag_slugs = _require_unique(tags_source, "slug", "Tag")
    product_slugs = _require_unique(products_source, "slug", "Product")
    all_slugs = brand_slugs | category_slugs | tag_slugs | product_slugs
    if any(not SLUG_PATTERN.fullmatch(slug) for slug in all_slugs):
        raise ValueError("Catalog slugs must use lowercase letters, numbers, and single hyphens")

    asset_root = WEB_ROOT / "frontend" / "public"
    for product in products_source:
        relative = Path(str(product.get("image") or "").lstrip("/"))
        if not (asset_root / relative).is_file():
            raise ValueError(f"Missing product image for {product['slug']}: {relative.as_posix()}")

    brands = [{
        **row,
        "id": _stable_id(namespace, "brand", row["slug"]),
        "image_url": _asset_url(asset_origin, row["image"]) if row.get("image") else None,
    } for row in brands_source]
    categories = [{
        "id": _stable_id(namespace, "category", row["slug"]),
        "slug": row["slug"],
        "translations": _localized(row["name"], row["name_ar"], row.get("description", ""), row.get("description_ar", "")),
        "status": row.get("status", "active"),
        "sort_order": int(row.get("sort_order", 0)),
        "image_url": None,
        "parent_id": None,
    } for row in categories_source]
    tags = [{
        "id": _stable_id(namespace, "tag", row["slug"]),
        "slug": row["slug"],
        "translations": _localized(row["name"], row["name_ar"]),
        "status": row.get("status", "active"),
    } for row in tags_source]

    color_catalog = source.get("colors") or {}
    sku_set: set[str] = set()
    products = []
    for product_index, row in enumerate(products_source):
        if row.get("brand") not in brand_slugs or row.get("category") not in category_slugs:
            raise ValueError(f"Unknown brand or category on {row['slug']}")
        if set(row.get("tags") or []) - tag_slugs:
            raise ValueError(f"Unknown tag on {row['slug']}")
        sizes = [str(value).strip() for value in row.get("sizes") or []]
        colors = [str(value).strip() for value in row.get("colors") or []]
        if not sizes or not colors or len(sizes) != len(set(sizes)) or len(colors) != len(set(colors)):
            raise ValueError(f"Product {row['slug']} requires unique size and color values")
        if set(colors) - set(color_catalog):
            raise ValueError(f"Product {row['slug']} references an unknown color")

        image = _asset_url(asset_origin, row["image"])
        size_option_id = _stable_id(namespace, "option", f"{row['slug']}:size")
        color_option_id = _stable_id(namespace, "option", f"{row['slug']}:color")
        size_values = [{
            "id": _stable_id(namespace, "value", f"{row['slug']}:size:{value}"),
            "code": re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-"),
            "value_translations": {"en": value, "ar": value},
            "normalized_value": value.casefold(),
            "sort_order": index,
            "active": True,
            "color_hex": None,
        } for index, value in enumerate(sizes)]
        color_values = [{
            "id": _stable_id(namespace, "value", f"{row['slug']}:color:{value}"),
            "code": value,
            "value_translations": {"en": color_catalog[value]["name"], "ar": color_catalog[value]["name_ar"]},
            "normalized_value": color_catalog[value]["name"].casefold(),
            "sort_order": index,
            "active": True,
            "color_hex": color_catalog[value]["hex"],
        } for index, value in enumerate(colors)]
        options = [
            {"id": size_option_id, "client_id": size_option_id, "code": "size", "name_translations": {"en": "Size", "ar": "المقاس"}, "normalized_name": "size", "required": True, "display_type": "text", "sort_order": 0, "values": size_values},
            {"id": color_option_id, "client_id": color_option_id, "code": "color", "name_translations": {"en": "Color", "ar": "اللون"}, "normalized_name": "color", "required": True, "display_type": "color", "sort_order": 1, "values": color_values},
        ]
        size_by_code = {value["code"]: value for value in size_values}
        color_by_code = {value["code"]: value for value in color_values}
        variants = []
        for variant_index, (size, color) in enumerate(combinations(sizes, colors)):
            size_code = re.sub(r"[^a-z0-9]+", "-", size.lower()).strip("-")
            sku = f"{row['sku_prefix']}-{size_code}-{color}".upper()
            if sku in sku_set:
                raise ValueError(f"Duplicate variant SKU: {sku}")
            sku_set.add(sku)
            variants.append({
                "id": _stable_id(namespace, "variant", f"{row['slug']}:{size_code}:{color}"),
                "sku": sku,
                "barcode": None,
                "price_override": None,
                "compare_at_price_override": None,
                "track_inventory": True,
                "inventory_quantity": 2 if product_index == 3 and variant_index == 0 else 8 + ((product_index * 7 + variant_index * 3) % 23),
                "low_stock_threshold": 4,
                "allow_backorder": False,
                "images": [image],
                "active": True,
                "option_value_ids": [size_by_code[size_code]["id"], color_by_code[color]["id"]],
            })
        attributes = [{
            "id": _stable_id(namespace, "attribute", f"{row['slug']}:{index}"),
            "name_translations": {"en": value["name"], "ar": value["name_ar"]},
            "value_translations": {"en": value["value"], "ar": value["value_ar"]},
            "normalized_name": value["name"].casefold(),
            "sort_order": index,
        } for index, value in enumerate(row.get("attributes") or [])]
        products.append({
            "id": _stable_id(namespace, "product", row["slug"]),
            "slug": row["slug"],
            "sku": row["sku_prefix"],
            "barcode": None,
            "category_slug": row["category"],
            "brand_slug": row["brand"],
            "tag_slugs": row.get("tags") or [],
            "translations": _localized(row["name"], row["name_ar"], row["description"], row["description_ar"]),
            "status": "active",
            "product_type": "physical",
            "price": row["price"],
            "compare_at_price": row.get("compare_at_price"),
            "cost_price": row.get("cost_price"),
            "currency": source["store"]["currency"],
            "track_inventory": True,
            "inventory_quantity": 0,
            "low_stock_threshold": 4,
            "allow_backorder": False,
            "images": [image],
            "weight": row.get("weight"),
            "weight_unit": "kg",
            "requires_shipping": True,
            "taxable": True,
            "seo_title": f"{row['name']} | {source['store']['name']}",
            "seo_description": row["description"],
            "attributes": attributes,
            "options": options,
            "variants": variants,
        })
    image_by_category = {}
    for product in products:
        image_by_category.setdefault(product["category_slug"], product["images"][0])
    for category in categories:
        category["image_url"] = image_by_category.get(category["slug"])
    if set(source.get("featured_products") or []) - product_slugs:
        raise ValueError("featured_products contains an unknown product")
    if set(source.get("featured_categories") or []) - category_slugs:
        raise ValueError("featured_categories contains an unknown category")
    return {
        "store": source["store"],
        "brands": brands,
        "categories": categories,
        "tags": tags,
        "products": products,
        "featured_products": source.get("featured_products") or [],
        "featured_categories": source.get("featured_categories") or [],
    }


def catalog_summary(catalog: dict) -> dict:
    return {
        "brands": len(catalog["brands"]),
        "categories": len(catalog["categories"]),
        "tags": len(catalog["tags"]),
        "products": len(catalog["products"]),
        "variants": sum(len(row["variants"]) for row in catalog["products"]),
        "variant_images": sum(len(row["images"]) for product in catalog["products"] for row in product["variants"]),
    }


def _rows(response) -> list[dict]:
    return getattr(response, "data", None) or []


def _resolve_settings(client, site_identifier: str) -> dict:
    for column in ("subdomain", "standard_path_slug"):
        rows = _rows(client.table("website_settings").select("*").eq(column, site_identifier).limit(2).execute())
        if rows:
            if len(rows) != 1:
                raise RuntimeError(f"Ambiguous website_settings rows for {site_identifier!r}")
            return rows[0]
    raise RuntimeError(f"No website_settings row found for {site_identifier!r}")


def _resolved_id(client, table: str, tenant_id: int, row: dict) -> str:
    existing = _rows(client.table(table).select("id").eq("tenant_id", tenant_id).eq("slug", row["slug"]).limit(1).execute())
    return str(existing[0]["id"]) if existing else row["id"]


def _upsert_taxonomy(client, table: str, tenant_id: int, rows: list[dict]) -> dict[str, str]:
    result = {}
    for row in rows:
        row_id = _resolved_id(client, table, tenant_id, row)
        client.table(table).upsert({**row, "id": row_id, "tenant_id": tenant_id, "created_by": None}, on_conflict="id").execute()
        result[row["slug"]] = row_id
    return result


def _archive_unlisted(client, table: str, tenant_id: int, retained_ids: set[str]) -> int:
    count = 0
    for row in _rows(client.table(table).select("id").eq("tenant_id", tenant_id).execute()):
        if str(row["id"]) not in retained_ids:
            client.table(table).update({"status": "inactive"}).eq("tenant_id", tenant_id).eq("id", row["id"]).execute()
            count += 1
    return count


def apply_catalog(client, settings: dict, catalog: dict, archive_unlisted: bool) -> dict:
    tenant_id = int(settings["tenant_id"])
    brand_ids = _upsert_taxonomy(client, "ecommerce_brands", tenant_id, catalog["brands"])
    category_ids = _upsert_taxonomy(client, "ecommerce_categories", tenant_id, catalog["categories"])
    tag_ids = _upsert_taxonomy(client, "ecommerce_tags", tenant_id, catalog["tags"])
    product_ids = {}
    for row in catalog["products"]:
        existing = _rows(client.table("ecommerce_products").select("id").eq("tenant_id", tenant_id).eq("slug", row["slug"]).limit(1).execute())
        product_id = str(existing[0]["id"]) if existing else row["id"]
        fields = {key:value for key,value in row.items() if key not in {"id","category_slug","brand_slug","tag_slugs","attributes","options","variants"}}
        fields.update({"brand_id":brand_ids[row["brand_slug"]], "status":"active"})
        params = {
            "p_tenant_id":tenant_id, "p_product":fields,
            "p_category_ids":[category_ids[row["category_slug"]]],
            "p_tag_ids":[tag_ids[slug] for slug in row["tag_slugs"]],
            "p_aggregate":{key:row[key] for key in ("attributes","options","variants")},
        }
        if existing:
            snapshot = client.rpc("read_ecommerce_product_catalog_v3_safe", {"p_tenant_id":tenant_id,"p_product_id":product_id}).execute().data
            fields.update(expected_catalog_version=snapshot["catalog_version"],expected_inventory_version=snapshot["inventory_version"])
            params["p_product_id"] = product_id
            result = client.rpc("update_ecommerce_product_v3_safe",params).execute()
        else:
            params.update(p_product_id=product_id,p_user_id=None)
            result = client.rpc("create_ecommerce_product_v3_safe",params).execute()
        product_ids[row["slug"]] = str(result.data["id"])

    archived = {"brands": 0, "categories": 0, "tags": 0, "products": 0}
    if archive_unlisted:
        for label, table, retained in (
            ("products", "ecommerce_products", set(product_ids.values())),
            ("categories", "ecommerce_categories", set(category_ids.values())),
            ("tags", "ecommerce_tags", set(tag_ids.values())),
            ("brands", "ecommerce_brands", set(brand_ids.values())),
        ):
            archived[label] = _archive_unlisted(client, table, tenant_id, retained)

    theme = dict(settings.get("ecommerce_theme") or {})
    theme.update(catalog["store"]["theme"])
    theme["store_identity_ar"] = {"store_name_ar": catalog["store"]["name_ar"], "store_description_ar": catalog["store"]["description_ar"]}
    theme["growth"] = {
        **catalog["store"]["growth"],
        "featured_product_ids": [product_ids[slug] for slug in catalog["featured_products"]],
        "featured_category_ids": [category_ids[slug] for slug in catalog["featured_categories"]],
    }
    client.table("website_settings").update({
        "footer_store_name": catalog["store"]["name"],
        "description": catalog["store"]["description"],
        "ecommerce_theme": theme,
    }).eq("tenant_id", tenant_id).eq("id", settings["id"]).execute()
    return {**catalog_summary(catalog), "tenant_id": tenant_id, "archived": archived}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or import a data-driven ecommerce catalog")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--asset-origin", required=True, help="HTTPS origin that serves catalog image paths")
    parser.add_argument("--site", help="Exact canonical or legacy site identifier; required with --apply")
    parser.add_argument("--expected-tenant-id", type=int, help="Required tenant safety assertion with --apply")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--archive-unlisted", action="store_true", help="Mark catalog rows absent from the file inactive")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = load_catalog(args.catalog.resolve(), args.asset_origin)
    if not args.apply:
        print(json.dumps({"mode": "dry-run", **catalog_summary(catalog)}, indent=2))
        return 0
    if not args.site or args.expected_tenant_id is None:
        raise SystemExit("--site and --expected-tenant-id are required with --apply")
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    from database import SUPABASE_URL, service_supabase

    host = (urlparse(SUPABASE_URL).hostname or "").lower()
    if host not in LOCAL_DATABASE_HOSTS and not args.allow_remote:
        raise SystemExit("Refusing remote database writes without --allow-remote")
    environment = (os.getenv("APP_ENV") or os.getenv("ENV") or "development").strip().lower()
    if environment in {"prod", "production"} and not args.allow_production:
        raise SystemExit("Refusing production writes without --allow-production")
    settings = _resolve_settings(service_supabase, args.site)
    tenant_id = int(settings["tenant_id"])
    if tenant_id != args.expected_tenant_id:
        raise SystemExit(f"Tenant assertion failed: resolved {tenant_id}, expected {args.expected_tenant_id}")
    result = apply_catalog(service_supabase, settings, catalog, args.archive_unlisted)
    print(json.dumps({"mode": "applied", "site": args.site, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
