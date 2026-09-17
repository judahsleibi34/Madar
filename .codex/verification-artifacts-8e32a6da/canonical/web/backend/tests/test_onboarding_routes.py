import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import auth_routes
from services import onboarding_service


def build_client():
    app = FastAPI()
    app.include_router(auth_routes.router)
    return TestClient(app)


class FakeAuthAdmin:
    def __init__(self, auth):
        self.auth = auth
        self.created_users = []
        self.deleted_users = []
        self.updated_users = []

    def create_user(self, payload):
        self.created_users.append(payload)
        auth_user = SimpleNamespace(
            id=f"auth-user-{len(self.created_users)}",
            email=payload.get("email"),
        )
        self.auth.auth_users.append(auth_user)
        return SimpleNamespace(user=auth_user)

    def delete_user(self, user_id):
        self.deleted_users.append(user_id)
        self.auth.auth_users = [
            user for user in self.auth.auth_users if str(getattr(user, "id", "")) != str(user_id)
        ]
        return SimpleNamespace()

    def update_user_by_id(self, user_id, payload):
        self.updated_users.append((user_id, payload))
        return SimpleNamespace(user=SimpleNamespace(id=user_id))

    def list_users(self, page=None, per_page=None):
        page = page or 1
        per_page = per_page or len(self.auth.auth_users) or 1
        start = (page - 1) * per_page
        end = start + per_page
        return self.auth.auth_users[start:end]


class FakeAuth:
    def __init__(self):
        self.admin = FakeAuthAdmin(self)
        self.signed_up_users = []
        self.auth_users = []
        self.resent_verifications = []

    def sign_up(self, payload):
        self.signed_up_users.append(payload)
        auth_user = SimpleNamespace(
            id=f"auth-user-{len(self.signed_up_users)}",
            email=payload["email"],
        )
        self.auth_users.append(auth_user)
        return SimpleNamespace(user=auth_user)

    def sign_in_with_password(self, payload):
        for auth_user in self.auth_users:
            if (
                auth_user.email == payload["email"]
                and getattr(auth_user, "password", None) == payload["password"]
            ):
                return SimpleNamespace(user=auth_user)
        raise RuntimeError("Invalid login credentials")

    def resend(self, payload):
        self.resent_verifications.append(payload)
        return SimpleNamespace()


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.limit_count = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        if self.operation == "insert":
            return self.supabase.insert_row(self.table_name, self.payload)

        if self.operation == "delete":
            return self.supabase.delete_rows(self.table_name, self.filters)

        rows = list(self.supabase.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self):
        self.auth = FakeAuth()
        self.tables = {
            "tenants": [],
            "users": [],
            "tenant_memberships": [],
            "pending_account_onboarding": [],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)

    def insert_row(self, table_name, payload):
        row = dict(payload)
        if table_name == "tenants":
            row.setdefault("tenant_id", len(self.tables[table_name]) + 1)
        elif table_name == "users":
            row.setdefault("id", len(self.tables[table_name]) + 1)

        self.tables.setdefault(table_name, []).append(row)
        return FakeResult([row])

    def delete_rows(self, table_name, filters):
        old_rows = list(self.tables.get(table_name, []))
        kept_rows = []
        deleted = []
        for row in old_rows:
            should_delete = all(row.get(column) == value for column, value in filters)
            if should_delete:
                deleted.append(row)
            else:
                kept_rows.append(row)
        self.tables[table_name] = kept_rows
        return FakeResult(deleted)


