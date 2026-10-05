import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock,patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from services import elearning_relationships_service as service,elearning_access_service as access
from routes import elearning_relationships_routes as routes

class RelationshipRouteTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router);self.http=TestClient(app)
        self.actor=SimpleNamespace(tenant_id=17,user_id=3,role='owner');self.group,self.target=[str(uuid4()) for _ in range(2)]
        self.url='/elearning/relationships/group/'+self.group
        self.db=MagicMock();self.db.rpc.return_value.execute.return_value.data={'entity':{'id':self.group},'members':[]}
        for patcher in [patch.object(access,'require_active_tenant_member',return_value=self.actor),patch.object(service,'service_supabase',self.db),patch.object(service,'settings_available',return_value=True),patch.object(routes,'record_audit_event')]:patcher.start();self.addCleanup(patcher.stop)

    def test_bulk_add_uses_only_active_session_scope(self):
        response=self.http.post(self.url+'/commands',json={'action':'add_members','user_ids':[4,5]})
        self.assertEqual(response.status_code,200)
        name,args=self.db.rpc.call_args_list[0].args
        self.assertEqual(name,'manage_elearning_relationships');self.assertEqual(args['p_tenant_id'],17);self.assertEqual(args['p_actor_id'],3);self.assertEqual(args['p_user_ids'],[4,5])
        self.assertEqual(response.headers['cache-control'],'private, no-store')

    def test_rejects_scope_spoofing_unconfirmed_removal_and_invalid_shapes(self):
        for command in [{'action':'remove_member','user_ids':[4]},{'action':'assign_course','target_id':self.target,'tenant_id':99},{'action':'add_members','user_ids':[True]},{'action':'add_members','user_ids':[4,4]},{'action':'assign_course','user_ids':[4]},{'action':'link_user','user_ids':[4,5]}]:
            self.assertEqual(self.http.post(self.url+'/commands',json=command).status_code,422)
        self.db.rpc.assert_not_called()

    def test_member_role_forbidden_before_sql(self):
        self.actor.role='member';self.assertEqual(self.http.get(self.url).status_code,403);self.db.rpc.assert_not_called()

    def test_sql_failures_and_schema_gate_are_closed(self):
        for code,status in [('P0002',404),('42501',403),('23505',409),('22023',400)]:
            self.db.rpc.return_value.execute.side_effect=APIError({'code':code,'message':'private database detail','details':None,'hint':None})
            response=self.http.get(self.url);self.assertEqual(response.status_code,status);self.assertNotIn('private database detail',response.text)
        service.settings_available.return_value=False;self.db.rpc.reset_mock();self.assertEqual(self.http.get(self.url).status_code,503);self.db.rpc.assert_not_called()

    def test_read_search_and_candidate_pagination_are_bounded(self):
        self.http.get(self.url+'?member_query=Sarah&member_offset=50');self.assertEqual(self.db.rpc.call_args.args[1]['p_member_offset'],50)
        self.db.rpc.return_value.execute.return_value.data=[{'id':1},{'id':2}]
        self.assertEqual(self.http.get('/elearning/relationships/candidates?kind=users&limit=1').json(),{'items':[{'id':1}],'has_more':True})
        self.assertEqual(self.http.get('/elearning/relationships/candidates?kind=users&limit=1000').status_code,422)
