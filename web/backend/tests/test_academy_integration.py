import unittest
from copy import deepcopy
from fastapi import HTTPException
from services.academy_builder_service import default_landing, validate_academy_schema
from services.academy_auth_service import safe_return_path


class AcademyCompositionTests(unittest.TestCase):
    def setUp(self):
        self.schema = default_landing({"platform_name": "Original Academy", "academy_hero_title": "Saved hero", "academy_benefits": "Saved benefits", "academy_featured_courses": []}, "testing")

    def test_saved_presentation_seeds_existing_builder_structure(self):
        validate_academy_schema(self.schema)
        self.assertEqual(len(self.schema['pages']), 1)
        serialized = str(self.schema)
        self.assertIn('Saved hero', serialized)
        self.assertIn('Saved benefits', serialized)
        for kind in ['academyFeaturedCourses','academyCourseCollection','academyPlans','academyContinueLearning']:
            self.assertIn(kind, serialized)
        self.assertNotIn('progress_percent', serialized)

    def test_excluded_components_in_every_supported_layout_are_rejected(self):
        for kind in ['formBlock','reservationRequest','reservationBlock','registrationBlock','embed','customCode','checkout','document']:
            for layout in ['elements','freeElements','rows']:
                with self.subTest(kind=kind, layout=layout):
                    schema = deepcopy(self.schema)
                    section = schema['pages'][0]['sections'][0]
                    element = {'id':'bad','type':kind}
                    if layout=='rows': section['rows']=[{'columns':[{'elements':[element]}]}]
                    else: section[layout]=[element]
                    with self.assertRaises(HTTPException): validate_academy_schema(schema)

    def test_private_data_and_unbounded_widget_config_are_rejected(self):
        for config in [{'progress_percent':50},{'enrollment_id':'secret'},{'maxItems':500},{'variant':'custom-js'},{'variant':[]},{'courseIds':['not-a-uuid']},{'heading':[]},{'description':'x'*1201},{'featuredOnly':'true'}]:
            schema=deepcopy(self.schema)
            schema['pages'][0]['sections'][1]['rows'][0]['columns'][0]['elements'][0]['academy']=config
            with self.assertRaises(HTTPException): validate_academy_schema(schema)

    def test_public_pages_and_instructors_use_schema_133_without_private_payloads(self):
        from unittest.mock import patch
        schema=deepcopy(self.schema)
        schema['pages'].append({'id':'about','name':'About','slug':'/about','sections':[]})
        schema['siteChrome']={'brand':'Tenant Academy','showHeader':True,'showFooter':True}
        widget={'id':'instructors','type':'academyInstructors','academy':{'heading':'Meet instructors','instructorIds':['00000000-0000-0000-0000-000000000001']}}
        schema['pages'][1]['sections']=[{'elements':[widget]}]
        with patch('services.elearning_settings_service.settings_available',return_value=True):
            validate_academy_schema(schema)
            for slug in ['/courses','/courses/secret','/plans','/my-learning','/checkout','/login']:
                bad=deepcopy(schema);bad['pages'][1]['slug']=slug
                with self.assertRaises(HTTPException):validate_academy_schema(bad)
        with patch('services.elearning_settings_service.settings_available',return_value=False):
            with self.assertRaises(HTTPException) as error:validate_academy_schema(schema)
            self.assertEqual(error.exception.status_code,503)

    def test_malformed_identity_and_connected_form_capabilities_are_rejected(self):
        for page_id in [[],{},False,1]:
            schema=deepcopy(self.schema);schema['pages'][0]['id']=page_id
            with self.assertRaises(HTTPException):validate_academy_schema(schema)
        for element in [{'id':'bad','type':[]},{'id':'bad','type':'button','connectedFormId':'form'},{'id':'bad','type':'button','action':{'type':'openForm'}},{'id':'bad','type':'button','action':{'type':[]}}]:
            schema=deepcopy(self.schema);schema['pages'][0]['sections'][0]['elements']=[element]
            with self.assertRaises(HTTPException):validate_academy_schema(schema)

    def test_return_paths_are_tenant_scoped_and_decode_traversal(self):
        base='/academy/testing'
        for requested in ['https://evil.test', '//evil.test', '/academy/foreign', '/academy/testing/../foreign', '/academy/testing/%2e%2e/foreign', '/academy/testing/%252e%252e/foreign','javascript:alert(1)','/academy/testing/%5c%5cevil.test','/my-learningevil','/my-learning/%2e%2e/e-learning']:
            with self.subTest(requested=requested): self.assertEqual(safe_return_path(requested,base),base)
        for requested in [base+'/courses/id?resume=enroll',base+'/plans?resume=checkout&plan=id','/my-learning/certificates']:
            self.assertEqual(safe_return_path(requested,base),requested)

