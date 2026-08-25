import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from services import account_lifecycle_service


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeUsersQuery:
    def __init__(self, client):
        self.client = client
        self.operation = "select"
        self.payload = None
        self.filters = []

    def select(self, *_args):
        self.operation = "select"
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, _count):
        return self

    def execute(self):
        rows = [self.client.user]
        for key, value in self.filters:
            rows = [row for row in rows if row.get(key) == value]
        if self.operation == "update":
            for row in rows:
                row.update(self.payload)
        return FakeResult([dict(row) for row in rows])


class FakeRpcQuery:
    def __init__(self, client):
        self.client = client

    def execute(self):
        self.client.rpc_executions += 1
        self.client.user.update(
            {"tenant_id": 12, "account_status": "active", "email_verified": True}
        )
        return FakeResult(dict(self.client.user))


class FakeServiceClient:
    def __init__(self, user):
        self.user = dict(user)
        self.rpc_calls = []
        self.rpc_executions = 0

    def table(self, name):
        if name != "users":
            raise AssertionError(name)
        return FakeUsersQuery(self)

    def rpc(self, name, payload):
        self.rpc_calls.append((name, payload))
        return FakeRpcQuery(self)


def auth_user(*, verified=True, email="owner@example.com"):
    return SimpleNamespace(
        id="auth-1",
        email=email,
        email_confirmed_at="2026-01-01T00:00:00Z" if verified else None,
        confirmed_at=None,
    )


class AccountLifecycleServiceTests(unittest.TestCase):
    def test_deletion_pending_account_cannot_be_reactivated_by_provider_sync(self):
        user = {
            "id": 9,
            "auth_id": "auth-9",
            "tenant_id": 7,
            "email": "closed@example.test",
            "account_status": "deletion_pending",
            "email_verified": True,
        }
        auth_user = SimpleNamespace(
            id="auth-9",
            email="closed@example.test",
            email_confirmed_at="2026-08-25T00:00:00Z",
        )
        with self.assertRaises(HTTPException) as raised:
            account_lifecycle_service.synchronize_verified_account(auth_user, user)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail["code"], "account_deletion_pending")

    def test_pending_verified_account_is_provisioned_through_transactional_rpc(self):
        local = {
            "id": 3,
            "auth_id": "auth-1",
            "tenant_id": None,
            "email": "owner@example.com",
            "email_verified": False,
            "email_verified_at": None,
            "account_status": "pending_verification",
        }
        fake = FakeServiceClient(local)

        with patch.object(account_lifecycle_service, "service_supabase", fake):
            result, activated = account_lifecycle_service.synchronize_verified_account(
                auth_user(),
                dict(local),
            )

        self.assertTrue(activated)
        self.assertEqual(result["tenant_id"], 12)
        self.assertEqual(result["account_status"], "active")
        self.assertEqual(
            fake.rpc_calls,
            [("provision_verified_account", {"p_auth_id": "auth-1"})],
        )
        self.assertEqual(fake.rpc_executions, 1)

    def test_active_verified_account_retry_does_not_provision_again(self):
        local = {
            "id": 3,
            "auth_id": "auth-1",
            "tenant_id": 12,
            "email": "owner@example.com",
            "email_verified": True,
            "email_verified_at": "2026-01-01T00:00:00Z",
            "account_status": "active",
        }
        fake = FakeServiceClient(local)

        with patch.object(account_lifecycle_service, "service_supabase", fake):
            result, activated = account_lifecycle_service.synchronize_verified_account(
                auth_user(),
                dict(local),
            )

        self.assertFalse(activated)
        self.assertEqual(result, local)
        self.assertEqual(fake.rpc_executions, 0)

    def test_verified_site_visitor_is_synchronized_without_platform_provisioning(self):
        local = {
            "id": 9,
            "auth_id": "auth-1",
            "tenant_id": None,
            "email": "owner@example.com",
            "email_verified": False,
            "email_verified_at": None,
            "account_kind": "site_visitor",
            "account_status": "pending_verification",
        }
        fake = FakeServiceClient(local)

        with patch.object(account_lifecycle_service, "service_supabase", fake):
            result, activated = account_lifecycle_service.synchronize_verified_account(
                auth_user(),
                dict(local),
            )

        self.assertTrue(activated)
        self.assertEqual(result["account_kind"], "site_visitor")
        self.assertEqual(result["account_status"], "active")
        self.assertTrue(result["email_verified"])
        self.assertIsNone(result["tenant_id"])
        self.assertEqual(fake.rpc_calls, [])
        self.assertEqual(fake.rpc_executions, 0)

    def test_unverified_provider_state_never_activates_local_account(self):
        local = {
            "id": 3,
            "auth_id": "auth-1",
            "tenant_id": None,
            "email": "owner@example.com",
            "email_verified": False,
            "account_status": "pending_verification",
        }

        with self.assertRaises(HTTPException) as caught:
            account_lifecycle_service.synchronize_verified_account(
                auth_user(verified=False),
                local,
            )

        self.assertEqual(caught.exception.detail["code"], "email_verification_required")

    def test_disabled_account_is_not_reactivated_by_provider_confirmation(self):
        local = {
            "id": 3,
            "auth_id": "auth-1",
            "tenant_id": 12,
            "email": "owner@example.com",
            "email_verified": True,
            "account_status": "disabled",
        }

        with self.assertRaises(HTTPException) as caught:
            account_lifecycle_service.synchronize_verified_account(auth_user(), local)

        self.assertEqual(caught.exception.detail["code"], "account_disabled")

    def test_expired_pending_account_is_not_provisioned_after_late_confirmation(self):
        local = {
            "id": 3,
            "auth_id": "auth-1",
            "tenant_id": None,
            "email": "owner@example.com",
            "email_verified": False,
            "account_status": "pending_verification",
            "pending_account_expires_at": "2020-01-01T00:00:00Z",
        }
        fake = FakeServiceClient(local)

        with patch.object(account_lifecycle_service, "service_supabase", fake):
            with self.assertRaises(HTTPException) as caught:
                account_lifecycle_service.synchronize_verified_account(
                    auth_user(),
                    local,
                )

        self.assertEqual(caught.exception.detail["code"], "pending_account_expired")
        self.assertEqual(fake.rpc_executions, 0)

    def test_stale_pending_cleanup_is_dry_run_by_default(self):
        pending_query = MagicMock()
        pending_query.select.return_value = pending_query
        pending_query.in_.return_value = pending_query
        pending_query.lte.return_value = pending_query
        pending_query.order.return_value = pending_query
        pending_query.limit.return_value = pending_query
        pending_query.execute.return_value = FakeResult(
            [
                {
                    "id": "pending-1",
                    "auth_id": "auth-1",
                    "user_id": 3,
                    "tenant_id": None,
                    "status": "pending",
                    "expires_at": "2026-01-01T00:00:00Z",
                }
            ]
        )
        fake = MagicMock()
        fake.table.return_value = pending_query
        fake.auth.admin.delete_user = MagicMock()

        with patch.object(account_lifecycle_service, "service_supabase", fake), patch.object(
            account_lifecycle_service,
            "get_local_user_by_auth_id",
            return_value={"id": 3, "tenant_id": None},
        ), patch.object(
            account_lifecycle_service,
            "get_auth_user_by_id",
            return_value=auth_user(verified=False),
        ):
            result = account_lifecycle_service.cleanup_stale_pending_accounts()

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["deleted"], 0)
        fake.auth.admin.delete_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()
