import json
import unittest
from uuid import uuid4
from tests import test_elearning_structure_database as structure
DSN = structure.DSN
import psycopg


@unittest.skipUnless(DSN, 'Requires marked disposable local database')
class AcademyIntegrationDatabaseTests(unittest.TestCase):
    setUpClass = structure.ELearningStructureDatabaseTests.setUpClass
    setUp = structure.ELearningStructureDatabaseTests.setUp

    def schema(self, kind='heading'):
        return {'version':1,'defaultPageId':'home','pages':[{'id':'home','name':'Home','slug':'/','isDefault':True,'access':'public','sections':[{'id':'section','elements':[{'id':'element','type':kind,'content':'Academy'}]}]}]}

    def project(self, schema=None, profile='academy', tenant=None):
        return self.db.execute('insert into public.builder_projects(tenant_id,owner_user_id,name,slug,usage_profile,draft_schema) values(%s,%s,%s,%s,%s,%s::jsonb) returning id',(tenant or self.tenant,self.user,'Academy',str(uuid4()),profile,json.dumps(schema or self.schema()))).fetchone()[0]

    def reject(self, operation, code='23514'):
        with self.db.transaction(force_rollback=True):
            with self.assertRaises(psycopg.Error) as error: operation()
            self.assertEqual(error.exception.sqlstate,code)

    def test_allowlist_is_database_enforced_and_profile_is_immutable(self):
        for kind in ['formBlock','reservationRequest','reservationBlock','embed','customCode']:
            self.reject(lambda:self.project(self.schema(kind)))
        project=self.project()
        self.reject(lambda:self.db.execute("update public.builder_projects set usage_profile='website' where id=%s",(project,)), 'P0001')
        self.reject(lambda:self.db.execute('update public.builder_projects set published_schema=%s::jsonb where id=%s',(json.dumps(self.schema('formBlock')),project)))

    def test_academy_publication_does_not_replace_main_website(self):
        main=self.project(profile='website'); academy=self.project()
        self.db.execute('insert into public.website_settings(tenant_id,user_id,subdomain) values(%s,%s,%s)',(self.tenant,self.user,'testing-'+uuid4().hex[:8]))
        self.db.execute('select public.publish_validated_builder_project_atomic(%s,%s,0,%s::jsonb,now(),1,false)',(main,self.tenant,json.dumps(self.schema())))
        self.db.execute('select public.publish_validated_builder_project_atomic(%s,%s,0,%s::jsonb,now(),1,false)',(academy,self.tenant,json.dumps(self.schema())))
        bindings=self.db.execute('select published_project_id,academy_project_id from public.website_settings where tenant_id=%s',(self.tenant,)).fetchone()
        self.assertEqual(bindings,(main,academy))
        self.reject(lambda:self.db.execute('update public.website_settings set published_project_id=%s where tenant_id=%s',(academy,self.tenant)), '23503')
        self.reject(lambda:self.db.execute('update public.website_settings set academy_project_id=%s where tenant_id=%s',(main,self.tenant)), '23503')

    def test_cross_tenant_binding_fails(self):
        academy=self.project()
        other=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other','Local') returning tenant_id").fetchone()[0]
        self.reject(lambda:self.db.execute('insert into public.website_settings(tenant_id,user_id,subdomain,academy_project_id) values(%s,%s,%s,%s)',(other,self.user,'other-'+uuid4().hex[:8],academy)), '23503')

    def test_verified_learner_is_not_promoted_to_owner(self):
        auth=uuid4();self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,f'{auth}@example.com'))
        user=self.db.execute("insert into public.users(auth_id,email,first_name,last_name,tenant_id,account_kind,account_status,email_verified) values(%s,%s,'Learner','Test',%s,'platform','pending_verification',true) returning id",(auth,f'{auth}@example.com',self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'learner','active')",(self.tenant,user,auth))
        self.db.execute('select public.provision_verified_account(%s)',(auth,))
        self.assertEqual(self.db.execute('select role from public.tenant_memberships where user_id=%s',(user,)).fetchone()[0],'learner')
        self.assertEqual(self.db.execute('select tenant_id,account_status from public.users where id=%s',(user,)).fetchone(),(self.tenant,'active'))
        self.assertEqual(self.db.execute('select count(*) from public.website_settings where user_id=%s',(user,)).fetchone()[0],0)

    def setup_website(self):
        self.db.execute('insert into public.website_settings(tenant_id,user_id,subdomain) values(%s,%s,%s)',(self.tenant,self.user,'academy-'+uuid4().hex[:8]))

    def ensure(self):
        return self.db.execute('select (public.ensure_academy_builder_project(%s,%s,%s::jsonb)).id',(self.tenant,self.user,json.dumps(self.schema()))).fetchone()[0]

    def test_ten_independent_owners_have_ten_durable_isolated_academy_projects(self):
        owners = []
        for index in range(10):
            auth = uuid4()
            email = f'{auth}@example.invalid'
            self.db.execute('insert into auth.users(id,email) values(%s,%s)', (auth, email))
            user = self.db.execute("insert into public.users(auth_id,email,first_name,last_name,account_kind,account_status,email_verified) values(%s,%s,'Academy','Owner','platform','pending_verification',true) returning id", (auth, email)).fetchone()[0]
            self.db.execute('insert into public.pending_account_onboarding(auth_id,user_id,business_name,requested_subdomain) values(%s,%s,%s,%s)', (auth, user, f'Owner {index} Academy', 'owner-' + uuid4().hex[:12]))
            tenant = self.db.execute('select (public.provision_verified_account(%s)).tenant_id', (auth,)).fetchone()[0]
            schema = self.schema()
            schema['pages'][0]['sections'][0]['elements'][0]['content'] = f'Owner {index} content'
            project = self.db.execute('select (public.ensure_academy_builder_project(%s,%s,%s::jsonb)).id', (tenant, user, json.dumps(schema))).fetchone()[0]
            owners.append((tenant, user, project, schema))
        self.assertEqual(len({owner[0] for owner in owners}), 10)
        self.assertEqual(len({owner[2] for owner in owners}), 10)
        for tenant, user, project, schema in owners:
            # Reopening must reuse saved content, even with a different seed.
            reopened = self.db.execute('select (public.ensure_academy_builder_project(%s,%s,%s::jsonb)).id', (tenant, user, json.dumps(self.schema()))).fetchone()[0]
            self.assertEqual(reopened, project)
            self.assertEqual(self.db.execute('select tenant_id,owner_user_id,draft_schema from public.builder_projects where id=%s', (project,)).fetchone(), (tenant, user, schema))
            self.assertEqual(self.db.execute('select academy_editor_project_id from public.website_settings where tenant_id=%s', (tenant,)).fetchone()[0], project)
            other_tenant = next(other[0] for other in owners if other[0] != tenant)
            self.reject(lambda: self.db.execute('select public.ensure_academy_builder_project(%s,%s,%s::jsonb)', (other_tenant, user, json.dumps(schema))), '42501')

    def test_editor_lifecycle_is_idempotent_recovers_deleted_or_archived_drafts(self):
        self.setup_website();first=self.ensure()
        self.assertEqual(self.ensure(),first)
        self.db.execute('delete from public.builder_projects where id=%s',(first,))
        self.assertIsNone(self.db.execute('select academy_editor_project_id from website_settings where tenant_id=%s',(self.tenant,)).fetchone()[0])
        second=self.ensure();self.assertNotEqual(first,second)
        self.db.execute("update public.builder_projects set status='archived' where id=%s",(second,))
        third=self.ensure();self.assertNotEqual(second,third)
        self.assertEqual(self.ensure(),third)

    def test_editor_recovery_preserves_published_project_and_schema(self):
        self.setup_website();live=self.ensure()
        self.db.execute('select public.publish_validated_builder_project_atomic(%s,%s,0,%s::jsonb,now(),1,false)',(live,self.tenant,json.dumps(self.schema())))
        draft=self.project();self.db.execute('update website_settings set academy_editor_project_id=%s where tenant_id=%s',(draft,self.tenant))
        self.db.execute('delete from builder_projects where id=%s',(draft,))
        self.assertEqual(self.ensure(),live)
        self.assertEqual(self.db.execute('select academy_project_id from website_settings where tenant_id=%s',(self.tenant,)).fetchone()[0],live)
        self.assertEqual(self.db.execute('select published_schema from builder_projects where id=%s',(live,)).fetchone()[0],self.schema())

    def test_full_public_pages_and_chrome_are_supported_but_fixed_routes_are_reserved(self):
        schema=self.schema();schema['pages'].append({'id':'about','name':'About','slug':'/about','access':'public','sections':[]});schema['siteChrome']={'showHeader':True,'showFooter':True,'brand':'Academy'}
        self.project(schema)
        for path in ['/courses','/courses/secret','/plans','/login','/my-learning','/api','/checkout']:
            schema['pages'][1]['slug']=path;self.reject(lambda:self.project(schema))
        self.project(self.schema('formBlock'),profile='website')
        self.project(self.schema('reservationBlock'),profile='website')
        self.project(self.schema('academyInstructors'))

    def test_editor_binding_rejects_foreign_tenant_or_website_profile(self):
        self.setup_website();main=self.project(profile='website')
        self.reject(lambda:self.db.execute('update website_settings set academy_editor_project_id=%s where tenant_id=%s',(main,self.tenant)), '23503')
        other=self.db.execute("insert into tenants(brand_name,owner_name) values('Other','Other') returning tenant_id").fetchone()[0]
        foreign=self.project(tenant=other)
        self.reject(lambda:self.db.execute('update website_settings set academy_editor_project_id=%s where tenant_id=%s',(foreign,self.tenant)), '23503')
        self.reject(lambda:self.db.execute('select public.ensure_academy_builder_project(%s,%s,%s::jsonb)',(other,self.user,json.dumps(self.schema()))), '42501')

    def test_instructors_projection_omits_private_assignments_and_contact_identity(self):
        instructor=self.db.execute("insert into elearning_instructors(tenant_id,name,description,email) values(%s,'Teacher','Public profile','private@example.invalid') returning id",(self.tenant,)).fetchone()[0]
        self.db.execute("insert into elearning_course_instructors(tenant_id,course_id,instructor_id) values(%s,%s,%s)",(self.tenant,self.course,instructor))
        self.assertEqual(self.db.execute('select public.get_academy_public_instructors(%s,%s)',(self.tenant,[self.course])).fetchone()[0],[])
        self.db.execute("update elearning_courses set status='published',catalog_visible=true,access_type='free' where id=%s",(self.course,))
        data=self.db.execute('select public.get_academy_public_instructors(%s,%s)',(self.tenant,[self.course])).fetchone()[0]
        self.assertEqual(data[0]['name'],'Teacher');self.assertNotIn('email',data[0]);self.assertNotIn('user_id',data[0]);self.assertEqual(data[0]['course_ids'],[str(self.course)])
        self.db.execute("update elearning_courses set access_type='private' where id=%s",(self.course,))
        self.assertEqual(self.db.execute('select public.get_academy_public_instructors(%s,%s)',(self.tenant,[self.course])).fetchone()[0],[])

    def test_cleanup_restores_every_binding_and_refuses_preexisting_projects(self):
        import importlib.util
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('academy_cleanup',Path(__file__).resolve().parents[2]/'scripts/academy_builder_fixture_cleanup.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        self.setup_website();original=self.ensure();fixture=self.project()
        self.db.execute('update website_settings set academy_project_id=%s,academy_editor_project_id=%s where tenant_id=%s',(fixture,fixture,self.tenant))
        state={'tenant_id':self.tenant,'builder_project':str(fixture),'builder_project_created':True,'preexisting_builder_projects':[str(original)],'original_academy_bindings':{'published':None,'editor':str(original)}}
        helper.restore_academy_fixture_binding(self.db,state)
        self.assertEqual(self.db.execute('select academy_project_id,academy_editor_project_id from website_settings where tenant_id=%s',(self.tenant,)).fetchone(),(None,original))
        self.assertIsNone(self.db.execute('select id from builder_projects where id=%s',(fixture,)).fetchone())
        state['builder_project']=str(original)
        with self.assertRaisesRegex(ValueError,'pre-existing'):helper.restore_academy_fixture_binding(self.db,state)
        self.assertIsNotNone(self.db.execute('select id from builder_projects where id=%s',(original,)).fetchone())

    def test_widget_configuration_and_hidden_form_actions_are_database_enforced(self):
        for config in [{'maxItems':True},{'maxItems':25},{'instructorIds':['not-a-uuid']},{'instructorIds':[1]},{'variant':'script'},{'heading':[]},{'email':'private@example.com'}]:
            schema=self.schema('academyInstructors');schema['pages'][0]['sections'][0]['elements'][0]['academy']=config
            self.reject(lambda:self.project(schema))
        for extra in [{'action':{'type':'openForm'}},{'connectedFormId':'hidden-form'}]:
            schema=self.schema('button');schema['pages'][0]['sections'][0]['elements'][0].update(extra)
            self.reject(lambda:self.project(schema))
