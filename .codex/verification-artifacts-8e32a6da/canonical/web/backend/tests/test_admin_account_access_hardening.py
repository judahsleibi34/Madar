import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient

from routes import (
    admin_account_access_routes,
    auth_routes,
    billing_routes,
    builder_routes,
    mfa_routes,
    user_routes,
)
from services import auth_service


ADMIN_USER = {
    "id": 99,
    "auth_id": "auth-admin",
    "tenant_id": None,
    "email": "admin@example.com",
    "user_type": "admin",
}
TARGET_USER = {
    "id": 5,
    "auth_id": "auth-target",
    "tenant_id": 7,
    "email": "target@example.com",
    "user_type": "user",
}


class _FakeUsersQuery:
    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def single(self):
        return self

    def execute(self):
        return SimpleNamespace(data=dict(ADMIN_USER))


class _FakeServiceSupabase:
    def table(self, name):
        if name != "users":
            raise AssertionError(f"unexpected table {name}")
        return _FakeUsersQuery()


def build_auth_probe_client():
    app = FastAPI()

    @app.get("/allowed")
    def allowed(request: Request, response: Response):
        _auth_user, user = auth_service.get_authenticated_user_row(request, response)
        return {
            "user_id": user["id"],
            "admin_access": auth_service.get_admin_account_access_context(request),
        }

    @app.get("/denied")
    def denied(request: Request, response: Response):
        auth_service.get_authenticated_user_row(
            request,
            response,
            allow_admin_account_access=False,
        )
        return {"ok": True}

    return TestClient(app)


def build_route_client(*routers):
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    return TestClient(app)


def resolve_target_with_context(request, response, admin_user):
    request.state.admin_account_access_context = {
        "admin_actor_user_id": admin_user["id"],
        "target_user_id": TARGET_USER["id"],
        "session_id": "session-1",
    }
    return dict(TARGET_USER)


