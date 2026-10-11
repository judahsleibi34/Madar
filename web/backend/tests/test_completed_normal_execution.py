"""Coordinator ordering/failure injection; not a full private deployment PASS."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from test_completed_normal_admission import fixture_contract
from deployment.lib import completed_normal_execution as m


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'attempt';self.calls=[]
        self.failure=None;self.mode='READ_ONLY';self.origin='NORMAL';self.schema=115
        self.owners=1;self.backup_count=0
        self.contract=fixture_contract()
        self.document={'source_bundle_sha256':'f'*64,'backup_timer_states':{'native':{'active':'active','enabled':'enabled'}}}
        def effect(name):
            self.calls.append(name)
            if self.failure==name:raise RuntimeError('PRIVATE VALUE MUST NOT APPEAR')
        self.effect=effect
        self.ops=SimpleNamespace(upgrade_root=self.base,state_root=self.base/'state',
            quiesce=lambda sha:effect('quiesce'),write_authorization=Mock(),clear_authorization=Mock(),
            release_deployment_lock=lambda:effect('release_lock'),close_locks=Mock(),clear_interlock=lambda:effect('clear_interlock'),
            systemctl_state=lambda n:{'active':'active','enabled':'enabled'},
            current_preflight=lambda **kw:effect('origin_rechecked'),
            restore_backup_timers=lambda:effect('restore_timers'),
            durable_quiesce_snapshot_exists=lambda sha:True,
            requiesce_backup_timers_for_failure=lambda:effect('requiesce_timers'))
        def service(label,sha,*,completed_normal_contract,completed_normal_mode):
            mode=completed_normal_mode;effect('service_'+mode)
            if mode=='activate':
                if self.origin!='READ_ONLY':raise AssertionError('unfenced_origin')
                self.owners=1
            if mode=='migrate':
                if self.mode!='READ_ONLY':raise AssertionError('sql_under_positive_grant')
                self.schema=136
        self.ops.run_deploy_service=service
        def compensate():
            # Real leaf behavior is covered separately; this verifies the
            # coordinator does not skip it because its audit failed.
            self.mode=self.origin='READ_ONLY';effect('compensate')
        kernel=SimpleNamespace(contract=self.contract,root=self.root,native_verifier=lambda:self.schema,
            round=lambda **kw:effect('round_normal' if kw['normal'] else 'round_read_only'),
            verify_mode=lambda **kw:effect('sustained_normal' if kw['normal'] else 'sustained_read_only'))
        actor=SimpleNamespace(contract=self.contract,document=self.document,ops=self.ops,root=self.root,package=self.base/'package',
            runtime=object(),guard=lambda:effect('source'),source=lambda:effect('source'),
            native=lambda:self.schema,measure=lambda:(self.document,self.base),
            candidate=lambda:kernel,compensate=compensate,event=lambda phase,**kw:effect('event_'+phase),
            installation=SimpleNamespace(install=lambda:effect('boot_install'),installed=lambda:effect('boot_attested')))
        self.driver=m.CompletedNormalUpgrade(actor,artifact_guard=lambda:effect('artifacts'),model_loader=lambda:{},
            acceptance_guard=lambda **kw:effect('acceptance_'+str(kw['schema'])+'_'+str(kw['normal'])),rehearsal_guard=lambda:None)
        self.driver.preflight=lambda **kw:effect('preflight_locked' if kw.get('locked') else 'preflight')
        self.driver.root_credential=lambda:nullcontext()
        def install():self.driver.controller_installed=True;effect('controller_install')
        self.driver.install_controller=install
        def admit(*a):self.root.mkdir();effect('admit');return self.root
        test=self
        class Handoff:
            def __init__(self,*a,**kw):pass
            def fence_origin(self):test.origin='READ_ONLY';effect('fence_origin')
            def revoke(self):test.mode='READ_ONLY';effect('revoke')
            def grant(self,*,schema):
                if test.origin!='READ_ONLY' or test.owners!=1 or test.schema!=schema:raise AssertionError('unsafe_grant')
                test.mode='NORMAL';effect('grant_'+str(schema))
        class Backup:
            def __init__(self,*a,stage,**kw):self.stage=stage
            def capture(self):
                test.backup_count+=1;effect('backup_'+self.stage)
                if self.stage=='pre-migration' and (test.mode!='READ_ONLY' or test.schema!=115):raise AssertionError('unsafe_source_backup')
                if self.stage=='post-migration' and (test.mode!='NORMAL' or test.schema!=136):raise AssertionError('wrong_target_backup')
                return {'stage':self.stage,'schema':test.schema}
            def seal_migration_inputs(self,r):effect('backup_inputs')
            def guard(self):effect('backup_guard')
        def snapshot(*a,**kw):
            if test.mode!='READ_ONLY':raise AssertionError('customer_snapshot_under_positive_grant')
            effect('customer_snapshot_'+str(test.schema))
            return {'schema':test.schema,'columns':{'fixture':['original_column']}}
        def preservation(before,after):
            if before['schema']!=115 or after['schema']!=136:raise AssertionError('invalid_customer_comparison')
            effect('customer_preservation');return {'verified':True}
        for p in (patch.object(m.os,'geteuid',lambda:0),patch.object(m,'acquire_lock',lambda *a,**kw:os.open('/dev/null',os.O_RDONLY)),
                  patch('deployment.lib.completed_normal_baseline.seal_compatible_release',lambda *a:effect('seal_compatible_release')),
                  patch.object(m,'protected',lambda p,**kw:Path(p)),
                  patch.object(m,'publish_admission',admit),patch.object(m,'CompletedNormalWriteHandoff',Handoff),
                  patch.object(m,'CompletedNormalBackupContext',Backup),
                  patch.object(m,'migration_customer_snapshot',snapshot),
                  patch.object(m,'verify_migration_customer_preservation',preservation),
                  patch.object(m,'seal_candidate_stage',lambda *a,**kw:effect('seal_stage')),
                  patch.object(m,'seal_candidate_runtime',lambda *a,**kw:effect('seal_runtime')),
                  patch.object(m,'seal_intent',lambda *a,**kw:effect('seal_sql_intent')),
                  patch.object(m,'seal_completion',lambda contract,release,state,**kw:self.seal_completion(contract,release,state))):
            p.start();self.addCleanup(p.stop)

    def seal_completion(self,contract,release,state):
        self.assertEqual(release,state/'releases'/contract['candidate']['source_sha'])
        self.effect('seal_sql_completion')

    def test_moving_remote_main_rejects_without_fetch_or_production_effect(self):
        git=Mock(return_value=SimpleNamespace(stdout=self.driver.controller+'\trefs/heads/main\n'))
        self.ops.madar_git=git;self.driver.verify_candidate_remote()
        git.assert_called_once_with('completed_upgrade_candidate_remote','ls-remote','--exit-code','origin','refs/heads/main')
        for value in ('f'*40+'\trefs/heads/main\n',self.driver.controller+' refs/heads/other',self.driver.controller+' refs/heads/main extra',''):
            git.return_value=SimpleNamespace(stdout=value)
            with self.assertRaisesRegex(RuntimeError,'candidate_remote_changed'):self.driver.verify_candidate_remote()
        self.assertEqual(self.calls,[]);self.assertFalse(self.root.exists())

    def test_complete_order_has_fence_owner_read_only_backup_and_durable_sql_before_target_grant(self):
        result=self.driver.execute()
        ordered=['preflight','preflight_locked','quiesce','admit','boot_install','controller_install','release_lock',
            'service_prepare','seal_stage','fence_origin','service_activate','seal_runtime','service_publish',
            'acceptance_115_False','grant_115','service_adopt','acceptance_115_True','revoke','sustained_read_only',
            'backup_pre-migration','backup_inputs','customer_snapshot_115','seal_sql_intent','service_migrate',
            'customer_snapshot_136','customer_preservation','seal_sql_completion',
            'service_refresh','acceptance_136_False','grant_136','acceptance_136_True','backup_post-migration',
            'restore_timers','acceptance_136_True','event_normal_completed','clear_interlock']
        self.assertEqual([c for c in self.calls if c in ordered],ordered)
        self.assertEqual(result['mode'],'NORMAL');self.assertEqual(result['schema'],136)
        self.assertEqual(self.mode,'NORMAL');self.assertEqual(self.backup_count,2)
        self.assertTrue((self.root/'normal-completion.json').is_file())
    def test_source_or_resource_preflight_failure_has_no_effect_and_no_consumed_namespace(self):
        self.failure='preflight_locked'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.calls,['preflight','preflight_locked'])
        self.assertFalse(self.root.exists());self.assertEqual(self.origin,'NORMAL')
    def test_partial_quiesce_failure_rechecks_origin_before_exact_timer_restore(self):
        self.failure='quiesce'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.calls[-2:],['origin_rechecked','restore_timers'])
        self.assertNotIn('compensate',self.calls)
    def test_rejected_quiesce_without_durable_snapshot_preserves_original_error(self):
        self.failure='quiesce'
        self.ops.durable_quiesce_snapshot_exists=lambda sha:False
        with self.assertRaisesRegex(RuntimeError,'PRIVATE VALUE MUST NOT APPEAR'):
            self.driver.execute()
        self.assertNotIn('restore_timers',self.calls)
        self.assertNotIn('origin_rechecked',self.calls)
        self.assertEqual(self.origin,'NORMAL')
        self.assertFalse(self.root.exists())
    def test_post_install_failure_restricts_current_data_and_does_not_retry(self):
        self.failure='service_prepare'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.calls.count('service_prepare'),1)
        self.assertEqual(self.mode,'READ_ONLY');self.assertEqual(self.origin,'READ_ONLY')
        self.assertIn('requiesce_timers',self.calls)
        self.assertFalse((self.root/'normal-completion.json').exists())
        self.assertNotIn('PRIVATE VALUE', (self.root/'failure.json').read_text())
    def test_actual_write_boundary_failure_is_compensated_before_audit(self):
        self.failure='grant_115'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.mode,'READ_ONLY');self.assertNotIn('service_migrate',self.calls)
        self.assertEqual(self.calls.count('grant_115'),1)
    def test_backup_failure_after_target_writes_never_restores_customer_database_or_old_schema(self):
        self.failure='backup_post-migration'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.schema,136);self.assertEqual(self.mode,'READ_ONLY')
        self.assertEqual(self.owners,1);self.assertNotIn('restore_timers',self.calls)
        self.assertTrue(json.loads((self.root/'failure.json').read_text())['customer_database_restored'] is False)

    def test_unconverged_revocation_blocks_backup_and_sql_then_compensates(self):
        self.failure='sustained_read_only'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.mode,'READ_ONLY');self.assertEqual(self.schema,115)
        self.assertNotIn('backup_pre-migration',self.calls);self.assertNotIn('seal_sql_intent',self.calls)
        self.assertNotIn('service_migrate',self.calls);self.assertIn('compensate',self.calls)
    def test_failed_timer_restoration_fences_target_and_quiesces_partial_schedules(self):
        self.failure='restore_timers'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.schema,136);self.assertEqual(self.mode,'READ_ONLY')
        self.assertIn('requiesce_timers',self.calls)
    def test_customer_preservation_failure_blocks_target_write_grant_and_preserves_actual136(self):
        self.failure='customer_preservation'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual(self.schema,136);self.assertEqual(self.mode,'READ_ONLY')
        self.assertNotIn('seal_sql_completion',self.calls);self.assertNotIn('grant_136',self.calls)
        self.assertTrue((self.root/'pre-migration-customer-snapshot.json').is_file())
    def test_unavailable_failure_audit_does_not_skip_compensation(self):
        self.failure='service_activate';original=m.exclusive
        def fail_audit(path,body):
            if Path(path).name=='failure.json':raise OSError('fixture_disk_full')
            return original(path,body)
        with patch.object(m,'exclusive',fail_audit):
            with self.assertRaises(OSError):self.driver.execute()
        self.assertEqual(self.mode,'READ_ONLY');self.assertIn('requiesce_timers',self.calls)

if __name__=='__main__':unittest.main()
