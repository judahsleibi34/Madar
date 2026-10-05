"""Public projections and private CTA authority on the marked local database."""
import json
import unittest
from tests.test_elearning_content_database import DSN
from uuid import uuid4
from tests import test_elearning_commerce_database as commerce


@unittest.skipUnless(DSN, "Requires marked disposable learning database")
class AcademyDatabaseTests(unittest.TestCase):
    setUpClass = commerce.LearningCommerceDatabaseTests.setUpClass
    plan = commerce.LearningCommerceDatabaseTests.plan
    checkout = commerce.LearningCommerceDatabaseTests.checkout
    event = commerce.LearningCommerceDatabaseTests.event
    enroll = commerce.LearningCommerceDatabaseTests.enroll
    rejected = commerce.LearningCommerceDatabaseTests.rejected
    def setUp(self):
        from tests.test_elearning_content_database import ELearningContentDatabaseTests
        ELearningContentDatabaseTests.setUp(self)
        self.db.execute("update public.elearning_courses set status='published',access_type='paid' where id=%s", (self.course,))
        self.other = self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Other','published','paid') returning id", (self.tenant,)).fetchone()[0]
        self.private = self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Private','published','private') returning id", (self.tenant,)).fetchone()[0]
        self.db.execute("insert into public.elearning_settings(tenant_id,settings) values(%s,%s::jsonb)",
                        (self.tenant,json.dumps({'enabled':True,'academy_enabled':True,'academy_featured_courses':[str(self.course),str(self.private)]})))
        self.db.execute("update public.elearning_sections set status='published' where id=%s",(self.section,))
        self.db.execute("update public.elearning_lessons set status='published' where id=%s",(self.lesson,))

    def academy(self, user=None, course=None, tenant=None):
        return self.db.execute('select public.get_elearning_academy(%s,%s,%s)',(tenant or self.tenant,user,course)).fetchone()[0]

    def card(self, user=None):
        return next(c for c in self.academy(user)['courses'] if c['id']==str(self.course))

    def test_public_projection_hides_private_unpublished_and_account_data(self):
        self.plan()
        self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Secret draft','draft','free'),(%s,'Secret archive','archived','free')",(self.tenant,self.tenant))
        data=self.academy()
        self.assertFalse(data['authenticated']);self.assertNotIn(str(self.private),[c['id'] for c in data['courses']])
        card=self.card();self.assertTrue(card['featured']);self.assertEqual(card['outline'],[{'name':'First','lesson_count':1}])
        self.assertIsNone(card['progress']);self.assertIsNone(card['credential']);self.assertEqual(card['cta'],{'action':'buy'})
        self.assertNotIn('blocks',json.dumps(data));self.assertNotIn('enrollment_id',json.dumps(data))
        self.rejected(lambda:self.academy(course=self.private),'P0002')
        self.rejected(lambda:self.academy(course=uuid4()),'P0002')
        self.db.execute("update public.elearning_courses set catalog_visible=false where id=%s",(self.course,))
        self.assertNotIn(str(self.course),[c['id'] for c in self.academy()['courses']])

    def test_only_relevant_active_plans_and_real_prices(self):
        active=self.plan();self.plan(status='draft');self.plan(scope='single_course',ids=[self.other],status='archived')
        self.assertEqual([p['id'] for p in self.academy()['plans']],[active['id']])
        self.assertEqual(self.card()['price']['amount'],20)
        self.db.execute("update public.elearning_courses set status='draft' where id=%s",(self.course,))
        self.assertEqual(self.academy()['plans'],[])

    def test_central_cta_entitlement_enrollment_progress_resume_suspension(self):
        plan=self.plan(scope='all_courses',ids=[]);self.event(self.checkout(plan))
        card=self.card(self.user);self.assertEqual(card['cta']['action'],'enroll');self.assertEqual(card['cta']['included_in'],{'name':'Test access'})
        eid=self.enroll();card=self.card(self.user);self.assertEqual(card['cta']['action'],'continue')
        self.assertEqual(card['resume'],f'/my-learning/courses/{self.course}/lessons/{self.lesson}')
        self.assertEqual(card['progress']['progress_percent'],0)
        self.db.execute('select public.complete_elearning_learner_lesson(%s,%s,%s,%s)',(self.tenant,self.user,self.course,self.lesson))
        card=self.card(self.user);self.assertEqual(card['progress']['progress_percent'],100)
        self.db.execute("update public.elearning_enrollments set status='suspended' where id=%s",(eid,))
        self.assertEqual(self.card(self.user)['cta']['action'],'suspended');self.assertIsNone(self.card(self.user)['progress'])
        self.assertEqual(self.card()['cta']['action'],'buy')

    def test_public_outline_does_not_expose_lesson_titles_or_drafts(self):
        self.db.execute("insert into public.elearning_lessons(tenant_id,course_id,section_id,name,status,position) values(%s,%s,%s,'Protected draft','draft',1)",(self.tenant,self.course,self.section))
        self.assertNotIn('Protected draft',json.dumps(self.academy()))
        self.db.execute("update public.elearning_sections set status='draft' where id=%s",(self.section,))
        self.assertEqual(self.card()['outline'],[])

    def test_foreign_user_membership_disabled_academy_and_rpc_privileges(self):
        foreign_tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Foreign Academy','Local') returning tenant_id").fetchone()[0]
        foreign_course=self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Foreign published course','published','free') returning id",(foreign_tenant,)).fetchone()[0]
        auth=uuid4();self.db.execute("insert into auth.users(id,email) values(%s,%s)",(auth,f'{auth}@example.com'))
        foreign_user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Foreign','Learner',%s,%s,'active',true) returning id",(auth,f'{auth}@example.com',foreign_tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(foreign_tenant,foreign_user,auth))
        self.rejected(lambda:self.academy(user=foreign_user),'42501')
        self.rejected(lambda:self.academy(course=foreign_course),'P0002')
        self.db.execute("update public.elearning_settings set settings=settings||'{\"academy_enabled\":false}' where tenant_id=%s",(self.tenant,))
        self.rejected(lambda:self.academy(),'P0002')
        for role in ['anon','authenticated']:
            self.assertFalse(self.db.execute("select has_function_privilege(%s,'public.get_elearning_academy(integer,integer,uuid)','execute')",(role,)).fetchone()[0])
        self.assertTrue(self.db.execute("select has_function_privilege('service_role','public.get_elearning_academy(integer,integer,uuid)','execute')").fetchone()[0])
