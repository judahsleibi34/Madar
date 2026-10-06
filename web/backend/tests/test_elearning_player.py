import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from routes import elearning_player_routes as routes
from services import elearning_player_service as service


class ELearningPlayerTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router);self.http=TestClient(app)
        self.actor=SimpleNamespace(tenant_id=17,user_id=3,role='member')
        self.db=MagicMock();self.db.rpc.return_value.execute.return_value.data={'progress':{'progress_percent':50}}
        self.course,self.lesson=[str(uuid4()) for _ in range(2)]
        self.url=f'/elearning/my-learning/courses/{self.course}/lessons/{self.lesson}'
        for patcher in [patch.object(routes,'require_active_tenant_member',return_value=self.actor),patch.object(service,'service_supabase',self.db),patch.object(service,'settings_available',return_value=True),patch.object(service,'get_settings',return_value={}),patch.object(routes,'record_audit_event')]:
            patcher.start();self.addCleanup(patcher.stop)

    def test_member_read_uses_only_session_scope_and_never_completes(self):
        response=self.http.get(self.url+'?tenant_id=999&user_id=999')
        self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'private, no-store')
        self.db.rpc.assert_called_once_with('get_elearning_learner_course',{'p_tenant_id':17,'p_user_id':3,'p_course_id':self.course,'p_lesson_id':self.lesson})

    def test_completion_is_explicit_and_scoped(self):
        self.assertEqual(self.http.post(self.url+'/completion').status_code,200)
        self.assertEqual(self.db.rpc.call_args.args[0],'complete_elearning_learner_lesson')
        self.assertEqual(self.db.rpc.call_args.args[1]['p_user_id'],3)

    def test_not_found_lock_and_upgrade_fail_closed(self):
        for code,status,message in [('P0002',404,'missing'),('42501',403,'elearning_lesson_locked')]:
            self.db.rpc.return_value.execute.side_effect=APIError({'code':code,'message':message,'details':None,'hint':None})
            self.assertEqual(self.http.get(self.url).status_code,status)
        service.settings_available.return_value=False;self.db.rpc.reset_mock()
        self.assertEqual(self.http.get(self.url).status_code,503);self.db.rpc.assert_not_called()

    def test_list_pagination_and_typed_ids(self):
        self.db.rpc.return_value.execute.return_value.data=[{'course':{'id':'a'}},{'course':{'id':'b'}}]
        self.assertEqual(self.http.get('/elearning/my-learning?limit=1').json(),{'courses':[{'course':{'id':'a'}}],'has_more':True,'settings':{}})
        self.assertEqual(self.http.get('/elearning/my-learning?limit=1000').status_code,422)
        self.assertEqual(self.http.get('/elearning/my-learning/courses/not-a-uuid').status_code,422)

    def test_learning_media_denial_and_nonlearning_rules(self):
        for result,allowed in [(True,True),(False,False),(None,True)]:
            self.db.rpc.return_value.execute.return_value.data=result
            self.assertEqual(service.media_access(17,3,'key'),allowed)
        self.db.rpc.return_value.execute.return_value.data={}
        with self.assertRaises(ValueError):service.media_access(17,3,'key')
