import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from data_analysis import services as data_services
from data_analysis.routes import analysis_routes, cleaning_routes, data_routes, visualization_routes
from services import rate_limit_service
from services.rate_limit_service import InMemoryRateLimitStore


def fake_require_regular_user_id(user_id, request, response):
    return SimpleNamespace(id=f"auth-{user_id}"), {
        "id": int(user_id),
        "tenant_id": "tenant-a",
        "user_type": "user",
    }


class DataWorkspaceRateLimitTests(unittest.TestCase):
    def setUp(self):
        rate_limit_service._store = None
        rate_limit_service._memory_store = InMemoryRateLimitStore()
        self.auth_patch = patch.object(
            data_routes,
            "require_regular_user_id",
            side_effect=fake_require_regular_user_id,
        )
        self.auth_patch.start()

    def tearDown(self):
        self.auth_patch.stop()
        rate_limit_service._store = None
        rate_limit_service._memory_store = InMemoryRateLimitStore()

    def build_client(self):
        app = FastAPI()
        app.include_router(data_routes.router)
        app.include_router(cleaning_routes.router)
        app.include_router(analysis_routes.router)
        app.include_router(visualization_routes.router)
        return TestClient(app)

    @contextmanager
    def rate_limit_config(self, *, limit_attr, window_attr, limit=1):
        store = InMemoryRateLimitStore()
        with patch.object(rate_limit_service, "_store", store), \
             patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True), \
             patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "127.0.0.1,::1"), \
             patch.object(rate_limit_service, limit_attr, limit), \
             patch.object(rate_limit_service, window_attr, 60):
            yield

    def assert_json_route_is_limited(
        self,
        *,
        path,
        payload,
        service_name,
        limit_attr,
        window_attr,
    ):
        client = self.build_client()

        with self.rate_limit_config(limit_attr=limit_attr, window_attr=window_attr), \
             patch.object(data_services, service_name, return_value={"ok": True}):
            first = client.post(path, json=payload)
            second = client.post(path, json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"ok": True})
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], "Too many requests. Please try again later.")

    def test_upload_returns_429_after_configured_limit(self):
        client = self.build_client()

        with self.rate_limit_config(
            limit_attr="DATA_UPLOAD_RATE_LIMIT_LIMIT",
            window_attr="DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
        ), patch.object(
            data_services,
            "process_upload",
            new=AsyncMock(return_value={"ok": True}),
        ):
            first = client.post(
                "/users/1/data/upload",
                files={"file": ("data.csv", b"value\n1\n", "text/csv")},
            )
            second = client.post(
                "/users/1/data/upload",
                files={"file": ("data.csv", b"value\n1\n", "text/csv")},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"ok": True})
        self.assertEqual(second.status_code, 429)

    def test_data_read_returns_429_after_configured_limit(self):
        self.assert_json_route_is_limited(
            path="/users/1/data/read",
            payload={"input_path": "https://example.com/data.csv"},
            service_name="process_read",
            limit_attr="DATA_UPLOAD_RATE_LIMIT_LIMIT",
            window_attr="DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
        )

    def test_cleaning_route_returns_429_after_configured_limit(self):
        self.assert_json_route_is_limited(
            path="/users/1/cleaning/inspect",
            payload={"input_path": "uploads/example.csv"},
            service_name="inspect_dataset",
            limit_attr="DATA_WORKSPACE_RATE_LIMIT_LIMIT",
            window_attr="DATA_WORKSPACE_RATE_LIMIT_WINDOW_SECONDS",
        )

    def test_analysis_run_returns_429_after_configured_limit(self):
        self.assert_json_route_is_limited(
            path="/users/1/analysis/run",
            payload={
                "input_path": "uploads/example.csv",
                "cleaning_actions": [],
                "analysis_requests": [],
            },
            service_name="run_analysis",
            limit_attr="DATA_ANALYSIS_RATE_LIMIT_LIMIT",
            window_attr="DATA_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS",
        )

    def test_analysis_assist_returns_429_after_configured_limit(self):
        self.assert_json_route_is_limited(
            path="/users/1/analysis/assist",
            payload={
                "input_path": "uploads/example.csv",
                "cleaning_actions": [],
                "question": "What changed?",
            },
            service_name="run_assisted_analysis",
            limit_attr="DATA_ANALYSIS_RATE_LIMIT_LIMIT",
            window_attr="DATA_ANALYSIS_RATE_LIMIT_WINDOW_SECONDS",
        )

    def test_visualization_create_returns_429_after_configured_limit(self):
        self.assert_json_route_is_limited(
            path="/users/1/visualization/create",
            payload={
                "input_path": "uploads/example.csv",
                "cleaning_actions": [],
                "chart_config": {"chart_type": "bar"},
            },
            service_name="create_visualization",
            limit_attr="DATA_VISUALIZATION_RATE_LIMIT_LIMIT",
            window_attr="DATA_VISUALIZATION_RATE_LIMIT_WINDOW_SECONDS",
        )

    def test_visualization_create_has_tenant_burst_bucket_across_users(self):
        client = self.build_client()
        payload = {
            "input_path": "uploads/example.csv",
            "cleaning_actions": [],
            "chart_config": {"chart_type": "bar"},
        }
        store = InMemoryRateLimitStore()

        with patch.object(rate_limit_service, "_store", store), \
             patch.object(rate_limit_service, "RATE_LIMIT_ENABLED", True), \
             patch.object(rate_limit_service, "TRUSTED_PROXY_IPS", "127.0.0.1,::1"), \
             patch.object(rate_limit_service, "DATA_VISUALIZATION_RATE_LIMIT_LIMIT", 10), \
             patch.object(rate_limit_service, "DATA_VISUALIZATION_RATE_LIMIT_WINDOW_SECONDS", 60), \
             patch.object(rate_limit_service, "DATA_VISUALIZATION_TENANT_RATE_LIMIT_LIMIT", 2), \
             patch.object(rate_limit_service, "DATA_VISUALIZATION_TENANT_RATE_LIMIT_WINDOW_SECONDS", 60), \
             patch.object(data_services, "create_visualization", return_value={"ok": True}):
            first = client.post("/users/1/visualization/create", json=payload)
            second = client.post("/users/2/visualization/create", json=payload)
            limited = client.post("/users/3/visualization/create", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)

    def test_visualization_profile_returns_429_after_configured_limit(self):
        self.assert_json_route_is_limited(
            path="/users/1/visualization/columns/profile",
            payload={
                "input_path": "uploads/example.csv",
                "cleaning_actions": [],
                "columns": ["answer"],
            },
            service_name="profile_visualization_columns",
            limit_attr="DATA_VISUALIZATION_RATE_LIMIT_LIMIT",
            window_attr="DATA_VISUALIZATION_RATE_LIMIT_WINDOW_SECONDS",
        )

    def test_different_users_get_separate_buckets(self):
        client = self.build_client()
        payload = {"input_path": "https://example.com/data.csv"}

        with self.rate_limit_config(
            limit_attr="DATA_UPLOAD_RATE_LIMIT_LIMIT",
            window_attr="DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
        ), patch.object(data_services, "process_read", return_value={"ok": True}):
            first = client.post("/users/1/data/read", json=payload)
            limited = client.post("/users/1/data/read", json=payload)
            other_user = client.post("/users/2/data/read", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(other_user.status_code, 200)

    def test_user_override_changes_only_that_users_limit(self):
        client = self.build_client()
        payload = {"input_path": "https://example.com/data.csv"}
        overrides = '{"1":{"read":{"limit":2,"window_seconds":60}}}'

        with self.rate_limit_config(
            limit_attr="DATA_UPLOAD_RATE_LIMIT_LIMIT",
            window_attr="DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
            limit=10,
        ), patch.dict("os.environ", {"DATA_WORKSPACE_RATE_LIMIT_USER_OVERRIDES": overrides}), \
             patch.object(data_services, "process_read", return_value={"ok": True}):
            first = client.post("/users/1/data/read", json=payload)
            second = client.post("/users/1/data/read", json=payload)
            limited = client.post("/users/1/data/read", json=payload)
            other_user = client.post("/users/2/data/read", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(other_user.status_code, 200)

    def test_tenant_user_override_takes_precedence(self):
        client = self.build_client()
        payload = {"input_path": "https://example.com/data.csv"}
        overrides = (
            '{"1":{"read":{"limit":5,"window_seconds":60}},'
            '"tenant:tenant-a:user:1":{"read":{"limit":1,"window_seconds":60}}}'
        )

        with self.rate_limit_config(
            limit_attr="DATA_UPLOAD_RATE_LIMIT_LIMIT",
            window_attr="DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
            limit=10,
        ), patch.dict("os.environ", {"DATA_WORKSPACE_RATE_LIMIT_USER_OVERRIDES": overrides}), \
             patch.object(data_services, "process_read", return_value={"ok": True}):
            first = client.post("/users/1/data/read", json=payload)
            limited = client.post("/users/1/data/read", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(limited.status_code, 429)

    def test_untrusted_spoofed_forwarded_headers_do_not_bypass_workspace_limit(self):
        client = self.build_client()
        payload = {"input_path": "https://example.com/data.csv"}

        with self.rate_limit_config(
            limit_attr="DATA_UPLOAD_RATE_LIMIT_LIMIT",
            window_attr="DATA_UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
            limit=2,
        ), patch.object(data_services, "process_read", return_value={"ok": True}):
            first = client.post(
                "/users/1/data/read",
                json=payload,
                headers={"x-forwarded-for": "203.0.113.1"},
            )
            second = client.post(
                "/users/1/data/read",
                json=payload,
                headers={"x-forwarded-for": "203.0.113.2"},
            )
            limited = client.post(
                "/users/1/data/read",
                json=payload,
                headers={"x-forwarded-for": "203.0.113.3"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)


if __name__ == "__main__":
    unittest.main()
