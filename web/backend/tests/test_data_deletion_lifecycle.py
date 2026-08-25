from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from services import data_deletion_service as lifecycle


class Response:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class Query:
    def __init__(self, client, table):
        self.client = client
        self.name = table
        self.filters = []
        self.order_field = None
        self.desc = False
        self.maximum = None
        self.operation = "select"
        self.payload = None

    def select(self, *_args, **_kwargs): return self
    def eq(self, field, value): self.filters.append(("eq", field, value)); return self
    def in_(self, field, values): self.filters.append(("in", field, set(values))); return self
    def order(self, field, desc=False): self.order_field = field; self.desc = desc; return self
    def limit(self, maximum): self.maximum = maximum; return self
    def update(self, payload): self.operation = "update"; self.payload = payload; return self
    def delete(self): self.operation = "delete"; return self

    def matches(self, row):
        for operation, field, expected in self.filters:
            if operation == "eq" and row.get(field) != expected: return False
            if operation == "in" and row.get(field) not in expected: return False
        return True

    def execute(self):
        source = self.client.tables.setdefault(self.name, [])
        selected = [row for row in source if self.matches(row)]
        if self.order_field:
            selected.sort(key=lambda row: row.get(self.order_field), reverse=self.desc)
        if self.maximum is not None:
            selected = selected[: self.maximum]
        if self.operation == "update":
            for row in selected: row.update(self.payload)
        elif self.operation == "delete":
            self.client.tables[self.name] = [row for row in source if not self.matches(row)]
        return Response([dict(row) for row in selected])


class StorageBucket:
    def __init__(self, client, bucket): self.client, self.bucket = client, bucket
    def remove(self, paths):
        for path in paths:
            key = (self.bucket, path)
            error = self.client.storage_errors.get(key)
            if error: raise error
            self.client.removed.append(key)
        return {}
    def list(self, _folder, _options): return []


class Storage:
    def __init__(self, client): self.client = client
    def from_(self, bucket): return StorageBucket(self.client, bucket)


class Client:
    def __init__(self, tables):
        self.tables = tables
        self.deleted_auth = []
        self.removed = []
        self.storage_errors = {}
        self.storage = Storage(self)
        self.auth = SimpleNamespace(admin=SimpleNamespace(
            delete_user=self.delete_auth,
            get_user_by_id=lambda _auth_id: (_ for _ in ()).throw(Exception("not found")),
        ))

    def table(self, name): return Query(self, name)
    def delete_auth(self, auth_id): self.deleted_auth.append(auth_id)


STEP_KEYS = [
    "freeze", "revoke_sessions", "revoke_integrations", "stop_queued_work",
    "delete_provider_objects", "delete_host_files", "delete_application_data",
    "delete_auth_identities", "verify", "finalize",
]


def workflow(request_type="user"):
    request = {
        "id": "request-1", "request_type": request_type, "state": "in_progress",
        "current_phase": "freeze", "attempt_count": 1, "max_attempts": 12,
        "target_user_id_snapshot": 9 if request_type == "user" else None,
        "target_tenant_id_snapshot": 7,
        "verification_status": "pending", "retained_classes": [], "completion_report": {},
    }
    steps = [
        {"id": index, "request_id": "request-1", "step_key": key, "step_order": index * 10,
         "state": "pending", "attempts": 0, "max_attempts": 3}
        for index, key in enumerate(STEP_KEYS, 1)
    ]
    users = [{"id": 9, "tenant_id": 7, "account_status": "deletion_pending"}]
    tenants = [{"tenant_id": 7, "lifecycle_state": "deletion_pending"}]
    return Client({
        "data_deletion_requests": [request], "data_deletion_steps": steps,
        "data_deletion_subjects": [{"request_id": "request-1", "user_id_snapshot": 9, "auth_id": "00000000-0000-0000-0000-000000000009", "provider_state": "pending"}],
        "data_deletion_resources": [], "users": users, "tenants": tenants,
        "calendar_sync_connections": [], "notification_outbox": [],
        "notification_deliveries": [], "calendar_task_sync_jobs": [],
        "calendar_connection_sync_jobs": [], "website_settings": [],
    }), request


