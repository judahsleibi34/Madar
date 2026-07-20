import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes
from services.tenant_service import TenantContext
from services.storage_quota_service import StorageSafetyError
from services.url_validation import validate_public_url


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP_BYTES = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"\x00" * 16
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"


def build_client():
    app = FastAPI()
    app.include_router(builder_routes.router)
    return TestClient(app)


def fake_context(tenant_id=1, user_id=2):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        auth_id="auth-1",
        role="owner",
        membership_status="active",
        user={},
        membership={"role": "owner"},
    )


class FakeQuery:
    def __init__(self):
        self.payload = None

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        return type("Response", (), {"data": [{"id": "project-1", **(self.payload or {})}]})()


class FakeSupabase:
    def __init__(self):
        self.query = FakeQuery()

    def table(self, _name):
        return self.query


class BuilderAssetUploadTests(unittest.TestCase):
    def setUp(self):
        self.client = build_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name).resolve()
        self.patches = [
            patch.object(builder_routes, "BUILDER_ASSET_UPLOAD_DIR", self.upload_dir),
            patch.object(builder_routes, "BUILDER_ASSET_MAX_BYTES", 5 * 1024 * 1024),
            patch.object(
                builder_routes,
                "require_builder_write_access",
                return_value=fake_context(),
            ),
            patch.object(
                builder_routes,
                "enforce_builder_asset_upload_rate_limit",
                return_value=None,
            ),
            patch.object(
                builder_routes,
                "register_builder_asset",
                return_value={"id": "asset-registry-1"},
            ),
            patch.object(builder_routes, "reserve_storage", return_value="reservation-1"),
            patch.object(builder_routes, "finish_storage", return_value="object-1"),
        ]

        for item in self.patches:
            item.start()

        self.audit_patch = patch.object(builder_routes, "record_audit_event")
        self.record_audit_event = self.audit_patch.start()

    def tearDown(self):
        self.audit_patch.stop()

        for item in reversed(self.patches):
            item.stop()

        self.temp_dir.cleanup()

    def post_asset(self, content, filename="asset.png", content_type="image/png"):
        return self.client.post(
            "/builder/assets/upload",
            files={"file": (filename, content, content_type)},
        )

    def test_unauthenticated_upload_is_rejected(self):
        with patch.object(
            builder_routes,
            "require_builder_write_access",
            side_effect=HTTPException(status_code=401, detail="Authentication required"),
        ):
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 401)

    def test_missing_tenant_context_is_rejected(self):
        with patch.object(
            builder_routes,
            "require_builder_write_access",
            return_value=fake_context(tenant_id=None),
        ):
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 403)

    def test_tenant_without_write_access_is_rejected(self):
        with patch.object(
            builder_routes,
            "require_builder_write_access",
            side_effect=HTTPException(status_code=403, detail="Write access required"),
        ):
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Write access required")

    def test_empty_file_is_rejected(self):
        response = self.post_asset(b"", "empty.png", "image/png")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Image file is required")

    def test_upload_rate_limit_is_applied(self):
        with patch.object(
            builder_routes,
            "enforce_builder_asset_upload_rate_limit",
            side_effect=HTTPException(status_code=429, detail="Too many asset uploads"),
        ):
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many asset uploads")

    def test_accepts_png_jpeg_and_webp(self):
        cases = [
            (PNG_BYTES, "asset.png", "image/png", ".png"),
            (JPEG_BYTES, "asset.jpg", "image/jpeg", ".jpg"),
            (WEBP_BYTES, "asset.webp", "image/webp", ".webp"),
        ]

        for content, filename, content_type, extension in cases:
            with self.subTest(content_type=content_type):
                response = self.post_asset(content, filename, content_type)

            self.assertEqual(response.status_code, 200)
            asset_url = response.json()["asset_url"]
            self.assertRegex(
                asset_url,
                rf"^/uploads/tenant_1/builder_assets/[a-f0-9]{{32}}{extension}$",
            )
            self.assertTrue((self.upload_dir / asset_url.removeprefix("/uploads/")).exists())


    def test_successful_upload_records_audit_event(self):
        response = self.post_asset(PNG_BYTES, "asset.png", "image/png")

        self.assertEqual(response.status_code, 200)
        asset_url = response.json()["asset_url"]
        self.record_audit_event.assert_called_once()
        audit_kwargs = self.record_audit_event.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 1)
        self.assertEqual(audit_kwargs["actor_user_id"], 2)
        self.assertEqual(audit_kwargs["action"], "builder.asset_uploaded")
        self.assertEqual(audit_kwargs["target_type"], "builder_asset")
        self.assertRegex(audit_kwargs["target_id"], r"^[a-f0-9]{32}\.png$")
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "asset_url": asset_url,
                "content_type": "image/png",
                "size_bytes": len(PNG_BYTES),
                "extension": ".png",
            },
        )
        self.assertNotIn(str(self.upload_dir), str(audit_kwargs["metadata"]))

    def test_rejected_upload_does_not_record_audit_event(self):
        response = self.post_asset(SVG_BYTES, "logo.svg", "image/svg+xml")

        self.assertEqual(response.status_code, 400)
        self.record_audit_event.assert_not_called()

    def test_rejects_svg_upload(self):
        response = self.post_asset(SVG_BYTES, "logo.svg", "image/svg+xml")

        self.assertEqual(response.status_code, 400)

    def test_rejects_wrong_magic_bytes(self):
        response = self.post_asset(b"not really an image", "asset.png", "image/png")

        self.assertEqual(response.status_code, 400)

    def test_rejects_mismatched_declared_content_type(self):
        response = self.post_asset(JPEG_BYTES, "asset.png", "image/png")

        self.assertEqual(response.status_code, 400)

    def test_rejects_oversized_image(self):
        with patch.object(builder_routes, "BUILDER_ASSET_MAX_BYTES", 8):
            response = self.post_asset(PNG_BYTES, "asset.png", "image/png")

        self.assertEqual(response.status_code, 413)

    def test_quota_rejection_writes_no_file(self):
        with patch.object(
            builder_routes,
            "reserve_storage",
            side_effect=StorageSafetyError("tenant_storage_quota_exceeded"),
        ):
            response = self.post_asset(PNG_BYTES)
        self.assertEqual(response.status_code, 507)
        self.assertEqual(response.json()["detail"]["code"], "tenant_storage_quota_exceeded")
        asset_dir = self.upload_dir / "tenant_1" / "builder_assets"
        self.assertFalse(asset_dir.exists())

    def test_path_traversal_filename_does_not_affect_storage_path(self):
        response = self.post_asset(PNG_BYTES, "../../evil.png", "image/png")

        self.assertEqual(response.status_code, 200)
        asset_url = response.json()["asset_url"]

        self.assertNotIn("evil", asset_url)
        self.assertRegex(asset_url, r"^/uploads/tenant_1/builder_assets/[a-f0-9]{32}\.png$")
        self.assertEqual(len(list((self.upload_dir / "tenant_1" / "builder_assets").iterdir())), 1)

    def test_url_validator_accepts_managed_asset_path(self):
        self.assertEqual(
            validate_public_url(
                "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png",
                field_name="Image URL",
                allow_relative=True,
            ),
            "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png",
        )

    def test_builder_schema_accepts_managed_asset_url(self):
        fake_supabase = FakeSupabase()
        schema = {
            "pages": [
                {
                    "sections": [
                        {
                            "rows": [
                                {
                                    "columns": [
                                        {
                                            "elements": [
                                                {
                                                    "id": "image-1",
                                                    "type": "image",
                                                    "content": "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png",
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ],
            "siteChrome": {
                "logoUrl": "/uploads/tenant_1/builder_assets/fedcba9876543210fedcba9876543210.webp"
            },
        }

        with patch.object(builder_routes, "service_supabase", fake_supabase), patch.object(
            builder_routes,
            "get_project_for_tenant",
            return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {}},
        ):
            response = self.client.put("/builder/projects/project-1", json={"draft_schema": schema})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_supabase.query.payload["draft_schema"], schema)

    def test_builder_schema_still_rejects_data_url(self):
        schema = {
            "pages": [
                {
                    "sections": [
                        {
                            "rows": [
                                {
                                    "columns": [
                                        {
                                            "elements": [
                                                {
                                                    "id": "image-1",
                                                    "type": "image",
                                                    "content": "data:image/png;base64,AAAA",
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        with patch.object(
            builder_routes,
            "get_project_for_tenant",
            return_value={"id": "project-1", "tenant_id": 1, "draft_schema": {}},
        ):
            response = self.client.put("/builder/projects/project-1", json={"draft_schema": schema})

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
