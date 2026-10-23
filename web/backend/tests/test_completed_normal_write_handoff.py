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
    def test_fresh_grant_uses_its_own_receipt_and_cannot_replay_an_old_boundary(self):
        import hashlib
        self.boundary.grant();self.boundary.revoke();self.kernel.schema=136
        with patch('deployment.lib.completed_normal_database.require_normal_migration_boundary'):
            self.boundary.grant(schema=136)
        historical={name:(self.root/name).read_bytes() for name in ('pre-grant-authority-136.json','write-boundary-136.json','normal-publication.json','target-normal-publication.json')}
        self.boundary.revoke()
        plan={'operation':'unit-backup-completion','source_sha256':'f'*64,'parent_context_sha256':self.root.name,
            'target_schema':136,'migrations':[],'restore_old_customer_database':False,'automatic_retry':False}
        h=admission.digest(plan);scope=self.root/'continuations'/h;scope.mkdir(parents=True)
        (scope/'plan.json').write_bytes(admission.encoded(plan))
        (scope/'operator-authorization.json').write_bytes(admission.encoded({
            'operation':plan['operation'],'plan_sha256':h,'source_sha256':'f'*64,
            'parent_context_sha256':self.root.name,'historical_authorization_reused':False}))
        witness={'operation':plan['operation'],'plan_sha256':h,'source_sha256':'f'*64,
            'parent_context_sha256':self.root.name,'application_sha':self.contract['candidate']['source_sha']}
        with patch.object(admission,'credential_witness',return_value=dict(witness,application_sha='e'*40)),                 patch('deployment.lib.completed_normal_database.require_normal_migration_boundary'):
            with self.assertRaisesRegex(RuntimeError,'fresh_grant_scope_invalid'):
                self.boundary.grant(schema=136,fresh_attempt_root=scope)
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
        with patch.object(admission,'credential_witness',return_value=witness),                 patch('deployment.lib.completed_normal_database.require_normal_migration_boundary'):
            self.boundary.grant(schema=136,fresh_attempt_root=scope)
            self.assertEqual(self.grant()['mode'],'NORMAL');self.boundary.revoke()
            with self.assertRaises(FileExistsError):self.boundary.grant(schema=136,fresh_attempt_root=scope)
        self.assertEqual(self.grant()['mode'],'READ_ONLY')
        self.assertTrue((scope/'target-normal-publication.json').exists())
        for name,body in historical.items():self.assertEqual((self.root/name).read_bytes(),body)

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