class AdminAccountAccessHardeningTests(unittest.TestCase):
    def test_allowed_support_route_returns_target_context_and_header(self):
        client = build_auth_probe_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(auth_service, "service_supabase", _FakeServiceSupabase()), patch(
            "services.admin_account_access_service.resolve_admin_account_access_user",
            side_effect=resolve_target_with_context,
        ):
            response = client.get(
                "/allowed",
                cookies={
                    "madar_access_token": "access",
                    "madar_admin_access_session": "admin-session",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], TARGET_USER["id"])
        self.assertEqual(
            response.json()["admin_access"],
            {
                "admin_actor_user_id": ADMIN_USER["id"],
                "target_user_id": TARGET_USER["id"],
                "session_id": "session-1",
            },
        )
        self.assertEqual(response.headers["x-madar-admin-account-access"], "true")

    def test_denied_route_rejects_valid_admin_account_access_session(self):
        client = build_auth_probe_client()

        with patch.object(
            auth_service.supabase.auth,
            "get_user",
            return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z")
            ),
        ), patch.object(auth_service, "service_supabase", _FakeServiceSupabase()), patch(
            "services.admin_account_access_service.resolve_admin_account_access_user",
            side_effect=resolve_target_with_context,
        ):
            response = client.get(
                "/denied",
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

    def test_password_change_denies_admin_account_access_before_mutation(self):
        client = build_route_client(auth_routes.router)

        with patch.object(
            auth_routes,
            "get_authenticated_user_row",
            side_effect=HTTPException(
                status_code=403,
                detail="Admin account access is not allowed for this route",
            ),
        ) as get_user, patch.object(
            auth_routes.supabase.auth,
            "sign_in_with_password",
        ) as sign_in:
            response = client.put(
                "/auth/password/change",
                json={
                    "current_password": "old-password123",
                    "new_password": "new-password123",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(sign_in.called)
        self.assertFalse(get_user.call_args.kwargs["allow_admin_account_access"])

    def test_mfa_route_denies_admin_account_access(self):
        client = build_route_client(mfa_routes.router)

        with patch.object(
            mfa_routes,
            "get_authenticated_user_row",
            side_effect=HTTPException(
                status_code=403,
                detail="Admin account access is not allowed for this route",
            ),
        ) as get_user, patch.object(
            mfa_routes.supabase.auth.mfa,
            "list_factors",
        ) as list_factors:
            response = client.get("/auth/mfa/status")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(list_factors.called)
        self.assertFalse(get_user.call_args.kwargs["allow_admin_account_access"])

    def test_billing_checkout_denies_admin_account_access(self):
        client = build_route_client(billing_routes.router)

        with patch.object(
            billing_routes,
            "require_active_tenant_member",
            side_effect=HTTPException(
                status_code=403,
                detail="Admin account access is not allowed for this route",
            ),
        ) as require_member, patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
        ) as apply_checkout:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "full_platform",
                    "plan": "pro",
                    "builder_type": None,
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(apply_checkout.called)
        self.assertFalse(require_member.call_args.kwargs["allow_admin_account_access"])

    def test_builder_publish_denies_admin_account_access(self):
        client = build_route_client(builder_routes.router)

        with patch.object(
            builder_routes,
            "require_builder_write_access",
            side_effect=HTTPException(
                status_code=403,
                detail="Admin account access is not allowed for this route",
            ),
        ), patch.object(builder_routes, "get_project_for_tenant") as get_project:
            response = client.post("/builder/projects/project-1/publish")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_project.called)

    def test_admin_account_access_management_rejects_account_access_context(self):
        client = build_route_client(admin_account_access_routes.router)

        with patch.object(
            admin_account_access_routes,
            "require_system_admin",
            side_effect=HTTPException(
                status_code=403,
                detail="Admin account access is not allowed for this route",
            ),
        ) as require_admin, patch.object(
            admin_account_access_routes,
            "generate_permission_code",
        ) as generate_code:
            response = client.post(
                "/admin/account-access/generate",
                json={"email": "target@example.com"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(generate_code.called)
        require_admin.assert_called_once()

    def test_admin_account_access_end_can_clear_account_access_context(self):
        client = build_route_client(admin_account_access_routes.router)

        with patch.object(
            admin_account_access_routes,
            "require_system_admin",
            return_value=(SimpleNamespace(id="auth-admin"), dict(ADMIN_USER)),
        ) as require_admin, patch.object(
            admin_account_access_routes,
            "end_admin_account_access_session",
            return_value={"success": True},
        ) as end_session:
            response = client.post("/admin/account-access/end")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(require_admin.call_args.kwargs["reject_admin_account_access"])
        end_session.assert_called_once()

    def test_user_info_remains_allowed_for_support_read(self):
        client = build_route_client(user_routes.router)

        with patch.object(
            user_routes,
            "require_regular_user_id",
            return_value=(SimpleNamespace(id="auth-target"), dict(TARGET_USER)),
        ) as require_user, patch.object(
            user_routes,
            "get_billing_summary_for_tenant",
            return_value={},
        ):
            response = client.post(f"/users/{TARGET_USER['id']}/info")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("allow_admin_account_access", require_user.call_args.kwargs)

    def test_normal_user_sensitive_route_still_uses_deny_flag_without_blocking(self):
        client = build_route_client(billing_routes.router)
        checkout = {
            "subscription_type": "full_platform",
            "plan": "pro",
            "builder_type": None,
        }
        context = SimpleNamespace(tenant_id=7, user_id=5)

        with patch.object(
            billing_routes,
            "require_active_tenant_member",
            return_value=context,
        ) as require_member, patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value={
                "tenant_id": 7,
                **checkout,
                "payment_status": "pending",
            },
        ), patch.object(billing_routes, "record_audit_event"):
            response = client.post("/billing/checkout", json=checkout)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(require_member.call_args.kwargs["allow_admin_account_access"])


if __name__ == "__main__":
    unittest.main()
