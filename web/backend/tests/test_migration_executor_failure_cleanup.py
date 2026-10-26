import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from deployment.lib.migration_executor import (
    LockedMigrationExecutor,
    Migration,
    MigrationManifest,
)


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())

        if normalized.startswith(
            "select pg_try_advisory_lock"
        ):
            self.row = (True,)
            return

        if (
            "select schema_version from "
            "public.application_schema_state"
            in normalized
        ):
            self.row = (83,)
            return

        if normalized == "BROKEN MIGRATION":
            self.connection.aborted = True
            raise RuntimeError(
                "primary_migration_failure"
            )

        if normalized.startswith(
            "select pg_advisory_unlock"
        ):
            self.connection.unlock_attempts += 1

            if self.connection.aborted:
                raise RuntimeError(
                    "unlock_in_aborted_transaction"
                )

            self.row = (True,)
            return

        raise AssertionError(
            f"unexpected SQL: {normalized}"
        )

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self):
        self.autocommit = False
        self.aborted = False
        self.rollback_calls = 0
        self.unlock_attempts = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rollback_calls += 1
        self.aborted = False

    def close(self):
        self.closed = True


class MigrationExecutorFailureCleanupTests(TestCase):
    def setup_executor(self, root, factory):
        path = root / '084.sql'
        path.write_text('BROKEN MIGRATION')
        manifest = MigrationManifest('a' * 40, (Migration(
            84, path, hashlib.sha256(path.read_bytes()).hexdigest(), 83, 84,
            'expand-only'),), coordinated=True)
        return LockedMigrationExecutor(connection_factory=factory, manifest=manifest,
            state_file=root / 'execution.json', backup_dir=root,
            backup_verifier=lambda _: None, migration_guard=lambda *_: None,
            failure_formatter=lambda error: type(error).__name__)

    def test_connection_failure_is_durable_and_does_not_reopen_consumed_attempt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []
            def connect():
                calls.append('connect')
                raise ConnectionError('synthetic_private_connection_details')
            executor = self.setup_executor(root, connect)
            with self.assertRaises(ConnectionError): executor.run()
            state = json.loads(executor.state_file.read_bytes())
            self.assertEqual((state['status'], state['phase']), ('failed', 'connecting'))
            self.assertEqual(state['failure_code'], 'ConnectionError')
            self.assertNotIn('rollback_failure_code', state)
            self.assertNotIn('synthetic_private', executor.state_file.read_text())
            with self.assertRaisesRegex(RuntimeError, 'attempt_consumed'): executor.run()
            self.assertEqual(calls, ['connect'])

    def test_autocommit_setup_failure_closes_connection_and_records_failure(self):
        class SetupFailure(_Connection):
            @property
            def autocommit(self): return False
            @autocommit.setter
            def autocommit(self, value):
                if value: raise RuntimeError('synthetic_setup_failure')
        with TemporaryDirectory() as directory:
            connection = SetupFailure()
            executor = self.setup_executor(Path(directory), lambda: connection)
            with self.assertRaisesRegex(RuntimeError, 'synthetic_setup_failure'): executor.run()
            self.assertTrue(connection.closed)
            self.assertEqual(connection.unlock_attempts, 0)
            state = json.loads(executor.state_file.read_bytes())
            self.assertEqual((state['status'], state['phase']), ('failed', 'connecting'))
            self.assertEqual(state['migrations'], [])

    def test_close_failure_does_not_replace_primary_migration_failure(self):
        class CloseFailure(_Connection):
            def close(self):
                super().close()
                raise OSError('synthetic_cleanup_failure')
        with TemporaryDirectory() as directory:
            connection = CloseFailure()
            executor = self.setup_executor(Path(directory), lambda: connection)
            with self.assertRaisesRegex(RuntimeError, 'primary_migration_failure'): executor.run()
            self.assertTrue(connection.closed)
            self.assertEqual(json.loads(executor.state_file.read_bytes())['status'], 'failed')

    def test_admitted_formatter_preserves_stage_without_private_sql_details(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);sql=root/'084.sql';sql.write_text('BROKEN MIGRATION')
            manifest=MigrationManifest(release_sha='a'*40,migrations=(Migration(84,sql,
                hashlib.sha256(sql.read_bytes()).hexdigest(),83,84,'expand-only'),))
            connection=_Connection()
            executor=LockedMigrationExecutor(connection_factory=lambda:connection,manifest=manifest,
                state_file=root/'execution.json',backup_dir=root,backup_verifier=lambda _:None,
                failure_formatter=lambda error:'completed_migration_error_'+type(error).__name__)
            with self.assertRaises(RuntimeError):executor.run()
            record=json.loads((root/'execution.json').read_text())
            self.assertEqual(record['failure_code'],'completed_migration_error_RuntimeError')
            self.assertEqual(record['phase'],'migration_84');self.assertEqual(record['observed_schema'],83)
            self.assertNotIn('primary_migration_failure',(root/'execution.json').read_text())
    def test_original_failure_survives_cleanup(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            migration_path = root / "084_failure.sql"
            migration_path.write_text(
                "BROKEN MIGRATION",
                encoding="utf-8",
            )

            checksum = hashlib.sha256(
                migration_path.read_bytes()
            ).hexdigest()

            manifest = MigrationManifest(
                release_sha="a" * 40,
                migrations=(
                    Migration(
                        number=84,
                        path=migration_path,
                        sha256=checksum,
                        from_schema=83,
                        to_schema=84,
                        compatibility="expand-only",
                    ),
                ),
            )

            state_file = root / "state.json"
            backup_dir = root / "backup"
            backup_dir.mkdir()

            connection = _Connection()

            executor = LockedMigrationExecutor(
                connection_factory=lambda: connection,
                manifest=manifest,
                state_file=state_file,
                backup_dir=backup_dir,
                backup_verifier=lambda _: None,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "primary_migration_failure",
            ):
                executor.run()

            self.assertGreaterEqual(
                connection.rollback_calls,
                1,
            )
            self.assertTrue(connection.closed)

            state = json.loads(
                state_file.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                state["status"],
                "failed",
            )

            self.assertEqual(
                state["failure_code"],
                "primary_migration_failure",
            )
