import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from routes import elearning_academy_routes as routes
from services import elearning_academy_service as service
from services.elearning_settings_service import ELearningSettings


class AcademyRoutesTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router);self.client=TestClient(app)
        self.website={'tenant_id':17,'subdomain':'tenant'}
        for name in ['enforce_public_rate_limit','resolve_website_settings']:
            mock=patch.object(routes,name,return_value=self.website if name=='resolve_website_settings' else None);mock.start();self.addCleanup(mock.stop)

    def test_guest_uses_null_actor_and_private_cache_headers(self):
        with patch.object(routes,'require_active_tenant_member',side_effect=HTTPException(401)),patch.object(service,'storefront',return_value={'courses':[]}) as call:
            result=self.client.get('/public/academies/tenant')
        self.assertEqual(result.status_code,200);self.assertEqual(result.headers['cache-control'],'private, no-store');self.assertEqual(result.headers['vary'],'Cookie')
        self.assertIsNone(call.call_args.args[2]);self.assertEqual(call.call_args.args[0],17)

    def test_foreign_session_cannot_personalize_tenant(self):
        actor=SimpleNamespace(tenant_id=88,user_id=9)
        with patch.object(routes,'require_active_tenant_member',return_value=actor),patch.object(service,'storefront',return_value={}) as call:
            self.client.get('/public/academies/tenant')
        self.assertIsNone(call.call_args.args[2])

    def test_own_session_and_course_relationship_pass_to_authority(self):
        actor=SimpleNamespace(tenant_id=17,user_id=9)
        with patch.object(routes,'require_active_tenant_member',return_value=actor),patch.object(service,'storefront',side_effect=HTTPException(404)) as call:
            result=self.client.get('/public/academies/tenant/courses/11111111-1111-1111-1111-111111111111')
        self.assertEqual(result.status_code,404);self.assertIs(call.call_args.args[2],actor)

    def test_identity_resolution_failures_are_not_downgraded_to_guests(self):
        with patch.object(routes,'resolve_website_settings',side_effect=HTTPException(404)),patch.object(service,'storefront') as call:
            self.assertEqual(self.client.get('/public/academies/foreign').status_code,404)
        call.assert_not_called()

    def test_server_errors_do_not_downgrade_to_guest(self):
        with patch.object(routes,'require_active_tenant_member',side_effect=HTTPException(503)),patch.object(service,'storefront') as call:
            self.assertEqual(self.client.get('/public/academies/tenant').status_code,503)
        call.assert_not_called()


class AcademyModelsTests(unittest.TestCase):
    def test_configuration_is_bounded_plain_content_not_layout(self):
        for payload in [{'academy_css':'*{}'},{'academy_hero_title':'x'*161},{'academy_featured_courses':['invalid']}]:
            with self.assertRaises(ValidationError):ELearningSettings(**payload)
        self.assertEqual(ELearningSettings(academy_hero_title='<b>plain text</b>').academy_hero_title,'<b>plain text</b>')

    def test_bridge_fails_before_new_rpc(self):
        with patch.object(service,'settings_available',return_value=False),patch.object(service,'service_supabase') as db:
            with self.assertRaises(HTTPException) as error:service.storefront(17,{'subdomain':'tenant'})
        self.assertEqual(error.exception.status_code,503);db.rpc.assert_not_called()

    def test_public_profile_does_not_expose_private_settings(self):
        cfg=ELearningSettings(sequential_progression=True).model_dump(mode='json')
        with patch.object(service,'get_settings',return_value=cfg):data=service.profile(17,{'subdomain':'tenant','tenant_id':17,'ecommerce_theme':{'accent':'#123456','private':'secret'}})
        self.assertNotIn('sequential_progression',data);self.assertNotIn('tenant_id',data);self.assertEqual(data['theme'],{'accent':'#123456'})


class AcademyProjectionTests(unittest.TestCase):
    def test_authorized_private_course_is_only_in_personal_continue_feed(self):
        db=MagicMock()
        public={"courses":[{"id":"public"}],"plans":[],"authenticated":True}
        runtime={"course":{"id":"private","name":"Private course","description":"Own enrolled course","cover_url":""},"progress":{"progress_status":"active","progress_percent":50},"continue_lesson_id":"next","blocks":[{"content":"protected lesson body"}],"sections":[]}
        db.rpc.return_value.execute.side_effect=[SimpleNamespace(data=public),SimpleNamespace(data=[runtime]),SimpleNamespace(data=[])]
        with patch.object(service,"settings_available",return_value=True),patch.object(service,"service_supabase",db),patch.object(service,"profile",return_value={}),patch.object(service,"get_settings",return_value=ELearningSettings().model_dump(mode="json")):
            result=service.storefront(17,{"subdomain":"testing"},SimpleNamespace(user_id=3,role="learner"))
        self.assertEqual(result["courses"],[{"id":"public"}])
        self.assertEqual(result["continue_courses"][0]["resume"],"/my-learning/courses/private/lessons/next")
        self.assertNotIn("protected lesson body",str(result))
        self.assertEqual(db.rpc.call_args_list[1].args[1]["p_user_id"],3)

    def test_guest_never_requests_learning_feed(self):
        db=MagicMock();db.rpc.return_value.execute.return_value.data={"courses":[],"plans":[],"authenticated":False}
        with patch.object(service,"settings_available",return_value=True),patch.object(service,"service_supabase",db),patch.object(service,"profile",return_value={}),patch.object(service,"get_settings",return_value=ELearningSettings().model_dump(mode="json")):
            result=service.storefront(17,{"subdomain":"testing"})
        self.assertEqual(result["continue_courses"],[]);self.assertEqual([call.args[0] for call in db.rpc.call_args_list],["get_elearning_academy", "get_academy_public_instructors"])
