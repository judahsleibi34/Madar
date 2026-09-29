import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import app as app_module


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class AssetVisibilityQuery:
    def __init__(self, store, table):
        self.store, self.table = store, table
        self.rows = store.tables.get(table, [])
        self.filters = []

    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append((key, value)); return self
    def in_(self, key, values): self.filters.append((key, set(values))); return self
    def filter(self, key, operator, value):
        assert operator == "cs"
        self.filters.append((key, json.loads(value)))
        return self
    def limit(self, value): self.limit_value = value; return self
    def execute(self):
        self.store.queries.append(self.table)
        rows = [row for row in self.rows if all(
            (set(value) <= set(row.get(key) or [])) if isinstance(value, list)
            else row.get(key) in value if isinstance(value, set)
            else row.get(key) == value for key, value in self.filters
        )]
        return SimpleNamespace(data=rows[:getattr(self, "limit_value", len(rows))])


class AssetVisibilityStore:
    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def table(self, name):
        return AssetVisibilityQuery(self, name)

    def rpc(self, name, params):
        self.queries.append(f"rpc:{name}")
        if name != "get_managed_asset_visibility_context":
            raise AssertionError(name)
        tenant_id = params["p_tenant_id"]
        key = params["p_storage_key"]
        assets = [row for row in self.tables.get("builder_assets", [])
                  if row.get("tenant_id") == tenant_id and row.get("storage_key") == key
                  and row.get("status") in {"active", "unreferenced"}]
        if not assets:
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))
        assert len(assets) == 1
        asset = assets[0]
        settings = next((row for row in self.tables.get("website_settings", [])
                         if row.get("tenant_id") == tenant_id), None)
        schema = None
        bound_id = settings.get("published_project_id") if settings and (
            settings.get("subdomain") or settings.get("standard_path_slug")) else None
        if bound_id and any(row.get("asset_id") == asset.get("id") and row.get("project_id") == bound_id
                            for row in self.tables.get("builder_asset_references", [])):
            project = next((row for row in self.tables.get("builder_projects", [])
                            if row.get("id") == bound_id and row.get("tenant_id") == tenant_id
                            and row.get("status") == "published"), None)
            schema = project.get("published_schema") if project else None
        result = {"asset_status": asset["status"], "metadata": asset.get("metadata") or {},
                  "settings": settings, "published_schema": schema}
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[result]))


class PublicUploadRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.public_dir = Path(self.temp_dir.name).resolve() / "public_uploads"
        self.asset_dir = self.public_dir / "tenant_1" / "builder_assets"
        self.asset_dir.mkdir(parents=True)
        self.asset_path = self.asset_dir / "0123456789abcdef0123456789abcdef.png"
        self.asset_path.write_bytes(PNG_BYTES)
        self.patch = patch.object(app_module, "PUBLIC_UPLOADS_DIR", self.public_dir)
        self.patch.start()
        # These transport/range tests model an already-published asset. Draft
        # privacy and publication-reference authorization are covered by the
        # dedicated asset-visibility tests.
        self.visibility_patch = patch.object(
            app_module, "_asset_visibility", return_value=(True, False)
        )
        self.visibility_patch.start()
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.visibility_patch.stop()
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_managed_builder_asset_is_public(self):
        response = self.client.get(
            "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.content, PNG_BYTES)
        self.assertEqual(response.headers["cache-control"], "public, max-age=31536000, immutable")
        self.assertEqual(response.headers["cdn-cache-control"], "public, max-age=31536000, immutable")

    def test_managed_image_serves_cached_high_quality_responsive_webp(self):
        image = Image.new("RGB", (1600, 900), color=(35, 90, 140))
        image.save(self.asset_path, format="PNG")

        response = self.client.get(
            "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png?w=480"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.assertEqual(
            response.headers["cache-control"],
            "public, max-age=31536000, immutable",
        )
        self.assertEqual(
            response.headers["cdn-cache-control"],
            "public, max-age=31536000, immutable",
        )
        with Image.open(BytesIO(response.content)) as delivered:
            self.assertEqual(delivered.size, (480, 270))

    def test_responsive_image_can_be_rendered_from_durable_storage(self):
        source = BytesIO()
        Image.new("RGB", (1200, 600), color=(80, 40, 120)).save(source, format="PNG")
        self.asset_path.unlink()
        with patch.object(app_module, "download_builder_asset", return_value=source.getvalue()) as download:
            response = self.client.get(
                "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png?w=320"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        download.assert_called_once_with(
            storage_key="tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        )

    def test_managed_builder_asset_falls_back_to_durable_storage(self):
        self.asset_path.unlink()
        signed_url = "https://project.supabase.co/storage/v1/object/sign/builder-assets/exact?token=test"
        with patch.object(
            app_module, "create_builder_asset_signed_url", return_value=signed_url
        ) as create_signed_url:
            response = self.client.get(
                "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], signed_url)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        create_signed_url.assert_called_once_with(
            storage_key="tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png",
            expires_in=60,
        )

    def test_local_video_supports_http_byte_ranges(self):
        video_path = self.asset_dir / "abcdefabcdefabcdefabcdefabcdefab.mp4"
        video_content = bytes(range(256)) * 8
        video_path.write_bytes(video_content)

        response = self.client.get(
            "/uploads/tenant_1/builder_assets/abcdefabcdefabcdefabcdefabcdefab.mp4",
            headers={"Range": "bytes=0-1023"},
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], f"bytes 0-1023/{len(video_content)}")
        self.assertEqual(response.headers["content-length"], "1024")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.content, video_content[:1024])

        full_response = self.client.get(
            "/uploads/tenant_1/builder_assets/abcdefabcdefabcdefabcdefabcdefab.mp4"
        )
        self.assertEqual(full_response.status_code, 200)
        self.assertEqual(full_response.headers["content-length"], str(len(video_content)))
        self.assertEqual(full_response.content, video_content)

    def test_local_video_rejects_unsatisfiable_range(self):
        video_path = self.asset_dir / "abcdefabcdefabcdefabcdefabcdefab.mp4"
        video_path.write_bytes(b"video")
        response = self.client.get(
            "/uploads/tenant_1/builder_assets/abcdefabcdefabcdefabcdefabcdefab.mp4",
            headers={"Range": "bytes=999-1000"},
        )
        self.assertEqual(response.status_code, 416)

    def test_local_video_supports_suffix_ranges(self):
        video_path = self.asset_dir / "abcdefabcdefabcdefabcdefabcdefab.mp4"
        video_content = b"0123456789"
        video_path.write_bytes(video_content)
        response = self.client.get(
            "/uploads/tenant_1/builder_assets/abcdefabcdefabcdefabcdefabcdefab.mp4",
            headers={"Range": "bytes=-4"},
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 6-9/10")
        self.assertEqual(response.headers["content-length"], "4")
        self.assertEqual(response.content, b"6789")

    def test_unmanaged_upload_path_is_not_publicly_served(self):
        private_like_dir = self.public_dir / "tenant_1" / "user_1"
        private_like_dir.mkdir(parents=True)
        (private_like_dir / "dataset.csv").write_text("name,value\nA,1\n", encoding="utf-8")

        response = self.client.get("/uploads/tenant_1/user_1/dataset.csv")

        self.assertEqual(response.status_code, 404)

    def test_unmanaged_builder_asset_filename_is_not_publicly_served(self):
        unmanaged_asset = self.asset_dir / "logo.png"
        unmanaged_asset.write_bytes(PNG_BYTES)

        response = self.client.get("/uploads/tenant_1/builder_assets/logo.png")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_invalid_tenant_id_is_not_cacheable(self):
        response = self.client.get(f"/uploads/tenant_0/builder_assets/{self.asset_path.name}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_public_asset_traversal_attempt_is_rejected(self):
        response = self.client.get("/uploads/tenant_1/builder_assets/%2e%2e%2fdataset.png")

        self.assertEqual(response.status_code, 404)

    def test_tenant_a_local_asset_is_not_served_from_tenant_b_path(self):
        with patch.object(
            app_module,
            "create_builder_asset_signed_url",
            side_effect=app_module.BuilderAssetStorageError("not_found"),
        ):
            response = self.client.get(
                "/uploads/tenant_2/builder_assets/0123456789abcdef0123456789abcdef.png"
            )
        self.assertEqual(response.status_code, 404)

    def test_registered_symlink_cannot_escape_its_tenant_asset_directory(self):
        foreign_dir = self.public_dir / "tenant_2" / "builder_assets"
        foreign_dir.mkdir(parents=True)
        foreign_file = foreign_dir / self.asset_path.name
        foreign_file.write_bytes(PNG_BYTES)
        self.asset_path.unlink()
        self.asset_path.symlink_to(foreign_file)
        response = self.client.get(f"/uploads/tenant_1/builder_assets/{self.asset_path.name}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_builder_directory_symlink_rejection_is_not_cacheable(self):
        foreign_dir = self.public_dir / "tenant_2" / "builder_assets"
        foreign_dir.mkdir(parents=True)
        self.asset_path.unlink()
        self.asset_dir.rmdir()
        self.asset_dir.symlink_to(foreign_dir, target_is_directory=True)
        response = self.client.get(f"/uploads/tenant_1/builder_assets/{self.asset_path.name}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_unregistered_physical_file_is_not_public(self):
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", AssetVisibilityStore({})), patch.object(
                app_module, "get_authenticated_user_row", side_effect=Exception("anonymous")
            ):
                response = self.client.get(f"/uploads/tenant_1/builder_assets/{self.asset_path.name}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b'{"detail":"Asset was not found."}')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["cdn-cache-control"], "no-store")

    def test_wrong_tenant_registry_asset_is_not_public_or_cacheable(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "website_settings": [{"tenant_id": 1, "subdomain": "one", "logo_url": f"/uploads/{key}"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                response = self.client.get(f"/uploads/tenant_2/builder_assets/{self.asset_path.name}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_same_filename_is_isolated_between_registered_tenants(self):
        foreign = self.public_dir / "tenant_2" / "builder_assets" / self.asset_path.name
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(b"other tenant image")
        key_1 = f"tenant_1/builder_assets/{self.asset_path.name}"
        key_2 = f"tenant_2/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [
                {"id": "asset-1", "tenant_id": 1, "storage_key": key_1, "status": "active"},
                {"id": "asset-2", "tenant_id": 2, "storage_key": key_2, "status": "active"},
            ],
            "website_settings": [
                {"tenant_id": 1, "subdomain": "one", "logo_url": f"/uploads/{key_1}"},
                {"tenant_id": 2, "subdomain": "two", "logo_url": f"/uploads/{key_2}"},
            ],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                own = self.client.get(f"/uploads/{key_1}")
                other = self.client.get(f"/uploads/{key_2}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(own.content, PNG_BYTES)
        self.assertEqual(other.content, b"other tenant image")

    def test_registered_asset_missing_from_both_storage_backends_returns_404(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        self.asset_path.unlink()
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "website_settings": [{"tenant_id": 1, "subdomain": "one", "logo_url": f"/uploads/{key}"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store), patch.object(
                app_module, "create_builder_asset_signed_url", side_effect=app_module.BuilderAssetStorageError("not_found"),
            ):
                response = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_responsive_asset_missing_from_both_storage_backends_is_not_cacheable(self):
        self.asset_path.unlink()
        with patch.object(
            app_module, "download_builder_asset",
            side_effect=app_module.BuilderAssetStorageError("not_found"),
        ):
            response = self.client.get(f"/uploads/tenant_1/builder_assets/{self.asset_path.name}?w=320")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_visibility_lookup_failure_is_not_cacheable(self):
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "_asset_visibility", side_effect=RuntimeError("unavailable")):
                response = self.client.get(f"/uploads/tenant_1/builder_assets/{self.asset_path.name}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_published_reference_is_public_but_unreferenced_draft_is_not(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        published = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key, "status": "active"}],
            "builder_asset_references": [{"asset_id": "asset-1", "project_id": "project-1"}],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "published_project_id": "project-1"}],
            "builder_projects": [{
                "id": "project-1", "tenant_id": 1, "status": "published",
                "published_schema": {"pages": [{"image": f"/uploads/{storage_key}"}]},
            }],
        })
        draft = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key, "status": "unreferenced"}],
            "builder_asset_references": [],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", published):
                public_response = self.client.get(f"/uploads/{storage_key}")
            with patch.object(app_module, "service_supabase", draft), patch.object(
                app_module, "get_authenticated_user_row", side_effect=Exception("anonymous")
            ):
                draft_response = self.client.get(f"/uploads/{storage_key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(draft_response.status_code, 404)
        self.assertEqual(draft_response.headers["cache-control"], "no-store")

    def test_common_project_path_uses_one_remote_authorization_call(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "builder_asset_references": [
                {"asset_id": "asset-1", "project_id": "draft"},
                {"asset_id": "asset-1", "project_id": "published"},
            ],
            "builder_projects": [
                {"id": "draft", "tenant_id": 1, "status": "draft", "published_schema": {"image": f"/uploads/{key}"}},
                {"id": "published", "tenant_id": 1, "status": "published", "published_schema": {"image": f"/uploads/{key}"}},
                {"id": "foreign", "tenant_id": 2, "status": "published", "published_schema": {"image": f"/uploads/{key}"}},
            ],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "published_project_id": "published"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                response = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(store.queries, ["rpc:get_managed_asset_visibility_context"])

    def test_published_site_chrome_requires_current_binding_and_status(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "builder_asset_references": [{"asset_id": "asset-1", "project_id": "project-1"}],
            "builder_projects": [{
                "id": "project-1", "tenant_id": 1, "status": "published",
                "published_schema": {"siteChrome": {"logoUrl": f"/uploads/{key}"}},
            }],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "published_project_id": "project-1"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store), patch.object(
                app_module, "get_authenticated_user_row", side_effect=Exception("anonymous"),
            ):
                public = self.client.get(f"/uploads/{key}")
                store.tables["website_settings"][0]["published_project_id"] = "another-project"
                unbound = self.client.get(f"/uploads/{key}")
                store.tables["website_settings"][0]["published_project_id"] = "project-1"
                store.tables["builder_projects"][0]["status"] = "draft"
                unpublished = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(public.status_code, 200)
        self.assertEqual(unbound.status_code, 404)
        self.assertEqual(unpublished.status_code, 404)
        for response in (unbound, unpublished):
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["cdn-cache-control"], "no-store")

    def test_draft_reference_in_bound_project_does_not_grant_public_access(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "builder_asset_references": [{"asset_id": "asset-1", "project_id": "project-1"}],
            "builder_projects": [{
                "id": "project-1", "tenant_id": 1, "status": "published",
                "draft_schema": {"pages": [{"image": f"/uploads/{key}"}]},
                "published_schema": {"pages": []},
            }],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "published_project_id": "project-1"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store), patch.object(
                app_module, "get_authenticated_user_row", side_effect=Exception("anonymous"),
            ):
                response = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["cdn-cache-control"], "no-store")

    def test_private_published_page_image_is_not_anonymous_public_media(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "builder_asset_references": [{"asset_id": "asset-1", "project_id": "project-1"}],
            "builder_projects": [{
                "id": "project-1", "tenant_id": 1, "status": "published",
                "published_schema": {
                    "pages": [{"id": "members", "visibility": "members", "image": f"/uploads/{key}"}],
                },
            }],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "published_project_id": "project-1"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store), patch.object(
                app_module, "get_authenticated_user_row", side_effect=Exception("anonymous"),
            ):
                response = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_unreferenced_asset_preview_requires_same_tenant_and_is_private(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        draft = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key, "status": "unreferenced"}],
            "builder_asset_references": [],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", draft), patch.object(
                app_module, "get_authenticated_user_row",
                return_value=(object(), {"tenant_id": 1}),
            ):
                own = self.client.get(f"/uploads/{storage_key}")
            with patch.object(app_module, "service_supabase", draft), patch.object(
                app_module, "get_authenticated_user_row",
                return_value=(object(), {"tenant_id": 2}),
            ):
                foreign = self.client.get(f"/uploads/{storage_key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.headers["cache-control"], "private, no-store")
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.headers["cache-control"], "no-store")

    def test_persisted_store_logo_is_public_without_project_reference(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key, "status": "unreferenced"}],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "logo_url": f"/uploads/{storage_key}"}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                response = self.client.get(f"/uploads/{storage_key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")

    def test_persisted_landing_slide_is_public_without_project_reference(self):
        storage_key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({
            "builder_assets": [{
                "id": "asset-1", "tenant_id": 1, "storage_key": storage_key,
                "status": "active", "metadata": {"usage": "ecommerce_landing_slide"},
            }],
            "website_settings": [{
                "tenant_id": 1, "subdomain": "olive", "ecommerce_theme": {
                    "landing_page": {"slides": [{"image_url": f"/uploads/{storage_key}"}]},
                },
            }],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                response = self.client.get(f"/uploads/{storage_key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)

    def test_public_catalog_asset_fallbacks_remain_available(self):
        storage_key = f"tenant_1/builder_assets/{self.asset_path.name}"
        url = f"/uploads/{storage_key}"
        cases = {
            "category": ("ecommerce_category", "ecommerce_categories", {"id": "category-1", "tenant_id": 1, "status": "active", "image_url": url}),
            "brand": ("ecommerce_brand", "ecommerce_brands", {"id": "brand-1", "tenant_id": 1, "status": "active", "image_url": url}),
            "product": ("ecommerce_product", "ecommerce_products", {"id": "product-1", "tenant_id": 1, "status": "active", "images": [url]}),
            "variant": ("ecommerce_product_variant", "ecommerce_product_variants", {"tenant_id": 1, "product_id": "product-1", "active": True, "images": [url]}),
        }
        self.visibility_patch.stop()
        try:
            for label, (usage, table, record) in cases.items():
                with self.subTest(label=label):
                    tables = {
                        "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key,
                                            "status": "active", "metadata": {"usage": usage}}],
                        "website_settings": [{"tenant_id": 1, "subdomain": "olive"}],
                        table: [record],
                    }
                    if label == "variant":
                        tables["ecommerce_products"] = [{"id": "product-1", "tenant_id": 1, "status": "active"}]
                    store = AssetVisibilityStore(tables)
                    with patch.object(app_module, "service_supabase", store):
                        response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(store.queries[0], "rpc:get_managed_asset_visibility_context")
        finally:
            self.visibility_patch.start()

    def test_foreign_settings_and_soft_deleted_registry_fail_closed(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        settings = {"tenant_id": 2, "subdomain": "foreign", "logo_url": f"/uploads/{storage_key}"}
        self.visibility_patch.stop()
        try:
            for status in ("active", "soft_deleted"):
                store = AssetVisibilityStore({
                    "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key, "status": status}],
                    "website_settings": [settings if status == "active" else {
                        "tenant_id": 1, "subdomain": "own", "logo_url": f"/uploads/{storage_key}",
                    }],
                })
                with patch.object(app_module, "service_supabase", store), patch.object(
                    app_module, "get_authenticated_user_row", side_effect=Exception("anonymous")
                ):
                    result = self.client.get(f"/uploads/{storage_key}")
                    self.assertEqual(result.status_code, 404)
                    self.assertEqual(result.headers["cache-control"], "no-store")
        finally:
            self.visibility_patch.start()

    def test_draft_catalog_reference_does_not_make_asset_public(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        store = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": storage_key, "status": "active"}],
            "ecommerce_products": [{"tenant_id": 1, "status": "draft", "images": [f"/uploads/{storage_key}"]}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store), patch.object(
                app_module, "get_authenticated_user_row", side_effect=Exception("anonymous")
            ):
                response = self.client.get(f"/uploads/{storage_key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_missing_registry_uses_one_remote_authorization_call(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        store = AssetVisibilityStore({})
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                response = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(store.queries, ["rpc:get_managed_asset_visibility_context"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["cdn-cache-control"], "no-store")

    def test_malformed_rpc_response_and_network_failure_fail_closed(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"

        class InvalidClient:
            def __init__(self, result=None, error=None):
                self.result, self.error = result, error
            def rpc(self, *_args, **_kwargs):
                if self.error:
                    raise self.error
                return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.result))

        self.visibility_patch.stop()
        try:
            for invalid in (None, [{}], [{"asset_status": "soft_deleted"}], [{"asset_status": "active", "published_schema": []}]):
                with self.subTest(invalid=invalid), patch.object(app_module, "service_supabase", InvalidClient(result=invalid)):
                    response = self.client.get(f"/uploads/{key}")
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(response.headers["cdn-cache-control"], "no-store")
            with patch.object(app_module, "service_supabase", InvalidClient(error=RuntimeError("network unavailable"))):
                response = self.client.get(f"/uploads/{key}")
                self.assertEqual(response.status_code, 503)
        finally:
            self.visibility_patch.start()

    def test_schema_112_missing_rpc_uses_complete_legacy_authorization(self):
        key = f"tenant_1/builder_assets/{self.asset_path.name}"
        class MissingRpc(Exception):
            code = "PGRST202"

        class BridgeStore(AssetVisibilityStore):
            def rpc(self, *_args, **_kwargs):
                self.queries.append("rpc:missing")
                raise MissingRpc()

        store = BridgeStore({
            "builder_assets": [{"id": "asset-1", "tenant_id": 1, "storage_key": key, "status": "active"}],
            "website_settings": [{"tenant_id": 1, "subdomain": "olive", "published_project_id": "project-1"}],
            "builder_asset_references": [{"asset_id": "asset-1", "project_id": "project-1"}],
            "builder_projects": [{"id": "project-1", "tenant_id": 1, "status": "published",
                                  "published_schema": {"siteChrome": {"logoUrl": f"/uploads/{key}"}}}],
        })
        self.visibility_patch.stop()
        try:
            with patch.object(app_module, "service_supabase", store):
                response = self.client.get(f"/uploads/{key}")
        finally:
            self.visibility_patch.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(store.queries, ["rpc:missing", "builder_assets", "website_settings",
                                         "builder_asset_references", "builder_projects"])


if __name__ == "__main__":
    unittest.main()
