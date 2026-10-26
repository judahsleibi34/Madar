"""Non-mutating safety and failure semantics of isolated native150 acceptance."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import schema150_acceptance as acceptance


class Schema150AcceptanceSafetyTests(unittest.TestCase):
    def test_production_host_rejects_before_artifact_or_resource_access(self):
        for mode in ('INSPECT', 'REHEARSE'):
            with self.subTest(mode=mode), patch.object(acceptance.manage.socket, 'gethostname', return_value='madar-gpu'), \
                    patch.object(acceptance, 'captured_source') as capture, patch.object(acceptance.manage, 'docker') as docker:
                with self.assertRaises(RuntimeError): acceptance.main(mode, Path.home() / 'private', 'a' * 40)
                capture.assert_not_called(); docker.assert_not_called()

    def test_wrong_mode_or_source_rejects_before_captured_source(self):
        for mode, source in (('EXECUTE', 'a' * 40), ('REHEARSE', 'main'), ('INSPECT', None)):
            with self.subTest(mode=mode, source=source), patch.object(acceptance.manage, 'require_staging_host'), \
                    patch.object(acceptance, 'captured_source') as capture:
                with self.assertRaises(RuntimeError): acceptance.main(mode, Path.home() / 'private', source)
                capture.assert_not_called()

    def test_inspect_captures_authenticated_metadata_but_never_prepares_or_mutates(self):
        snapshots = {n: str(n).encode() for n in range(147, 151)}
        with patch.object(acceptance.manage, 'require_staging_host'), \
                patch.object(acceptance, 'captured_source', return_value=({}, snapshots)), \
                patch.object(acceptance.previous, 'artifacts', return_value=({}, {}, {}, {})), \
                patch.object(acceptance, 'prepare') as prepare, patch.object(acceptance.manage, 'docker') as docker:
            report = acceptance.main('INSPECT', Path.home() / 'private', 'a' * 40)
            self.assertEqual(report['target_schema'], 150)
            self.assertFalse(report['mutations_executed'])
            self.assertEqual(report['migration_sha256']['150'], hashlib.sha256(b'150').hexdigest())
            prepare.assert_not_called(); docker.assert_not_called()

    def test_context_restores_all_globals_after_exception(self):
        previous = acceptance.previous
        names = ('PROJECT', 'OWNER', 'MARKER', 'PORTS', 'replace_ports')
        old = tuple(getattr(previous, name) for name in names)
        globals_before = (acceptance.manage.PROJECT, acceptance.manage.RUNTIME, acceptance.manage.OWNER,
                          acceptance.smoke.PROVIDER, acceptance.smoke.APPLICATION)
        with self.assertRaisesRegex(RuntimeError, 'synthetic interruption'):
            with acceptance.target(Path.home() / acceptance.PROJECT):
                self.assertEqual(acceptance.manage.PROJECT, acceptance.PROJECT)
                self.assertEqual(acceptance.smoke.PROVIDER, 'http://127.0.0.1:21081')
                self.assertEqual(acceptance.smoke.APPLICATION, 'http://127.0.0.1:21080/api')
                raise RuntimeError('synthetic interruption')
        self.assertEqual(old, tuple(getattr(previous, name) for name in names))
        self.assertEqual(globals_before, (acceptance.manage.PROJECT, acceptance.manage.RUNTIME, acceptance.manage.OWNER,
                          acceptance.smoke.PROVIDER, acceptance.smoke.APPLICATION))

    def test_port_replacement_never_reuses_existing_staging_bindings(self):
        text = ' '.join('127.0.0.1:' + port for port in ('18080', '19080', '20080', '18443', '19443', '20443', '18081', '19081', '20081'))
        actual = acceptance.replace_ports(text)
        self.assertEqual(actual, ' '.join(['127.0.0.1:21080'] * 3 + ['127.0.0.1:21443'] * 3 + ['127.0.0.1:21081'] * 3))

    def test_existing_attempt_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory, acceptance.target(Path(directory)), \
                patch.object(acceptance.manage, 'docker') as docker:
            with self.assertRaisesRegex(RuntimeError, 'Preserve'):
                acceptance.prepare(Path(directory), Path(directory), 'a' * 40, {}, {}, {n: b'sql' for n in range(147, 151)})
            docker.assert_not_called()

    def test_incomplete_or_mutable_migration_snapshots_reject_before_prepare(self):
        for snapshots in ({149: b'sql'}, {n: 'sql' for n in range(147, 151)}):
            with self.subTest(snapshots=snapshots), patch.object(acceptance.previous, 'prepare') as prepare:
                with self.assertRaisesRegex(RuntimeError, 'Captured'):
                    acceptance.prepare(Path('/unused'), Path('/unused'), 'a' * 40, {}, {}, snapshots)
                prepare.assert_not_called()

    def test_migration_executes_captured_sql_and_checks_preservation(self):
        original = {'tables': {'auth.users': {'rows': 1, 'digest': 'same'},
                    'public.data_deletion_requests': {'rows': 0, 'digest': 'empty'},
                    'public.data_deletion_steps': {'rows': 0, 'digest': 'empty'}}, 'sequences': {'public.users': 3}}
        calls = []
        def sql(statement):
            calls.append(statement)
            if statement == acceptance.previous.OUTBOX_PREIMAGE: return 'outbox-original'
            if statement == acceptance.restore.FINGERPRINT_SQL: return json.dumps(original)
            if statement == acceptance.PROTOCOL_SQL: return '150:2:2:2'
            if statement.startswith('select schema_version '): return str(148 + sum('set lock_timeout=' in call for call in calls))
            if statement.startswith('select count(*)'): return '0'
            return ''
        with patch.object(acceptance.manage, 'sql', side_effect=sql):
            report = acceptance.migrate_and_preserve(original, {149: b'captured149', 150: b'captured150'})
        self.assertTrue(report['business_auth_storage_rows_preserved'])
        self.assertEqual([call.split(';')[-1] for call in calls if call.startswith('set lock_timeout=')], ['captured149', 'captured150'])

    def test_native_deletion_rejects_wrong_protocol_before_fixture_creation(self):
        with patch.object(acceptance.manage, 'require_database_marker'), \
                patch.object(acceptance.manage, 'sql', return_value='149:2:2:0'), \
                patch.object(acceptance.smoke, 'http') as http:
            with self.assertRaisesRegex(RuntimeError, 'compatible'): acceptance.deletion_workflow()
            http.assert_not_called()

    def test_worker_health_must_show_actual_consumption(self):
        for value in ({'status': 'ok', 'consuming': False}, {'status': 'starting', 'consuming': True}):
            with self.subTest(value=value), patch.object(acceptance.manage, 'compose', return_value=b'owned-worker'), \
                    patch.object(acceptance.manage, 'docker', return_value=json.dumps(value).encode()):
                with self.assertRaisesRegex(RuntimeError, 'not consuming'): acceptance.worker_health()


if __name__ == '__main__': unittest.main()
