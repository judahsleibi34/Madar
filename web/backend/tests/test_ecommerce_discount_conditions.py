from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from routes import ecommerce_routes as routes
from routes import public_site_routes as public


PRODUCT = "11111111-1111-1111-1111-111111111111"
CONDITION = {
    "audience": "loyalty",
    "product_ids": [PRODUCT],
    "discount_basis_points": 1000,
    "validity_mode": "lifetime",
}
ROOT = Path(__file__).resolve().parents[2]


class EcommerceDiscountConditionsTests(unittest.TestCase):

    def test_condition_validation(self):
        rule = routes.LoyaltyRulePayload(
            threshold_points=100,
            discount_conditions=[
                CONDITION,
                {
                    **CONDITION,
                    "audience": "normal",
                    "validity_mode": "fixed_period",
                    "validity_days": 30,
                },
            ],
        )
        self.assertEqual(len(rule.discount_conditions), 2)

        invalid = (
            {**CONDITION, "product_ids": []},
            {**CONDITION, "product_ids": [PRODUCT, PRODUCT]},
            {**CONDITION, "discount_basis_points": 10001},
            {**CONDITION, "validity_mode": "fixed_period"},
            {**CONDITION, "validity_days": 30},
        )

        for condition in invalid:
            with self.subTest(condition=condition):
                with self.assertRaises(ValidationError):
                    routes.LoyaltyRulePayload(
                        threshold_points=100,
                        discount_conditions=[condition],
                    )

        with self.assertRaises(ValidationError):
            routes.LoyaltyRulePayload(
                threshold_points=100,
                discount_conditions=[
                    {**CONDITION, "audience": "normal"}
                ],
            )

    def test_bridge_never_discards_supported_condition(self):
        database = MagicMock()
        database.rpc.return_value.execute.side_effect = [
            Exception("PGRST202 could not find the function"),
            SimpleNamespace(data={"id": "saved"}),
        ]

        payload = routes.LoyaltyRulePayload(
            threshold_points=100,
            discount_conditions=[CONDITION],
        )

        with (
            patch.object(routes, "service_supabase", database),
            patch.object(
                routes,
                "_require_ecommerce_access",
                return_value=SimpleNamespace(tenant_id=7, user_id=8),
            ),
            patch.object(routes, "_require_role"),
            patch.object(routes, "invalidate_ecommerce_cache"),
        ):
            result = routes.update_loyalty_rule(payload, None, None)

        self.assertEqual(result, {"rule": {"id": "saved"}})
        self.assertEqual(
            database.rpc.call_args.args[0],
            "save_ecommerce_loyalty_rule_safe",
        )

    def test_bridge_refuses_unsupported_condition_without_discarding_it(self):
        database = MagicMock()
        database.rpc.return_value.execute.side_effect = [
            Exception("PGRST202 could not find the function"),
        ]

        payload = routes.LoyaltyRulePayload(
            threshold_points=100,
            discount_conditions=[
                {**CONDITION, "discount_basis_points": 2000}
            ],
        )

        with (
            patch.object(routes, "service_supabase", database),
            patch.object(
                routes,
                "_require_ecommerce_access",
                return_value=SimpleNamespace(tenant_id=7, user_id=8),
            ),
            patch.object(routes, "_require_role"),
            patch.object(routes, "invalidate_ecommerce_cache"),
        ):
            with self.assertRaises(HTTPException) as caught:
                routes.update_loyalty_rule(payload, None, None)

        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(database.rpc.call_count, 1)

    def test_v2_preserves_all_products_and_percentages(self):
        conditions = [
            CONDITION,
            {
                **CONDITION,
                "audience": "normal",
                "discount_basis_points": 2500,
            },
        ]

        database = MagicMock()
        database.rpc.return_value.execute.return_value = SimpleNamespace(
            data={"discount_conditions": conditions}
        )

        payload = routes.LoyaltyRulePayload(
            threshold_points=100,
            discount_conditions=conditions,
        )

        with (
            patch.object(routes, "service_supabase", database),
            patch.object(
                routes,
                "_require_ecommerce_access",
                return_value=SimpleNamespace(tenant_id=7, user_id=8),
            ),
            patch.object(routes, "_require_role"),
            patch.object(routes, "invalidate_ecommerce_cache"),
        ):
            routes.update_loyalty_rule(payload, None, None)

        self.assertEqual(
            database.rpc.call_args.args[0],
            "save_ecommerce_loyalty_rule_v2_safe",
        )
        self.assertEqual(
            database.rpc.call_args.args[1]["p_conditions"][1][
                "discount_basis_points"
            ],
            2500,
        )

    def test_migration_mirror_and_checkout_invariants(self):
        name = "102_add_ecommerce_discount_conditions.sql"

        sql = (ROOT / "database/migrations" / name).read_bytes()
        self.assertEqual(
            sql,
            (ROOT / "supabase/migrations" / name).read_bytes(),
        )

        text = sql.decode().lower()

        for contract in (
            "v_schema_version <> 101",
            "schema_version = 102",
            "basis_points desc",
            "for share",
            "inventory_allocated_quantity",
            "idempotency_conflict",
            "reward_conditions",
            "transaction_type='earn'",
        ):
            self.assertIn(contract, text)

    def test_public_offers_do_not_expose_loyalty_conditions(self):
        query = MagicMock()
        (
            query.select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
        ) = SimpleNamespace(
            data=[
                {
                    "created_at": "2026-09-16T00:00:00Z",
                    "discount_conditions": [
                        CONDITION,
                        {**CONDITION, "audience": "normal"},
                    ],
                }
            ]
        )

        database = MagicMock()
        database.table.return_value = query

        with (
            patch.object(public, "service_supabase", database),
            patch.object(
                public,
                "resolve_public_store_settings",
                return_value={},
            ),
            patch.object(public, "resolve_tenant_id", return_value=7),
            patch.object(public, "enforce_public_rate_limit"),
        ):
            result = public.get_public_store_discounts("demo", None)

        self.assertEqual(len(result["conditions"]), 1)
        self.assertEqual(
            result["conditions"][0]["audience"],
            "normal",
        )
        self.assertEqual(
            result["conditions"][0]["starts_at"],
            "2026-09-16T00:00:00Z",
        )


if __name__ == "__main__":
    unittest.main()
