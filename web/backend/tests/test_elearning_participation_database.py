"""Meaningful real-PostgreSQL tests, only on the marked disposable database."""
import json
import sys
from pathlib import Path
from uuid import uuid4
import psycopg
from tests.test_elearning_structure_database import ELearningStructureDatabaseTests

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from seed_elearning_demo import seed, cleanup, verify, stable_id, expected_ids


class ParticipationDatabaseTests(ELearningStructureDatabaseTests):
    def enrollment(self, learner=None, source='manual', course=None):
        learner=learner or self.db.execute("insert into public.elearning_learners(tenant_id,name,email) values(%s,'Test',%s) returning id",(self.tenant,f'{uuid4()}@example.invalid')).fetchone()[0]
        return self.db.execute("select public.manage_elearning_participation(%s,%s,%s,'enroll',%s::jsonb)",(self.tenant,course or self.course,self.user,json.dumps({'learner_id':str(learner),'access_source':source}))).fetchone()[0]['enrollment_id']

    def complete(self,enrollment,lesson):
        return self.db.execute("select public.manage_elearning_participation(%s,%s,%s,'complete_lesson',%s::jsonb)",(self.tenant,self.course,self.user,json.dumps({'enrollment_id':enrollment,'lesson_id':lesson}))).fetchone()[0]

    def progress(self):
        return self.db.execute('select public.get_elearning_progress(%s,%s)',(self.tenant,self.course)).fetchone()[0]

    def publish(self):
        self.db.execute("update public.elearning_courses set status='published' where id=%s",(self.course,))
        a,b=self.section('A'),self.section('B')
        self.run_command('update_section',a,{'name':'A','status':'published'})
        self.run_command('update_section',b,{'name':'B','status':'published'})
        l1,l2=self.lesson(a,'One'),self.lesson(b,'Two')
        self.run_command('update_lesson',l1,{'name':'One','status':'published'})
        self.run_command('update_lesson',l2,{'name':'Two','status':'published'})
        return a,b,l1,l2

    def test_published_only_enrollment_completion_and_derived_progress(self):
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.db.transaction():self.enrollment()
        a,b,l1,l2=self.publish();enrollment=self.enrollment()
        self.complete(enrollment,l1);self.complete(enrollment,l1)
        result=self.progress();self.assertEqual(result['learner_count'],1)
        row=result['enrollments'][0];self.assertEqual(row['progress_percent'],50)
        self.assertEqual([part['progress_percent'] for part in row['sections']],[100,0])
        self.assertEqual(row['completed_lessons'],1)
        self.run_command('move_lesson',l1,{'section_id':b})
        self.assertEqual(self.progress()['enrollments'][0]['sections'][1]['completed_lessons'],1)
        self.complete(enrollment,l2);self.assertEqual(self.progress()['completed_count'],1)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.db.transaction():self.run_command('delete_lesson',l1,{'confirmed':True})
        self.run_command('archive_lesson',l1)
        self.assertEqual(self.progress()['enrollments'][0]['progress_percent'],100)
        self.assertEqual(self.progress()['total_lessons'],1)
        self.run_command('update_lesson',l2,{'name':'Two','status':'draft'})
        self.assertEqual(self.progress()['total_lessons'],0)
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.complete(enrollment,l2)

    def test_cross_tenant_course_permissions_and_access(self):
        self.publish()
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self.db.transaction():self.enrollment(source='free')
        enrollment=self.enrollment()
        other=self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Other','published') returning id",(self.tenant,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.db.execute("select public.manage_elearning_participation(%s,%s,%s,'archive_enrollment',%s::jsonb)",(self.tenant,other,self.user,json.dumps({'enrollment_id':enrollment})))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.db.transaction():self.db.execute("select public.manage_elearning_participation(%s,%s,-1,'archive_enrollment',%s::jsonb)",(self.tenant,self.course,json.dumps({'enrollment_id':enrollment})))
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction():self.db.execute('select public.get_elearning_progress(%s,%s)',(self.tenant+10000,self.course))
        counts=self.db.execute('select public.get_elearning_participation_counts(%s,%s)',(self.tenant,[self.course])).fetchone()[0]
        self.assertEqual(counts[str(self.course)]['learner_count'],1)
        for table in ('elearning_learners','elearning_enrollments','elearning_lesson_completions'):
            for role in ('anon','authenticated'):
                self.assertFalse(self.db.execute("select has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE')",(role,'public.'+table)).fetchone()[0])
        self.db.execute("select public.manage_elearning_participation(%s,%s,%s,'archive_enrollment',%s::jsonb)",(self.tenant,self.course,self.user,json.dumps({'enrollment_id':enrollment})))
        self.assertEqual(self.progress()['learner_count'],0)

    def test_seed_rerun_and_cleanup_preserve_unrelated_data(self):
        original=self.db.execute('select count(*) from public.elearning_courses where tenant_id=%s',(self.tenant,)).fetchone()[0]
        seed(self.db,self.tenant,self.user);first=verify(self.db,self.tenant)
        self.assertEqual([course['lessons'] for course in first],[40,24,15,20])
        self.assertEqual([course['learners'] for course in first],[22,18,12,0])
        self.assertEqual(self.db.execute('select count(*) from public.elearning_learners where tenant_id=%s',(self.tenant,)).fetchone()[0],30)
        times=self.db.execute('select id,created_at from public.elearning_courses where id=any(%s) order by id',(list(expected_ids(self.tenant)[0]),)).fetchall()
        seed(self.db,self.tenant,self.user)
        self.assertEqual(first,verify(self.db,self.tenant))
        self.assertEqual(times,self.db.execute('select id,created_at from public.elearning_courses where id=any(%s) order by id',(list(expected_ids(self.tenant)[0]),)).fetchall())
        english=self.db.execute('select public.get_elearning_progress(%s,%s)',(self.tenant,stable_id(self.tenant,'english'))).fetchone()[0]
        self.assertTrue({0,10,25,40,50,65,75,90,100}.issubset({row['progress_percent'] for row in english['enrollments']}))
        section=self.db.execute('select id from public.elearning_sections where course_id=%s order by position limit 1',(stable_id(self.tenant,'english'),)).fetchone()[0]
        foreign=self.db.execute("insert into public.elearning_lessons(tenant_id,course_id,section_id,name,position,created_by) values(%s,%s,%s,'Non-seed content',100,%s) returning id",(self.tenant,stable_id(self.tenant,'english'),section,self.user)).fetchone()[0]
        with self.assertRaisesRegex(RuntimeError,'non-seed'):cleanup(self.db,self.tenant,self.user)
        self.db.execute('delete from public.elearning_lessons where id=%s',(foreign,))
        cleanup(self.db,self.tenant,self.user)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_courses where tenant_id=%s',(self.tenant,)).fetchone()[0],original)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_learners where tenant_id=%s',(self.tenant,)).fetchone()[0],0)

    def test_tenant_purge_cascades_owned_participation_but_lesson_delete_preserves_history(self):
        self.publish();enrollment=self.enrollment()
        lesson=str(self.db.execute('select id from public.elearning_lessons where course_id=%s limit 1',(self.course,)).fetchone()[0])
        self.complete(enrollment,lesson)
        # The existing users FK requires the normal purge ordering first.
        self.db.execute('delete from public.users where id=%s',(self.user,))
        self.db.execute('delete from public.tenants where tenant_id=%s',(self.tenant,))
        for table in ('elearning_learners','elearning_enrollments','elearning_lesson_completions'):
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where tenant_id=%s',(self.tenant,)).fetchone()[0],0)

    def test_progress_report_filters_course_tenant_and_inactive_learners(self):
        self.publish(); enrollment = self.enrollment()
        other_course = self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Other course','published') returning id", (self.tenant,)).fetchone()[0]
        other_enrollment = self.enrollment(course=other_course)
        rows = self.progress()['enrollments']
        self.assertEqual([row['id'] for row in rows], [enrollment])
        self.assertNotIn(other_enrollment, [row['id'] for row in rows])
        other_tenant = self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other tenant','Test') returning tenant_id").fetchone()[0]
        foreign_learner = self.db.execute("insert into public.elearning_learners(tenant_id,name,email) values(%s,'Foreign learner','foreign@example.invalid') returning id", (other_tenant,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction(): self.enrollment(learner=foreign_learner)
        with self.assertRaises(psycopg.errors.NoDataFound):
            with self.db.transaction(): self.db.execute('select public.get_elearning_progress(%s,%s)', (other_tenant, self.course))
        learner = rows[0]['learner_id']
        self.db.execute("update public.elearning_learners set status='archived' where tenant_id=%s and id=%s", (self.tenant, learner))
        result = self.progress()
        self.assertEqual(result['enrollments'], [])
        self.assertEqual(result['learner_count'], 0)
        self.assertEqual(result['average_progress'], 0)
