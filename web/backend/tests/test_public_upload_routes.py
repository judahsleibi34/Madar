import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as app_module


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class AssetVisibilityQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class AssetVisibilityStore:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return AssetVisibilityQuery(self.tables.get(name, []))


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

    def test_published_reference_is_public_but_unreferenced_draft_is_not(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        published = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "status": "active"}],
            "builder_asset_references": [{"project_id": "project-1"}],
            "builder_projects": [{
                "id": "project-1", "status": "published",
                "published_schema": {"pages": [{"image": f"/uploads/{storage_key}"}]},
            }],
        })
        draft = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "status": "unreferenced"}],
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

    def test_unreferenced_asset_preview_requires_same_tenant_and_is_private(self):
        storage_key = "tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        draft = AssetVisibilityStore({
            "builder_assets": [{"id": "asset-1", "status": "unreferenced"}],
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


if __name__ == "__main__":
    unittest.main()
