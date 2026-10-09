"""Concrete-driver ordering and fail-closed regressions, not production proof."""
import os
import tempfile
import json
import pwd
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_operations import ProductionActiveRecoveryOperations
from deployment.lib.active_recovery_resumption import ActiveRecoveryResumption

class ConcreteOperationsTests(unittest.TestCase):
    def setUp(self):
        self.ops=ProductionActiveRecoveryOperations.__new__(ProductionActiveRecoveryOperations)
        self.ops.plan=SimpleNamespace(digest='a'*64)
        self.ops.root=Path('/synthetic/plan');self.ops.package=Path('/synthetic/frozen')
        self.ops.source=SimpleNamespace(verify=Mock())
        self.ops.candidate=SimpleNamespace(contract=object(),_publish_write_authority=Mock(),require_write_authority=Mock())
        self.ops.workers=SimpleNamespace(stop_consumers=Mock())
        self.ops.kernel=object()
    def test_every_protocol_operation_has_concrete_implementation(self):
        import ast,inspect
        tree=ast.parse(inspect.getsource(ActiveRecoveryResumption))
        names={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Attribute)
            and node.func.value.attr=='ops'}
        self.assertTrue(names)
        for name in names:
            with self.subTest(name=name):self.assertTrue(callable(getattr(ProductionActiveRecoveryOperations,name,None)))
    def test_failed_revocation_still_stops_consumers(self):
        self.ops.candidate._publish_write_authority.side_effect=RuntimeError('failed_fence')
        with self.assertRaises(RuntimeError):self.ops.fence_normal_writes_and_stop_consumers(self.ops.plan)
        self.ops.workers.stop_consumers.assert_called_once()
    def test_failed_stop_prevents_fallback_publication(self):
        self.ops.workers.stop_consumers.side_effect=RuntimeError('failed_stop')
        with self.assertRaises(RuntimeError):self.ops.fence_normal_writes_and_stop_consumers(self.ops.plan)
        self.ops.candidate.require_write_authority.assert_not_called()
    def test_no_compensation_deadline_override(self):
        self.ops.actor=Mock()
        with self.assertRaises(RuntimeError):self.ops.publish_verified_current_data_fallback(self.ops.plan,self.ops.root,61)
        self.ops.actor.assert_not_called()
    def test_compensation_uses_existing_current_data_adapter(self):
        actor=Mock();self.ops.actor=Mock(return_value=actor)
        self.ops.publish_verified_current_data_fallback(self.ops.plan,self.ops.root,60)
        actor.compensation.publish.assert_called_once_with(actor.fallback_public_round)
    def test_changed_convergence_policy_denied(self):
        self.ops.require_emergency_routing_handoff_complete=Mock()
        with self.assertRaises(RuntimeError):self.ops.require_sustained_read_only_serving(self.ops.plan,deadline_seconds=181,consecutive_rounds=3,minimum_span_seconds=5)
        self.ops.require_emergency_routing_handoff_complete.assert_not_called()
    def test_convergence_retries_only_explicit_availability(self):
        from deployment.lib.emergency_routing_repair import AvailabilityFailure
        self.ops.runtime=SimpleNamespace(budget=Mock(return_value=0))
        check=Mock(side_effect=[AvailabilityFailure('starting'),'verified'])
        with patch('deployment.lib.active_recovery_operations.verification_window'),patch('deployment.lib.active_recovery_operations.time.sleep'):
            self.assertEqual(self.ops.converge(check,180),'verified')
        self.assertEqual(check.call_count,2)
        check=Mock(side_effect=RuntimeError('identity_changed'))
        with patch('deployment.lib.active_recovery_operations.verification_window'),self.assertRaises(RuntimeError):self.ops.converge(check,180)
        self.assertEqual(check.call_count,1)
    def test_normal_config_publication_precedes_positive_grant(self):
        self.ops.verify_final_write_grant_prerequisites=Mock()
        with patch('deployment.lib.active_recovery_operations.ActiveRecoveryWriteAuthority') as authority,patch('deployment.lib.active_recovery_operations.ActiveRecoveryNormalPublication') as publication:
            calls=Mock();calls.attach_mock(authority.return_value.guard,'guard');calls.attach_mock(publication.return_value.publish,'publish');calls.attach_mock(authority.return_value.grant,'grant')
            self.ops.commit_normal_release_and_grant_writes(self.ops.plan,self.ops.root)
            self.assertEqual([call[0] for call in calls.mock_calls],['guard','publish','grant'])

    def test_public_backup_health_marker_accepts_0644_and_preserves_private_preimage(self):
        from deployment.lib import active_recovery_operations as module
        from deployment.lib.provider_recovery_runtime import readonly_configuration
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);marker=base/'latest.json';marker.write_text('{"old_health":true}');marker.chmod(0o644)
            self.ops.root=base/'new-attempt';self.ops.root.mkdir()
            self.ops.plan.checkpoint_execution_sha256='b'*64
            identity=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())
            real_path=Path
            def trusted_fixture_ancestors(value):
                stat=os.lstat(value)
                # Only the test's world-writable tmp ancestor is modeled as a
                # production parent. The leaf's real 0644 permissions are kept.
                return SimpleNamespace(st_uid=0,st_mode=0o40755) if value==Path('/tmp') else stat
            def path(value):return marker if value=='/var/lib/madar/backup-state/latest.json' else real_path(value)
            with patch.object(module,'Path',side_effect=path),patch.object(module,'ActiveRecoveryBackupTimers') as timers, \
                 patch.object(module,'coordinated_health_marker',return_value={'verified':True}), \
                 patch.object(module.pwd,'getpwnam',return_value=identity),patch.object(Path,'lstat',trusted_fixture_ancestors):
                with self.assertRaisesRegex(RuntimeError,'not_private'):readonly_configuration(marker)
                self.ops.quiesce_backup_timers_before_staging(self.ops.plan,self.ops.root)
                timers.return_value.quiesce.assert_called_once()
            self.assertEqual(json.loads((self.ops.root/'backup-health-preimage.json').read_text()),{'old_health':True})
            self.assertEqual((self.ops.root/'backup-health-preimage.json').stat().st_mode&0o777,0o600)
            self.assertEqual(marker.stat().st_mode&0o777,0o644)
            self.assertEqual(json.loads(marker.read_text()),{'verified':True})


