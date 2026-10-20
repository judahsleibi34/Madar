"""Parent migration integration: MODEL authority, transport, backup and admission.

Real files and the existing coordinator/run_migration path. These cases do not
claim a registered150 profile, a privileged release or independent authority.
"""
import copy
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import completed_normal_migration as migration
from deployment.lib import completed_normal_execution as execution
from deployment.lib import schema150_provider_adapter as provider
from deployment.lib import schema150_provider_lifecycle as lifecycle
from deployment.lib import schema149_provider_lifecycle as journal_module
from deployment.lib import schema150_release as release
from deployment.lib.completed_normal_profile import DELETION,LEGACY
from deployment.lib.completed_normal_resources import ROLES
from test_schema150_admission import deletion_contract

class ParentMigrationTests(unittest.TestCase):
    def setUp(self,*,contract=None,native=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name)
        self.contract=copy.deepcopy(contract or deletion_contract());self.sha=self.contract['candidate']['source_sha']
        self.root=self.directory/'admissions'/migration.digest(self.contract);self.root.mkdir(parents=True)
        self.state=self.directory/'state';self.state.mkdir()
        interlock=self.directory/'synthetic-interlock.json';interlock.write_text('{}')
        self.enterContext(patch('deployment.lib.control_plane_upgrade_authorization.UPGRADE_INTERLOCK',interlock))
        self.release=self.state/'releases'/self.sha
        releases=self.release/'web/deployment/releases';releases.mkdir(parents=True)
        source=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
        (releases/DELETION.manifest).write_bytes((source/'deployment/releases'/DELETION.manifest).read_bytes())
        self.initial={'active_slot':self.contract['origin']['slot'],'known_good_release':{
            'slot':self.contract['origin']['slot'],'sha':self.contract['source_roles']['application_sha'],
            'schema':146},'preserved_fixture':{'not_promoted':True}}
        (self.state/'state.json').write_text(json.dumps(self.initial))
        self.driver=execution.CompletedNormalUpgrade.__new__(execution.CompletedNormalUpgrade)
        self.driver.contract=self.contract;self.driver.profile=DELETION;self.driver.root=self.root;self.driver.lock=71
        self.driver.controller=self.contract['candidate']['controller_sha']
        self.driver.ops=SimpleNamespace(state_root=self.state,upgrade_root=self.directory/'upgrade',
            control_root=self.directory/'installed',deploy_lock_descriptor=72)
        self.driver.actor=SimpleNamespace(runtime=Mock(),guard=Mock(),native=Mock(return_value=150),event=Mock())
        self.driver.artifact_guard=Mock();self.driver.model_loader=Mock(return_value={})
        self.driver.root_credential=Mock(side_effect=lambda:nullcontext())
        self.actor=provider.Schema150ProviderAdapter.__new__(provider.Schema150ProviderAdapter)
        self.actor.contract=copy.deepcopy(self.contract);self.actor.root=self.root
        self.actor.runtime=self.driver.actor.runtime;self.actor.lock_descriptors=(71,72)
        self.actor.binding={'operation':DELETION.operation,'context_sha256':migration.digest(self.contract),
            'source_sha':self.sha,'controller_sha':self.driver.controller,'inventory_sha256':'4'*64,
            'system_identifier':self.contract['database']['system_identifier'],'source_schema':146,'target_schema':150}
        self.actor.require_authority=Mock();self.actor.observe_quiescence=Mock();self.actor.migration_guard=Mock()
        self.actor.migration_completion_guard=Mock()
        self.journal_root=self.root/'provider-journal';self.journal_root.mkdir(mode=0o700)
        self.enterContext(patch.object(journal_module,'require_root_directory',lambda p:None))
        self.enterContext(patch.object(journal_module,'protected',lambda p,**kw:Path(p)))
        self.journal=lifecycle.ProtectedProviderJournal(self.journal_root)
        self.journal.append('prepared',{'binding':self.actor.binding,'preimage':{'synthetic':'preimage'}})
        for step in lifecycle.FENCE_STEPS:
            self.journal.append('effect_intent',{'step':step});self.journal.append('effect_complete',{'step':step})
        self.bindings={role:{'id':migration.digest({'role':role}),'image':'sha256:'+'1'*64,
            'spec_sha256':'2'*64,'networks':{},'network_aliases':{}} for role in ROLES}
        self.stage={'operation':DELETION.operation,'context_sha256':migration.digest(self.contract),
            'source_sha':self.sha,'images':self.contract['candidate']['images'],'runtimes':self.bindings,
            'networks':{},'worker_generation':'3'*64,'origin_workers':[]}
        self.write_stage()
        self.witness={'intent':migration.intent_document(self.contract),'backup':str(self.directory/'madar-synthetic'),
            **{k:'5'*64 for k in ('backup_manifest_sha256','backup_checksums_sha256','restore_execution_sha256',
                'replica_execution_sha256','maintenance_manifest_sha256')},
            'provider_maintenance':{'version':1,'binding':self.actor.binding,'journal_sha256':migration.digest(self.journal.read()),
                'preimage_sha256':migration.digest(self.journal.read()[0]['payload']['preimage'])}}
        self.enterContext(patch.object(migration,'ADMISSIONS',self.directory/'admissions'))
        self.enterContext(patch.object(migration.os,'geteuid',return_value=0))
        self.enterContext(patch.object(migration,'profile',return_value=DELETION))
        self.enterContext(patch.object(migration,'require_fresh_authorization'))
        self.enterContext(patch.object(migration,'require_candidate_authority'))
        self.enterContext(patch.object(migration,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(migration,'readonly_configuration',lambda p,**kw:Path(p)))
        self.credentials=self.enterContext(patch.object(migration,'credential_witness',side_effect=lambda key,digest:
            copy.deepcopy(self.witness if key=='migration_inputs' else self.stage)))
        if not native:self.locks=self.enterContext(patch.object(provider,'require_owned_lock'))
        self.model=self.enterContext(patch('deployment.lib.completed_normal_runtime.validate_model',return_value=(self.bindings,{})))
        self.runtime=self.enterContext(patch('deployment.lib.emergency_routing_repair.Runtime'))
        self.admitted=self.enterContext(patch.object(release,'admitted_manifest',return_value=SimpleNamespace(
            release_sha='CURRENT',migrations=(),coordinated=True)))
        from deployment.lib.migration_executor import MigrationManifest,Migration
        raw=json.loads((releases/DELETION.manifest).read_bytes())
        self.manifest=MigrationManifest(self.sha,tuple(Migration(row['number'],self.release/row['path'],row['sha256'],
            row['from_schema'],row['to_schema'],row['compatibility']) for row in raw['migrations']),coordinated=True)
        self.admitted.return_value=self.manifest
        if not native:
            self.executor=self.enterContext(patch.object(migration,'LockedMigrationExecutor'))
            self.executor.return_value.run.return_value={'observed_schema':150,'status':'completed'}
        self.driver.actor.native.side_effect=[146,150,150]

    def write_stage(self):
        (self.root/'candidate-staged-runtime.json').write_text(json.dumps(self.stage))

    def run_parent(self):return self.driver.migrate(provider_adapter=self.actor)

    def test_parent_invokes_existing_executor_under_root_window_without_public_promotion(self):
        original=(self.state/'state.json').read_bytes()
        result=self.run_parent()
        self.assertEqual(result['observed_schema'],150)
        self.driver.root_credential.assert_called_once_with()
        self.executor.assert_called_once()
        self.assertIs(self.executor.call_args.kwargs['migration_guard'],self.actor.migration_guard)
        self.assertIs(self.executor.call_args.kwargs['completion_guard'],self.actor.migration_completion_guard)
        self.model.assert_called_once_with(self.contract,{},self.actor.runtime,phase='fenced')
        self.runtime.return_value.json_http.assert_not_called()
        self.assertEqual((self.state/'state.json').read_bytes(),original)
        self.assertEqual(self.driver.actor.event.call_args.args,('parent_migration_completed',))

    def test_legacy_profile_retains_existing_unprivileged_child_path(self):
        self.driver.profile=LEGACY;self.driver.service=Mock()
        self.driver.migrate()
        self.driver.service.assert_called_once_with('migrate')
        self.executor.assert_not_called();self.driver.root_credential.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,'parent_profile_invalid'):self.run_parent()

    def test_missing_or_wrong_concrete_actor_refuses_before_new_credential(self):
        for value in (None,object(),SimpleNamespace(contract=self.contract)):
            with self.subTest(value=type(value)),self.assertRaisesRegex(RuntimeError,'concrete_provider_required'):
                self.driver.migrate(provider_adapter=value)
        self.driver.root_credential.assert_not_called();self.executor.assert_not_called()

    def test_wrong_parent_locks_or_runtime_refuse_before_sql(self):
        self.actor.lock_descriptors=(71,73)
        with self.assertRaisesRegex(RuntimeError,'parent_binding_invalid'):self.run_parent()
        self.executor.assert_not_called()

    def test_unknown_root_lock_never_reaches_database(self):
        self.locks.side_effect=RuntimeError('synthetic_unheld_lock')
        with self.assertRaisesRegex(RuntimeError,'unheld_lock'):self.run_parent()
        self.executor.assert_not_called()

    def test_changed_provider_journal_refuses_sql(self):
        self.journal.append('quiescence',{'synthetic':'changed after backup'})
        with self.assertRaisesRegex(RuntimeError,'provider_witness_changed'):self.run_parent()
        self.executor.assert_not_called()

    def test_pending_provider_effect_refuses_sql(self):
        self.journal.append('effect_intent',{'step':lifecycle.PRIVATE_STEPS[0]})
        with self.assertRaisesRegex(RuntimeError,'provider_witness_changed'):self.run_parent()
        self.executor.assert_not_called()

    def test_changed_candidate_stage_refuses_sql(self):
        self.stage['source_sha']='f'*40;self.write_stage()
        with self.assertRaisesRegex(RuntimeError,'private_stage_changed'):self.run_parent()
        self.executor.assert_not_called()

    def test_replaced_candidate_container_is_not_the_sealed_candidate(self):
        changed=copy.deepcopy(self.bindings);changed['backend']['id']='f'*64
        self.model.return_value=(changed,{})
        with self.assertRaisesRegex(RuntimeError,'private_candidate_changed'):self.run_parent()
        self.executor.assert_not_called()

    def test_existing_admission_block_cannot_be_bypassed_by_a_parent_or_actor(self):
        self.admitted.side_effect=RuntimeError('schema150_protected_controller_integration_incomplete')
        with self.assertRaisesRegex(RuntimeError,'integration_incomplete'):self.run_parent()
        self.executor.assert_not_called()

    def test_executor_error_is_not_retried_or_promoted(self):
        self.executor.return_value.run.side_effect=OSError('synthetic_lost_commit_response')
        with self.assertRaisesRegex(RuntimeError,'completed_migration_error_OSError'):self.run_parent()
        self.executor.return_value.run.assert_called_once()
        self.assertEqual(json.loads((self.state/'state.json').read_bytes()),self.initial)
        self.assertNotEqual(self.driver.actor.event.call_args.args,('parent_migration_completed',))

    def test_runtime_state_change_after_commit_blocks_completion_without_overwriting_it(self):
        changed=dict(self.initial,unexpected='concurrent mutation')
        def execute():
            (self.state/'state.json').write_text(json.dumps(changed));return {'status':'completed'}
        self.executor.return_value.run.side_effect=execute
        with self.assertRaisesRegex(RuntimeError,'release_changed_during_execution'):self.run_parent()
        self.assertEqual(json.loads((self.state/'state.json').read_bytes()),changed)

if __name__=='__main__':unittest.main()