class AcademyAuthenticationTests(unittest.TestCase):
    def test_email_domain_registration_is_direct_and_reuses_verified_signup(self):
        from unittest.mock import patch
        from fastapi import Request
        from routes.elearning_academy_routes import register, AcademyRegisterRequest
        request = Request({'type':'http','method':'POST','path':'/public/academies/testing/auth/register','headers':[(b'host',b'localhost')]})
        settings = {'academy_registration':'email_domain', 'academy_email_domains':['university.edu', 'xn--bcher-kva.de']}
        for email in ['jack@UNIVERSITY.edu', 'jack@bücher.de']:
            with self.subTest(email=email), patch('services.academy_auth_service.academy_auth_settings', return_value=({'subdomain':'testing'},7,settings)), patch('routes.public_site_routes.register_tenant_account', return_value={'requires_email_verification':True}) as shared:
                payload = AcademyRegisterRequest(full_name='Jack', email=email, password='Safe-password-123')
                result = register('testing', payload, request)
                self.assertTrue(result['requires_email_verification'])
                shared.assert_called_once()
                self.assertEqual(shared.call_args.args[0], 'testing')
                self.assertIn('academy_context', shared.call_args.kwargs)

    def test_email_domain_rejects_unlisted_subdomain_and_suffix_spoof_before_account_creation(self):
        from unittest.mock import patch
        from fastapi import Request
        from routes.elearning_academy_routes import register, AcademyRegisterRequest
        request = Request({'type':'http','method':'POST','path':'/public/academies/testing/auth/register','headers':[(b'host',b'localhost')]})
        for email in ['jack@gmail.com', 'jack@student.university.edu', 'jack@university.edu.attacker.com', 'jack@fakeuniversity.edu']:
            with self.subTest(email=email), patch('services.academy_auth_service.academy_auth_settings', return_value=({'subdomain':'testing'},7,{'academy_registration':'email_domain','academy_email_domains':['university.edu']})), patch('routes.public_site_routes.register_tenant_account') as shared:
                payload = AcademyRegisterRequest(full_name='Jack', email=email, password='Safe-password-123')
                with self.assertRaises(HTTPException) as failure:
                    register('testing', payload, request)
                self.assertEqual(failure.exception.status_code, 403)
                self.assertEqual(failure.exception.detail['code'], 'academy_email_domain_not_allowed')
                shared.assert_not_called()

    def test_invitation_policy_is_enforced_before_registration(self):
        from unittest.mock import patch
        from fastapi import Request
        from routes.elearning_academy_routes import register, AcademyRegisterRequest
        request = Request({'type':'http','method':'POST','path':'/public/academies/testing/auth/register','headers':[(b'host',b'localhost')]})
        payload = AcademyRegisterRequest(full_name='Learner Test',email='learner@example.com',password='Safe-password-123',return_to='/academy/testing/courses/course?resume=enroll')
        with patch('services.academy_auth_service.academy_auth_settings',return_value=({'subdomain':'testing'},7,{'academy_registration':'invitation_only'})), patch('routes.public_site_routes.register_tenant_account') as shared:
            with self.assertRaises(HTTPException) as failure: register('testing',payload,request)
            self.assertEqual(failure.exception.status_code,403)
            shared.assert_not_called()

    def test_verified_email_continuation_uses_canonical_tenant_paths(self):
        from unittest.mock import patch
        from fastapi import Request
        from routes.elearning_academy_routes import register, AcademyRegisterRequest
        request = Request({'type':'http','method':'POST','path':'/public/academies/testing/auth/register','headers':[(b'host',b'localhost')]})
        target='/academy/testing/plans?resume=checkout&plan=plan-id'
        payload = AcademyRegisterRequest(full_name='Learner Test',email='learner@example.com',password='Safe-password-123',return_to=target)
        with patch('services.academy_auth_service.academy_auth_settings',return_value=({'subdomain':'testing'},7,{'academy_registration':'open'})), patch('routes.public_site_routes.register_tenant_account',return_value={'requires_email_verification':True}) as shared:
            result=register('testing',payload,request)
            self.assertEqual(result['return_to'],target)
            from urllib.parse import parse_qs,urlsplit
            continuation=shared.call_args.kwargs['academy_context']['return_to']
            self.assertEqual(urlsplit(continuation).path,'/academy/login')
            self.assertEqual(parse_qs(urlsplit(continuation).query)['returnTo'],['/academy/plans?resume=checkout&plan=plan-id'])

    def test_academy_registration_reuses_users_and_learner_membership_without_enrollment(self):
        from unittest.mock import patch
        from fastapi import Request
        from routes import public_site_routes as routes
        from tests.test_builder_site_members import FakeSupabase
        fake=FakeSupabase({})
        payload=routes.TenantRegisterRequest(full_name='Learner Test',email='learner@example.com',password='Safe-password-123')
        request=Request({'type':'http','method':'POST','path':'/public/academies/testing/auth/register','headers':[(b'host',b'localhost')]})
        with patch.object(routes,'service_supabase',fake), patch.object(routes,'supabase',fake), patch.object(routes,'resolve_website_settings',return_value={'tenant_id':7,'subdomain':'testing'}), patch.object(routes,'enforce_auth_rate_limit'):
            routes.register_tenant_account('testing',payload,request,academy_context={'return_to':'/academy/login'})
        self.assertEqual(len(fake.tables['users']),1)
        self.assertEqual(fake.tables['users'][0]['tenant_id'],7)
        self.assertEqual(fake.tables['tenant_memberships'][0]['role'],'learner')
        self.assertFalse(fake.tables.get('tenant_site_memberships'))
        self.assertFalse(fake.tables.get('elearning_enrollments'))

    def test_academy_relative_buttons_use_shared_publication_validator_only_when_authorized(self):
        from routes.builder_routes import validate_publish_schema
        schema=default_landing({'platform_name':'Academy'},'testing')
        with self.assertRaises(HTTPException): validate_publish_schema(schema)
        validate_publish_schema(schema,allow_relative_button_urls=True)

    def test_learner_membership_never_grants_staff_website_capabilities(self):
        from routes import public_site_routes as routes
        from tests.test_builder_site_members import FakeSupabase
        from unittest.mock import patch
        for status in ['active','suspended']:
            fake=FakeSupabase({'tenant_memberships':[{'tenant_id':7,'user_id':11,'role':'learner','status':status}]})
            with patch.object(routes,'service_supabase',fake):
                self.assertIsNone(routes.get_tenant_site_access({'tenant_id':7},{'id':11,'tenant_id':7}))

    def test_hosted_runtime_rejects_another_tenant_session(self):
        from fastapi import Request
        from types import SimpleNamespace
        from unittest.mock import patch
        from services import tenant_service
        from tests.test_builder_site_members import FakeSupabase
        request=Request({'type':'http','method':'GET','path':'/elearning/my-learning','headers':[(b'host',b'foreign.madarportal.com')]})
        fake=FakeSupabase({'website_settings':[{'subdomain':'foreign','tenant_id':99}]})
        with patch.object(tenant_service,'service_supabase',fake),patch.object(tenant_service,'require_regular_user',return_value=(SimpleNamespace(id='auth-id'),{'id':11,'tenant_id':7,'auth_id':'auth-id'})):
            with self.assertRaises(HTTPException) as failure: tenant_service.require_active_tenant_member(request,allow_learner=True)
            self.assertEqual(failure.exception.status_code,403)

    def test_malformed_academy_schema_is_a_validation_error(self):
        for schema in [{'pages':None},{'pages':{'home':{}}},{'pages':[None]}]:
            with self.assertRaises(HTTPException): validate_academy_schema(schema)
        schema=default_landing({'platform_name':'Academy'},'testing')
        schema['pages'][0]['sections'][0]['rows'][0]['columns'][0]['elements'][0]['action']='invalid'
        with self.assertRaises(HTTPException): validate_academy_schema(schema)

