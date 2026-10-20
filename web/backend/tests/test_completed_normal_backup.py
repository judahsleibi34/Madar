"""Fresh backup scope must not recycle the historical schema115 authorization."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_backup as m
from deployment.lib.completed_normal_admission import digest,encoded,OPERATION
from test_completed_normal_admission import fixture_contract

class CompletedBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.contract=fixture_contract()
        self.document={'source_bundle_sha256':'f'*64,'live_configuration_sha256':{'node1_configuration':'e'*64}}
        self.contract['plan_sha256']=digest(self.document)
        self.calls=[]
        self.kernel=SimpleNamespace(contract=self.contract,root=self.root/digest(self.contract),
            native_verifier=lambda:115,round=lambda **kw:self.calls.append(kw),
            runtime=SimpleNamespace(command=lambda args:json.dumps(['anon','authenticated','service_role'])))
        self.artifacts={'node1_replica':{'host':'madar-node1-lan','filesystem_uuid':'12345678-1234-1234-1234-123456789abc','configuration_sha256':'e'*64}}
        patches=[patch.object(m,'ADMISSIONS',self.root),patch.object(m,'require_fresh_authorization',lambda c:None),
            patch.object(m,'protected',lambda p,**kw:Path(p)),patch.object(m,'file_digest',lambda p:'f'*64),
            patch.object(m.os,'geteuid',lambda:0)]
        for p in patches:p.start();self.addCleanup(p.stop)
        self.context=self.create('pre-migration');self.context.root.mkdir()
        self.authorization={'operation':OPERATION,'context_sha256':digest(self.contract),'plan_sha256':self.contract['plan_sha256'],
            'source_bundle_sha256':'f'*64,'controller_sha':self.contract['candidate']['controller_sha'],
            'application_sha':self.contract['candidate']['source_sha']}
        (self.context.root/'operator-authorization.json').write_bytes(encoded(self.authorization))
        (self.context.root/'admission.json').write_bytes(encoded({'operation':OPERATION,'contract':self.contract}))
    def create(self,stage):
        return m.CompletedNormalBackupContext(self.contract,self.document,self.root/'package',self.kernel,
            stage=stage,source_guard=lambda:self.calls.append('source'),artifact_guard=lambda:copy.deepcopy(self.artifacts))
    def test_pre_and_post_have_distinct_nonreplayable_scopes_and_expected_modes(self):
        pre=self.context;post=self.create('post-migration')
        self.assertNotEqual(pre.scope,post.scope)
        pre.guard();self.assertIn({'normal':False},self.calls)
        self.kernel.native_verifier=lambda:136;post.guard();self.assertIn({'normal':True},self.calls)
        with self.assertRaisesRegex(RuntimeError,'schema_changed'):pre.guard()
    def test_exact_operator_binding_and_consumed_stage_are_required(self):
        self.context.validate(self.context.plan,self.context.root,self.context.package)
        changed=dict(self.authorization,controller_sha='0'*40)
        (self.context.root/'operator-authorization.json').write_bytes(encoded(changed))
        with self.assertRaisesRegex(RuntimeError,'operator_binding_changed'):
            self.context.validate(self.context.plan,self.context.root,self.context.package)
        (self.context.root/'operator-authorization.json').write_bytes(encoded(self.authorization))
        (self.context.root/self.context.receipt_name).write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError,'already_consumed'):
            self.context.validate(self.context.plan,self.context.root,self.context.package)
    def test_wrong_source_images_root_or_package_is_rejected(self):
        for key,value in [('source_sha','0'*40),('candidate_images',{'backend':'changed'}),('digest','0'*64)]:
            changed=copy.copy(self.context.plan);setattr(changed,key,value)
            with self.assertRaisesRegex(RuntimeError,'fresh_binding_invalid'):
                self.context.validate(changed,self.context.root,self.context.package)
        with self.assertRaisesRegex(RuntimeError,'fresh_binding_invalid'):
            self.context.validate(self.context.plan,self.root,self.context.package)
    def test_node1_configuration_or_identity_changed_is_fatal(self):
        self.context.artifacts()
        for key,value in [('configuration_sha256','0'*64),('host','other-host'),('filesystem_uuid','invalid')]:
            original=self.artifacts['node1_replica'][key];self.artifacts['node1_replica'][key]=value
            with self.assertRaisesRegex(RuntimeError,'replica_binding_invalid'):self.context.artifacts()
            self.artifacts['node1_replica'][key]=original
    def test_role_inventory_reads_only_current_names_and_rejects_unreviewed_names(self):
        self.assertEqual(self.context.role_names(),('anon','authenticated','service_role'))
        self.kernel.runtime.command=lambda args:json.dumps(['anon','quoted-role'])
        with self.assertRaisesRegex(RuntimeError,'role_inventory_invalid'):self.context.role_names()

    def test_initdb_reserved_roles_are_not_recreated_but_application_roles_remain(self):
        self.kernel.runtime.command=lambda args:json.dumps(['anon','authenticated','pg_checkpoint','pg_monitor','postgres','service_role','supabase_auth_admin'])
        self.assertEqual(self.context.role_names(),('anon','authenticated','postgres','service_role','supabase_auth_admin'))
        self.kernel.runtime.command=lambda args:json.dumps(['anon','anon','pg_monitor'])
        with self.assertRaisesRegex(RuntimeError,'role_inventory_invalid'):self.context.role_names()
    def test_actual_pipeline_receives_only_fresh_context_and_no_old_plan(self):
        with patch('deployment.lib.active_recovery_backup.capture_and_replicate',return_value={'verified':True}) as call:
            self.assertEqual(self.context.capture(),{'verified':True})
        self.assertIs(call.call_args.kwargs['completed_context'],self.context)
        self.assertNotIn('authorizing_context',call.call_args.kwargs)
        self.assertNotIn('recovery_context',call.call_args.kwargs)

    def test_maintenance_preparation_needs_concrete_adapter_and_never_probes_stopped_http(self):
        from test_schema150_admission import deletion_contract
        from deployment.lib.schema150_provider_adapter import Schema150ProviderAdapter
        from deployment.lib.completed_normal_profile import profile,DELETION
        from unittest.mock import Mock
        contract=deletion_contract();contract['plan_sha256']=digest(self.document)
        kernel=SimpleNamespace(contract=contract,root=self.root/digest(contract),round=Mock())
        with self.assertRaisesRegex(RuntimeError,'concrete_provider_required'):
            m.CompletedNormalBackupContext(contract,self.document,self.root/'package',kernel,stage='pre-migration',
                source_guard=lambda:None,artifact_guard=lambda:{},provider_adapter=object())
        adapter=Schema150ProviderAdapter.__new__(Schema150ProviderAdapter)
        adapter.contract=contract;adapter.binding={'synthetic':'MODEL ONLY'}
        adapter.require_authority=Mock();adapter.observe_quiescence=Mock(return_value={'schema':146})
        context=m.CompletedNormalBackupContext(contract,self.document,self.root/'package',kernel,stage='pre-migration',
            source_guard=lambda:None,artifact_guard=lambda:{},provider_adapter=adapter)
        self.assertIs(context.profile,DELETION);context.guard();kernel.round.assert_not_called()
        adapter.require_authority.assert_called_with(adapter.binding,purpose='backup')
        with self.assertRaisesRegex(RuntimeError,'profile_invalid'):profile(contract)

    def test_two_backup_publications_preserve_distinct_exact_latest_preimages(self):
        from deployment.lib.active_recovery_backup import latest_preimage_name
        from deployment.lib.emergency_routing_repair import exclusive
        pre=self.context;post=self.create('post-migration')
        # Exercise the real exclusive filesystem primitive: the legacy shared
        # name fails on the second publication, while stage-bound names retain
        # both original bytes and still prohibit an automatic stage replay.
        legacy=self.root/latest_preimage_name()
        exclusive(legacy,b'old')
        with self.assertRaises(FileExistsError):exclusive(legacy,b'new')
        for context,body in ((pre,b'old-current-backup'),(post,b'verified-source115-backup')):
            path=self.root/latest_preimage_name(context);exclusive(path,body)
            self.assertEqual(path.read_bytes(),body)
            with self.assertRaises(FileExistsError):exclusive(path,b'replay')
        self.assertEqual(legacy.read_bytes(),b'old')

if __name__=='__main__':unittest.main()
