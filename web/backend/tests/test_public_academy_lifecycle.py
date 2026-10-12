"""Public presentation must obey publication and existing operational authority."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from services import elearning_academy_service as service
from services.elearning_settings_service import ELearningSettings


class PublicAcademyLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.rpc.return_value.execute.return_value.data = {'courses': [], 'plans': [], 'authenticated': False}
        self.cfg = ELearningSettings().model_dump(mode='json')
        for target, value in [('service_supabase', self.db), ('settings_available', True), ('get_settings', self.cfg), ('profile', {})]:
            mock = patch.object(service, target, **({'return_value': value} if target != 'service_supabase' else {'new': value}))
            mock.start(); self.addCleanup(mock.stop)
        self.gate = patch.object(service, 'require_public_runtime_entitlement').start()
        self.addCleanup(patch.stopall)

    def test_website_entitlement_denial_precedes_any_public_content_read(self):
        self.gate.side_effect = HTTPException(503, 'Unavailable')
        with self.assertRaises(HTTPException) as caught:
            service.storefront(17, {'subdomain': 'testing'})
        self.assertEqual(caught.exception.status_code, 503)
        self.db.rpc.assert_not_called(); self.db.table.assert_not_called()
        self.gate.assert_called_once_with({'subdomain': 'testing', 'tenant_id': 17}, 'website_publish')

    def test_bound_unpublished_missing_or_empty_snapshot_never_restores_default_website(self):
        for rows in [[], [{'status': 'draft', 'published_schema': {'pages': []}}], [{'status': 'published', 'published_schema': None}]]:
            with self.subTest(rows=rows):
                self.db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = rows
                with self.assertRaises(HTTPException) as caught:
                    service.storefront(17, {'subdomain': 'testing', 'academy_project_id': 'bound'})
                self.assertEqual(caught.exception.status_code, 404)

    def test_never_bound_legacy_academy_keeps_default_presentation(self):
        result = service.storefront(17, {'subdomain': 'testing'})
        self.assertTrue(result['landing']['pages'])
        self.db.table.assert_not_called()

    def test_new_exchange_entry_requires142_forms_and_public_links(self):
        self.cfg.update(programmes_enabled=True, exchange_programme_enabled=True, exchange_programme_name='Exchange', exchange_terms='Terms')
        for schema142, forms_grant, public_links in [(False, True, True), (True, False, True), (True, True, False), (True, True, True)]:
            with self.subTest(schema142=schema142, forms=forms_grant, links=public_links), patch.object(service, 'settings_available', side_effect=lambda version=131: version < 142 or schema142), patch('services.academy_capability_service.capabilities', return_value={'affiliate': False, 'tuition': False, 'exchange': True, 'forms': forms_grant}), patch.object(service, 'get_tenant_entitlements', return_value={'operational_capabilities': ['public_form_links'] if public_links else []}):
                self.db.rpc.reset_mock()
                result = service.storefront(17, {'subdomain': 'testing'})
                enabled = schema142 and forms_grant and public_links
                self.assertEqual('exchange_programme_name' in result['programme_info'], enabled)
                self.assertEqual(any(call.args[0] == 'get_academy_open_opportunities' for call in self.db.rpc.call_args_list), enabled)

    def test_public_form_website_denial_precedes_definition_and_response_authority(self):
        from routes import elearning_forms_routes as routes
        with patch('routes.public_site_routes.resolve_website_settings', return_value={'tenant_id':17}), patch('services.entitlement_service.require_public_runtime_entitlement', side_effect=HTTPException(503,'Unavailable')), patch.object(routes.service,'definition') as definition, patch.object(routes.service,'gate') as gate:
            with self.assertRaises(HTTPException) as caught:
                routes.context('testing','form',None,None)
        self.assertEqual(caught.exception.status_code,503)
        definition.assert_not_called();gate.assert_not_called()

    def test_authorized_preview_data_survives_unpublished_website(self):
        self.gate.side_effect = HTTPException(503, 'Website unavailable')
        self.db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{'status': 'draft', 'published_schema': None}]
        result = service.storefront(17, {'subdomain':'testing','academy_project_id':'bound'}, preview=True)
        self.assertTrue(result['landing']['pages'])
        self.gate.assert_not_called()

    def test_preview_http_requires_owner_and_matching_tenant(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes import elearning_academy_routes as routes
        app = FastAPI();app.include_router(routes.router)
        client = TestClient(app)
        with patch('services.elearning_access_service.require_elearning_access', side_effect=HTTPException(403,'Owner required')), patch.object(service,'storefront') as data:
            self.assertEqual(client.get('/public/academies/testing/preview').status_code,403)
            data.assert_not_called()
        actor = SimpleNamespace(tenant_id=17,user_id=3,role='owner')
        with patch('services.elearning_access_service.require_elearning_access',return_value=actor), patch('services.entitlement_service.require_entitlement'), patch.object(routes,'resolve_website_settings',return_value={'tenant_id':88,'subdomain':'other'}), patch.object(service,'storefront') as data:
            self.assertEqual(client.get('/public/academies/other/preview').status_code,403)
            data.assert_not_called()
        with patch('services.elearning_access_service.require_elearning_access',return_value=actor), patch('services.entitlement_service.require_entitlement'), patch.object(routes,'resolve_website_settings',return_value={'tenant_id':17,'subdomain':'testing'}), patch.object(service,'storefront',return_value={'courses':[]}) as data:
            response = client.get('/public/academies/testing/preview')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'private, no-store')
            self.assertTrue(data.call_args.kwargs['preview'])
