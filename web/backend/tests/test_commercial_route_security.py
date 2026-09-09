import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import admin_commercial_routes, ecommerce_routes, builder_routes, public_site_routes
from services import entitlement_service
from tests.entitlement_test_support import EntitlementTestState


class CommercialRouteSecurityTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(admin_commercial_routes.router)
        self.client=TestClient(app)

    def payload(self, suffix):
        body={'idempotency_key':'command-fixture-123456','reason':'Synthetic proof'}
        if suffix in {'manual-payments','complimentary-grants'}:
            body.update(plan_id='business',valid_from='2026-09-01T00:00:00Z',valid_until='2026-10-01T00:00:00Z')
        if suffix=='manual-payments':body.update(method='cash',actual_minor=2500,currency='USD',paid_at='2026-09-01T00:00:00Z',receipt_reference='SYNTHETIC')
        if suffix=='payment-corrections':body.update(payment_id='00000000-0000-0000-0000-000000000001',actual_minor=2500,paid_at='2026-09-01T00:00:00Z',receipt_reference='SYNTHETIC')
        if suffix=='revocations':body.update(period_id='00000000-0000-0000-0000-000000000001')
        return body

    def test_every_admin_route_rejects_unprivileged_identity_before_database(self):
        for status in [401,403]:
            with patch.object(admin_commercial_routes,'require_system_admin',side_effect=HTTPException(status_code=status,detail='denied')) as auth,patch.object(admin_commercial_routes,'service_supabase') as db,patch.object(admin_commercial_routes,'execute_commercial_command') as command:
                for route in admin_commercial_routes.router.routes:
                    path=route.path.replace('{tenant_id}','7')
                    with self.subTest(path=path,status=status):
                        result=self.client.get(path) if 'GET' in route.methods else self.client.post(path,json=self.payload(path.rsplit('/',1)[-1]))
                        self.assertEqual(result.status_code,status)
                self.assertTrue(all(call.kwargs.get('require_aal2') is True for call in auth.call_args_list))
                db.table.assert_not_called();command.assert_not_called()

    def test_mass_assignment_rejected_even_for_admin(self):
        for field in ['expected_minor','created_by','aal','revision','tenant_id','source_type']:
            body=self.payload('manual-payments');body[field]=1
            with patch.object(admin_commercial_routes,'execute_commercial_command') as command:
                result=self.client.post('/admin/commercial/tenants/7/manual-payments',json=body)
            self.assertEqual(result.status_code,422);command.assert_not_called()

    def test_catalog_cached_business_snapshot_does_not_survive_downgrade(self):
        context=SimpleNamespace(tenant_id=7,user_id=3,role='owner')
        state=EntitlementTestState().activate_plan(7,'business_plus')
        app=FastAPI();app.include_router(ecommerce_routes.router);client=TestClient(app)
        with state.installed(),patch.object(ecommerce_routes,'require_active_tenant_member',return_value=context),patch.object(ecommerce_routes,'get_or_create_ecommerce_cache',return_value=({'products':['cached']},True)) as cache:
            self.assertEqual(client.get('/ecommerce/catalog').status_code,200)
            self.assertEqual(cache.call_count,1)
            state.activate_plan(7,'forms')
            result=client.get('/ecommerce/catalog')
            self.assertEqual(result.status_code,403)
            self.assertEqual(result.json()['detail']['code'],'entitlement_required')
            self.assertEqual(cache.call_count,1)

    def test_protected_module_routes_cannot_omit_commercial_boundary(self):
        for route in ecommerce_routes.router.routes:
            self.assertIn('_require_ecommerce_access',route.endpoint.__code__.co_names,route.path)
        for route in builder_routes.router.routes:
            if '/builder/' in route.path:
                def reaches_gate(function, seen=None):
                    seen=set(seen or ())
                    if function in seen: return False
                    seen.add(function)
                    names=function.__code__.co_names
                    if {'require_builder_context','require_builder_context_without_admin_account_access'} & set(names): return True
                    return any(reaches_gate(target,seen) for name in names if inspect.isfunction(target:=getattr(builder_routes,name,None)) and target.__module__==builder_routes.__name__)
                self.assertTrue(reaches_gate(route.endpoint),route.path)
        for route in public_site_routes.router.routes:
            if route.path.endswith('/catalog') or '/catalog/products/' in route.path or route.path.endswith('/orders') or route.path.endswith('/store-profile'):
                self.assertIn('resolve_public_store_settings',route.endpoint.__code__.co_names,route.path)
        # The helpers themselves must resolve a commercial decision, including
        # public binding lookup before any catalog cache can return a result.
        self.assertIn('require_entitlement',ecommerce_routes._require_ecommerce_access.__code__.co_names)
        self.assertIn('require_entitlement',public_site_routes.resolve_public_store_settings.__code__.co_names)
        self.assertIn('require_any_entitlement',builder_routes.require_builder_context.__code__.co_names)
        self.assertNotIn('read_ecommerce_cache',public_site_routes.resolve_public_store_settings.__code__.co_names)

    def test_every_commercial_mutation_keeps_csrf_and_origin_protection(self):
        from starlette.requests import Request
        from services.request_security import validate_csrf_token, validate_cookie_write_origin, create_csrf_token
        from unittest.mock import patch
        from os import environ
        with patch.dict(environ, {'CSRF_SECRET':'synthetic-csrf-secret-not-production'}):
            token=create_csrf_token(access_token='synthetic-access')
            for route in admin_commercial_routes.router.routes:
                if 'POST' not in route.methods: continue
                path=route.path.replace('{tenant_id}','7')
                def request(origin,csrf):
                    headers=[(b'cookie',f'madar_access_token=synthetic-access; madar_csrf_token={token}'.encode()),(b'origin',origin.encode())]
                    if csrf:headers.append((b'x-csrf-token',csrf.encode()))
                    return Request({'type':'http','method':'POST','path':path,'headers':headers})
                with self.subTest(path=path):
                    self.assertEqual(validate_csrf_token(request('https://app.example.invalid','')).status_code,403)
                    self.assertEqual(validate_csrf_token(request('https://app.example.invalid','wrong')).status_code,403)
                    self.assertEqual(validate_cookie_write_origin(request('https://evil.example.invalid',token),{'https://app.example.invalid'}).status_code,403)
                    self.assertIsNone(validate_csrf_token(request('https://app.example.invalid',token)))
                    self.assertIsNone(validate_cookie_write_origin(request('https://app.example.invalid',token),{'https://app.example.invalid'}))

    def test_backend_plan_role_intersection(self):
        for plan in ['forms','website','business','business_plus']:
            for role in ['owner','admin','member','unknown']:
                with self.subTest(plan=plan,role=role):
                    state=EntitlementTestState().activate_plan(7,plan)
                    context=SimpleNamespace(tenant_id=7,user_id=3,role=role)
                    from starlette.requests import Request
                    from starlette.responses import Response
                    request=Request({'type':'http','headers':[]})
                    with state.installed(),patch.object(ecommerce_routes,'require_active_tenant_member',return_value=context):
                        if plan in {'business','business_plus'} and role!='unknown':
                            self.assertEqual(ecommerce_routes._require_ecommerce_access(request,Response()),context)
                        else:
                            with self.assertRaises(HTTPException) as caught:ecommerce_routes._require_ecommerce_access(request,Response())
                            self.assertEqual(caught.exception.status_code,403)


