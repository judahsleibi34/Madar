import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services.url_validation import validate_builder_schema_urls, validate_public_url


class UrlValidationTests(unittest.TestCase):
    def test_accepts_https_url(self):
        self.assertEqual(
            validate_public_url(" https://example.com/image.png ", field_name="Image URL"),
            "https://example.com/image.png",
        )

    def test_rejects_blocked_schemes_and_protocol_relative_urls(self):
        unsafe_values = [
            "javascript:alert(1)",
            "data:image/svg+xml;base64,PHN2Zy8+",
            "vbscript:msgbox(1)",
            "file:///etc/passwd",
            "ftp://example.com/file.png",
            "//evil.example/image.png",
        ]

        for unsafe_value in unsafe_values:
            with self.subTest(unsafe_value=unsafe_value), self.assertRaises(HTTPException) as error:
                validate_public_url(unsafe_value, field_name="Image URL", allow_relative=True)

            self.assertEqual(error.exception.status_code, 400)

    def test_rejects_http_by_default(self):
        with self.assertRaises(HTTPException) as error:
            validate_public_url("http://example.com/image.png", field_name="Image URL")

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("https://", error.exception.detail)

    def test_allows_http_when_explicitly_enabled(self):
        with patch.dict(os.environ, {"ALLOW_INSECURE_HTTP_URLS": "true"}):
            self.assertEqual(
                validate_public_url("http://localhost:3000/image.png", field_name="Image URL"),
                "http://localhost:3000/image.png",
            )

    def test_relative_paths_require_explicit_allowance(self):
        with self.assertRaises(HTTPException):
            validate_public_url("/contact", field_name="Action URL")

        self.assertEqual(
            validate_public_url("/contact", field_name="Action URL", allow_relative=True),
            "/contact",
        )

    def test_accepts_managed_upload_asset_path(self):
        self.assertEqual(
            validate_public_url(
                "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.webp",
                field_name="Image URL",
                allow_relative=True,
            ),
            "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.webp",
        )

    def test_rejects_unmanaged_upload_paths(self):
        unmanaged_paths = [
            "/uploads/logo.png",
            "/uploads/tenant_1/avatar.png",
            "/uploads/tenant_1/builder_assets/not-random.png",
            "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png?x=1",
        ]

        for path in unmanaged_paths:
            with self.subTest(path=path), self.assertRaises(HTTPException) as error:
                validate_public_url(path, field_name="Image URL", allow_relative=True)

            self.assertEqual(error.exception.status_code, 400)

    def test_rejects_svg_urls(self):
        for svg_url in ["https://example.com/logo.svg", "/uploads/logo.svgz"]:
            with self.subTest(svg_url=svg_url), self.assertRaises(HTTPException) as error:
                validate_public_url(svg_url, field_name="Logo URL", allow_relative=True)

            self.assertEqual(error.exception.status_code, 400)

    def test_rejects_unsafe_urls_in_all_supported_carousel_variants(self):
        for element_type in ("carouselSpotlight", "carouselStack", "carouselEditorial"):
            with self.subTest(element_type=element_type), self.assertRaises(HTTPException):
                validate_builder_schema_urls(
                    {
                        "pages": [
                            {
                                "sections": [
                                    {
                                        "elements": [
                                            {
                                                "id": "carousel-1",
                                                "type": element_type,
                                                "content": "Title\nDescription\njavascript:alert(1)",
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                )


if __name__ == "__main__":
    unittest.main()
