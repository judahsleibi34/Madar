"""Original-role input/model and temporary journal tests; no backup success."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import maintenance_backup_roles as roles
from deployment.lib import schema149_provider_lifecycle as retained
from deployment.lib.schema150_provider_lifecycle import FENCE_STEPS, ProtectedProviderJournal
from test_schema150_provider_lifecycle import binding


class MaintenanceRoleInputTests(unittest.TestCase):
    def actor(self, *, fenced=True):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); root.chmod(0o700)
        context = binding(); root = root / context['context_sha256']; root.mkdir(mode=0o700)
        (root / 'provider-journal').mkdir(mode=0o700)
        self.enterContext(patch.object(retained, 'protected', lambda path, **kw: Path(path)))
        self.enterContext(patch.object(retained, 'require_root_directory', lambda path: None))
        self.enterContext(patch.object(roles.os, 'geteuid', return_value=0))
        journal = ProtectedProviderJournal(root / 'provider-journal')
        preimage = {'roles': {'original': {'provider': {'login': True}}}}
        journal.append('prepared', {'binding': context, 'preimage': preimage})
        if fenced:
            for step in FENCE_STEPS:
                journal.append('effect_intent', {'step': step})
                journal.append('effect_complete', {'step': step})
        actor = roles.Schema150ProviderAdapter.__new__(roles.Schema150ProviderAdapter)
        actor.root, actor.binding = root, context
        actor.require_authority = Mock()
        actor.observe_quiescence = Mock(return_value={'schema': 146})
        actor.backup_role_archive = Mock(return_value=b'-- synthetic original LOGIN role SQL\n')
        return actor, context, journal

    def test_original_bytes_are_captured_once_not_replaced_by_current_nologin_roles(self):
        actor, context, journal = self.actor()
        before = journal.read()
        captured = roles.capture_original_roles(actor)
        actor.backup_role_archive.assert_called_once_with(context)
        self.assertEqual(captured.sql_bytes, b'-- synthetic original LOGIN role SQL\n')
        self.assertEqual(journal.read(), before)
        self.assertFalse(captured.verify(context, expected_schema=146)['authority_issued'])
        actor.backup_role_archive.return_value = b'-- current NOLOGIN, not original\n'
        self.assertNotEqual(captured.sql_bytes, actor.backup_role_archive.return_value)

    def test_wrong_actor_missing_authority_incomplete_fence_and_middle_schema_refuse(self):
        with self.assertRaisesRegex(RuntimeError, 'protected_actor_required'):
            roles.capture_original_roles(Mock())
        actor, _, _ = self.actor(fenced=False)
        with self.assertRaisesRegex(RuntimeError, 'complete_fence_required'):
            roles.capture_original_roles(actor)
        actor, _, _ = self.actor()
        actor.require_authority.side_effect = RuntimeError('actual_authority_missing')
        with self.assertRaisesRegex(RuntimeError, 'actual_authority_missing'):
            roles.capture_original_roles(actor)
        actor.require_authority.side_effect = None
        actor.observe_quiescence.return_value = {'schema': 149}
        with self.assertRaisesRegex(RuntimeError, 'backup_boundary_invalid'):
            roles.capture_original_roles(actor)

    def test_context_cluster_source_schema_and_bytes_cannot_be_substituted(self):
        actor, context, _ = self.actor(); captured = roles.capture_original_roles(actor)
        for key in ('context_sha256', 'system_identifier', 'source_sha', 'controller_sha'):
            wrong = dict(context); wrong[key] = 'different'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                captured.verify(wrong, expected_schema=146)
        for sql in (captured.sql_bytes+b'changed', b'', b'\xff'):
            with self.subTest(sql=sql), self.assertRaises(RuntimeError):
                roles.OriginalRoleArchive(captured.metadata_bytes, sql).verify(context, expected_schema=146)
        for schema in (True, 150, 147, '146'):
            with self.subTest(schema=schema), self.assertRaises(RuntimeError):
                captured.verify(context, expected_schema=schema)

    def test_malformed_metadata_or_authority_claim_never_becomes_backup_evidence(self):
        actor, context, _ = self.actor(); captured = roles.capture_original_roles(actor)
        original = json.loads(captured.metadata_bytes)
        for key, value in (('authority_issued', True), ('version', True), ('sql_bytes', True),
                           ('preimage_sha256', 'bad'), ('captured_schema', True)):
            bad = dict(original); bad[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                roles.OriginalRoleArchive(json.dumps(bad).encode(), captured.sql_bytes).verify(context, expected_schema=146)
        with self.assertRaises(RuntimeError):
            roles.OriginalRoleArchive(b'not json', captured.sql_bytes).verify(context, expected_schema=146)

    def test_journal_change_during_capture_refuses_without_success_publication(self):
        actor, _, journal = self.actor()
        def changed(_):
            journal.append('quiescence', {'schema': 146})
            return b'-- original role SQL\n'
        actor.backup_role_archive.side_effect = changed
        with self.assertRaisesRegex(RuntimeError, 'preimage_changed'):
            roles.capture_original_roles(actor)

    def test_fixed_append_only_input_refuses_replay_and_never_publishes_backup_success(self):
        actor, context, _ = self.actor()
        self.enterContext(patch.object(roles, 'ADMISSIONS', actor.root.parent))
        self.enterContext(patch.object(roles, 'protected', lambda path, **kw: Path(path)))
        (actor.root / 'admission.json').write_text('{}')
        target = roles.seal_role_input(actor, stage='pre-migration')
        self.assertEqual(target, actor.root / 'pre-migration-original-roles')
        self.assertEqual(set(p.name for p in target.iterdir()), {'roles.sql', 'metadata.json', 'COMPLETE'})
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        for path in target.iterdir(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        marker = json.loads((target / 'COMPLETE').read_bytes())
        self.assertEqual(marker, {'metadata_sha256': hashlib.sha256((target / 'metadata.json').read_bytes()).hexdigest()})
        with self.assertRaises(FileExistsError): roles.seal_role_input(actor, stage='pre-migration')
        self.assertFalse((actor.root / 'pre-migration-backup.json').exists())
        self.assertFalse((actor.root / 'LATEST').exists())
        with self.assertRaises(RuntimeError): roles.seal_role_input(actor, stage='../arbitrary')

    def test_partial_publication_is_retained_and_cannot_be_automatically_replayed(self):
        actor, _, _ = self.actor()
        self.enterContext(patch.object(roles, 'ADMISSIONS', actor.root.parent))
        self.enterContext(patch.object(roles, 'protected', lambda path, **kw: Path(path)))
        (actor.root / 'admission.json').write_text('{}')
        actual = roles.exclusive
        def interrupt(path, body):
            actual(path, body)
            if path.name == 'metadata.json': raise RuntimeError('synthetic_controller_crash')
        with patch.object(roles, 'exclusive', side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, 'synthetic_controller_crash'):
                roles.seal_role_input(actor, stage='pre-migration')
        folder = actor.root / 'pre-migration-original-roles'
        self.assertTrue((folder / 'roles.sql').is_file())
        self.assertFalse((folder / 'COMPLETE').exists())
        with self.assertRaises(FileExistsError): roles.seal_role_input(actor, stage='pre-migration')


if __name__ == '__main__': unittest.main()
