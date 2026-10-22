"""Actual coordinator ordering, modeled authority/provider/backup/runtime.

Native SQL and domain transaction tests are separate. This module does not
register150, accept caller PASS flags, issue authority or certify an application.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

from deployment.lib import completed_normal_execution as execution
from deployment.lib import schema150_provider_adapter as adapter
from deployment.lib import schema150_provider_lifecycle as lifecycle
from deployment.lib.completed_normal_admission import digest,encoded
from deployment.lib.completed_normal_profile import DELETION, RECONCILED
import test_completed_normal_execution as historical
from test_schema150_admission import deletion_contract
from test_schema150_actor_inventory import fixture,repin


def maintenance_fixture(test, selected=DELETION):
    f=historical.ExecutionTests();f.setUp();test.addCleanup(f.doCleanups)
    f.source_schema=146;f.target_schema=selected.target;f.schema=146
    f.contract=deletion_contract()
    if selected is RECONCILED:
        from deployment.lib.schema160_release import MANIFEST_SHA256
        f.contract.update(version=selected.version,operation=selected.operation,migration_manifest_sha256=MANIFEST_SHA256)
        f.contract['candidate']['compatible_max']=selected.target
    f.driver.contract=f.contract;f.driver.actor.contract=f.contract
    f.driver.profile=selected
    f.driver.actor.candidate().contract=f.contract
    f.document['application_evidence']={'provenance':{'synthetic':'only'}}
    f.driver.maintenance_acceptance_guard=Mock(return_value=True)
    f.driver.maintenance_activation_guard=Mock(return_value={'synthetic':'only'})
    (inventory,_),_=fixture()
    scope={'operation':selected.operation,'context_sha256':'0'*64,'source_sha':f.contract['candidate']['source_sha'],
        'controller_sha':f.driver.controller,'inventory_sha256':'0'*64,
        'system_identifier':f.contract['database']['system_identifier'],'source_schema':146,'target_schema':selected.target}
    inventory,scope=repin(inventory,scope)
    f.contract['writer_inventory_sha256']=scope['inventory_sha256']
    f.driver.package.mkdir()
    (f.driver.package/'provider-inventory.json').write_bytes(encoded(inventory))
    f.ops.deploy_lock_descriptor=None
    def release():
        if f.ops.deploy_lock_descriptor is not None:os.close(f.ops.deploy_lock_descriptor)
        f.ops.deploy_lock_descriptor=None;f.effect('release_lock')
    f.ops.release_deployment_lock=release
    f.ops.close_locks=release
    f.provider=None
    class Provider:
        def __init__(self,contract,binding,runtime,**kwargs):
            self.contract,self.binding,self.runtime=contract,binding,runtime
            self.lock_descriptors=kwargs['lock_descriptors'];self.root=f.root
            f.provider=self
        def require_authority(self,*a,**kw):f.effect('provider_authority')
        def verify_candidate_stage(self):
            if 'seal_stage' not in f.calls:raise AssertionError('unsealed candidate')
            f.effect('candidate_reobserved')
        def observe_quiescence(self,*a,**kw):
            if f.mode!='READ_ONLY':raise AssertionError('quiescence under NORMAL')
            f.effect('quiescence');return {'schema':f.schema}
    class Lifecycle:
        def __init__(self,binding,journal,provider):self.actor=provider
        def prepare(self):
            if f.origin!='NORMAL':raise AssertionError('preimage captured after fence')
            f.effect('provider_preimage')
        def fence(self):
            if f.origin!='READ_ONLY' or any(x=='service_prepare' for x in f.calls):raise AssertionError('bridge first')
            f.effect('provider_fence')
        def prepare_private_activation(self):
            if f.schema!=selected.target or f.mode!='READ_ONLY':raise AssertionError('private boundary')
            f.effect('private_acceptance')
        def activate_after_grant(self,*,clear_boot=True):
            if f.schema!=selected.target or f.mode!='NORMAL':raise AssertionError('premature activation')
            if clear_boot and not (f.root/'normal-acceptance.json').exists():raise AssertionError('premature boot')
            f.effect('clear_provider_boot' if clear_boot else 'workers_proxy_activate')
    def migrate(*,provider_adapter):
        if provider_adapter is not f.provider:raise AssertionError('different provider')
        if provider_adapter.lock_descriptors!=(f.driver.lock,f.ops.deploy_lock_descriptor):raise AssertionError('stale descriptors')
        if 'seal_stage' not in f.calls or f.mode!='READ_ONLY':raise AssertionError('SQL before sealed maintenance')
        f.effect('parent_sql')
        for schema in selected.migrations:
            f.schema=schema;f.effect('committed_'+str(schema))
    f.driver.migrate=migrate
    patches=[patch.object(adapter,'Schema150ProviderAdapter',Provider),
        patch.object(adapter,'private_json',lambda p:json.loads(Path(p).read_text())),
        patch.object(adapter,'require_owned_lock'),patch.object(lifecycle,'ProviderMaintenance150',Lifecycle),
        patch.object(lifecycle,'ProtectedProviderJournal',lambda p:p),
        patch.object(execution,'require_root_directory',lambda p,**kw:Path(p).mkdir(mode=0o700,exist_ok=True)),
        patch('deployment.lib.schema148_artifacts.seal_candidate_provenance',lambda *a,**kw:f.effect('artifact_seal')),
        patch('deployment.lib.completed_normal_evidence.measured_record',lambda p:p)]
    for item in patches:item.start();test.addCleanup(item.stop)
    return f


class MaintenanceExecutionTests(unittest.TestCase):
    def test_original_schema146_grant_is_preserved_without_target_range_widening(self):
        from deployment.lib import completed_normal_profile as profiles
        contract=deletion_contract()
        with patch.object(profiles,'profile',return_value=DELETION):
            grant=profiles.expected_origin_grant(contract,'READ_ONLY')
        self.assertEqual((grant['version'],grant['schema'],grant['compatible_min'],grant['compatible_max']),
            (2,146,144,146))
        self.assertEqual(grant['release_sha'],contract['source_roles']['application_sha'])
        self.assertNotEqual(grant['release_sha'],contract['candidate']['source_sha'])

    def test_order_is_maintenance_backup_creation_sql_private_handoff_workers_proxy_boot(self):
        f=maintenance_fixture(self)
        result=f.driver._execute()
        self.assertEqual(result['schema'],150)
        sequence=['provider_preimage','fence_origin','provider_fence','backup_pre-migration','service_prepare',
            'seal_stage','candidate_reobserved','parent_sql','committed_147','committed_148','committed_149',
            'committed_150','customer_preservation','private_acceptance','grant_150','service_activate',
            'workers_proxy_activate','service_adopt','backup_post-migration','clear_provider_boot','restore_timers','clear_interlock']
        indices=[f.calls.index(item) for item in sequence]
        self.assertEqual(indices,sorted(indices))
        self.assertFalse(any(x in f.calls for x in ('service_publish','service_refresh','retained_blue_retirement_pending')))
        self.assertTrue((f.root/'normal-completion.json').exists())
        self.assertIsNone(f.driver.lock);self.assertIsNone(f.ops.deploy_lock_descriptor)

    def test_reconciled_operation_uses_all_fourteen_boundaries_and_exact_target(self):
        f=maintenance_fixture(self, RECONCILED)
        result=f.driver._execute()
        self.assertEqual(result['schema'],160)
        sequence=['provider_preimage','fence_origin','provider_fence','backup_pre-migration','service_prepare',
            'seal_stage','candidate_reobserved','parent_sql',
            *('committed_'+str(n) for n in range(147,161)),
            'customer_preservation','private_acceptance','grant_160','service_activate',
            'workers_proxy_activate','service_adopt','backup_post-migration','clear_provider_boot','clear_interlock']
        self.assertEqual([f.calls.index(s) for s in sequence],sorted(f.calls.index(s) for s in sequence))
        self.assertNotIn('grant_150',f.calls)
        self.assertNotIn('service_publish',f.calls)
        self.assertEqual(f.provider.binding['target_schema'],160)
        self.assertEqual(f.provider.binding['operation'],RECONCILED.operation)

    def test_each_irreversible_failure_preserves_fence_and_never_runs_later_effects(self):
        for fault,forbidden in [('provider_fence','parent_sql'),('backup_pre-migration','service_prepare'),
                ('seal_stage','parent_sql'),('committed_147','private_acceptance'),
                ('committed_150','grant_150'),('private_acceptance','grant_150'),
                ('service_activate','workers_proxy_activate'),('workers_proxy_activate','clear_provider_boot'),
                ('clear_provider_boot','restore_timers')]:
            with self.subTest(fault=fault):
                nested=unittest.TestCase();f=maintenance_fixture(nested)
                try:
                    f.failure=fault
                    with self.assertRaises(RuntimeError):f.driver._execute()
                    self.assertNotIn(forbidden,f.calls)
                    self.assertFalse((f.root/'normal-completion.json').exists())
                    self.assertEqual(f.mode,'READ_ONLY');self.assertEqual(f.origin,'READ_ONLY')
                    self.assertIsNone(f.driver.lock);self.assertIsNone(f.ops.deploy_lock_descriptor)
                finally:nested.doCleanups()

    def test_missing_independent_private_verifiers_stops_before_any_effect(self):
        f=maintenance_fixture(self);f.driver.maintenance_activation_guard=None
        with self.assertRaisesRegex(RuntimeError,'independent_private_verifiers_required'):f.driver._execute()
        self.assertEqual(f.calls,[])

    def test_guarded_profile_is_still_unregistered_even_with_private_callbacks(self):
        from deployment.lib.completed_normal_profile import profile
        with self.assertRaisesRegex(RuntimeError,'operation_profile_invalid'):profile(deletion_contract())
