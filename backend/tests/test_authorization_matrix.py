import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from data_analysis import services as data_services
from data_analysis.routes import analysis_routes, cleaning_routes, data_routes, visualization_routes
from routes import (
    admin_account_access_routes,
    admin_billing_routes,
    admin_profile_routes,
    admin_user_routes,
    billing_routes,
    builder_routes,
    notification_routes,
    user_routes,
    website_routes,
)
from services.tenant_service import TenantContext
from tests.entitlement_test_support import EntitlementTestState


TENANT_A_USER = {
    "id": 1,
    "tenant_id": "tenant-a",
    "auth_id": "auth-user-1",
    "user_type": "user",
    "email": "user1@example.com",
}
TENANT_A_SECOND_USER = {
    **TENANT_A_USER,
    "id": 2,
    "auth_id": "auth-user-2",
    "email": "user2@example.com",
}
TENANT_B_USER = {
    **TENANT_A_USER,
    "id": 3,
    "tenant_id": "tenant-b",
    "auth_id": "auth-user-3",
    "email": "user3@example.com",
}
SYSTEM_ADMIN_USER = {
    "id": 99,
    "tenant_id": None,
    "auth_id": "auth-admin",
    "user_type": "admin",
    "email": "admin@example.com",
}


def fake_auth_result(user_data):
    return SimpleNamespace(id=user_data.get("auth_id")), dict(user_data)


