from tests.test_elearning_participation_database import ParticipationDatabaseTests
import psycopg


class CourseDeletionDatabaseTests(ParticipationDatabaseTests):
    def delete(self,tenant=None,user=None,revision=1,structure=None,name='Structure test',confirmed=True):
        structure=self.revision if structure is None else structure
        return self.db.execute('select public.delete_elearning_course(%s,%s,%s,%s,%s,%s,%s)',(tenant or self.tenant,self.course,user or self.user,revision,structure,name,confirmed)).fetchone()[0]

    def test_course_deletion_is_confirmed_atomic_and_retains_learner_profiles(self):
        _a,_b,l1,_l2=self.publish();enrollment=self.enrollment();self.complete(enrollment,l1)
        for kwargs,exception in [({'confirmed':False},psycopg.errors.InvalidParameterValue),({'name':'Wrong'},psycopg.errors.InvalidParameterValue),({'structure':1},psycopg.errors.RaiseException),({'revision':99},psycopg.errors.RaiseException),({'tenant':self.tenant+10000},psycopg.errors.NoDataFound),({'user':-1},psycopg.errors.InsufficientPrivilege)]:
            with self.assertRaises(exception):
                with self.db.transaction():self.delete(**kwargs)
            self.assertEqual(self.progress()['learner_count'],1)
        result=self.delete();self.assertTrue(result['deleted'])
        for table in ('elearning_courses','elearning_sections','elearning_lessons','elearning_enrollments','elearning_lesson_completions'):
            column='id' if table=='elearning_courses' else 'course_id'
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where tenant_id=%s and {column}=%s',(self.tenant,self.course)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_learners where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        for role in ('anon','authenticated'):
            self.assertFalse(self.db.execute("select has_function_privilege(%s,'public.delete_elearning_course(integer,uuid,integer,integer,integer,text,boolean)','EXECUTE')",(role,)).fetchone()[0])
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.elearning_courses','DELETE')").fetchone()[0])

    def test_unknown_future_reference_blocks_entire_delete(self):
        self.publish();enrollment=self.enrollment()
        self.db.execute('create table public.synthetic_future_blocks(lesson_id uuid references public.elearning_lessons(id))')
        lesson=self.db.execute('select id from public.elearning_lessons where course_id=%s limit 1',(self.course,)).fetchone()[0]
        self.db.execute('insert into public.synthetic_future_blocks values(%s)',(lesson,))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.db.transaction():self.delete()
        self.assertEqual(self.progress()['learner_count'],1)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_enrollments where id=%s',(enrollment,)).fetchone()[0],1)
