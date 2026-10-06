import sys
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from pathlib import Path

from routes.ecommerce_routes import ProductPayload


WEB_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WEB_ROOT / "scripts"))

from import_ecommerce_catalog import apply_catalog, catalog_summary, load_catalog  # noqa: E402


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

    def test_import_creates_products_with_one_atomic_command_each(self):
        client=Mock()
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value=SimpleNamespace(data=[])
        client.rpc.side_effect=lambda name,params: SimpleNamespace(execute=lambda:SimpleNamespace(data={"id":params["p_product_id"]}))
        def taxonomy(_client,_table,_tenant,rows):return {row['slug']:row['id'] for row in rows}
        with patch('import_ecommerce_catalog._upsert_taxonomy',side_effect=taxonomy):
            apply_catalog(client,{'tenant_id':7,'id':1},self.catalog,False)
        self.assertEqual(client.rpc.call_count,len(self.catalog['products']))
        for call in client.rpc.call_args_list:
            self.assertEqual(call.args[0],'create_ecommerce_product_v3_safe')
            params=call.args[1];self.assertEqual(params['p_tenant_id'],7)
            self.assertEqual(len(params['p_category_ids']),1)
            self.assertIn('options',params['p_aggregate']);self.assertEqual(params['p_product']['status'],'active')
        client.table.return_value.upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