class MaintenancePrivateWriteTests(unittest.TestCase):
    """Real root grant/preimage writes, explicitly modeled live observations."""
    def setUp(self):
        CompletedNormalWriteTests.setUp(self)
        from test_schema160_release import reconciled_contract
        from deployment.lib.completed_normal_profile import RECONCILED
        from deployment.lib.schema150_provider_adapter import Schema150ProviderAdapter
        self.contract=reconciled_contract()
        previous=self.root;self.root=self.path/admission.digest(self.contract)
        previous.rename(self.root)
        self.grant_path=self.root/'write-authority/authority.json'
        self.candidate={'version':3,'schema':146,'release_sha':self.contract['candidate']['source_sha'],
            'contract_digest':admission.digest(self.contract),'mode':'READ_ONLY','compatible_min':146,'compatible_max':160,
            'operation':RECONCILED.operation,'origin_schema':146,'controller_sha':self.contract['candidate']['controller_sha'],
            'migration_manifest_sha256':self.contract['migration_manifest_sha256']}
        self.grant_path.write_bytes(admission.encoded(self.candidate))
        from deployment.lib.completed_normal_profile import expected_origin_grant
        patches=(patch.object(m,'profile',return_value=RECONCILED),
                 patch.object(admission,'profile',return_value=RECONCILED),
                 patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED),
                 patch('deployment.lib.completed_normal_database.require_normal_migration_boundary'))
        for p in patches:p.start();self.addCleanup(p.stop)
        self.old_path.write_bytes(admission.encoded(expected_origin_grant(self.contract,'READ_ONLY')))
        (self.root/'admission.json').write_bytes(admission.encoded({'operation':RECONCILED.operation,'contract':self.contract}))
        (self.root/'candidate-runtime.json').unlink()
        self.kernel=Kernel(self.contract,self.root);self.kernel.schema=160
        self.kernel.round=lambda **kw:(_ for _ in ()).throw(AssertionError('historical running kernel used'))
        self.provider=Schema150ProviderAdapter.__new__(Schema150ProviderAdapter)
        self.provider.contract=self.contract;self.provider.root=self.root;self.provider.runtime=self.kernel.runtime
        def private_round(*,normal):
            value=json.loads(self.grant_path.read_text())
            self.assertEqual(value['mode'],'NORMAL' if normal else 'READ_ONLY')
            return {'operation':RECONCILED.operation,'context_sha256':admission.digest(self.contract),
                'schema':160,'mode':value['mode'],'candidate_stage_sha256':'a'*64,'provider_journal_sha256':'b'*64,
                'write_authority_sha256':admission.digest(value),'workers_started':False,'ingress_restored':False}
        from unittest.mock import Mock
        self.provider.verify_private_handoff=Mock(side_effect=private_round)
        self.private_observation=private_round
        self.boundary=m.CompletedNormalWriteHandoff(self.contract,self.kernel,source_guard=lambda:None,
            boot_guard=lambda:None,artifact_guard=lambda:None,admissions=self.path,state_root=self.path,
            provider_adapter=self.provider)

    def test_actual_private_grant_does_not_claim_running_or_public_acceptance(self):
        result=self.boundary.grant(schema=160)
        self.assertEqual(json.loads(self.grant_path.read_text())['mode'],'NORMAL')
        self.assertFalse(result['workers_started']);self.assertFalse(result['ingress_restored'])
        self.assertGreaterEqual(self.clock.value,5)
        receipt=json.loads((self.root/'maintenance-write-handoff.json').read_text())
        self.assertEqual(receipt['schema'],160)
        self.assertEqual(receipt['write_authority_sha256'],admission.digest(json.loads(self.grant_path.read_text())))
        self.assertTrue((self.root/'write-boundary-160.json').exists())
        for name in ('candidate-runtime.json','normal-publication.json','target-normal-publication.json'):
            self.assertFalse((self.root/name).exists())
        self.boundary.revoke()
        with self.assertRaises(FileExistsError):self.boundary.grant(schema=160)

    def test_failed_private_acceptance_never_grants_and_lost_publication_revokes(self):
        self.provider.verify_private_handoff.side_effect=RuntimeError('private_acceptance_failed')
        with self.assertRaisesRegex(RuntimeError,'private_acceptance_failed'):self.boundary.grant(schema=160)
        self.assertEqual(json.loads(self.grant_path.read_text())['mode'],'READ_ONLY')
        self.assertFalse((self.root/'write-boundary-160.json').exists())
        self.provider.verify_private_handoff.side_effect=self.private_observation
        original=m.exclusive
        def fail(path,data):
            if path.name=='maintenance-write-handoff.json':raise OSError('synthetic_receipt_failure')
            original(path,data)
        with patch.object(m,'exclusive',side_effect=fail),self.assertRaises(OSError):self.boundary.grant(schema=160)
        self.assertEqual(json.loads(self.grant_path.read_text())['mode'],'READ_ONLY')
        self.assertIn(('compensate_without_database_restore',),self.kernel.calls)

    def test_status_packet_and_old_continuation_cannot_replace_private_observation(self):
        self.provider.verify_private_handoff.side_effect=None
        self.provider.verify_private_handoff.return_value={'approved':True}
        with self.assertRaisesRegex(RuntimeError,'private_observation_invalid'):self.boundary.grant(schema=160)
        self.assertEqual(json.loads(self.grant_path.read_text())['mode'],'READ_ONLY')
        with self.assertRaisesRegex(RuntimeError,'separate_contract'):
            self.boundary.grant(schema=160,fresh_attempt_root=self.root/'continuations'/('a'*64))
        self.assertFalse((self.root/'write-boundary-160.json').exists())

    def test_full_running_publication_is_separate_from_private_grant(self):
        from unittest.mock import Mock
        self.boundary.grant(schema=160)
        actual=admission.encoded({'full_runtime':'explicit-model-only'})
        (self.root/'candidate-runtime.json').write_bytes(actual)
        self.kernel.round=Mock()
        with patch.object(admission,'require_maintenance_handoff') as proof:
            self.boundary.seal_maintenance_runtime()
        proof.assert_called_once_with(self.contract,admissions=self.path)
        self.assertTrue(all(c.kwargs=={'normal':True} for c in self.kernel.round.call_args_list))
        self.assertEqual((self.root/'normal-publication.json').read_bytes(),actual)
        self.assertTrue((self.root/'target-normal-publication.json').exists())
        self.assertEqual(json.loads(self.grant_path.read_text())['mode'],'NORMAL')

    def test_missing_handoff_witness_revokes_the_existing_private_grant(self):
        self.boundary.grant(schema=160)
        with patch.object(admission,'require_maintenance_handoff',side_effect=RuntimeError('missing_fresh_handoff')):
            with self.assertRaisesRegex(RuntimeError,'missing_fresh_handoff'):self.boundary.seal_maintenance_runtime()
        self.assertEqual(json.loads(self.grant_path.read_text())['mode'],'READ_ONLY')
        self.assertFalse((self.root/'normal-publication.json').exists())

    def test_private_provider_is_mandatory_and_cannot_be_a_callback_packet(self):
        for provider in (None,{'approved':True},object()):
            with self.subTest(provider=type(provider).__name__),self.assertRaisesRegex(RuntimeError,'concrete_private_provider_required'):
                m.CompletedNormalWriteHandoff(self.contract,self.kernel,source_guard=lambda:None,
                    boot_guard=lambda:None,artifact_guard=lambda:None,admissions=self.path,state_root=self.path,
                    provider_adapter=provider)


if __name__=='__main__':unittest.main()
