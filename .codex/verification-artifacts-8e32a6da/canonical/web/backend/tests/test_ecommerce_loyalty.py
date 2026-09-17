import unittest
from pathlib import Path

from pydantic import ValidationError

from routes.ecommerce_routes import LoyaltyRulePayload


WEB_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = WEB_ROOT / "database" / "migrations" / "097_create_ecommerce_verified_loyalty_core.sql"
MIRROR = WEB_ROOT / "supabase" / "migrations" / "097_create_ecommerce_verified_loyalty_core.sql"


class EcommerceLoyaltyTests(unittest.TestCase):
    def test_rule_payload_enforces_validity_contract(self):
        common = {
            "threshold_points": 100,
            "reward_product_id": "11111111-1111-1111-1111-111111111111",
        }
        lifetime = LoyaltyRulePayload(**common)
        self.assertEqual(lifetime.earning_rate_basis_points, 500)
        self.assertEqual(lifetime.validity_mode, "lifetime")
        with self.assertRaises(ValidationError):
            LoyaltyRulePayload(**common, validity_mode="fixed_period")
        with self.assertRaises(ValidationError):
            LoyaltyRulePayload(**common, validity_mode="lifetime", validity_days=30)

    def test_migration_is_mirrored_and_guarded_96_to_97(self):
        self.assertEqual(MIGRATION.read_bytes(), MIRROR.read_bytes())
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("v_schema_version <> 96", sql)
        self.assertIn("schema_version = 97", sql)
        for table in (
            "ecommerce_loyalty_accounts",
            "ecommerce_loyalty_rules",
            "ecommerce_loyalty_entitlements",
            "ecommerce_loyalty_transactions",
        ):
            self.assertIn(f"create table public.{table}", sql)

    def test_verified_identity_and_guest_boundary_are_server_authoritative(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("p_customer_id integer", sql)
        self.assertIn("auth_id is not null and email_verified=true", sql)
        self.assertIn("customer_id=p_customer_id", sql)
        self.assertNotIn("customer_email=", sql)
        self.assertNotIn("customer_phone=", sql)

    def test_ledger_projection_locking_and_idempotency_are_explicit(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("ecommerce_loyalty_ledger_append_only", sql)
        self.assertIn("before update or delete", sql)
        self.assertIn("unique (tenant_id,idempotency_key)", sql)
        self.assertIn("for update", sql)
        self.assertIn("version=version+1", sql)
        self.assertIn("concat_ws(':','earn',p_tenant_id,p_order_id,v_rule.version)", sql)

    def test_earning_formula_conditions_and_single_threshold_unlock_are_explicit(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("v_order.status<>'delivered'", sql)
        self.assertIn("v_order.payment_status not in ('collected','paid')", sql)
        self.assertIn("floor((v_order.total::numeric*v_rule.earning_rate_basis_points::numeric)/10000)", sql)
        self.assertIn("v_balance>=v_rule.threshold_points", sql)
        self.assertNotIn("while v_balance", sql)
        self.assertGreaterEqual(sql.count("process_ecommerce_loyalty_order_safe(p_tenant_id,p_order_id)"), 4)

    def test_entitlement_snapshot_reuse_expiry_revocation_and_discount_snapshot(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("reward_discount_basis_points integer not null check (reward_discount_basis_points = 1000)", sql)
        self.assertIn("status in ('active','expired','revoked')", sql)
        self.assertIn("reward_unlock_reversal", sql)
        self.assertIn("loyalty_entitlement_id", sql)
        self.assertIn("discount_source", sql)
        self.assertIn("v_entitlement.reward_product_id=v_product.id", sql)
        self.assertNotIn("set status='redeemed'", sql)


if __name__ == "__main__":
    unittest.main()
