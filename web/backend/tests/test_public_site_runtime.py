"""The hosted first-render contract uses one publication context operation."""

import unittest
import copy
import os
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from routes import public_site_routes as routes
from services import commercial_access_service
from tests.test_commercial_authority import snapshot


SETTINGS = {
    "id": 10,
    "tenant_id": 1,
    "subdomain": "alpha",
    "standard_path_slug": "alpha",
    "published_project_id": "project-a",
}
SCHEMA = {
    "defaultPageId": "home",
    "siteChrome": {"brand": "Alpha"},
    "theme": {},
    "forms": [],
    "pages": [
        {"id": "home", "slug": "/", "name": "Home", "sections": []},
        {"id": "secret", "slug": "/secret", "name": "Secret", "visibility": "members", "sections": []},
    ],
}
PROJECT = {
    "id": "project-a",
    "tenant_id": 1,
    "name": "Alpha",
    "slug": "alpha",
    "status": "published",
    "published_schema": SCHEMA,
    "published_version": 1,
    "published_revision": 1,
    "schema_version": 1,
    "last_published_at": "2026-09-29T00:00:00Z",
    "updated_at": "2026-09-29T00:00:00Z",
}


class RemoteContext:
    def __init__(self, data=None, error=None):
        self.data = data if data is not None else [
            {"settings": SETTINGS, "tenant_active": True, "project": PROJECT}
        ]
        self.error = error
        self.calls = []

    def rpc(self, name, args):
        self.calls.append((name, args))
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.data)

    def table(self, name):
        raise AssertionError(f"unexpected additional remote read: {name}")


