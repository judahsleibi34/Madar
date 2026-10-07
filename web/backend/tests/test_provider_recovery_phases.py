"""Phase separation: rehearsal capability never grants activation authority."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
WEB_ROOT=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB_ROOT))
from deployment.lib.provider_recovery import ProviderRecoveryTransaction
from deployment.lib.provider_recovery_phases import (PREPARE, AUTHORIZE, MANDATORY_GATES, PRECONDITIONS,
    preparation_binding, sha256, validate_completed_rehearsal, PreparationTransaction, require_activation_evidence)
from deployment.lib.provider_recovery_preparation import PrivatePreparationOperations
import test_provider_recovery_controller as fixtures


class PhaseTests(unittest.TestCase):
    def setUp(self):
        fixtures.RecoveryControllerTests.setUp(self)
        self.report={'format':2,'phase':PREPARE,'schema':115,'production_modified':False,'migrations_executed':False,
            'preparation_binding':sha256(preparation_binding(self.contract,self.metadata)),
            'origin_evidence':self.origin,'preconditions':{key:'PASS' for key in PRECONDITIONS},
            'checks':{key:'PASS' for key in MANDATORY_GATES}}

    def test_preparation_does_not_need_human_or_rollback(self):
        test=self
        class PrivateOperations:
            def __init__(self): self.calls=[]
            def require_isolated(self): self.calls.append('isolation')
            def collect_preconditions(self,*args): return {key:'PASS' for key in PRECONDITIONS},test.origin
            def prepare_isolated_candidate_and_fallback(self,*args): self.calls.append('private_candidate')
            def save_preparation_report(self,report): self.report=report
        ops=PrivateOperations()
        report=PreparationTransaction(ops).prepare(self.contract,self.metadata)
        self.assertEqual(report['checks']['human_auth'],'PENDING')
        self.assertEqual(report['checks']['runtime_only_local_rollback'],'PENDING')
        self.assertFalse(report['production_modified'])
        self.assertEqual(ops.calls,['isolation','private_candidate','isolation'])

    def test_every_activation_gate_is_required_including_human_and_rollback(self):
        validate_completed_rehearsal(self.contract,self.metadata,self.report)
        for gate in MANDATORY_GATES:
            report=copy.deepcopy(self.report);report['checks'][gate]='PENDING'
            with self.subTest(gate=gate),self.assertRaises(RuntimeError):
                validate_completed_rehearsal(self.contract,self.metadata,report)
        for gate in MANDATORY_GATES:
            report=copy.deepcopy(self.report);del report['checks'][gate]
            with self.subTest(missing=gate),self.assertRaises(RuntimeError):
                validate_completed_rehearsal(self.contract,self.metadata,report)

    def test_source_images_checkpoint_fingerprints_and_schema_are_bound(self):
        changes=[replace(self.contract,sha='9'*40),replace(self.contract,images={**self.contract.images,'backend':'sha256:'+'9'*64}),
            replace(self.contract,checkpoint_digest='9'*64),replace(self.contract,production_fingerprints={**self.contract.production_fingerprints,'state':'9'*64})]
        for contract in changes:
            with self.subTest(contract=contract.sha),self.assertRaises(RuntimeError):
                validate_completed_rehearsal(contract,self.metadata,self.report)
        for key,value in (('target',116),('migration_class','expand-only')):
            metadata=copy.deepcopy(self.metadata);metadata['schema'][key]=value
            with self.assertRaises(RuntimeError): validate_completed_rehearsal(self.contract,metadata,self.report)
        metadata=copy.deepcopy(self.metadata);metadata['migration_manifest']=None
        with self.assertRaises(RuntimeError): validate_completed_rehearsal(self.contract,metadata,self.report)

    def test_phase1_receipt_or_tampering_cannot_enter_phase3(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for report in (self.report,{**self.report,'phase':AUTHORIZE}, {**self.report,'production_modified':True}):
                # Receipt/file verifier is exercised with controlled file reads;
                # no adapter authorization or mutation method may be reached.
                receipt={'format':2,'phase':PREPARE}
                def files(path,**kw): return root/('report.json' if 'rehearsal' in str(path) else 'receipt.json')
                (root/'receipt.json').write_text(json.dumps(receipt));(root/'report.json').write_text(json.dumps(report))
                operations=unittest.mock.Mock()
                with patch('deployment.lib.provider_recovery_runtime.protected',side_effect=files), patch('deployment.lib.provider_recovery_phases.require_activation_evidence',side_effect=lambda c,m: require_activation_evidence(c,m)),self.assertRaises(RuntimeError):
                    ProviderRecoveryTransaction(root,operations).activate(self.contract,self.metadata)
                operations.assert_not_called()
                operations.authorize.assert_not_called()
                operations.switch_recovery_traffic.assert_not_called()

    def test_private_adapter_rejects_production_capabilities(self):
        ops=PrivatePreparationOperations.__new__(PrivatePreparationOperations)
        ops.scope_prefix='madar-provider402-rehearsal-123456789abc'
        ops.directory=Path('/var/lib/madar-control-plane/provider402/rehearsals/'+'a'*64)
        from deployment.lib.provider_recovery_runtime import RecoveryPaths
        ops.paths=RecoveryPaths(proxy=ops.scope_prefix+'-proxy')
        # Only skip filesystem setup in this unit test; production-resource
        # capability checks run in the actual command implementation.
        ops.require_isolated=lambda: True
        for args in (['docker','stop','madar-green-backend'], ['docker','update','--restart=no','madar-green-notification-worker'],
                     ['docker','exec','madar-release-proxy','nginx','-s','reload'], ['docker','network','connect','madar-supabase-client','madar-blue-backend'],
                     ['docker','run','--name','madar-green-backend','image'], ['systemctl','stop','madar-auto-deploy.timer'],
                     ['docker','exec','-i','supabase-db','psql']):
            with self.subTest(operation=args),self.assertRaises(RuntimeError): ops.command(args)
