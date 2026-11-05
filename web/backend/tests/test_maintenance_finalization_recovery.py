"""Approval/lock component coverage; does not claim installed application recovery."""
import copy
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import Mock,patch

from deployment.lib import completed_normal_maintenance_recovery as recovery
from deployment.lib import exceptional_release_approval as approval
from deployment.lib import historical_origin as origin
from deployment.lib.migration_inventory import canonical,digest
from test_canonical_exceptional_review import CanonicalExceptionalReviewTests as Fixture


class MaintenanceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.p['version']=3;f.p['recovery_actions']=[recovery.ACTION]
        f.driver.observe_maintenance_finalization=Mock(return_value={'phase':'service_adopt_completed','schema':160,'data':'measured','stale_credentials':{'root':None,'issuer':None}})
        self.enterContext(patch.object(recovery,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(approval,'root',return_value=f.root))
        self.enterContext(patch.object(recovery,'owner_live',return_value=False))
        result,self.parent=f.approved();self.parent_id=result['request_id']
        with f.held_locks(),patch.object(origin,'bind_successor_under_locks'),patch.object(origin,'require_successor_binding'):
            approval.verify_canonical_execution(self.parent,f.system,consume=True,token='stdin-token')
            approval.execution_event(f.system,self.parent,'EXECUTING',{})
        self.original={p.name:p.read_bytes() for p in (f.root/self.parent_id).iterdir() if p.is_file()}

    def approved(self):
        f=self.f;r=recovery.create(f.system,self.parent_id)
        approval.decide(f.system,r['request_id'],'approve','stdin-token',r['request_sha256'])
        return approval.inspect(f.system,r['request_id'])['request']['admission']

    def test_fresh_approval_consumes_once_without_modifying_parent(self):
        f=self.f;value=self.approved()
        self.assertNotEqual(value['request_id'],self.parent_id)
        with f.held_locks():
            recovery.verify(f.system,value,consume=True,token='stdin-token')
            approval.execution_event(f.system,value,'EXECUTING',{})
            lease=recovery.require_lease(f.system,f.contract,value)
            self.assertEqual(lease['request_id'],value['request_id'])
            self.assertEqual(lease['execution_expires_at'],value['expires_at'])
            with self.assertRaisesRegex(RuntimeError,'consumed'):
                recovery.verify(f.system,value,consume=True,token='stdin-token')
        self.assertEqual(self.original,{p.name:p.read_bytes() for p in (f.root/self.parent_id).iterdir() if p.is_file()})

    def test_live_parent_cannot_be_recovered(self):
        with patch.object(recovery,'owner_live',return_value=True),self.assertRaisesRegex(RuntimeError,'not_interrupted'):
            recovery.create(self.f.system,self.parent_id)

    def test_unenrolled_recovery_refuses(self):
        self.f.p['version']=2;self.f.p.pop('recovery_actions')
        with self.assertRaisesRegex(RuntimeError,'not_independently_enrolled'):
            recovery.create(self.f.system,self.parent_id)

    def test_version3_real_policy_parser_preserves_scope_and_separate_keys(self):
        self.f.test_independent_policy_parser_requires_exact_canonical_contract_and_distinct_key()

    def test_competing_controller_refuses_on_existing_upgrade_lock(self):
        from deployment.lib import completed_normal_execution as execution
        value=self.approved();driver=self.f.driver;driver.lock=None
        with self.f.held_locks(),patch.object(execution.os,'geteuid',return_value=0),self.assertRaisesRegex(RuntimeError,'lock'):
            driver.recover_maintenance_finalization(value,'stdin-token')
        self.assertFalse((self.f.root/value['request_id']/'approval-consumed.json').exists())

    def test_dead_parent_credential_retirement_requires_fresh_consumption_and_exact_bytes(self):
        f=self.f;f.system.runtime_root=f.root/'runtime';f.system.runtime_root.mkdir()
        consumed=approval.verified(f.root/self.parent_id/'approval-consumed.json',f.key)
        lease={k:consumed[k] for k in ('pid','process_start','boot_id','admission_sha256','approval_sha256')}
        lease.update(request_id=self.parent_id,context_sha256=self.parent['context_sha256'])
        body=canonical({'canonical_exceptional_approval':lease,'test_bearer':'private-fixture-only'})
        import hashlib
        expected={'sha256':hashlib.sha256(body).hexdigest(),'lease':lease}
        f.driver.observe_maintenance_finalization.return_value['stale_credentials']['root']=expected
        path=f.system.runtime_root/('root-credentials-'+self.parent['context_sha256'][:16])/'madar-control-plane-upgrade'
        path.parent.mkdir();path.write_bytes(body);path.chmod(0o600)
        value=self.approved()
        with f.held_locks():
            with self.assertRaisesRegex(RuntimeError,'not_current_owner'):
                recovery.retire_parent_credential(f.system,value)
            self.assertTrue(path.exists())
            recovery.verify(f.system,value,consume=True,token='stdin-token')
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'credential_changed'):
                recovery.retire_parent_credential(f.system,value)
            path.write_bytes(body)
            recovery.retire_parent_credential(f.system,value)
        self.assertFalse(path.exists())
        record=approval.verified(f.root/value['request_id']/'retired-parent-credential.json',f.key)
        self.assertEqual(record['credential_sha256'],expected['sha256'])
        self.assertNotIn('private-fixture-only',json.dumps(record))

    def test_wrong_source_database_operation_or_parent_digest_refuses(self):
        value=self.approved()
        for key,bad in [('source_sha','f'*40),('operation_id','00000000-0000-4000-8000-000000000000'),
                        ('parent_consumption_sha256','f'*64),('controller_sha','f'*40)]:
            with self.subTest(key=key),self.f.held_locks(),self.assertRaises(RuntimeError):
                recovery.verify(self.f.system,dict(value,**{key:bad}),consume=True,token='stdin-token')
        altered=copy.deepcopy(value);altered['contract']['database']['system_identifier']='999999'
        with self.f.held_locks(),self.assertRaises(RuntimeError):
            recovery.verify(self.f.system,altered,consume=True,token='stdin-token')

    def test_changed_observation_refuses_before_consumption(self):
        value=self.approved();self.f.driver.observe_maintenance_finalization.return_value={'schema':146,'stale_credentials':{'root':None,'issuer':None}}
        with self.f.held_locks(),self.assertRaisesRegex(RuntimeError,'observation_changed'):
            recovery.verify(self.f.system,value,consume=True,token='stdin-token')
        self.assertFalse((self.f.root/value['request_id']/'approval-consumed.json').exists())

    def test_expired_revoked_or_forged_approval_refuses(self):
        for kind in ('expired','revoked','forged'):
            with self.subTest(kind=kind):
                value=self.approved();path=self.f.root/value['request_id']
                if kind=='revoked':
                    status=approval.inspect(self.f.system,value['request_id'])
                    approval.decide(self.f.system,value['request_id'],'revoke','stdin-token',status['request_sha256'])
                elif kind=='forged':
                    packet=json.loads((path/'approval.json').read_text());packet['signature']='0'*64
                    (path/'approval.json').write_bytes(canonical(packet))
                with self.f.held_locks(),patch.object(recovery.time,'time',return_value=value['expires_at'] if kind=='expired' else time.time()),self.assertRaises(RuntimeError):
                    recovery.verify(self.f.system,value,consume=True,token='stdin-token')
                self.assertFalse((path/'approval-consumed.json').exists())

    def test_failed_operator_or_technical_gate_refuses(self):
        value=self.approved();self.f.system.authenticate_operator.side_effect=RuntimeError('revoked_session')
        with self.f.held_locks(),self.assertRaisesRegex(RuntimeError,'revoked_session'):
            recovery.verify(self.f.system,value,consume=True,token='stdin-token')
        self.assertFalse((self.f.root/value['request_id']/'approval-consumed.json').exists())

    def test_missing_actual_locks_refuses(self):
        value=self.approved()
        with self.assertRaises(RuntimeError):recovery.verify(self.f.system,value,consume=True,token='stdin-token')

    def test_actual_observer_rejects_earlier_boundaries_and_completed_state(self):
        from deployment.lib import completed_normal_execution as execution
        driver=self.f.driver;del driver.observe_maintenance_finalization
        driver.root=self.f.root/'controller-records';driver.root.mkdir()
        driver.actor.guard=Mock();driver.actor.native=Mock(return_value=160)
        driver.artifact_guard=Mock();driver.rehearsal_guard=Mock()
        with patch.object(execution,'protected',lambda p,**kw:Path(p)):
            for phase in ('pre_migration_backup_pending','parent_migration_pending',
                          'post_migration_backup_pending','accepted_workers_pending'):
                (driver.root/'boot-events.jsonl').write_text(json.dumps({'phase':phase})+'\n')
                with self.subTest(phase=phase),self.assertRaisesRegex(RuntimeError,'boundary_required'):
                    driver.observe_maintenance_finalization()
            (driver.root/'normal-completion.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'state_unsupported'):
                driver.observe_maintenance_finalization()
            (driver.root/'normal-completion.json').unlink()
            (driver.root/'boot-events.jsonl').write_text(json.dumps({'phase':'service_adopt_completed'})+'\n')
            driver.actor.native.return_value=159
            with self.assertRaisesRegex(RuntimeError,'committed_target_required'):
                driver.observe_maintenance_finalization()

    def test_preconsumption_refusal_does_not_clear_parent_credentials(self):
        from deployment.lib import completed_normal_execution as execution
        from deployment.lib.control_plane_upgrade import SystemOperations
        driver=self.f.driver;driver.lock=None
        driver.ops.clear_authorization=Mock()
        driver.ops.close_locks=lambda:SystemOperations.release_deployment_lock(driver.ops)
        with patch.object(execution.os,'geteuid',return_value=0),patch.object(recovery,'verify',side_effect=RuntimeError('stale_observation')):
            with self.assertRaisesRegex(RuntimeError,'stale_observation'):
                driver.recover_maintenance_finalization({},'stdin-token')
        driver.ops.clear_authorization.assert_not_called()
        self.assertIsNone(driver.lock)
        self.assertIsNone(driver.ops.deploy_lock_descriptor)

    def test_restart_uses_durable_timer_preimages_not_current_timer_state(self):
        from deployment.lib import completed_normal_execution as execution
        from deployment.lib.control_plane_upgrade import BACKUP_TIMERS
        driver=self.f.driver;driver.root=self.f.root/'timer-records';driver.root.mkdir()
        expected={name:{'enabled':'disabled','active':'inactive'} for name in BACKUP_TIMERS}
        driver.document['backup_timer_states']=expected
        path=driver.root/'backup-timer-preimages.json';path.write_text(json.dumps(expected))
        driver.ops.interlock_backup_states=Mock(return_value=expected)
        with patch.object(execution,'protected',lambda p,**kw:Path(p)):
            self.assertEqual(driver.maintenance_recovery_timer_snapshot(),expected)
            driver.ops.interlock_backup_states.assert_called_with(driver.controller)
            driver.ops.interlock_backup_states.return_value=None
            with self.assertRaisesRegex(RuntimeError,'preimages_changed'):
                driver.maintenance_recovery_timer_snapshot()
            driver.ops.interlock_backup_states.return_value=expected
            path.write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'preimages_changed'):
                driver.maintenance_recovery_timer_snapshot()

    def test_issuer_cannot_dispatch_sql_or_child_using_recovery(self):
        from deployment.lib.control_plane_upgrade import SystemOperations
        s=object.__new__(SystemOperations);s.canonical_maintenance_recovery={'kind':recovery.KIND}
        for args in ({},{'completed_normal_contract':{},'completed_normal_mode':'activate'},
                     {'completed_normal_contract':{},'migration_resumption':{}},
                     {'completed_normal_contract':{},'recovery':True}):
            with self.subTest(args=args),self.assertRaisesRegex(RuntimeError,'finalization_only'):
                s.write_authorization('a'*40,**args)
