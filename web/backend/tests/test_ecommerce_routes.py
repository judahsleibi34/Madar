import unittest
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from unittest.mock import patch

from routes.ecommerce_routes import BrandPayload, CategoryPayload, CatalogItemPayload, ProductPayload, StoreSocialLinksPayload, StoreThemePayload, _clean_slug, _handle_product_delete_error, _managed_catalog_asset_keys, _product_data, _require_multi_category_storage
from routes.public_site_routes import (
    _filter_catalog_taxonomy,
    _localized_catalog_text,
    _public_catalog_item,
    _public_catalog_brand,
    _public_catalog_product,
    build_public_site_profile,
    build_public_store_profile,
)


def translations(name="Product"):
    return {
        "en": {"name": name, "description": "English description"},
        "ar": {"name": "ظ…ظ†طھط¬", "description": "ظˆطµظپ ط¹ط±ط¨ظٹ"},
    }


class EcommerceRoutesTests(unittest.TestCase):

    def test_product_delete_migration_is_mirrored_and_keeps_history_protection(self):
        web_root = Path(__file__).resolve().parents[2]
        database = web_root / "database/migrations/112_allow_unreferenced_product_deletion.sql"
        mirror = web_root / "supabase/migrations/112_allow_unreferenced_product_deletion.sql"
        sql = database.read_text(encoding="utf-8")

        self.assertEqual(database.read_bytes(), mirror.read_bytes())
        self.assertIn("ecommerce_product_variants_product_fk", sql)
        self.assertIn("on delete cascade", sql.lower())
        self.assertIn("if v_schema_version <> 111 then", sql)
        self.assertIn("set schema_version = 112", sql)
        self.assertNotIn("ecommerce_order_items", sql)
        self.assertNotIn("ecommerce_inventory_movements", sql)
        self.assertNotIn("ecommerce_loyalty", sql)

    def test_product_delete_foreign_key_conflict_explains_archive_fallback(self):
        with (
            patch("routes.ecommerce_routes._catalog_schema_version", return_value=112),
            self.assertRaises(HTTPException) as caught,
        ):
            _handle_product_delete_error(Exception("23503 foreign key violation"))

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("Archive it instead", caught.exception.detail)

    def test_product_delete_reports_an_unapplied_schema_migration_separately(self):
        with (
            patch("routes.ecommerce_routes._catalog_schema_version", return_value=110),
            self.assertRaises(HTTPException) as caught,
        ):
            _handle_product_delete_error(Exception("23503 foreign key violation"))

        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(
            caught.exception.detail["code"],
            "product_delete_migration_required",
        )
        self.assertEqual(
            caught.exception.detail["context"],
            {"current_schema": 110, "required_schema": 112},
        )

    def test_product_categories_migration_is_mirrored_and_forward_only(self):
        web_root = Path(__file__).resolve().parents[2]
        database = web_root / "database/migrations/111_add_ecommerce_product_categories.sql"
        mirror = web_root / "supabase/migrations/111_add_ecommerce_product_categories.sql"
        sql = database.read_text(encoding="utf-8")

        self.assertEqual(database.read_bytes(), mirror.read_bytes())
        self.assertIn("create table public.ecommerce_product_categories", sql)
        self.assertIn("from public.ecommerce_products product", sql)
        self.assertIn("if v_schema_version <> 110 then", sql)
        self.assertIn("set schema_version = 111", sql)
        self.assertNotIn("drop table", sql.lower())

    def test_public_store_profile_uses_ecommerce_settings_only(self):
        profile = build_public_store_profile(
            {
                "footer_store_name": "Olive House",
                "description": "Local goods",
                "ecommerce_theme": {"accent": "#287a55"},
            },
            "olive-house",
        )

        self.assertEqual(profile["brand"], "Olive House")
        self.assertEqual(profile["description"], "Local goods")
        self.assertEqual(profile["store_theme"]["accent"], "#287a55")
        self.assertEqual(profile["store_theme"]["background"], "#ffffff")

    def test_site_bound_store_inherits_the_published_builder_theme(self):
        profile = build_public_site_profile(
            {},
            "form-flow",
            {"published_schema": {
                "theme": {
                    "primary": "#365849",
                    "background": "#f3efe7",
                    "softSurface": "#e4ebe2",
                    "text": "#21312a",
                    "muted": "#68736d",
                },
                "siteChrome": {"brand": "Form & Flow"},
            }},
        )

        self.assertEqual(profile["brand"], "Form & Flow")
        self.assertEqual(profile["store_theme"]["accent"], "#365849")
        self.assertEqual(profile["store_theme"]["background"], "#f3efe7")
        self.assertEqual(profile["store_theme"]["surface"], "#e4ebe2")
        self.assertEqual(profile["store_theme"]["text"], "#21312a")

    def test_public_store_profile_does_not_require_a_website_project(self):
        settings = {
            "footer_store_name": "Standalone Store",
            "contact_email": "hello@example.com",
            "phone": "+970590000000",
            "description": "Independent storefront",
        }
        profile = build_public_store_profile(settings, "standalone")

        self.assertEqual(profile["brand"], "Standalone Store")
        self.assertEqual(profile["contact_email"], "hello@example.com")
        self.assertEqual(profile["phone"], "+970590000000")
        self.assertEqual(profile["description"], "Independent storefront")
    def test_store_theme_accepts_complete_hex_colors(self):
        theme = StoreThemePayload(accent="#A33A2B")
        self.assertEqual(theme.accent, "#a33a2b")

    def test_store_theme_rejects_incomplete_colors(self):
        with self.assertRaises(ValidationError):
            StoreThemePayload(accent="#123")

    def test_social_links_require_https_and_are_exposed_publicly(self):
        links = StoreSocialLinksPayload(
            instagram="https://instagram.com/madar",
        )
        profile = build_public_store_profile(
            {"ecommerce_theme": {"social_links": links.model_dump()}},
            "madar",
        )
        self.assertEqual(profile["social_links"], {"instagram": "https://instagram.com/madar"})
        self.assertNotIn("social_links", profile["store_theme"])
        with self.assertRaises(ValidationError):
            StoreSocialLinksPayload(facebook="http://facebook.com/madar")

    def test_category_image_is_validated_and_exposed_publicly(self):
        image_url = "/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp"
        payload = CategoryPayload(
            translations=translations("Home"),
            image_url=image_url,
        )
        self.assertEqual(payload.image_url, image_url)
        self.assertEqual(_managed_catalog_asset_keys([image_url], 7), {
            "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp"
        })
        public_item = _public_catalog_item({
            "id": "category-1",
            "slug": "home",
            "translations": translations("Home"),
            "image_url": image_url,
        }, "en")
        self.assertEqual(public_item["image_url"], image_url)

        with self.assertRaises(ValidationError):
            CategoryPayload(
                translations=translations("Unsafe"),
                image_url="http://example.com/category.svg",
            )

    def test_brand_accepts_one_image_and_is_exposed_publicly(self):
        image_url = "/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp"
        payload = BrandPayload(name="Nike", image_url=image_url)
        self.assertEqual(payload.name, "Nike")
        self.assertEqual(_public_catalog_brand({
            "id": "brand-1", "slug": "nike", "name": "Nike", "image_url": image_url,
        }), {
            "id": "brand-1", "slug": "nike", "name": "Nike", "image_url": image_url,
        })
        with self.assertRaises(HTTPException):
            _managed_catalog_asset_keys([image_url], 8)

    def test_catalog_names_require_letters_and_plain_text(self):
        with self.assertRaisesRegex(ValidationError, "at least one letter"):
            BrandPayload(name="12345")
        with self.assertRaisesRegex(ValidationError, "plain text"):
            BrandPayload(name="<b>Nike</b>")
        with self.assertRaisesRegex(ValidationError, "at least one letter"):
            CatalogItemPayload(translations={"en": {"name": "12345", "description": ""}})
        with self.assertRaisesRegex(ValidationError, "plain text"):
            CatalogItemPayload(translations={"en": {"name": "Chair", "description": "<p>Unsafe</p>"}})

    def test_product_sku_is_generated_when_left_empty(self):
        payload = ProductPayload(
            sku="",
            slug="summer-shirt",
            translations=translations("Summer Shirt"),
        )

        with patch("routes.ecommerce_routes._store_currency_for_tenant", return_value=None):
            data, _category_ids, _tag_ids = _product_data(payload, type("Context", (), {"tenant_id": 7})())

        self.assertRegex(data["sku"], r"^SUMMER-SHIRT-[A-F0-9]{8}$")

    def test_catalog_items_support_inactive_status(self):
        payload = CatalogItemPayload(translations=translations(), status="inactive")

        self.assertEqual(payload.status, "inactive")

    def test_slug_is_generated_from_translated_name(self):
        self.assertEqual(
            _clean_slug(None, translations("Summer Collection")),
            "summer-collection",
        )

    def test_product_payload_keeps_translations_and_full_catalog_fields(self):
        payload = ProductPayload(
            sku="SKU-100",
            translations=translations(),
            price="19.95",
            compare_at_price="24.95",
            cost_price="8.50",
            currency="usd",
            inventory_quantity=12,
            low_stock_threshold=3,
            images=["https://example.com/product.jpg"],
            weight="1.250",
            weight_unit="kg",
            seo_title="Product SEO title",
            seo_description="Product SEO description",
        )

        self.assertEqual(payload.currency, "USD")
        self.assertEqual(payload.translations["ar"]["name"], "ظ…ظ†طھط¬")
        self.assertEqual(payload.inventory_quantity, 12)
        self.assertEqual(str(payload.price), "19.95")

    def test_product_rejects_compare_at_price_below_sale_price(self):
        with self.assertRaises(ValidationError):
            ProductPayload(
                sku="SKU-101",
                translations=translations(),
                price="20.00",
                compare_at_price="10.00",
            )

    def test_product_rejects_equal_regular_and_discounted_prices(self):
        with self.assertRaises(ValidationError):
            ProductPayload(
                sku="SKU-PRICE",
                translations=translations(),
                price="20.00",
                compare_at_price="20.00",
            )


    def test_product_accepts_up_to_ten_managed_media_from_its_workspace(self):
        media = [
            f"/uploads/tenant_7/builder_assets/{index:032x}.{'mp4' if index == 10 else 'webp'}"
            for index in range(1, 11)
        ]
        payload = ProductPayload(translations=translations(), images=media)

        with patch("routes.ecommerce_routes._store_currency_for_tenant", return_value=None):
            data, _category_ids, _tag_ids = _product_data(payload, type("Context", (), {"tenant_id": 7})())

        self.assertEqual(data["images"], media)

    def test_product_rejects_more_than_ten_media_items(self):
        with self.assertRaises(ValidationError):
            ProductPayload(
                translations=translations(),
                images=[f"https://example.com/{index}.webp" for index in range(11)],
            )

    def test_product_rejects_another_workspaces_managed_image(self):
        payload = ProductPayload(
            translations=translations(),
            images=["/uploads/tenant_8/builder_assets/0123456789abcdef0123456789abcdef.webp"],
        )

        with self.assertRaises(HTTPException):
            _product_data(payload, type("Context", (), {"tenant_id": 7})())

    def test_product_accepts_multiple_categories_and_preserves_the_first_as_primary(self):
        first = "11111111-1111-4111-8111-111111111111"
        second = "22222222-2222-4222-8222-222222222222"
        payload = ProductPayload(
            translations=translations(),
            category_ids=[first, second],
        )

        with (
            patch("routes.ecommerce_routes._tenant_row", side_effect=lambda table, item_id, tenant_id: {"id": str(item_id)}),
            patch("routes.ecommerce_routes._store_currency_for_tenant", return_value=None),
        ):
            data, category_ids, _tag_ids = _product_data(
                payload,
                type("Context", (), {"tenant_id": 7})(),
            )

        self.assertEqual(category_ids, [first, second])
        self.assertEqual(data["category_id"], first)
        self.assertNotIn("category_ids", data)

    def test_multi_category_storage_is_checked_before_product_writes_on_legacy_schema(self):
        context = type("Context", (), {"tenant_id": 7})()
        with patch("routes.ecommerce_routes.service_supabase") as service:
            service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = Exception(
                "PGRST205 could not find the table"
            )
            with self.assertRaises(HTTPException) as caught:
                _require_multi_category_storage(context, ["category-1", "category-2"])

        self.assertEqual(caught.exception.status_code, 503)


    def test_product_rejects_non_http_image_urls(self):
        with self.assertRaises(ValidationError):
            ProductPayload(
                sku="SKU-102",
                translations=translations(),
                images=["javascript:alert(1)"],
            )

    def test_public_catalog_uses_locale_fallback_and_hides_internal_values(self):
        self.assertTrue(_localized_catalog_text(translations("Chair"), "ar")["name"])
        product = _public_catalog_product(
            {
                "id": "product-1",
                "slug": "chair",
                "sku": "CHAIR-1",
                "translations": translations("Chair"),
                "price": "20.00",
                "cost_price": "4.00",
                "currency": "USD",
                "track_inventory": True,
                "inventory_quantity": 0,
                "allow_backorder": False,
                "images": ["https://example.com/chair.jpg"],
            },
            locale="en",
            tag_ids=["tag-1"],
        )
        self.assertEqual(product["name"], "Chair")
        self.assertFalse(product["in_stock"])
        self.assertNotIn("cost_price", product)
        self.assertNotIn("inventory_quantity", product)
        self.assertNotIn("created_by", product)
        detail_product = _public_catalog_product(
            {
                "id": "product-1",
                "slug": "chair",
                "translations": translations("Chair"),
                "price": "20.00",
                "track_inventory": True,
                "inventory_quantity": 6,
                "allow_backorder": False,
            },
            locale="en",
            tag_ids=[],
            include_inventory=True,
        )
        self.assertTrue(detail_product["track_inventory"])
        self.assertEqual(detail_product["inventory_quantity"], 6)

    def test_public_category_filter_includes_descendants_and_is_tenant_row_scoped(self):
        categories = [
            {"id": "parent", "slug": "furniture", "parent_id": None},
            {"id": "child", "slug": "chairs", "parent_id": "parent"},
            {"id": "other", "slug": "lighting", "parent_id": None},
        ]
        products = [
            {"id": "one", "category_id": "other", "category_ids": ["other", "child"], "tag_ids": []},
            {"id": "two", "category_id": "other", "tag_ids": []},
        ]
        filtered = _filter_catalog_taxonomy(
            products,
            category_rows=categories,
            tag_rows=[],
            category="furniture",
            tag="",
        )
        self.assertEqual([item["id"] for item in filtered], ["one"])

    def test_public_brand_filter_matches_products_by_brand_id(self):
        products = [
            {"id": "one", "brand_id": "brand-1", "tag_ids": []},
            {"id": "two", "brand_id": None, "tag_ids": []},
        ]
        filtered = _filter_catalog_taxonomy(
            products,
            category_rows=[],
            tag_rows=[],
            brand_rows=[{"id": "brand-1", "slug": "nike"}],
            category="",
            tag="",
            brand="nike",
        )
        self.assertEqual([item["id"] for item in filtered], ["one"])


if __name__ == "__main__":
    unittest.main()
