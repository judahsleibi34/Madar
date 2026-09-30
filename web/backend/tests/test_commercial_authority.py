import copy
import unittest
from datetime import datetime, timezone, timedelta
from os import environ
from types import SimpleNamespace
from unittest.mock import patch, Mock

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient
from routes import admin_billing_routes, public_site_routes, ecommerce_routes, billing_routes, website_routes
from services import entitlement_service as ent, commercial_access_service as access, auth_service, tenant_service
from services.commercial_billing_service import assign_plan
from services.commercial_catalog import GIB
from tests.test_admin_mfa_aal2_enforcement import ADMIN_USER, REGULAR_USER, _FakeServiceSupabase


def snapshot(tenant=7, **changes):
    now = datetime.now(timezone.utc)
    state = {"contract_version": 115, "tenant_id": tenant, "revision": 17, "review_state": "reviewed",
             "commercial_suspended_at": None, "effective_at": now.isoformat(), "has_history": True, "access_state": "active",
             "next_transition_at": (now + timedelta(days=1)).isoformat(),
             "period": {"tenant_id": tenant, "plan_id": "business_plus", "valid_from": (now-timedelta(days=1)).isoformat(),
                        "valid_until": (now+timedelta(days=1)).isoformat()},
             "subscriptions": [{"tenant_id": tenant, "plan_id": "business_plus", "state": "active"}], "addons": []}
    state.update(changes)
    return state


class CommercialAuthorityTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(environ, {"COMMERCIAL_ENTITLEMENTS_ENFORCED": "true", "COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"})
        env.start(); self.addCleanup(env.stop)
        self.state = snapshot()
        lookup = patch.object(ent, "resolve_commercial_access", side_effect=lambda tenant: copy.deepcopy(self.state))
        lookup.start(); self.addCleanup(lookup.stop)

    def test_assigned_plan_and_valid_ledger_grant_capabilities(self):
        result = ent.get_tenant_entitlements(7)
        self.assertIn("reservations", result["capabilities"])
        self.assertEqual(result["commercial_revision"], 17)
        self.assertEqual(result["next_transition_at"], self.state["next_transition_at"])

    def test_active_subscription_without_period_cannot_grant(self):
        self.state["period"] = None
        self.assertEqual(ent.get_tenant_entitlements(7)["commercial_denial_code"], "commercial_access_required")
        self.state["access_state"] = "expired"
        self.assertEqual(ent.get_tenant_entitlements(7)["commercial_denial_code"], "commercial_access_expired")
        with self.assertRaises(HTTPException): ent.require_entitlement(7, "website_publish")

    def test_unknown_plan_mismatch_and_malformed_period_fail_closed(self):
        for bad in ("forged", "website"):
            self.state["subscriptions"][0]["plan_id"] = bad
            self.assertEqual(ent.get_tenant_entitlements(7)["capabilities"], [])
        self.state = snapshot(); self.state["period"]["valid_until"] = "not-a-date"
        self.assertEqual(ent.get_tenant_entitlements(7)["commercial_denial_code"], "commercial_state_invalid")

    def test_malformed_assignment_state_cannot_mask_hold_or_grant_access(self):
        for value in ({}, [], False):
            self.state["subscriptions"][0]["state"]=value
            self.assertEqual(ent.get_tenant_entitlements(7)["capabilities"],[])
            self.state["commercial_suspended_at"]=self.state["effective_at"]
            with patch.dict(environ,{"COMMERCIAL_ENTITLEMENTS_ENFORCED":"false"}):
                self.assertEqual(ent.get_tenant_entitlements(7)["commercial_denial_code"],"commercial_access_suspended")
            self.state["commercial_suspended_at"]=None

    def test_review_required_is_preserved(self):
        self.state["review_state"] = "review_required"
        self.assertEqual(ent.get_tenant_entitlements(7)["commercial_denial_code"], "commercial_review_required")

    def test_subscription_and_addon_bounds_restrict_access(self):
        self.state["subscriptions"][0]["period_end"] = "2020-01-01T00:00:00Z"
        self.assertEqual(ent.get_tenant_entitlements(7)["capabilities"], [])
        self.state = snapshot()
        self.state["addons"] = [{"addon_id": "additional_storage_5gb", "quantity": 2, "state": "active", "period_end": "2020-01-01T00:00:00Z"}]
        quota = ent.get_tenant_entitlements(7)["allowances"]["storage_bytes"]
        self.state["addons"][0]["period_end"] = self.state["period"]["valid_until"]
        self.assertEqual(ent.get_tenant_entitlements(7)["allowances"]["storage_bytes"], quota+10*GIB)

    def test_hold_wins_over_bypass_and_legacy_fields(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENTS_ENFORCED": "false"}), patch.object(ent, "_legacy_features", return_value=[{"payment_status":"active","plan":"complete"}]):
            with self.assertRaises(HTTPException) as error: ent.require_entitlement(7, "forms")
        self.assertEqual(error.exception.status_code, 402)
        self.assertEqual(error.exception.detail["code"], "commercial_access_suspended")

    def test_unsuspended_unresolved_bypass_is_preserved(self):
        self.state = snapshot(review_state="review_required", period=None, subscriptions=[])
        with patch.dict(environ, {"COMMERCIAL_ENTITLEMENTS_ENFORCED": "false"}):
            result = ent.require_entitlement(7, "reservations")
        self.assertEqual(result["source"], "operator_configuration_override")

    def test_no_cache_survives_suspend_reactivate_or_expiry(self):
        self.assertIn("forms", ent.get_tenant_entitlements(7)["capabilities"])
        self.state.update(commercial_suspended_at=self.state["effective_at"], revision=18)
        self.assertEqual(ent.get_tenant_entitlements(7)["capabilities"], [])
        self.state.update(commercial_suspended_at=None, revision=19)
        self.assertIn("forms", ent.get_tenant_entitlements(7)["capabilities"])
        self.state["period"] = None
        self.assertEqual(ent.get_tenant_entitlements(7)["capabilities"], [])

    def test_public_surfaces_redact_state_and_fail_closed(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        for capability in ("website_publish", "public_form_links", "reservations"):
            with self.assertRaises(HTTPException) as error:
                ent.require_public_runtime_entitlement({"tenant_id":7,"published_project_id":"project"}, capability)
            self.assertEqual(error.exception.status_code, 503)
            self.assertEqual(error.exception.detail, {"code":"tenant_service_unavailable","message":"This service is temporarily unavailable."})

    def test_public_website_and_form_routes_stop_before_content_on_hold(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        settings={"tenant_id":7,"published_project_id":"project"}
        request=Request({"type":"http","method":"GET","path":"/public/sites/shop/runtime","headers":[]})
        with patch.object(public_site_routes,"enforce_public_rate_limit"), patch.object(public_site_routes,"resolve_public_site_runtime_context",return_value=(settings,{})), patch.object(public_site_routes,"get_optional_tenant_visitor") as visitor:
            with self.assertRaises(HTTPException): public_site_routes.get_public_site_runtime("shop",request,Response())
            visitor.assert_not_called()
        with patch.object(public_site_routes,"enforce_public_rate_limit"), patch.object(public_site_routes,"resolve_website_settings",return_value=settings), patch.object(public_site_routes,"get_published_form_for_site") as content:
            with self.assertRaises(HTTPException): public_site_routes.get_public_form("shop","form",request,Response())
            content.assert_not_called()

    def test_reservation_route_stops_before_business_mutation_on_hold(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        settings={"tenant_id":7,"published_project_id":"project"}
        request=Request({"type":"http","method":"POST","path":"/public/sites/shop/events","headers":[]})
        event=public_site_routes.PublicBuilderBlockEventCreate(block_type="reservationBlock",block_id="reservation")
        with patch.object(public_site_routes,"enforce_public_form_submission_rate_limit"), patch.object(public_site_routes,"reject_suspicious_public_submission"), patch.object(public_site_routes,"resolve_website_settings",return_value=settings), patch.object(public_site_routes,"get_bound_published_project",return_value={"status":"published","published_schema":{}}), patch.object(public_site_routes,"find_published_block",return_value={"id":"reservation"}), patch.object(public_site_routes,"authorize_site_resource") as mutate:
            with self.assertRaises(HTTPException): public_site_routes.submit_public_builder_block_event("shop",event,request,Response())
            mutate.assert_not_called()

    def test_storefront_checkout_stops_before_order_rpc_on_hold(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        request=Request({"type":"http","method":"POST","path":"/public/sites/shop/orders","headers":[]})
        payload=public_site_routes.PublicStoreOrderCreate(idempotency_key="synthetic-order-test",customer_name="Synthetic",email="synthetic@example.com",phone="0590000000",service_area_id="95000000-0000-0000-0000-000000000001",street="Synthetic street",items=[{"product_id":"97100000-0000-0000-0000-000000000001","quantity":1}])
        with patch.object(public_site_routes,"enforce_public_rate_limit"), patch.object(public_site_routes,"enforce_request_tenant_identity",return_value="shop"), patch.object(public_site_routes,"request_hosted_tenant",return_value="shop"), patch.object(public_site_routes,"read_ecommerce_cache",return_value={"tenant_id":7}), patch.object(public_site_routes.service_supabase,"rpc") as orders:
            with self.assertRaises(HTTPException): public_site_routes.create_public_store_order("shop",payload,request,Response())
            orders.assert_not_called()

    def test_platform_commercial_inspection_remains_usable_on_hold(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        app=FastAPI(); app.include_router(admin_billing_routes.router)
        query=Mock()
        for method in ("select","eq","is_","limit","order","gte","lt","gt"):
            getattr(query,method).return_value=query
        query.execute.return_value=SimpleNamespace(data=[])
        with patch.object(auth_service,"get_authenticated_user_row",return_value=(SimpleNamespace(id="auth-admin"),ADMIN_USER)), patch.object(auth_service,"get_current_aal",return_value={"current_level":"aal2"}), patch.object(admin_billing_routes.service_supabase,"table",return_value=query):
            response=TestClient(app).get("/admin/billing/tenants/7/commercial-state")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["entitlements"]["commercial_denial_code"],"commercial_access_suspended")
        self.assertEqual(response.json()["storage"]["quota_bytes"],0)

    def test_public_dependency_failure_cannot_hide_hold(self):
        with patch.object(ent, "resolve_commercial_access", side_effect=HTTPException(503, {"code":"commercial_dependency_unavailable"})):
            with self.assertRaises(HTTPException): ent.require_public_runtime_entitlement({"tenant_id":7,"published_project_id":"project"}, "website_publish")

    def test_cached_store_identity_still_reauthorizes(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        request = Request({"type":"http", "method":"GET", "path":"/sites/shop/catalog", "headers":[]})
        with patch.object(public_site_routes, "enforce_request_tenant_identity", return_value="shop"), patch.object(public_site_routes, "request_hosted_tenant", return_value="shop"), patch.object(public_site_routes, "read_ecommerce_cache", return_value={"tenant_id":7}):
            with self.assertRaises(HTTPException): public_site_routes.resolve_public_store_settings("shop", request=request)

    def test_historical_merchant_actions_remain_available_new_activity_denied(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        context = SimpleNamespace(tenant_id=7, role="owner")
        with patch.object(ecommerce_routes, "require_active_tenant_member", return_value=context):
            for path in ("/ecommerce/orders/abc/status", "/ecommerce/orders/abc/collect-payment"):
                request = Request({"type":"http","method":"POST","path":path,"headers":[]})
                self.assertIs(ecommerce_routes._require_ecommerce_access(request, Response(), historical_operation=True), context)
            with self.assertRaises(HTTPException): ecommerce_routes._require_ecommerce_access(Request({"type":"http","method":"POST","path":"/ecommerce/products","headers":[]}), Response())

    def test_plan_assignment_only_calls_assignment_rpc(self):
        client = Mock(); client.rpc.return_value.execute.return_value.data = [{"id":1}]
        with patch("services.commercial_billing_service.service_supabase", client):
            assign_plan(tenant_id=7, plan_id="business", state="active", admin_user_id=99, reason="Product assignment", idempotency_key="assignment-test-key")
        self.assertEqual(client.rpc.call_args.args[0], "assign_commercial_subscription")
        client.table.assert_not_called()

    def test_website_settings_write_denied_on_hold_but_read_available(self):
        self.state["commercial_suspended_at"] = self.state["effective_at"]
        context=SimpleNamespace(tenant_id=7,user_id=5)
        with patch.object(website_routes,"require_active_tenant_member",return_value=context):
            for method in ("POST","PUT","PATCH"):
                with self.assertRaises(HTTPException):
                    website_routes.get_website_tenant_context(Request({"type":"http","method":method,"path":"/website","headers":[]}),Response())
            self.assertIs(website_routes.get_website_tenant_context(Request({"type":"http","method":"GET","path":"/website","headers":[]}),Response()),context)

    def test_same_user_tenant_switch_recomputes_and_does_not_change_auth(self):
        contexts = {7: snapshot(7, commercial_suspended_at=self.state["effective_at"]), 8: snapshot(8)}
        app = FastAPI(); app.include_router(billing_routes.router)
        user = {"id":5,"auth_id":"same-user","payment_status":"active","plan":"complete"}
        selected = {"tenant":7}
        with patch.object(billing_routes, "_commercial_context", side_effect=lambda *_: SimpleNamespace(tenant_id=selected["tenant"], user=user)), patch.object(ent, "resolve_commercial_access", side_effect=lambda t: contexts[t]):
            client = TestClient(app)
            a = client.get("/billing/entitlements"); selected["tenant"] = 8
            b = client.get("/billing/entitlements"); selected["tenant"] = 7
            again = client.get("/billing/entitlements")
        self.assertEqual(a.status_code, 200); self.assertEqual(a.json()["entitlements"]["capabilities"], [])
        self.assertIn("forms", b.json()["entitlements"]["capabilities"])
        self.assertEqual(again.json()["entitlements"]["commercial_denial_code"], "commercial_access_suspended")
        self.assertEqual(user, {"id":5,"auth_id":"same-user","payment_status":"active","plan":"complete"})


class CommercialCommandSecurityTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(admin_billing_routes.router)
        self.client = TestClient(app)
        self.payload = {"expected_revision":17,"reason":"Payment review","idempotency_key":"commercial-test-request"}

    def test_unauthenticated_denied(self):
        result = self.client.post("/admin/billing/tenants/7/suspend", json=self.payload)
        self.assertEqual(result.status_code, 401)

    def call_as(self, user, aal, action="suspend", payload=None):
        with patch.object(auth_service, "get_authenticated_user_row", return_value=(SimpleNamespace(id=user["auth_id"]), user)), patch.object(auth_service, "get_current_aal", return_value={"current_level":aal}), patch.object(admin_billing_routes, "apply_commercial_command", return_value={"revision":18,"operation":action}) as command:
            response = self.client.post(f"/admin/billing/tenants/7/{action}", json=payload or self.payload)
        return response, command

    def test_ordinary_user_and_tenant_admin_aal2_denied(self):
        for role in ("member", "owner", "admin"):
            user = {**REGULAR_USER, "tenant_role":role}
            response, command = self.call_as(user, "aal2")
            self.assertEqual(response.status_code, 403); command.assert_not_called()

    def test_platform_aal1_step_up_and_aal2_permitted(self):
        response, command = self.call_as(ADMIN_USER, "aal1")
        self.assertEqual(response.json()["detail"]["code"], "aal2_required"); command.assert_not_called()
        for action in ("suspend", "reactivate"):
            response, command = self.call_as(ADMIN_USER, "aal2", action)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(command.call_args.kwargs["actor_user_id"],99)
            self.assertEqual(command.call_args.kwargs["command"]["expected_revision"],17)
            self.assertTrue(response.headers["X-Request-ID"])

    def test_reason_and_expected_revision_required(self):
        for change in ({"reason":"   "}, {"expected_revision":0}, {"expected_revision":"17"}):
            response, command = self.call_as(ADMIN_USER, "aal2", payload={**self.payload, **change})
            self.assertEqual(response.status_code,422); command.assert_not_called()

    def test_stale_conflict_error_contract(self):
        from postgrest.exceptions import APIError
        rpc = Mock(); rpc.rpc.return_value.execute.side_effect=APIError({"message":"commercial_revision_conflict","code":"40001","details":None,"hint":None})
        with patch.object(access, "resolve_commercial_access", return_value=snapshot()), patch.object(access, "service_supabase", rpc):
            with self.assertRaises(HTTPException) as error:
                access.apply_commercial_command(tenant_id=7,actor_user_id=99,operation="suspend",idempotency_key="commercial-test-request",request_id="request-test",command=self.payload)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(error.exception.detail["code"],"commercial_revision_conflict")

    def test_missing_command_result_is_not_reported_as_success(self):
        db=Mock(); db.rpc.return_value.execute.return_value.data=None
        with patch.object(access,"resolve_commercial_access",return_value=snapshot()), patch.object(access,"service_supabase",db):
            with self.assertRaises(HTTPException) as error:
                access.apply_commercial_command(tenant_id=7,actor_user_id=99,operation="suspend",idempotency_key="commercial-test-request",request_id="request-test",command=self.payload)
        self.assertEqual(error.exception.detail["code"],"commercial_command_unavailable")

    def test_bridge_refuses_mutation_before_hold_schema_exists(self):
        with patch.object(access, "resolve_commercial_access", return_value={"revision":17}), patch.object(access, "service_supabase") as db:
            with self.assertRaises(HTTPException) as error:
                access.apply_commercial_command(tenant_id=7,actor_user_id=99,operation="suspend",idempotency_key="commercial-test-request",request_id="request-test",command=self.payload)
        self.assertEqual(error.exception.detail["code"], "commercial_upgrade_required"); db.rpc.assert_not_called()

    def test_malformed_or_missing_snapshot_fails_closed_even_bypass(self):
        for state in (None, {}, {**snapshot(),"revision":True}, {**snapshot(),"contract_version":116},
                      {k:v for k,v in snapshot().items() if k!="commercial_suspended_at"},
                      {k:v for k,v in snapshot().items() if k!="subscriptions"}):
            db = Mock(); db.rpc.return_value.execute.return_value.data=state
            with patch.object(access, "service_supabase", db), patch.dict(environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS":"true","COMMERCIAL_ENTITLEMENTS_ENFORCED":"false"}):
                with self.assertRaises(HTTPException): access.resolve_commercial_access(7)
