"""Section/course placement and formal completion integration on marked local DBs."""
import json
import unittest
from uuid import uuid4
import psycopg
from test_elearning_player_database import ELearningPlayerDatabaseTests as Player
from test_elearning_content_database import DSN

@unittest.skipUnless(DSN,'Requires marked disposable learning database')
class PlacementDatabaseTests(unittest.TestCase):
    setUpClass=Player.__dict__['setUpClass']
    setUp=Player.setUp
    command=Player.command
    media=Player.media
    snapshot=Player.snapshot

    def create(self,section=None,required=True,assessment=None,course=None,tenant=None,status='published'):
        target=course or self.course;owner=tenant or self.tenant
        revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(target,)).fetchone()[0]
        settings={'title':'Section Check' if section else 'Final Check','instructions':'Answer','passing_score':70,'max_attempts':2,'required_for_completion':required,'status':status}
        questions=[{'type':'true_false','prompt':'True?','points':1,'config':{'correct_answer':True}}]
        return self.db.execute('select public.create_elearning_placed_assessment(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)',(owner,target,section,self.user,revision,json.dumps(settings),json.dumps(questions),assessment)).fetchone()[0]

    def runtime(self,p,start=False,course=None,user=None):
        return self.db.execute('select public.'+('start_elearning_assessment_attempt' if start else 'elearning_assessment_runtime')+'(%s,%s,null,%s,%s)',(self.tenant,course or self.course,p['block_id'],user or self.learner)).fetchone()[0]

    def submit(self,p,passed=True,attempt=None):
        attempt=attempt or self.runtime(p,True)['attempt']['id']
        return self.db.execute('select public.submit_elearning_assessment_attempt(%s,%s,null,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,p['block_id'],self.learner,attempt,json.dumps({p['questions'][0]['id']:{'value':passed}}))).fetchone()[0]

    def denied(self,callback,code=None):
        with self.db.transaction(force_rollback=True):
            with self.assertRaises(psycopg.Error) as caught:callback()
            if code:self.assertEqual(caught.exception.sqlstate,code)

    def test_section_then_course_completion_and_sequence(self):
        other=self.db.execute("insert into public.elearning_sections(tenant_id,course_id,name,status,position) values(%s,%s,'Second section','published',1) returning id",(self.tenant,self.course)).fetchone()[0]
        self.db.execute('update public.elearning_lessons set section_id=%s,position=0 where id=%s',(other,self.second))
        self.db.execute("insert into public.elearning_settings(tenant_id,settings) values(%s,'{\"sequential_progression\":true}') on conflict(tenant_id) do update set settings=excluded.settings",(self.tenant,))
        section=self.create(self.section);final=self.create()
        self.denied(lambda:self.runtime(section,True),'42501');self.denied(lambda:self.runtime(final,True),'42501')
        first=self.snapshot(self.lesson,complete=True);self.assertFalse(first['sections'][0]['completion']['completed']);self.denied(lambda:self.snapshot(self.second),'42501')
        fail=self.submit(section,False);self.assertFalse(fail['attempt']['passed']);self.denied(lambda:self.snapshot(self.second),'42501')
        self.submit(section);self.assertTrue(self.snapshot()['sections'][0]['completion']['completed']);self.assertFalse(self.snapshot(self.second)['lesson']['locked'])
        last=self.snapshot(self.second,complete=True);self.assertEqual(last['progress']['progress_percent'],100);self.assertFalse(last['progress']['completion']['completed']);self.assertEqual(last['progress']['progress_status'],'active')
        self.submit(final,False);self.assertFalse(self.snapshot()['progress']['completion']['completed']);self.submit(final)
        complete=self.snapshot()['progress'];self.assertTrue(complete['completion']['completed']);self.assertEqual(complete['progress_status'],'completed');self.assertIsNotNone(complete['completed_at'])
        event=self.db.execute("select completion_snapshot from public.elearning_completion_events where enrollment_id=%s and scope='course'",(complete['id'],)).fetchone()[0];self.assertTrue(event['requirements'][0]['passed']);self.assertEqual(len(event['sections']),2)
        self.assertEqual(self.snapshot()['progress']['completed_at'],complete['completed_at'])

    def test_optional_available_early_and_historical_completion_is_stable(self):
        optional=self.create(required=False);self.assertEqual(self.runtime(optional,True)['attempt']['attempt_number'],1)
        self.submit(optional,False);self.snapshot(self.lesson,complete=True);self.snapshot(self.second,complete=True)
        completed=self.snapshot()['progress']['completion'];self.assertTrue(completed['completed'])
        self.create();self.create(self.section);after=self.snapshot()['progress']['completion'];self.assertTrue(after['completed']);self.assertEqual(after['completed_at'],completed['completed_at']);self.assertEqual(after['completion_id'],completed['completion_id'])
        self.denied(lambda:self.db.execute('update public.elearning_completion_events set completed_at=now() where id=%s',(completed['completion_id'],)),'42501')
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.elearning_completion_events','INSERT')").fetchone()[0])

    def test_placement_results_cannot_cross_courses_and_limits_are_independent(self):
        original=self.create(required=False);attached=self.create(self.section,required=False,assessment=original['assessment']['id'])
        attempt=self.runtime(original,True)['attempt']['id'];self.submit(original,True,attempt)
        self.assertFalse(self.runtime(attached)['summary']['passed']);self.assertEqual(self.runtime(attached,True)['attempt']['attempt_number'],1)
        self.submit(attached,False);self.submit(attached,False);self.denied(lambda:self.runtime(attached,True),'42501');self.assertTrue(self.runtime(original)['summary']['passed'])
        other=self.db.execute("insert into public.elearning_courses(tenant_id,name,status) values(%s,'Other','published') returning id",(self.tenant,)).fetchone()[0]
        self.denied(lambda:self.runtime(original,course=other));self.denied(lambda:self.create(section=self.section,course=other),'P0002')
        foreign=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Foreign','Other') returning tenant_id").fetchone()[0]
        aid=self.db.execute("insert into public.elearning_assessments(tenant_id,title) values(%s,'Foreign') returning id",(foreign,)).fetchone()[0]
        self.denied(lambda:self.create(assessment=aid),'P0002')
        self.denied(lambda:self.db.execute('select public.create_elearning_placed_assessment(%s,%s,null,%s,1,%s::jsonb,%s::jsonb,null)',(foreign,self.course,self.user,'{}','[]')))
        self.denied(lambda:self.runtime(original,user=self.user))

    def test_group_access_suspension_and_wrong_attempt_ownership(self):
        p=self.create(required=False);group=self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Placement group') returning id",(self.tenant,)).fetchone()[0]
        enrollment=self.snapshot()['progress']['id']
        for action,target,users,kind,entity in [('add_members',None,[self.learner],'group',group),('assign_course',self.course,None,'group',group),('revoke_manual',enrollment,None,'course',self.course)]:self.db.execute('select public.manage_elearning_relationships(%s,%s,%s,%s,%s,%s,%s,true)',(self.tenant,self.user,kind,entity,action,target,users))
        attempt=self.runtime(p,True)['attempt']['id'];self.assertEqual(self.runtime(p)['attempt']['id'],attempt)
        self.denied(lambda:self.db.execute('select public.submit_elearning_assessment_attempt(%s,%s,null,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,p['block_id'],self.user,attempt,'{}')))
        self.db.execute("select public.manage_elearning_enrollments(%s,%s,%s,'suspend',null,%s,'active',null,true)",(self.tenant,self.course,self.user,enrollment));self.denied(lambda:self.runtime(p));self.denied(lambda:self.submit(p,attempt=attempt))

    def test_remove_duplicate_and_draft_publication(self):
        p=self.create(required=False,status='draft');self.denied(lambda:self.runtime(p),'P0002')
        def command(action,confirmed=False):
            revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
            return self.db.execute('select public.manage_elearning_placement(%s,%s,%s,%s,%s,%s,%s)',(self.tenant,self.course,p['block_id'],self.user,revision,action,confirmed)).fetchone()[0]
        duplicate=command('duplicate');self.assertEqual(len(duplicate['placements']),2);self.assertNotEqual(duplicate['placements'][0]['assessment_id'],duplicate['placements'][1]['assessment_id'])
        self.denied(lambda:command('remove',False),'22023');command('remove',True);self.denied(lambda:self.runtime(p),'P0002');command('restore')
        settings={k:p['assessment'][k] for k in ['title','instructions','passing_score','max_attempts','required_for_completion']};settings['status']='published'
        self.db.execute('select public.manage_elearning_assessment(%s,%s,null,%s,%s,%s,%s,null,%s::jsonb)',(self.tenant,self.course,p['block_id'],self.user,p['assessment']['revision'],'settings',json.dumps(settings)))
        self.assertIsNone(self.runtime(p)['attempt'])

    def test_withdrawn_requirement_finalizes_immutable_completion(self):
        final=self.create();self.snapshot(self.lesson,complete=True);self.snapshot(self.second,complete=True);self.assertFalse(self.snapshot()['progress']['completion']['completed'])
        revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
        self.db.execute("select public.manage_elearning_placement(%s,%s,%s,%s,%s,'remove',true)",(self.tenant,self.course,final['block_id'],self.user,revision))
        state=self.snapshot()['progress']['completion'];self.assertTrue(state['completed']);self.assertIsNotNone(state['completed_at']);self.create();self.assertEqual(self.snapshot()['progress']['completion']['completion_id'],state['completion_id'])
