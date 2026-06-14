import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services import audit_service


class FakeExecuteResult:
    data = []


class FakeInsertQuery:
    def __init__(self, should_fail=False):
        self.payload = None
        self.should_fail = should_fail

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.should_fail:
            raise RuntimeError("insert failed")
        return FakeExecuteResult()


class FakeSupabase:
    def __init__(self, should_fail=False):
        self.query = FakeInsertQuery(should_fail=should_fail)
        self.table_names = []

    def table(self, name):
        self.table_names.append(name)
        return self.query


def build_client(handler):
    app = FastAPI()

    @app.post("/audit")
    def audit_endpoint(request: Request):
        handler(request)
        return {"ok": True}

    return TestClient(app)


class AuditServiceTests(unittest.TestCase):
    def test_record_audit_event_inserts_expected_payload(self):
        fake_supabase = FakeSupabase()

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_audit_event(
                tenant_id=7,
                actor_user_id=3,
                action="builder.project_published",
                target_type="builder_project",
                target_id=123,
                metadata={"project_slug": "site"},
            )

        self.assertEqual(fake_supabase.table_names, ["audit_logs"])
        self.assertEqual(
            fake_supabase.query.payload,
            {
                "tenant_id": 7,
                "actor_user_id": 3,
                "action": "builder.project_published",
                "target_type": "builder_project",
                "target_id": "123",
                "metadata": {"project_slug": "site"},
                "ip": None,
                "user_agent": None,
            },
        )

    def test_record_audit_event_captures_ip_and_truncates_user_agent(self):
        fake_supabase = FakeSupabase()
        long_user_agent = "A" * 1200

        def handler(request):
            with patch.object(audit_service, "service_supabase", fake_supabase),                  patch.object(audit_service, "get_client_ip", return_value="203.0.113.10"):
                audit_service.record_audit_event(
                    request=request,
                    tenant_id=7,
                    actor_user_id=3,
                    action="builder.project_archived",
                    target_type="builder_project",
                    target_id="project-1",
                    metadata={},
                )

        client = build_client(handler)
        response = client.post("/audit", headers={"user-agent": long_user_agent})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_supabase.query.payload["ip"], "203.0.113.10")
        self.assertEqual(len(fake_supabase.query.payload["user_agent"]), 1000)

    def test_record_audit_event_strips_sensitive_metadata_keys(self):
        fake_supabase = FakeSupabase()

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_audit_event(
                tenant_id=7,
                actor_user_id=3,
                action="builder.project_published",
                target_type="builder_project",
                target_id="project-1",
                metadata={
                    "project_slug": "site",
                    "password": "secret",
                    "access-token": "secret",
                    "nested": {
                        "published_schema": {"pages": []},
                        "safe": "value",
                    },
                    "items": [{"answers": {"field": "value"}, "label": "safe"}],
                },
            )

        metadata = fake_supabase.query.payload["metadata"]
        self.assertEqual(metadata["project_slug"], "site")
        self.assertNotIn("password", metadata)
        self.assertNotIn("access-token", metadata)
        self.assertEqual(metadata["nested"], {"safe": "value"})
        self.assertEqual(metadata["items"], [{"label": "safe"}])

    def test_record_audit_event_failure_does_not_raise(self):
        fake_supabase = FakeSupabase(should_fail=True)

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_audit_event(
                tenant_id=7,
                actor_user_id=3,
                action="builder.project_published",
                target_type="builder_project",
                target_id="project-1",
                metadata={},
            )

        self.assertEqual(fake_supabase.table_names, ["audit_logs"])


if __name__ == "__main__":
    unittest.main()
