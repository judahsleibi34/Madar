"""Concrete supervisor refusal checks with synthetic systemd observations.

These are model/component tests, not native stop or privileged-controller proof.
"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_provider_lifecycle as lifecycle
from test_schema150_actor_inventory import phase_rows
import test_schema150_provider_adapter as fixtures


STOPPED = {'ActiveState': 'inactive', 'SubState': 'dead', 'Job': '',
           'MainPID': '0', 'ControlPID': '0'}


class SupervisorQuiescenceTests(unittest.TestCase):
    def component(self, **kwargs):
        values=fixtures.ConcreteAdapterTests.component(self, **kwargs)
        actor=values[0];actor.inventory['supervisors']=dict(sorted(actor.inventory['supervisors'].items()))
        return values

    def unit_state(self,name,**changed):
        result=dict(STOPPED)
        if name.endswith('.timer'):
            result.pop('MainPID');result.pop('ControlPID')
        result.update(changed);return result

    def test_only_complete_inactive_dead_observation_is_accepted(self):
        actor, _, _, _ = self.component(stage='fenced')
        actor._unit = Mock(side_effect=self.unit_state)
        self.assertTrue(actor._supervisors_stopped())
        self.assertEqual(actor._unit.call_count, len(actor.inventory['supervisors']))
        actor.runtime.command.assert_not_called()

    def test_active_transitions_jobs_and_surviving_pids_refuse(self):
        actor, _, _, _ = self.component(stage='fenced')
        mutations = ({'ActiveState': 'active'}, {'ActiveState': 'activating'},
                     {'ActiveState': 'deactivating'}, {'ActiveState': 'failed'},
                     {'SubState': 'running'}, {'Job': '271'}, {'Job': 'start'},
                     {'MainPID': '123'}, {'ControlPID': '123'},
                     {'MainPID': 0}, {'ControlPID': None})
        for changed in mutations:
            actor._unit = Mock(side_effect=lambda name:self.unit_state(name,**changed))
            with self.subTest(changed=changed), self.assertRaisesRegex(RuntimeError, 'supervisor_not_quiescent'):
                actor._supervisors_stopped()
        actor.runtime.command.assert_not_called()

    def test_missing_systemd_properties_never_mean_stopped(self):
        actor, _, _, _ = self.component(stage='fenced')
        for missing in STOPPED:
            def observed(name):
                fields=self.unit_state(name);fields.pop(missing,None);return fields
            actor._unit = Mock(side_effect=observed)
            with self.subTest(missing=missing), self.assertRaisesRegex(RuntimeError, 'supervisor_not_quiescent'):
                actor._supervisors_stopped()

    def test_pending_supervisor_stop_cannot_reconcile_from_container_states_alone(self):
        actor, scope, _, journal = self.component()
        actor._rows.return_value = phase_rows(actor.inventory, actor._rows.return_value, 'fenced')
        actor.barrier.write_text('{}')
        for step in lifecycle.FENCE_STEPS[:2]:
            journal.append('effect_intent', {'step': step})
            journal.append('effect_complete', {'step': step})
        journal.append('effect_intent', {'step': 'fence_supervisors'})
        actor._unit = Mock(side_effect=lambda name:self.unit_state(name,ActiveState='active'))
        model = lifecycle.ProviderMaintenance150(scope, journal, actor)
        before = journal.read()
        with self.assertRaisesRegex(RuntimeError, 'supervisor_not_quiescent'):
            model.reconcile_pending()
        self.assertEqual(journal.read(), before)
        self.assertEqual(model._state()[2], 'fence_supervisors')
        actor.runtime.command.assert_not_called()

    def test_migration_quiescence_refuses_supervisor_before_sql_or_object_capture(self):
        actor, scope, _, _ = self.component(stage='fenced')
        actor._unit = Mock(side_effect=lambda name:self.unit_state(name,Job='271'))
        actor._sql = Mock(side_effect=AssertionError('database must not be queried'))
        actor._object_preservation = Mock(side_effect=AssertionError('object bytes must not be captured'))
        with self.assertRaisesRegex(RuntimeError, 'supervisor_not_quiescent'):
            actor.observe_quiescence(scope)
        actor._sql.assert_not_called(); actor._object_preservation.assert_not_called()
        actor.runtime.command.assert_not_called()

    def test_private_boundary_does_not_assert_supervisor_fencing_from_barrier_alone(self):
        actor, scope, _, _ = self.component(stage='private')
        actor._unit = Mock(side_effect=lambda name:self.unit_state(name,ControlPID='271'))
        actor._sessions = Mock(side_effect=AssertionError('sessions must not be queried'))
        with self.assertRaisesRegex(RuntimeError, 'supervisor_not_quiescent'):
            actor.observe_private_boundary(scope)
        actor._sessions.assert_not_called(); actor.runtime.command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
