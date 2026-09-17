import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import admin_user_routes, data_deletion_routes


class DataDeletionAuthorizationTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(data_deletion_routes.router)
        app.include_router(admin_user_routes.router)
        self.client = TestClient(app)

    def test_self_closure_derives_target_from_authenticated_user(self):
        user = {"id": 7, "tenant_id": 3}
        with patch.object(data_deletion_routes, "require_regular_user", return_value=(object(), user)), \
             patch.object(data_deletion_routes, "request_user_deletion", return_value={"request_id": "request-1"}) as create, \
             patch.object(data_deletion_routes, "delete_auth_cookies"):
            response = self.client.post("/account/deletion")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(create.call_args.kwargs, {"target_user_id": 7, "requested_by_user_id": 7})

    def test_ordinary_member_cannot_delete_tenant(self):
        context = SimpleNamespace(tenant_id=3, user_id=7, role="member")
        with patch.object(data_deletion_routes, "get_current_tenant_context", return_value=context), \
             patch.object(data_deletion_routes, "request_tenant_deletion") as create:
            response = self.client.post("/tenant/deletion")
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_tenant_owner_requires_exact_aal2_before_request(self):
        context = SimpleNamespace(tenant_id=3, user_id=7, role="owner")
        denial = HTTPException(status_code=403, detail={"code": "aal2_required"})
        with patch.object(data_deletion_routes, "get_current_tenant_context", return_value=context), \
             patch.object(data_deletion_routes, "require_current_session_aal2", side_effect=denial), \
             patch.object(data_deletion_routes, "request_tenant_deletion") as create:
            response = self.client.post("/tenant/deletion")
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_owner_request_uses_authoritative_tenant_context(self):
        context = SimpleNamespace(tenant_id=3, user_id=7, role="owner")
        with patch.object(data_deletion_routes, "get_current_tenant_context", return_value=context), \
             patch.object(data_deletion_routes, "require_current_session_aal2", return_value={"current_level": "aal2"}), \
             patch.object(data_deletion_routes, "request_tenant_deletion", return_value={"request_id": "request-2"}) as create, \
             patch.object(data_deletion_routes, "delete_auth_cookies"):
            response = self.client.post("/tenant/deletion")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(create.call_args.kwargs, {"target_tenant_id": 3, "requested_by_user_id": 7})

    def test_admin_user_delete_requires_aal2_and_only_schedules(self):
        admin = {"id": 99, "user_type": "admin"}
        scheduled = {"request_id": "request-3", "target_tenant_id": 3}
        with patch.object(admin_user_routes, "require_system_admin", return_value=(object(), admin)) as authorize, \
             patch.object(admin_user_routes, "delete_user_account", return_value={"id": 7, "tenant_id": 3, "deletion_pending": True, "deletion_request_id": "request-3"}) as create, \
             patch.object(admin_user_routes, "record_audit_event"):
            response = self.client.delete("/admin/users/7")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["deleted_user"]["deletion_pending"])
        self.assertTrue(authorize.call_args.kwargs["require_aal2"])
        self.assertEqual(create.call_args.kwargs, {"user_id": 7, "requesting_user_id": 99})

    def test_cross_user_status_is_hidden(self):
        with patch.object(data_deletion_routes, "require_regular_user", return_value=(object(), {"id": 7})), \
             patch.object(data_deletion_routes, "get_deletion_request", return_value={"id": "request-x", "requested_by_user_id": 8}):
            response = self.client.get("/account/deletion/request-x")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
