import hashlib
import json
import os
import sys
import tempfile
import unittest
import multiprocessing
import stat
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock, patch

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))

from deployment.lib.migration_executor import LockedMigrationExecutor, MigrationManifest
from deployment.lib import migration_executor as migration_module


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
            self.connection.applied.append(self.connection.schema)
            self.result = None
        else:
            self.result = None
    def fetchone(self): return self.result


class FakeConnection:
    def __init__(self, schema=81, lock_available=True):
        self.schema = schema
        self.applied = []
        self.lock_available = lock_available
        self.autocommit = False
        self.closed = False
    def cursor(self): return FakeCursor(self)
    def close(self): self.closed = True


class RecordingCursor(FakeCursor):
    def execute(self, query, params=None):
        if 'MIGRATION_TO=' in str(query):
            self.connection.executed_sql.append(str(query))
        return super().execute(query, params)


class RecordingConnection(FakeConnection):
    def __init__(self):
        super().__init__()
        self.executed_sql = []
    def cursor(self): return RecordingCursor(self)


class MigrationExecutorTests(unittest.TestCase):
    def fixture(self, root: Path, numbers=(82, 83)):
        repository = root / "repo"
        migration_dir = repository / "web/database/migrations"
        migration_dir.mkdir(parents=True)
        entries = []
        for number in numbers:
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

    def test_completion_guard_observes_target_on_the_same_session_before_completed_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repository,path,backup=self.fixture(root)
            connection=FakeConnection();state_file=root/'execution.json';observed=[]
            def complete(cursor):
                observed.append(cursor.connection)
                self.assertEqual(cursor.connection.schema,83)
                self.assertFalse(cursor.connection.closed)
                self.assertEqual(json.loads(state_file.read_bytes())['status'],'running')
            result=LockedMigrationExecutor(connection_factory=lambda:connection,manifest=MigrationManifest.load(path,repository),
                state_file=state_file,backup_dir=backup,backup_verifier=lambda _:None,completion_guard=complete).run()
            self.assertEqual(observed,[connection]);self.assertEqual(result['status'],'completed')

    def test_completion_guard_failure_preserves_committed_schema_and_consumes_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repository,path,backup=self.fixture(root)
            connection=FakeConnection();state_file=root/'execution.json'
            executor=LockedMigrationExecutor(connection_factory=lambda:connection,
                manifest=replace(MigrationManifest.load(path,repository),coordinated=True),
                state_file=state_file,backup_dir=backup,backup_verifier=lambda _:None,migration_guard=lambda *args:None,
                completion_guard=Mock(side_effect=RuntimeError('synthetic_target_boundary_changed')))
            with self.assertRaisesRegex(RuntimeError,'target_boundary_changed'):executor.run()
            state=json.loads(state_file.read_bytes())
            self.assertEqual((state['status'],state['observed_schema']),('failed',83))
            self.assertEqual(connection.schema,83);self.assertTrue(connection.closed)
            with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):executor.run()

    def test_coordinated_processes_cannot_both_claim_the_same_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repository,path,backup=self.fixture(root)
            manifest=replace(MigrationManifest.load(path,repository),coordinated=True)
            context=multiprocessing.get_context('fork');barrier=context.Barrier(2)
            children=[];readers=[]
            def attempt(writer):
                try:
                    result=LockedMigrationExecutor(connection_factory=FakeConnection,manifest=manifest,
                        state_file=root/'execution.json',backup_dir=backup,backup_verifier=lambda _:barrier.wait(10),
                        migration_guard=lambda *args:None).run()
                    writer.send(result['status'])
                except RuntimeError as error:writer.send(str(error))
                finally:writer.close()
            try:
                for _ in range(2):
                    reader,writer=context.Pipe(duplex=False)
                    child=context.Process(target=attempt,args=(writer,));child.start();writer.close()
                    children.append(child);readers.append(reader)
                outcomes=[]
                for reader in readers:
                    self.assertTrue(reader.poll(15),'Owned executor process did not finish')
                    outcomes.append(reader.recv())
                self.assertEqual(sorted(outcomes),['completed','coordinated_migration_attempt_consumed'])
                self.assertEqual(json.loads((root/'execution.json').read_bytes())['status'],'completed')
            finally:
                for child in children:
                    child.join(2)
                    if child.is_alive():child.kill();child.join(2)
                for reader in readers:reader.close()

    def test_atomic_receipt_syncs_file_then_replacement_and_parent_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'new-parent'/'new-attempt'/'execution.json';events=[]
            original_sync=migration_module.os.fsync;original_replace=migration_module.os.replace
            def sync(descriptor):
                events.append('directory_sync' if stat.S_ISDIR(os.fstat(descriptor).st_mode) else 'file_sync')
                return original_sync(descriptor)
            def replace_file(*args):events.append('replace');return original_replace(*args)
            with patch.object(migration_module.os,'fsync',side_effect=sync),patch.object(migration_module.os,'replace',side_effect=replace_file):
                migration_module.atomic_json(target,{'synthetic':'durable receipt'})
            self.assertEqual(events[-3:],['file_sync','replace','directory_sync'])
            self.assertGreaterEqual(events.count('directory_sync'),3)

    def test_schema_105_bridge_requires_backup_then_applies_only_106_through_108(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository, manifest_path, backup = self.fixture(root, (106, 107, 108))
            connection = FakeConnection(schema=105)
            events = []

            def verified_backup(path):
                self.assertEqual(path, backup)
                events.append("backup_verified")

            def connect():
                events.append("database_opened")
                return connection

            manifest = MigrationManifest.load(manifest_path, repository)
            with self.assertRaisesRegex(RuntimeError, "backup_not_verified"):
                LockedMigrationExecutor(
                    connection_factory=connect,
                    manifest=manifest,
                    state_file=root / "unverified.json",
                    backup_dir=backup,
                    backup_verifier=lambda _path: (_ for _ in ()).throw(
                        RuntimeError("backup_not_verified")
                    ),
                ).run()
            self.assertEqual(events, [])
            self.assertEqual(connection.applied, [])

            executor = LockedMigrationExecutor(
                connection_factory=connect,
                manifest=manifest,
                state_file=root / "state.json",
                backup_dir=backup,
                backup_verifier=verified_backup,
            )
            result = executor.run()

        self.assertEqual(events, ["backup_verified", "database_opened"])
        self.assertEqual(connection.applied, [106, 107, 108])
        self.assertEqual(result["observed_schema"], 108)
        self.assertEqual(
            [row["number"] for row in result["migrations"]],
            [106, 107, 108],
        )

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

    def test_backup_time_file_substitution_cannot_change_executed_sql_or_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            repository,manifest_path,backup=self.fixture(root)
            manifest=MigrationManifest.load(manifest_path,repository)
            approved=[migration.path.read_text() for migration in manifest.migrations]
            connection=RecordingConnection()
            def substitute(_):
                manifest.migrations[0].path.write_text('-- unreviewed substitution\n'+approved[0])
            result=LockedMigrationExecutor(connection_factory=lambda:connection,manifest=manifest,
                state_file=root/'state.json',backup_dir=backup,backup_verifier=substitute).run()
            self.assertNotEqual(manifest.migrations[0].path.read_text(),approved[0])
            self.assertEqual(connection.executed_sql,approved)
            self.assertEqual([row['checksum'] for row in result['migrations']],
                             [hashlib.sha256(value.encode()).hexdigest() for value in connection.executed_sql])

    def test_coordinated_guard_time_replace_or_symlink_cannot_substitute_sql(self):
        for replacement in ('bytes','symlink'):
            with self.subTest(replacement=replacement),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                repository,manifest_path,backup=self.fixture(root)
                manifest=replace(MigrationManifest.load(manifest_path,repository),coordinated=True)
                approved=[migration.path.read_text() for migration in manifest.migrations]
                connection=RecordingConnection()
                def guard(cursor,migration):
                    if migration.number!=82:return
                    changed='-- unreviewed guard-time substitution\n'+approved[0]
                    if replacement=='bytes':migration.path.write_text(changed)
                    else:
                        evil=root/'unreviewed.sql';evil.write_text(changed)
                        migration.path.unlink();migration.path.symlink_to(evil)
                LockedMigrationExecutor(connection_factory=lambda:connection,manifest=manifest,
                    state_file=root/'state.json',backup_dir=backup,backup_verifier=lambda _:None,
                    migration_guard=guard).run()
                self.assertEqual(connection.executed_sql,approved)

    def test_symlink_fifo_encoding_and_size_are_rejected_before_backup_or_connection(self):
        for invalid in ('symlink','fifo','encoding','size','batch_size'):
            with self.subTest(invalid=invalid),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                repository,manifest_path,backup=self.fixture(root)
                manifest=MigrationManifest.load(manifest_path,repository)
                migration=manifest.migrations[0]
                if invalid=='symlink':
                    target=root/'copied.sql';target.write_bytes(migration.path.read_bytes())
                    migration.path.unlink();migration.path.symlink_to(target)
                elif invalid=='fifo':
                    migration.path.unlink();os.mkfifo(migration.path)
                elif invalid=='encoding':
                    migration.path.write_bytes(b'\xff\xfe')
                    manifest=replace(manifest,migrations=(replace(migration,sha256=hashlib.sha256(b'\xff\xfe').hexdigest()),
                                                          manifest.migrations[1]))
                backup_verifier=Mock();connection_factory=Mock()
                executor=LockedMigrationExecutor(connection_factory=connection_factory,manifest=manifest,
                    state_file=root/'state.json',backup_dir=backup,backup_verifier=backup_verifier)
                with patch.object(executor,'MAX_MIGRATION_BYTES',1 if invalid=='size' else 16*1024*1024,create=True), \
                        patch.object(executor,'MAX_BATCH_BYTES',1 if invalid=='batch_size' else 64*1024*1024,create=True):
                    with self.assertRaisesRegex(RuntimeError,'migration_(source|encoding|size|batch)'):
                        executor.run()
                backup_verifier.assert_not_called();connection_factory.assert_not_called()
                self.assertFalse((root/'state.json').exists())

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
