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

    def backup_environment(self, root, timestamp="20260720T000000Z"):
        root = Path(root)
        source_root = root / "source"
        environment = {
            "MADAR_BACKUP_DIR": str(root / "backups"),
            "PGHOST": "source.invalid",
            "PGPORT": "5432",
            "PGUSER": "backup",
            "PGPASSWORD": "synthetic-test-password",
            "PGDATABASE": "madar",
            "MADAR_BACKUP_TIMESTAMP": timestamp,
        }
        for key, name in (
            ("MADAR_BUILDER_ASSETS_DIR", "builder-assets"),
            ("MADAR_PRIVATE_UPLOADS_DIR", "private-uploads"),
            ("MADAR_GENERATED_ARTIFACTS_DIR", "generated-artifacts"),
            ("MADAR_AVATARS_DIR", "avatars"),
        ):
            source = source_root / name
            source.mkdir(parents=True)
            (source / "fixture.txt").write_text(name, encoding="utf-8")
            environment[key] = str(source)
        return environment

    def fake_postgres_tools(self, root, *, succeeds=True):
        fake_bin = Path(root) / "fake-bin"
        fake_bin.mkdir()
        executable = fake_bin / "pg_dump"
        if succeeds:
            executable.write_text(
                "#!/bin/sh\n"
                "for arg in \"$@\"; do\n"
                "  case \"$arg\" in --file=*) printf fixture > \"${arg#*=}\";; esac\n"
                "done\n",
                encoding="utf-8",
            )
        else:
            executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        executable.chmod(0o700)
        pg_restore = fake_bin / "pg_restore"
        pg_restore.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        pg_restore.chmod(0o700)
        psql = fake_bin / "psql"
        psql.write_text(
            "#!/bin/sh\n"
            "case \"$*\" in *server_version*) printf '17.6\\n';; *) printf '82\\n';; esac\n",
            encoding="utf-8",
        )
        psql.chmod(0o700)
        return f"{fake_bin}:{os.environ.get('PATH', '')}"

    def test_backup_requires_environment(self):
        result = self.run_script("backup_madar.sh", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MADAR_BACKUP_DIR", result.stderr)

    def test_backup_dry_run_constructs_commands_without_executing(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_script("backup_madar.sh", "--dry-run", env={
                "MADAR_BACKUP_DIR": root,
                "PGHOST": "source.invalid",
                "PGPORT": "5432",
                "PGUSER": "backup",
                "PGPASSWORD": "synthetic-test-password",
                "PGDATABASE": "madar",
                "MADAR_BACKUP_TIMESTAMP": "20260720T000000Z",
            })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pg_dump --format=custom", result.stdout)
        self.assertNotIn("source.invalid", result.stdout)

    def test_backup_is_published_only_after_verified_completion(self):
        with tempfile.TemporaryDirectory() as root:
            env = self.backup_environment(root)
            env["PATH"] = self.fake_postgres_tools(root)
            result = self.run_script("backup_madar.sh", env=env)
            published = Path(root) / "backups" / "madar-20260720T000000Z"

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((published / "BACKUP_COMPLETE").is_file())
            self.assertIn("MADAR_BACKUP_FORMAT=3", (published / "backup.env").read_text())
            self.assertTrue((published / "manifest.json").is_file())
            self.assertFalse(list((Path(root) / "backups").glob(".*.incomplete.*")))
            verified = self.run_script("verify_backup.sh", published, env={"PATH": env["PATH"]})
            self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_failed_backup_never_occupies_final_recovery_path(self):
        with tempfile.TemporaryDirectory() as root:
            env = self.backup_environment(root)
            env["PATH"] = self.fake_postgres_tools(root, succeeds=False)
            result = self.run_script("backup_madar.sh", env=env)
            backup_root = Path(root) / "backups"

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((backup_root / "madar-20260720T000000Z").exists())
            self.assertEqual(len(list(backup_root.glob(".*.incomplete.*"))), 0)

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
                "MADAR_SOURCE_DATABASE_ID": "source",
                "MADAR_RESTORE_DATABASE_ID": "source",
                "MADAR_RESTORE_PGHOST": "localhost",
                "MADAR_RESTORE_PGPORT": "5432",
                "MADAR_RESTORE_PGUSER": "restore",
                "MADAR_RESTORE_PGPASSWORD": "synthetic-test-password",
                "MADAR_RESTORE_PGDATABASE": "madar_restore_test",
                "MADAR_RESTORE_CONFIRM_ISOLATED": "YES",
            }
            same = self.run_script("restore_madar.sh", "--dry-run", backup, env=common)
            self.assertIn("must differ", same.stderr)
            common["MADAR_RESTORE_DATABASE_ID"] = "other"
            common["MADAR_RESTORE_PGHOST"] = "prod.example.com"
            unsafe = self.run_script("restore_madar.sh", "--dry-run", backup, env=common)
            self.assertIn("not recognizably isolated", unsafe.stderr)

    def test_restore_dry_run_verifies_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            env = {
                "MADAR_SOURCE_DATABASE_ID": "production",
                "MADAR_RESTORE_DATABASE_ID": "isolated-test",
                "MADAR_RESTORE_PGHOST": "localhost",
                "MADAR_RESTORE_PGPORT": "5432",
                "MADAR_RESTORE_PGUSER": "restore",
                "MADAR_RESTORE_PGPASSWORD": "synthetic-test-password",
                "MADAR_RESTORE_PGDATABASE": "madar_restore_test",
                "MADAR_RESTORE_CONFIRM_ISOLATED": "YES",
                "PATH": self.fake_postgres_tools(root),
            }
            for name in ("BUILDER_ASSETS", "PRIVATE_UPLOADS", "GENERATED_ARTIFACTS", "AVATARS"):
                env[f"MADAR_RESTORE_{name}_DIR"] = str(Path(root) / name.lower())
            result = self.run_script("restore_madar.sh", "--dry-run", backup, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pg_restore", result.stdout)

    def test_offhost_replication_refuses_an_unmounted_local_directory(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            backup = root / "madar-20260720T000000Z"
            mount = root / "drive"
            recipients = root / "recipients.txt"
            backup.mkdir()
            mount.mkdir()
            recipients.write_text("age1synthetic-public-recipient\n", encoding="utf-8")
            result = self.run_script("replicate_backup_offhost.sh", backup, env={
                "MADAR_OFFHOST_MOUNT": str(mount),
                "MADAR_OFFHOST_VOLUME_ID": "expected-drive",
                "MADAR_BACKUP_AGE_RECIPIENTS_FILE": str(recipients),
            })
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a mounted filesystem", result.stderr)
            self.assertFalse((mount / "madar-encrypted").exists())

    def test_offhost_replication_requires_exact_volume_identity_before_writing(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            backup = root / "madar-20260720T000000Z"
            mount = root / "drive"
            recipients = root / "recipients.txt"
            fake_bin = root / "fake-bin"
            backup.mkdir()
            mount.mkdir()
            fake_bin.mkdir()
            recipients.write_text("age1synthetic-public-recipient\n", encoding="utf-8")
            (mount / ".madar-backup-volume").write_text("wrong-drive\n", encoding="utf-8")
            mountpoint = fake_bin / "mountpoint"
            mountpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mountpoint.chmod(0o700)
            findmnt = fake_bin / "findmnt"
            findmnt.write_text(f"#!/bin/sh\nprintf '%s\\n' '{mount}'\n", encoding="utf-8")
            findmnt.chmod(0o700)
            result = self.run_script("replicate_backup_offhost.sh", backup, env={
                "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
                "MADAR_OFFHOST_MOUNT": str(mount),
                "MADAR_OFFHOST_VOLUME_ID": "expected-drive",
                "MADAR_BACKUP_AGE_RECIPIENTS_FILE": str(recipients),
            })
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("identity does not match", result.stderr)
            self.assertFalse((mount / "madar-encrypted").exists())


if __name__ == "__main__":
    unittest.main()
