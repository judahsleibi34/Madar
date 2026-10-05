import json
from uuid import uuid4
import psycopg
from tests.test_elearning_participation_database import ParticipationDatabaseTests


class EnrollmentManagementDatabaseTests(ParticipationDatabaseTests):
    def manage(self, action='enroll_users', users=None, enrollment=None, expected=None, source='manual', confirmed=False, tenant=None, course=None, actor=None):
        return self.db.execute('select public.manage_elearning_enrollments(%s,%s,%s,%s,%s,%s,%s,%s,%s)', (tenant or self.tenant,course or self.course,actor or self.user,action,users,enrollment,expected,source,confirmed)).fetchone()[0]

    def report(self):
        return self.db.execute('select public.get_elearning_enrollment_report(%s,%s)',(self.tenant,self.course)).fetchone()[0]

    def new_user(self, tenant=None, status='active'):
        tenant=tenant or self.tenant;auth=uuid4();email=f'{auth}@example.invalid'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Existing','User',%s,%s,%s,true) returning id",(auth,email,tenant,status)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'member','active')",(tenant,user,auth))
        return user

    def test_bulk_enrollment_links_existing_users_and_rejects_duplicates_atomically(self):
        self.publish();second=self.new_user();user_count=self.db.execute('select count(*) from public.users').fetchone()[0]
        result=self.manage(users=[self.user,second]);self.assertEqual(len(result['enrollment_ids']),2)
        self.assertEqual(self.db.execute('select count(*) from public.users').fetchone()[0],user_count)
        self.assertEqual({r['user_id'] for r in self.report()['enrollments']},{self.user,second})
        third=self.new_user()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.db.transaction():self.manage(users=[third,self.user])
        self.assertEqual(self.report()['learner_count'],2)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_learners where user_id=%s',(third,)).fetchone()[0],0)
        candidates=self.db.execute("select public.get_elearning_enrollment_candidates(%s,%s,'',50,0)",(self.tenant,self.course)).fetchone()[0]
        self.assertTrue(next(u for u in candidates if u['id']==self.user)['already_enrolled'])
        self.assertFalse(next(u for u in candidates if u['id']==third)['already_enrolled'])

    def test_suspend_cancel_reactivate_preserve_users_and_completion_history(self):
        _a,_b,lesson,_l2=self.publish();enrollment=self.manage(users=[self.user])['enrollment_ids'][0];self.complete(enrollment,lesson)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.db.transaction():self.manage('suspend',enrollment=enrollment,expected='active')
        self.manage('suspend',enrollment=enrollment,expected='active',confirmed=True)
        self.assertEqual(self.progress()['learner_count'],0)
        row=self.report()['enrollments'][0];self.assertEqual(row['enrollment_status'],'suspended');self.assertEqual(row['progress_percent'],50);self.assertIsNotNone(row['last_activity'])
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.db.transaction():self.complete(enrollment,lesson)
        with self.assertRaises(psycopg.errors.RaiseException):
            with self.db.transaction():self.manage('cancel',enrollment=enrollment,expected='active',confirmed=True)
        self.manage('cancel',enrollment=enrollment,expected='suspended',confirmed=True)
        self.assertEqual(self.report()['enrollments'][0]['enrollment_status'],'archived')
        self.manage('reactivate',enrollment=enrollment,expected='archived')
        self.assertEqual(self.progress()['enrollments'][0]['completed_lessons'],1)
        self.assertEqual(self.db.execute('select count(*) from public.users where id=%s',(self.user,)).fetchone()[0],1)
        self.db.execute("update public.tenant_memberships set status='disabled' where tenant_id=%s and user_id=%s",(self.tenant,self.user))
        # Use a separate owner to test linked-user membership revocation.
        other=self.new_user();self.db.execute("update public.tenant_memberships set role='owner' where tenant_id=%s and user_id=%s",(self.tenant,other))
        self.manage('suspend',enrollment=enrollment,expected='active',confirmed=True,actor=other)
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.db.transaction():self.manage('reactivate',enrollment=enrollment,expected='suspended',actor=other)
        learner=self.report()['enrollments'][0]['learner_id']
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.db.execute("select public.manage_elearning_participation(%s,%s,%s,'enroll',%s::jsonb)",(self.tenant,self.course,other,json.dumps({'learner_id':learner,'access_source':'manual'})))

    def test_cross_tenant_users_courses_enrollments_and_roles_are_rejected(self):
        self.publish();enrollment=self.manage(users=[self.user])['enrollment_ids'][0]
        foreign_tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Foreign','Test') returning tenant_id").fetchone()[0]
        foreign=self.new_user(foreign_tenant)
        for kwargs in ({'users':[foreign]},{'users':[self.new_user(status='disabled')]},{'users':[self.user],'tenant':foreign_tenant}):
            with self.assertRaises((psycopg.errors.NoDataFound,psycopg.errors.InsufficientPrivilege)):
                with self.db.transaction():self.manage(**kwargs)
        member=self.new_user()
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():self.manage(users=[member],actor=member)
        other=self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Other','published') returning id",(self.tenant,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.manage('cancel',course=other,enrollment=enrollment,expected='active',confirmed=True)
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.db.execute('select public.get_elearning_enrollment_report(%s,%s)',(foreign_tenant,self.course))
        for role in ('anon','authenticated'):
            self.assertFalse(self.db.execute("select has_function_privilege(%s,'public.manage_elearning_enrollments(integer,uuid,integer,text,integer[],uuid,text,text,boolean)','EXECUTE')",(role,)).fetchone()[0])
