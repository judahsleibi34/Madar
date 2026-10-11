"""The durable dispatcher delegates cold database convergence to the kernel."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from deployment.lib import completed_normal_boot_actor as m


class BootDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        actor=object.__new__(m.CompletedNormalBootActor);self.actor=actor
        actor.root=Path(self.tmp.name);(actor.root/'candidate-runtime.json').write_text('{}')
        actor.contract={};actor.guard=Mock();actor.proxy_identity=Mock();actor.event=Mock()
        actor.native=Mock(side_effect=AssertionError('native check outside bounded kernel'))
        actor.publish=Mock();actor.compensate=Mock()
        self.kernel=SimpleNamespace(execute=Mock(return_value={'mode':'NORMAL'}),
            execute_read_only=Mock(return_value={'mode':'READ_ONLY'}))
        actor.candidate=Mock(return_value=self.kernel)

    def test_cold_normal_restart_does_not_probe_database_before_bounded_kernel(self):
        with patch.object(m,'require_candidate_authority',return_value={'mode':'NORMAL'}):
            self.assertEqual(self.actor.resume(),{'mode':'NORMAL'})
        self.actor.native.assert_not_called();self.kernel.execute.assert_called_once()
        self.actor.publish.assert_not_called()

    def test_uncompleted_sql_intent_revokes_normal_and_recovers_only_compatible_read_only(self):
        self.kernel.execute.side_effect=RuntimeError('compatible_boot_migration_forward_repair_required')
        with patch.object(m,'require_candidate_authority',return_value={'mode':'NORMAL'}):
            self.assertEqual(self.actor.resume(),{'mode':'READ_ONLY'})
        self.actor.publish.assert_called_once_with('READ_ONLY')
        self.kernel.execute_read_only.assert_called_once();self.actor.native.assert_not_called()

    def test_identity_failure_is_fatal_and_never_falls_back_to_old115(self):
        self.kernel.execute.side_effect=RuntimeError('compatible_boot_runtime_image_changed')
        with patch.object(m,'require_candidate_authority',return_value={'mode':'NORMAL'}):
            with self.assertRaisesRegex(RuntimeError,'runtime_image_changed'):self.actor.resume()
        self.kernel.execute_read_only.assert_not_called();self.actor.publish.assert_not_called()

    def test_revoked_grant_can_only_resume_read_only(self):
        with patch.object(m,'require_candidate_authority',return_value={'mode':'READ_ONLY'}):
            self.assertEqual(self.actor.resume(),{'mode':'READ_ONLY'})
        self.kernel.execute.assert_not_called();self.kernel.execute_read_only.assert_called_once()

if __name__=='__main__':unittest.main()
