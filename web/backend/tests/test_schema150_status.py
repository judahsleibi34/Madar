"""Actual temporary journal read/validation; no service or authority transport."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_status as status
from deployment.lib import schema149_provider_lifecycle as retained
from deployment.lib import schema150_provider_lifecycle as lifecycle

class StatusTests(unittest.TestCase):
    def fixture(self):
        from test_schema150_provider_adapter import ConcreteAdapterTests
        contract,scope,data,_=ConcreteAdapterTests.constructor_inputs(self)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700)
        context=scope['context_sha256'];admission=root/context;admission.mkdir(mode=0o700)
        journal_root=admission/'provider-journal';journal_root.mkdir(mode=0o700)
        self.enterContext(patch.object(status,'ADMISSIONS',root))
        self.enterContext(patch.object(status,'protected',lambda path,**kwargs:Path(path)))
        self.enterContext(patch.object(retained,'protected',lambda path,**kwargs:Path(path)))
        self.enterContext(patch.object(retained,'require_root_directory',lambda path:None))
        (admission/'admission.json').write_text(json.dumps({'operation':contract['operation'],'contract':contract}))
        (admission/'provider-inventory.json').write_text(json.dumps(data))
        journal=lifecycle.ProtectedProviderJournal(journal_root)
        preimage={'roles':{'archive':'SENSITIVE-NEVER-OUTPUT'},'objects':{},'ingress':{},'supervisors':{}}
        journal.append('prepared',{'binding':scope,'preimage':preimage,'proof':{}})
        return context,admission,journal,scope,preimage

    def test_prepared_observation_is_partial_and_never_authority_or_live_database_proof(self):
        context,_,_,_,_=self.fixture()
        value=status.inspect_maintenance(context)
        self.assertEqual(value['status'],'PARTIAL');self.assertEqual(value['completed_steps'],[])
        for key in ('authority_issued','mutations_executed','operational_profile_registered',
                    'current_database_verified','current_services_verified'):
            self.assertIs(value[key],False)
        self.assertNotIn('SENSITIVE-NEVER-OUTPUT',json.dumps(value))

    def test_pending_fence_without_barrier_fails_and_records_no_new_journal(self):
        context,_,journal,_,_=self.fixture()
        journal.append('effect_intent',{'step':'arm_boot_interlock'})
        before=journal.read();value=status.inspect_maintenance(context)
        self.assertEqual(value['status'],'FAIL');self.assertTrue(value['requires_independent_recovery'])
        self.assertEqual(journal.read(),before)

    def test_exact_barrier_is_verified_using_journal_digest_not_contract_encoding(self):
        context,root,journal,binding,preimage=self.fixture()
        journal.append('effect_intent',{'step':'arm_boot_interlock'})
        (root/'provider-barrier.json').write_text(json.dumps({'binding':binding,'preimage_sha256':lifecycle.digest(preimage)}))
        self.assertTrue(status.inspect_maintenance(context)['persistent_barrier_present'])
        (root/'provider-barrier.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'barrier_changed'):status.inspect_maintenance(context)

    def test_tampered_chain_and_out_of_order_effect_rejected(self):
        context,root,journal,_,_=self.fixture()
        journal.append('effect_intent',{'step':'resume_accepted_workers'})
        with self.assertRaisesRegex(RuntimeError,'sequence'):status.inspect_maintenance(context)
        target=root/'provider-journal'/'0001.json'
        value=json.loads(target.read_bytes());value['previous_sha256']='f'*64;target.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'chain'):status.inspect_maintenance(context)

    def test_wrong_contract_or_inventory_cannot_be_relabelled(self):
        context,root,_,_,_=self.fixture()
        path=root/'admission.json';value=json.loads(path.read_bytes());value['contract']['rehearsal_sha256']='f'*64;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'admission_changed'):status.inspect_maintenance(context)

    def test_surviving_barrier_after_recorded_clear_requires_recovery(self):
        context,root,journal,binding,preimage=self.fixture()
        for step in lifecycle.STEPS:
            if step==lifecycle.ACTIVATE_STEPS[0]:
                journal.append('private_ready',{'binding_sha256':lifecycle.digest(binding)})
            journal.append('effect_intent',{'step':step})
            journal.append('effect_complete',{'step':step})
        (root/'provider-barrier.json').write_text(json.dumps({'binding':binding,
            'preimage_sha256':lifecycle.digest(preimage)}))
        result=status.inspect_maintenance(context)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(result['requires_independent_recovery'])

    def test_private_quiescence_payload_cannot_escape_as_an_untyped_schema_value(self):
        context,_,journal,binding,_=self.fixture()
        for step in lifecycle.FENCE_STEPS:
            journal.append('effect_intent',{'step':step});journal.append('effect_complete',{'step':step})
        journal.append('quiescence',{'schema':{'private':'NEVER-EMIT'},
            'system_identifier':binding['system_identifier']})
        with self.assertRaisesRegex(RuntimeError,'recorded_database_invalid'):
            status.inspect_maintenance(context)

    def test_unknown_target_and_arbitrary_path_rejected_before_read(self):
        for target in ('../../etc','production','A'*64,'a'*63,None):
            with self.subTest(target=target),self.assertRaisesRegex(RuntimeError,'exact_context_required'):
                status.inspect_maintenance(target)

if __name__=='__main__':unittest.main()
