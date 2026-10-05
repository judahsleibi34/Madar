import unittest
from unittest.mock import patch
from uuid import UUID, uuid4
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routes import elearning_credentials_routes as routes

class CredentialRouteTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router);self.http=TestClient(app);self.course=str(uuid4());self.id=str(uuid4());self.actor=SimpleNamespace(tenant_id=3,user_id=1)
        for name in ('owner','member'):
            p=patch.object(routes,name,return_value=self.actor);p.start();self.addCleanup(p.stop)

    def test_learner_detail_and_pdf_cannot_override_identity(self):
        with patch.object(routes.service,'mine',side_effect=HTTPException(404,'credential_not_found')) as mine:
            self.assertEqual(self.http.get('/elearning/my-certificates/'+self.id+'?user_id=99&pdf=true').status_code,404)
            mine.assert_called_once_with(self.actor,UUID(self.id))

    def test_public_is_unauthenticated_whitelisted_and_no_store(self):
        with patch.object(routes,'enforce_public_rate_limit'),patch.object(routes.service,'verification',return_value=None),patch.object(routes,'member',side_effect=AssertionError('public auth')):
            response=self.http.get('/verify/credential/unknown');self.assertEqual(response.json(),{'credential':None});self.assertEqual(response.headers['cache-control'],'no-store')

    def test_permissions_and_payload_validation(self):
        with patch.object(routes,'owner',side_effect=HTTPException(403,'forbidden')):
            self.assertEqual(self.http.get(f'/elearning/courses/{self.course}/certificate').status_code,403)
        self.assertEqual(self.http.post(f'/elearning/courses/{self.course}/certificate/backfill',json={'confirmed':True,'completion_id':'fake'}).status_code,422)
        self.assertEqual(self.http.post(f'/elearning/courses/{self.course}/certificate/credentials/{self.id}/revocation',json={'confirmed':'yes','reason':'test'}).status_code,422)
        self.assertEqual(self.http.post('/elearning/my-certificates',json={'completed':True}).status_code,405)
