"""Fixed already-restored150 candidate refresh; no container/database effects."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import schema150_candidate_refresh as refresh

SHA = 'b' * 40


class CandidateRefreshSafetyTests(unittest.TestCase):
    def test_wrong_mode_mutable_or_same_origin_source_rejects_before_host(self):
        for mode, source in (('EXECUTE', SHA), ('REHEARSE', 'main'), ('REHEARSE', refresh.ORIGIN_SHA)):
            with self.subTest(mode=mode, source=source), patch.object(refresh.manage, 'require_staging_host') as host:
                with self.assertRaises(RuntimeError): refresh.main(mode, Path('/target'), source, Path('/origin'))
                host.assert_not_called()

    def test_production_host_rejects_before_artifact_or_database_access(self):
        with patch.object(refresh.manage.socket, 'gethostname', return_value='madar-gpu'), \
                patch.object(refresh.acceptance.previous, 'artifacts') as artifacts:
            with self.assertRaises(RuntimeError): refresh.main('REHEARSE', Path('/target'), SHA, Path('/origin'))
            artifacts.assert_not_called()

    def test_inspect_authenticates_distinct_origin_without_effects(self):
        with patch.object(refresh.manage, 'require_staging_host'), \
                patch.object(refresh.acceptance.previous, 'artifacts', return_value=({}, {}, {}, {})) as artifacts, \
                patch.object(refresh, 'attest_origin', return_value=({}, {}, b'{}', 'report-root')), \
                patch.object(refresh, 'stop_owned') as stop, patch.object(refresh.configuration, 'generate') as generate, \
                patch.object(refresh.application_restore, 'import_target_images') as load:
            report = refresh.main('INSPECT', Path('/target'), SHA, Path('/origin'))
            self.assertFalse(report['mutations_executed'])
            self.assertFalse(report['database_restore_or_migration'])
            self.assertEqual(artifacts.call_args_list[0].args, (Path('/target'), SHA))
            self.assertEqual(artifacts.call_args_list[1].args, (Path('/origin'), refresh.ORIGIN_SHA))
            stop.assert_not_called(); generate.assert_not_called(); load.assert_not_called()

    def test_consumed_private_scope_or_runtime_is_not_overwritten(self):
        for use_runtime in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                home = Path(directory); original = home / refresh.PROJECT; original.mkdir(mode=0o700)
                consumed = home / (refresh.PROJECT + '-candidate-' + SHA[:12]) if use_runtime else original / ('candidate-refresh-' + SHA)
                consumed.mkdir()
                with self.subTest(runtime=use_runtime), patch.object(Path, 'home', return_value=home), \
                        patch.object(refresh.manage, 'require_staging_host'), \
                        patch.object(refresh.acceptance.previous, 'artifacts', return_value=({}, {}, {}, {})), \
                        patch.object(refresh, 'attest_origin', return_value=({}, {}, b'{}', 'report-root')), \
                        patch.object(refresh, 'stop_owned') as stop:
                    with self.assertRaisesRegex(RuntimeError, 'already_consumed'):
                        refresh.main('REHEARSE', home / 'target', SHA, home / 'origin')
                    stop.assert_not_called()

    def test_origin_is_fixed_to_accepted8e17_not_caller_selected_source(self):
        with patch.object(refresh.manage, 'state', return_value={'source_sha': 'c' * 40}), \
                patch.object(refresh.manage, 'sql') as sql, patch.object(refresh, 'containers') as containers:
            with self.assertRaisesRegex(RuntimeError, 'wrong_origin_source'): refresh.attest_origin({})
            sql.assert_not_called(); containers.assert_not_called()

    def test_processing_or_foreign_session_blocks_without_reset_or_termination(self):
        rows = {name: {'State': {'Running': False}} for name in refresh.SERVICES}
        for result, marker in (('1', 'other_database_session'), ('0', 'processing_work')):
            def sql(statement):
                if statement == refresh.acceptance.PROTOCOL_SQL: return '150:2:2:2'
                if 'pg_stat_activity' in statement: return result
                if 'pg_prepared_xacts' in statement: return '0'
                if 'notification_deliveries' in statement: return '1'
                raise AssertionError('Unexpected SQL')
            with self.subTest(marker=marker), patch.object(refresh, 'containers', return_value=rows), \
                    patch.object(refresh.manage, 'sql', side_effect=sql), patch.object(refresh.manage, 'docker') as docker:
                with self.assertRaisesRegex(RuntimeError, marker): refresh.require_quiescence()
                docker.assert_not_called()

    def test_pre_activation_preservation_mismatch_rejects_before_provider_start(self):
        for key in ('system_identifier', 'rows_sequences', 'roles_sha256', 'privileges_sha256', 'objects'):
            checkpoint = {'system_identifier': 'same', 'rows_sequences': {}, 'roles_sha256': 'same',
                          'privileges_sha256': 'same', 'objects': {}}
            changed = dict(checkpoint); changed[key] = 'changed'
            with self.subTest(key=key), patch.object(refresh.manage, 'sql', return_value='150:2:2:2'), \
                    patch.object(refresh, 'preservation', return_value=changed), patch.object(refresh.manage, 'compose') as compose:
                with self.assertRaisesRegex(RuntimeError, 'preservation_failed'): refresh.require_preservation(checkpoint)
                compose.assert_not_called()

    def test_failure_cleanup_can_stop_only_attested_surviving_recovery_actors(self):
        rows = {'backend': {'Id': 'owned-backend', 'State': {'Running': True}},
                'postgres': {'Id': 'owned-postgres', 'State': {'Running': False}}}
        with patch.object(refresh, 'containers', return_value=rows) as inventory, patch.object(refresh.manage, 'docker') as docker:
            refresh.stop_owned(('backend', 'postgres', 'deletion-worker'))
        inventory.assert_called_once_with(complete=False)
        docker.assert_called_once_with('stop', '--time', '20', 'owned-backend')

    def test_prepared_actor_substitution_rejects_before_first_stop(self):
        expected = {'backend': {'Id': 'original', 'Image': 'original-image', 'State': {'Running': True}}}
        for replacement in ({}, {'backend': {**expected['backend'], 'Id': 'replacement'}},
                            {'backend': {**expected['backend'], 'Image': 'replacement-image'}}):
            with self.subTest(replacement=replacement), patch.object(refresh, 'containers', return_value=replacement), \
                    patch.object(refresh.manage, 'docker') as docker:
                with self.assertRaisesRegex(RuntimeError, 'prepared_container_identity_changed'):
                    refresh.stop_owned(('backend',), expected=expected)
                docker.assert_not_called()

    def test_headroom_failure_precedes_scope_creation_and_service_effects(self):
        for disk, memory, marker in ((7 * 1024**3, 1400 * 1024, 'disk_headroom'),
                                     (9 * 1024**3, 1200 * 1024, 'memory_headroom')):
            with tempfile.TemporaryDirectory() as directory:
                home = Path(directory); original = home / refresh.PROJECT; original.mkdir(mode=0o700)
                actual_read_text = Path.read_text
                def read_text(path, *args, **kwargs):
                    if str(path) == '/proc/meminfo': return f'MemAvailable: {memory} kB\n'
                    return actual_read_text(path, *args, **kwargs)
                with self.subTest(marker=marker), patch.object(Path, 'home', return_value=home), \
                        patch.object(refresh.manage, 'require_staging_host'), \
                        patch.object(refresh.acceptance.previous, 'artifacts', return_value=({}, {}, {}, {})), \
                        patch.object(refresh, 'attest_origin', return_value=({}, {}, b'{}', 'report-root')), \
                        patch.object(refresh.shutil, 'disk_usage', return_value=SimpleNamespace(free=disk)), \
                        patch.object(Path, 'read_text', read_text), patch.object(refresh, 'stop_owned') as stop:
                    with self.assertRaisesRegex(RuntimeError, marker):
                        refresh.main('REHEARSE', home / 'target', SHA, home / 'origin')
                    stop.assert_not_called()
                    self.assertEqual(list(original.iterdir()), [])

    def test_different_candidate_shas_cannot_overlap_fixed_project(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); project = home / refresh.PROJECT; project.mkdir(mode=0o700)
            with refresh.configuration.private_directory_lock(project), patch.object(Path, 'home', return_value=home), \
                    patch.object(refresh.manage, 'require_staging_host'), patch.object(refresh, '_run') as run:
                for candidate in ('b' * 40, 'c' * 40):
                    with self.subTest(candidate=candidate), self.assertRaisesRegex(RuntimeError, 'project_busy'):
                        refresh.main('REHEARSE', home / 'target', candidate, home / 'origin')
                run.assert_not_called()

    def test_inspect_does_not_acquire_project_lock(self):
        with patch.object(refresh.manage, 'require_staging_host'), patch.object(refresh, '_run', return_value={}) as run, \
                patch.object(refresh.configuration, 'private_directory_lock') as lock:
            refresh.main('INSPECT', Path('/target'), SHA, Path('/origin'))
            run.assert_called_once(); lock.assert_not_called()


if __name__ == '__main__': unittest.main()
