import unittest
from unittest.mock import patch
from uuid import UUID

from pydantic import ValidationError
from starlette.requests import Request

from routes.ecommerce_routes import StoreGrowthPayload, _validate_featured_rows
from routes.public_site_routes import (
    _public_catalog_product,
    _public_store_growth,
    _storefront_sitemap_xml,
    build_public_store_profile,
)


def make_request(host="www.madarportal.com"):
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", host.encode("ascii"))],
        "scheme": "https",
        "server": (host, 443),
        "client": ("127.0.0.1", 1234),
        "query_string": b"",
    })


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args): return self
    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self
    def in_(self, key, values):
        self.rows = [row for row in self.rows if str(row.get(key)) in {str(value) for value in values}]
        return self
    def execute(self): return type("Response", (), {"data": self.rows})()


class Client:
    def __init__(self, rows): self.rows = rows
    def table(self, _name): return Query(list(self.rows))


class EcommerceGrowthSeoTests(unittest.TestCase):
    def test_growth_payload_accepts_relative_or_https_links(self):
        self.assertEqual(StoreGrowthPayload(announcement_link="/shop/catalog").announcement_link, "/shop/catalog")
        self.assertEqual(StoreGrowthPayload(announcement_link="https://example.com/sale").announcement_link, "https://example.com/sale")

    def test_growth_payload_rejects_scripts_credentials_and_duplicates(self):
        for link in ("javascript:alert(1)", "//evil.example/path", "https://user:secret@example.com"):
            with self.subTest(link=link), self.assertRaises(ValidationError):
                StoreGrowthPayload(announcement_link=link)
        with self.assertRaises(ValidationError):
            StoreGrowthPayload(featured_product_ids=[UUID(int=1), UUID(int=1)])

    def test_enabled_announcement_requires_localized_copy(self):
        with self.assertRaises(ValidationError):
            StoreGrowthPayload(announcement_enabled=True)

    def test_public_profile_separates_theme_from_growth(self):
        profile = build_public_store_profile({
            "footer_store_name": "Olive House",
            "ecommerce_theme": {"accent": "#123456", "growth": {"seo_title_ar": "متجر الزيتون", "featured_product_ids": ["one", "one"]}},
        }, "olive")
        self.assertNotIn("growth", profile["store_theme"])
        self.assertEqual(profile["growth"]["seo_title_ar"], "متجر الزيتون")
        self.assertEqual(profile["growth"]["featured_product_ids"], ["one"])

    def test_availability_uses_inventory_and_backorder_truth(self):
        base = {"id": "one", "slug": "one", "translations": {"en": {"name": "One"}}, "price": "10", "currency": "USD", "track_inventory": True, "inventory_quantity": 0, "images": []}
        unavailable = _public_catalog_product({**base, "allow_backorder": False}, locale="en", tag_ids=[])
        backorder = _public_catalog_product({**base, "allow_backorder": True}, locale="en", tag_ids=[])
        self.assertEqual(unavailable["seo_availability"], "OutOfStock")
        self.assertEqual(backorder["seo_availability"], "BackOrder")

    def test_feature_validation_is_tenant_and_active_scoped(self):
        selected = UUID(int=1)
        rows = [{"id": str(selected), "tenant_id": 7, "status": "active"}, {"id": str(UUID(int=2)), "tenant_id": 8, "status": "active"}]
        with patch("routes.ecommerce_routes.service_supabase", Client(rows)):
            _validate_featured_rows(7, "ecommerce_products", [selected])
            with self.assertRaisesRegex(Exception, "active items from this store"):
                _validate_featured_rows(7, "ecommerce_products", [UUID(int=2)])

    def test_sitemap_contains_only_supplied_active_public_rows(self):
        settings = {"tenant_id": 7, "standard_path_slug": "olive", "updated_at": "2026-09-01T10:00:00Z"}
        rows = ([{"slug": "gifts", "updated_at": "2026-09-02"}], [], [{"slug": "soap", "updated_at": "2026-09-03"}], [])
        with patch("routes.public_site_routes._cached_public_catalog_rows", return_value=rows):
            xml = _storefront_sitemap_xml(settings, "olive", make_request())
        self.assertIn("/site/olive/shop</loc>", xml)
        self.assertIn("category=gifts", xml)
        self.assertIn("/product/soap", xml)
        for forbidden in ("checkout", "confirmation", "dashboard", "token"):
            self.assertNotIn(forbidden, xml)


if __name__ == "__main__":
    unittest.main()
