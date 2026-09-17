import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from routes.ecommerce_routes import DeliveryAreasUpdate, OrderStatusUpdate
from routes.public_site_routes import PublicStoreOrderCreate


WEB_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = WEB_ROOT / "database" / "migrations" / "095_create_ecommerce_delivery_and_order_operations.sql"
MIRROR = WEB_ROOT / "supabase" / "migrations" / "095_create_ecommerce_delivery_and_order_operations.sql"


class EcommerceDeliveryOrderOperationsTests(unittest.TestCase):
    def test_canonical_delivery_catalog_is_exact_and_has_one_jerusalem(self):
        text = MIGRATION.read_text(encoding="utf-8")
        seed = text.split("insert into public.ecommerce_service_areas", 1)[1].split("create table public.ecommerce_tenant_service_areas", 1)[0]
        codes = re.findall(r"'95000000-[^']+','([^']+)','([^']+)','([^']+)',true,\d+", seed)
        self.assertEqual(
            codes,
            [
                ("ramallah", "Ramallah", "رام الله"),
                ("al-bireh", "Al-Bireh", "البيرة"),
                ("nablus", "Nablus", "نابلس"),
                ("al-khalil", "Hebron / Al-Khalil", "الخليل"),
                ("bethlehem", "Bethlehem", "بيت لحم"),
                ("jenin", "Jenin", "جنين"),
                ("tulkarm", "Tulkarm", "طولكرم"),
                ("qalqilya", "Qalqilya", "قلقيلية"),
                ("jericho", "Jericho", "أريحا"),
                ("salfit", "Salfit", "سلفيت"),
                ("tubas", "Tubas", "طوباس"),
                ("jerusalem", "Jerusalem", "القدس"),
            ],
        )
        self.assertEqual(seed.count("'jerusalem'"), 1)
        for excluded in (
            "gaza city", "khan younis", "rafah", "deir al-balah",
            "tel aviv", "haifa", "beersheba", "nazareth", "acre", "akko",
            "ashdod", "ashkelon", "netanya", "petah tikva", "rishon lezion",
            "holon", "bnei brak", "ramat gan", "herzliya", "kfar saba",
            "ra'anana", "lod", "ramla", "eilat",
        ):
            self.assertNotIn(excluded, seed.lower())

    def test_tenant_coverage_has_no_default_rows_and_complete_set_rpc(self):
        text = MIGRATION.read_text(encoding="utf-8").lower()
        catalog_end = text.index("create table public.ecommerce_tenant_service_areas")
        rpc_start = text.index("create or replace function public.set_ecommerce_delivery_areas_safe")
        order_rpc_start = text.index("create or replace function public.create_ecommerce_order_safe", rpc_start)
        coverage_section = text[catalog_end:order_rpc_start]
        self.assertNotIn("insert into public.ecommerce_tenant_service_areas", text[:rpc_start])
        self.assertIn("update public.ecommerce_tenant_service_areas", coverage_section)
        self.assertIn("set enabled = false", coverage_section)
        self.assertIn("where tenant_id = p_tenant_id", coverage_section)
        self.assertIn("on conflict (tenant_id, service_area_id) do update", coverage_section)

    def test_order_rpc_locks_and_validates_delivery_inside_transaction(self):
        text = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("pg_advisory_xact_lock", text)
        self.assertIn("mapping.tenant_id = v_tenant_id and mapping.enabled", text)
        self.assertIn("area.active", text)
        self.assertIn("ecommerce_delivery_area_unavailable", text)
        self.assertIn("service_area_code,service_area_name_en,service_area_name_ar", text)
        self.assertIn("confirmation_token_hash", text)
        self.assertIn("variant_snapshot", text)
        self.assertIn("selected_options_snapshot", text)

    def test_lifecycle_inventory_history_and_cod_are_separate(self):
        text = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("transition_ecommerce_order_status_safe", text)
        self.assertIn("restore_ecommerce_order_inventory_safe", text)
        self.assertIn("ecommerce_order_transition_invalid", text)
        self.assertIn("ecommerce_order_status_history", text)
        self.assertIn("unique (tenant_id, order_id, idempotency_key_hash)", text)
        cod = text.split("create or replace function public.collect_ecommerce_cod_payment_safe", 1)[1]
        cod = cod.split("revoke all on function", 1)[0]
        self.assertIn("payment_status='collected'", cod)
        self.assertNotIn("set status=", cod)
        self.assertNotIn("restore_ecommerce_order_inventory_safe", cod)

    def test_request_models_reject_unstructured_checkout_and_invalid_status(self):
        base = {
            "idempotency_key": "checkout-1234567890abcdef",
            "customer_name": "Buyer",
            "email": "buyer@example.com",
            "phone": "+970590000000",
            "items": [{"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 1}],
        }
        with self.assertRaises(ValidationError):
            PublicStoreOrderCreate(**base)
        order = PublicStoreOrderCreate(
            **base,
            service_area_id="95000000-0000-0000-0000-000000000001",
            street="Main Street",
        )
        self.assertEqual(order.payment_method, "cash_on_delivery")
        with self.assertRaises(ValidationError):
            OrderStatusUpdate(status="pending")

    def test_delivery_selection_deduplicates_ids(self):
        selected = DeliveryAreasUpdate(enabled_service_area_ids=[
            "95000000-0000-0000-0000-000000000001",
            "95000000-0000-0000-0000-000000000001",
        ])
        self.assertEqual(len(selected.enabled_service_area_ids), 1)

    def test_migration_is_mirrored_and_guarded_94_to_95(self):
        self.assertEqual(MIGRATION.read_bytes(), MIRROR.read_bytes())
        text = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("v_schema_version <> 94", text)
        self.assertIn("set schema_version = 95", text)


if __name__ == "__main__":
    unittest.main()
