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

    def test_hash_audit_identifier_is_stable_and_not_raw_value(self):
        digest = audit_service.hash_audit_identifier("User@Example.com")

        self.assertEqual(digest, audit_service.hash_audit_identifier(" user@example.com "))
        self.assertNotIn("user@example.com", digest)
        self.assertEqual(len(digest), 64)

    def test_record_tenant_role_change_uses_explicit_event_type(self):
        fake_supabase = FakeSupabase()

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_tenant_role_change(
                tenant_id=7,
                actor_user_id=3,
                target_user_id=9,
                old_role="member",
                new_role="admin",
            )

        payload = fake_supabase.query.payload
        self.assertEqual(payload["action"], "tenant.role_changed")
        self.assertEqual(payload["actor_user_id"], 3)
        self.assertEqual(payload["target_id"], "9")
        self.assertEqual(payload["metadata"]["old_role"], "member")
        self.assertEqual(payload["metadata"]["new_role"], "admin")

    def test_record_user_restoration_uses_explicit_event_type(self):
        fake_supabase = FakeSupabase()

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_user_restoration(
                tenant_id=7,
                actor_user_id=3,
                restored_user_id=9,
            )

        payload = fake_supabase.query.payload
        self.assertEqual(payload["action"], "admin.user_restored")
        self.assertEqual(payload["actor_user_id"], 3)
        self.assertEqual(payload["target_id"], "9")
        self.assertEqual(payload["metadata"], {"restored_user_id": 9, "source": "admin"})

    def test_mfa_audit_event_constants_are_explicit(self):
        self.assertEqual(audit_service.MFA_ENROLL_STARTED, "auth.mfa_enroll_started")
        self.assertEqual(audit_service.MFA_ENROLL_VERIFIED, "auth.mfa_enroll_verified")
        self.assertEqual(audit_service.MFA_CHALLENGE_FAILED, "auth.mfa_challenge_failed")
        self.assertEqual(audit_service.MFA_VERIFIED, "auth.mfa_verified")
        self.assertEqual(audit_service.MFA_FACTOR_REMOVED, "auth.mfa_factor_removed")
        self.assertEqual(audit_service.MFA_REQUIRED_CHANGED, "auth.mfa_required_changed")

    def test_record_mfa_event_uses_explicit_event_type(self):
        fake_supabase = FakeSupabase()

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_mfa_event(
                tenant_id=7,
                actor_user_id=3,
                action=audit_service.MFA_ENROLL_STARTED,
                target_user_id=3,
                factor_id="factor-1",
                metadata={"factor_type": "totp"},
            )

        payload = fake_supabase.query.payload
        self.assertEqual(payload["action"], "auth.mfa_enroll_started")
        self.assertEqual(payload["target_type"], "mfa_factor")
        self.assertEqual(payload["target_id"], "factor-1")
        self.assertEqual(payload["metadata"]["factor_type"], "totp")
        self.assertEqual(payload["metadata"]["factor_id"], "factor-1")

    def test_record_mfa_required_changed_uses_explicit_event_type(self):
        fake_supabase = FakeSupabase()

        with patch.object(audit_service, "service_supabase", fake_supabase):
            audit_service.record_mfa_required_changed(
                tenant_id=7,
                actor_user_id=3,
                target_user_id=9,
                required=True,
            )

        payload = fake_supabase.query.payload
        self.assertEqual(payload["action"], "auth.mfa_required_changed")
        self.assertEqual(payload["target_type"], "user")
        self.assertEqual(payload["target_id"], "9")
        self.assertEqual(payload["metadata"], {"required": True, "source": "admin"})


if __name__ == "__main__":
    unittest.main()
