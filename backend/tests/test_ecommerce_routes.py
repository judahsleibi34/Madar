import unittest
from pydantic import ValidationError

from routes.ecommerce_routes import ProductPayload, _clean_slug
from routes.public_site_routes import (
    _filter_catalog_taxonomy,
    _localized_catalog_text,
    _public_catalog_product,
)


def translations(name="Product"):
    return {
        "en": {"name": name, "description": "English description"},
        "ar": {"name": "منتج", "description": "وصف عربي"},
    }


class EcommerceRoutesTests(unittest.TestCase):
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
        self.assertEqual(payload.translations["ar"]["name"], "منتج")
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
