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

    def test_frontend_runtime_is_non_root_and_digest_pinned(self):
        dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER nginx", dockerfile)
        self.assertIn("RUN npm ci", dockerfile)
        self.assertEqual(dockerfile.count("@sha256:"), 2)
        self.assertIn("EXPOSE 8080", dockerfile)

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
