import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
SCRIPT = WEB_ROOT / "deployment" / "bin" / "madar-provision-supabase-secret"
loader = importlib.machinery.SourceFileLoader("madar_provision_supabase_secret", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
provisioner = importlib.util.module_from_spec(spec)
loader.exec_module(provisioner)


SECRET_FIXTURE = "sb_secret_synthetic_fixture_not_a_credential"


class SupabaseSecretProvisioningTests(unittest.TestCase):
    def test_atomic_update_preserves_mode_and_creates_protected_backup(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            env_file.write_text(
                "SUPABASE_URL=https://example.invalid\n"
                "SUPABASE_SERVICE_KEY:legacy-fixture\n",
                encoding="utf-8",
            )
            env_file.chmod(0o600)
            backup = provisioner.provision(
                env_file,
                SECRET_FIXTURE,
                timestamp="fixture",
            )
            updated = env_file.read_text(encoding="utf-8")
            original = backup.read_text(encoding="utf-8")
            self.assertIn(f"SUPABASE_SERVICE_KEY:{SECRET_FIXTURE}", updated)
            self.assertIn("SUPABASE_SERVICE_KEY:legacy-fixture", original)
            self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_rejects_broad_secret_input_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            secret_file = Path(root) / "secret"
            secret_file.write_text(SECRET_FIXTURE + "\n", encoding="utf-8")
            secret_file.chmod(0o640)
            with self.assertRaisesRegex(RuntimeError, "permissions"):
                provisioner.read_secret_file(secret_file)

    def test_rejects_ambiguous_assignments(self):
        original = "SUPABASE_SERVICE_KEY=first\nSUPABASE_SERVICE_KEY:second\n"
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            provisioner.render_environment(original, SECRET_FIXTURE)

    def test_rejects_non_secret_api_key_type(self):
        with self.assertRaisesRegex(RuntimeError, "format"):
            provisioner.validate_secret("sb_publishable_synthetic_fixture")


if __name__ == "__main__":
    unittest.main()
