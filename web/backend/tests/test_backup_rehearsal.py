import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


def load_harness():
    candidates = [Path(__file__).resolve().parents[2] / 'scripts/rehearse_backup.py', Path('/scripts/rehearse_backup.py')]
    path = next(path for path in candidates if path.is_file())
    spec = importlib.util.spec_from_file_location('backup_rehearsal', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = load_harness()


class BackupRehearsalTests(unittest.TestCase):
    def test_missing_file_fails_before_docker_without_creating_directory(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'missing.sql'
            with mock.patch.object(harness.subprocess, 'run') as run:
                with self.assertRaisesRegex(harness.RehearsalError, 'absolute_regular_file'):
                    harness.readonly_file_mount(str(source), '/migration.sql')
                run.assert_not_called()
            self.assertFalse(source.exists())

    def test_directory_and_symlink_are_not_accepted_as_sql(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'migration.sql'
            directory.mkdir()
            link = Path(root) / 'link.sql'
            link.symlink_to(directory)
            for path in [directory, link]:
                with self.subTest(path=path), self.assertRaises(harness.RehearsalError):
                    harness.readonly_file_mount(str(path), '/migration.sql')

    def test_file_mount_is_explicit_readonly_and_predictable(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'migration.sql'
            source.write_text('SELECT 1;')
            self.assertEqual(harness.readonly_file_mount(str(source), '/migration.sql'), f'type=bind,src={source.resolve()},dst=/migration.sql,readonly')

    def test_relative_source_and_mount_delimiter_fail_closed(self):
        with self.assertRaises(harness.RehearsalError):
            harness.regular_source('migration.sql')
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'bad,name.sql'
            source.write_text('SELECT 1;')
            with self.assertRaises(harness.RehearsalError):
                harness.regular_source(str(source))

    def test_unpinned_image_fails_before_commands(self):
        with mock.patch.object(harness.subprocess, 'run') as run:
            with self.assertRaisesRegex(harness.RehearsalError, 'digest_pinned'):
                harness.rehearse(Path('/missing'), 'postgres:latest')
            run.assert_not_called()

    def test_error_does_not_emit_database_rows(self):
        result = mock.Mock(returncode=1, stdout='private row', stderr='COPY private customer row')
        with mock.patch.object(harness.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(harness.RehearsalError, '^restore:exit_1$'):
                harness.run(['pg_restore'], phase='restore')

    def test_file_inventory_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'escape').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(harness.RehearsalError, 'symlink'):
                harness.file_inventory(Path(root))

    def test_migration_requires_explicit_target_before_any_restore(self):
        with mock.patch.object(harness.subprocess, 'run') as run:
            with self.assertRaisesRegex(harness.RehearsalError, 'explicit_target_schema'):
                harness.rehearse(Path('/missing'), 'postgres@sha256:' + 'a'*64, Path('/migration.sql'))
            run.assert_not_called()

    def test_target_table_contract_rejects_duplicates_or_sql(self):
        for names in [('ledger', 'ledger'), ('ledger;drop table users',)]:
            with mock.patch.object(harness.subprocess, 'run') as run:
                with self.assertRaisesRegex(harness.RehearsalError, 'invalid_expected_new_tables'):
                    harness.rehearse(Path('/missing'), 'postgres@sha256:' + 'a'*64, Path('/migration.sql'), target_schema=94, new_tables=names)
                run.assert_not_called()