def fake_require_regular_user_id(current_user):
    def _fake(user_id, request, response, **_kwargs):
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not logged in")

        if current_user.get("user_type") == "admin":
            raise HTTPException(status_code=403, detail="User access is required")

        if int(current_user["id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="User id does not match session")

        return fake_auth_result(current_user)

    return _fake


def fake_require_active_tenant_user_id(current_user):
    def _fake(user_id, request, response, **_kwargs):
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not logged in")
        if current_user.get("user_type") != "user":
            raise HTTPException(status_code=403, detail="User access is required")
        if current_user.get("tenant_id") is None:
            raise HTTPException(status_code=403, detail="User workspace access is required")
        if int(current_user["id"]) != int(user_id):
            raise HTTPException(status_code=403, detail="User id does not match session")
        return tenant_context(current_user)

    return _fake


def tenant_context(user=TENANT_A_USER, *, role="owner", status="active"):
    return TenantContext(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        auth_id=user["auth_id"],
        role=role,
        membership_status=status,
        user=dict(user),
        membership={"role": role, "status": status},
    )


def fake_tenant_context(user=TENANT_A_USER, *, role="owner", status="active"):
    if status != "active":
        return HTTPException(status_code=403, detail="Active tenant membership required")
    return tenant_context(user, role=role, status=status)


def build_data_client():
    app = FastAPI()
    app.include_router(data_routes.router)
    app.include_router(cleaning_routes.router)
    app.include_router(analysis_routes.router)
    app.include_router(visualization_routes.router)
    return TestClient(app)


def build_tenant_client():
    app = FastAPI()
    app.include_router(builder_routes.router)
    app.include_router(website_routes.router)
    app.include_router(billing_routes.router)
    return TestClient(app)


def build_user_client():
    app = FastAPI()
    app.include_router(user_routes.router)
    return TestClient(app)


def build_admin_client():
    app = FastAPI()
    app.include_router(admin_user_routes.router)
    app.include_router(admin_profile_routes.router)
    app.include_router(admin_account_access_routes.router)
    app.include_router(admin_billing_routes.router)
    return TestClient(app)


def build_notification_client():
    app = FastAPI()
    app.include_router(notification_routes.router)
    return TestClient(app)


def assert_no_private_path(test_case, response):
    body = str(response.json())
    test_case.assertNotIn("private_uploads", body)
    test_case.assertNotIn("private_generated_charts", body)
    test_case.assertNotIn("C:\\", body)
    test_case.assertNotIn("D:\\", body)


class DataRouteAuthorizationMatrixTests(unittest.TestCase):
    def setUp(self):
        self.entitlement_state = EntitlementTestState().activate_plan("tenant-a", "business")
        self.entitlement_state.allow_capability("tenant-b", "data_import")
        self.entitlement_state.allow_capability("tenant-b", "charts")
        self.entitlement_patch = self.entitlement_state.installed()
        self.entitlement_patch.__enter__()
        self.client = build_data_client()

    def tearDown(self):
        self.entitlement_patch.__exit__(None, None, None)

    def auth_patches(self, current_user):
        return (
            patch.object(data_routes, "require_active_tenant_user_id", side_effect=fake_require_active_tenant_user_id(current_user)),
            patch.object(analysis_routes, "require_regular_user_id", side_effect=fake_require_regular_user_id(current_user)),
            patch.object(data_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(cleaning_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(analysis_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(visualization_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(visualization_routes, "enforce_visualization_generation_rate_limit", return_value=None),
        )

    def test_data_read_owner_success_wrong_user_and_unauthenticated(self):
        payload = {"input_path": "dataset.csv"}

        with self.auth_patches(TENANT_A_USER)[0], \
             patch.object(data_routes, "enforce_data_workspace_rate_limit"), \
             patch.object(data_services, "process_read", return_value={"ok": True}) as service:
            owner = self.client.post("/users/1/data/read", json=payload)

        self.assertEqual(owner.status_code, 200)
        self.assertEqual(service.call_args.kwargs["tenant_id"], "tenant-a")
        self.assertEqual(service.call_args.kwargs["user_id"], "1")

        with self.auth_patches(TENANT_A_USER)[0]:
            wrong_user = self.client.post("/users/2/data/read", json=payload)

        with self.auth_patches(None)[0]:
            unauthenticated = self.client.post("/users/1/data/read", json=payload)

        self.assertEqual(wrong_user.status_code, 403)
        self.assertEqual(unauthenticated.status_code, 401)
        assert_no_private_path(self, wrong_user)
        assert_no_private_path(self, unauthenticated)

    def test_upload_export_cleaning_analysis_visualization_and_ai_reject_wrong_user(self):
        route_cases = [
            ("post", "/users/2/data/export", {"input_path": "dataset.csv"}),
            ("post", "/users/2/cleaning/export", {"input_path": "dataset.csv", "actions": []}),
            ("post", "/users/2/analysis/run", {"input_path": "dataset.csv", "analysis_requests": []}),
            ("post", "/users/2/analysis/assist", {"input_path": "dataset.csv", "question": "summary"}),
            ("post", "/users/2/analysis/ai", {"input_path": "dataset.csv", "user_message": "summary"}),
            ("post", "/users/2/visualization/create", {"input_path": "dataset.csv", "chart_config": {"chart_type": "bar"}}),
            ("post", "/users/2/visualization/columns/profile", {"input_path": "dataset.csv", "columns": ["a"]}),
        ]

        patches = self.auth_patches(TENANT_A_USER)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            for method, path, payload in route_cases:
                with self.subTest(path=path):
                    response = getattr(self.client, method)(path, json=payload)
                    self.assertEqual(response.status_code, 403)
                    assert_no_private_path(self, response)

    def test_admin_is_blocked_from_regular_data_workspace(self):
        with self.auth_patches(SYSTEM_ADMIN_USER)[0]:
            response = self.client.post("/users/99/data/read", json={"input_path": "dataset.csv"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User access is required")

    def test_cleaning_export_failure_does_not_leak_private_paths(self):
        patches = self.auth_patches(TENANT_A_USER)
        with patches[0], patches[3], \
             patch.object(
                 data_services,
                 "export_cleaned_dataframe",
                 side_effect=RuntimeError(r"D:\Madar\private_uploads\tenant-a\user-1\secret.csv"),
             ):
            response = self.client.post(
                "/users/1/cleaning/export",
                json={"input_path": "dataset.csv", "actions": []},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Could not export cleaned data.")
        assert_no_private_path(self, response)

    def test_private_chart_route_blocks_cross_user_and_cross_tenant(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chart_dir = root / "private_generated_charts" / "tenant_tenant-a" / "user_1"
            chart_dir.mkdir(parents=True)
            (chart_dir / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            patches = self.auth_patches(TENANT_A_USER)
            with patch.dict("os.environ", {"PRIVATE_CHARTS_DIR": str(root / "private_generated_charts")}), \
                 patches[0]:
                owner = self.client.get("/users/1/visualization/charts/chart.png")
                wrong_user = self.client.get("/users/2/visualization/charts/chart.png")

            patches = self.auth_patches(TENANT_B_USER)
            with patch.dict("os.environ", {"PRIVATE_CHARTS_DIR": str(root / "private_generated_charts")}), \
                 patches[0]:
                wrong_tenant = self.client.get("/users/3/visualization/charts/chart.png")

        self.assertEqual(owner.status_code, 200)
        self.assertEqual(wrong_user.status_code, 403)
        self.assertEqual(wrong_tenant.status_code, 403)
        assert_no_private_path(self, wrong_user)
        assert_no_private_path(self, wrong_tenant)


class TenantScopedRouteAuthorizationMatrixTests(unittest.TestCase):
    def setUp(self):
        self.entitlement_state = EntitlementTestState().allow_capability(
            "tenant-b", "response_management"
        )
        self.entitlement_patch = self.entitlement_state.installed()
        self.entitlement_patch.__enter__()
        self.client = build_tenant_client()

    def tearDown(self):
        self.entitlement_patch.__exit__(None, None, None)

    def test_website_settings_requires_active_matching_user_context(self):
        with patch.object(website_routes, "require_active_tenant_member", return_value=tenant_context()), \
             patch.object(website_routes, "ensure_settings_for_tenant", return_value={"tenant_id": "tenant-a"}):
            owner = self.client.get("/users/1/website/settings")
            wrong_user = self.client.get("/users/2/website/settings")

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            side_effect=HTTPException(status_code=403, detail="Active tenant membership required"),
        ):
            inactive = self.client.get("/website/settings")

        self.assertEqual(owner.status_code, 200)
        self.assertEqual(wrong_user.status_code, 403)
        self.assertEqual(inactive.status_code, 403)

    def test_billing_checkout_requires_membership_and_matching_user_alias(self):
        checkout = {"subscription_type": "individual_builder", "plan": "pro", "builder_type": "data"}
        with patch.object(billing_routes, "require_active_tenant_member", return_value=tenant_context()), \
             patch.object(billing_routes, "apply_pending_checkout_selection", return_value={"tenant_id": "tenant-a", **checkout}), \
             patch.object(billing_routes, "record_audit_event"):
            canonical = self.client.post("/billing/checkout", json=checkout)
            wrong_user = self.client.post("/users/2/billing/checkout", json=checkout)

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(wrong_user.status_code, 403)

    def test_builder_project_and_submission_cross_tenant_are_not_found(self):
        with patch.object(builder_routes, "require_active_tenant_member", return_value=tenant_context(TENANT_B_USER)), \
             patch.object(builder_routes, "service_supabase", _BuilderFakeSupabase()):
            project = self.client.get("/builder/projects/project-a")
            submissions = self.client.get("/builder/projects/project-a/form-submissions")

        self.assertEqual(project.status_code, 404)
        self.assertEqual(submissions.status_code, 404)
        self.assertEqual(project.json()["detail"], "Builder project not found")

    def test_builder_write_and_admin_boundaries(self):
        with patch.object(
            builder_routes,
            "require_builder_write_access",
            side_effect=HTTPException(status_code=403, detail="Builder write access required"),
        ):
            create_response = self.client.post("/builder/projects", json={"name": "Site", "slug": "site", "draft_schema": {}})

        with patch.object(
            builder_routes,
            "require_builder_admin_access",
            side_effect=HTTPException(status_code=403, detail="Builder admin access required"),
        ):
            archive_response = self.client.delete("/builder/projects/project-a")

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(archive_response.status_code, 403)


class UserAndAdminRouteAuthorizationMatrixTests(unittest.TestCase):
    def test_user_profile_routes_reject_wrong_user_and_admin_workspace_access(self):
        client = build_user_client()

        with patch.object(user_routes, "require_regular_user_id", side_effect=fake_require_regular_user_id(TENANT_A_USER)):
            wrong_info = client.post("/users/2/info")
            wrong_profile = client.put("/users/2/profile", json={"first_name": "Ada"})

        with patch.object(user_routes, "require_regular_user_id", side_effect=fake_require_regular_user_id(SYSTEM_ADMIN_USER)):
            admin_workspace = client.post("/users/99/info")

        self.assertEqual(wrong_info.status_code, 403)
        self.assertEqual(wrong_profile.status_code, 403)
        self.assertEqual(admin_workspace.status_code, 403)

    def test_admin_routes_reject_regular_user_and_allow_system_admin(self):
        client = build_admin_client()

        admin_patches = (
            patch.object(admin_user_routes, "require_system_admin", return_value=fake_auth_result(SYSTEM_ADMIN_USER)),
            patch.object(admin_profile_routes, "require_system_admin", return_value=fake_auth_result(SYSTEM_ADMIN_USER)),
            patch.object(admin_account_access_routes, "require_system_admin", return_value=fake_auth_result(SYSTEM_ADMIN_USER)),
            patch.object(admin_billing_routes, "require_system_admin", return_value=fake_auth_result(SYSTEM_ADMIN_USER)),
        )
        with admin_patches[0], admin_patches[1], admin_patches[2], admin_patches[3], \
             patch.object(admin_user_routes, "list_users_with_features", return_value={"items": [], "users": [], "pagination": {}}), \
             patch.object(admin_profile_routes, "service_supabase"), \
             patch.object(admin_account_access_routes, "generate_permission_code", return_value={"success": True}), \
             patch.object(admin_billing_routes, "apply_verified_billing_update", return_value={"tenant_id": "tenant-a", "id": "feature-1"}), \
             patch.object(admin_billing_routes, "record_audit_event"):
            users = client.get("/admin/users")
            profile = client.post("/admin/profile/info")
            access = client.post("/admin/account-access/generate", json={"email": "target@example.com"})
            billing = client.post(
                "/admin/billing/features",
                json={
                    "tenant_id": 1,
                    "subscription_type": "individual_builder",
                    "plan": "pro",
                    "builder_type": "data",
                    "payment_status": "active",
                },
            )

        self.assertEqual(users.status_code, 200)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(access.status_code, 200)
        self.assertEqual(billing.status_code, 200)

        for module in (admin_user_routes, admin_profile_routes, admin_account_access_routes, admin_billing_routes):
            with self.subTest(module=module.__name__), \
                 patch.object(
                     module,
                     "require_system_admin",
                     side_effect=HTTPException(status_code=403, detail="Admin access is required"),
                 ):
                route = {
                    admin_user_routes: (client.get, "/admin/users", None),
                    admin_profile_routes: (client.post, "/admin/profile/info", None),
                    admin_account_access_routes: (client.post, "/admin/account-access/generate", {"email": "target@example.com"}),
                    admin_billing_routes: (
                        client.post,
                        "/admin/billing/features",
                        {
                            "tenant_id": 1,
                            "subscription_type": "individual_builder",
                            "plan": "pro",
                            "builder_type": "data",
                            "payment_status": "active",
                        },
                    ),
                }[module]
                method, path, payload = route
                response = method(path, json=payload) if payload is not None else method(path)
                self.assertEqual(response.status_code, 403)


class NotificationAuthorizationMatrixTests(unittest.TestCase):
    def test_notifications_require_auth_and_scope_service_calls_to_session_user(self):
        client = build_notification_client()

        with patch.object(
            notification_routes,
            "get_current_tenant_context",
            side_effect=HTTPException(status_code=401, detail="Not logged in"),
        ):
            unauthenticated = client.get("/notifications")

        with patch.object(
            notification_routes,
            "get_current_tenant_context",
            return_value=SimpleNamespace(
                tenant_id=TENANT_A_USER["tenant_id"],
                user_id=TENANT_A_USER["id"],
            ),
        ), patch.object(
            notification_routes,
            "list_user_notifications",
            return_value={"items": [], "unread_count": 0},
        ) as list_notifications:
            owner = client.get("/notifications")

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(owner.status_code, 200)
        list_notifications.assert_called_once_with(
            tenant_id=TENANT_A_USER["tenant_id"],
            user_id=TENANT_A_USER["id"],
            limit=30,
            unread_only=False,
        )

    def test_push_public_key_is_intentionally_public(self):
        client = build_notification_client()

        with patch.object(notification_routes, "get_web_push_public_config", return_value={"public_key": ""}):
            response = client.get("/notifications/push-public-key")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "public_key": ""})


class _BuilderResponse:
    def __init__(self, data):
        self.data = data


class _BuilderQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def neq(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        rows = self.rows
        for key, value in self.filters:
            rows = [row for row in rows if row.get(key) == value]
        return _BuilderResponse(rows)


class _BuilderFakeSupabase:
    def __init__(self):
        self.tables = {
            "builder_projects": [
                {"id": "project-a", "tenant_id": "tenant-a", "status": "published", "draft_schema": {}}
            ],
            "builder_form_submissions": [
                {"id": "submission-a", "tenant_id": "tenant-a", "project_id": "project-a"}
            ],
        }

    def table(self, table_name):
        return _BuilderQuery(self.tables.get(table_name, []))


if __name__ == "__main__":
    unittest.main()
