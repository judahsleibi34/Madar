import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from services import elearning_content_service as service, elearning_access_service as access
from routes import elearning_content_routes as routes


class ELearningContentTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(routes.router)
        self.http = TestClient(app)
        self.course, self.lesson, self.block, self.media = [str(uuid4()) for _ in range(4)]
        self.base = f'/elearning/courses/{self.course}/lessons/{self.lesson}/content'
        self.member = SimpleNamespace(tenant_id=17, user_id=3, role='owner')
        self.db = MagicMock(); self.snapshot = {'revision': 2, 'blocks': [], 'editable': True}
        self.db.rpc.return_value.execute.return_value.data = self.snapshot
        for item in (patch.object(access, 'require_active_tenant_member', return_value=self.member), patch.object(service, 'service_supabase', self.db), patch.object(service, 'settings_available', return_value=True), patch.object(routes, 'record_audit_event')):
            item.start(); self.addCleanup(item.stop)

    def command(self, **values):
        return self.http.post(self.base+'/commands', json={'action':'create','expected_revision':1,'payload':{'type':'text','content':{'body':'Welcome'}}, **values})

    def test_create_all_types_uses_session_identity_and_typed_content(self):
        for kind in ('text','audio','video'):
            payload = {'type':kind,'content':{'body':'Welcome'}} if kind=='text' else {'type':kind,'media_id':self.media}
            self.assertEqual(self.command(payload=payload).json(), self.snapshot)
            name, args = self.db.rpc.call_args.args
            self.assertEqual(name,'manage_elearning_content')
            self.assertEqual((args['p_tenant_id'],args['p_user_id'],args['p_course_id'],args['p_lesson_id']),(17,3,self.course,self.lesson))
            self.assertEqual(args['p_payload']['content']['version'],1)

    def test_rejects_invalid_types_unsafe_text_and_client_scope(self):
        cases = [{'tenant_id':9},{'expected_revision':True},{'payload':{'type':'quiz','content':{}}},{'payload':{'type':'text','content':{'body':' '}}},{'payload':{'type':'text','content':{'body':'hello','html':'<script>'}}},{'payload':{'type':'text','content':{'body':'hello','formats':['iframe']}}},{'payload':{'type':'text','content':{'body':'hello','formats':['p','p']}}},{'payload':{'type':'text','content':{'body':'hello','ranges':[{'start':0,'end':50}]}}},{'payload':{'type':'audio','media_id':'not-a-uuid'}},{'payload':{'type':'video','media_id':self.media,'url':'https://example.com'}},{'payload':{'type':'text','content':{'body':'hello'},'position':1}},{'action':'archive','entity_id':self.block,'payload':{'confirmed':False}},{'action':'delete','entity_id':self.block,'payload':{'confirmed':1}},{'action':'reorder','entity_id':self.block,'payload':{'direction':'sideways'}}]
        for values in cases:
            with self.subTest(values=values): self.assertEqual(self.command(**values).status_code,422)
        self.db.rpc.assert_not_called()

    def test_read_permissions_and_database_bridge_fail_closed(self):
        self.assertEqual(self.http.get(self.base).json(),self.snapshot)
        self.db.rpc.assert_called_with('get_elearning_content',{'p_tenant_id':17,'p_course_id':self.course,'p_lesson_id':self.lesson})
        for role in ('member','viewer','instructor'):
            self.member.role=role
            self.assertEqual(self.command().status_code,403)
            self.assertEqual(self.http.get(self.base).status_code,403)
        self.member.role='owner';self.db.reset_mock()
        with patch.object(service,'settings_available',return_value=False):
            self.assertEqual(self.command().status_code,503)
            self.assertEqual(self.http.get(self.base).status_code,503)
            self.db.rpc.assert_not_called()
        with patch.object(access,'require_active_tenant_member',side_effect=HTTPException(401)):
            self.assertEqual(self.command().status_code,401)

    def test_sql_security_errors_and_conflicts_are_safe(self):
        for code,message,status in [('22023','elearning_content_invalid_media',400),('42501','forbidden',403),('P0002','missing',404),('P0001','elearning_content_conflict',409),('P0001','elearning_content_parent_archived',409),('XX000','database secret',503)]:
            self.db.rpc.return_value.execute.side_effect=APIError({'code':code,'message':message,'details':None,'hint':None})
            result=self.command();self.assertEqual(result.status_code,status);self.assertNotIn('database secret',result.text)
        self.db.rpc.return_value.execute.side_effect=None;self.db.rpc.return_value.execute.return_value.data=None
        self.assertEqual(self.http.get(self.base).status_code,404)

    def test_text_offsets_preserve_whitespace_and_unicode(self):
        payload={'type':'text','content':{'body':'\n😀 Test\n','formats':['p','h2','p'],'ranges':[{'start':1,'end':3,'fontWeight':'700'}]}}
        self.assertEqual(self.command(payload=payload).status_code,200)
        self.assertEqual(self.db.rpc.call_args.args[1]['p_payload']['content']['body'],'\n😀 Test\n')
