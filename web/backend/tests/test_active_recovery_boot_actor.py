"""Boot actor dispatch/compensation regressions; no actual production effects."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_boot_actor import ActiveRecoveryBootActor,EARLY_PHASES

class BootActorTests(unittest.TestCase):
    def setUp(self):
        self.actor=ActiveRecoveryBootActor.__new__(ActiveRecoveryBootActor)
        self.actor.plan=SimpleNamespace(retained_inputs={'fixture':'a'*64})
        self.actor.phase=Mock(return_value='normal');self.actor.assemble=Mock()
        self.actor.source=SimpleNamespace(verify=Mock());self.actor.runtime=object()
        self.actor.candidate=SimpleNamespace(contract=object(),require_write_authority=Mock())
        self.actor.root=Path('/synthetic/fixture');self.actor.kernel=object()
        self.actor.completed_evidence=Mock();self.actor.native=Mock();self.actor.compensate=Mock()
        self.actor.fallback=SimpleNamespace(verify=Mock())
    def test_completed_normal_uses_guarded_boot_kernel(self):
        with patch('deployment.lib.active_recovery_boot_actor.ActiveRecoveryNormalBoot') as boot:
            boot.return_value.execute.return_value={'mode':'NORMAL'}
            self.assertEqual(self.actor.resume(),{'mode':'NORMAL'})
            self.actor.candidate.require_write_authority.assert_called_once_with(self.actor.candidate.contract,'NORMAL')
            boot.return_value.execute.assert_called_once();self.actor.compensate.assert_not_called()
    def test_revoked_grant_with_retained_normal_event_compensates_without_replay(self):
        self.actor.candidate.require_write_authority.side_effect=RuntimeError('revoked')
        with patch('deployment.lib.active_recovery_boot_actor.ActiveRecoveryNormalBoot') as boot:
            self.assertEqual(self.actor.resume()['mode'],'READ_ONLY');boot.assert_not_called()
        self.actor.compensate.assert_called_once()
    def test_every_interrupted_handoff_state_compensates_before_proxy_gate(self):
        for phase in ['read_only_handoff_pending','read_only_serving','controller_resume_pending','controller_resumed','standby_ready','write_grant_pending','compensation_pending']:
            self.actor.phase.return_value=phase;self.actor.compensate.reset_mock()
            with self.subTest(phase=phase):
                self.assertEqual(self.actor.resume()['phase'],'restricted_fallback');self.actor.compensate.assert_called_once()
    def test_failed_compensation_is_not_automatically_retried_or_granted(self):
        self.actor.phase.return_value='compensation_failed'
        with self.assertRaisesRegex(RuntimeError,'requires_operator'):self.actor.resume()
        self.actor.compensate.assert_not_called();self.actor.candidate.require_write_authority.assert_not_called()
    def test_early_staging_preserves_original_route_and_helper(self):
        with patch('deployment.lib.active_recovery_boot_actor.observe_retained_inputs',return_value=self.actor.plan.retained_inputs),patch('deployment.lib.active_recovery_boot_actor.verify') as verify:
            for phase in EARLY_PHASES:
                self.actor.phase.return_value=phase
                self.assertEqual(self.actor.resume()['mode'],'ORIGINAL_RESTRICTED_RECOVERY')
            self.assertEqual(verify.call_count,len(EARLY_PHASES))
        self.actor.assemble.assert_not_called();self.actor.compensate.assert_not_called()
    def test_changed_early_recovery_binding_denies_without_effect(self):
        self.actor.phase.return_value='detached_candidate_ready'
        with patch('deployment.lib.active_recovery_boot_actor.observe_retained_inputs',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'early_recovery_changed'):self.actor.resume()
        self.actor.assemble.assert_not_called();self.actor.compensate.assert_not_called()
    def test_incomplete_proxy_gate_cannot_publish_or_enable_normal(self):
        self.actor.phase.return_value='write_grant_pending'
        with self.assertRaisesRegex(RuntimeError,'proxy_gate_denied'):self.actor.proxy_gate()
        self.actor.compensate.assert_not_called();self.actor.candidate.require_write_authority.assert_not_called()
    def test_compensation_failure_propagates(self):
        self.actor.phase.return_value='write_grant_pending';self.actor.compensate.side_effect=RuntimeError('compensation_failed')
        with self.assertRaisesRegex(RuntimeError,'compensation_failed'):self.actor.resume()
