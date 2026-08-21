import copy
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from routes import public_site_routes


ROOT = Path(__file__).resolve().parents[2]


def schema(*, body="Tenant A", default_id="home", pages=None, chrome=None):
    return {
        "defaultPageId": default_id,
        "siteChrome": chrome or {"brand": "Tenant A", "footerStoreName": "Tenant A"},
        "forms": [],
        "pages": pages or [
            {
                "id": "home",
                "name": "Home",
                "slug": "/",
                "isDefault": True,
                "sections": [{"id": "hero", "body": body}],
            }
        ],
    }


def project(project_id="project-a", tenant_id=1, **overrides):
    value = {
        "id": project_id,
        "tenant_id": tenant_id,
        "name": "Site",
        "slug": "site",
        "status": "published",
        "published_schema": schema(),
        "published_version": 3,
        "published_revision": 7,
        "schema_version": 1,
        "last_published_at": "2026-07-31T00:00:00Z",
        "updated_at": "2026-07-31T00:00:00Z",
    }
    value.update(overrides)
    return value


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.limit_value = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    @property
    def not_(self):
        return self

    def is_(self, field, value):
        self.filters.append(("not_null", field, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        result = []
        for row in self.client.tables.get(self.table, []):
            include = True
            for operation, field, value in self.filters:
                if operation == "eq" and str(row.get(field)) != str(value):
                    include = False
                if operation == "not_null" and row.get(field) is None:
                    include = False
            if include:
                result.append(copy.deepcopy(row))
        if self.limit_value is not None:
            result = result[: self.limit_value]
        return SimpleNamespace(data=result)


class FakeSupabase:
    def __init__(self, **tables):
        self.tables = tables

    def table(self, name):
        return Query(self, name)


class RequestStub:
    def __init__(self, host="madarportal.com"):
        self.headers = {"host": host}


class PublicPublicationIsolationTests(unittest.TestCase):
    def test_two_tenants_with_same_page_slug_resolve_only_bound_project(self):
        fake = FakeSupabase(
            website_settings=[
                {"id": 10, "tenant_id": 1, "standard_path_slug": "alpha", "subdomain": "alpha", "published_project_id": "project-a"},
                {"id": 20, "tenant_id": 2, "standard_path_slug": "beta", "subdomain": "beta", "published_project_id": "project-b"},
            ],
            builder_projects=[
                project("project-a", 1, published_schema=schema(body="Alpha")),
                project("project-b", 2, published_schema=schema(body="Beta")),
            ],
        )
        with patch.object(public_site_routes, "service_supabase", fake):
            settings = public_site_routes.resolve_website_settings("alpha", request=RequestStub())
            resolved = public_site_routes.get_bound_published_project(settings)
        self.assertEqual(resolved["tenant_id"], 1)
        self.assertEqual(resolved["published_schema"]["pages"][0]["sections"][0]["body"], "Alpha")

    def test_two_projects_in_one_tenant_remain_isolated_by_exact_binding(self):
        fake = FakeSupabase(
            builder_projects=[
                project("project-a", 1, published_schema=schema(body="Bound")),
                project("project-b", 1, published_schema=schema(body="Other")),
            ]
        )
        with patch.object(public_site_routes, "service_supabase", fake):
            resolved = public_site_routes.get_bound_published_project(
                {"tenant_id": 1, "published_project_id": "project-a"}
            )
        self.assertEqual(resolved["id"], "project-a")
        self.assertEqual(resolved["published_schema"]["pages"][0]["sections"][0]["body"], "Bound")

    def test_header_footer_body_and_loading_profile_share_project_snapshot(self):
        bound = project(
            published_schema=schema(
                body="Bound body",
                chrome={
                    "brand": "Bound brand",
                    "footerStoreName": "Bound footer",
                    "loadingImageUrl": "/uploads/tenant_1/builder_assets/loading.png",
                },
            )
        )
        profile = public_site_routes.build_public_site_profile(
            {"id": 9, "brand": "Wrong settings brand"},
            "alpha",
            bound,
        )
        self.assertEqual(profile["brand"], "Bound brand")
        self.assertEqual(profile["footer_store_name"], "Bound footer")
        self.assertEqual(
            profile["loading_image_url"],
            "/uploads/tenant_1/builder_assets/loading.png",
        )

    def test_bootstrap_uses_brand_and_loading_image_from_published_snapshot(self):
        settings = {
            "tenant_id": 1,
            "published_project_id": "project-a",
            "brand": "Stale settings brand",
            "logo_url": "/uploads/stale-logo.png",
        }
        bound = project(
            published_schema=schema(
                chrome={
                    "brand": "PalCode Academy Portal",
                    "logoUrl": "/uploads/published-logo.png",
                    "loadingImageUrl": "/uploads/published-loading.png",
                },
            )
        )
        with patch.object(public_site_routes, "enforce_public_rate_limit"), patch.object(
            public_site_routes, "resolve_website_settings", return_value=settings
        ), patch.object(
            public_site_routes, "require_public_runtime_entitlement"
        ), patch.object(
            public_site_routes, "get_bound_published_project", return_value=bound
        ) as get_project:
            result = public_site_routes.get_public_site_bootstrap("alpha", RequestStub())

        self.assertEqual(result["site"]["brand"], "PalCode Academy Portal")
        self.assertEqual(result["site"]["logo_url"], "/uploads/published-logo.png")
        self.assertEqual(result["site"]["loading_image_url"], "/uploads/published-loading.png")
        get_project.assert_called_once_with(settings, require_pages=False)

    def test_unknown_hostname_identifier_fails_closed(self):
        fake = FakeSupabase(website_settings=[])
        with patch.object(public_site_routes, "service_supabase", fake):
            with self.assertRaises(HTTPException) as caught:
                public_site_routes.resolve_website_settings("missing", request=RequestStub())
        self.assertEqual(caught.exception.status_code, 404)

    def test_duplicate_hostname_rows_fail_closed(self):
        duplicate = {"tenant_id": 1, "standard_path_slug": "alpha", "subdomain": "alpha", "published_project_id": "project-a"}
        fake = FakeSupabase(website_settings=[{"id": 1, **duplicate}, {"id": 2, **duplicate}])
        with patch.object(public_site_routes, "service_supabase", fake):
            with self.assertRaises(HTTPException) as caught:
                public_site_routes.resolve_website_settings("alpha", request=RequestStub())
        self.assertEqual(caught.exception.status_code, 409)

    def test_duplicate_project_rows_fail_closed_instead_of_first(self):
        fake = FakeSupabase(builder_projects=[project(), project()])
        with patch.object(public_site_routes, "service_supabase", fake):
            with self.assertRaises(HTTPException) as caught:
                public_site_routes.get_bound_published_project(
                    {"tenant_id": 1, "published_project_id": "project-a"}
                )
        self.assertEqual(caught.exception.status_code, 409)

    def test_duplicate_homepage_rows_fail_closed(self):
        invalid = project(
            published_schema=schema(
                pages=[
                    {"id": "home", "slug": "/", "isDefault": True},
                    {"id": "other", "slug": "/", "isDefault": True},
                ]
            )
        )
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.validate_published_snapshot(
                invalid, expected_tenant_id=1, expected_project_id="project-a"
            )
        self.assertEqual(caught.exception.status_code, 409)

    def test_homepage_id_mismatch_is_rejected(self):
        invalid = project(published_schema=schema(default_id="other"))
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.validate_published_snapshot(
                invalid, expected_tenant_id=1, expected_project_id="project-a"
            )
        self.assertEqual(caught.exception.status_code, 409)

    def test_unpublished_or_deleted_homepage_does_not_fallback(self):
        invalid = project(
            published_schema=schema(default_id="deleted"),
        )
        with self.assertRaises(HTTPException):
            public_site_routes.validate_published_snapshot(
                invalid, expected_tenant_id=1, expected_project_id="project-a"
            )
        unpublished = project(status="draft")
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.validate_published_snapshot(
                unpublished, expected_tenant_id=1, expected_project_id="project-a"
            )
        self.assertEqual(caught.exception.status_code, 404)

    def test_cache_identity_cannot_cross_site_or_publication(self):
        first = project()
        second = project("project-b", 2, published_version=3)
        first_meta = public_site_routes.build_publication_metadata(
            first, first["published_schema"], settings={"id": 1}, site_identifier="alpha"
        )
        second_meta = public_site_routes.build_publication_metadata(
            second, second["published_schema"], settings={"id": 2}, site_identifier="beta"
        )
        republished_meta = public_site_routes.build_publication_metadata(
            {**first, "published_version": 4},
            first["published_schema"],
            settings={"id": 1},
            site_identifier="alpha",
        )
        self.assertNotEqual(first_meta["etag"], second_meta["etag"])
        self.assertNotEqual(first_meta["etag"], republished_meta["etag"])
        self.assertIn("alpha:project-a:3", first_meta["publication_key"])

    def test_mismatched_direct_page_id_cannot_leave_bound_snapshot(self):
        bound = project(
            published_schema=schema(
                pages=[
                    {"id": "home", "slug": "/", "isDefault": True},
                    {"id": "shared", "slug": "/inside"},
                ]
            )
        )
        _, page, _ = public_site_routes.find_published_page(bound, "shared")
        self.assertEqual(page["slug"], "/inside")
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.find_published_page(bound, "other-project-page")
        self.assertEqual(caught.exception.status_code, 404)

    def test_managed_asset_from_another_tenant_is_rejected(self):
        invalid = project(
            published_schema=schema(chrome={
                "brand": "Tenant A",
                "logoUrl": "/uploads/tenant_2/builder_assets/logo.png",
            })
        )
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.validate_published_snapshot(
                invalid, expected_tenant_id=1, expected_project_id="project-a"
            )
        self.assertEqual(caught.exception.status_code, 409)

    def test_duplicate_form_ids_fail_closed(self):
        invalid_schema = schema()
        invalid_schema["forms"] = [{"id": "contact"}, {"id": "contact"}]
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.validate_published_snapshot(
                project(published_schema=invalid_schema),
                expected_tenant_id=1,
                expected_project_id="project-a",
            )
        self.assertEqual(caught.exception.status_code, 409)

    def test_duplicate_reservation_block_reference_fails_closed(self):
        published_schema = schema()
        published_schema["pages"][0]["sections"] = [
            {
                "rows": [{"columns": [{"elements": [
                    {"id": "booking", "type": "reservationBlock"},
                    {"id": "booking", "type": "reservationBlock"},
                ]}]}]
            }
        ]
        with self.assertRaises(HTTPException) as caught:
            public_site_routes.find_published_block(
                published_schema, "booking", "reservationBlock"
            )
        self.assertEqual(caught.exception.status_code, 409)

    def test_valid_published_site_endpoint_returns_one_boundary(self):
        settings = {"id": 9, "tenant_id": 1, "standard_path_slug": "alpha", "subdomain": "alpha", "published_project_id": "project-a"}
        fake = FakeSupabase(website_settings=[settings], builder_projects=[project()])
        with patch.object(public_site_routes, "service_supabase", fake), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(public_site_routes, "require_public_runtime_entitlement"), \
             patch.object(public_site_routes, "get_optional_tenant_visitor", return_value=None):
            response = TestClient(app).get("/public/sites/alpha", headers={"host": "madarportal.com"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project"]["site_id"], "9")
        self.assertEqual(payload["project"]["published_schema"]["defaultPageId"], "home")
        self.assertEqual(response.headers["CDN-Cache-Control"], "no-store")
        self.assertIn("Host", response.headers["Vary"])

    def test_publish_rpc_updates_snapshot_and_binding_in_one_transaction(self):
        migrations_dir = Path(
            os.getenv("MADAR_MIGRATIONS_DIR", str(ROOT / "database/migrations"))
        )
        migration = (migrations_dir / "072_harden_publication_isolation.sql").read_text()
        function_body = migration.split(
            "create or replace function public.publish_validated_builder_project_atomic", 1
        )[1]
        self.assertIn("for update", function_body.lower())
        self.assertIn("update public.builder_projects", function_body)
        self.assertIn("update public.website_settings", function_body)
        self.assertLess(
            function_body.index("update public.builder_projects"),
            function_body.index("return current_project"),
        )


if __name__ == "__main__":
    unittest.main()
