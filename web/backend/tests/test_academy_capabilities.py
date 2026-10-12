"""API plan enforcement exercises Madar's real module/dated-ledger resolver."""
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routes import academy_programme_routes as routes
from services import academy_programme_service as programmes
from services import academy_capability_service as gates
from services.elearning_access_service import authorize_elearning_context


def snapshot(tenant, modules, suspended=None):
    return {'contract_version':115,'tenant_id':tenant,'revision':1,'review_state':'reviewed','commercial_suspended_at':suspended,'access_state':'active','effective_at':datetime.now(timezone.utc).isoformat(),
            'period':{'tenant_id':tenant,'plan_id':None,'module_ids':modules,'valid_from':'2025-01-01T00:00:00Z','valid_until':'2030-01-01T00:00:00Z'},
            'subscriptions':[{'tenant_id':tenant,'plan_id':None,'module_basis':{name:{'price_book_id':str(uuid4())} for name in modules},'state':'active','pricing':{'pricing_status':'priced'}}],'addons':[]}


class AcademyCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.stack=[]
        # Published intake navigation is a separate projection; isolate it from
        # the finance entitlement tests rather than contacting a real provider.
        navigation=patch('services.elearning_academy_service.member_profile',return_value={'application_paths':{}})
        navigation.start();self.addCleanup(navigation.stop)
        def start(patcher):
            value=patcher.start();self.addCleanup(patcher.stop);return value
        start(patch.dict(os.environ,{'COMMERCIAL_ENTITLEMENTS_ENFORCED':'true'}))
        self.ledger=start(patch('services.entitlement_service.resolve_commercial_access',side_effect=lambda tenant:snapshot(tenant,['forms','website','ecommerce'] if tenant==1 else ['website'])))
        start(patch.object(programmes,'settings_available',return_value=True))
        start(patch.object(programmes,'get_settings',return_value={'programmes_enabled':True,'support_programme_name':'Student Scholarship','exchange_programme_name':'International Study'}))
        self.db=start(patch.object(programmes,'service_supabase'))
        self.db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data=[]
        self.db.rpc.return_value.execute.return_value.data={'enrollments':[]}
        def context(request,response):
            return SimpleNamespace(tenant_id=int(request.headers.get('x-test-academy','1')),user_id=9,role='owner')
        start(patch.object(routes,'member',side_effect=context));start(patch.object(routes,'owner',side_effect=context))
        app=FastAPI();app.include_router(routes.router);self.client=TestClient(app)

    def test_academy_module_sets_are_different_without_another_plan_store(self):
        self.assertTrue(all(gates.capabilities(1).values()))
        b=gates.capabilities(2)
        self.assertTrue(b['tuition']);self.assertTrue(b['exchange'])
        for key in ('affiliate','referrals','rewards','wallet','withdrawal','transactions','reports'):self.assertFalse(b[key])

    def test_disabled_owner_endpoints_reject_before_queries(self):
        paths=['/finance/rewards','/finance/referrals','/finance/transactions','/reports','/reports?export=true','/management/application?kind=affiliate','/management/withdrawal']
        for path in paths:
            with self.subTest(path=path):
                response=self.client.get('/elearning/programmes'+path,headers={'x-test-academy':'2'})
                self.assertEqual(response.status_code,402)
        self.db.table.assert_not_called();self.db.rpc.assert_not_called()

    def test_disabled_member_actions_reject_before_mutation(self):
        response=self.client.post('/elearning/programmes/withdrawals',headers={'x-test-academy':'2'},json={'amount':'50','payment_method':'PayPal','payment_information':'Owned','ownership_confirmed':True,'idempotency_key':str(uuid4())})
        self.assertEqual(response.status_code,402)
        response=self.client.post('/elearning/programmes/applications',headers={'x-test-academy':'2'},json={'kind':'affiliate','details':{'terms_accepted':True},'idempotency_key':str(uuid4())})
        self.assertEqual(response.status_code,402)
        self.db.rpc.assert_not_called()

    def test_allowed_report_export_uses_only_authenticated_tenant(self):
        response=self.client.get('/elearning/programmes/reports?export=true')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.db.rpc.call_args.args[1]['p_tenant'],1)
        self.assertIn('private',response.headers['cache-control'])
        self.assertNotIn('tenant_id',routes.reports.__annotations__)

    def test_configuration_cannot_enable_an_unentitled_capability(self):
        with self.assertRaises(HTTPException) as error:gates.validate_settings_access(2,{'affiliates_enabled':True},{'affiliates_enabled':False})
        self.assertEqual(error.exception.status_code,402)
        gates.validate_settings_access(2,{'affiliates_enabled':True},{'affiliates_enabled':True})
        visible=gates.permitted_settings(2,{'affiliate_terms':'Private','tuition_terms':'Scholarship'})
        self.assertEqual(visible,{'tuition_terms':'Scholarship'})

    def test_suspension_wins_over_existing_operator_override(self):
        self.ledger.side_effect=lambda tenant:snapshot(tenant,['ecommerce'],suspended='2026-10-01T00:00:00Z')
        with patch.dict(os.environ,{'COMMERCIAL_ENTITLEMENTS_ENFORCED':'false'}):
            self.assertFalse(any(gates.capabilities(1).values()))
            with self.assertRaises(HTTPException) as error:gates.require_capability(1,'withdrawal')
            self.assertEqual(error.exception.status_code,403)

    def test_learner_and_platform_identity_do_not_gain_owner_permissions(self):
        for role in ('learner','affiliate','platform_admin'):
            with self.subTest(role=role),self.assertRaises(HTTPException):authorize_elearning_context(SimpleNamespace(role=role),'elearning.manage')

    def test_cefr_is_optional_without_enabling_programmes_or_commerce(self):
        programmes.get_settings.return_value={'programmes_enabled':False}
        response=self.client.put('/elearning/programmes/courses/'+str(uuid4())+'/cefr',headers={'x-test-academy':'2'},json={'section_id':str(uuid4()),'level':'A1','template_id':str(uuid4()),'enabled':True})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.db.rpc.call_args.args[0],'configure_elearning_cefr')

    def test_finance_projection_hides_unentitled_support_configuration(self):
        self.ledger.side_effect=lambda tenant:snapshot(tenant,['ecommerce'])
        wallet={'available':'20','verified_sales':2,'threshold':6,'remaining_sales':4,'tuition_eligible':False,'exchange_eligible':True}
        visible=gates.permitted_wallet(wallet,gates.capabilities(1))
        self.assertEqual(visible,{'available':'20','verified_sales':2})
        self.db.rpc.return_value.execute.return_value.data=wallet
        self.db.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data=[]
        result=programmes.account(SimpleNamespace(tenant_id=1,user_id=9,role='learner'))
        self.assertNotIn('threshold',result['wallet'])
        self.assertNotIn('support_programme_name',result['settings'])

    def test_report_only_plan_cannot_disclose_reward_aggregates(self):
        self.ledger.side_effect=lambda tenant:snapshot(tenant,['forms'])
        self.db.rpc.return_value.execute.return_value.data={'enrollments':[],'rewards':[{'amount':'999'}],'applications':[{'kind':'tuition','count':10}]}
        result=self.client.get('/elearning/programmes/reports')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['rewards'],[])
        self.assertEqual(result.json()['applications'],[])

    def test_finance_member_history_excludes_unentitled_programmes(self):
        self.ledger.side_effect=lambda tenant:snapshot(tenant,['ecommerce'])
        permitted=str(uuid4());hidden=str(uuid4())
        self.db.rpc.return_value.execute.return_value.data={'wallet':{'available':'20','threshold':6},'history':[{'entity_type':'application','entity_id':permitted},{'entity_type':'application','entity_id':hidden},{'entity_type':'withdrawal','entity_id':str(uuid4())}]}
        query=self.db.table.return_value
        query.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value.data=[{'id':permitted}]
        response=self.client.get('/elearning/programmes/management/members/9?tenant_id=2')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['history']),2)
        self.assertNotIn('threshold',response.json()['wallet'])
        self.assertEqual(self.db.rpc.call_args.args[1]['p_tenant'],1)
        query.select.return_value.eq.assert_called_once_with('tenant_id',1)

    def test_review_checks_tenant_record_and_its_own_module(self):
        query=MagicMock();self.db.table.return_value=query
        query.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'kind':'affiliate'}]
        response=self.client.post('/elearning/programmes/management/application/'+str(uuid4())+'/review',headers={'x-test-academy':'2'},json={'status':'approved','revision':1,'note':'Review'})
        self.assertEqual(response.status_code,402)
        query.select.return_value.eq.return_value.eq.assert_called()
        self.db.rpc.assert_not_called()
