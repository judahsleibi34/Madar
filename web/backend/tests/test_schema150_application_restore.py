"""Strict staging-only restoration boundaries; no Docker/database effects."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import schema150_application_restore as rehearsal


class Schema150ApplicationRestoreSafetyTests(unittest.TestCase):
    def test_wrong_mode_or_mutable_source_rejects_before_access(self):
        for mode, source in (('EXECUTE', 'a' * 40), ('REHEARSE', 'main')):
            with self.subTest(mode=mode), patch.object(rehearsal.manage, 'require_staging_host') as host:
                with self.assertRaises(RuntimeError): rehearsal.main(mode, Path.home() / 'private', source)
                host.assert_not_called()

    def test_origin_identity_requires_both_immutable_source_and_artifact_directory(self):
        for directory, source in ((Path('/private-origin'), None), (None, 'a' * 40), (Path('/private-origin'), 'main')):
            with self.subTest(directory=directory, source=source), patch.object(rehearsal.manage, 'require_staging_host') as host:
                with self.assertRaisesRegex(RuntimeError, 'paired_exact_origin'):
                    rehearsal.main('INSPECT', Path('/target-artifacts'), 'b' * 40, directory, source)
                host.assert_not_called()

    def test_production_host_rejects_before_artifact_or_source_inspection(self):
        with patch.object(rehearsal.manage.socket, 'gethostname', return_value='madar-gpu'), \
                patch.object(rehearsal.acceptance.previous, 'artifacts') as artifacts:
            with self.assertRaises(RuntimeError): rehearsal.main('REHEARSE', Path.home() / 'private', 'a' * 40)
            artifacts.assert_not_called()

    def test_inspect_does_not_dump_fence_prepare_restore_or_resume(self):
        with patch.object(rehearsal.manage, 'require_staging_host'), \
                patch.object(rehearsal.acceptance.previous, 'artifacts', return_value=({}, {}, {}, {})), \
                patch.object(rehearsal, 'require_source'), patch.object(rehearsal, 'fence') as fence, \
                patch.object(rehearsal, 'prepare_target') as prepare, patch.object(rehearsal, 'restore_target') as restore, \
                patch.object(rehearsal, 'resume_source') as resume, patch.object(rehearsal.manage, 'docker') as docker:
            value = rehearsal.main('INSPECT', Path.home() / 'private', 'a' * 40)
            self.assertFalse(value['mutations_executed'])
            self.assertEqual(value['target_project'], 'madar-schema150-recovery-phase6-20261018')
            for operation in (fence, prepare, restore, resume, docker): operation.assert_not_called()

    def test_target_and_source_contexts_restore_globals_after_interruption(self):
        saved = (rehearsal.manage.PROJECT, rehearsal.manage.RUNTIME, rehearsal.manage.OWNER,
                 rehearsal.acceptance.PROJECT, rehearsal.providers.PROJECT, rehearsal.providers.OWNER,
                 rehearsal.smoke.PROVIDER, rehearsal.smoke.APPLICATION,
                 rehearsal.manage.compose, rehearsal.manage.database_container)
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            with rehearsal.source():
                self.assertEqual(rehearsal.manage.PROJECT, rehearsal.SOURCE)
                with rehearsal.target(Path.home() / rehearsal.PROJECT):
                    self.assertEqual(rehearsal.manage.PROJECT, rehearsal.PROJECT)
                    self.assertEqual(rehearsal.smoke.PROVIDER, 'http://127.0.0.1:22081')
                    self.assertEqual(rehearsal.smoke.APPLICATION, 'http://127.0.0.1:22080/api')
                    raise RuntimeError('interrupted')
        self.assertEqual(saved, (rehearsal.manage.PROJECT, rehearsal.manage.RUNTIME, rehearsal.manage.OWNER,
                 rehearsal.acceptance.PROJECT, rehearsal.providers.PROJECT, rehearsal.providers.OWNER,
                 rehearsal.smoke.PROVIDER, rehearsal.smoke.APPLICATION,
                 rehearsal.manage.compose, rehearsal.manage.database_container))

    def test_existing_target_never_overwrites_or_touches_docker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(rehearsal.manage, 'docker') as docker:
            with self.assertRaisesRegex(RuntimeError, 'already_consumed'):
                rehearsal.prepare_target(Path(directory), Path('/unused'), 'a' * 40, {})
            docker.assert_not_called()

    def test_target_configuration_uses_new_source_images_and_build_not_origin_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / rehearsal.SOURCE; source.mkdir()
            destination = root / rehearsal.PROJECT
            old = {'backend': 'sha256:' + '1' * 64, 'frontend': 'sha256:' + '2' * 64}
            new = {'backend': 'sha256:' + '3' * 64, 'frontend': 'sha256:' + '4' * 64}
            for name in ('compose.env', 'application.env', 'compose.yaml', 'acceptance-compose.json', 'fresh-edge.conf'):
                (source / name).write_text('HARDENING_ROOT=' + str(source) + '\nSOURCE_SHA=' + 'a' * 40 +
                    '\nMADAR_RELEASE_SHA=' + 'a' * 40 + '\nMADAR_BUILD_TIMESTAMP=origin-build\n' +
                    old['backend'] + '\n' + old['frontend'] + '\nhttp://127.0.0.1:21080\n' + rehearsal.SOURCE_OWNER + '\n')
            for name in ('tls.crt', 'tls.key'): (source / name).write_bytes(b'synthetic-tls')
            credentials = {'DATABASE_PASSWORD': 'a' * 64, 'JWT_SECRET': 'b' * 64}
            with patch.object(Path, 'home', return_value=root), patch.object(rehearsal.manage, 'state'), \
                    patch.object(rehearsal.manage, 'attest_resources'), patch.object(rehearsal.configuration, 'generate') as generate, \
                    patch.object(rehearsal.acceptance.previous, 'regular', side_effect=AssertionError('Origin configuration must never be read')):
                rehearsal.prepare_target(destination, source, 'b' * 40, new, {'build_timestamp': 'target-build'}, old, credentials)
            generate.assert_called_once_with(destination, 'b' * 40, new, {'build_timestamp': 'target-build'}, credentials,
                                             rehearsal.PROJECT, rehearsal.OWNER)

    def test_capture_preimage_rejects_unknown_database_writer_without_termination(self):
        with patch.object(rehearsal, 'rows', return_value={}), \
                patch.object(rehearsal.providers, 'sessions', return_value=[{'role': 'postgres', 'client': '127.0.0.1'}]), \
                patch.object(rehearsal.manage, 'docker') as docker:
            with self.assertRaisesRegex(RuntimeError, 'unknown_database_client'):
                rehearsal.capture_preimage('a' * 40, {})
            docker.assert_not_called()

    def test_changed_archives_reject_before_target_database_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('roles.sql', 'database.dump', 'objects.tar'): (root / name).write_bytes(b'changed')
            checkpoint = {'archive_sha256': {name: '0' * 64 for name in ('roles.sql', 'database.dump', 'objects.tar')}}
            with patch.object(rehearsal.manage, 'compose') as compose:
                with self.assertRaisesRegex(RuntimeError, 'archive_digest_changed'):
                    rehearsal.restore_target(Path('/unused'), root, checkpoint, {}, 'a' * 40)
                compose.assert_not_called()

    def test_preimage_and_original_roles_are_durable_before_any_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); runtime = home / rehearsal.SOURCE; runtime.mkdir(mode=0o700)
            credentials = {'DATABASE_PASSWORD': 'a' * 64, 'JWT_SECRET': 'b' * 64}
            preimage = {'all_roles_sha256': 'role-root', 'source_sha': 'a' * 40, 'images': {},
                        'runtime_credentials_sha256': rehearsal.hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).hexdigest()}
            def interrupted(value, journal):
                self.assertEqual(value, preimage)
                self.assertEqual(journal.read()[0]['payload']['preimage'], preimage)
                roles = runtime / (rehearsal.SCOPE + '-files') / 'roles.sql'
                self.assertEqual(roles.read_bytes(), b'original roles before NOLOGIN')
                self.assertEqual(roles.stat().st_mode & 0o777, 0o600)
                raise RuntimeError('fence-interrupted')
            with patch.object(Path, 'home', return_value=home), patch.object(rehearsal.manage, 'require_staging_host'), \
                    patch.object(rehearsal.acceptance.previous, 'artifacts', return_value=({}, {}, {}, {})), \
                    patch.object(rehearsal, 'require_source'), patch.object(rehearsal.acceptance, 'runtime_identity'), \
                    patch.object(rehearsal, 'positive_probes'), patch.object(rehearsal, 'capture_preimage', return_value=preimage), \
                    patch.object(rehearsal, 'rows', return_value={'postgres': {'Id': 'synthetic-source'}}), \
                    patch.object(rehearsal.configuration, 'live_credentials', return_value=credentials), \
                    patch.object(rehearsal.shutil, 'disk_usage', return_value=SimpleNamespace(free=32 * 1024**3)), \
                    patch.object(rehearsal.manage, 'docker', return_value=b'original roles before NOLOGIN'), \
                    patch.object(rehearsal.manage, 'database_container', return_value='synthetic-source-container'), \
                    patch.object(rehearsal.manage, 'sql', return_value='role-root'), patch.object(rehearsal, 'fence', side_effect=interrupted):
                with self.assertRaisesRegex(RuntimeError, 'fence-interrupted'):
                    rehearsal.main('REHEARSE', home / 'private', 'a' * 40)
            self.assertTrue((runtime / (rehearsal.SCOPE + '-journal')).is_dir())

    def test_resume_requires_original_journal_and_cannot_guess_role_defaults(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)), \
                patch.object(rehearsal, 'require_source'), patch.object(rehearsal.manage, 'sql') as sql:
            with self.assertRaises(RuntimeError): rehearsal.resume_source('a' * 40, {})
            sql.assert_not_called()

    def test_restore_ports_are_distinct_and_never_reuse_source_bindings(self):
        self.assertEqual(rehearsal.replace_ports('http://127.0.0.1:21080 https://127.0.0.1:21443 http://127.0.0.1:21081'),
                         'http://127.0.0.1:22080 https://127.0.0.1:22443 http://127.0.0.1:22081')

    def test_error_or_redirect_responder_is_not_mistaken_for_fenced_ingress(self):
        for code in (302, 403, 500):
            with self.subTest(code=code), patch.object(rehearsal.smoke.OPENER, 'open',
                    side_effect=HTTPError('http://127.0.0.1', code, 'synthetic', {}, None)):
                with self.assertRaisesRegex(RuntimeError, 'still_reachable'): rehearsal.require_ingress_fenced()
        with patch.object(rehearsal.smoke.OPENER, 'open', side_effect=URLError('connection refused')) as open_request:
            rehearsal.require_ingress_fenced()
            self.assertEqual(open_request.call_count, 2)

    def test_unknown_bind_mount_of_object_bytes_is_also_a_writer(self):
        root = '/var/lib/docker/volumes/owned_objects/_data'
        for mount in ({'Name': 'owned_objects', 'RW': True}, {'Source': root, 'RW': True},
                      {'Source': root + '/private-subdirectory', 'RW': True},
                      {'Source': '/var/lib/docker/volumes', 'RW': True}, {'Source': '/', 'RW': True}):
            with self.subTest(mount=mount):
                self.assertTrue(rehearsal.has_object_writer([{'Mounts': [mount]}], 'owned_objects', root))
        self.assertFalse(rehearsal.has_object_writer([{'Mounts': [{'Source': root, 'RW': False},
                    {'Source': root + '-unrelated', 'RW': True}]}], 'owned_objects', root))

    def test_interrupted_resume_reconciles_exact_preimages_without_requiring_old_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); source = home / rehearsal.SOURCE; source.mkdir(mode=0o700)
            files = source / (rehearsal.SCOPE + '-files'); files.mkdir(mode=0o700)
            (files / 'checkpoint.json').write_text('{}')
            roles = {name: {'login': True, 'other_sha256': name + '-stable'} for name in rehearsal.ROLE_NAMES}
            preimage = {'source_sha': 'a' * 40, 'images': {}, 'roles': roles,
                        'all_roles_sha256': 'role-root', 'containers': {'postgres': {'id': 'exact-source', 'running': True}}}
            records = [{'event': 'prepared', 'payload': {'preimage': preimage}},
                       {'event': 'source_resume_intent', 'payload': {'preservation_checkpoint_verified': True}}]
            journal = SimpleNamespace(read=lambda: records, append=lambda event, payload: records.append({'event': event, 'payload': payload}))
            with patch.object(Path, 'home', return_value=home), patch.object(rehearsal, 'require_source'), \
                    patch.object(rehearsal.providers, 'Journal', return_value=journal), \
                    patch.object(rehearsal, 'require_preimage_identity'), patch.object(rehearsal.providers, 'roles', return_value=roles), \
                    patch.object(rehearsal.providers, 'sessions', return_value=[]), \
                    patch.object(rehearsal, 'rows', return_value={'postgres': {'State': {'Running': True}, 'NetworkSettings': {'Networks': {}}}}), \
                    patch.object(rehearsal.manage, 'sql', return_value='role-root'), patch.object(rehearsal.manage, 'docker'), \
                    patch.object(rehearsal, 'require_quiescence') as quiescence, patch.object(rehearsal, 'positive_probes'), \
                    patch.object(rehearsal.acceptance, 'worker_health'):
                value = rehearsal.resume_source('a' * 40, {})
            self.assertTrue(value['interrupted_resume_reconciled'])
            self.assertFalse(value['preservation_checkpoint_verified'])
            self.assertEqual(records[-1]['event'], 'source_resumed')
            quiescence.assert_not_called()

    def test_completed_source_resume_cannot_be_replayed(self):
        records = [{'event': 'prepared', 'payload': {'preimage': {}}}, {'event': 'source_resumed', 'payload': {}}]
        with patch.object(rehearsal, 'require_source'), \
                patch.object(rehearsal.providers, 'Journal', return_value=SimpleNamespace(read=lambda: records)), \
                patch.object(rehearsal.manage, 'sql') as sql, patch.object(rehearsal.manage, 'docker') as docker:
            with self.assertRaisesRegex(RuntimeError, 'already_consumed'): rehearsal.resume_source('a' * 40, {})
            sql.assert_not_called(); docker.assert_not_called()

    def test_final_source_observation_requires_fence_and_preserved_rows_objects(self):
        checkpoint = {'rows_sequences': {'tables': {'auth.users': {'digest': 'original'}}},
                      'objects': {'private/object': 'original-bytes'}}
        for changed_rows, changed_objects in ((True, False), (False, True), (False, False)):
            actual = {'tables': {'auth.users': {'digest': 'changed'}}} if changed_rows else checkpoint['rows_sequences']
            objects = {'private/object': 'changed-bytes'} if changed_objects else checkpoint['objects']
            with self.subTest(changed_rows=changed_rows, changed_objects=changed_objects), \
                    patch.object(rehearsal, 'require_quiescence') as quiescence, \
                    patch.object(rehearsal.manage, 'sql', return_value=json.dumps(actual)), \
                    patch.object(rehearsal.restore, 'inventory', return_value=objects):
                if changed_rows or changed_objects:
                    with self.assertRaisesRegex(RuntimeError, 'source_changed_during_target'):
                        rehearsal.verify_retained_source({'original': 'binding'}, checkpoint)
                else:
                    proof = rehearsal.verify_retained_source({'original': 'binding'}, checkpoint)
                    self.assertTrue(proof['quiescence_reverified_after_target_acceptance'])
                quiescence.assert_called_once_with({'original': 'binding'})

    def test_final_source_observation_rejects_resurrected_writer_before_hashing(self):
        with patch.object(rehearsal, 'require_quiescence', side_effect=RuntimeError('source_writer_resurrected')), \
                patch.object(rehearsal.manage, 'sql') as sql, patch.object(rehearsal.restore, 'inventory') as objects:
            with self.assertRaisesRegex(RuntimeError, 'source_writer_resurrected'):
                rehearsal.verify_retained_source({}, {})
            sql.assert_not_called(); objects.assert_not_called()

    def test_restore_and_resume_cli_serialize_original_source_before_any_run(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); source = home / rehearsal.SOURCE; source.mkdir(mode=0o700)
            with rehearsal.configuration.private_directory_lock(source), patch.object(Path, 'home', return_value=home), \
                    patch.object(rehearsal.manage, 'require_staging_host'), patch.object(rehearsal, '_run') as run:
                for mode in ('REHEARSE', 'RESUME-SOURCE'):
                    with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, 'project_busy'):
                        rehearsal.main(mode, home / 'target', 'b' * 40)
                run.assert_not_called()

    def test_resume_arbitrates_same_target_lock_as_candidate_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); source = home / rehearsal.SOURCE; source.mkdir(mode=0o700)
            target = home / rehearsal.PROJECT; target.mkdir(mode=0o700)
            with rehearsal.configuration.private_directory_lock(target), patch.object(Path, 'home', return_value=home), \
                    patch.object(rehearsal.manage, 'require_staging_host'), \
                    patch.object(rehearsal, '_run', side_effect=lambda *_args: rehearsal.resume_source('a' * 40, {})), \
                    patch.object(rehearsal, '_resume_source') as resume:
                with self.assertRaisesRegex(RuntimeError, 'project_busy'):
                    rehearsal.main('RESUME-SOURCE', home / 'artifacts', 'b' * 40)
                resume.assert_not_called()
            # Failed nonblocking target acquisition releases SOURCE too.
            with rehearsal.configuration.private_directory_lock(source): pass

    def test_resume_acquires_source_then_target_and_rejects_ambiguous_target_root(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); source = home / rehearsal.SOURCE; source.mkdir(mode=0o700)
            target = home / rehearsal.PROJECT; target.mkdir(mode=0o700)
            def observe(*_args):
                for path in (source, target):
                    with self.assertRaisesRegex(RuntimeError, 'project_busy'):
                        with rehearsal.configuration.private_directory_lock(path): self.fail('Lock not held')
                return {'locked': True}
            with patch.object(Path, 'home', return_value=home), patch.object(rehearsal.manage, 'require_staging_host'), \
                    patch.object(rehearsal, '_run', side_effect=lambda *_args: rehearsal.resume_source('a' * 40, {})), \
                    patch.object(rehearsal, '_resume_source', side_effect=observe):
                self.assertTrue(rehearsal.main('RESUME-SOURCE', home / 'artifacts', 'b' * 40)['locked'])
            target.rmdir(); target.symlink_to(home / 'missing', target_is_directory=True)
            with patch.object(Path, 'home', return_value=home), patch.object(rehearsal, '_resume_source') as resume:
                with self.assertRaises(OSError): rehearsal.resume_source('a' * 40, {})
                resume.assert_not_called()


if __name__ == '__main__': unittest.main()