class SignupRoutesTests(unittest.TestCase):
    def test_legacy_immediate_tenant_provisioning_is_blocked(self):
        with self.assertRaises(onboarding_service.HTTPException) as raised:
            onboarding_service.create_onboarded_tenant(
                supabase_client=object(),
                payload=object(),
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail["code"],
            "pending_verification_flow_required",
        )

    def test_signup_onboard_endpoint_is_removed(self):
        client = build_client()

        response = client.post(
            "/auth/signup/onboard",
            json={
                "first_name": "Madar",
                "last_name": "Owner",
                "email": "Owner@Example.COM",
                "password": "super-secret-password",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_signup_requires_terms_acceptance_before_creating_identity(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "supabase", fake_supabase), patch.object(
            auth_routes, "service_supabase", fake_supabase
        ):
            response = client.post(
                "/auth/signup",
                json={
                    "first_name": "Madar",
                    "last_name": "Owner",
                    "email": "owner@example.com",
                    "password": "super-secret-password",
                    "terms_accepted": False,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"]["code"],
            "terms_acceptance_required",
        )
        self.assertEqual(fake_supabase.auth.admin.created_users, [])
        self.assertEqual(fake_supabase.tables["users"], [])

    def test_signup_creates_pending_user_without_active_tenant_resources(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "supabase", fake_supabase), patch.object(
            auth_routes, "service_supabase", fake_supabase
        ), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ), patch.object(
            auth_routes,
            "FRONTEND_URL",
            "http://localhost:5173",
        ), patch.object(
            auth_routes,
            "send_verification_email",
            return_value={"sent": True, "retry_after": 60},
        ), patch.object(
            auth_routes,
            "set_pending_verification_cookie",
        ), patch.object(
            auth_routes,
            "record_security_event",
        ):
            response = client.post(
                "/auth/signup",
                json={
                    "first_name": "Existing",
                    "last_name": "Signup",
                    "email": "Existing@Example.COM",
                    "password": "super-secret-password",
                    "terms_accepted": True,
                    "business_name": "Ignored Business",
                    "subdomain": "ignored-site",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["message"],
            "Account created. Please verify your email before logging in.",
        )
        self.assertTrue(body["requires_email_verification"])
        self.assertEqual(body["user"]["email"], "existing@example.com")
        self.assertEqual(len(fake_supabase.auth.admin.created_users), 1)
        self.assertEqual(fake_supabase.auth.admin.created_users[0]["email"], "existing@example.com")
        self.assertEqual(
            fake_supabase.auth.admin.created_users[0]["email_confirm"],
            False,
        )
        self.assertEqual(fake_supabase.auth.admin.updated_users, [])
        self.assertEqual(fake_supabase.auth.signed_up_users, [])
        self.assertEqual(fake_supabase.tables["tenants"], [])
        self.assertEqual(len(fake_supabase.tables["users"]), 1)
        self.assertIs(fake_supabase.tables["users"][0]["email_verified"], False)
        self.assertIsNone(fake_supabase.tables["users"][0]["email_verified_at"])
        self.assertIsNone(fake_supabase.tables["users"][0]["tenant_id"])
        self.assertEqual(
            fake_supabase.tables["users"][0]["account_status"],
            "pending_verification",
        )
        self.assertEqual(
            fake_supabase.tables["users"][0]["terms_version"],
            auth_routes.CURRENT_TERMS_VERSION,
        )
        self.assertTrue(fake_supabase.tables["users"][0]["terms_accepted_at"])
        self.assertEqual(fake_supabase.tables["tenant_memberships"], [])
        self.assertEqual(len(fake_supabase.tables["pending_account_onboarding"]), 1)

    def test_original_signup_rejects_email_that_already_exists_in_supabase_auth(self):
        client = build_client()
        fake_supabase = FakeSupabase()
        fake_supabase.auth.auth_users.append(
            SimpleNamespace(id="auth-existing", email="existing@example.com")
        )

        with patch.object(auth_routes, "supabase", fake_supabase), patch.object(
            auth_routes, "service_supabase", fake_supabase
        ), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(
                "/auth/signup",
                json={
                    "first_name": "Existing",
                    "last_name": "Signup",
                    "email": "Existing@Example.COM",
                    "password": "super-secret-password",
                    "terms_accepted": True,
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Email is already registered")
        self.assertEqual(fake_supabase.auth.admin.created_users, [])
        self.assertEqual(fake_supabase.tables["tenants"], [])
        self.assertEqual(fake_supabase.tables["users"], [])
        self.assertEqual(fake_supabase.tables["tenant_memberships"], [])
        self.assertEqual(fake_supabase.tables["pending_account_onboarding"], [])

    def test_original_signup_recovers_unverified_auth_user_without_local_profile(self):
        client = build_client()
        fake_supabase = FakeSupabase()
        fake_supabase.auth.auth_users.append(
            SimpleNamespace(
                id="auth-orphaned",
                email="orphaned@example.com",
                email_confirmed_at=None,
            )
        )

        with patch.object(auth_routes, "supabase", fake_supabase), patch.object(
            auth_routes, "service_supabase", fake_supabase
        ), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ), patch.object(
            auth_routes,
            "send_verification_email",
            return_value={"sent": True, "retry_after": 60},
        ), patch.object(
            auth_routes,
            "set_pending_verification_cookie",
        ), patch.object(
            auth_routes,
            "record_security_event",
        ):
            response = client.post(
                "/auth/signup",
                json={
                    "first_name": "Recovered",
                    "last_name": "Signup",
                    "email": "Orphaned@Example.COM",
                    "password": "super-secret-password",
                    "terms_accepted": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("auth-orphaned", fake_supabase.auth.admin.deleted_users)
        self.assertEqual(len(fake_supabase.tables["users"]), 1)
        self.assertEqual(fake_supabase.tables["users"][0]["email"], "orphaned@example.com")

    def test_original_signup_recovers_verified_auth_user_after_password_check(self):
        client = build_client()
        fake_supabase = FakeSupabase()
        fake_supabase.auth.auth_users.append(
            SimpleNamespace(
                id="auth-verified-orphan",
                email="verified@example.com",
                email_confirmed_at="2026-01-01T00:00:00+00:00",
                password="super-secret-password",
            )
        )

        def provision_verified(_auth_user, local_user):
            return (
                {
                    **local_user,
                    "tenant_id": 1,
                    "email_verified": True,
                    "account_status": "active",
                },
                True,
            )

        with patch.object(auth_routes, "supabase", fake_supabase), patch.object(
            auth_routes, "service_supabase", fake_supabase
        ), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ), patch.object(
            auth_routes,
            "synchronize_verified_account",
            side_effect=provision_verified,
        ) as synchronize, patch.object(
            auth_routes,
            "record_verification_result",
        ), patch.object(
            auth_routes,
            "record_security_event",
        ):
            response = client.post(
                "/auth/signup",
                json={
                    "first_name": "Verified",
                    "last_name": "Owner",
                    "email": "Verified@Example.COM",
                    "password": "super-secret-password",
                    "terms_accepted": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["requires_email_verification"])
        self.assertEqual(response.json()["user"]["auth_id"], "auth-verified-orphan")
        self.assertEqual(fake_supabase.auth.signed_up_users, [])
        self.assertEqual(response.json()["user"]["account_status"], "active")
        synchronize.assert_called_once()

    def test_original_signup_rejects_numeric_names(self):
        client = build_client()

        for payload_overrides in ({"first_name": "123"}, {"last_name": "456"}):
            with self.subTest(payload_overrides=payload_overrides):
                fake_supabase = FakeSupabase()
                payload = {
                    "first_name": "Existing",
                    "last_name": "Signup",
                    "email": "Existing@Example.COM",
                    "password": "super-secret-password",
                    "terms_accepted": True,
                }
                payload.update(payload_overrides)

                with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
                    auth_routes,
                    "enforce_auth_rate_limit",
                ):
                    response = client.post("/auth/signup", json=payload)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(fake_supabase.auth.admin.created_users, [])
                self.assertEqual(fake_supabase.tables["tenants"], [])

    def test_login_rejects_unverified_email_with_clear_message(self):
        client = build_client()

        with patch.object(auth_routes, "enforce_auth_rate_limit"), patch.object(
            auth_routes.supabase.auth,
            "sign_in_with_password",
            side_effect=RuntimeError("Email not confirmed"),
        ), patch.object(
            auth_routes,
            "get_login_audit_user",
            return_value=None,
        ), patch.object(
            auth_routes,
            "record_security_event",
        ):
            response = client.post(
                "/auth/login",
                json={
                    "email": "unverified@example.com",
                    "password": "super-secret-password",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            {
                "code": "email_verification_required",
                "message": "Verify your email before logging in.",
                "context": {"resend_available_after": 0},
            },
        )

    def test_login_rejects_session_when_supabase_user_is_not_email_confirmed(self):
        client = build_client()
        auth_response = SimpleNamespace(
            user=SimpleNamespace(id="auth-1", email_confirmed_at=None, confirmed_at=None),
            session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )

        with patch.object(auth_routes, "enforce_auth_rate_limit"), patch.object(
            auth_routes.supabase.auth,
            "sign_in_with_password",
            return_value=auth_response,
        ), patch.object(
            auth_routes,
            "get_local_user_by_auth_id",
            return_value={
                "id": 1,
                "auth_id": "auth-1",
                "tenant_id": 1,
                "email": "unverified@example.com",
                "email_verified": False,
            },
        ), patch.object(
            auth_routes,
            "get_login_audit_user",
            return_value=None,
        ), patch.object(
            auth_routes,
            "record_security_event",
        ), patch.object(
            auth_routes,
            "set_pending_verification_cookie",
        ):
            response = client.post(
                "/auth/login",
                json={
                    "email": "unverified@example.com",
                    "password": "super-secret-password",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            {
                "code": "email_verification_required",
                "message": "Verify your email before logging in.",
                "context": {"resend_available_after": 0},
            },
        )

    def test_main_login_rejects_public_site_visitor_account(self):
        client = build_client()
        auth_response = SimpleNamespace(
            user=SimpleNamespace(
                id="auth-visitor",
                email="visitor@example.com",
                email_confirmed_at="2026-01-01T00:00:00Z",
                confirmed_at="2026-01-01T00:00:00Z",
            ),
            session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )
        local_user = {
            "id": 22,
            "auth_id": "auth-visitor",
            "tenant_id": None,
            "email": "visitor@example.com",
            "email_verified": True,
            "account_kind": "site_visitor",
            "account_status": "active",
        }

        with patch.object(auth_routes, "enforce_auth_rate_limit"), patch.object(
            auth_routes.supabase.auth,
            "sign_in_with_password",
            return_value=auth_response,
        ), patch.object(
            auth_routes,
            "get_local_user_by_auth_id",
            return_value=local_user,
        ), patch.object(
            auth_routes,
            "record_security_event",
        ):
            response = client.post(
                "/auth/login",
                json={
                    "email": "visitor@example.com",
                    "password": "super-secret-password",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["code"],
            "platform_account_required",
        )

    def test_main_user_status_does_not_authenticate_public_site_visitor(self):
        client = build_client()
        local_user = {
            "id": 22,
            "auth_id": "auth-visitor",
            "tenant_id": None,
            "email": "visitor@example.com",
            "account_kind": "site_visitor",
            "account_status": "active",
        }

        with patch.object(
            auth_routes,
            "get_authenticated_user_row",
            return_value=(SimpleNamespace(id="auth-visitor"), local_user),
        ):
            response = client.get("/auth/user_status")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["logged_in"])
        self.assertEqual(
            response.json()["account_state"],
            "platform_account_required",
        )


if __name__ == "__main__":
    unittest.main()