class DeletionLifecycleTests(unittest.TestCase):
    def test_user_deletion_completes_only_after_database_auth_and_verification(self):
        client, request = workflow("user")
        result = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(result["state"], "completed_with_retained_records")
        self.assertEqual(client.tables["users"], [])
        self.assertEqual(client.deleted_auth, ["00000000-0000-0000-0000-000000000009"])
        self.assertEqual(result["verification_status"], "verified_with_retained_records")
        self.assertIn("security_audit_metadata", result["retained_classes"])

    def test_tenant_deletion_unbinds_public_state_and_removes_platform_users(self):
        client, request = workflow("tenant")
        client.tables["website_settings"] = [{"id": 1, "tenant_id": 7}]
        # Model both the tenant-owned cascades and PostgreSQL's restrictive
        # users.tenant_id FK so the service's ordering is exercised faithfully.
        original_delete = Query.execute
        def cascade(query):
            if query.name == "tenants" and query.operation == "delete":
                tenant_ids = {
                    row["tenant_id"] for row in client.tables["tenants"]
                    if query.matches(row)
                }
                if any(row.get("tenant_id") in tenant_ids for row in client.tables["users"]):
                    raise RuntimeError("users_tenant_id_fkey")
            response = original_delete(query)
            if query.name == "tenants" and query.operation == "delete":
                client.tables["website_settings"] = []
                client.tables["calendar_sync_connections"] = []
            return response
        with patch.object(Query, "execute", cascade):
            result = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(result["state"], "completed_with_retained_records")
        self.assertEqual(client.tables["tenants"], [])
        self.assertEqual(client.tables["users"], [])
        self.assertIn("billing_webhook_replay_metadata", result["retained_classes"])

    def test_transient_provider_failure_persists_retry_state_and_phase(self):
        client, request = workflow("user")
        def unavailable(*_args, **_kwargs):
            raise lifecycle.DeletionStepError("auth_provider_unavailable")
        with patch.dict(lifecycle.STEP_HANDLERS, {"revoke_sessions": unavailable}):
            result = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(result["state"], "waiting_retry")
        self.assertEqual(result["phase"], "revoke_sessions")
        self.assertEqual(result["last_error_code"], "auth_provider_unavailable")
        self.assertIsNotNone(result["retry_after"])

    def test_auth_provider_timeout_resumes_after_irreversible_database_step(self):
        client, request = workflow("user")
        client.auth.admin.delete_user = MagicMock(side_effect=TimeoutError("provider timeout"))
        first = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(first["state"], "waiting_retry")
        self.assertEqual(first["phase"], "delete_auth_identities")
        self.assertEqual(client.tables["users"], [])
        client.tables["data_deletion_requests"][0]["state"] = "in_progress"
        client.auth.admin.delete_user = client.delete_auth
        forbidden = MagicMock(side_effect=AssertionError("database deletion replayed"))
        with patch.dict(lifecycle.STEP_HANDLERS, {"delete_application_data": forbidden}):
            second = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(second["state"], "completed_with_retained_records")
        forbidden.assert_not_called()

    def test_completed_steps_are_not_replayed_after_worker_restart(self):
        client, request = workflow("user")
        for step in client.tables["data_deletion_steps"][:3]:
            step["state"] = "completed"
        forbidden = MagicMock(side_effect=AssertionError("completed step replayed"))
        with patch.dict(lifecycle.STEP_HANDLERS, {"freeze": forbidden, "revoke_sessions": forbidden, "revoke_integrations": forbidden}):
            result = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(result["state"], "completed_with_retained_records")
        forbidden.assert_not_called()

    def test_verification_mismatch_cannot_be_marked_completed(self):
        client, request = workflow("user")
        with self.assertRaises(lifecycle.DeletionStepError) as raised:
            lifecycle._step_verify(request, client=client)
        self.assertEqual(raised.exception.code, "deletion_verification_mismatch")
        self.assertEqual(client.tables["data_deletion_requests"][0]["verification_status"], "mismatch")

    def test_provider_objects_are_tenant_manifest_bound_and_replay_safe(self):
        client, request = workflow("user")
        client.tables["data_deletion_resources"] = [
            {"id": 1, "request_id": "request-1", "resource_kind": "supabase_avatar", "resource_key": "users/auth/avatar.png", "state": "pending", "attempts": 0}
        ]
        first = lifecycle._step_delete_provider_objects(request, client=client)
        second = lifecycle._step_delete_provider_objects(request, client=client)
        self.assertEqual(first["deleted"], 1)
        self.assertEqual(second["deleted"], 0)
        self.assertEqual(client.removed, [("avatars", "users/auth/avatar.png")])

    def test_host_path_traversal_and_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(lifecycle.HOST_RESOURCE_ROOTS, {"host_dataset": lambda: Path(directory)}):
                with self.assertRaises(lifecycle.DeletionStepError):
                    lifecycle._safe_host_path({"resource_kind": "host_dataset", "resource_key": "../../etc/passwd"})
                tenant = Path(directory) / "tenant_7" / "user_9"
                tenant.mkdir(parents=True)
                target = tenant / "file.csv"
                target.symlink_to(Path(directory) / "outside.csv")
                client, request = workflow("user")
                client.tables["data_deletion_resources"] = [{"id": 1, "request_id": "request-1", "resource_kind": "host_dataset", "resource_key": "tenant_7/user_9/file.csv", "state": "pending", "attempts": 0}]
                with self.assertRaises(lifecycle.DeletionStepError):
                    lifecycle._step_delete_host_files(request, client=client)

    def test_unknown_storage_policy_requires_manual_intervention(self):
        client, request = workflow("user")
        client.tables["data_deletion_resources"] = [{
            "id": 1, "request_id": "request-1", "resource_kind": "unknown_storage",
            "resource_key": "opaque-resource", "state": "pending", "attempts": 0,
        }]
        result = lifecycle.process_deletion_request(request, client=client)
        self.assertEqual(result["state"], "failed_manual_intervention")
        self.assertEqual(result["last_error_code"], "storage_category_policy_undefined")

    def test_user_closure_stops_calendar_work_for_only_the_users_connections(self):
        client, request = workflow("user")
        client.tables["calendar_sync_connections"] = [
            {"id": "own", "user_id": 9, "tenant_id": 7},
            {"id": "other", "user_id": 10, "tenant_id": 7},
        ]
        client.tables["calendar_task_sync_jobs"] = [
            {"id": "job-own", "connection_id": "own", "status": "pending"},
            {"id": "job-other", "connection_id": "other", "status": "pending"},
        ]
        client.tables["calendar_connection_sync_jobs"] = []
        lifecycle._step_stop_queued_work(request, client=client)
        jobs = {row["id"]: row for row in client.tables["calendar_task_sync_jobs"]}
        self.assertEqual(jobs["job-own"]["status"], "failed")
        self.assertEqual(jobs["job-other"]["status"], "pending")

    def test_pending_cancellation_restores_frozen_user(self):
        client, request = workflow("user")
        request.update({
            "state": "pending", "target_user_id": 9,
            "freeze_snapshot": {"account_status": "active"},
        })
        result = lifecycle.cancel_deletion_request("request-1", client=client)
        self.assertEqual(result["state"], "cancelled_before_execution")
        self.assertEqual(client.tables["users"][0]["account_status"], "active")

    def test_cancellation_after_a_completed_step_is_rejected(self):
        client, request = workflow("user")
        request.update({
            "state": "pending", "target_user_id": 9,
            "freeze_snapshot": {"account_status": "active"},
        })
        client.tables["data_deletion_steps"][0]["state"] = "completed"
        with self.assertRaises(HTTPException) as raised:
            lifecycle.cancel_deletion_request("request-1", client=client)
        self.assertEqual(raised.exception.status_code, 409)

    def test_metrics_expose_manual_and_retry_backlogs_without_target_data(self):
        client, _ = workflow("user")
        client.tables["data_deletion_requests"] += [
            {"state": "waiting_retry", "created_at": "2026-08-25T00:00:00Z"},
            {"state": "failed_manual_intervention", "created_at": "2026-08-25T00:00:00Z"},
        ]
        metrics = lifecycle.get_deletion_metrics(client=client)
        self.assertEqual(metrics["deletion_retrying"], 1)
        self.assertEqual(metrics["deletion_manual_intervention"], 1)
        self.assertNotIn("target_user_id", metrics)


if __name__ == "__main__":
    unittest.main()
