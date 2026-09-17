from tests.entitlement_test_support import installed_business_fixture
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import zipfile

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from routes import builder_routes
from services.tenant_service import TenantContext
from services.storage_quota_service import StorageSafetyError
from services.url_validation import validate_public_url


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP_BYTES = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"\x00" * 16
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
MP4_BYTES = bytes.fromhex("00000018667479706d703432") + bytes(16)
WEBM_BYTES = bytes.fromhex("1a45dfa3") + bytes(20)
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
DOC_BYTES = bytes.fromhex("d0cf11e0a1b11ae1") + bytes(20)


def build_docx_bytes():
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return output.getvalue()


DOCX_BYTES = build_docx_bytes()


def build_client():
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://madarportal.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
        self.enterContext(installed_business_fixture(1))
        self.client = build_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name).resolve()
        self.patches = [
            patch.object(builder_routes, "BUILDER_ASSET_UPLOAD_DIR", self.upload_dir),
            patch.object(builder_routes, "BUILDER_ASSET_MAX_BYTES", 25 * 1024 * 1024),
            patch.object(
                builder_routes,
                "require_builder_write_access",
                return_value=fake_context(),
            ),
            patch.object(
                builder_routes,
                "require_active_tenant_member",
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
            patch.object(builder_routes, "delete_builder_asset_registration", return_value=None),
            patch.object(builder_routes, "reserve_storage", return_value="reservation-1"),
            patch.object(builder_routes, "finish_storage", return_value="object-1"),
            patch.object(builder_routes, "release_storage", return_value=True),
            patch.object(builder_routes, "store_builder_asset", return_value=None),
            patch.object(builder_routes, "delete_builder_asset", return_value=None),
            patch.object(builder_routes, "require_entitlement", return_value={}),
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

    def post_asset(self, content, filename="asset.png", content_type="image/png", headers=None):
        return self.client.post(
            "/builder/assets/upload",
            files={"file": (filename, content, content_type)},
            headers=headers,
        )

    def post_product_media(self, content, filename="asset.png", content_type="image/png"):
        return self.client.post(
            "/ecommerce/product-media/upload",
            files={"file": (filename, content, content_type)},
        )

    def test_ecommerce_product_media_does_not_require_builder_upload_entitlement(self):
        builder_routes.reserve_storage.reset_mock()
        def ecommerce_only(_tenant, feature):
            if feature != "ecommerce_management":
                raise HTTPException(status_code=402, detail="Builder upload entitlement required")
            return {}
        with patch.object(
            builder_routes,
            "require_entitlement",
            side_effect=ecommerce_only,
        ) as entitlement:
            response = self.post_product_media(PNG_BYTES)
            entitlement.assert_called_once_with(1, "ecommerce_management")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.json()["asset_url"],
            r"^/uploads/tenant_1/builder_assets/[a-f0-9]{32}\.png$",
        )
        self.assertEqual(
            builder_routes.reserve_storage.call_args.kwargs["category"],
            "ecommerce_product_media",
        )
        self.assertEqual(
            builder_routes.reserve_storage.call_args.kwargs["tenant_quota_bytes"],
            5 * 1024 * 1024 * 1024,
        )

    def test_ecommerce_product_media_requires_commercial_ecommerce_access(self):
        builder_routes.reserve_storage.reset_mock()
        with patch.object(builder_routes, "require_entitlement",
                          side_effect=HTTPException(status_code=402, detail="Ecommerce entitlement required")):
            response = self.post_product_media(PNG_BYTES)
        self.assertEqual(response.status_code, 402)
        builder_routes.reserve_storage.assert_not_called()

    def test_ecommerce_product_media_rejects_documents(self):
        response = self.post_product_media(PDF_BYTES, "guide.pdf", "application/pdf")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Product media must be a PNG, JPG, WebP, MP4, or WebM file",
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

    def test_tenant_without_image_upload_entitlement_is_rejected_before_storage(self):
        with patch.object(
            builder_routes,
            "require_entitlement",
            side_effect=HTTPException(status_code=403, detail="Image uploads are unavailable"),
        ), patch.object(builder_routes, "reserve_storage") as reserve_storage:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Image uploads are unavailable")
        reserve_storage.assert_not_called()

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

    def test_accepts_optimized_browser_video_formats(self):
        cases = [
            (MP4_BYTES, "clip.mp4", "video/mp4", ".mp4"),
            (WEBM_BYTES, "clip.webm", "video/webm", ".webm"),
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

    def test_accepts_pdf_and_docx_documents(self):
        cases = [
            (PDF_BYTES, "guide.pdf", "application/pdf", ".pdf"),
            (
                DOCX_BYTES,
                "guide.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
            ),
        ]

        for content, filename, content_type, extension in cases:
            with self.subTest(content_type=content_type):
                response = self.post_asset(content, filename, content_type)

            self.assertEqual(response.status_code, 200)
            self.assertRegex(
                response.json()["asset_url"],
                rf"^/uploads/tenant_1/builder_assets/[a-f0-9]{{32}}{extension}$",
            )

    def test_accepts_validated_legacy_doc(self):
        with patch.object(builder_routes, "validate_builder_asset_file", return_value=None):
            response = self.post_asset(DOC_BYTES, "guide.doc", "application/msword")
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.json()["asset_url"], r"[a-f0-9]{32}\.doc$")

    def test_rejects_arbitrary_zip_as_docx(self):
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("payload.txt", "not a Word document")
        response = self.post_asset(
            output.getvalue(),
            "guide.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_filename_and_mime_mismatch(self):
        response = self.post_asset(PDF_BYTES, "guide.docx", "application/pdf")
        self.assertEqual(response.status_code, 400)
        self.assertIn("filename", response.json()["detail"].lower())

    def test_rejects_document_with_spoofed_content_type(self):
        response = self.post_asset(PNG_BYTES, "guide.pdf", "application/pdf")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Document content does not match the declared file type")

    def test_rejects_video_with_spoofed_content_type(self):
        response = self.post_asset(PNG_BYTES, "clip.mp4", "video/mp4")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Video content does not match the declared file type")

    def test_upload_creates_missing_tenant_directory(self):
        tenant_asset_dir = self.upload_dir / "tenant_1" / "builder_assets"
        self.assertFalse(tenant_asset_dir.exists())

        response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(tenant_asset_dir.is_dir())
        asset_url = response.json()["asset_url"]
        self.assertTrue((self.upload_dir / asset_url.removeprefix("/uploads/")).is_file())

    def test_upload_is_copied_to_durable_storage(self):
        with patch.object(builder_routes, "store_builder_asset") as durable_store:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 200)
        storage_key = response.json()["asset_url"].removeprefix("/uploads/")
        durable_store.assert_called_once()
        durable_kwargs = durable_store.call_args.kwargs
        self.assertEqual(durable_kwargs["storage_key"], storage_key)
        self.assertEqual(durable_kwargs["content_type"], "image/png")
        self.assertEqual(durable_kwargs["source_path"].read_bytes(), PNG_BYTES)

    def test_durable_storage_failure_does_not_publish_a_broken_url(self):
        with patch.object(
            builder_routes,
            "store_builder_asset",
            side_effect=builder_routes.BuilderAssetStorageError("unavailable"),
        ), patch.object(builder_routes, "finish_storage") as finish_storage:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "asset_storage_unavailable")
        self.assertEqual(list(self.upload_dir.rglob("*.png")), [])
        finish_storage.assert_called_once_with(
            reservation_id="reservation-1",
            succeeded=False,
        )

    def test_registry_failure_rolls_back_local_durable_and_reserved_storage(self):
        with patch.object(
            builder_routes,
            "register_builder_asset",
            side_effect=RuntimeError("registry unavailable"),
        ), patch.object(builder_routes, "delete_builder_asset") as delete_builder_asset, patch.object(
            builder_routes,
            "finish_storage",
        ) as finish_storage:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(list(self.upload_dir.rglob("*.png")), [])
        delete_builder_asset.assert_called_once()
        finish_storage.assert_called_once_with(
            reservation_id="reservation-1",
            succeeded=False,
        )

    def test_accounting_failure_rolls_back_registry_storage_and_reservation(self):
        with patch.object(
            builder_routes,
            "finish_storage",
            side_effect=[RuntimeError("commit unavailable"), None],
        ) as finish_storage, patch.object(
            builder_routes,
            "delete_builder_asset",
        ) as delete_builder_asset, patch.object(
            builder_routes,
            "delete_builder_asset_registration",
        ) as delete_registration:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(list(self.upload_dir.rglob("*.png")), [])
        delete_builder_asset.assert_called_once()
        delete_registration.assert_called_once_with(
            asset_id="asset-registry-1",
            tenant_id=1,
        )
        self.assertEqual(finish_storage.call_count, 2)
        self.assertEqual(
            finish_storage.call_args_list[1].kwargs,
            {"reservation_id": "reservation-1", "succeeded": False},
        )

    def test_uncertain_accounting_commit_releases_any_committed_storage_object(self):
        with patch.object(
            builder_routes,
            "finish_storage",
            side_effect=[RuntimeError("commit response lost"), RuntimeError("state conflict")],
        ), patch.object(builder_routes, "release_storage") as release_storage:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 503)
        release_storage.assert_called_once()
        self.assertEqual(release_storage.call_args.kwargs["tenant_id"], 1)
        self.assertEqual(release_storage.call_args.kwargs["category"], "builder_asset")
        self.assertRegex(
            release_storage.call_args.kwargs["storage_key"],
            r"^tenant_1/builder_assets/[a-f0-9]{32}\.png$",
        )

    def test_unwritable_storage_returns_controlled_cors_error(self):
        with patch.object(Path, "open", side_effect=PermissionError("denied")):
            response = self.post_asset(
                PNG_BYTES,
                headers={"Origin": "https://madarportal.com"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "asset_storage_unavailable")
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://madarportal.com",
        )


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

    def test_image_upload_25_mib_boundaries(self):
        limit = 25 * 1024 * 1024

        for size_bytes, expected_status in (
            (limit - 1, 200),
            (limit, 200),
            (limit + 1, 413),
        ):
            content = b"\x89PNG\r\n\x1a\n" + bytes(size_bytes - 8)
            with self.subTest(size_bytes=size_bytes), patch.object(
                builder_routes,
                "reserve_storage",
                return_value="reservation-1",
            ) as reserve_storage:
                response = self.post_asset(content, "asset.png", "image/png")

            self.assertEqual(response.status_code, expected_status)
            if expected_status == 200:
                self.assertEqual(
                    reserve_storage.call_args.kwargs["size_bytes"],
                    size_bytes,
                )
            else:
                reserve_storage.assert_not_called()

    def test_validation_failure_removes_partial_file_and_releases_reservation(self):
        with patch.object(
            builder_routes,
            "validate_builder_asset_file",
            side_effect=builder_routes.BuilderAssetValidationError("invalid"),
        ), patch.object(builder_routes, "finish_storage") as finish_storage:
            response = self.post_asset(PNG_BYTES)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.upload_dir.rglob("*.png")), [])
        finish_storage.assert_called_once_with(
            reservation_id="reservation-1",
            succeeded=False,
        )

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
