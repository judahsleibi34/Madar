import unittest
from fastapi import HTTPException
from pydantic import ValidationError

from routes.ecommerce_routes import CatalogItemPayload, ProductPayload, StoreThemePayload, _clean_slug, _product_data
from routes.public_site_routes import (
    _filter_catalog_taxonomy,
    _localized_catalog_text,
    _public_catalog_product,
    build_public_store_profile,
)


def translations(name="Product"):
    return {
        "en": {"name": name, "description": "English description"},
        "ar": {"name": "ظ…ظ†طھط¬", "description": "ظˆطµظپ ط¹ط±ط¨ظٹ"},
    }


class EcommerceRoutesTests(unittest.TestCase):

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
    def test_product_sku_is_generated_when_left_empty(self):
        payload = ProductPayload(
            sku="",
            slug="summer-shirt",
            translations=translations("Summer Shirt"),
        )

        data, _tag_ids = _product_data(payload, type("Context", (), {"tenant_id": 7})())

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


    def test_product_accepts_up_to_four_managed_images_from_its_workspace(self):
        images = [
            f"/uploads/tenant_7/builder_assets/{index:032x}.webp"
            for index in range(1, 5)
        ]
        payload = ProductPayload(translations=translations(), images=images)

        data, _tag_ids = _product_data(payload, type("Context", (), {"tenant_id": 7})())

        self.assertEqual(data["images"], images)

    def test_product_rejects_more_than_four_images(self):
        with self.assertRaises(ValidationError):
            ProductPayload(
                translations=translations(),
                images=[f"https://example.com/{index}.webp" for index in range(5)],
            )

    def test_product_rejects_another_workspaces_managed_image(self):
        payload = ProductPayload(
            translations=translations(),
            images=["/uploads/tenant_8/builder_assets/0123456789abcdef0123456789abcdef.webp"],
        )

        with self.assertRaises(HTTPException):
            _product_data(payload, type("Context", (), {"tenant_id": 7})())


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

    def test_public_category_filter_includes_descendants_and_is_tenant_row_scoped(self):
        categories = [
            {"id": "parent", "slug": "furniture", "parent_id": None},
            {"id": "child", "slug": "chairs", "parent_id": "parent"},
            {"id": "other", "slug": "lighting", "parent_id": None},
        ]
        products = [
            {"id": "one", "category_id": "child", "tag_ids": []},
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


if __name__ == "__main__":
    unittest.main()
