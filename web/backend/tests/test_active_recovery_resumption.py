"""Synthetic protocol tests; these fixtures are never production evidence."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.provider_recovery_runtime import digest
from deployment.lib.active_recovery_inputs import KEYS
from deployment.lib.active_recovery_resumption import ResumptionPlan,ActiveRecoveryResumption,load_saved_resumption_plan

class Operations:
    def __init__(self):self.calls=[];self.fail=None;self.compensation_fail=False
    def __getattr__(self,name):
        def method(*args,**kwargs):
            self.calls.append(name)
            if name=='exclusive_private_namespace':args[0].mkdir(parents=True,mode=0o700)
            if name=='require_unused_attempt':
                events=[json.loads(line) for line in (args[0]/'events.jsonl').read_text().splitlines()]
                if len(events)!=1 or events[0]['phase']!='authorized':raise RuntimeError('attempt_already_used')
            if name==self.fail:raise RuntimeError('fixture_failure')
            if name=='capture_verified_runtime_dependencies':return {'runtimes':{},'networks':{}}
            if name=='publish_verified_current_data_fallback' and self.compensation_fail:raise RuntimeError('fixture_compensation_failure')
        return method
    def upgrade_lock(self):return self
    def deploy_lock(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):return False

class ActiveRecoveryResumptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.addCleanup(patch.stopall)
        patch('deployment.lib.active_recovery_resumption.ROOT',self.root).start()
        patch('deployment.lib.active_recovery_resumption.os.geteuid',return_value=0).start()
        patch('deployment.lib.active_recovery_resumption.protected',side_effect=lambda p,**kw:p).start()
        identity={'container_id':'b'*64,'image_id':'sha256:'+'c'*64,'spec_sha256':'d'*64}
        keys=KEYS
        self.plan=ResumptionPlan('a'*40,'b'*64,{'backend':'sha256:'+'c'*64,'frontend':'sha256:'+'d'*64},
            {key:'e'*64 for key in keys},{'backend':identity,'frontend':identity},'f'*64,'1'*64,'2'*64,'3'*64,'4'*64)
        bindings=dict(self.plan.retained_inputs);bindings['runtime_dependencies']=digest({'runtimes':{},'networks':{}})
        self.plan=replace(self.plan,retained_inputs=bindings)
        self.ops=Operations();self.tx=ActiveRecoveryResumption(self.plan,self.ops)
    def authorize(self):self.tx.authorize(approved_plan=self.plan.digest,approved_source=self.plan.source_bundle_sha256)
    def test_fresh_approval_and_actual_evidence_before_any_effect(self):
        with self.assertRaisesRegex(RuntimeError,'explicit_approval'):self.tx.authorize(approved_plan='0'*64,approved_source='b'*64)
        self.assertEqual(self.ops.calls,[]);self.assertFalse(self.tx.root.exists())
        self.ops.fail='verify_actual_execution_evidence'
        with self.assertRaises(RuntimeError):self.authorize()
        self.assertFalse(self.tx.root.exists())
    def test_no_run_credential_needed_and_no_receipt_replacement(self):
        self.authorize();data=self.tx.authorization.read_bytes()
        with self.assertRaises(FileExistsError):self.authorize()
        self.assertEqual(self.tx.authorization.read_bytes(),data)
        self.assertNotIn('legacy_authorize',self.ops.calls)
    def test_handoff_before_controller_and_standby_before_grant(self):
        self.authorize();self.assertEqual(self.tx.execute()['phase'],'normal');calls=self.ops.calls
        self.assertLess(calls.index('require_sustained_read_only_serving'),calls.index('install_and_attest_governed_controller'))
        self.assertLess(calls.index('verify_standby_workers'),calls.index('commit_normal_release_and_grant_writes'))
        events=[json.loads(line) for line in self.tx.journal.read_text().splitlines()]
        self.assertIn('write_grant_pending',[e['phase'] for e in events]);self.assertEqual(events[-1]['phase'],'normal')
        with self.assertRaisesRegex(RuntimeError,'attempt_already_used'):self.tx.execute()
    def test_changed_identity_or_unhealthy_fallback_denied_before_mutation(self):
        for stage in ['verify_active_rollback_inputs','verify_emergency_installation','verify_restricted_fallback','require_all_consumers_stopped','require_no_normal_write_authority']:
            self.ops.fail=stage
            with self.subTest(stage=stage),self.assertRaises(RuntimeError):self.authorize()
            self.assertFalse(self.tx.root.exists())
    def test_post_handoff_failure_fences_before_current_data_compensation(self):
        self.authorize();self.ops.fail='install_and_attest_governed_controller'
        with self.assertRaises(RuntimeError):self.tx.execute()
        calls=self.ops.calls
        self.assertLess(calls.index('fence_normal_writes_and_stop_consumers'),calls.index('publish_verified_current_data_fallback'))
        self.assertEqual(self.tx.phase,'restricted_fallback');self.assertNotIn('commit_normal_release_and_grant_writes',calls)
    def test_failure_after_grant_preserves_current_data(self):
        self.authorize();self.ops.fail='capture_replicate_and_verify_post_cutover_backup'
        with self.assertRaises(RuntimeError):self.tx.execute()
        self.assertIn('commit_normal_release_and_grant_writes',self.ops.calls)
        self.assertIn('publish_verified_current_data_fallback',self.ops.calls)
        self.assertNotIn('restore_database',self.ops.calls)
    def test_failed_compensation_uses_maintenance(self):
        self.authorize();self.ops.fail='publish_read_only_handoff';self.ops.compensation_fail=True
        with self.assertRaises(RuntimeError):self.tx.execute()
        self.assertIn('activate_maintenance_or_stop_proxy',self.ops.calls);self.assertEqual(self.tx.phase,'compensation_failed')
    def test_scope_migration_and_source_binding_changes_rejected(self):
        for key,value in [('schema',116),('restore_customer_database',True),('migration_policy','automatic'),('source_sha','bad'),('candidate_images',{}),('convergence_seconds',0)]:
            with self.subTest(key=key),self.assertRaises(RuntimeError):replace(self.plan,**{key:value}).validate()

    def test_failed_detached_staging_consumes_attempt_and_preserves_public_route(self):
        self.authorize();self.ops.fail='stage_detached_read_only_candidate'
        with self.assertRaises(RuntimeError):self.tx.execute()
        self.assertEqual(self.tx.phase,'detached_candidate_failed')
        self.assertNotIn('publish_read_only_handoff',self.ops.calls)
        self.assertNotIn('publish_verified_current_data_fallback',self.ops.calls)
        self.ops.fail=None
        with self.assertRaisesRegex(RuntimeError,'attempt_already_used'):self.tx.execute()

    def test_append_journal_is_private_even_with_permissive_umask(self):
        previous=os.umask(0o022)
        try:self.authorize()
        finally:os.umask(previous)
        self.assertEqual(self.tx.journal.stat().st_mode&0o777,0o600)
        self.assertEqual((self.tx.root/'plan.json').stat().st_mode&0o777,0o600)
        self.assertEqual((self.tx.root/'runtime-dependencies.json').stat().st_mode&0o777,0o600)
    def test_saved_plan_or_dependency_change_prevents_staging(self):
        self.authorize()
        for name in ('plan.json','runtime-dependencies.json'):
            path=self.tx.root/name;previous=path.read_bytes();path.write_text('{}')
            with self.subTest(name=name),self.assertRaises(RuntimeError):self.tx.execute()
            self.assertNotIn('stage_detached_read_only_candidate',self.ops.calls)
            path.write_bytes(previous)

    def test_compensation_preparation_failure_preserves_public_and_consumes_attempt(self):
        self.authorize();self.ops.fail='prepare_current_data_compensation'
        with self.assertRaises(RuntimeError):self.tx.execute()
        self.assertEqual(self.tx.phase,'compensation_preparation_failed')
        self.assertNotIn('publish_read_only_handoff',self.ops.calls)
        self.assertNotIn('install_and_attest_governed_controller',self.ops.calls)
        self.ops.fail=None
        with self.assertRaisesRegex(RuntimeError,'attempt_already_used'):self.tx.execute()
    def test_backup_timers_restore_only_after_verified_post_cutover_backup(self):
        self.authorize();self.tx.execute()
        calls=self.ops.calls
        self.assertLess(calls.index('capture_replicate_and_verify_post_cutover_backup'),calls.index('restore_configured_backup_timers'))
    def test_failed_timer_restoration_compensates_current_data(self):
        self.authorize();self.ops.fail='restore_configured_backup_timers'
        with self.assertRaises(RuntimeError):self.tx.execute()
        self.assertEqual(self.tx.phase,'restricted_fallback')
        self.assertIn('fence_normal_writes_and_stop_consumers',self.ops.calls)
        self.assertNotIn('restore_database',self.ops.calls)

    def test_changed_plan_formatting_cannot_reuse_exact_operator_approval(self):
        self.authorize();path=self.tx.root/'plan.json';old=json.loads(path.read_text())
        self.assertEqual(__import__('hashlib').sha256(path.read_bytes()).hexdigest(),self.plan.digest)
        path.write_text(json.dumps(old,sort_keys=True,indent=2))
        with self.assertRaisesRegex(RuntimeError,'sealed_plan_bytes_changed'):self.tx.execute()
        self.assertNotIn('stage_detached_read_only_candidate',self.ops.calls)

    def test_listener_and_boot_plan_loader_require_exact_saved_bytes(self):
        self.authorize();self.assertEqual(load_saved_resumption_plan(self.tx.root),self.plan)
        path=self.tx.root/'plan.json';path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(RuntimeError,'saved_plan_bytes_changed'):load_saved_resumption_plan(self.tx.root)