class PublicSiteRuntimeTests(unittest.TestCase):
    def request(self, remote, *, host="madarportal.com", visitor=None, access=None, commercial=False):
        with ExitStack() as stack:
            stack.enter_context(patch.object(routes, "service_supabase", remote))
            stack.enter_context(patch.object(routes, "enforce_public_rate_limit"))
            if not commercial:
                stack.enter_context(patch.object(routes, "require_public_runtime_entitlement"))
            else:
                stack.enter_context(patch.dict(os.environ, {"COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS": "true"}))
                stack.enter_context(patch.object(commercial_access_service, "service_supabase", remote))
            if visitor is None:
                stack.enter_context(patch.object(
                    routes, "get_authenticated_user_row",
                    side_effect=routes.HTTPException(status_code=401),
                ))
            elif isinstance(visitor, Exception):
                stack.enter_context(patch.object(routes, "get_authenticated_user_row", side_effect=visitor))
            else:
                stack.enter_context(patch.object(routes, "get_authenticated_user_row", return_value=visitor))
            stack.enter_context(patch.object(routes, "get_tenant_site_access", return_value=access))
            stack.enter_context(patch.object(routes, "has_project_permission", return_value=bool(access)))
            result = TestClient(app).get("/public/sites/alpha/runtime", headers={"host": host})
        return result

    def test_anonymous_runtime_uses_one_remote_context_read_and_redacts_protected_page(self):
        remote = RemoteContext()
        result = self.request(remote)
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["visitor"], {"logged_in": False, "user": None})
        self.assertEqual([page["id"] for page in body["project"]["published_schema"]["pages"]], ["home"])
        self.assertEqual(len(remote.calls), 1)
        self.assertEqual(remote.calls[0][0], "get_public_site_runtime_context")
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.assertEqual(result.headers["CDN-Cache-Control"], "no-store")

    def commercial_remote(self, *, consolidated=True, state=None):
        state = snapshot(tenant=1) if state is None else state
        settings = copy.deepcopy(SETTINGS)
        if consolidated:
            settings["_commercial_snapshot"] = state
        class Remote(RemoteContext):
            def execute(self):
                if self.calls[-1][0] == "resolve_commercial_access":
                    return SimpleNamespace(data=state)
                return super().execute()
        return Remote(data=[{"settings": settings, "tenant_active": True, "project": PROJECT}])

    def test_schema_114_bridge_proves_two_sequential_remote_calls(self):
        remote = self.commercial_remote(consolidated=False)
        result = self.request(remote, commercial=True)
        self.assertEqual(result.status_code, 200)
        self.assertEqual([call[0] for call in remote.calls], ["get_public_site_runtime_context", "resolve_commercial_access"])

    def test_schema_115_real_entitlement_path_uses_exactly_one_remote_call(self):
        for enforced in ("false", "true"):
            with self.subTest(enforced=enforced), patch.dict(os.environ, {"COMMERCIAL_ENTITLEMENTS_ENFORCED": enforced}):
                remote = self.commercial_remote()
                result = self.request(remote, commercial=True)
                self.assertEqual(result.status_code, 200)
                self.assertEqual([call[0] for call in remote.calls], ["get_public_site_runtime_context"])
                self.assertNotIn("commercial", str(result.json()).lower())

    def test_consolidated_hold_denied_under_bypass_without_second_read(self):
        state = snapshot(tenant=1, commercial_suspended_at="2026-09-30T00:00:00Z")
        with patch.dict(os.environ, {"COMMERCIAL_ENTITLEMENTS_ENFORCED": "false"}):
            remote = self.commercial_remote(state=state)
            result = self.request(remote, commercial=True)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(len(remote.calls), 1)
        self.assertEqual(result.json()["detail"]["code"], "tenant_service_unavailable")
        self.assertNotIn("suspended", str(result.json()))

    def test_malformed_cross_tenant_or_missing_consolidated_snapshot_fails_closed(self):
        for state in (None, {}, snapshot(tenant=2), snapshot(tenant=1, contract_version=116)):
            remote = self.commercial_remote()
            remote.data[0]["settings"]["_commercial_snapshot"] = state
            result = self.request(remote, commercial=True)
            self.assertEqual(result.status_code, 503)
            self.assertEqual(len(remote.calls), 1)

    def test_hosted_hostname_disables_legacy_alias(self):
        remote = RemoteContext()
        result = self.request(remote, host="alpha.madarportal.com")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(remote.calls[0][1]["p_allow_legacy_alias"], False)

    def test_public_non_home_page_is_available_in_initial_runtime_schema(self):
        public_schema = {
            **SCHEMA,
            "pages": [
                SCHEMA["pages"][0],
                {"id": "team", "slug": "/about/team", "name": "Team", "sections": []},
            ],
        }
        remote = RemoteContext(data=[{
            "settings": SETTINGS,
            "tenant_active": True,
            "project": {**PROJECT, "published_schema": public_schema},
        }])
        result = self.request(remote)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            [page["slug"] for page in result.json()["project"]["published_schema"]["pages"]],
            ["/", "/about/team"],
        )

    def test_hosted_path_and_hostname_mismatch_is_rejected_before_rpc(self):
        remote = RemoteContext()
        result = self.request(remote, host="beta.madarportal.com")
        self.assertEqual(result.status_code, 404)
        self.assertEqual(remote.calls, [])

    def test_entirely_protected_publication_returns_no_private_page_to_anonymous_visitor(self):
        protected_schema = {
            **SCHEMA,
            "defaultPageId": "secret",
            "pages": [{**SCHEMA["pages"][1], "slug": "/"}],
        }
        remote = RemoteContext(data=[{
            "settings": SETTINGS,
            "tenant_active": True,
            "project": {**PROJECT, "published_schema": protected_schema},
        }])
        result = self.request(remote)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["project"]["published_schema"]["pages"], [])
        self.assertFalse(result.json()["visitor"]["logged_in"])

    def test_same_tenant_member_may_receive_authorized_protected_page(self):
        result = self.request(
            RemoteContext(),
            visitor=(None, {"id": 42, "tenant_id": 1, "full_name": "Member"}),
            access={"tenant_id": 1, "user_id": 42, "role": "member", "status": "active"},
        )
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["visitor"]["logged_in"])
        self.assertEqual(
            [page["id"] for page in result.json()["project"]["published_schema"]["pages"]],
            ["home", "secret"],
        )
        self.assertEqual(result.headers["Cache-Control"], "private, no-store")
        self.assertEqual(result.headers["CDN-Cache-Control"], "no-store")

    def test_cross_tenant_or_unauthorized_session_gets_no_protected_page(self):
        for tenant_id in (1, 2):
            with self.subTest(tenant_id=tenant_id):
                result = self.request(
                    RemoteContext(),
                    visitor=(None, {"id": 42, "tenant_id": tenant_id}),
                    access=None,
                )
                self.assertEqual(result.status_code, 200)
                self.assertFalse(result.json()["visitor"]["logged_in"])
                self.assertEqual(
                    [page["id"] for page in result.json()["project"]["published_schema"]["pages"]],
                    ["home"],
                )

    def test_missing_inactive_unbound_and_invalid_publication_fail_closed(self):
        cases = [
            ([], 404),
            ([{"settings": SETTINGS, "tenant_active": False, "project": PROJECT}], 404),
            ([{"settings": SETTINGS, "tenant_active": True, "project": None}], 404),
            ([{"settings": SETTINGS, "tenant_active": True, "project": {**PROJECT, "status": "draft"}}], 404),
            ([{"settings": SETTINGS, "tenant_active": True, "project": {**PROJECT, "tenant_id": 2}}], 409),
            ([{"settings": SETTINGS, "tenant_active": True, "project": {**PROJECT, "id": "unbound"}}], 409),
            ([{"settings": SETTINGS, "tenant_active": "true", "project": PROJECT}], 503),
            ([{"settings": SETTINGS, "tenant_active": True, "project": PROJECT}] * 2, 409),
        ]
        for data, status in cases:
            with self.subTest(status=status, data=data):
                result = self.request(RemoteContext(data=data))
                self.assertEqual(result.status_code, status)

    def test_remote_failure_is_controlled_and_does_not_use_fallback(self):
        remote = RemoteContext(error=RuntimeError("network unavailable"))
        result = self.request(remote)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(len(remote.calls), 1)

    def test_exact_missing_function_uses_complete_legacy_bridge(self):
        error = RuntimeError("missing function")
        error.code = "PGRST202"
        remote = RemoteContext(error=error)
        with patch.object(routes, "service_supabase", remote), patch.object(
            routes, "enforce_public_rate_limit"
        ), patch.object(routes, "require_public_runtime_entitlement"), patch.object(
            routes, "resolve_website_settings", return_value=SETTINGS
        ) as settings_read, patch.object(
            routes, "get_bound_published_project", return_value=PROJECT
        ) as project_read:
            result = TestClient(app).get("/public/sites/alpha/runtime", headers={"host": "madarportal.com"})
        self.assertEqual(result.status_code, 200)
        settings_read.assert_called_once()
        project_read.assert_called_once_with(SETTINGS)


if __name__ == "__main__":
    unittest.main()
