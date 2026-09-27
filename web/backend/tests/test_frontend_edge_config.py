import os
import unittest
from pathlib import Path


ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT", Path(__file__).resolve().parents[2]))


class FrontendEdgeConfigTests(unittest.TestCase):
    def test_csp_and_hsts_policy_are_explicit(self):
        headers = (ROOT / "frontend" / "security_headers.conf.template").read_text(encoding="utf-8")
        self.assertIn("script-src 'self'", headers)
        self.assertNotIn("unsafe-eval", headers)
        self.assertIn("frame-ancestors 'none'", headers)
        self.assertIn("object-src 'none'", headers)
        self.assertIn("${MADAR_HSTS}", headers)
        storefront_headers = (ROOT / "frontend" / "storefront_frame_headers.conf.template").read_text(encoding="utf-8")
        self.assertIn("frame-ancestors https://${MADAR_PUBLIC_SITE_DOMAIN}", storefront_headers)
        self.assertNotIn("X-Frame-Options", storefront_headers)
        preview_headers = (ROOT / "frontend" / "admin_preview_frame_headers.conf.template").read_text(encoding="utf-8")
        self.assertIn("frame-ancestors 'self'", preview_headers)
        self.assertIn('X-Frame-Options "SAMEORIGIN"', preview_headers)
        self.assertIn('X-Robots-Tag "noindex, nofollow, noarchive"', preview_headers)
        self.assertNotIn("frame-ancestors 'none'", preview_headers)
        self.assertNotIn('X-Frame-Options "DENY"', preview_headers)
        self.assertNotIn("frame-ancestors *", preview_headers)

    def test_frontend_runtime_is_non_root_and_digest_pinned(self):
        dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER nginx", dockerfile)
        self.assertIn("RUN npm ci", dockerfile)
        self.assertEqual(dockerfile.count("@sha256:"), 2)
        self.assertIn("EXPOSE 8080", dockerfile)

    def test_same_origin_api_proxy_preserves_trusted_forwarding_context(self):
        nginx = (ROOT / "frontend" / "nginx.conf.template").read_text(encoding="utf-8")
        self.assertIn("location ^~ /api/", nginx)
        self.assertIn("proxy_pass http://backend:8000/", nginx)
        self.assertIn("proxy_set_header Host $host", nginx)
        self.assertIn("proxy_set_header X-Forwarded-Host $host", nginx)
        self.assertIn("proxy_set_header X-Forwarded-Proto $madar_forwarded_proto", nginx)
        self.assertIn("proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for", nginx)
        self.assertIn("proxy_set_header X-Real-IP $remote_addr", nginx)
        self.assertIn("proxy_set_header X-Request-ID $madar_request_id", nginx)
        self.assertNotIn("location ^~ /api/ {\n        try_files", nginx)

    def test_api_assets_cannot_be_intercepted_by_static_file_regex(self):
        nginx = (ROOT / "frontend" / "nginx.conf.template").read_text(encoding="utf-8")
        self.assertIn("location ^~ /api/", nginx)
        self.assertIn("location ~* \\.(?:js|css|png|jpg|jpeg|gif|ico|svg|webp|woff2?|pdf)$", nginx)

    def test_compose_drops_privileges_and_keeps_dev_ports_loopback_only(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        development = (ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(compose.count('cap_drop: ["ALL"]'), 4)
        self.assertGreaterEqual(compose.count('security_opt: ["no-new-privileges:true"]'), 4)
        self.assertGreaterEqual(compose.count("read_only: true"), 4)
        self.assertIn('"127.0.0.1:3001:8080"', development)

    def test_backend_runtime_is_non_root_and_digest_pinned(self):
        dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER 65534:65534", dockerfile)
        self.assertIn("@sha256:", dockerfile)


if __name__ == "__main__":
    unittest.main()
