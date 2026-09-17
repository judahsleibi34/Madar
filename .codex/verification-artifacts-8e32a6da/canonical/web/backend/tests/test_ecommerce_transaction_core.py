import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from starlette.responses import Response
from starlette.requests import Request

from routes import public_site_routes
from routes.public_site_routes import PublicStoreOrderCreate


WEB_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = WEB_ROOT / "database" / "migrations" / "094_create_ecommerce_transaction_core.sql"
MIRROR = WEB_ROOT / "supabase" / "migrations" / "094_create_ecommerce_transaction_core.sql"


def order_payload(**overrides):
    payload = {
        "idempotency_key": "checkout-1234567890abcdef",
        "customer_name": "Test Customer",
        "email": "buyer@example.com",
        "phone": "+970590000000",
        "address_line_1": "1 Main Street",
        "city": "Ramallah",
        "country": "PS",
        "service_area_id": "95000000-0000-0000-0000-000000000001",
        "street": "1 Main Street",
        "items": [{"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 2}],
    }
    payload.update(overrides)
    return payload


class RpcResult:
    data = {
        "duplicate": False,
        "order": {
            "id": "22222222-2222-2222-2222-222222222222",
            "order_number": "MD-20260912-ABC12345",
            "status": "pending",
            "payment_status": "unpaid",
            "payment_method": "cash_on_delivery",
            "currency": "ILS",
            "subtotal": "20.00",
            "discount_total": "0.00",
            "total": "20.00",
        },
    }


class RpcOnlyClient:
    def __init__(self):
        self.name = None
        self.params = None

    def rpc(self, name, params):
        self.name = name
        self.params = params
        return SimpleNamespace(execute=lambda: RpcResult())

    def table(self, _name):
        raise AssertionError("public checkout must not perform split table writes")


class EcommerceTransactionCoreTests(unittest.TestCase):
    def test_order_requires_idempotency_key(self):
        with self.assertRaises(ValidationError):
            PublicStoreOrderCreate(**order_payload(idempotency_key=None))

    def test_public_order_uses_single_transaction_rpc_and_server_payload(self):
        client = RpcOnlyClient()
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
        payload = PublicStoreOrderCreate(**order_payload())

        with (
            patch.object(public_site_routes, "service_supabase", client),
            patch.object(public_site_routes, "enforce_public_rate_limit"),
            patch.object(public_site_routes, "resolve_public_store_settings", return_value={"tenant_id": 7}),
            patch.object(public_site_routes, "resolve_tenant_id", return_value=7),
        ):
            result = public_site_routes.create_public_store_order("test-store", payload, request, Response())

        self.assertEqual(client.name, "create_ecommerce_order_safe")
        self.assertEqual(client.params["p_order"]["tenant_id"], 7)
        self.assertEqual(client.params["p_order"]["items"][0]["quantity"], 2)
        self.assertNotIn("price", client.params["p_order"]["items"][0])
        self.assertEqual(len(client.params["p_idempotency_key_hash"]), 64)
        self.assertEqual(len(client.params["p_request_hash"]), 64)
        self.assertEqual(len(client.params["p_confirmation_token_hash"]), 64)
        self.assertEqual(len(result["confirmation_token"]), 64)
        self.assertEqual(result["order"]["currency"], "ILS")
        self.assertIsNone(client.params["p_customer_id"])

    def test_migration_is_mirrored_and_contains_concurrency_guards(self):
        sql = MIGRATION.read_bytes()
        self.assertEqual(sql, MIRROR.read_bytes())
        text = sql.decode("utf-8").lower()
        self.assertIn("pg_advisory_xact_lock", text)
        self.assertIn("for update of product", text)
        self.assertIn("ecommerce_orders_idempotency_unique_idx", text)
        self.assertIn("inventory_quantity = inventory_quantity - v_allocated", text)
        self.assertIn("create_ecommerce_order_safe", text)

    def test_migration_has_idempotent_inventory_restoration_foundation(self):
        text = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("restore_ecommerce_order_inventory_safe", text)
        self.assertIn("ecommerce_inventory_one_restoration_per_item_idx", text)
        self.assertIn("inventory_quantity = inventory_quantity + v_item.inventory_allocated_quantity", text)
        self.assertIn("inventory_restored_at = now()", text)
        self.assertIn("set status = p_reason", text)
        self.assertIn("p_reason not in ('cancelled', 'rejected')", text)


if __name__ == "__main__":
    unittest.main()
