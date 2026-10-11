"""Root-boundary regression tests, with fixture-only authorization adapters.

These exercise actual atomic grant/preimage/publication writes. Independent
live guards and the complete deployment rehearsal remain separate gates.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_write_handoff as m
from deployment.lib import completed_normal_admission as admission
from deployment.lib.emergency_routing_repair import spec
from test_completed_normal_admission import fixture_contract
from test_compatible_normal_boot import Clock

class Kernel:
    publication_name='candidate-runtime.json'
    def __init__(self,contract,root):
        self.contract,self.root=contract,root;self.calls=[];self.mode='READ_ONLY';self.schema=115
        self.runtime=self;self.denials=[];self.inspection={};self.fail_round=False;self.fail_start=False
    def budget(self,n):return n
    def native_verifier(self):return self.schema
    def round(self,*,normal):
        self.calls.append(('round',normal))
        if self.fail_round and normal:raise RuntimeError('injected_integrity_failure')
    def compensate_current_data(self):self.calls.append(('compensate_without_database_restore',))
    def inspect(self,names):return {n:self.inspection[n] for n in names if n in self.inspection}
    def json_http(self,url):
        if url.endswith('/health/version'):
            return {'release_sha':'a'*40,'release_slot':'blue','schema_compatible_min':115,'schema_compatible_max':115}
        return {'restricted':False,'business_writes_enabled':True}
    def denied(self,url):self.denials.append(url)

class CompletedNormalWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name);self.contract=fixture_contract();self.root=self.path/admission.digest(self.contract)
        self.root.mkdir();(self.root/'write-authority').mkdir()
        self.original=self.path/'original';(self.original/'write-authority').mkdir(parents=True)
        self.grant_path=self.root/'write-authority/authority.json'
        self.old_path=self.original/'write-authority/authority.json'
        self.candidate={'version':2,'schema':115,'release_sha':'c'*40,'contract_digest':admission.digest(self.contract),
            'compatible_min':115,'compatible_max':136,'mode':'READ_ONLY'}
        self.old={'version':1,'schema':115,'release_sha':'a'*40,'contract_digest':'3'*64,'mode':'READ_ONLY'}
        self.grant_path.write_bytes(admission.encoded(self.candidate));self.old_path.write_bytes(admission.encoded(self.old))
        (self.root/'admission.json').write_bytes(admission.encoded({'operation':admission.OPERATION,'contract':self.contract}))
        (self.root/'candidate-runtime.json').write_bytes(admission.encoded({'real_fixture_runtime':'unit-only'}))
        self.kernel=Kernel(self.contract,self.root);self.guards=[]
        self.boundary=m.CompletedNormalWriteHandoff(self.contract,self.kernel,source_guard=lambda:self.guards.append('source'),
            boot_guard=lambda:self.guards.append('boot'),artifact_guard=lambda:self.guards.append('artifacts'),
            admissions=self.path,state_root=self.path)
        self.clock=Clock()
        def path_adapter(path,**kwargs):
            path=Path(path);old=Path(self.contract['source_roles']['completion_root'])
            return self.original/path.relative_to(old) if path.is_relative_to(old) else path
        atomic=m.atomic_public_authority
        for p in (patch.object(m,'protected',path_adapter),
            patch('deployment.lib.provider_recovery_runtime.protected',path_adapter),
            patch.object(m.os,'geteuid',return_value=0),
            patch.object(m,'require_fresh_authorization',lambda c:self.guards.append('fresh_authorization')),
            patch.object(m,'verify_history',lambda c:self.guards.append('original_history')),
            patch.object(m,'atomic_public_authority',lambda path,value:atomic(path_adapter(path),value)),
            patch.object(m.time,'monotonic',self.clock.monotonic),patch.object(m.time,'sleep',self.clock.sleep)):
            p.start();self.addCleanup(p.stop)
    def grant(self):return json.loads(self.grant_path.read_text())
    def test_actual_atomic_grant_requires_sustained_rounds_and_seals_real_preimage(self):
        original=self.grant_path.read_bytes();result=self.boundary.grant()
        self.assertEqual(result['mode'],'NORMAL');self.assertFalse(result['customer_database_restored'])
        self.assertEqual(self.grant()['mode'],'NORMAL');self.assertEqual(self.grant_path.stat().st_mode&0o777,0o644)
        self.assertEqual((self.root/'pre-grant-authority.json').read_bytes(),original)
        self.assertEqual((self.root/'normal-publication.json').read_bytes(),(self.root/'candidate-runtime.json').read_bytes())
        self.assertGreaterEqual(self.clock.value,5)
        self.assertGreaterEqual(self.guards.count('fresh_authorization'),2)
        with self.assertRaisesRegex(RuntimeError,'candidate_authority_changed'):self.boundary.grant()
        self.boundary.revoke()
        with self.assertRaises(FileExistsError):self.boundary.grant()
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
        self.assertEqual((self.root/'pre-grant-authority.json').read_bytes(),original)
    def test_changed_boot_artifact_source_or_database_cannot_grant(self):
        def reject():raise RuntimeError('independent_guard_failed')
        for name in ('boot_guard','artifact_guard','source_guard'):
            original=getattr(self.boundary,name);setattr(self.boundary,name,reject)
            with self.assertRaisesRegex(RuntimeError,'guard_failed'):self.boundary.grant()
            self.assertEqual(self.grant()['mode'],'READ_ONLY');setattr(self.boundary,name,original)
        self.kernel.schema=116
        with self.assertRaisesRegex(RuntimeError,'source_schema_changed'):self.boundary.grant()
        self.assertFalse((self.root/'write-boundary.json').exists())
    def test_origin_must_be_fenced_before_candidate_positive_grant(self):
        self.old_path.write_bytes(admission.encoded(dict(self.old,mode='NORMAL')))
        with self.assertRaisesRegex(RuntimeError,'origin_not_fenced'):self.boundary.grant()
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
    def test_integrity_failure_revokes_before_compensation_without_restore(self):
        self.kernel.fail_round=True
        with self.assertRaisesRegex(RuntimeError,'integrity_failure'):self.boundary.grant()
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
        self.assertIn(('compensate_without_database_restore',),self.kernel.calls)
        self.assertTrue((self.root/'write-boundary.json').exists())
        self.assertFalse((self.root/'normal-publication.json').exists())
        self.assertEqual(json.loads(self.old_path.read_text())['mode'],'READ_ONLY')
    def test_failure_publishing_receipt_revokes_positive_authority(self):
        original=m.exclusive
        def fail(path,data):
            if path.name=='normal-publication.json':raise OSError('injected_private_publication_failure')
            original(path,data)
        with patch.object(m,'exclusive',side_effect=fail):
            with self.assertRaises(OSError):self.boundary.grant()
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
        self.assertIn(('compensate_without_database_restore',),self.kernel.calls)
    def test_target_grant_requires_actual_completed_migrations_and_preserves_initial_publication(self):
        self.boundary.grant();original=(self.root/'normal-publication.json').read_bytes()
        self.boundary.revoke();self.kernel.schema=136
        with patch('deployment.lib.completed_normal_database.require_normal_migration_boundary',
                side_effect=RuntimeError('compatible_boot_migration_forward_repair_required')):
            with self.assertRaisesRegex(RuntimeError,'forward_repair_required'):self.boundary.grant(schema=136)
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
        self.assertFalse((self.root/'pre-grant-authority-136.json').exists())
        with patch('deployment.lib.completed_normal_database.require_normal_migration_boundary') as guard:
            result=self.boundary.grant(schema=136)
        self.assertEqual(result['schema'],136);self.assertEqual(self.grant()['schema'],136)
        self.assertGreaterEqual(guard.call_count,3)
        self.assertEqual((self.root/'normal-publication.json').read_bytes(),original)
        self.assertTrue((self.root/'target-normal-publication.json').is_file())
        self.boundary.revoke()
        with patch('deployment.lib.completed_normal_database.require_normal_migration_boundary'):
            with self.assertRaises(FileExistsError):self.boundary.grant(schema=136)
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
    def test_partial_schema_cannot_obtain_target_grant(self):
        for schema in (116,119,135):
            self.kernel.schema=schema
            with self.assertRaisesRegex(RuntimeError,'source_schema_changed'):self.boundary.grant(schema=136)
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
    def test_origin_grant_digest_is_original_runtime_context_not_old_plan_hash(self):
        binding={'plan_sha256':'a'*64,'source_sha':'a'*40,'runtimes':{}}
        for kind in ('backend','frontend','parser','notification','calendar-sync','data-deletion'):
            row={'Id':kind,'Image':'sha256:'+'1'*64,'Config':{},'HostConfig':{},'Mounts':[],'State':{'Running':True}}
            self.kernel.inspection[kind]=row
            binding['runtimes'][kind]={'id':kind,'image':row['Image'],'spec_sha256':spec(row)}
        (self.original/'candidate-identities.json').write_bytes(admission.encoded(binding))
        self.old_path.write_bytes(admission.encoded(dict(self.old,mode='NORMAL')))
        self.boundary.fence_origin()
        self.assertEqual(json.loads(self.old_path.read_text())['mode'],'READ_ONLY')
        preimage=json.loads((self.root/'origin-grant-preimage.json').read_text())
        self.assertEqual(preimage['contract_digest'],'3'*64)
        self.assertNotEqual(preimage['contract_digest'],self.contract['source_roles']['original_plan_sha256'])
        self.assertEqual(len(self.kernel.denials),1)

if __name__=='__main__':unittest.main()
