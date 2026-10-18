"""Schema150 source preparation cannot activate a privileged operation."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_release as release
from deployment.lib import completed_normal_admission as admission
from deployment.lib.completed_normal_profile import DELETION, OUTBOX, FENCED, profile
from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
from deployment.lib.migration_executor import MigrationManifest
from test_schema149_admission import successor_contract


def deletion_contract():
    value = successor_contract()
    value.update(version=DELETION.version, operation=DELETION.operation,
                 migration_manifest_sha256=release.MANIFEST_SHA256)
    value['candidate']['compatible_max'] = 150
    return value


class DeletionAdmissionPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        web = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
        shutil.copytree(web/'deployment/releases', self.root/'web/deployment/releases')
        for name in release.SQL_NAMES.values():
            for tree in ('database', 'supabase'):
                source = web/tree/'migrations'/name
                if not source.exists():
                    source = Path('/'+tree+'/migrations')/name
                target = self.root/'web'/tree/'migrations'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())

    def observation(self, schema):
        return {'system_identifier': deletion_contract()['database']['system_identifier'], 'schema': schema,
                'delivery_protocol': 1 if schema == 146 else 2,
                'outbox_protocol': 2 if schema >= 149 else 1,
                'deletion_protocol': 2 if schema == 150 else 0,
                **{name: 0 for name in release.COUNTERS}}

    def test_preparation_profile_exact_historical_operations_unchanged(self):
        self.assertEqual((DELETION.version, DELETION.source, DELETION.target, DELETION.migrations),
                         (7, 146, 150, (147, 148, 149, 150)))
        self.assertEqual((OUTBOX.version, OUTBOX.source, OUTBOX.target, OUTBOX.migrations),
                         (6, 146, 149, (147, 148, 149)))
        self.assertEqual((FENCED.version, FENCED.source, FENCED.target), (5, 146, 148))
        # Recognition is deliberately withheld: generic historical paths must
        # not accidentally skip the missing provider/backup/boot integration.
        with self.assertRaisesRegex(RuntimeError, 'operation_profile_invalid'):
            profile(deletion_contract())
        with self.assertRaises(RuntimeError): admission.validate_contract(deletion_contract())

    def test_no_approval_or_caller_adapter_can_enable_preparation(self):
        with patch.object(admission, 'require_fresh_authorization') as authorization:
            with self.assertRaisesRegex(RuntimeError, 'integration_incomplete'):
                release.admitted_manifest(self.root, deletion_contract())
            authorization.assert_not_called()
        actor = SimpleNamespace(contract=deletion_contract(), document={}, provider_adapter=object())
        with self.assertRaisesRegex(RuntimeError, 'operation_profile_invalid'):
            CompletedNormalUpgrade(actor, artifact_guard=lambda: None, model_loader=lambda: None,
                                   acceptance_guard=lambda: None, rehearsal_guard=lambda: None)
        with self.assertRaisesRegex(ValueError, 'automatic executor'):
            MigrationManifest.load(self.root/'web/deployment/releases'/release.MANIFEST, self.root)

    def test_exact_captured_manifest_and_sql_bytes(self):
        raw, snapshots = release.captured_source(self.root)
        self.assertEqual([row['number'] for row in raw['migrations']], [147, 148, 149, 150])
        self.assertEqual(set(snapshots), {147, 148, 149, 150})
        path = self.root/'web/database/migrations'/release.SQL_NAMES[150]
        original = snapshots[150]
        path.write_bytes(original+b'\n')
        self.assertEqual(snapshots[150], original)
        with self.assertRaises(RuntimeError): release.source_manifest(self.root)

    def test_every_sql_mirror_metadata_and_symlink_tamper_rejected(self):
        paths = [self.root/'web/deployment/releases'/release.MANIFEST,
                 self.root/'web/deployment/releases'/release.BRIDGE,
                 *self.root.glob('web/database/migrations/*.sql'),
                 *self.root.glob('web/supabase/migrations/*.sql')]
        for path in paths:
            original = path.read_bytes(); path.write_bytes(original+b'\n')
            with self.subTest(path=path), self.assertRaises(RuntimeError): release.source_manifest(self.root)
            path.write_bytes(original)
        for path in (paths[0], self.root/'web/database/migrations'/release.SQL_NAMES[150]):
            original = path.read_bytes(); alias = self.root/'alias'; alias.write_bytes(original)
            path.unlink(); path.symlink_to(alias)
            with self.subTest(path=path), self.assertRaises(OSError): release.source_manifest(self.root)
            path.unlink(); path.write_bytes(original); alias.unlink()
        parent = self.root/'web/database/migrations'
        parent.rename(self.root/'relocated-sql'); parent.symlink_to(self.root/'relocated-sql', target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'path_invalid'): release.source_manifest(self.root)

    def test_target_requires_exact_integer_schema_and_three_protocols(self):
        release.require_target_protocols(150, 2, 2, 2)
        for value in ((149, 2, 2, 2), (150, 2, 2, 1), (150, 2, 1, 2), (150, 1, 2, 2),
                      (150, 2, 2, True), (150.0, 2, 2, 2), (150, 2, 2, '2')):
            with self.subTest(value=value), self.assertRaises(RuntimeError): release.require_target_protocols(*value)

    def test_every_processing_lease_idle_session_lock_and_protocol_refuses(self):
        for schema in range(146, 151):
            value = self.observation(schema)
            release.require_database_quiescence(value, deletion_contract(), schema)
            for key in value:
                bad = copy.deepcopy(value); bad[key] = True if type(value[key]) is int else 'other-cluster'
                with self.subTest(schema=schema, key=key), self.assertRaises(RuntimeError):
                    release.require_database_quiescence(bad, deletion_contract(), schema)
            for key in release.COUNTERS:
                bad = dict(value); bad[key] = 1
                with self.subTest(schema=schema, counter=key), self.assertRaises(RuntimeError):
                    release.require_database_quiescence(bad, deletion_contract(), schema)
        for schema in (None, True, '150', 145, 151):
            with self.subTest(schema=schema), self.assertRaises(RuntimeError):
                release.require_database_quiescence({}, deletion_contract(), schema)

    def test_actual_protocol_results_not_just_function_presence_are_checked(self):
        class Cursor:
            def __init__(self, observation, protocols):
                self.observation, self.protocols, self.calls = observation, protocols, []
            def execute(self, sql, args=None):
                self.calls.append((sql, args))
                self.value = self.observation if sql == release.QUIESCENCE_SQL else self.protocols.pop(0)
            def fetchone(self): return (self.value,)
        base = self.observation(150)
        for key in ('delivery_protocol', 'outbox_protocol', 'deletion_protocol'): base.pop(key)
        good = Cursor(dict(base), [2, 2, 2])
        release.observe_database_quiescence(good, deletion_contract(), 150)
        self.assertEqual([row[0] for row in good.calls[1:]], [
            'select public.notification_delivery_protocol()', 'select public.notification_outbox_protocol()',
            'select public.data_deletion_ownership_protocol()'])
        for values in ([2, 2, 1], [2, 1, 2], [True, 2, 2]):
            with self.subTest(protocols=values), self.assertRaises(RuntimeError):
                release.observe_database_quiescence(Cursor(dict(base), list(values)), deletion_contract(), 150)
        old = self.observation(149)
        for key in ('delivery_protocol', 'outbox_protocol', 'deletion_protocol'): old.pop(key)
        with self.assertRaisesRegex(RuntimeError, 'unexpected_protocol'):
            release.observe_database_quiescence(Cursor(old, [2, 2, 'unexpected-present-function']), deletion_contract(), 149)
