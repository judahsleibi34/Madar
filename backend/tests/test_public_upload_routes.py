import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

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


if __name__ == "__main__":
    unittest.main()
