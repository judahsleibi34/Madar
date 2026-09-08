import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from routes import (
    admin_account_access_routes,
    admin_billing_routes,
    admin_user_routes,
    auth_routes,
    mfa_routes,
)
from services import auth_service


ADMIN_USER = {
    "id": 99,
    "auth_id": "auth-admin",
    "tenant_id": None,
    "email": "admin@example.com",
    "user_type": "admin",
}
REGULAR_USER = {
    "id": 5,
    "auth_id": "auth-user",
    "tenant_id": 7,
    "email": "user@example.com",
    "user_type": "user",
}
TARGET_USER = {
    "id": 6,
    "auth_id": "auth-target",
    "tenant_id": 7,
    "email": "target@example.com",
    "user_type": "user",
}


class _FakeUsersQuery:
    def __init__(self, user):
        self.user = user

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def single(self):
        return self

    def execute(self):
        return SimpleNamespace(data=dict(self.user))


class _FakeServiceSupabase:
    def __init__(self, user):
        self.user = user

    def table(self, name):
        if name != "users":
            raise AssertionError(f"unexpected table {name}")
        return _FakeUsersQuery(self.user)


def build_auth_client():
    app = FastAPI()

    @app.get("/admin/aal2")
    def admin_aal2(request: Request, response: Response):
        _auth_user, user = auth_service.require_system_admin(
            request,
            response,
            require_aal2=True,
        )
        return {"ok": True, "user_id": user["id"]}

    @app.get("/admin/basic")
    def admin_basic(request: Request, response: Response):
        _auth_user, user = auth_service.require_system_admin(request, response)
        return {"ok": True, "user_id": user["id"]}

    return TestClient(app)


def resolve_target_with_context(request, response, admin_user):
    request.state.admin_account_access_context = {
        "admin_actor_user_id": admin_user["id"],
        "target_user_id": TARGET_USER["id"],
        "session_id": "session-1",
    }
    return dict(TARGET_USER)


