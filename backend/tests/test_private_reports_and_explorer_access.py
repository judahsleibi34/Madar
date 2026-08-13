import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from data_analysis.routes import visualization_routes
from services.upload_config import validate_private_charts_not_publicly_mounted


def fake_user_scope(user_id, request, response):
    if request.headers.get("x-test-unauthenticated") == "1":
        raise HTTPException(status_code=401, detail="Not authenticated")

    tenant_id = request.headers.get("x-test-tenant-id", "1")
    return SimpleNamespace(id=f"auth-{user_id}"), {
        "id": int(user_id),
        "tenant_id": tenant_id,
        "user_type": "user",
    }


class PrivateReportsAndExplorerAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.public_dir = self.root / "public_uploads"
        self.charts_dir = self.root / "private_generated_charts"
        self.public_dir.mkdir()
        self.charts_dir.mkdir()

        self.user_dir = self.charts_dir / "tenant_1" / "user_1"
        self.user_dir.mkdir(parents=True)
        self.explorer_path = self.user_dir / "madar-visualization-test-explorer.html"
        self.explorer_path.write_text(
            "<!doctype html><html><body><script>alert('dataset')</script>dataset value</body></html>",
            encoding="utf-8",
        )

        app = FastAPI()
        app.include_router(visualization_routes.router)
        self.client = TestClient(app)

        self.patches = [
            patch.dict(
                "os.environ",
                {
                    "PUBLIC_UPLOADS_DIR": str(self.public_dir),
                    "PRIVATE_CHARTS_DIR": str(self.charts_dir),
                },
                clear=False,
            ),
            patch.object(visualization_routes, "get_storage_scope", side_effect=self.get_storage_scope),
        ]

        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def get_storage_scope(self, request, response, user_id):
        _, user_data = fake_user_scope(user_id, request, response)
        return str(user_data["tenant_id"]), str(user_data["id"])

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get(
            f"/users/1/visualization/charts/{self.explorer_path.name}",
            headers={"x-test-unauthenticated": "1"},
        )

        self.assertEqual(response.status_code, 401)

    def test_wrong_tenant_returns_403(self):
        response = self.client.get(
            f"/users/1/visualization/charts/{self.explorer_path.name}",
            headers={"x-test-tenant-id": "2"},
        )

        self.assertEqual(response.status_code, 403)

    def test_wrong_user_returns_403(self):
        response = self.client.get(f"/users/2/visualization/charts/{self.explorer_path.name}")

        self.assertEqual(response.status_code, 403)

    def test_path_traversal_returns_403(self):
        response = self.client.get("/users/1/visualization/charts/%2e%2e%2fsecret.html")

        self.assertEqual(response.status_code, 403)

    def test_missing_file_returns_404(self):
        response = self.client.get("/users/1/visualization/charts/missing-explorer.html")

        self.assertEqual(response.status_code, 404)

    def test_valid_owner_access_returns_html_as_attachment_with_security_headers(self):
        response = self.client.get(f"/users/1/visualization/charts/{self.explorer_path.name}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/html; charset=utf-8")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn(self.explorer_path.name, response.headers["content-disposition"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn("script-src 'none'", response.headers["content-security-policy"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertIn("sandbox", response.headers["content-security-policy"])
        self.assertIn(b"dataset value", response.content)

    def test_private_generated_directory_nested_under_public_dir_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "PRIVATE_CHARTS_DIR"):
            validate_private_charts_not_publicly_mounted(
                public_uploads_dir=self.public_dir,
                private_charts_dir=self.public_dir / "generated_charts",
            )


if __name__ == "__main__":
    unittest.main()
