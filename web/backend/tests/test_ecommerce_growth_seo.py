import unittest
from unittest.mock import patch
from uuid import UUID

from pydantic import ValidationError
from starlette.requests import Request

from routes.ecommerce_routes import StoreGrowthPayload, StoreLandingPagePayload, _validate_featured_rows
from routes.public_site_routes import (
    _public_catalog_product,
    _public_store_growth,
    _public_store_landing_page,
    _public_sale_summary,
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
    def test_public_sale_summary_uses_highest_valid_discount(self):
        summary = _public_sale_summary([
            {"price": "80", "compare_at_price": "100"},
            {"price": "45", "compare_at_price": "90"},
            {"price": "30", "compare_at_price": "30"},
            {"price": "invalid", "compare_at_price": "90"},
        ])
        self.assertEqual(summary, {"active": True, "max_percentage": 50})
        self.assertEqual(
            _public_sale_summary([{"price": "10", "compare_at_price": None}]),
            {"active": False, "max_percentage": 0},
        )

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

    def test_landing_page_validates_interval_media_and_links(self):
        payload = StoreLandingPagePayload(interval_ms=7000, slides=[{
            "image_url": "https://example.com/campaign.webp",
            "title_en": "New season",
            "link": "/shop/catalog",
        }])
        self.assertEqual(payload.interval_ms, 7000)
        self.assertEqual(payload.slides[0].link, "/shop/catalog")
        demo = StoreLandingPagePayload(slides=[{"image_url": "/demo/landing/editorial-essentials.webp"}])
        self.assertEqual(demo.slides[0].image_url, "/demo/landing/editorial-essentials.webp")
        for invalid in (
            {"interval_ms": 1000, "slides": []},
            {"slides": [{"image_url": "javascript:alert(1)"}]},
            {"slides": [{"image_url": "https://example.com/a.webp", "link": "//evil.example"}]},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                StoreLandingPagePayload(**invalid)

    def test_public_landing_page_is_separate_from_theme(self):
        saved = {"landing_page": {"autoplay_enabled": True, "interval_ms": 6500, "slides": [{"id": "one", "image_url": "https://example.com/hero.webp", "title_en": "Sale", "link": "/shop/catalog"}]}}
        public = _public_store_landing_page(saved)
        self.assertEqual(public["interval_ms"], 6500)
        self.assertEqual(public["slides"][0]["title_en"], "Sale")
        profile = build_public_store_profile({"ecommerce_theme": {"accent": "#123456", **saved}}, "olive")
        self.assertNotIn("landing_page", profile["store_theme"])
        self.assertEqual(profile["landing_page"]["slides"][0]["image_url"], "https://example.com/hero.webp")

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
        settings = {"tenant_id": 7, "subdomain": "olive", "standard_path_slug": "olive-old", "updated_at": "2026-09-01T10:00:00Z"}
        rows = ([{"slug": "gifts", "updated_at": "2026-09-02"}], [], [{"slug": "soap", "updated_at": "2026-09-03"}], [])
        with patch("routes.public_site_routes._cached_public_catalog_rows", return_value=rows):
            xml = _storefront_sitemap_xml(settings, "olive", make_request())
        self.assertIn("https://olive.madarportal.com/shop</loc>", xml)
        self.assertIn("category=gifts", xml)
        self.assertIn("/product/soap", xml)
        for forbidden in ("checkout", "confirmation", "dashboard", "token"):
            self.assertNotIn(forbidden, xml)


if __name__ == "__main__":
    unittest.main()
