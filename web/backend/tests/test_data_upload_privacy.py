import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from data_analysis import services as data_services
from data_analysis.routes import data_routes
from routes import builder_routes
from services.tenant_service import TenantContext
from services.upload_config import validate_private_uploads_not_publicly_mounted


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def fake_user_scope(user_id, request, response):
    if request.headers.get("x-test-unauthenticated") == "1":
        raise HTTPException(status_code=401, detail="Not authenticated")

    tenant_id = request.headers.get("x-test-tenant-id", "1")
    return SimpleNamespace(user_id=int(user_id), tenant_id=tenant_id)


def fake_builder_context(tenant_id=1, user_id=1):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        auth_id=f"auth-{user_id}",
        role="owner",
        membership_status="active",
        user={},
        membership={"role": "owner"},
    )


class DataUploadPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.public_dir = self.root / "public_uploads"
        self.private_dir = self.root / "private_uploads"
        self.public_dir.mkdir()
        self.private_dir.mkdir()

        app = FastAPI()
        app.mount("/uploads", StaticFiles(directory=str(self.public_dir)), name="uploads")
        app.include_router(data_routes.router)
        app.include_router(builder_routes.router)
        self.client = TestClient(app)

        self.patches = [
            patch.dict(
                "os.environ",
                {
                    "PUBLIC_UPLOADS_DIR": str(self.public_dir),
                    "DATA_UPLOAD_DIR": str(self.private_dir),
                },
                clear=False,
            ),
            patch.object(data_routes, "require_active_tenant_user_id", side_effect=fake_user_scope),
            patch.object(data_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value="reservation-1"),
            patch.object(data_services, "finish_storage", return_value="object-1"),
            patch.object(builder_routes, "BUILDER_ASSET_UPLOAD_DIR", self.public_dir),
            patch.object(builder_routes, "BUILDER_ASSET_MAX_BYTES", 25 * 1024 * 1024),
            patch.object(builder_routes, "store_builder_asset", return_value=None),
            patch.object(builder_routes, "delete_builder_asset", return_value=None),
            patch.object(builder_routes, "register_builder_asset", return_value={"id": "asset-1"}),
            patch.object(builder_routes, "delete_builder_asset_registration", return_value=None),
            patch.object(builder_routes, "reserve_storage", return_value="reservation-1"),
            patch.object(builder_routes, "finish_storage", return_value="object-1"),
            patch.object(builder_routes, "release_storage", return_value=True),
            patch.object(
                builder_routes,
                "require_builder_write_access",
                return_value=fake_builder_context(),
            ),
            patch.object(builder_routes, "enforce_builder_asset_upload_rate_limit", return_value=None),
            patch.object(builder_routes, "record_audit_event", return_value=None),
        ]

        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def upload_dataset(self, user_id=1):
        return self.client.post(
            f"/users/{user_id}/data/upload",
            files={"file": ("dataset.csv", b"name,value\nA,1\n", "text/csv")},
        )

    def test_data_analysis_upload_is_saved_under_private_data_dir(self):
        response = self.upload_dataset()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["dataset_id"], body["file_path"])
        self.assertFalse(Path(body["file_path"]).is_absolute())
        stored_path = self.private_dir / "tenant_1" / "user_1" / body["dataset_id"]
        self.assertTrue(stored_path.is_file())
        self.assertEqual(stored_path.parent, self.private_dir / "tenant_1" / "user_1")
        self.assertNotIn(self.public_dir, stored_path.parents)

    def test_data_analysis_upload_is_not_accessible_through_public_uploads(self):
        response = self.upload_dataset()

        self.assertEqual(response.status_code, 200)
        public_guess = f"/uploads/tenant_1/user_1/{response.json()['dataset_id']}"

        static_response = self.client.get(public_guess)

        self.assertEqual(static_response.status_code, 404)

    def test_public_builder_asset_upload_remains_public(self):
        upload_response = self.client.post(
            "/builder/assets/upload",
            files={"file": ("asset.png", PNG_BYTES, "image/png")},
        )

        self.assertEqual(upload_response.status_code, 200)
        asset_url = upload_response.json()["asset_url"]
        self.assertRegex(asset_url, r"^/uploads/tenant_1/builder_assets/[a-f0-9]{32}\.png$")

        static_response = self.client.get(asset_url)

        self.assertEqual(static_response.status_code, 200)
        self.assertEqual(static_response.content, PNG_BYTES)

    def test_authenticated_read_and_export_can_access_private_dataset(self):
        upload_response = self.upload_dataset()
        self.assertEqual(upload_response.status_code, 200)
        file_path = upload_response.json()["file_path"]

        read_response = self.client.post(
            "/users/1/data/read",
            json={"input_path": file_path},
        )
        export_response = self.client.post(
            "/users/1/data/export",
            json={"input_path": file_path},
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json()["preview"], [{"name": "A", "value": 1}])
        self.assertEqual(export_response.status_code, 200)
        self.assertIn("name,value", export_response.json()["csv"])

    def test_path_traversal_to_another_user_dataset_is_rejected(self):
        other_dir = self.private_dir / "tenant_1" / "user_2"
        other_dir.mkdir(parents=True)
        other_file = other_dir / "secret.csv"
        other_file.write_text("name,value\nSecret,99\n", encoding="utf-8")

        traversal_path = self.private_dir / "tenant_1" / "user_1" / ".." / "user_2" / "secret.csv"
        response = self.client.post(
            "/users/1/data/read",
            json={"input_path": str(traversal_path)},
        )

        self.assertEqual(response.status_code, 403)

    def test_user_and_tenant_isolation_is_preserved_for_private_dataset_reads(self):
        upload_response = self.upload_dataset(user_id=1)
        self.assertEqual(upload_response.status_code, 200)
        file_path = upload_response.json()["file_path"]

        other_user_response = self.client.post(
            "/users/2/data/read",
            json={"input_path": file_path},
        )
        other_tenant_response = self.client.post(
            "/users/1/data/read",
            json={"input_path": file_path},
            headers={"x-test-tenant-id": "2"},
        )

        self.assertEqual(other_user_response.status_code, 403)
        self.assertEqual(other_tenant_response.status_code, 403)

    def test_unauthenticated_user_cannot_access_private_dataset(self):
        upload_response = self.upload_dataset(user_id=1)
        self.assertEqual(upload_response.status_code, 200)
        file_path = upload_response.json()["file_path"]

        response = self.client.post(
            "/users/1/data/read",
            json={"input_path": file_path},
            headers={"x-test-unauthenticated": "1"},
        )

        self.assertEqual(response.status_code, 401)

    def test_missing_private_dataset_returns_404(self):
        missing_path = self.private_dir / "tenant_1" / "user_1" / "missing.csv"
        response = self.client.post(
            "/users/1/data/read",
            json={"input_path": str(missing_path)},
        )

        self.assertEqual(response.status_code, 404)

    def test_public_mount_guard_rejects_private_dir_nested_under_public_dir(self):
        with self.assertRaisesRegex(RuntimeError, "DATA_UPLOAD_DIR must not"):
            validate_private_uploads_not_publicly_mounted(
                public_uploads_dir=self.public_dir,
                data_upload_dir=self.public_dir / "tenant_1" / "user_1",
            )


if __name__ == "__main__":
    unittest.main()
