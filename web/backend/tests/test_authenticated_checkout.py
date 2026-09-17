"""HTTP regressions for the (provider user, public.users profile) auth contract."""
import os
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import public_site_routes as routes
from tests.test_ecommerce_transaction_core import order_payload, RpcOnlyClient


class AuthenticatedCheckoutTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.rpc = RpcOnlyClient()
        # Provider UUID and local integer profile identity must never be confused.
        self.profile = {"id": 42, "auth_id": "provider-uuid", "tenant_id": 8,
                        "email": "verified@example.com", "email_verified": True}
        self.auth = MagicMock(return_value=(SimpleNamespace(id="provider-uuid"), self.profile))
        for name, value in (
            ("service_supabase", self.rpc),
            ("get_authenticated_user_row", self.auth),
            ("enforce_public_rate_limit", MagicMock()),
            ("resolve_public_store_settings", MagicMock(return_value={"tenant_id": 7})),
            ("resolve_tenant_id", MagicMock(return_value=7)),
        ):
            patcher = patch.object(routes, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def checkout(self, cookie=None):
        headers = {"cookie": cookie} if cookie else {}
        return self.client.post("/public/sites/test-store/orders", json=order_payload(), headers=headers)

    def test_authenticated_cod_checkout_uses_local_profile_identity(self):
        for cookie in ("madar_access_token=access", "madar_refresh_token=refresh"):
            with self.subTest(cookie=cookie):
                response = self.checkout(cookie)
                self.assertEqual(response.status_code, 201, response.text)
                self.assertEqual(response.json()["order"]["payment_method"], "cash_on_delivery")
                self.assertEqual(self.rpc.params["p_customer_id"], 42)
                self.assertEqual(self.rpc.params["p_order"]["verified_customer_id"], 42)
                self.assertEqual(self.rpc.params["p_order"]["tenant_id"], 7)
                self.assertEqual(self.rpc.params["p_order"]["email"], "buyer@example.com")
                self.assertEqual(self.rpc.params["p_order"]["items"][0]["quantity"], 2)
                self.assertEqual(self.auth.call_args.kwargs, {
                    "allow_admin_account_access": False, "reject_admin_account_access": True})

    def test_guest_checkout_does_not_infer_identity_from_contact(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 201, response.text)
        self.auth.assert_not_called()
        self.assertIsNone(self.rpc.params["p_customer_id"])
        self.assertIsNone(self.rpc.params["p_order"]["verified_customer_id"])

    def test_rejected_session_keeps_existing_guest_checkout_behavior(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.auth.side_effect = HTTPException(status_code=status, detail="Rejected session")
                response = self.checkout("madar_access_token=invalid")
                self.assertEqual(response.status_code, 201, response.text)
                self.assertIsNone(self.rpc.params["p_customer_id"])

    def test_loyalty_read_uses_same_profile_and_store(self):
        database = MagicMock()
        database.rpc.return_value.execute.return_value = SimpleNamespace(data=None)
        query = database.table.return_value
        for method in ("select", "eq", "limit", "order"):
            getattr(query, method).return_value = query
        query.execute.return_value = SimpleNamespace(data=[])
        with patch.object(routes, "service_supabase", database):
            response = self.client.get("/public/sites/test-store/loyalty/me",
                                       headers={"cookie": "madar_access_token=access"})
        self.assertEqual(response.status_code, 200, response.text)
        database.rpc.assert_called_once_with("expire_ecommerce_loyalty_entitlements_safe", {
            "p_tenant_id": 7, "p_customer_id": 42})
        self.assertEqual(query.eq.call_args_list.count(call("customer_id", 42)), 3)
        self.assertEqual(query.eq.call_args_list.count(call("tenant_id", 7)), 3)

    def test_guest_loyalty_read_requires_authentication(self):
        self.auth.side_effect = HTTPException(status_code=401, detail="Not logged in")
        response = self.client.get("/public/sites/test-store/loyalty/me")
        self.assertEqual(response.status_code, 401)


# Opt in only against an explicitly disposable, isolated PostgreSQL database.
# The ordinary offline suite runs the HTTP contract tests above without a DB.
@unittest.skipUnless(os.getenv("MADAR_CHECKOUT_TEST_DATABASE_URL"), "isolated PostgreSQL integration opt-in required")
class CheckoutDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        database_url = os.environ["MADAR_CHECKOUT_TEST_DATABASE_URL"]
        if urlsplit(database_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError("checkout integration requires a disposable loopback database")
        cls.db = psycopg.connect(database_url, autocommit=True)
        cls.addClassCleanup(cls.db.close)
        cls.db.execute("""
            create role anon nologin; create role authenticated nologin; create role service_role nologin;
            create schema auth; create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
            create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
            create schema storage; create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
            create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
            alter table storage.objects enable row level security;
            create schema extensions; create extension pgcrypto schema extensions;
        """)
        migrations = Path(__file__).resolve().parents[2] / "database" / "migrations"
        files = sorted(migrations.glob("*.sql"))
        if not files:
            raise RuntimeError("checkout rehearsal requires the complete migration tree")
        for migration in files:
            cls.db.execute(migration.read_text(encoding="utf-8"))
        cls.db.execute("""
            insert into public.tenants(tenant_id,brand_name,owner_name) values(971,'Checkout Store','Owner'),(972,'Customer Home','Customer');
            insert into auth.users(id,email_confirmed_at) values('00000000-0000-0000-0000-000000000971',now()),('00000000-0000-0000-0000-000000000972',now());
            insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) values
            ('00000000-0000-0000-0000-000000000971','Owner','One','owner-971@example.invalid',971,'active',true,now()),
            ('00000000-0000-0000-0000-000000000972','Customer','One','customer-972@example.invalid',972,'active',true,now());
            insert into public.website_settings(user_id,tenant_id,subdomain,ecommerce_currency)
                select id,tenant_id,case tenant_id when 971 then 'checkout-store' else 'customer-home' end,'ILS' from public.users where tenant_id in(971,972);
            insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled) values(971,'95000000-0000-0000-0000-000000000001',true);
            insert into public.ecommerce_products(id,tenant_id,sku,slug,translations,status,price,currency,inventory_quantity) values
            ('97100000-0000-0000-0000-000000000001',971,'CHECKOUT-971','checkout-971','{"en":{"name":"Checkout"}}','active',100,'ILS',20);
        """)
        cls.customer_id = cls.db.execute("select id from public.users where tenant_id=972").fetchone()[0]
        cls.actor_id = cls.db.execute("select id from public.users where tenant_id=971").fetchone()[0]
        cls.db.execute("select public.save_ecommerce_loyalty_rule_safe(971,%s,true,500,100,'97100000-0000-0000-0000-000000000001','lifetime',null)", (cls.actor_id,))

    def test_http_checkout_inventory_and_loyalty_are_exactly_once(self):
        from psycopg.types.json import Jsonb
        db = self.db

        class DatabaseRpc:
            def rpc(self, name, params):
                if name != "create_ecommerce_order_safe":
                    raise AssertionError(name)
                def execute():
                    result = db.execute("select public.create_ecommerce_order_safe(%s,%s,%s,%s,%s)", (
                        Jsonb(params["p_order"]), params["p_idempotency_key_hash"], params["p_request_hash"],
                        params["p_confirmation_token_hash"], params["p_customer_id"],
                    )).fetchone()[0]
                    return SimpleNamespace(data=result)
                return SimpleNamespace(execute=execute)

            def table(self, name):
                raise AssertionError("checkout must use the atomic RPC")

        app = FastAPI()
        app.include_router(routes.router)
        client = TestClient(app, raise_server_exceptions=False)
        profile = {"id": self.customer_id, "auth_id": "00000000-0000-0000-0000-000000000972"}
        payload = order_payload(items=[{"product_id": "97100000-0000-0000-0000-000000000001", "quantity": 2}])
        with (
            patch.object(routes, "service_supabase", DatabaseRpc()),
            patch.object(routes, "get_authenticated_user_row", return_value=(SimpleNamespace(id=profile["auth_id"]), profile)),
            patch.object(routes, "enforce_public_rate_limit"),
            patch.object(routes, "resolve_public_store_settings", return_value={"tenant_id": 971}),
            patch.object(routes, "resolve_tenant_id", return_value=971),
        ):
            headers = {"cookie": "madar_access_token=verified"}
            first = client.post("/public/sites/checkout-store/orders", json=payload, headers=headers)
            self.assertEqual(first.status_code, 201, first.text)
            order = first.json()["order"]
            oid = order["id"]
            self.assertEqual(order["payment_method"], "cash_on_delivery")
            self.assertEqual(db.execute("select customer_id from public.ecommerce_orders where id=%s", (oid,)).fetchone()[0], self.customer_id)
            self.assertEqual(db.execute("select inventory_quantity from public.ecommerce_products where sku='CHECKOUT-971'").fetchone()[0], 18)
            self.assertEqual(db.execute("select count(*) from public.ecommerce_loyalty_transactions where order_id=%s", (oid,)).fetchone()[0], 0)
            db.execute("select public.collect_ecommerce_cod_payment_safe(971,%s,%s)", (oid, self.actor_id))
            for index, status in enumerate(("confirmed", "preparing", "out_for_delivery", "delivered")):
                db.execute("select public.transition_ecommerce_order_status_safe(971,%s,%s,%s,'',%s)", (oid, status, self.actor_id, str(index) * 64))
            self.assertEqual(db.execute("select points_delta from public.ecommerce_loyalty_transactions where order_id=%s and transaction_type='earn'", (oid,)).fetchone()[0], 10)
            replay = client.post("/public/sites/checkout-store/orders", json=payload, headers=headers)
            self.assertEqual(replay.status_code, 201, replay.text)
            self.assertTrue(replay.json()["idempotent_replay"])
            self.assertEqual(replay.json()["order"]["id"], oid)
            db.execute("select public.collect_ecommerce_cod_payment_safe(971,%s,%s)", (oid, self.actor_id))
            db.execute("select public.transition_ecommerce_order_status_safe(971,%s,'delivered',%s,'',%s)", (oid, self.actor_id, '3' * 64))
            self.assertEqual(db.execute("select inventory_quantity from public.ecommerce_products where sku='CHECKOUT-971'").fetchone()[0], 18)
            self.assertEqual(db.execute("select count(*) from public.ecommerce_loyalty_transactions where order_id=%s and transaction_type='earn'", (oid,)).fetchone()[0], 1)
            self.assertEqual(db.execute("select current_balance from public.ecommerce_loyalty_accounts where tenant_id=971 and customer_id=%s", (self.customer_id,)).fetchone()[0], 10)
            self.assertEqual(db.execute("select count(*) from public.ecommerce_inventory_movements where order_id=%s", (oid,)).fetchone()[0], 1)
            guest_payload = dict(payload, idempotency_key="guest-checkout-1234567890")
            guest = client.post("/public/sites/checkout-store/orders", json=guest_payload)
            self.assertEqual(guest.status_code, 201, guest.text)
            guest_id = guest.json()["order"]["id"]
            self.assertIsNone(db.execute("select customer_id from public.ecommerce_orders where id=%s", (guest_id,)).fetchone()[0])

            db.execute("select public.collect_ecommerce_cod_payment_safe(971,%s,%s)", (guest_id, self.actor_id))
            for index, status in enumerate(("confirmed", "preparing", "out_for_delivery", "delivered")):
                db.execute("select public.transition_ecommerce_order_status_safe(971,%s,%s,%s,'',%s)", (guest_id, status, self.actor_id, str(index + 4) * 64))
            self.assertEqual(db.execute("select count(*) from public.ecommerce_loyalty_transactions where order_id=%s", (guest_id,)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
