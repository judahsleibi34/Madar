import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import public_site_routes, website_routes
from services import website_settings_service
from tests.entitlement_test_support import installed_business_fixture


_entitlement_fixture = installed_business_fixture(7)


def setUpModule():
    _entitlement_fixture.__enter__()


def tearDownModule():
    _entitlement_fixture.__exit__(None, None, None)


def build_website_client():
    app = FastAPI()
    app.include_router(website_routes.router)
    return TestClient(app)


def build_public_client(fake_supabase):
    app = FastAPI()
    app.include_router(public_site_routes.router)
    return TestClient(app)


def fake_auth_result(user_data):
    return object(), user_data


def fake_tenant_context(tenant_id=7, user_id=3):
    return SimpleNamespace(tenant_id=tenant_id, user_id=user_id)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = []
        self.not_null_columns = set()
        self.limit_count = None
        self.order_column = None
        self.order_desc = False

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        if value == "null":
            self.not_null_columns.add(column)
        return self

    def order(self, column, desc=False):
        self.order_column = column
        self.order_desc = desc
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = list(self.supabase.tables.get(self.table_name, []))

        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]

        for column in self.not_null_columns:
            rows = [row for row in rows if row.get(column) is not None]

        if self.order_column:
            rows = sorted(
                rows,
                key=lambda row: row.get(self.order_column) or "",
                reverse=self.order_desc,
            )

        if self.limit_count is not None:
            rows = rows[: self.limit_count]

        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "website_settings": [
                {
                    "id": 1,
                    "tenant_id": 7,
                    "user_id": 3,
                    "subdomain": "fresh-site",
                    "standard_path_slug": "standard-site",
                    "brand": "Fresh Brand",
                    "published_project_id": "project-1",
                }
            ],
            "builder_projects": [
                {
                    "id": "project-1",
                    "tenant_id": 7,
                    "name": "Fresh Project",
                    "slug": "fresh-project",
                    "status": "published",
                    "published_schema": {
                        "defaultPageId": "home",
                        "siteChrome": {"brand": "Fresh Brand"},
                        "pages": [{"id": "home", "name": "Home", "slug": "/", "isDefault": True}],
                        "forms": [],
                    },
                    "published_version": 2,
                    "last_published_at": "2026-06-12T10:00:00+00:00",
                    "updated_at": "2026-06-12T10:00:00+00:00",
                }
            ],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


