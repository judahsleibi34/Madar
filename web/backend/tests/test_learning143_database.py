"""Real canonical mixed-assessment transactions on a marked disposable DB."""
import json
import unittest
from uuid import uuid4
from test_elearning_placements_database import PlacementDatabaseTests
from test_elearning_content_database import DSN

@unittest.skipUnless(DSN,'Requires marked disposable learning database')
class Learning143DatabaseTests(PlacementDatabaseTests):
    def setUp(self):
        super().setUp()
        version=self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
        if version != 143: self.skipTest('Requires learning-only schema143')

    def mixed(self):
        revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
        details={'title':'Human-reviewed final','instructions':'Answer','passing_score':70,'max_attempts':3,'required_for_completion':True,'status':'published','activity_mode':'graded'}
        questions=[{'type':'true_false','prompt':'The sky is visible?','points':1,'config':{'correct_answer':True}}, {'type':'written','prompt':'Describe your plan.','points':4,'config':{'rubric':'Clarity and relevance','max_characters':1000}}]
        return self.db.execute('select public.create_elearning_placed_assessment(%s,%s,null,%s,%s,%s::jsonb,%s::jsonb,null)',(self.tenant,self.course,self.user,revision,json.dumps(details),json.dumps(questions))).fetchone()[0]

    def pending(self):
        p=self.mixed();self.snapshot(self.lesson,complete=True);self.snapshot(self.second,complete=True)
        attempt=self.runtime(p,True)['attempt']
        answers={q['id']:({'value':True} if q['type']=='true_false' else {'text':'My original answer'}) for q in attempt['questions']}
        result=self.db.execute('select public.submit_elearning_assessment_attempt(%s,%s,null,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,p['block_id'],self.learner,attempt['id'],json.dumps(answers))).fetchone()[0]
        return p,result,answers

    def grade(self,attempt,question,points=4,actor=None,revision=1,feedback='Clear answer'):
        return self.db.execute('select public.review_elearning_answer(%s,%s,%s,%s,%s,%s,%s)',(self.tenant,actor or self.user,attempt,question,revision,points,feedback)).fetchone()[0]

    def test_pending_then_human_result_controls_completion(self):
        p,result,_=self.pending();attempt=result['attempt'];written=next(q for q in attempt['questions'] if q['type']=='written')
        self.assertEqual(attempt['status'],'pending_review');self.assertIsNone(attempt['passed']);self.assertIsNone(attempt['score_percentage'])
        self.assertFalse(self.snapshot()['progress']['completion']['completed'])
        queue=self.db.execute('select public.get_elearning_pending_reviews(%s,%s,1,0)',(self.tenant,self.user)).fetchone()[0]
        self.assertEqual(queue[0]['id'],attempt['id'])
        result=self.grade(attempt['id'],written['id']);self.assertEqual(result['status'],'submitted')
        final=self.runtime(p)['attempt'];self.assertTrue(final['passed']);self.assertEqual(final['score_percentage'],100)
        self.assertTrue(self.snapshot()['progress']['completion']['completed'])

    def test_self_grading_bounds_and_revision_conflicts(self):
        _,result,_=self.pending();attempt=result['attempt'];question=next(q for q in attempt['questions'] if q['type']=='written')
        self.denied(lambda:self.grade(attempt['id'],question['id'],actor=self.learner),'42501')
        self.denied(lambda:self.grade(attempt['id'],question['id'],points=5),'22023')
        self.denied(lambda:self.grade(attempt['id'],question['id'],revision=99),'P0001')
        first=self.grade(attempt['id'],question['id'])
        self.assertEqual(self.grade(attempt['id'],question['id']),first)
        self.denied(lambda:self.grade(attempt['id'],question['id'],points=3),'P0001')
        self.denied(lambda:self.db.execute('update public.elearning_assessment_reviews set points=0 where attempt_id=%s',(attempt['id'],)),'42501')

    def test_duplicate_pending_submission_and_author_edits_preserve_answers(self):
        p,result,_=self.pending();attempt=result['attempt'];question=next(q for q in attempt['questions'] if q['type']=='written')
        duplicate=self.db.execute('select public.submit_elearning_assessment_attempt(%s,%s,null,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,p['block_id'],self.learner,attempt['id'],'{}')).fetchone()[0]
        self.assertEqual(duplicate['attempt']['id'],attempt['id'])
        self.assertEqual(self.runtime(p,True)['attempt']['id'],attempt['id'])
        self.db.execute("update public.elearning_assessment_questions set prompt='Changed',points=1,config='{\"rubric\":\"Changed\",\"max_characters\":1000}' where id=%s",(question['id'],))
        self.grade(attempt['id'],question['id'],4)
        row=self.db.execute('select private_snapshot from public.elearning_assessment_attempts where id=%s',(attempt['id'],)).fetchone()[0]
        old=next(q for q in row['questions'] if q['id']==question['id']);self.assertEqual(old['points'],4);self.assertEqual(old['config']['rubric'],'Clarity and relevance')

    def test_pending_review_queue_is_bounded_and_tenant_scoped(self):
        _,result,_=self.pending()
        self.assertEqual(self.db.execute('select public.get_elearning_pending_reviews(%s,%s,1,1)',(self.tenant,self.user)).fetchone()[0],[])
        self.assertEqual(self.db.execute('select public.get_elearning_pending_reviews(%s,%s,1,0)',(self.tenant,self.learner)).fetchone()[0],[])
        self.denied(lambda:self.db.execute('select public.get_elearning_pending_reviews(%s,%s,101,0)',(self.tenant,self.user)),'22023')
        self.denied(lambda:self.db.execute('select public.get_elearning_review(%s,%s,%s)',(self.tenant+10000,self.user,result['attempt']['id'])),'42501')
    def lesson_activity(self,questions,mode='practice',pool=None):
        revision=self.db.execute('select content_revision from public.elearning_lessons where id=%s',(self.lesson,)).fetchone()[0]
        details={'title':'Reusable activity','instructions':'Listen and respond','passing_score':70,'max_attempts':3,'required_for_completion':True,'status':'published','activity_mode':mode,'pool_size':pool,'shuffle_questions':pool is not None}
        return self.db.execute('select public.create_elearning_assessment(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)',(self.tenant,self.course,self.lesson,self.user,revision,json.dumps(details),json.dumps(questions))).fetchone()[0]

    def lesson_runtime(self,p,start=False):
        return self.db.execute('select public.'+('start_elearning_assessment_attempt' if start else 'elearning_assessment_runtime')+'(%s,%s,%s,%s,%s)',(self.tenant,self.course,self.lesson,p['block_id'],self.learner)).fetchone()[0]

    def lesson_submit(self,p,attempt,answers):
        return self.db.execute('select public.submit_elearning_assessment_attempt(%s,%s,%s,%s,%s,%s,%s::jsonb)',(self.tenant,self.course,self.lesson,p['block_id'],self.learner,attempt,json.dumps(answers))).fetchone()[0]

    def test_speaking_practice_has_no_score_no_recording_and_no_review(self):
        p=self.lesson_activity([{'type':'speaking_practice','prompt':'Introduce yourself','points':1,'config':{'rubric':'','max_duration_seconds':30,'max_size_bytes':100000}}])
        attempt=self.lesson_runtime(p,True)['attempt'];question=attempt['questions'][0]
        result=self.lesson_submit(p,attempt['id'],{question['id']:{'finished':True}})['attempt']
        self.assertEqual(result['status'],'submitted');self.assertIsNone(result['score_percentage']);self.assertIsNone(result['passed'])
        self.assertIsNone(result['feedback'][0]['points']);self.assertIsNone(result['earned_points']);self.assertIsNone(result['total_points']);self.assertIsNone(question['points'])
        self.assertIsNone(self.db.execute('select earned_points from public.elearning_assessment_answers where attempt_id=%s',(attempt['id'],)).fetchone()[0])
        self.assertEqual(self.db.execute('select count(*) from public.elearning_assessment_recordings where attempt_id=%s',(attempt['id'],)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select public.get_elearning_pending_reviews(%s,%s,10,0)',(self.tenant,self.user)).fetchone()[0],[])
        self.assertEqual(self.db.execute('select public.elearning_assessment_results(%s,%s)',(self.tenant,self.snapshot()['progress']['id'])).fetchone()[0],[])
        self.snapshot(self.lesson,complete=True)

    def test_picture_practice_feedback_and_retry_use_frozen_media(self):
        audio=self.media();images=[]
        for alt in ('Blue door','Green door'):
            name=uuid4().hex+'.png'
            image=self.db.execute("insert into public.builder_assets(tenant_id,storage_key,managed_filename,mime_type,size_bytes,sha256) values(%s,%s,%s,'image/png',128,%s) returning id",(self.tenant,f'tenant_{self.tenant}/builder_assets/{name}',name,'a'*64)).fetchone()[0]
            images.append({'id':str(uuid4()),'media_id':str(image),'alt':alt})
        p=self.lesson_activity([{'type':'picture_listen','prompt':'Choose the blue door','points':1,'config':{'media_id':audio,'options':images,'correct_option_id':images[0]['id']}}])
        attempt=self.lesson_runtime(p,True)['attempt'];question=attempt['questions'][0]
        self.assertNotIn('correct_option_id',question['config']);self.assertTrue(question['config']['options'][0]['media']['url'])
        wrong=self.lesson_submit(p,attempt['id'],{question['id']:{'option_id':images[1]['id']}})['attempt']
        self.assertFalse(wrong['feedback'][0]['correct']);self.assertIsNone(wrong['score_percentage'])
        retry=self.lesson_runtime(p,True)['attempt'];self.assertNotEqual(retry['id'],attempt['id'])
        correct=self.lesson_submit(p,retry['id'],{question['id']:{'option_id':images[0]['id']}})['attempt']
        self.assertTrue(correct['feedback'][0]['correct'])

    def test_recording_ownership_limits_and_human_only_finalization(self):
        p=self.lesson_activity([{'type':'speaking','prompt':'Explain a choice','points':2,'config':{'rubric':'Clear explanation','max_duration_seconds':30,'max_size_bytes':100000}}],mode='graded')
        attempt=self.lesson_runtime(p,True)['attempt'];question=attempt['questions'][0];recording=str(uuid4())
        def register(user=None,size=32044,duration=1000,identifier=recording):
            return self.db.execute('select public.register_elearning_recording(%s,%s,%s,%s,%s,%s,%s,%s)',(self.tenant,user or self.learner,attempt['id'],question['id'],identifier,size,duration,'a'*64)).fetchone()[0]
        self.denied(lambda:register(user=self.user),'42501');self.denied(lambda:register(duration=31000),'22023');self.denied(lambda:register(size=100001),'22023')
        first=register();self.assertEqual(register(),first)
        for _ in range(4):register(identifier=str(uuid4()))
        self.denied(lambda:register(identifier=str(uuid4())),'42501')
        self.denied(lambda:self.lesson_submit(p,attempt['id'],{question['id']:{'recording_id':str(uuid4())}}),'22023')
        pending=self.lesson_submit(p,attempt['id'],{question['id']:{'recording_id':recording}})['attempt']
        self.assertEqual(pending['status'],'pending_review');self.assertIsNone(pending['score_percentage'])
        self.grade(attempt['id'],question['id'],points=1)
        final=self.lesson_runtime(p)['attempt'];self.assertEqual(final['score_percentage'],50);self.assertFalse(final['passed'])

    def test_pool_selection_is_server_owned_and_snapshot_is_immutable(self):
        questions=[{'type':'true_false','prompt':f'Original {i}','points':1,'config':{'correct_answer':True}} for i in range(60)]
        p=self.lesson_activity(questions,mode='graded',pool=52);attempt=self.lesson_runtime(p,True)['attempt']
        self.assertEqual(len(attempt['questions']),52)
        self.assertEqual(len({q['id'] for q in attempt['questions']}),52)
        answers={q['id']:{'value':False} for q in attempt['questions']}
        self.lesson_submit(p,attempt['id'],answers)
        retry=self.lesson_runtime(p,True)['attempt'];self.assertEqual(len(retry['questions']),52)
        self.assertNotEqual([q['id'] for q in retry['questions']],[q['id'] for q in attempt['questions']])
        snapshot=self.db.execute('select private_snapshot from public.elearning_assessment_attempts where id=%s',(attempt['id'],)).fetchone()[0]
        self.db.execute("update public.elearning_assessment_questions set prompt='Edited bank' where assessment_id=%s",(p['assessment']['id'],))
        self.assertEqual(self.db.execute('select private_snapshot from public.elearning_assessment_attempts where id=%s',(attempt['id'],)).fetchone()[0],snapshot)
    def test_cleanup_fences_orphan_retries_and_preserves_selected_evidence(self):
        p=self.lesson_activity([{'type':'speaking','prompt':'Explain','points':1,'config':{'rubric':'Clear','max_duration_seconds':30,'max_size_bytes':100000}}],mode='graded')
        attempt=self.lesson_runtime(p,True)['attempt'];qid=attempt['questions'][0]['id']
        identifiers=[str(uuid4()),str(uuid4())]
        for identifier in identifiers:
            key=f'elearning-assessments/tenant_{self.tenant}/attempt_{attempt["id"]}/{identifier}.wav'
            reservation=self.db.execute("select public.reserve_storage_bytes(%s,%s,'elearning_assessment',32044,1000000,1000000)",(self.tenant,self.learner)).fetchone()[0]
            self.db.execute('select public.finish_storage_reservation(%s,true,%s,%s,null)',(reservation,key,'a'*64))
            self.db.execute("update public.storage_objects set created_at=now()-interval '2 days' where storage_key=%s",(key,))
        selected,orphan=identifiers
        self.db.execute('select public.register_elearning_recording(%s,%s,%s,%s,%s,32044,1000,%s)',(self.tenant,self.learner,attempt['id'],qid,selected,'a'*64))
        self.lesson_submit(p,attempt['id'],{qid:{'recording_id':selected}})
        dry=self.db.execute('select public.prepare_elearning_recording_cleanup(100,false)').fetchone()[0]
        self.assertEqual([r['recording_id'] for r in dry],[orphan])
        self.assertEqual(self.db.execute('select count(*) from public.elearning_recording_cleanup').fetchone()[0],0)
        queued=self.db.execute('select public.prepare_elearning_recording_cleanup(100,true)').fetchone()[0]
        self.assertEqual(queued,dry)
        self.db.execute('select public.finish_elearning_recording_cleanup(%s,%s)',(self.tenant,queued[0]['storage_key']))
        self.assertEqual(self.db.execute('select public.prepare_elearning_recording_cleanup(100,true)').fetchone()[0],[])
        self.assertEqual(self.db.execute('select public.get_elearning_recording(%s,%s,%s)',(self.tenant,self.learner,selected)).fetchone()[0]['id'],selected)
        self.assertEqual(self.db.execute("select status from public.storage_objects where storage_key=%s",(queued[0]['storage_key'],)).fetchone()[0],'deleted')
    def test_cefr_uses_owner_configured_threshold_without_global_70_rule(self):
        p=self.create(section=self.section)
        self.db.execute('update public.elearning_assessments set passing_score=65,max_attempts=1 where id=%s',(p['assessment']['id'],))
        template=self.db.execute("insert into public.elearning_certificate_templates(tenant_id,design) values(%s,'{\"name\":\"Sample\",\"title\":\"Sample certificate\",\"issuer_name\":\"Sample academy\"}') returning id",(self.tenant,)).fetchone()[0]
        self.db.execute('select public.configure_elearning_cefr(%s,%s,%s,%s,%s,%s,true)',(self.tenant,self.user,self.course,self.section,'A1',template))
        self.assertTrue(self.db.execute('select enabled from public.elearning_section_certificates where course_id=%s and section_id=%s',(self.course,self.section)).fetchone()[0])
    def assigned_reviewer(self):
        auth=uuid4();email=f'{auth}@example.com'
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(auth,email))
        user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Reviewer','Test',%s,%s,'active',true) returning id",(auth,email,self.tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'member','active')",(self.tenant,user,auth))
        instructor=self.db.execute("insert into public.elearning_instructors(tenant_id,user_id,name,email) values(%s,%s,'Assigned reviewer',%s) returning id",(self.tenant,user,email)).fetchone()[0]
        self.db.execute('insert into public.elearning_course_instructors(tenant_id,course_id,instructor_id) values(%s,%s,%s)',(self.tenant,self.course,instructor))
        return user,instructor

    def test_assignment_and_status_revocation_recheck_before_grading(self):
        _,result,_=self.pending();attempt=result['attempt'];q=next(q for q in attempt['questions'] if q['type']=='written')
        user,instructor=self.assigned_reviewer()
        self.assertEqual(len(self.db.execute('select public.get_elearning_pending_reviews(%s,%s,50,0)',(self.tenant,user)).fetchone()[0]),1)
        self.db.execute('delete from public.elearning_course_instructors where instructor_id=%s',(instructor,))
        self.denied(lambda:self.grade(attempt['id'],q['id'],actor=user),'42501')
        self.db.execute('insert into public.elearning_course_instructors(tenant_id,course_id,instructor_id) values(%s,%s,%s)',(self.tenant,self.course,instructor))
        self.db.execute("update public.elearning_instructors set status='archived' where id=%s",(instructor,))
        self.denied(lambda:self.grade(attempt['id'],q['id'],actor=user),'42501')
        self.db.execute("update public.elearning_instructors set status='active' where id=%s",(instructor,))
        self.assertEqual(self.grade(attempt['id'],q['id'],actor=user)['status'],'submitted')

    def test_historical_human_grade_does_not_issue_completion_after_access_revocation(self):
        _,result,_=self.pending();attempt=result['attempt'];q=next(q for q in attempt['questions'] if q['type']=='written')
        self.db.execute("update public.elearning_enrollments set status='suspended' where id=(select enrollment_id from public.elearning_assessment_attempts where id=%s)",(attempt['id'],))
        self.grade(attempt['id'],q['id'])
        self.assertEqual(self.db.execute('select status from public.elearning_assessment_attempts where id=%s',(attempt['id'],)).fetchone()[0],'submitted')
        self.assertEqual(self.db.execute("select count(*) from public.elearning_completion_events where course_id=%s and scope='course'",(self.course,)).fetchone()[0],0)
    def test_attempt_and_answer_evidence_cannot_be_rewritten(self):
        _,result,_=self.pending();attempt=result['attempt'];question=next(q for q in attempt['questions'] if q['type']=='written')
        self.denied(lambda:self.db.execute("update public.elearning_assessment_attempts set private_snapshot='{}' where id=%s",(attempt['id'],)),'42501')
        self.denied(lambda:self.db.execute("update public.elearning_assessment_answers set response='{\"text\":\"Forged\"}' where attempt_id=%s and question_id=%s",(attempt['id'],question['id'])),'42501')
        self.grade(attempt['id'],question['id'])
        self.denied(lambda:self.db.execute('update public.elearning_assessment_attempts set score_percentage=0,passed=false where id=%s',(attempt['id'],)),'42501')
        self.denied(lambda:self.db.execute('update public.elearning_assessment_answers set earned_points=0 where attempt_id=%s and question_id=%s',(attempt['id'],question['id'])),'42501')
    def test_practice_cannot_be_created_or_attached_as_a_formal_exam(self):
        revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
        details={'title':'Practice','instructions':'Practice','passing_score':70,'required_for_completion':True,'status':'published','activity_mode':'practice'}
        questions=[{'type':'true_false','prompt':'Practice?','points':1,'config':{'correct_answer':True}}]
        self.denied(lambda:self.db.execute('select public.create_elearning_placed_assessment(%s,%s,null,%s,%s,%s::jsonb,%s::jsonb,null)',(self.tenant,self.course,self.user,revision,json.dumps(details),json.dumps(questions))),'22023')
        practice=self.lesson_activity(questions)
        revision=self.db.execute('select structure_revision from public.elearning_courses where id=%s',(self.course,)).fetchone()[0]
        self.denied(lambda:self.db.execute('select public.create_elearning_placed_assessment(%s,%s,null,%s,%s,%s::jsonb,null,%s)',(self.tenant,self.course,self.user,revision,json.dumps({'required_for_completion':True}),practice['assessment']['id'])),'22023')

    def test_reviewers_cannot_read_private_drafts_or_unused_takes(self):
        p=self.lesson_activity([{'type':'speaking','prompt':'Explain','points':1,'config':{'rubric':'Clear','max_duration_seconds':30,'max_size_bytes':100000}}],mode='graded')
        attempt=self.lesson_runtime(p,True)['attempt'];qid=attempt['questions'][0]['id'];recordings=[str(uuid4()),str(uuid4())]
        for identifier in recordings:self.db.execute('select public.register_elearning_recording(%s,%s,%s,%s,%s,32044,1000,%s)',(self.tenant,self.learner,attempt['id'],qid,identifier,'a'*64))
        self.denied(lambda:self.db.execute('select public.get_elearning_review(%s,%s,%s)',(self.tenant,self.user,attempt['id'])),'42501')
        self.denied(lambda:self.db.execute('select public.get_elearning_recording(%s,%s,%s)',(self.tenant,self.user,recordings[0])),'42501')
        self.assertEqual(self.db.execute('select public.get_elearning_recording(%s,%s,%s)',(self.tenant,self.learner,recordings[0])).fetchone()[0]['id'],recordings[0])
        self.lesson_submit(p,attempt['id'],{qid:{'recording_id':recordings[1]}})
        self.denied(lambda:self.db.execute('select public.get_elearning_recording(%s,%s,%s)',(self.tenant,self.user,recordings[0])),'42501')
        self.assertEqual(self.db.execute('select public.get_elearning_recording(%s,%s,%s)',(self.tenant,self.user,recordings[1])).fetchone()[0]['id'],recordings[1])
