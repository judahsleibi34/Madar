import unittest
from unittest.mock import patch

import routes.ecommerce_routes as ecommerce_routes
from routes.ecommerce_routes import _attach_product_aggregates, _inventory_state


class EcommerceLowStockTests(unittest.TestCase):
    def test_tracked_simple_inventory_boundaries(self):
        self.assertEqual(_inventory_state({"track_inventory": True, "inventory_quantity": 6, "low_stock_threshold": 5}), "healthy")
        self.assertEqual(_inventory_state({"track_inventory": True, "inventory_quantity": 5, "low_stock_threshold": 5}), "low_stock")
        self.assertEqual(_inventory_state({"track_inventory": True, "inventory_quantity": 2, "low_stock_threshold": 5}), "low_stock")
        self.assertEqual(_inventory_state({"track_inventory": True, "inventory_quantity": 0, "low_stock_threshold": 5}), "out_of_stock")

    def test_untracked_disabled_threshold_and_backorder(self):
        self.assertEqual(_inventory_state({"track_inventory": False, "inventory_quantity": 0, "low_stock_threshold": 5}), "untracked")
        self.assertEqual(_inventory_state({"track_inventory": True, "inventory_quantity": 2, "low_stock_threshold": None}), "healthy")
        self.assertEqual(_inventory_state({"track_inventory": True, "inventory_quantity": 0, "low_stock_threshold": 5, "allow_backorder": True}), "backorder")

    def test_variant_inventory_uses_the_same_unit_level_rules(self):
        variants = [
            {"track_inventory": True, "inventory_quantity": 1, "low_stock_threshold": 3, "active": True},
            {"track_inventory": True, "inventory_quantity": 0, "low_stock_threshold": 3, "active": True},
            {"track_inventory": True, "inventory_quantity": 20, "low_stock_threshold": 3, "active": True},
            {"track_inventory": True, "inventory_quantity": 0, "low_stock_threshold": 3, "active": False},
        ]
        active_states = [_inventory_state(item) for item in variants if item["active"]]
        self.assertEqual(active_states, ["low_stock", "out_of_stock", "healthy"])

    def test_variant_aggregation_ignores_product_stock_and_inactive_variants(self):
        class Query:
            def __init__(self, table_name):
                self.table_name = table_name

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def order(self, *_args, **_kwargs):
                return self

        rows = {
            "ecommerce_product_attributes": [],
            "ecommerce_product_options": [{"id": "option-1", "product_id": "variant-product"}],
            "ecommerce_product_option_values": [],
            "ecommerce_variant_option_values": [],
            "ecommerce_product_variants": [
                {"id": "low", "product_id": "variant-product", "active": True, "track_inventory": True, "inventory_quantity": 1, "low_stock_threshold": 3},
                {"id": "out", "product_id": "variant-product", "active": True, "track_inventory": True, "inventory_quantity": 0, "low_stock_threshold": 3},
                {"id": "healthy", "product_id": "variant-product", "active": True, "track_inventory": True, "inventory_quantity": 20, "low_stock_threshold": 3},
                {"id": "inactive", "product_id": "variant-product", "active": False, "track_inventory": True, "inventory_quantity": 0, "low_stock_threshold": 3},
            ],
        }
        products = [{
            "id": "variant-product", "track_inventory": True,
            "inventory_quantity": 0, "low_stock_threshold": 5,
        }]

        with patch.object(ecommerce_routes.service_supabase, "table", side_effect=lambda name: Query(name)) as table, \
             patch.object(ecommerce_routes, "_rows", side_effect=lambda query: rows[query.table_name]):
            result = _attach_product_aggregates(products, tenant_id=7)

        self.assertEqual(table.call_count, 5)
        self.assertEqual(result[0]["low_stock_count"], 1)
        self.assertEqual(result[0]["out_of_stock_count"], 1)
        self.assertEqual(result[0]["inventory_status"], "low_stock")
        self.assertTrue(result[0]["has_low_stock"])
        self.assertTrue(result[0]["has_out_of_stock"])

if __name__ == "__main__":
    unittest.main()