class WebsiteRoutesTests(unittest.TestCase):
    def setUp(self):
        self.entitlement_patches = [
            patch.object(website_routes, "require_any_entitlement", return_value={}),
            patch.object(website_routes, "require_branded_subdomain", return_value=None),
        ]
        for entitlement_patch in self.entitlement_patches:
            entitlement_patch.start()

    def tearDown(self):
        for entitlement_patch in reversed(self.entitlement_patches):
            entitlement_patch.stop()

    def test_canonical_get_returns_tenant_settings(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "fresh-site"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            website_routes,
            "ensure_settings_for_tenant",
            return_value=website,
        ) as ensure_settings:
            response = client.get("/website/settings")

        self.assertEqual(response.status_code, 200)
        ensure_settings.assert_called_once_with(7, 3)
        self.assertEqual(response.json()["website"], website)

    def test_canonical_put_saves_tenant_settings(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "fresh-site"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "old-site"},
        ), patch.object(
            website_routes,
            "save_settings_for_tenant",
            return_value=website,
        ) as save_settings, patch.object(
            website_routes,
            "record_audit_event",
        ):
            response = client.put(
                "/website/settings",
                json={"subdomain": "Fresh-Site", "brand": "Fresh Brand"},
            )

        self.assertEqual(response.status_code, 200)
        save_settings.assert_called_once_with(
            tenant_id=7,
            user_id=3,
            update_payload={"subdomain": "fresh-site", "brand": "Fresh Brand"},
        )
        self.assertEqual(response.json()["website"], website)

    def test_canonical_put_allows_clearing_optional_contact_email(self):
        client = build_website_client()
        website = {
            "id": 1,
            "tenant_id": 7,
            "user_id": 3,
            "subdomain": "fresh-site",
            "contact_email": "",
        }

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(tenant_id=7, user_id=3),
        ), patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3},
        ), patch.object(
            website_routes,
            "save_settings_for_tenant",
            return_value=website,
        ) as save_settings, patch.object(
            website_routes,
            "record_audit_event",
        ):
            response = client.put(
                "/website/settings",
                json={
                    "subdomain": "fresh-site",
                    "brand": "Ibtikar Shipment Portal",
                    "contact_email": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["website"]["contact_email"], "")
        self.assertEqual(
            save_settings.call_args.kwargs["update_payload"]["contact_email"],
            "",
        )

    def test_canonical_get_rejects_stale_user_tenant_without_active_membership(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            side_effect=website_routes.HTTPException(
                status_code=403,
                detail="Active tenant membership required",
            ),
        ), patch.object(
            website_routes,
            "ensure_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "stale-site"},
        ) as ensure_settings:
            response = client.get("/website/settings")

        self.assertEqual(response.status_code, 403)
        ensure_settings.assert_not_called()

    def test_canonical_put_rejects_membership_mismatch_before_saving_settings(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            side_effect=website_routes.HTTPException(
                status_code=403,
                detail="Active tenant membership required",
            ),
        ), patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "old-site"},
        ) as get_settings, patch.object(
            website_routes,
            "save_settings_for_tenant",
        ) as save_settings, patch.object(
            website_routes,
            "record_audit_event",
        ) as record_audit:
            response = client.put(
                "/website/settings",
                json={"subdomain": "fresh-site", "brand": "Fresh Brand"},
            )

        self.assertEqual(response.status_code, 403)
        get_settings.assert_not_called()
        save_settings.assert_not_called()
        record_audit.assert_not_called()

    def test_canonical_put_ignores_client_supplied_tenant_id(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "fresh-site"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "old-site"},
        ), patch.object(
            website_routes,
            "save_settings_for_tenant",
            return_value=website,
        ) as save_settings, patch.object(
            website_routes,
            "record_audit_event",
        ):
            response = client.put(
                "/website/settings",
                json={
                    "tenant_id": 99,
                    "subdomain": "fresh-site",
                    "brand": "Fresh Brand",
                },
            )

        self.assertEqual(response.status_code, 200)
        save_settings.assert_called_once_with(
            tenant_id=7,
            user_id=3,
            update_payload={"subdomain": "fresh-site", "brand": "Fresh Brand"},
        )

    def test_canonical_put_accepts_https_logo_url(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {"id": 1, "tenant_id": 7, "user_id": 3, "logo_url": "https://cdn.example.com/logo.png"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value=website,
        ), patch.object(
            website_routes,
            "save_settings_for_tenant",
            return_value=website,
        ) as save_settings, patch.object(
            website_routes,
            "record_audit_event",
        ):
            response = client.put(
                "/website/settings",
                json={"logo_url": " https://cdn.example.com/logo.png "},
            )

        self.assertEqual(response.status_code, 200)
        save_settings.assert_called_once_with(
            tenant_id=7,
            user_id=3,
            update_payload={"logo_url": "https://cdn.example.com/logo.png"},
        )


    def test_canonical_put_records_audit_changed_fields_only(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {
            "id": 1,
            "tenant_id": 7,
            "user_id": 3,
            "subdomain": "fresh-site",
            "brand": "Fresh Brand",
            "description": "Public description",
        }

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "old-site"},
        ), patch.object(
            website_routes,
            "save_settings_for_tenant",
            return_value=website,
        ), patch.object(website_routes, "record_audit_event") as record_audit:
            response = client.put(
                "/website/settings",
                json={
                    "subdomain": "Fresh-Site",
                    "brand": "Fresh Brand",
                    "description": "Public description",
                },
            )

        self.assertEqual(response.status_code, 200)
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 7)
        self.assertEqual(audit_kwargs["actor_user_id"], 3)
        self.assertEqual(audit_kwargs["action"], "website.settings_updated")
        self.assertEqual(audit_kwargs["target_type"], "website_settings")
        self.assertEqual(audit_kwargs["target_id"], 1)
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "changed_fields": ["brand", "description", "subdomain"],
                "old_subdomain": "old-site",
                "new_subdomain": "fresh-site",
            },
        )
        self.assertNotIn("Public description", str(audit_kwargs["metadata"]))

    def test_failed_website_settings_validation_does_not_record_audit(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(website_routes, "record_audit_event") as record_audit:
            response = client.put(
                "/website/settings",
                json={"logo_url": "javascript:alert(1)"},
            )

        self.assertEqual(response.status_code, 400)
        record_audit.assert_not_called()

    def test_canonical_put_rejects_unsafe_logo_urls(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        unsafe_urls = [
            "javascript:alert(1)",
            "data:image/svg+xml;base64,PHN2Zy8+",
            "//evil.example/logo.png",
            "http://cdn.example.com/logo.png",
        ]

        for unsafe_url in unsafe_urls:
            with self.subTest(unsafe_url=unsafe_url), patch.object(
                website_routes,
                "require_active_tenant_member",
                return_value=fake_tenant_context(
                    tenant_id=user_data.get("tenant_id"),
                    user_id=user_data.get("id"),
                ),
            ), patch.object(website_routes, "save_settings_for_tenant") as save_settings:
                response = client.put(
                    "/website/settings",
                    json={"logo_url": unsafe_url},
                )

            self.assertEqual(response.status_code, 400)
            save_settings.assert_not_called()

    def test_user_scoped_get_still_works_for_matching_user_id(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "fresh-site"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ) as require_user, patch.object(
            website_routes,
            "ensure_settings_for_tenant",
            return_value=website,
        ):
            response = client.get("/users/3/website/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["website"], website)

    def test_user_scoped_put_still_works_for_matching_user_id(self):
        client = build_website_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        website = {"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "fresh-site"}

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ) as require_user, patch.object(
            website_routes,
            "get_settings_for_tenant",
            return_value={"id": 1, "tenant_id": 7, "user_id": 3, "subdomain": "old-site"},
        ), patch.object(
            website_routes,
            "save_settings_for_tenant",
            return_value=website,
        ) as save_settings, patch.object(
            website_routes,
            "record_audit_event",
        ):
            response = client.put(
                "/users/3/website/settings",
                json={"subdomain": "fresh-site", "brand": "Fresh Brand"},
            )

        self.assertEqual(response.status_code, 200)
        save_settings.assert_called_once_with(
            tenant_id=7,
            user_id=3,
            update_payload={"subdomain": "fresh-site", "brand": "Fresh Brand"},
        )

    def test_user_scoped_route_rejects_mismatched_user_id(self):
        client = build_website_client()

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            return_value=fake_tenant_context(tenant_id=7, user_id=4),
        ):
            response = client.get("/users/3/website/settings")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User id does not match session")

    def test_admin_user_is_blocked_from_website_settings(self):
        client = build_website_client()

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            side_effect=website_routes.HTTPException(
                status_code=403,
                detail="User access is required",
            ),
        ):
            response = client.get("/website/settings")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User access is required")

    def test_user_without_tenant_context_returns_403(self):
        client = build_website_client()

        with patch.object(
            website_routes,
            "require_active_tenant_member",
            side_effect=website_routes.HTTPException(
                status_code=403,
                detail="User does not belong to a tenant",
            ),
        ):
            response = client.get("/website/settings")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User does not belong to a tenant")

    def test_public_site_still_resolves_by_subdomain(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/fresh-site")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["site"]["subdomain"], "fresh-site")
        self.assertEqual(body["site"]["brand"], "Fresh Brand")
        self.assertEqual(
            body["project"]["published_schema"],
            {
                "defaultPageId": "home",
                "siteChrome": {"brand": "Fresh Brand"},
                "pages": [{"id": "home", "name": "Home", "slug": "/", "isDefault": True}],
                "forms": [],
            },
        )

    def test_standard_path_resolves_published_content_without_premium_addon(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(public_site_routes, "require_branded_subdomain") as branded_gate:
            response = client.get("/public/sites/standard-site")

        self.assertEqual(response.status_code, 200)
        branded_gate.assert_not_called()
        self.assertEqual(response.json()["project"]["published_schema"]["defaultPageId"], "home")

    def test_branded_hostname_invokes_backend_entitlement_gate(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(public_site_routes, "require_branded_subdomain") as branded_gate:
            response = client.get(
                "/public/sites/fresh-site",
                headers={"Host": "fresh-site.madarportal.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(branded_gate.call_count, 1)
        for call in branded_gate.call_args_list:
            self.assertEqual(call.args[0]["tenant_id"], 7)



class TestWebsiteSettingsServiceLegacyFallback(unittest.TestCase):
    def test_get_settings_for_tenant_does_not_fallback_to_user_id(self):
        class LegacyFallbackQuery:
            def __init__(self, rows):
                self.rows = rows
                self.filters = []
                self.update_payload = None

            def select(self, *_args):
                return self

            def eq(self, column, value):
                self.filters.append((column, value))
                return self

            def limit(self, *_args):
                return self

            def update(self, payload):
                self.update_payload = payload
                return self

            def execute(self):
                rows = list(self.rows)
                for column, value in self.filters:
                    rows = [row for row in rows if row.get(column) == value]

                if self.update_payload is not None:
                    updated_rows = [dict(row, **self.update_payload) for row in rows]
                    return FakeResponse(updated_rows)

                return FakeResponse(rows)

        class LegacyFallbackSupabase:
            def __init__(self):
                self.tables = {
                    'website_settings': [
                        {'id': 1, 'tenant_id': None, 'user_id': 99, 'subdomain': 'legacy-site'},
                    ]
                }

            def table(self, table_name):
                return LegacyFallbackQuery(self.tables.get(table_name, []))

        fake_supabase = LegacyFallbackSupabase()

        with patch.object(website_settings_service, 'service_supabase', fake_supabase):
            settings = website_settings_service.get_settings_for_tenant(tenant_id=7, user_id=99)

        self.assertIsNone(settings)

class TenantSiteOwnerAccessTests(unittest.TestCase):
    def test_subdomain_owner_can_use_existing_main_account(self):
        settings = {"tenant_id": 7, "user_id": 3, "subdomain": "owner-site"}
        user = {"id": 3, "tenant_id": 7, "email": "owner@example.com"}

        with patch.object(public_site_routes, "get_active_tenant_membership", return_value=None), \
             patch.object(public_site_routes, "get_tenant_staff_membership", return_value=None):
            access = public_site_routes.get_tenant_site_access(settings, user)

        self.assertEqual(access["role"], "owner")
        self.assertEqual(access["tenant_id"], 7)

    def test_unrelated_main_account_cannot_access_tenant_site(self):
        settings = {"tenant_id": 7, "user_id": 3, "subdomain": "owner-site"}
        user = {"id": 9, "tenant_id": 8, "email": "other@example.com"}

        with patch.object(public_site_routes, "get_active_tenant_membership", return_value=None), \
             patch.object(public_site_routes, "get_tenant_staff_membership", return_value=None):
            access = public_site_routes.get_tenant_site_access(settings, user)

        self.assertIsNone(access)


if __name__ == "__main__":
    unittest.main()