class SustainedNormalTests(unittest.TestCase):
    def setUp(self):
        self.ops=ProductionActiveRecoveryOperations.__new__(ProductionActiveRecoveryOperations)
        self.ops.runtime=SimpleNamespace(budget=Mock(return_value=0))
    def test_requires_three_complete_rounds_spanning_five_seconds(self):
        check=Mock(return_value={'verified':'actual round'})
        with patch('deployment.lib.active_recovery_operations.verification_window'), \
             patch('deployment.lib.active_recovery_operations.time.sleep'), \
             patch('deployment.lib.active_recovery_operations.time.monotonic',side_effect=[0,5]):
            self.assertEqual(self.ops.sustained_normal_rounds(check),{'verified':'actual round'})
        self.assertEqual(check.call_count,3)
    def test_transient_availability_resets_success_count(self):
        from deployment.lib.emergency_routing_repair import AvailabilityFailure
        check=Mock(side_effect=[True,True,AvailabilityFailure('warming'),True,True,True])
        with patch('deployment.lib.active_recovery_operations.verification_window'), \
             patch('deployment.lib.active_recovery_operations.time.sleep'), \
             patch('deployment.lib.active_recovery_operations.time.monotonic',side_effect=[0,5,10]):
            self.assertTrue(self.ops.sustained_normal_rounds(check))
        self.assertEqual(check.call_count,6)
    def test_integrity_failure_is_not_retried(self):
        check=Mock(side_effect=RuntimeError('identity_changed'))
        with patch('deployment.lib.active_recovery_operations.verification_window'), \
             self.assertRaisesRegex(RuntimeError,'identity_changed'):
            self.ops.sustained_normal_rounds(check)
        self.assertEqual(check.call_count,1)
    def test_overall_deadline_stops_verification(self):
        from deployment.lib.emergency_routing_repair import VerificationDeadline
        self.ops.runtime.budget.side_effect=VerificationDeadline('expired')
        check=Mock()
        with patch('deployment.lib.active_recovery_operations.verification_window'), \
             self.assertRaises(VerificationDeadline):self.ops.sustained_normal_rounds(check)
        check.assert_not_called()
