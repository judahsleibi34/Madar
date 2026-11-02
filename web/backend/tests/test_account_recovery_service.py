from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from services import account_recovery_service as recovery, data_deletion_service as deletion, account_erasure_service as erasure
from routes import data_deletion_routes


CAPABILITY = {"version": 1, "recovery_hours": 2160, "permanent_erasure": False,
              "request_admission": False,
              "recovery_authority": "aal2_system_admin"}


class AccountRecoveryServiceTests(unittest.TestCase):
    def test_capability_is_exact_and_has_no_unsafe_legacy_fallback(self):
        client = Mock()
        for value in (None, {}, {**CAPABILITY, "version": True},
                      {**CAPABILITY, "recovery_hours": 0}, {**CAPABILITY, "permanent_erasure": True}):
            client.rpc.return_value.execute.return_value = SimpleNamespace(data=value)
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                deletion.request_user_deletion(target_user_id=7, requested_by_user_id=7, client=client)
            self.assertEqual(caught.exception.status_code, 503)
        self.assertTrue(all(call.args[0] == "account_lifecycle_capability167" for call in client.rpc.call_args_list))
        client.rpc.return_value.execute.return_value = SimpleNamespace(data=CAPABILITY)
        self.assertEqual(recovery.require_capability(client=client), CAPABILITY)
        client.rpc.return_value.execute.return_value = SimpleNamespace(data={"protocol":3,"deactivate_recovery_hours":2160,"delete_recovery_hours":0,"completion_boundary":"server_controlled","admission":{"deactivate":False,"delete":False}})
        with self.assertRaises(HTTPException) as caught:
            deletion.request_user_deletion(target_user_id=7, requested_by_user_id=7, client=client)
        self.assertEqual(caught.exception.detail["code"], "account_lifecycle_acceptance_required")

    def test_missing_capability_fails_closed_without_provider_error_details(self):
        client = Mock()
        client.rpc.return_value.execute.side_effect = RuntimeError("private-provider-detail")
        with self.assertRaises(HTTPException) as caught:
            recovery.require_capability(client=client)
        self.assertNotIn("private-provider-detail", str(caught.exception.detail))

    def test_work_guard_keeps_historical_paths_and_refuses_future_schema(self):
        client = Mock()
        with patch("services.project_dataset_service.schema_version", return_value=166):
            recovery.require_processing_account(tenant_id=3, user_id=7, client=client)
        client.table.assert_not_called()
        for version in (0,145,168):
            with patch("services.project_dataset_service.schema_version", return_value=version), self.assertRaises(HTTPException):
                recovery.require_processing_account(tenant_id=3, user_id=7, client=client)

    def test_work_guard_requires_live_same_tenant_account(self):
        client = Mock()
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(data=[{"id":7,"account_status":"deletion_pending"}])
        with patch("services.project_dataset_service.schema_version", return_value=167), self.assertRaises(HTTPException) as caught:
            recovery.require_processing_account(tenant_id=3, user_id=7, client=client)
        self.assertEqual(caught.exception.status_code,409)

    def test_recovery_route_requires_aal2_system_admin_and_never_recreates_content(self):
        app=FastAPI();app.include_router(data_deletion_routes.router)
        with TestClient(app) as client, patch.object(data_deletion_routes, "require_system_admin", return_value=(object(),{"id":99})) as authorize, patch.object(erasure,"reactivate", return_value={"id":"request-1","action":"deactivate","state":"reactivated"}) as recover:
            response=client.post("/admin/data-deletions/request-1/recover")
        self.assertEqual(response.status_code,200)
        self.assertTrue(authorize.call_args.kwargs["require_aal2"])
        self.assertEqual(recover.call_args.kwargs["actor_id"],99)
