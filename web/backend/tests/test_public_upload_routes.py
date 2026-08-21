import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import app as app_module


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


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
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_managed_builder_asset_is_public(self):
        response = self.client.get(
            "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.content, PNG_BYTES)

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


if __name__ == "__main__":
    unittest.main()
