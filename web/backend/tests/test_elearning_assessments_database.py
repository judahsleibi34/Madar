"""Assessment SQL integrity tests against a marked disposable local database."""
import json
import unittest
from uuid import uuid4
import psycopg
from test_elearning_player_database import ELearningPlayerDatabaseTests as Player
from test_elearning_content_database import DSN


@unittest.skipUnless(DSN, 'Requires marked disposable learning database')
class AssessmentDatabaseTests(unittest.TestCase):
    setUpClass = Player.__dict__['setUpClass']
    setUp = Player.setUp
    command = Player.command
    media = Player.media
    snapshot = Player.snapshot

    def questions(self):
        options=[{'id':str(uuid4()),'label':v} for v in ['One','Two']]
        result=[{'type':'multiple_choice','prompt':'Choose one','points':1,'config':{'options':options,'correct_option_id':options[0]['id']}}, {'type':'true_false','prompt':'True?','points':1,'config':{'correct_answer':True}}]
        for typ in ['matching','listen_match']:
            targets=[{'id':str(uuid4()),'label':v} for v in ['Hello','Goodbye','Thanks','Welcome']]
            prompts=[{'id':str(uuid4()),**({'label':v['label']} if typ=='matching' else {'media_id':self.media(),'admin_label':'HIDDEN ANSWER LABEL'})} for v in targets]
            result.append({'type':typ,'prompt':typ,'points':1,'config':{'prompts':prompts,'targets':targets,'correct_pairs':{p['id']:t['id'] for p,t in zip(prompts,targets)}}})
        return result

    def create(self, questions=None, **settings):
        value={'title':'Practice Check','instructions':'Answer all questions','passing_score':70,'max_attempts':3,'required_for_completion':True,'status':'published',**settings}
        revision=self.db.execute('select content_revision from public.elearning_lessons where id=%s',(self.lesson,)).fetchone()[0]
        self.author=self.db.execute('select public.create_elearning_assessment(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',(self.tenant,self.course,self.lesson,self.user,revision,json.dumps(value),json.dumps(self.questions() if questions is None else questions))).fetchone()[0]
        self.block=self.author['block_id'];self.aid=self.author['assessment']['id'];return self.author

    def manage(self, action, question=None, payload=None):
        result=self.db.execute('select public.manage_elearning_assessment(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,self.lesson,self.block,self.user,self.author['assessment']['revision'],action,question,json.dumps(payload or {}))).fetchone()[0]
        self.author=result;return result

    def runtime(self, start=False, **overrides):
        args={'tenant':self.tenant,'course':self.course,'lesson':self.lesson,'block':self.block,'user':self.learner,**overrides}
        function='start_elearning_assessment_attempt' if start else 'elearning_assessment_runtime'
        return self.db.execute(f'select public.{function}(%s,%s,%s,%s,%s)',tuple(args.values())).fetchone()[0]

    def answers(self, wrong=False, partial=False):
        answers={}
        for q in self.author['questions']:
            if q.get('archived_at'):continue
            cfg=q['config']
            if q['type']=='multiple_choice': response={'option_id':cfg['options'][1 if wrong else 0]['id']}
            elif q['type']=='true_false': response={'value':not cfg['correct_answer'] if wrong else cfg['correct_answer']}
            else:
                pairs=cfg['correct_pairs'].copy();ids=list(pairs);targets=list(pairs.values())
                if wrong: pairs={key:targets[(i+1)%len(targets)] for i,key in enumerate(ids)}
                elif partial: pairs[ids[0]],pairs[ids[1]]=pairs[ids[1]],pairs[ids[0]]
                response={'matches':pairs}
            answers[q['id']]=response
        return answers

    def submit(self, attempt, answers, user=None):
        return self.db.execute('select public.submit_elearning_assessment_attempt(%s,%s,%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,self.lesson,self.block,user or self.learner,attempt,json.dumps(answers))).fetchone()[0]

    def expect_error(self, callback, code=None):
        with self.db.transaction(force_rollback=True):
            with self.assertRaises(psycopg.Error) as caught: callback()
            if code:self.assertEqual(caught.exception.sqlstate,code)

    def safe(self, value):
        payload=json.dumps(value)
        for key in ['correct_option_id','correct_answer','correct_pairs','admin_label','HIDDEN ANSWER LABEL','private_snapshot','grading_key','is_correct']:self.assertNotIn(key,payload)

    def test_four_types_scoring_partial_history_idempotence_and_report(self):
        self.create();self.safe(self.runtime())
        started=self.runtime(True);self.safe(started);attempt=started['attempt']['id'];answers=self.answers(partial=True)
        # Editing definitions after start must not change grading or presented order.
        q=self.author['questions'][0];changed={k:q[k] for k in ['type','prompt','points','config']};changed['points']=99
        self.manage('update_question',q['id'],changed)
        self.manage('settings',payload={'title':'Changed','instructions':'New','passing_score':99,'max_attempts':3,'required_for_completion':True,'status':'published'})
        result=self.submit(attempt,answers);self.safe(result);self.assertEqual(result['attempt']['score_percentage'],75);self.assertTrue(result['attempt']['passed']);self.assertEqual(result['attempt']['total_points'],4)
        repeat=self.submit(attempt,self.answers(wrong=True));self.assertEqual(repeat['attempt']['score_percentage'],75)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_assessment_answers where attempt_id=%s',(attempt,)).fetchone()[0],4)
        self.assertFalse(self.snapshot(self.lesson)['lesson']['completed'])
        self.assertTrue(self.snapshot(self.lesson,complete=True)['lesson']['completed'])
        report=self.db.execute('select public.get_elearning_progress_records(%s,%s,true)',(self.tenant,self.course)).fetchone()[0]
        results=next(v for v in report['enrollments'] if v['user_id']==self.learner)['assessment_results'];self.assertEqual(results[0]['best_score'],75);self.assertTrue(results[0]['passed'])

    def test_fail_retry_limits_best_and_completion_gate(self):
        self.create();self.expect_error(lambda:self.snapshot(self.lesson,complete=True),'42501')
        for i in range(3):
            attempt=self.runtime(True)['attempt'];self.assertEqual(attempt['attempt_number'],i+1)
            result=self.submit(attempt['id'],self.answers(wrong=i!=1));self.assertEqual(result['attempt']['score_percentage'],0 if i!=1 else 100)
            self.safe(result)
        self.expect_error(lambda:self.runtime(True),'42501')
        self.assertTrue(self.runtime()['summary']['passed']);self.assertEqual(self.runtime()['summary']['best_score'],100)
        self.assertEqual(self.snapshot(self.lesson,complete=True)['progress']['completed_lessons'],1)

    def test_optional_multiple_required_and_preserve_existing_completion(self):
        self.create(required_for_completion=False);self.snapshot(self.lesson,complete=True)
        self.create();self.assertTrue(self.snapshot(self.lesson,complete=True)['lesson']['completed'])
        self.db.execute('delete from public.elearning_lesson_completions where enrollment_id in (select id from public.elearning_enrollments where learner_id in (select id from public.elearning_learners where user_id=%s))',(self.learner,))
        self.create();attempt=self.runtime(True)['attempt']['id'];self.submit(attempt,self.answers());self.expect_error(lambda:self.snapshot(self.lesson,complete=True),'42501')

    def test_crud_order_archive_duplicate_delete_and_publication(self):
        self.create(status='draft');self.expect_error(lambda:self.runtime(),'P0002')
        q=self.author['questions'][0];self.manage('duplicate_question',q['id']);self.assertEqual(len(self.author['questions']),5)
        duplicate=self.author['questions'][1];self.manage('reorder_question',duplicate['id'],{'direction':'up'});self.assertEqual(self.author['questions'][0]['id'],duplicate['id'])
        self.manage('archive_question',duplicate['id'],{'confirmed':True});self.assertIsNotNone(self.author['questions'][-1]['archived_at'])
        self.manage('restore_question',duplicate['id']);self.manage('delete_question',duplicate['id'],{'confirmed':True});self.assertEqual(len(self.author['questions']),4)
        self.manage('create_question',payload={'type':'true_false','prompt':'New','points':2,'config':{'correct_answer':False}})
        self.expect_error(lambda:self.manage('delete_question',q['id'],{'confirmed':False}),'22023')
        self.expect_error(lambda:self.create(questions=[]),'22023')
        bad=self.questions();bad[0]['config']['correct_option_id']=str(uuid4());self.expect_error(lambda:self.create(bad),'22023')
        bad=self.questions();bad[-1]['config']['prompts'][0]['media_id']=self.media('video');self.expect_error(lambda:self.create(bad),'22023')
        self.manage('delete_assessment',payload={'confirmed':True});self.assertTrue(self.author['deleted'])

    def test_access_relationships_suspension_ownership_and_private_permissions(self):
        self.create();attempt=self.runtime(True)['attempt']['id']
        for overrides in [{'tenant':self.tenant+10000},{'course':str(uuid4())},{'lesson':str(self.second)},{'block':str(uuid4())},{'user':self.user}]:self.expect_error(lambda:self.runtime(**overrides))
        self.expect_error(lambda:self.submit(attempt,self.answers(),self.user))
        self.db.execute("update public.elearning_enrollments set status='suspended' where learner_id in (select id from public.elearning_learners where user_id=%s)",(self.learner,));self.expect_error(lambda:self.runtime());self.expect_error(lambda:self.submit(attempt,self.answers()))
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.elearning_assessment_attempts','SELECT')").fetchone()[0])
        self.assertFalse(self.db.execute("select has_function_privilege('service_role','public.elearning_safe_question(integer,jsonb)','EXECUTE')").fetchone()[0])

    def test_group_access_media_retention_and_instructor_has_no_authority(self):
        self.create();group=self.db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Assessment cohort') returning id",(self.tenant,)).fetchone()[0]
        def relate(action, target=None, users=None, kind='group', entity=None):
            return self.db.execute('select public.manage_elearning_relationships(%s,%s,%s,%s,%s,%s,%s,true)',(self.tenant,self.user,kind,entity or group,action,target,users)).fetchone()[0]
        relate('add_members',users=[self.learner]);relate('assign_course',target=self.course)
        enrollment=self.snapshot()['progress']['id'];relate('revoke_manual',enrollment,kind='course',entity=self.course)
        self.assertEqual([v['type'] for v in self.db.execute('select public.elearning_valid_grants(%s,%s)',(self.tenant,enrollment)).fetchone()[0]],['group'])
        attempt=self.runtime(True)['attempt']['id'];self.submit(attempt,self.answers());self.assertTrue(self.snapshot(self.lesson,complete=True)['lesson']['completed'])
        listening=next(q for q in self.author['questions'] if q['type']=='listen_match');media=list({p['media_id'] for p in listening['config']['prompts']})
        for mid in media:
            key=self.db.execute('select storage_key from public.builder_assets where id=%s',(mid,)).fetchone()[0]
            self.assertTrue(self.db.execute('select public.elearning_learner_media_access(%s,%s,%s)',(self.tenant,self.learner,key)).fetchone()[0])
        self.manage('delete_question',listening['id'],{'confirmed':True})
        for mid in media:self.assertGreater(self.db.execute('select count(*) from public.elearning_assessment_media_refs where media_id=%s and attempt_id=%s',(mid,attempt)).fetchone()[0],0)
        # Course instructor assignment does not confer owner/admin authoring capability.
        instructor=self.db.execute("insert into public.elearning_instructors(tenant_id,name,user_id) values(%s,'Learner instructor',%s) returning id",(self.tenant,self.learner)).fetchone()[0]
        relate('assign_instructor',target=instructor,kind='course',entity=self.course)
        self.expect_error(lambda:self.db.execute('select public.manage_elearning_assessment(%s,%s,%s,%s,%s,%s,%s,null,%s::jsonb)',(self.tenant,self.course,self.lesson,self.block,self.learner,self.author['assessment']['revision'],'settings',json.dumps({'title':'Unauthorized','status':'draft','passing_score':70,'max_attempts':3,'required_for_completion':True}))), '42501')
        relate('remove_member',users=[self.learner]);self.expect_error(lambda:self.runtime())

    def test_matching_partial_exact_points_and_invalid_tenant_audio(self):
        questions=self.questions();match=questions[2];match['points']=3
        self.create([match],passing_score=51);attempt=self.runtime(True)['attempt']['id'];response=self.answers(partial=True);result=self.submit(attempt,response)
        self.assertEqual(result['attempt']['earned_points'],1.5);self.assertEqual(result['attempt']['score_percentage'],50);self.assertFalse(result['attempt']['passed'])
        foreign=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Other assessment tenant','Other') returning tenant_id").fetchone()[0]
        audio=questions[-1];audio['config']['prompts'][0]['media_id']=self.media(tenant=foreign)
        self.expect_error(lambda:self.create([audio]),'22023')

    def test_start_resume_response_validation_and_stale_author_conflicts(self):
        self.create();attempt=self.runtime(True)['attempt'];self.assertEqual(self.runtime(True)['attempt']['id'],attempt['id'])
        self.expect_error(lambda:self.submit(attempt['id'],{}),'22023')
        q=self.author['questions'][0];answers=self.answers();answers[q['id']]={'option_id':str(uuid4())};self.expect_error(lambda:self.submit(attempt['id'],answers),'22023')
        self.expect_error(lambda:self.submit(str(uuid4()),self.answers()),'P0002')
        self.expect_error(lambda:self.db.execute('select public.manage_elearning_assessment(%s,%s,%s,%s,%s,999,%s,%s,%s::jsonb)',(self.tenant,self.course,self.lesson,self.block,self.user,'duplicate_question',q['id'],'{}')), 'P0001')