class AcademyManagementProfileTests(unittest.TestCase):
    def queries(self):
        from unittest.mock import MagicMock
        website, projects = MagicMock(), MagicMock()
        for query in (website, projects):
            for method in ('select', 'eq', 'neq', 'order', 'limit'):
                getattr(query, method).return_value = query
        website.execute.return_value.data = [{'subdomain': 'testing', 'academy_project_id': 'landing'}]
        projects.execute.return_value.data = [{'id': 'landing', 'draft_schema': {'pages': []}, 'published_schema': {'pages': []}}]
        client = MagicMock(); client.table.side_effect = lambda name: {'website_settings': website, 'builder_projects': projects}[name]
        return client, website, projects

    def test_management_read_is_tenant_scoped_and_never_seeds(self):
        from unittest.mock import patch, call
        from services.academy_builder_service import management_profile
        client, website, projects = self.queries()
        with patch('database.service_supabase', client), patch('services.elearning_settings_service.settings_available', return_value=True):
            for _ in range(2):
                result = management_profile(17)
                self.assertEqual(result['published_project_id'], 'landing')
        self.assertEqual(website.eq.call_args_list, [call('tenant_id', 17)] * 2)
        self.assertEqual(projects.eq.call_args_list, [call('tenant_id', 17), call('usage_profile', 'academy')] * 2)
        projects.neq.assert_called_with('status', 'archived')
        client.rpc.assert_not_called(); website.update.assert_not_called(); projects.insert.assert_not_called()

    def test_initializer_uses_atomic_lifecycle_after_existing_builder_permission_checks(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from fastapi import Request, Response
        from routes.elearning_academy_routes import initialize_landing
        client, _, _ = self.queries()
        actor = SimpleNamespace(tenant_id=17, user_id=3)
        client.rpc.return_value.execute.return_value.data = {'id': 'landing'}
        with patch('database.service_supabase', client), patch('services.elearning_access_service.require_elearning_access', return_value=actor), patch('services.elearning_settings_service.settings_available', return_value=True), patch('services.elearning_settings_service.get_settings', return_value={'platform_name':'Original'}), patch('routes.builder_routes.require_supported_builder_client'), patch('routes.builder_routes.require_builder_context', return_value=actor), patch('routes.builder_routes.require_any_entitlement') as entitlement, patch('routes.builder_routes.require_schema_asset_tenant'):
            for _ in range(2):
                self.assertEqual(initialize_landing(Request({'type':'http','headers':[]}),Response())['project']['id'], 'landing')
        entitlement.assert_called_with(17, {'page_builder'}, message='An active page-builder plan is required.')
        self.assertEqual(client.rpc.call_count, 2)
        self.assertEqual(client.rpc.call_args.args[0], 'ensure_academy_builder_project')
        self.assertEqual(client.rpc.call_args.args[1]['p_tenant_id'], 17)
        client.table.return_value.insert.assert_not_called()
