"""Real SQL checks on a marked disposable loopback database."""
import json
import unittest
from uuid import uuid4
import psycopg
from test_elearning_content_database import ELearningContentDatabaseTests, DSN


@unittest.skipUnless(DSN, 'Requires marked disposable learning database')
class ELearningPlayerDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ELearningContentDatabaseTests.setUpClass()

    command = ELearningContentDatabaseTests.command
    media = ELearningContentDatabaseTests.media

    def setUp(self):
        ELearningContentDatabaseTests.setUp(self)
        for table, identifier in [('elearning_courses', self.course), ('elearning_sections', self.section), ('elearning_lessons', self.lesson)]:
            self.db.execute(f"update public.{table} set status='published' where id=%s", (identifier,))
        self.second = self.db.execute("insert into public.elearning_lessons(tenant_id,course_id,section_id,name,status,position) values(%s,%s,%s,'Second','published',1) returning id", (self.tenant,self.course,self.section)).fetchone()[0]
        self.draft = self.db.execute("insert into public.elearning_lessons(tenant_id,course_id,section_id,name,status,position) values(%s,%s,%s,'SECRET DRAFT','draft',2) returning id", (self.tenant,self.course,self.section)).fetchone()[0]
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        self.learner=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Learner','Player',%s,%s,'active',true) returning id",(auth,email,self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'member','active')",(self.tenant,self.learner,auth))
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'enroll_users',%s,null,null,'manual',false)",(self.tenant,self.course,self.user,[self.learner]))
        self.command()

    def snapshot(self, lesson=None, user=None, course=None, tenant=None, complete=False):
        function='complete_elearning_learner_lesson' if complete else 'get_elearning_learner_course'
        return self.db.execute(f'select public.{function}(%s,%s,%s,%s)',(tenant or self.tenant,user or self.learner,course or self.course,lesson)).fetchone()[0]

    def denied(self, code, **args):
        with self.db.transaction(force_rollback=True):
            with self.assertRaises(psycopg.Error) as caught: self.snapshot(**args)
            self.assertEqual(caught.exception.sqlstate,code)

    def test_read_filters_drafts_blocks_and_other_enrollments(self):
        self.command('archive', self.snapshot(lesson=self.lesson)['blocks'][0]['id'], {'confirmed':True})
        data=self.snapshot(lesson=self.lesson)
        self.assertEqual(data['blocks'],[])
        self.assertEqual(data['progress']['total_lessons'],2)
        self.assertNotIn('SECRET DRAFT',json.dumps(data))
        self.assertNotIn('email',data['progress'])
        self.denied('P0002',lesson=self.draft)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_lesson_completions').fetchone()[0],0)

    def test_explicit_idempotent_completion_and_shared_reports(self):
        before=self.snapshot(lesson=self.lesson);self.assertFalse(before['lesson']['completed'])
        after=self.snapshot(lesson=self.lesson,complete=True)
        self.assertTrue(after['lesson']['completed']);self.assertEqual(after['progress']['progress_percent'],50)
        self.assertEqual(after['sections'][0]['progress_percent'],50)
        self.snapshot(lesson=self.lesson,complete=True)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_lesson_completions where enrollment_id=%s',(after['progress']['id'],)).fetchone()[0],1)
        report=self.db.execute('select public.get_elearning_progress(%s,%s)',(self.tenant,self.course)).fetchone()[0]
        self.assertEqual(report['enrollments'][0]['progress_percent'],50)
        finished=self.snapshot(lesson=self.second,complete=True)
        self.assertEqual(finished['progress']['progress_status'],'completed');self.assertIsNone(finished['continue_lesson_id'])

    def test_sequence_read_completion_and_continue(self):
        self.db.execute("insert into public.elearning_settings(tenant_id,settings) values(%s,'{\"sequential_progression\":true,\"allow_locked_content\":true}') on conflict(tenant_id) do update set settings=excluded.settings",(self.tenant,))
        outline=self.snapshot();self.assertEqual(outline['continue_lesson_id'],self.lesson)
        self.assertTrue(outline['sections'][0]['lessons'][1]['locked'])
        self.denied('42501',lesson=self.second);self.denied('42501',lesson=self.second,complete=True)
        data=self.snapshot(lesson=self.lesson,complete=True)
        self.assertEqual(data['continue_lesson_id'],str(self.second))
        self.assertFalse(data['sections'][0]['lessons'][1]['locked'])
        self.snapshot(lesson=self.second)

    def test_enrollment_and_url_guessing_are_denied(self):
        self.denied('P0002',user=self.user) # owner without an enrollment is not a learner
        self.denied('P0002',course=uuid4(),lesson=self.lesson)
        self.denied('P0002',tenant=self.tenant+100000,lesson=self.lesson)
        foreign_tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other tenant','Local') returning tenant_id").fetchone()[0]
        foreign_course=self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Foreign course','published') returning id",(foreign_tenant,)).fetchone()[0]
        self.denied('P0002',course=foreign_course)
        self.denied('P0002',lesson=uuid4())
        self.db.execute("update public.elearning_enrollments set status='suspended' where course_id=%s",(self.course,))
        self.denied('P0002',lesson=self.lesson,complete=True)

    def test_inactive_user_and_membership_denied(self):
        self.db.execute("update public.tenant_memberships set status='disabled' where user_id=%s",(self.learner,))
        self.denied('P0002',lesson=self.lesson)

    def test_unpublished_section_and_course_denied(self):
        self.db.execute("update public.elearning_sections set status='draft' where id=%s",(self.section,))
        self.assertEqual(self.snapshot()['progress']['total_lessons'],0)
        self.denied('P0002',lesson=self.lesson)
        self.db.execute("update public.elearning_courses set status='archived' where id=%s",(self.course,))
        self.denied('P0002')

    def test_media_checks_prerequisites_and_active_content(self):
        media=self.media();result=self.command(payload={'type':'audio','media_id':media,'content':{'version':1}})
        key=self.db.execute('select storage_key from public.builder_assets where id=%s',(media,)).fetchone()[0]
        def access(user=self.learner):return self.db.execute('select public.elearning_learner_media_access(%s,%s,%s)',(self.tenant,user,key)).fetchone()[0]
        self.assertTrue(access())
        self.db.execute('update public.elearning_content_blocks set lesson_id=%s,position=0 where media_id=%s',(self.second,media))
        self.db.execute("insert into public.elearning_settings(tenant_id,settings) values(%s,'{\"sequential_progression\":true}') on conflict(tenant_id) do update set settings=excluded.settings",(self.tenant,))
        self.assertFalse(access());self.assertTrue(access(self.user))
        self.snapshot(lesson=self.lesson,complete=True);self.assertTrue(access())
        self.db.execute('update public.elearning_content_blocks set archived_at=now() where media_id=%s',(media,))
        self.assertFalse(access())

    def test_my_learning_is_only_current_active_enrollment(self):
        rows=self.db.execute('select public.get_elearning_my_learning(%s,%s,50,0)',(self.tenant,self.learner)).fetchone()[0]
        self.assertEqual(len(rows),1)
        self.assertEqual(self.db.execute('select public.get_elearning_my_learning(%s,%s,50,0)',(self.tenant,self.user)).fetchone()[0],[])
        self.db.execute("update public.elearning_enrollments set status='archived' where course_id=%s",(self.course,))
        self.assertEqual(self.db.execute('select public.get_elearning_my_learning(%s,%s,50,0)',(self.tenant,self.learner)).fetchone()[0],[])

    def test_rpc_permissions_and_cross_course_relationship(self):
        for function in ['get_elearning_learner_course(integer,integer,uuid,uuid)', 'complete_elearning_learner_lesson(integer,integer,uuid,uuid)', 'get_elearning_my_learning(integer,integer,integer,integer)', 'elearning_learner_media_access(integer,integer,text)']:
            for role in ['anon', 'authenticated']:
                self.assertFalse(self.db.execute("select has_function_privilege(%s,%s,'execute')", (role, 'public.'+function)).fetchone()[0])
        other=self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Other enrolled course','published') returning id",(self.tenant,)).fetchone()[0]
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'enroll_users',%s,null,null,'manual',false)",(self.tenant,other,self.user,[self.learner]))
        self.denied('P0002',course=other,lesson=self.lesson)