class BuilderDocumentCapabilityTests(unittest.TestCase):
    def test_forms_cannot_create_or_edit_website_documents(self):
        state = EntitlementTestState().activate_plan(7, "forms")
        with state.installed():
            for field, value in [("pages", [{"id": "page", "sections": []}]), ("roles", [{"id": "role"}]), ("users", [{"id": "member"}])]:
                with self.subTest(field=field), self.assertRaises(HTTPException) as caught:
                    builder_routes.require_builder_schema_capabilities(7, {field: value})
                self.assertEqual(caught.exception.status_code, 403)
            previous = {"pages": [{"id": "historical"}], "forms": []}
            builder_routes.require_builder_schema_capabilities(7, {**previous, "forms": [{"id": "new-form"}]}, previous)
            with self.assertRaises(HTTPException):
                builder_routes.require_builder_schema_capabilities(7, {**previous, "pages": []}, previous)

    def test_reservation_inside_form_requires_reservation_capability(self):
        document = {"forms": [{"id": "form", "elements": [{"type": "reservationBlock"}]}]}
        for plan in ["forms", "website", "business", "business_plus"]:
            with self.subTest(plan=plan), EntitlementTestState().activate_plan(7, plan).installed():
                if plan == "forms":
                    with self.assertRaises(HTTPException):
                        builder_routes.require_builder_schema_capabilities(7, document)
                else:
                    builder_routes.require_builder_schema_capabilities(7, document)

    def test_forms_cannot_call_website_member_administration(self):
        app = FastAPI(); app.include_router(builder_routes.router)
        context = SimpleNamespace(tenant_id=7, user_id=3, role="owner")
        with EntitlementTestState().activate_plan(7, "forms").installed(), patch.object(builder_routes, "require_builder_context", return_value=context), patch.object(builder_routes, "get_project_for_tenant") as query:
            result = TestClient(app).get("/builder/projects/project/site-members")
        self.assertEqual(result.status_code, 403)
        query.assert_not_called()

    def test_member_page_cannot_bypass_website_plan(self):
        app = FastAPI(); app.include_router(public_site_routes.router)
        with EntitlementTestState().activate_plan(7, "forms").installed(), patch.object(public_site_routes, "resolve_website_settings", return_value={"tenant_id": 7}), patch.object(public_site_routes, "enforce_public_rate_limit"), patch.object(public_site_routes, "get_bound_published_project") as query:
            result = TestClient(app).get("/public/sites/synthetic/pages/member")
        self.assertEqual(result.status_code, 403)
        query.assert_not_called()

    def test_published_binding_never_grants_access_during_resolver_failure(self):
        for capability in ["public_form_links", "website_publish", "reservations", "ecommerce_publish"]:
            with self.subTest(capability=capability), patch.object(entitlement_service, "require_entitlement", side_effect=HTTPException(status_code=503, detail="dependency unavailable")):
                with self.assertRaises(HTTPException) as caught:
                    entitlement_service.require_public_runtime_entitlement({"tenant_id": 7, "published_project_id": "published"}, capability)
                self.assertEqual(caught.exception.status_code, 503)
