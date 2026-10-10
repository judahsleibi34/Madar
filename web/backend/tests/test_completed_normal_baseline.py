import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_baseline as m
from deployment.lib.control_plane_upgrade import SystemOperations, UpgradeError, CommandResult

class CompletedNormalBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/('a'*64);self.root.mkdir()
        self.app='d'*40;self.controller='c'*40;self.bundle='b'*64
        self.plan=SimpleNamespace(digest=self.root.name,source_sha=self.app,controller_source_sha=self.controller,
            source_bundle_sha256=self.bundle,candidate_images={'backend':'sha256:'+'1'*64,'frontend':'sha256:'+'2'*64},candidate_destination={'slot':'blue'})
        self.inputs={k:self.base/k for k in ('controller','production_configuration','backup_configuration','release_state','traffic')}
        self.inputs['controller'].write_text(self.controller)
        self.library=self.base/'lib';self.library.mkdir();self.code=self.library/'fixture.py';self.code.write_text('immutable')
        self.state={'active_slot':'blue','known_good_release':{'slot':'blue','sha':self.app,'images':self.plan.candidate_images,'provider':'local','schema':115,'schema_compatible_min':115,'schema_compatible_max':115,'runtime_only_rollback':True,'migration_policy':'none'},'in_progress_release':None,'rollback_failure':None}
        self.write('authorization.json',{'operation':'active-local-rollback-resumption','plan_sha256':self.root.name,'source_bundle_sha256':self.bundle})
        self.write('events.jsonl',None,body=json.dumps({'phase':'normal','plan_sha256':self.root.name})+'\n')
        required={'normal-acceptance.json','post-cutover-backup.json','installed-controller.json','worker-owner.json','normal-publication.json'}
        for name in required:self.write(name,{})
        outputs={}
        for key in ('production_configuration','backup_configuration','release_state','traffic'):
            self.inputs[key].write_text('{}');outputs[key]=self.sha(self.inputs[key])
        self.write('normal-publication.json',{'published_sha256':outputs})
        self.completion={'operation':'completed-normal-local-continuation','plan_sha256':self.root.name,'source_sha':self.app,'source_bundle_sha256':self.bundle,'schema':115,'images':self.plan.candidate_images,'database_restore_performed':False,'retained_execution_files':{name:self.sha(self.root/name) for name in required}}
        self.write('normal-completion.json',self.completion)
        for name,value in [('ROOT',self.base),('INPUTS',self.inputs),('load_saved_resumption_plan',lambda root:self.plan),('protected',lambda path,**kw:path),('readonly_configuration',lambda path,**kw:path),('historical_source',lambda plan:{'files':{'web/deployment/lib/fixture.py':self.sha(self.code)}})]:
            p=patch.object(m,name,value);p.start();self.addCleanup(p.stop)
    def sha(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def write(self,name,value,*,body=None):(self.root/name).write_text(body if body is not None else json.dumps(value))
    def call(self):return m.attest_split(self.state,self.root,self.controller,self.controller)
    def test_measured_controller_and_application_roles_remain_distinct(self):
        result=self.call();self.assertEqual(result['application_sha'],self.app);self.assertEqual(result['controller_sha'],self.controller)
        self.assertNotEqual(result['application_sha'],result['controller_sha'])
    def test_forged_matching_sha_is_rejected(self):
        self.state['known_good_release']['sha']=self.controller
        with self.assertRaisesRegex(RuntimeError,'release_role_changed'):self.call()
    def test_installed_source_revision_or_bytes_changed(self):
        with self.assertRaisesRegex(RuntimeError,'controller_role_changed'):m.attest_split(self.state,self.root,self.controller,'e'*40)
        self.inputs['controller'].write_text('e'*40)
        with self.assertRaisesRegex(RuntimeError,'provenance_changed'):self.call()
    def test_changed_completed_receipt_is_rejected(self):
        self.write('normal-acceptance.json',{'altered':True})
        with self.assertRaisesRegex(RuntimeError,'execution_bytes_changed'):self.call()
    def test_compensated_or_incomplete_normal_cannot_be_reinterpreted(self):
        self.write('events.jsonl',None,body=json.dumps({'phase':'restricted_fallback','plan_sha256':self.root.name})+'\n')
        with self.assertRaisesRegex(RuntimeError,'execution_changed'):self.call()
    def test_source_schema_and_publication_are_binding(self):
        self.state['known_good_release']['schema']=136
        with self.assertRaisesRegex(RuntimeError,'release_role_changed'):self.call()
        self.state['known_good_release']['schema']=115;self.inputs['backup_configuration'].write_text('altered')
        with self.assertRaisesRegex(RuntimeError,'publication_changed'):self.call()
    def test_unknown_execution_files_fail_closed(self):
        self.completion['retained_execution_files']['unbound.json']='0'*64;self.write('normal-completion.json',self.completion)
        with self.assertRaisesRegex(RuntimeError,'execution_incomplete'):self.call()

    def operations(self):
        operations=object.__new__(SystemOperations)
        operations.state_root=self.base
        operations.repository_head=lambda:self.controller
        operations.installed_sha=lambda:self.controller
        authority=self.root/'write-authority';authority.mkdir()
        (authority/'authority.json').write_text(json.dumps({'mode':'NORMAL','release_sha':self.app,'schema':115}))
        container=[{'Mounts':[{'Destination':'/run/madar/business-write-authority',
            'Type':'bind','RW':False,'Source':str(authority)}]}]
        operations.command=lambda *args,**kwargs:CommandResult(json.dumps(container),'',0)
        self.inputs['release_state']=self.base/'state.json'
        self.inputs['release_state'].write_text(json.dumps(self.state))
        publication=json.loads((self.root/'normal-publication.json').read_text())
        publication['published_sha256']['release_state']=self.sha(self.inputs['release_state'])
        self.write('normal-publication.json',publication)
        self.completion['retained_execution_files']['normal-publication.json']=self.sha(self.root/'normal-publication.json')
        self.write('normal-completion.json',self.completion)
        return operations

    def test_completed_normal_terminal_uses_real_receipts_without_creating_release(self):
        operations=self.operations()
        self.assertEqual(operations.migration_terminal(self.app,115),'not_requested')
        self.assertEqual(operations.migration_origin_state(self.app,115,115),'not_requested')
        self.assertFalse((self.base/'releases').exists())
        self.assertEqual(self.call()['controller_sha'],self.controller)

    def test_completed_normal_terminal_rejects_changed_execution(self):
        operations=self.operations();self.write('normal-acceptance.json',{'altered':True})
        with self.assertRaisesRegex(UpgradeError,'completed_normal_migration_contract_invalid'):
            operations.migration_terminal(self.app,115)

    def test_completed_normal_terminal_requires_positive_authority(self):
        operations=self.operations()
        (self.root/'write-authority/authority.json').write_text(json.dumps({'mode':'READ_ONLY','release_sha':self.app,'schema':115}))
        with self.assertRaisesRegex(UpgradeError,'completed_normal_migration_contract_invalid'):
            operations.migration_terminal(self.app,115)

    def test_completed_normal_terminal_rejects_schema_advancement(self):
        operations=self.operations()
        with self.assertRaisesRegex(UpgradeError,'completed_normal_migration_contract_invalid'):
            operations.migration_terminal(self.app,116)
        with self.assertRaisesRegex(UpgradeError,'migration_terminal_schema_mismatch'):
            operations.migration_origin_state(self.app,115,116)

    def test_completed_normal_terminal_rejects_conflicting_migration_history(self):
        operations=self.operations();(self.base/'migrations'/self.app).mkdir(parents=True)
        with self.assertRaisesRegex(UpgradeError,'completed_normal_migration_state_conflict'):
            operations.migration_terminal(self.app,115)

    def test_missing_ordinary_contract_still_fails(self):
        operations=self.operations()
        self.state['known_good_release'].pop('runtime_only_rollback')
        self.inputs['release_state'].write_text(json.dumps(self.state))
        with self.assertRaisesRegex(UpgradeError,'known_good_release_contract_missing'):
            operations.migration_terminal(self.app,115)

    def test_changed_migration_policy_cannot_be_classified_as_no_sql(self):
        operations=self.operations()
        self.state['known_good_release']['migration_policy']='automatic-after-known-good-backup-first-forward-repair'
        self.inputs['release_state'].write_text(json.dumps(self.state))
        with self.assertRaisesRegex(UpgradeError,'completed_normal_migration_contract_invalid'):
            operations.migration_terminal(self.app,115)

    def test_isolated_bootstrap_can_import_measured_completed_attestor(self):
        code="import runpy,sys;runpy.run_path(sys.argv[1],run_name='fixture');from deployment.lib.completed_normal_baseline import discover_split"
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(WEB/'deployment/lib/control_plane_upgrade.py')],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_completed_runtime_reuses_exact_continuation_verification(self):
        operations=self.operations()
        with patch('deployment.lib.active_recovery_boot_actor.ActiveRecoveryBootActor') as actor:
            result=m.attest_runtime(operations,self.state)
        actor.return_value.assemble.assert_called_once_with()
        actor.return_value.completed_evidence.assert_called_once_with()
        actor.return_value.kernel.normal.assert_called_once_with()
        self.assertEqual(result['application_sha'],self.app)

    def test_continuation_image_attestation_does_not_fabricate_worker_reference(self):
        operations=self.operations()
        with patch.object(m,'attest_runtime',return_value=self.call()) as verify:
            operations.attest_active_images('blue',self.state['known_good_release'])
        verify.assert_called_once_with(operations,self.state)
        self.assertNotIn('worker',self.state['known_good_release']['images'])
        with self.assertRaisesRegex(UpgradeError,'completed_normal_runtime_contract_invalid'):
            operations.attest_active_images('blue',self.state['known_good_release'],allow_refreshable_workers=True)

    def test_changed_runtime_identity_is_not_accepted(self):
        operations=self.operations()
        with patch.object(m,'attest_runtime',side_effect=RuntimeError('active_runtime_identity_changed')):
            with self.assertRaisesRegex(UpgradeError,'completed_normal_runtime_contract_invalid'):
                operations.attest_active_images('blue',self.state['known_good_release'])

if __name__=='__main__':unittest.main()
