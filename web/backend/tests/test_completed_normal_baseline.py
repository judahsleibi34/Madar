import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_baseline as m

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
        self.state={'active_slot':'blue','known_good_release':{'slot':'blue','sha':self.app,'images':self.plan.candidate_images,'provider':'local','schema':115,'schema_compatible_min':115,'schema_compatible_max':115},'in_progress_release':None,'rollback_failure':None}
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

if __name__=='__main__':unittest.main()
