"""Exercise forward-controller preservation with each admitted SQL profile.

Transport, authorization and privileged effects use isolated fixtures. The real
controller execute path and original-column preservation verifier run together;
an executor-only retry cannot establish this controller boundary.
"""
from contextlib import nullcontext
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from deployment.lib import completed_normal_forward as forward
from deployment.lib.completed_normal_profile import LEGACY, MANUAL, COMMERCIAL, FENCED
from test_completed_normal_admission import fixture_contract
from test_completed_normal_forward import fixture_plan


def snapshots(selected):
    names = [f'public.fixture_{index:03d}' for index in range(95)]
    names += ['public.application_schema_state', 'auth.users', 'auth.identities',
              'auth.mfa_factors', 'storage.objects', 'storage.buckets']
    if selected is FENCED:
        names += ['auth.sessions', 'storage.synthetic_metadata']
    if selected is COMMERCIAL:
        names += ['public.commercial_price_books']
    before = {'schema': selected.source,
              'columns': {name: ['id', 'value'] for name in names},
              'roots': {name: {'table': name, 'count': 1, 'sha256': 'a' * 64}
                        for name in names}}
    after = copy.deepcopy(before)
    after['schema'] = selected.target
    after['roots']['public.application_schema_state']['sha256'] = 'b' * 64
    if selected is COMMERCIAL:
        after['roots']['public.commercial_price_books'].update(count=2, sha256='c' * 64)
        after['commercial_addition'] = {
            'verified': True,
            'preserved_original_rows': before['roots']['public.commercial_price_books']}
    return before, after


class ForwardPreservationTests(unittest.TestCase):
    def execute_fixture(self, selected, *, changed_table=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        contract = fixture_contract()
        contract.update(version=selected.version, operation=selected.operation)
        plan = fixture_plan(contract)
        plan.update(version=selected.version,
                    operation=forward.forward_operation(contract),
                    observed_schema=selected.source)
        actor = SimpleNamespace(contract=contract, root=root / 'parent',
                                ops=Mock(upgrade_root=root, state_root=root / 'state'),
                                runtime=Mock(), guard=Mock(), native=Mock(), compensate=Mock())
        actor.root.mkdir()
        original, current = snapshots(selected)
        if changed_table:
            current['roots'][changed_table]['sha256'] = 'd' * 64
        (actor.root / 'pre-migration-customer-snapshot.json').write_text(json.dumps(original))
        driver = forward.CompletedNormalForwardResumption(
            actor, plan, artifact_guard=Mock(), rehearsal_guard=Mock())
        driver.root = root / 'resumptions' / 'new-attempt'
        driver.preflight = Mock()
        driver.credential = nullcontext
        # A real owned descriptor is closed by the controller's finally block.
        descriptor = os.open(root / 'upgrade.lock', os.O_RDWR | os.O_CREAT, 0o600)
        patches = [
            patch.object(forward.os, 'geteuid', return_value=0),
            patch.object(forward, 'protected', lambda path, **kwargs: Path(path)),
            patch('deployment.lib.control_plane_upgrade.acquire_lock', return_value=descriptor),
            patch('deployment.lib.control_plane_filesystem.require_root_protected_directory'),
            patch('deployment.lib.completed_normal_execution.protected_creation_mode', nullcontext),
            patch('deployment.lib.completed_normal_database.migration_customer_snapshot', return_value=current),
            patch('deployment.lib.completed_normal_execution.verify_serving', return_value={'mode': 'READ_ONLY'}),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        seal_patch = patch('deployment.lib.completed_normal_migration.seal_completion')
        seal = seal_patch.start()
        self.addCleanup(seal_patch.stop)
        return driver, actor, seal

    def test_forward_completion_uses_actual_profile_and_remains_read_only(self):
        for selected in (LEGACY, MANUAL, COMMERCIAL, FENCED):
            with self.subTest(profile=selected.operation):
                driver, actor, seal = self.execute_fixture(selected)
                result = driver.execute()
                self.assertEqual((result['schema'], result['mode']), (selected.target, 'READ_ONLY'))
                self.assertFalse(result['normal_grant_issued'])
                self.assertTrue(result['separate_normal_completion_required'])
                preservation = json.loads((driver.root / 'customer-preservation.json').read_text())
                self.assertEqual((preservation['starting_schema'], preservation['final_schema']),
                                 (selected.source, selected.target))
                seal.assert_called_once()
                actor.ops.clear_interlock.assert_called_once()
                actor.compensate.assert_not_called()
                self.doCleanups()

    def test_schema148_forward_rejects_customer_auth_and_storage_changes(self):
        for table in ('public.fixture_000', 'auth.users', 'auth.mfa_factors',
                      'auth.sessions', 'storage.objects', 'storage.synthetic_metadata'):
            with self.subTest(table=table):
                driver, actor, seal = self.execute_fixture(FENCED, changed_table=table)
                with self.assertRaisesRegex(RuntimeError, 'existing_customer_values_changed'):
                    driver.execute()
                seal.assert_not_called()
                actor.ops.clear_interlock.assert_not_called()
                actor.compensate.assert_called_once()
                self.assertFalse((driver.root / 'completion.json').exists())
                self.assertEqual(actor.ops.run_deploy_service.call_count, 1)
                self.doCleanups()


if __name__ == '__main__':
    unittest.main()
