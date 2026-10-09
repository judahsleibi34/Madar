"""Concrete-driver ordering and fail-closed regressions, not production proof."""
import os
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
