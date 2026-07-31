import re
import os
import unittest
from pathlib import Path


ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
SCRIPT = ROOT / "scripts" / "prepare_production_storage.sh"
DROP_IN = (
    ROOT
    / "deployment"
    / "systemd"
    / "madar-auto-deploy.service.d"
    / "storage-preparation.conf"
)


class ProductionStoragePreparationTests(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")
        self.drop_in = DROP_IN.read_text(encoding="utf-8")

    def test_all_and_only_fixed_storage_roots_are_prepared(self):
        expected = {
            "backend/private_uploads",
            "backend/avatar_uploads",
            "backend/private_generated_charts",
            "backend/uploads",
        }
        configured = set(re.findall(r'^    "(backend/[^\"]+)"$', self.script, re.MULTILINE))
        self.assertEqual(configured, expected)
        self.assertIn("if (( $# != 0 ))", self.script)
        self.assertNotIn("STORAGE_PATHS:-", self.script)

    def test_creation_ownership_mode_and_preservation_are_explicit(self):
        self.assertIn("install -d", self.script)
        self.assertIn("readonly STORAGE_UID=65534", self.script)
        self.assertIn("readonly STORAGE_GID=65534", self.script)
        self.assertIn("readonly STORAGE_MODE=0755", self.script)
        self.assertIn('chown -R -- "$STORAGE_UID:$STORAGE_GID" "$target_path"', self.script)
        self.assertNotRegex(self.script, r"\brm\b|\btruncate\b|chmod\s+777")
        self.assertIn('[[ -L "$target_path" ]]', self.script)

    def test_root_preparation_precedes_compose_deployment(self):
        self.assertIn("ExecStartPre=+", self.drop_in)
        self.assertIn("/scripts/prepare_production_storage.sh", self.drop_in)
        self.assertNotIn("docker compose", self.script)

    def test_backend_image_remains_non_root(self):
        dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(dockerfile, r"(?m)^USER 65534:65534$")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        backend_section = compose.split("\n  backend:\n", 1)[1].split("\n  notification-worker:\n", 1)[0]
        self.assertNotIn("user: root", backend_section)


if __name__ == "__main__":
    unittest.main()
