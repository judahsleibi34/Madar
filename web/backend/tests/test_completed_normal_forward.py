"""Fresh scope/immutable executor guards; actual resumption is a separate gate."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from deployment.lib import completed_normal_forward as m
from deployment.lib.completed_normal_admission import digest,encoded
from test_completed_normal_admission import fixture_contract

def fixture_plan(contract):
    plan={'version':1,'operation':m.OPERATION,'nonce':'a'*32,'controller_sha':contract['candidate']['controller_sha'],
        'application_sha':contract['candidate']['source_sha'],'source_bundle_sha256':'b'*64,
        'parent_plan_sha256':contract['plan_sha256'],'parent_context_sha256':digest(contract),
        'observed_schema':119,'database':contract['database'],'previous_execution':'execution.json',
        'fixture_only':True,'production_authorization':False}
    for key in ('previous_execution_sha256','parent_failure_sha256','customer_snapshot_sha256','grant_sha256',
                'runtime_sha256','worker_owner_sha256'):plan[key]='c'*64
    return plan

class ForwardScopeTests(unittest.TestCase):
    def setUp(self):self.contract=fixture_contract();self.plan=fixture_plan(self.contract)
    def test_new_scope_is_distinct_and_legacy_executor_remains_fixed(self):
        m.validate_scope(self.contract,self.plan)
        parent=Path('/state/migrations')/self.plan['application_sha']/'execution.json'
        self.assertEqual(m.executor_path('/state',self.plan['application_sha'],'execution.json'),parent)
        resumed=m.executor_path('/state',self.plan['application_sha'],'resumptions/'+digest(self.plan)+'/execution.json')
        self.assertNotEqual(parent,resumed);self.assertEqual(resumed.parent.name,digest(self.plan))
        other=dict(self.plan,nonce='d'*32);self.assertNotEqual(digest(other),digest(self.plan))
    def test_identity_schema_or_authorization_ambiguity_fails_closed(self):
        for key,value in [('controller_sha','e'*40),('application_sha','e'*40),('parent_context_sha256','f'*64),
                ('observed_schema',114),('observed_schema',137),('observed_schema',True),
                ('fixture_only',False),('production_authorization',True),('nonce','bad'),('previous_execution','../../execution.json')]:
            with self.subTest(key=key,value=value):
                changed=copy.deepcopy(self.plan);changed[key]=value
                with self.assertRaises(RuntimeError):m.validate_scope(self.contract,changed)
        changed=copy.deepcopy(self.plan);changed['database']['container_id']='f'*64
        with self.assertRaises(RuntimeError):m.validate_scope(self.contract,changed)
    def test_previous_execution_paths_are_confined_to_reviewed_release(self):
        for path in ('/absolute','resumptions/../execution.json','other.json','resumptions/'+'a'*63+'/execution.json'):
            with self.assertRaisesRegex(RuntimeError,'previous_execution_invalid'):m.executor_path('/state','c'*40,path)
    def test_parent_authorization_is_not_a_resumption_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);(root/'operator-authorization.json').write_text(json.dumps({'operation':'completed-normal-schema115-136-upgrade'}))
            with patch.object(m,'scope_root',return_value=root),patch.object(m,'protected',lambda path,**kw:Path(path)),patch.object(m.os,'geteuid',return_value=0),patch.object(m,'file_digest',return_value='c'*64):
                with self.assertRaisesRegex(RuntimeError,'fresh_authorization_missing'):m.authorize_witness(self.contract,self.plan)
                (root/'operator-authorization.json').write_bytes(encoded(m.authorization_record(self.plan)))
                self.assertEqual(m.authorize_witness(self.contract,self.plan),self.plan)
    def test_root_issuer_rejects_changed_private_parent_before_credential(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);(root/'operator-authorization.json').write_bytes(encoded(m.authorization_record(self.plan)))
            with patch.object(m,'scope_root',return_value=root),patch.object(m,'protected',lambda path,**kw:Path(path)),patch.object(m.os,'geteuid',return_value=0),patch.object(m,'file_digest',return_value='d'*64):
                with self.assertRaisesRegex(RuntimeError,'runtime_witness_changed'):m.authorize_witness(self.contract,self.plan)
    def test_deployment_user_cannot_issue_a_private_history_witness(self):
        with patch.object(m.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(RuntimeError,'root_issuer_required'):m.authorize_witness(self.contract,self.plan)
    def test_child_executor_never_reads_root_private_parent_history(self):
        with tempfile.TemporaryDirectory() as raw:
            state=Path(raw);prior=m.executor_path(state,self.plan['application_sha'],'execution.json');prior.parent.mkdir(parents=True)
            prior.write_text('preserved failed executor');owner=state/'worker-ownership.json';owner.write_text('exclusive current owner')
            runtime={'fixture':'root-issued sealed runtime'};grant={'fixture':'root-issued READ_ONLY grant'}
            plan=dict(self.plan,previous_execution_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),worker_owner_sha256=hashlib.sha256(owner.read_bytes()).hexdigest(),runtime_sha256=digest(runtime),grant_sha256=digest(grant))
            def witness(name,key):return {'migration_resumption':plan,'candidate_runtime':runtime}[name]
            with patch.object(m.os,'geteuid',return_value=1000),patch.object(m,'credential_witness',side_effect=witness),patch.object(m,'protected',side_effect=AssertionError('private parent read attempted')),patch.object(m,'readonly_configuration',lambda path,**kw:Path(path)),patch.object(m,'require_candidate_authority',return_value=grant),patch('deployment.lib.completed_normal_admission.require_fresh_authorization') as authorization:
                actual,path=m.authorized_executor(self.contract,state)
                self.assertEqual(actual,plan);self.assertIn('/resumptions/',str(path));authorization.assert_called_once_with(self.contract)
    def test_stale_plan_fails_before_new_attempt_or_effect(self):
        actor=SimpleNamespace(contract=self.contract)
        driver=m.CompletedNormalForwardResumption(actor,self.plan,artifact_guard=Mock(),rehearsal_guard=Mock())
        with patch.object(m,'measure_plan',return_value=dict(self.plan,observed_schema=120)):
            with self.assertRaisesRegex(RuntimeError,'live_bindings_changed'):driver.preflight()
    def test_consumed_fresh_scope_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as raw:
            actor=SimpleNamespace(contract=self.contract)
            driver=m.CompletedNormalForwardResumption(actor,self.plan,artifact_guard=Mock(),rehearsal_guard=Mock());driver.root=Path(raw)/'consumed';driver.root.mkdir()
            with patch.object(m,'measure_plan',return_value=self.plan),patch('deployment.lib.control_plane_filesystem.require_root_protected_directory'):
                with self.assertRaisesRegex(RuntimeError,'attempt_already_consumed'):driver.preflight()

if __name__=='__main__':unittest.main()
