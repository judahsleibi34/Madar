"""Nonmutating checks for the one-project native provider rehearsal boundary."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import schema149_provider_rehearsal as rehearsal


class ProviderRehearsalSafetyTests(unittest.TestCase):
    def test_primary_host_rejects_all_modes_before_docker_or_sql(self):
        for mode in ('INSPECT', 'REHEARSE', 'RECOVER'):
            with self.subTest(mode=mode), patch.object(rehearsal.manage.socket, 'gethostname', return_value='madar-gpu'), \
                    patch.object(rehearsal.manage, 'docker') as docker, patch.object(rehearsal.manage, 'sql') as sql:
                with self.assertRaises(RuntimeError): rehearsal.main(mode)
                docker.assert_not_called(); sql.assert_not_called()

    def test_arbitrary_mode_and_effect_rejected_before_host_actions(self):
        for mode, stage in (('EXECUTE', None), ('REHEARSE', 'fence_roles'), ('APPLY-ONE', 'arbitrary_sql')):
            with self.subTest(mode=mode, stage=stage), patch.object(rehearsal.manage, 'require_staging_host') as host:
                with self.assertRaises(RuntimeError): rehearsal.main(mode, stage)
                host.assert_not_called()

    def test_private_journal_persists_and_rejects_linked_or_truncated_records(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); root.chmod(0o700)
            journal = rehearsal.Journal(root)
            journal.append('prepared', {'synthetic': True})
            self.assertEqual(rehearsal.Journal(root).read()[0]['payload'], {'synthetic': True})
            (root / '0001.json').write_text('{')
            (root / '0001.json').chmod(0o600)
            with self.assertRaises(json.JSONDecodeError): journal.read()
            (root / '0001.json').unlink()
            (root / '0001.json').symlink_to(root / '0000.json')
            with self.assertRaisesRegex(RuntimeError, 'untrusted'): journal.read()

    def test_unknown_database_session_is_never_terminated(self):
        actor = rehearsal.StagingActor.__new__(rehearsal.StagingActor)
        preimage = {'supervisors': {'known_sessions': [{'pid': 10, 'start': 'old', 'role': 'authenticator'}]}}
        for actual in ([{'pid': 11, 'start': 'new', 'role': 'postgres'}],
                       [{'pid': 10, 'start': 'new', 'role': 'authenticator'}]):
            with self.subTest(actual=actual), patch.object(rehearsal, 'sessions', return_value=actual), \
                    patch.object(rehearsal, 'sql') as sql:
                with self.assertRaisesRegex(RuntimeError, 'unknown_session'):
                    actor.drain_sessions({}, preimage)
                sql.assert_not_called()

    def test_native_fixture_cannot_claim_privileged_controller_or_replica_gates(self):
        actor = rehearsal.StagingActor.__new__(rehearsal.StagingActor)
        with patch.object(rehearsal, 'sql', return_value='149:2:2'):
            evidence = actor.activation_evidence({}, {})
        self.assertFalse(evidence['target_write_authority'])
        self.assertFalse(evidence['boot_recovery'])
        self.assertFalse(evidence['backup_restore_replica'])
        self.assertFalse(evidence['migration_receipts'])
        with patch.object(rehearsal, 'sql', return_value='148:2:1'):
            with self.assertRaisesRegex(RuntimeError, 'incompatible'):
                actor.activation_evidence({}, {})


if __name__ == '__main__':
    unittest.main()
