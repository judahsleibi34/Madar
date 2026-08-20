import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BackupToolingTests(unittest.TestCase):
    def run_script(self, name, *args, env=None):
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / name), *map(str, args)],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", ""), **(env or {})},
            text=True,
            capture_output=True,
            check=False,
        )

    def fixture(self, root):
        backup = Path(root) / "madar-20260720T000000Z"
        for name in ("builder-assets", "private-uploads", "generated-artifacts", "avatars"):
            (backup / "files" / name).mkdir(parents=True)
        (backup / "database.dump").write_bytes(b"fixture database")
        (backup / "backup.env").write_text("MADAR_BACKUP_FORMAT=1\n", encoding="utf-8")
        lines = []
        for path in sorted(p for p in backup.rglob("*") if p.is_file()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(backup)}\n")
        (backup / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
        return backup

    def test_backup_requires_environment(self):
        result = self.run_script("backup_madar.sh", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MADAR_BACKUP_DIR", result.stderr)

    def test_backup_dry_run_constructs_commands_without_executing(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_script("backup_madar.sh", "--dry-run", env={
                "MADAR_BACKUP_DIR": root,
                "MADAR_DATABASE_URL": "postgresql://source.invalid/madar",
                "MADAR_BACKUP_TIMESTAMP": "20260720T000000Z",
            })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pg_dump --format=custom", result.stdout)
        self.assertNotIn("source.invalid", result.stdout)

    def test_verifier_rejects_missing_member_and_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            (backup / "files" / "avatars").rmdir()
            missing = self.run_script("verify_backup.sh", backup)
            self.assertIn("missing backup member", missing.stderr)
            (backup / "files" / "avatars").mkdir()
            (backup / "database.dump").write_bytes(b"tampered")
            mismatch = self.run_script("verify_backup.sh", backup)
            self.assertIn("checksum verification failed", mismatch.stderr)

    def test_restore_refuses_same_database_and_unsafe_target(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            common = {
                "MADAR_DATABASE_URL": "postgresql://localhost/source",
                "MADAR_RESTORE_DATABASE_URL": "postgresql://localhost/source",
                "MADAR_RESTORE_CONFIRM_ISOLATED": "YES",
            }
            same = self.run_script("restore_madar.sh", "--dry-run", backup, env=common)
            self.assertIn("must differ", same.stderr)
            common["MADAR_RESTORE_DATABASE_URL"] = "postgresql://prod.example.com/madar"
            unsafe = self.run_script("restore_madar.sh", "--dry-run", backup, env=common)
            self.assertIn("not recognizably isolated", unsafe.stderr)

    def test_restore_dry_run_verifies_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            env = {
                "MADAR_DATABASE_URL": "postgresql://source.invalid/madar",
                "MADAR_RESTORE_DATABASE_URL": "postgresql://localhost/madar_restore_test",
                "MADAR_RESTORE_CONFIRM_ISOLATED": "YES",
            }
            for name in ("BUILDER_ASSETS", "PRIVATE_UPLOADS", "GENERATED_ARTIFACTS", "AVATARS"):
                env[f"MADAR_RESTORE_{name}_DIR"] = str(Path(root) / name.lower())
            result = self.run_script("restore_madar.sh", "--dry-run", backup, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pg_restore", result.stdout)


if __name__ == "__main__":
    unittest.main()
