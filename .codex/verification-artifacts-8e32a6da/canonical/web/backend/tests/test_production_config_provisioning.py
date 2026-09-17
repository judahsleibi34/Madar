import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
SCRIPT = WEB_ROOT / "deployment" / "bin" / "madar-provision-production-config"
loader = importlib.machinery.SourceFileLoader("madar_production_config", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class ProductionConfigProvisioningTests(unittest.TestCase):
    def test_dry_run_does_not_modify_or_create_backup(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            backup = Path(root) / "backup"
            env_file.write_text("APP_ENV=production\nALLOW_REMOTE_DATASET_URLS=true\n")
            env_file.chmod(0o600)
            before = env_file.read_bytes()
            changed = module.provision(env_file, backup, apply=False)
            self.assertEqual(changed, ["CSRF_SECRET", "ALLOW_REMOTE_DATASET_URLS"])
            self.assertEqual(env_file.read_bytes(), before)
            self.assertFalse(backup.exists())

    def test_apply_is_atomic_restrictive_and_backup_first(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            backup = Path(root) / "backup"
            env_file.write_text("APP_ENV: production\nALLOW_REMOTE_DATASET_URLS=true\n")
            env_file.chmod(0o600)
            before = env_file.read_bytes()
            module.provision(env_file, backup, apply=True)
            result = env_file.read_text()
            self.assertIn("ALLOW_REMOTE_DATASET_URLS=false", result)
            self.assertIn("CSRF_SECRET=", result)
            self.assertNotIn("ALLOW_REMOTE_DATASET_URLS=true", result)
            backups = list(backup.iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), before)
            self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_duplicate_managed_variable_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            env_file.write_text("CSRF_SECRET=one\nCSRF_SECRET=two\n")
            env_file.chmod(0o600)
            with self.assertRaisesRegex(RuntimeError, "duplicate managed"):
                module.provision(env_file, Path(root) / "backup", apply=False)

    def test_existing_csrf_is_not_rotated_implicitly(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            env_file.write_text("CSRF_SECRET=existing-dedicated-value\nALLOW_REMOTE_DATASET_URLS=false\n")
            env_file.chmod(0o600)
            before = env_file.read_bytes()
            changed = module.provision(env_file, Path(root) / "backup", apply=True)
            self.assertEqual(changed, [])
            self.assertEqual(env_file.read_bytes(), before)

    def test_group_readable_environment_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            env_file.write_text("APP_ENV=production\n")
            env_file.chmod(0o640)
            with self.assertRaisesRegex(RuntimeError, "permissions too broad"):
                module.provision(env_file, Path(root) / "backup", apply=False)


if __name__ == "__main__":
    unittest.main()
