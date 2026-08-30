import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))

from deployment.lib.migration_executor import LockedMigrationExecutor, MigrationManifest


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def execute(self, query, params=None):
        text = str(query)
        if "pg_try_advisory_lock" in text:
            self.result = (self.connection.lock_available,)
        elif "pg_advisory_unlock" in text:
            self.result = (True,)
        elif "select schema_version" in text:
            self.result = (self.connection.schema,)
        elif "MIGRATION_TO=" in text:
            self.connection.schema = int(text.rsplit("MIGRATION_TO=", 1)[1].split()[0])
            self.result = None
        else:
            self.result = None
    def fetchone(self): return self.result


class FakeConnection:
    def __init__(self, schema=81, lock_available=True):
        self.schema = schema
        self.lock_available = lock_available
        self.autocommit = False
        self.closed = False
    def cursor(self): return FakeCursor(self)
    def close(self): self.closed = True


class MigrationExecutorTests(unittest.TestCase):
    def fixture(self, root: Path):
        repository = root / "repo"
        migration_dir = repository / "web/database/migrations"
        migration_dir.mkdir(parents=True)
        entries = []
        for number in (82, 83):
            path = migration_dir / f"{number:03d}.sql"
            path.write_text(f"-- MIGRATION_TO={number}\n", encoding="utf-8")
            entries.append({
                "number": number,
                "path": str(path.relative_to(repository)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "from_schema": number - 1,
                "to_schema": number,
                "compatibility": "expand-only",
            })
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps({"release_sha": "STAGING", "migrations": entries}), encoding="utf-8")
        backup = root / "backup"
        backup.mkdir()
        return repository, manifest_path, backup

    def test_applies_contiguous_manifest_and_writes_durable_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, backup = self.fixture(root)
            connection = FakeConnection()
            state_file = root / "state/migration.json"
            executor = LockedMigrationExecutor(
                connection_factory=lambda: connection,
                manifest=MigrationManifest.load(manifest_path, repository),
                state_file=state_file,
                backup_dir=backup,
                backup_verifier=lambda _path: None,
            )
            result = executor.run()
            persisted = json.loads(state_file.read_text())
        self.assertEqual(result["observed_schema"], 83)
        self.assertEqual(persisted["status"], "completed")
        self.assertEqual([row["status"] for row in persisted["migrations"]], ["applied", "applied"])
        self.assertTrue(connection.closed)

    def test_resume_from_schema_82_skips_first_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, backup = self.fixture(root)
            connection = FakeConnection(schema=82)
            executor = LockedMigrationExecutor(
                connection_factory=lambda: connection,
                manifest=MigrationManifest.load(manifest_path, repository),
                state_file=root / "state.json", backup_dir=backup,
                backup_verifier=lambda _path: None,
            )
            result = executor.run()
        self.assertEqual(result["observed_schema"], 83)
        self.assertEqual(result["migrations"][0]["status"], "already_applied")

    def test_refuses_checksum_mismatch_before_opening_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, backup = self.fixture(root)
            manifest = MigrationManifest.load(manifest_path, repository)
            manifest.migrations[0].path.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "migration_checksum_mismatch"):
                LockedMigrationExecutor(
                    connection_factory=lambda: self.fail("database must not open"),
                    manifest=manifest, state_file=root / "state.json", backup_dir=backup,
                    backup_verifier=lambda _path: None,
                ).run()

    def test_refuses_missing_backup_and_held_database_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, backup = self.fixture(root)
            manifest = MigrationManifest.load(manifest_path, repository)
            with self.assertRaisesRegex(RuntimeError, "backup_stale"):
                LockedMigrationExecutor(
                    connection_factory=lambda: FakeConnection(), manifest=manifest,
                    state_file=root / "state.json", backup_dir=backup,
                    backup_verifier=lambda _path: (_ for _ in ()).throw(RuntimeError("backup_stale")),
                ).run()
            with self.assertRaisesRegex(RuntimeError, "migration_lock_held"):
                LockedMigrationExecutor(
                    connection_factory=lambda: FakeConnection(lock_available=False), manifest=manifest,
                    state_file=root / "state2.json", backup_dir=backup,
                    backup_verifier=lambda _path: None,
                ).run()

    def test_manifest_rejects_repository_escape_and_unsupported_class(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, _backup = self.fixture(root)
            raw = json.loads(manifest_path.read_text())
            raw["migrations"][0]["path"] = "../outside.sql"
            manifest_path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "escapes repository"):
                MigrationManifest.load(manifest_path, repository)

            _repository, manifest_path, _backup = self.fixture(root / "class")
            raw = json.loads(manifest_path.read_text())
            raw["migrations"][0]["compatibility"] = "coordinated"
            manifest_path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "expand/forward-compatible"):
                MigrationManifest.load(manifest_path, _repository)

    def test_manifest_rejects_noncontiguous_transitions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, _backup = self.fixture(root)
            raw = json.loads(manifest_path.read_text())
            raw["migrations"][1].update(
                number=84,
                from_schema=83,
                to_schema=84,
            )
            manifest_path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "not contiguous"):
                MigrationManifest.load(manifest_path, repository)


if __name__ == "__main__":
    unittest.main()
