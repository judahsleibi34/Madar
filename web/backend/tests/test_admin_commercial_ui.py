"""Read-only administrative proposal boundary; SQL pricing owns the amounts."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from fastapi import HTTPException, Response
from starlette.requests import Request
from routes.admin_billing_routes import quote_commercial_modules, CommercialModuleQuoteRequest

class CommercialQuoteAPITests(unittest.TestCase):
    def setUp(self):
        self.request = Request({"type": "http", "headers": []})
        self.payload = CommercialModuleQuoteRequest(module_ids=["website"], billing_months=3)

    def test_read_only_rpc_and_server_amount(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = {"revision": 17, "module_basis": {"website": {"price_book_id": "launch_2026"}}, "pricing": {"module_ids": ["website"], "recurring_minor": 2000, "price_groups": [{"grandfathered": True}]}}
        with patch("routes.admin_billing_routes._admin") as admin, patch("routes.admin_billing_routes.resolve_commercial_access", return_value={"contract_version": 115}), patch("routes.admin_billing_routes.service_supabase", db):
            result = quote_commercial_modules(42, self.payload, self.request, Response())
        admin.assert_called_once()
        db.table.assert_not_called()
        db.rpc.assert_called_once_with("quote_commercial_modules", {"p_tenant_id": 42, "r": {"module_ids": ["website"], "price_books": {}}})
        self.assertEqual(result["quote"]["expected_payment_minor"], 6000)

    def test_admin_guard_denial_prevents_lookup(self):
        for status in (401,403):
            with self.subTest(status=status), patch("routes.admin_billing_routes._admin", side_effect=HTTPException(status_code=status)), patch("routes.admin_billing_routes.resolve_commercial_access") as lookup:
                with self.assertRaises(HTTPException) as error:
                    quote_commercial_modules(42,self.payload,self.request,Response())
                self.assertEqual(error.exception.status_code,status)
                lookup.assert_not_called()

    def test_schema_bridge_no_quote(self):
        with patch("routes.admin_billing_routes._admin"), patch("routes.admin_billing_routes.resolve_commercial_access", return_value={"contract_version":114}):
            with self.assertRaises(HTTPException) as error:
                quote_commercial_modules(42,self.payload,self.request,Response())
        self.assertEqual(error.exception.status_code,503)

    def test_unavailable_price_safe_conflict(self):
        db=MagicMock(); err=Exception("private SQL"); err.code="22023"
        db.rpc.return_value.execute.side_effect=err
        with patch("routes.admin_billing_routes._admin"), patch("routes.admin_billing_routes.resolve_commercial_access",return_value={"contract_version":115}), patch("routes.admin_billing_routes.service_supabase",db):
            with self.assertRaises(HTTPException) as result:
                quote_commercial_modules(42,self.payload,self.request,Response())
        self.assertEqual(result.exception.status_code,409)
        self.assertNotIn("private",str(result.exception.detail))

    def test_payload_cannot_supply_identity_or_price(self):
        for key in ("actor_user_id","aal","role","recurring_minor"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                CommercialModuleQuoteRequest(module_ids=["website"],**{key:"fake"})

    def test_malformed_quote_fails_closed(self):
        db=MagicMock(); db.rpc.return_value.execute.return_value.data={"pricing":{"recurring_minor":2000}}
        with patch("routes.admin_billing_routes._admin"), patch("routes.admin_billing_routes.resolve_commercial_access",return_value={"contract_version":115}), patch("routes.admin_billing_routes.service_supabase",db):
            with self.assertRaises(HTTPException) as result:
                quote_commercial_modules(42,self.payload,self.request,Response())
        self.assertEqual(result.exception.status_code,503)
