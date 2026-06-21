import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import user_security_settings_service as service


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, data=None, should_fail=False):
        self.data = data or []
        self.should_fail = should_fail
        self.operations = []

    def select(self, columns):
        self.operations.append(("select", columns))
        return self

    def eq(self, column, value):
        self.operations.append(("eq", column, value))
        return self

    def limit(self, value):
        self.operations.append(("limit", value))
        return self

    def upsert(self, payload, on_conflict=None):
        self.operations.append(("upsert", payload, on_conflict))
        self.data = [payload]
        return self

    def execute(self):
        if self.should_fail:
            raise RuntimeError("query failed")
        return FakeResult(self.data)


class FakeSupabase:
    def __init__(self, data=None, should_fail=False):
        self.query = FakeQuery(data=data, should_fail=should_fail)
        self.table_names = []

    def table(self, name):
        self.table_names.append(name)
        return self.query


class UserSecuritySettingsServiceTests(unittest.TestCase):
    def test_get_user_security_settings_returns_normalized_row(self):
        fake = FakeSupabase(data=[{"user_id": 5, "auth_id": "auth-1", "mfa_required": True}])

        with patch.object(service, "service_supabase", fake):
            result = service.get_user_security_settings(5)

        self.assertEqual(fake.table_names, ["user_security_settings"])
        self.assertEqual(result["user_id"], 5)
        self.assertEqual(result["auth_id"], "auth-1")
        self.assertTrue(result["mfa_required"])

    def test_get_user_security_settings_returns_none_when_missing(self):
        fake = FakeSupabase(data=[])

        with patch.object(service, "service_supabase", fake):
            result = service.get_user_security_settings(5)

        self.assertIsNone(result)

    def test_get_user_security_settings_by_auth_id_ignores_blank_auth_id(self):
        fake = FakeSupabase(data=[])

        with patch.object(service, "service_supabase", fake):
            result = service.get_user_security_settings_by_auth_id("  ")

        self.assertIsNone(result)
        self.assertEqual(fake.table_names, [])

    def test_upsert_user_security_settings_writes_expected_payload(self):
        fake = FakeSupabase()

        with patch.object(service, "service_supabase", fake):
            result = service.upsert_user_security_settings(
                user_id=5,
                auth_id="auth-1",
                mfa_required=True,
                mfa_required_at="2026-06-21T10:00:00+00:00",
            )

        operation = fake.query.operations[0]
        self.assertEqual(operation[0], "upsert")
        self.assertEqual(operation[1]["user_id"], 5)
        self.assertEqual(operation[1]["auth_id"], "auth-1")
        self.assertTrue(operation[1]["mfa_required"])
        self.assertEqual(operation[2], "user_id")
        self.assertEqual(result["user_id"], 5)

    def test_upsert_user_security_settings_requires_auth_id(self):
        with self.assertRaises(HTTPException):
            service.upsert_user_security_settings(user_id=5, auth_id="")

    def test_set_mfa_required_delegates_to_upsert(self):
        fake = FakeSupabase()

        with patch.object(service, "service_supabase", fake):
            service.set_mfa_required(
                user_id=5,
                auth_id="auth-1",
                required=True,
                required_at="2026-06-21T10:00:00+00:00",
                grace_until="2026-06-28T10:00:00+00:00",
            )

        payload = fake.query.operations[0][1]
        self.assertTrue(payload["mfa_required"])
        self.assertEqual(payload["mfa_grace_until"], "2026-06-28T10:00:00+00:00")

    def test_mark_aal2_verified_updates_timestamp(self):
        fake = FakeSupabase()

        with patch.object(service, "service_supabase", fake):
            service.mark_aal2_verified(
                user_id=5,
                auth_id="auth-1",
                verified_at="2026-06-21T10:00:00+00:00",
            )

        payload = fake.query.operations[0][1]
        self.assertEqual(payload["last_aal2_at"], "2026-06-21T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
