import unittest
from uuid import uuid4
import psycopg
from test_elearning_content_database import DSN
from test_elearning_player_database import ELearningPlayerDatabaseTests
from tests.test_elearning_enrollment_management_database import EnrollmentManagementDatabaseTests

@unittest.skipUnless(DSN,'Requires marked disposable learning database')
class RelationshipsDatabaseTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: ELearningPlayerDatabaseTests.setUpClass())
    command=ELearningPlayerDatabaseTests.command
    media=ELearningPlayerDatabaseTests.media
    snapshot=ELearningPlayerDatabaseTests.snapshot
    new_user=EnrollmentManagementDatabaseTests.new_user

    def setUp(self):
        ELearningPlayerDatabaseTests.setUp(self)
        self.a=self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Group A') returning id",(self.tenant,)).fetchone()[0]
        self.b=self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Group B') returning id",(self.tenant,)).fetchone()[0]
        self.instructor=self.db.execute("insert into public.elearning_instructors(tenant_id,name) values(%s,'Trainer') returning id",(self.tenant,)).fetchone()[0]
        self.enrollment=self.snapshot()['progress']['id']

    def relate(self,action,entity=None,target=None,users=None,kind='group',actor=None,confirmed=True):
        return self.db.execute('select public.manage_elearning_relationships(%s,%s,%s,%s,%s,%s,%s,%s)',(self.tenant,actor or self.user,kind,entity or self.a,action,target,users,confirmed)).fetchone()[0]
    def valid(self):return self.db.execute('select public.elearning_valid_grants(%s,%s)',(self.tenant,self.enrollment)).fetchone()[0]
    def access(self):return self.db.execute('select public.elearning_enrollment_has_access(%s,%s)',(self.tenant,self.enrollment)).fetchone()[0]
    def grant_group(self,group=None):
        self.relate('add_members',entity=group,users=[self.learner]);self.relate('assign_course',entity=group,target=self.course)
    def revoke_manual(self):self.relate('revoke_manual',kind='course',entity=self.course,target=self.enrollment)

    def test_manual_plus_group_removal_preserves_manual_and_progress(self):
        self.snapshot(lesson=self.lesson,complete=True);self.grant_group()
        self.assertEqual({v['type'] for v in self.valid()},{'manual','group'})
        self.relate('remove_member',users=[self.learner]);self.assertTrue(self.access())
        self.assertEqual([v['type'] for v in self.valid()],['manual'])
        self.assertEqual(self.snapshot()['progress']['progress_percent'],50)

    def test_free_plus_group_is_independent(self):
        self.revoke_manual();self.db.execute("update public.elearning_courses set access_type='free' where id=%s",(self.course,))
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'enroll_users',%s,null,null,'free',false)",(self.tenant,self.course,self.user,[self.learner]))
        candidates=self.db.execute("select public.get_elearning_enrollment_candidates(%s,%s,'',50,0)",(self.tenant,self.course)).fetchone()[0]
        self.assertEqual(next(row for row in candidates if row['id']==self.learner)['individual_sources'],['free'])
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'enroll_users',%s,null,null,'manual',false)",(self.tenant,self.course,self.user,[self.learner]))
        self.grant_group();self.assertEqual({v['type'] for v in self.valid()},{'manual','free','group'})
        self.revoke_manual();self.relate('remove_course',target=self.course)
        self.assertTrue(self.access());self.assertEqual([v['type'] for v in self.valid()],['free'])

    def test_two_groups_group_only_loss_and_regrant_preserve_history(self):
        self.snapshot(lesson=self.lesson,complete=True);self.revoke_manual();self.grant_group();self.grant_group(self.b)
        self.relate('remove_course',target=self.course);self.assertTrue(self.access())
        self.assertEqual([v['group_id'] for v in self.valid()],[str(self.b)])
        self.relate('remove_member',entity=self.b,users=[self.learner]);self.assertFalse(self.access())
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.snapshot(lesson=self.lesson)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_lesson_completions where enrollment_id=%s',(self.enrollment,)).fetchone()[0],1)
        self.relate('add_members',entity=self.b,users=[self.learner]);self.assertTrue(self.access())
        self.assertEqual(self.snapshot()['progress']['progress_percent'],50)
        self.assertEqual(self.snapshot()['progress']['id'],self.enrollment)

    def test_new_member_sync_and_repeated_membership_assignment_are_idempotent(self):
        self.relate('assign_course',target=self.course);new=self.new_user()
        for _ in range(2):self.relate('add_members',users=[new]);self.relate('assign_course',target=self.course)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_group_members where group_id=%s and user_id=%s',(self.a,new)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_access_grants a join public.elearning_enrollments e on e.id=a.enrollment_id join public.elearning_learners l on l.id=e.learner_id where l.user_id=%s',(new,)).fetchone()[0],1)
        self.assertEqual(self.snapshot(user=new)['progress']['total_lessons'],2)

    def test_member_added_while_assigned_course_is_draft_gains_access_only_after_publication(self):
        self.relate('assign_course',target=self.course)
        self.db.execute("update public.elearning_courses set status='draft' where id=%s",(self.course,))
        new=self.new_user();self.relate('add_members',users=[new])
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.snapshot(user=new)
        self.db.execute("update public.elearning_courses set status='published' where id=%s",(self.course,))
        self.assertEqual(self.snapshot(user=new)['progress']['total_lessons'],2)

    def test_suspension_and_cancellation_override_all_grants(self):
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'suspend',null,%s,'active',null,true)",(self.tenant,self.course,self.user,self.enrollment))
        self.grant_group();self.assertFalse(self.access());self.relate('assign_course',target=self.course);self.assertFalse(self.access())
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'reactivate',null,%s,'suspended',null,false)",(self.tenant,self.course,self.user,self.enrollment));self.assertTrue(self.access())
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'cancel',null,%s,'active',null,true)",(self.tenant,self.course,self.user,self.enrollment));self.grant_group(self.b);self.assertFalse(self.access())

    def test_remove_manual_keeps_group_and_remove_last_source_excludes_reports(self):
        self.grant_group();self.revoke_manual();self.assertTrue(self.access())
        self.relate('remove_course',target=self.course);self.assertFalse(self.access())
        self.assertEqual(self.db.execute('select public.get_elearning_progress(%s,%s)',(self.tenant,self.course)).fetchone()[0]['learner_count'],0)
        record=self.db.execute('select public.get_elearning_enrollment_report(%s,%s)',(self.tenant,self.course)).fetchone()[0]['enrollments'][0]
        self.assertFalse(record['effective_access']);self.assertEqual(record['access_sources'],[])

    def test_group_summary_uses_existing_engine_without_lesson_details(self):
        self.snapshot(lesson=self.lesson,complete=True);self.grant_group()
        full=self.db.execute('select public.get_elearning_progress(%s,%s)',(self.tenant,self.course)).fetchone()[0]
        compact=self.db.execute('select public.get_elearning_progress_records(%s,%s,false,false)',(self.tenant,self.course)).fetchone()[0]
        self.assertEqual(compact['average_progress'],full['average_progress'])
        self.assertEqual(compact['enrollments'][0]['sections'],[])
        self.assertTrue(full['enrollments'][0]['sections'][0]['lessons'])
        summary=self.db.execute("select public.get_elearning_relationships(%s,'group',%s)",(self.tenant,self.a)).fetchone()[0]['courses'][0]
        self.assertEqual(summary['average_progress'],full['average_progress'])
        self.assertFalse(self.db.execute("select has_function_privilege('service_role','public.get_elearning_progress_records(integer,uuid,boolean,boolean)','EXECUTE')").fetchone()[0])

    def test_instructor_course_group_and_user_link_never_enroll(self):
        person=self.new_user();before=self.db.execute('select count(*) from public.elearning_enrollments').fetchone()[0]
        for _ in range(2):self.relate('assign_instructor',target=self.instructor);self.relate('assign_instructor',kind='course',entity=self.course,target=self.instructor)
        self.relate('link_user',kind='instructor',entity=self.instructor,users=[person])
        self.assertEqual(self.db.execute('select count(*) from public.elearning_enrollments').fetchone()[0],before)
        info=self.db.execute("select public.get_elearning_relationships(%s,'instructor',%s)",(self.tenant,self.instructor)).fetchone()[0]
        self.assertEqual(info['entity']['user_id'],person);self.assertEqual(len(info['courses']),1);self.assertEqual(len(info['groups']),1)
        self.relate('remove_group',kind='instructor',entity=self.instructor,target=self.a);self.relate('remove_course',kind='instructor',entity=self.instructor,target=self.course)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_enrollments').fetchone()[0],before)

    def test_cross_tenant_role_confirmation_and_atomic_bulk_rejection(self):
        other=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other','Local') returning tenant_id").fetchone()[0]
        foreign_user=self.new_user(other);foreign_group=self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Foreign') returning id",(other,)).fetchone()[0]
        foreign_course=self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Foreign','published') returning id",(other,)).fetchone()[0]
        foreign_instructor=self.db.execute("insert into public.elearning_instructors(tenant_id,name) values(%s,'Foreign') returning id",(other,)).fetchone()[0]
        for args in [dict(action='add_members',users=[self.learner,foreign_user]),dict(action='assign_course',target=foreign_course),dict(action='assign_group',kind='course',entity=self.course,target=foreign_group),dict(action='assign_instructor',target=foreign_instructor),dict(action='link_user',kind='instructor',entity=self.instructor,users=[foreign_user])]:
            with self.assertRaises(psycopg.errors.NoDataFound):
                with self.db.transaction():self.relate(**args)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_group_members where group_id=%s',(self.a,)).fetchone()[0],0)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():self.relate('add_members',users=[self.learner],actor=self.learner)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.db.transaction():self.relate('remove_member',users=[self.learner],confirmed=False)

    def test_archived_group_and_disabled_user_revoke_effective_group_access(self):
        self.revoke_manual();self.grant_group();self.db.execute("update public.elearning_groups set status='archived' where id=%s",(self.a,));self.assertFalse(self.access())
        self.db.execute("update public.elearning_groups set status='active' where id=%s",(self.a,));self.assertTrue(self.access())
        self.db.execute("update public.tenant_memberships set status='disabled' where tenant_id=%s and user_id=%s",(self.tenant,self.learner));self.assertFalse(self.access())

    def test_purchase_requires_commerce_and_client_mutation_forbidden(self):
        schema = self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
        if schema < 128:
            with self.assertRaises(psycopg.errors.CheckViolation):
                with self.db.transaction():self.db.execute("insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type) values(%s,%s,%s,'purchase')",(self.tenant,self.course,self.enrollment))
        else:
            self.revoke_manual()
            self.db.execute("insert into public.elearning_access_grants(tenant_id,course_id,enrollment_id,grant_type) values(%s,%s,%s,'purchase')",(self.tenant,self.course,self.enrollment))
            self.assertFalse(self.access())  # A grant is not a confirmed entitlement.
        for table in ['elearning_access_grants','elearning_group_members','elearning_group_courses','elearning_course_instructors','elearning_group_instructors']:
            for role in ['anon','authenticated','service_role']:
                self.assertFalse(self.db.execute("select has_table_privilege(%s,%s,'INSERT')",(role,'public.'+table)).fetchone()[0])
        self.assertFalse(self.db.execute("select has_function_privilege('service_role','public.manage_elearning_participation_schema124(integer,uuid,integer,text,jsonb)','EXECUTE')").fetchone()[0])
