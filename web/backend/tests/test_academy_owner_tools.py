"""Owner routes, private bytes and provider reconciliation fail closed."""
import asyncio
import io
import unittest
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from services import academy_owner_service as service
from services import learning_payment_provider as payments
from tests.test_academy_capabilities import AcademyCapabilityTests
from routes import academy_owner_routes as routes
from fastapi import FastAPI
from fastapi.testclient import TestClient


class AcademyOwnerApiTests(AcademyCapabilityTests):
    def setUp(self):
        super().setUp()
        self.actor=SimpleNamespace(tenant_id=1,user_id=9,role='owner')
        for target,name,value in [(routes,'owner',self.actor),(routes,'member',self.actor),(service,'settings_available',True)]:
            p=patch.object(target,name,return_value=value);p.start();self.addCleanup(p.stop)
        p=patch.object(service,'service_supabase',self.db);p.start();self.addCleanup(p.stop)
        app=FastAPI();app.include_router(routes.router);self.owner_client=TestClient(app)

    def test_opportunity_plan_denial_precedes_database_write(self):
        self.actor.tenant_id=3
        self.ledger.side_effect=lambda tenant:__import__('tests.test_academy_capabilities',fromlist=['snapshot']).snapshot(tenant,['forms'])
        response=self.owner_client.post('/elearning/owner/exchange',json={'title':'Opportunity'})
        self.assertEqual(response.status_code,402);self.db.rpc.assert_not_called()

    def test_private_document_requires_tenant_applicant_or_admin(self):
        query=self.db.table.return_value
        query.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'id':str(uuid4()),'user_id':44,'kind':'tuition','status':'submitted'}]
        actor=SimpleNamespace(tenant_id=1,user_id=9,role='learner')
        with self.assertRaises(HTTPException) as error:service.application_access(actor,uuid4())
        self.assertEqual(error.exception.status_code,403)
        with self.assertRaises(HTTPException):service.application_access(self.actor,uuid4(),True)
        query.select.return_value.eq.assert_called_with('tenant_id',1)

    def test_upload_validates_bytes_and_cleans_failed_metadata(self):
        actor=SimpleNamespace(tenant_id=1,user_id=9,role='learner');application=uuid4()
        with patch.object(service,'application_access'),patch.object(service,'require_private_storage'),patch.object(service,'reserve_storage',return_value='reservation'),patch.object(service,'finish_storage'),patch.object(service,'release_storage'),patch.object(service,'store_builder_asset') as store,patch.object(service,'delete_builder_asset') as remove:
            invalid=UploadFile(io.BytesIO(b'<script>'),filename='../../unsafe.pdf',headers=Headers({'content-type':'application/pdf'}))
            with self.assertRaises(HTTPException) as error:asyncio.run(service.upload_document(actor,application,invalid))
            self.assertEqual(error.exception.status_code,415);store.assert_not_called()
            self.db.rpc.return_value.execute.side_effect=RuntimeError('database unavailable')
            valid=UploadFile(io.BytesIO(b'%PDF-1.4\n%%EOF\n'),filename='../../unsafe.pdf',headers=Headers({'content-type':'application/pdf'}))
            with self.assertRaises(RuntimeError):asyncio.run(service.upload_document(actor,application,valid))
            self.assertTrue(store.call_args.kwargs['storage_key'].startswith('academy-private/tenant_1/'))
            self.assertNotIn('..',store.call_args.kwargs['storage_key']);remove.assert_called_once()

    def test_public_bucket_cannot_store_private_documents(self):
        with patch.object(service, 'ensure_builder_asset_bucket'):
            for metadata in ({'public': True}, {}, {'public': None}):
                self.db.storage.get_bucket.return_value = metadata
                with self.assertRaises(HTTPException) as error:
                    service.require_private_storage()
                self.assertEqual(error.exception.status_code, 503)
            self.db.storage.get_bucket.return_value = {'public': False}
            service.require_private_storage()

    def test_dashboard_redacts_other_modules(self):
        from tests.test_academy_capabilities import snapshot
        self.ledger.side_effect=lambda tenant:snapshot(tenant,['forms'])
        self.db.rpc.return_value.execute.return_value.data={'total_learners':7,'applications':[{'kind':'tuition','count':5}],'affiliates':9,'revenue':[{'amount':'999'}],'recent_activity':[{'event_type':'learning_reward_earned'},{'event_type':'learning_course_completed'}]}
        with patch.object(service,'report',return_value={'summary':{'completed_courses':3}}):
            result=service.dashboard(self.actor)
        self.assertEqual(result['total_learners'],7);self.assertNotIn('revenue',result);self.assertEqual(result['applications'],[])
        self.assertEqual(len(result['recent_activity']),1)

    def test_institution_configuration_normalizes_domains(self):
        from services.elearning_settings_service import ELearningSettings
        cfg=ELearningSettings(institution_enabled=True,institution_name='Test Institution',institution_email_domains=['Student@School.EDU'])
        self.assertEqual(cfg.institution_email_domains,['school.edu'])

    def test_public_contact_uses_bound_published_academy(self):
        from routes import public_site_routes
        from services import elearning_settings_service
        app = FastAPI(); app.include_router(routes.public); client = TestClient(app)
        query = self.db.table.return_value.select.return_value
        bound = query.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute
        bound.return_value.data = [{'id': 'bound-project', 'published_schema': {'pages': [{'elements': [{'type': 'academyContact'}]}]}}]
        with patch.object(public_site_routes, 'resolve_website_settings', return_value={'tenant_id': 1, 'academy_project_id': 'bound-project'}), patch.object(elearning_settings_service, 'get_settings', return_value={'enabled': True, 'academy_enabled': True}), patch.object(routes, 'enforce_public_contact_rate_limit'), patch.object(routes, 'service_supabase', self.db):
            payload = {'name': 'Student', 'email': 'student@example.com', 'message': 'Help'}
            self.assertEqual(client.post('/public/academies/academy/contact', json=payload).status_code, 200)
            values = self.db.table.return_value.insert.call_args.args[0]
            self.assertEqual((values['tenant_id'], values['project_id']), (1, 'bound-project'))
            self.assertEqual([call.args[0] for call in self.db.table.call_args_list], ['builder_projects', 'contacts'])
            self.db.table.return_value.insert.reset_mock(); bound.return_value.data = []
            self.assertEqual(client.post('/public/academies/academy/contact', json=payload).status_code, 404)
            self.db.table.return_value.insert.assert_not_called()
            self.assertEqual(client.post('/public/academies/academy/contact', json={**payload, 'tenant_id': 2}).status_code, 422)

    def test_programme_responses_use_learning_owned_storage(self):
        from services import academy_programme_service
        rows = [{'id': str(uuid4()), 'tenant_id': 1, 'kind': 'tuition'}]
        query = self.db.table.return_value.select.return_value
        query.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = rows
        result = academy_programme_service.records(self.actor, 'academy_applications', admin=True, kind='tuition')
        self.assertEqual(result, rows)
        self.db.table.assert_called_once_with('academy_applications')
        query.eq.assert_called_once_with('tenant_id', 1)

    def test_owner_contacts_filter_tenant_before_listing(self):
        with patch.object(routes,'service_supabase',self.db):
            self.db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data=[]
            result=self.owner_client.get('/elearning/owner/contacts?tenant_id=2')
        self.assertEqual(result.status_code,200)
        self.db.table.return_value.select.return_value.eq.assert_called_once_with('tenant_id',1)


class PaymentReconciliationTests(unittest.TestCase):
    def test_provider_reconciliation_rejects_mismatched_purchase(self):
        identifier=uuid4();actor=SimpleNamespace(tenant_id=1,user_id=9,role='learner');db=MagicMock()
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'id':str(identifier),'tenant_id':1,'user_id':9,'provider':'verified_test'}]
        provider=MagicMock();provider.configured.return_value=True
        provider.reconcile.return_value=payments.VerifiedPaymentEvent(tenant_id=2,checkout_id=identifier,event_id='e',transaction_id='p',sequence=1,state='paid',amount='30',currency='USD')
        with patch.object(payments,'service_supabase',db),patch.dict(payments.PROVIDERS,{'verified_test':provider}),patch.object(payments,'apply_verified_event') as apply:
            with self.assertRaises(HTTPException) as error:payments.reconcile_checkout(actor,identifier)
            self.assertEqual(error.exception.status_code,409);apply.assert_not_called()
            provider.reconcile.return_value=provider.reconcile.return_value.model_copy(update={'tenant_id':1})
            payments.reconcile_checkout(actor,identifier);apply.assert_called_once()