class AdminAal2EnforcementTests(unittest.TestCase):
    def test_admin_aal1_is_denied_from_aal2_route(self):
        client = build_auth_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(
            auth_service,
            "service_supabase",
            _FakeServiceSupabase(ADMIN_USER),
        ), patch.object(auth_service, "get_current_aal", return_value={"current_level": "aal1"}):
            response = client.get("/admin/aal2", cookies={"madar_access_token": "access"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "aal2_required")

    def test_admin_aal2_is_allowed_on_aal2_route(self):
        client = build_auth_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(
            auth_service,
            "service_supabase",
            _FakeServiceSupabase(ADMIN_USER),
        ), patch.object(auth_service, "get_current_aal", return_value={"current_level": "aal2"}):
            response = client.get("/admin/aal2", cookies={"madar_access_token": "access"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "user_id": ADMIN_USER["id"]})

    def test_non_admin_does_not_gain_admin_access_with_aal2(self):
        client = build_auth_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-user", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(
            auth_service,
            "service_supabase",
            _FakeServiceSupabase(REGULAR_USER),
        ), patch.object(auth_service, "get_current_aal", return_value={"current_level": "aal2"}):
            response = client.get("/admin/aal2", cookies={"madar_access_token": "access"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Admin access is required")

    def test_admin_account_access_cannot_bypass_aal2_route(self):
        client = build_auth_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(
            auth_service,
            "service_supabase",
            _FakeServiceSupabase(ADMIN_USER),
        ), patch(
            "services.admin_account_access_service.resolve_admin_account_access_user",
            side_effect=resolve_target_with_context,
        ), patch.object(auth_service, "get_current_aal", return_value={"current_level": "aal2"}) as get_aal:
            response = client.get(
                "/admin/aal2",
                cookies={
                    "madar_access_token": "access",
                    "madar_admin_access_session": "admin-session",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "Admin account access is not allowed for this route",
        )
        get_aal.assert_not_called()

    def test_basic_admin_route_does_not_require_aal2(self):
        client = build_auth_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(
            auth_service,
            "service_supabase",
            _FakeServiceSupabase(ADMIN_USER),
        ), patch.object(auth_service, "get_current_aal") as get_aal:
            response = client.get("/admin/basic", cookies={"madar_access_token": "access"})

        self.assertEqual(response.status_code, 200)
        get_aal.assert_not_called()

    def test_sensitive_admin_routes_opt_into_aal2(self):
        app = FastAPI()
        app.include_router(admin_user_routes.router)
        app.include_router(admin_billing_routes.router)
        app.include_router(admin_account_access_routes.router)
        client = TestClient(app)

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            return_value=(SimpleNamespace(id="auth-admin"), dict(ADMIN_USER)),
        ) as require_admin, patch.object(
            admin_user_routes,
            "list_users_with_features",
            return_value={"items": [], "users": [], "pagination": {}},
        ):
            response = client.get("/admin/users")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(require_admin.call_args.kwargs["require_aal2"])

        with patch.object(
            admin_billing_routes,
            "require_system_admin",
            return_value=(SimpleNamespace(id="auth-admin"), dict(ADMIN_USER)),
        ) as require_admin, patch.object(
            admin_billing_routes,
            "apply_verified_billing_update",
            return_value={"tenant_id": 7, "id": "feature-1"},
        ), patch.object(admin_billing_routes, "record_audit_event"):
            response = client.post(
                "/admin/billing/features",
                json={
                    "tenant_id": 7,
                    "subscription_type": "full_platform",
                    "plan": "pro",
                    "builder_type": None,
                    "payment_status": "active",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(require_admin.call_args.kwargs["require_aal2"])

        with patch.object(
            admin_account_access_routes,
            "require_system_admin",
            return_value=(SimpleNamespace(id="auth-admin"), dict(ADMIN_USER)),
        ) as require_admin, patch.object(
            admin_account_access_routes,
            "generate_permission_code",
            return_value={"success": True},
        ):
            response = client.post(
                "/admin/account-access/generate",
                json={"email": "target@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(require_admin.call_args.kwargs["require_aal2"])

    def test_mfa_enrollment_remains_usable_without_aal2(self):
        app = FastAPI()
        app.include_router(mfa_routes.router)
        client = TestClient(app)
        enroll_response = SimpleNamespace(
            data=SimpleNamespace(
                id="factor-1",
                factor_type="totp",
                status="unverified",
                totp=SimpleNamespace(qr_code="qr", uri="otpauth://totp/example"),
            )
        )

        with patch.object(
            mfa_routes,
            "get_authenticated_user_row",
            return_value=(SimpleNamespace(id="auth-admin"), dict(ADMIN_USER)),
        ), patch.object(
            mfa_routes,
            "get_user_security_settings",
            return_value={"mfa_required": True},
        ), patch.object(
            mfa_routes,
            "get_request_mfa_client",
            return_value=SimpleNamespace(auth=SimpleNamespace(mfa=SimpleNamespace(enroll=MagicMock(return_value=enroll_response)))),
        ), patch.object(mfa_routes, "record_mfa_event"), patch.object(
            auth_service,
            "get_current_aal",
        ) as get_aal:
            response = client.post("/auth/mfa/enroll", json={"friendly_name": "Admin phone"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["factor"]["id"], "factor-1")
        get_aal.assert_not_called()

    def test_status_and_logout_do_not_require_aal2(self):
        app = FastAPI()
        app.include_router(auth_routes.router)
        client = TestClient(app)

        with patch.object(
            auth_routes,
            "get_authenticated_user_row",
            return_value=(SimpleNamespace(id="auth-admin"), dict(ADMIN_USER)),
        ), patch.object(
            auth_routes,
            "get_billing_summary_for_tenant",
            return_value={},
        ), patch.object(
            auth_routes,
            "ensure_csrf_token",
            return_value="csrf",
        ), patch.object(auth_service, "get_current_aal") as get_aal:
            status_response = client.get("/auth/user_status")

        with patch.object(auth_routes, "delete_auth_cookies") as delete_auth_cookies, patch.object(
            auth_service,
            "get_current_aal",
        ) as logout_get_aal:
            logout_response = client.post("/auth/log_out")

        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["logged_in"])
        self.assertEqual(logout_response.status_code, 200)
        delete_auth_cookies.assert_called_once()
        get_aal.assert_not_called()
        logout_get_aal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
