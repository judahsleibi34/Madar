"""Regressions for the (provider user, local profile) auth contract."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import public_site_routes as routes
from tests.test_ecommerce_transaction_core import RpcOnlyClient, order_payload


class AuthenticatedCheckoutTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.rpc = RpcOnlyClient()
        self.profile = {
            "id": 42,
            "auth_id": "provider-uuid",
            "tenant_id": 8,
            "email": "verified@example.com",
            "email_verified": True,
        }
        self.auth = MagicMock(
            return_value=(SimpleNamespace(id="provider-uuid"), self.profile)
        )
        for name, value in (
            ("service_supabase", self.rpc),
            ("get_authenticated_user_row", self.auth),
            ("enforce_public_rate_limit", MagicMock()),
            (
                "resolve_public_store_settings",
                MagicMock(return_value={"tenant_id": 7}),
            ),
            ("resolve_tenant_id", MagicMock(return_value=7)),
        ):
            patcher = patch.object(routes, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def checkout(self, cookie=None):
        headers = {"cookie": cookie} if cookie else {}
        return self.client.post(
            "/public/sites/test-store/orders",
            json=order_payload(),
            headers=headers,
        )

    def test_authenticated_checkout_uses_local_profile_identity(self):
        for cookie in (
            "madar_access_token=access",
            "madar_refresh_token=refresh",
        ):
            with self.subTest(cookie=cookie):
                response = self.checkout(cookie)
                self.assertEqual(response.status_code, 201, response.text)
                self.assertEqual(self.rpc.params["p_customer_id"], 42)
                self.assertEqual(
                    self.rpc.params["p_order"]["verified_customer_id"], 42
                )
                self.assertEqual(self.rpc.params["p_order"]["tenant_id"], 7)
                self.assertEqual(
                    self.auth.call_args.kwargs,
                    {
                        "allow_admin_account_access": False,
                        "reject_admin_account_access": True,
                    },
                )

    def test_guest_checkout_does_not_infer_identity_from_contact(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 201, response.text)
        self.auth.assert_not_called()
        self.assertIsNone(self.rpc.params["p_customer_id"])
        self.assertIsNone(
            self.rpc.params["p_order"]["verified_customer_id"]
        )

    def test_rejected_session_keeps_guest_checkout_behavior(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.auth.side_effect = HTTPException(
                    status_code=status, detail="Rejected session"
                )
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
            response = self.client.get(
                "/public/sites/test-store/loyalty/me",
                headers={"cookie": "madar_access_token=access"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        database.rpc.assert_called_once_with(
            "expire_ecommerce_loyalty_entitlements_safe",
            {"p_tenant_id": 7, "p_customer_id": 42},
        )
        self.assertEqual(query.eq.call_args_list.count(call("customer_id", 42)), 3)
        self.assertEqual(query.eq.call_args_list.count(call("tenant_id", 7)), 3)

    def test_guest_loyalty_read_requires_authentication(self):
        self.auth.side_effect = HTTPException(
            status_code=401, detail="Not logged in"
        )
        response = self.client.get("/public/sites/test-store/loyalty/me")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
