import sys
import unittest
from pathlib import Path

from routes.ecommerce_routes import ProductPayload


WEB_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WEB_ROOT / "scripts"))

from import_ecommerce_catalog import catalog_summary, load_catalog  # noqa: E402


CATALOG_PATH = WEB_ROOT / "demo-data" / "clothing-store.json"


class EcommerceCatalogImportTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(CATALOG_PATH, "https://catalog.example.test")

    def test_catalog_is_fully_data_driven_and_has_complete_variant_images(self):
        summary = catalog_summary(self.catalog)
        self.assertEqual(summary["brands"], 4)
        self.assertEqual(summary["categories"], 6)
        self.assertEqual(summary["products"], 12)
        self.assertEqual(summary["variants"], 102)
        self.assertEqual(summary["variant_images"], summary["variants"])
        for product in self.catalog["products"]:
            self.assertTrue(product["images"])
            self.assertTrue(all(variant["images"] for variant in product["variants"]))
            expected = 1
            for option in product["options"]:
                expected *= len(option["values"])
            self.assertEqual(len(product["variants"]), expected, product["slug"])

    def test_catalog_products_satisfy_the_production_api_contract(self):
        category_ids = {row["slug"]: row["id"] for row in self.catalog["categories"]}
        brand_ids = {row["slug"]: row["id"] for row in self.catalog["brands"]}
        tag_ids = {row["slug"]: row["id"] for row in self.catalog["tags"]}
        for row in self.catalog["products"]:
            payload = {
                key: value for key, value in row.items()
                if key not in {"id", "category_slug", "brand_slug", "tag_slugs"}
            }
            payload.update({
                "category_id": category_ids[row["category_slug"]],
                "brand_id": brand_ids[row["brand_slug"]],
                "tag_ids": [tag_ids[slug] for slug in row["tag_slugs"]],
                "brand": "",
            })
            validated = ProductPayload.model_validate(payload)
            self.assertEqual(validated.slug, row["slug"])


if __name__ == "__main__":
    unittest.main()
