import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from services import elearning_participation_service as service, elearning_access_service as access
from routes import elearning_participation_routes as routes


class ParticipationAPITests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router);self.http=TestClient(app)
        self.db=MagicMock();self.course,self.learner,self.enrollment,self.lesson=map(str,[uuid4(),uuid4(),uuid4(),uuid4()])
        self.member=SimpleNamespace(tenant_id=17,user_id=3,role='owner')
        for item in (patch.object(access,'require_active_tenant_member',return_value=self.member),patch.object(service,'service_supabase',self.db),patch.object(service,'participation_available',return_value=True),patch.object(routes,'record_audit_event')):
            item.start();self.addCleanup(item.stop)
        self.db.rpc.return_value.execute.return_value.data={'enrollment_id':self.enrollment}

    def test_enrollment_and_completion_inject_scoped_session_identity(self):
        result=self.http.post(f'/elearning/courses/{self.course}/enrollments',json={'learner_id':self.learner,'access_source':'manual'})
        self.assertEqual(result.status_code,200)
        self.db.rpc.assert_called_with('manage_elearning_participation',{'p_tenant_id':17,'p_course_id':self.course,'p_user_id':3,'p_action':'enroll','p_payload':{'learner_id':self.learner,'access_source':'manual'}})
        url=f'/elearning/courses/{self.course}/enrollments/{self.enrollment}/lessons/{self.lesson}/completion'
        self.assertEqual(self.http.put(url,json={'completed':True}).status_code,200)
        self.assertEqual(self.db.rpc.call_args.args[1]['p_action'],'complete_lesson')
        self.assertEqual(self.http.put(url,json={'completed':False}).status_code,200)
        self.assertEqual(self.db.rpc.call_args.args[1]['p_action'],'uncomplete_lesson')
        self.assertEqual(self.http.put(url,json={'completed':1}).status_code,422)

    def test_schema_gate_and_roles(self):
        with patch.object(service,'participation_available',return_value=False):
            self.assertEqual(self.http.get('/elearning/learners').json(),{'available':False,'learners':[],'has_more':False})
            self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/progress').status_code,503)
            self.assertEqual(self.http.post('/elearning/learners',json={'name':'Test','email':'test@example.invalid'}).status_code,503)
            self.db.table.assert_not_called();self.db.rpc.assert_not_called()
        for role in ('member','viewer','instructor'):
            self.member.role=role
            self.assertEqual(self.http.get('/elearning/learners').status_code,403)
            self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/progress').status_code,403)

    def test_invalid_identity_overrides_and_payments_rejected(self):
        for extra in ({'tenant_id':18},{'user_id':1},{'access_source':'paid'},{'access_source':'pending'}):
            self.assertEqual(self.http.post(f'/elearning/courses/{self.course}/enrollments',json={'learner_id':self.learner,**extra}).status_code,422)
        for email in ('no-at','a@@b','a @b'):
            self.assertEqual(self.http.post('/elearning/learners',json={'name':'Test','email':email}).status_code,422)
        self.db.rpc.assert_not_called()

    def test_sql_errors_redacted_and_read_scope(self):
        self.http.get(f'/elearning/courses/{self.course}/progress')
        self.db.rpc.assert_called_with('get_elearning_progress',{'p_tenant_id':17,'p_course_id':self.course})
        for code,status in [('P0002',404),('42501',403),('22023',400),('XX000',503)]:
            self.db.rpc.return_value.execute.side_effect=APIError({'code':code,'message':'internal SQL secret','details':None,'hint':None})
            result=self.http.get(f'/elearning/courses/{self.course}/progress')
            self.assertEqual(result.status_code,status);self.assertNotIn('internal SQL secret',result.text)


class EnrollmentManagementAPITests(ParticipationAPITests):
    def setUp(self):
        super().setUp()
        patcher=patch.object(service,'settings_available',return_value=True);patcher.start();self.addCleanup(patcher.stop)

    def test_user_enrollment_identity_and_payload_validation(self):
        url=f'/elearning/courses/{self.course}/enrollments/users'
        self.assertEqual(self.http.post(url,json={'user_ids':[3,4],'access_source':'manual'}).status_code,200)
        args=self.db.rpc.call_args.args[1]
        self.assertEqual(args['p_tenant_id'],17);self.assertEqual(args['p_actor_id'],3);self.assertEqual(args['p_user_ids'],[3,4])
        for payload in ({'user_ids':[3,3]},{'user_ids':['3']},{'user_ids':[True]},{'user_ids':[]},{'user_ids':[3],'tenant_id':18},{'user_ids':[3],'access_source':'purchase'}):
            self.assertEqual(self.http.post(url,json=payload).status_code,422)

    def test_enrollment_read_status_scope_and_upgrade_gate(self):
        self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/enrollments').status_code,200)
        self.db.rpc.assert_called_with('get_elearning_enrollment_report',{'p_tenant_id':17,'p_course_id':self.course})
        self.db.rpc.return_value.execute.return_value.data=[]
        self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/enrollment-candidates?query=test&limit=20').status_code,200)
        self.db.rpc.assert_called_with('get_elearning_enrollment_candidates',{'p_tenant_id':17,'p_course_id':self.course,'p_query':'test','p_limit':20,'p_offset':0})
        url=f'/elearning/courses/{self.course}/enrollments/{self.enrollment}/status'
        self.assertEqual(self.http.post(url,json={'action':'suspend','expected_status':'active','confirmed':True}).status_code,200)
        args=self.db.rpc.call_args.args[1];self.assertEqual(args['p_enrollment_id'],self.enrollment);self.assertEqual(args['p_expected_status'],'active')
        self.assertEqual(self.http.post(url,json={'action':'cancel','expected_status':'active','confirmed':False}).status_code,400)
        with patch.object(service,'settings_available',return_value=False):
            self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/enrollments').status_code,503)
            self.assertEqual(self.http.post(url,json={'action':'reactivate','expected_status':'suspended'}).status_code,503)
        self.member.role='member'
        self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/enrollments').status_code,403)
        self.assertEqual(self.http.post(url,json={'action':'reactivate','expected_status':'suspended'}).status_code,403)
