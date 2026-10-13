"""Application-only continuation at144; these are controller tests, not a deployment PASS."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from deployment.lib import completed_normal_admission as admission
from deployment.lib.completed_normal_profile import APPLICATION, MANUAL, profile, expected_origin_grant
from deployment.lib.completed_normal_database import require_normal_migration_boundary
from deployment.lib.release_deployer import Compatibility
from test_completed_normal_manual_profile import manual_contract
from test_completed_normal_manual_execution import ManualExecutionTests
from test_completed_normal_runtime import RuntimeModelTests


def application_contract():
    value=manual_contract()
    value.update(version=3,operation=APPLICATION.operation)
    value['source_roles']['schema']=144
    value['database']['schema']=144
    return value


class ApplicationContractTests(unittest.TestCase):
    def test_no_sql_profile_is_exact144_and_retains_accepted_bridge_range(self):
        value=application_contract();admission.validate_contract(value)
        self.assertIs(profile(value),APPLICATION)
        self.assertEqual(APPLICATION.migrations,())
        self.assertEqual((APPLICATION.source,APPLICATION.target,APPLICATION.minimum),(144,144,136))
        self.assertTrue(APPLICATION.supports(144))
        for schema in (136,142,143,145,True):self.assertFalse(APPLICATION.supports(schema))
        metadata=Path(__file__).resolve().parents[2]/'deployment/releases'/APPLICATION.metadata
        loaded=Compatibility.load(metadata)
        self.assertEqual(loaded.migration_class,'none')
        self.assertTrue(loaded.accepts_schema(144));self.assertFalse(loaded.accepts_schema(142))
        self.assertNotIn('migration_manifest',json.loads(metadata.read_text()))

    def test_historical136_authorization_does_not_authorize144_application(self):
        for field,value in [('version',2),('operation',MANUAL.operation)]:
            c=application_contract();c[field]=value
            with self.assertRaises(RuntimeError):admission.validate_contract(c)
        for field in ('database','source_roles'):
            c=application_contract();c[field]['schema']=136
            with self.assertRaises(RuntimeError):admission.validate_contract(c)

    def test_exact_origin_grant_is144_not_the_historical115_136_grant(self):
        grant=expected_origin_grant(application_contract(),'NORMAL')
        self.assertEqual((grant['schema'],grant['compatible_min'],grant['compatible_max']),(144,136,144))

    def test_app_only_boot_rejects_schema_changes_and_any_sql_intent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c=application_contract()
            require_normal_migration_boundary(c,144,root,root)
            for schema in (136,142,143,145):
                with self.assertRaises(RuntimeError):require_normal_migration_boundary(c,schema,root,root)
            (root/'migration-intent.json').write_text('{}')
            with self.assertRaises(RuntimeError):require_normal_migration_boundary(c,144,root,root)


class ApplicationExecutionTests(ManualExecutionTests):
    source_schema=144
    target_schema=144
    make_contract=staticmethod(application_contract)

    # The inherited fixture exercises the actual coordinator with replaceable
    # host transports. Do not inherit the unrelated SQL-stage assertions.
    test_only_target_grant_follows_verified_backup_and_actual_sql_completion=None
    test_pre_migration_failures_never_grant_normal=None
    test_post_migration_failure_preserves144_and_revokes_writes=None
    test_changed_retirement_stops_before_candidate_and_sql=None

    def setUp(self):
        super().setUp()
        self.ops.state_root.mkdir()
        (self.ops.state_root/'state.json').write_text(json.dumps({'active_slot':'blue','known_good_release':{
            'sha':self.contract['source_roles']['application_sha']}}))
        worker={'version':1,'generation':self.contract['origin']['worker_generation'],'owner':'CANDIDATE',
            'old':{'sha':'b'*40,'slot':'green'},'candidate':{'sha':self.contract['source_roles']['application_sha'],'slot':'blue'}}
        (self.ops.state_root/'worker-ownership.json').write_text(json.dumps(worker))
        (self.ops.state_root/'worker-ownership.json').chmod(0o600)
        self.route=self.base/'route.conf';self.route.write_bytes(b'fixture route\n')
        import hashlib
        self.document['origin_routing_sha256']=hashlib.sha256(self.route.read_bytes()).hexdigest()
        self.document['rollback_source_selection']={}
        from deployment.lib import completed_normal_execution as execution
        def read(path,**kw):
            return self.route if path==Path('/var/lib/madar/proxy/active-upstreams.conf') else path
        p=patch.object(execution,'readonly_configuration',read);p.start();self.addCleanup(p.stop)
        self.ops.resolve_candidate=lambda *a,**kw:self.effect('freeze_source')
        self.ops.stage_candidate=lambda *a,**kw:(self.base,self.base/'rollback-source')
        self.ops.protected_tree_digest=lambda path:'f'*64
        def rollback():
            self.mode='READ_ONLY';self.origin='NORMAL';self.effect('rollback_origin')
        self.driver.rollback_application_origin=rollback

    def test_successor_uses_existing_phases_but_never_calls_migration_or_refresh(self):
        result=self.driver.execute()
        self.assertEqual((result['schema'],result['mode'],result['sql_executed']),(144,'NORMAL',False))
        self.assertNotIn('service_migrate',self.calls);self.assertNotIn('service_refresh',self.calls)
        self.assertNotIn('seal_sql_intent',self.calls);self.assertNotIn('seal_sql_completion',self.calls)
        self.assertNotIn('backup_inputs',self.calls)
        self.assertLess(self.calls.index('fence_origin'),self.calls.index('service_activate'))
        self.assertLess(self.calls.index('service_adopt'),self.calls.index('grant_144'))
        self.assertLess(self.calls.index('backup_pre-migration'),self.calls.index('grant_144'))
        self.assertEqual((self.schema,self.mode,self.owners),(144,'NORMAL',1))

    def test_failed_admission_does_not_fence_or_replace_original_normal(self):
        self.failure='admit'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual((self.schema,self.origin),(144,'NORMAL'))
        self.assertNotIn('fence_origin',self.calls);self.assertNotIn('controller_install',self.calls)

    def test_failed_backup_and_interrupted_handoff_remain_fenced_without_sql(self):
        for boundary in ('service_activate','backup_pre-migration','backup_post-migration'):
            with self.subTest(boundary=boundary):
                self.setUp();self.failure=boundary
                with self.assertRaises(RuntimeError):self.driver.execute()
                self.assertEqual(self.schema,144);self.assertEqual(self.mode,'READ_ONLY')
                self.assertNotIn('service_migrate',self.calls)
                self.assertNotIn('seal_sql_intent',self.calls)

    def test_rejected_rollback_uses_existing_fenced_compensation(self):
        self.failure='backup_post-migration'
        def rejected():raise RuntimeError('rollback_identity_changed')
        self.driver.rollback_application_origin=rejected
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual((self.schema,self.mode),(144,'READ_ONLY'))
        evidence=json.loads((self.root/'failure.json').read_text())
        self.assertEqual(evidence['compensation_exception_type'],'RuntimeError')
        self.assertFalse(evidence['customer_database_restored'])

    def test_rollback_rejects_schema_advancement_before_any_effect(self):
        from deployment.lib.completed_normal_execution import CompletedNormalUpgrade
        from deployment.lib import completed_normal_admission as a
        from deployment.lib import active_recovery_inputs as inputs
        self.driver.lock=object();self.driver.admitted=True
        self.driver.preparation_source=lambda:None
        self.driver.actor.native=lambda:145
        with patch.object(a,'verify_history',lambda contract:None):
            with self.assertRaisesRegex(RuntimeError,'application_rollback_schema_changed'):
                CompletedNormalUpgrade.rollback_application_origin(self.driver)
        self.assertNotIn('rollback_origin',self.calls)


class ApplicationRuntimeTests(unittest.TestCase):
    def setUp(self):
        fixture=RuntimeModelTests();fixture.setUp();self.fixture=fixture
        old=fixture.contract;fixture.contract=application_contract()
        old_context=admission.digest(old);context=admission.digest(fixture.contract)
        for role in fixture.model['services']:
            service=fixture.model['services'][role];row=fixture.rows[service['container_name']]
            if service['environment']:
                service['environment'].update(MADAR_BUSINESS_WRITE_CONTRACT=context,
                    SCHEMA_COMPATIBLE_MIN='136',SCHEMA_COMPATIBLE_MAX='144',SCHEMA_EXCLUDED_VERSIONS='142')
                service['volumes'][0]['source']=str(admission.ADMISSIONS/context/'write-authority')
                row['Mounts'][0]['Source']=service['volumes'][0]['source']
                row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]
        # Rebind the context-derived Docker names and network declarations.
        from deployment.lib.completed_normal_resources import allocation
        new=allocation(fixture.contract,'green');rows={}
        old_network=fixture.selected['networks']['default'];new_network=new['networks']['default']
        fixture.model['networks']['default']['name']=new_network
        for role,service in fixture.model['services'].items():
            row=fixture.rows[service['container_name']];name=new['containers'][role]
            service['container_name']=name;row['Name']='/'+name
            row['Config']['Labels']['com.docker.compose.project']=new['project']
            row['HostConfig']['NetworkMode']=new_network
            endpoint=row['NetworkSettings']['Networks'].pop(old_network)
            endpoint['Aliases']=[name,role];row['NetworkSettings']['Networks'][new_network]=endpoint
            rows[name]=row
        fixture.rows=rows;fixture.selected=new

    def test_actual_bound144_compose_model_is_accepted(self):
        self.fixture.validate()

    def test_stale_range_or_writable_authority_mount_is_rejected(self):
        f=self.fixture;service=f.model['services']['backend']
        for minimum,maximum in (('115','136'),('144','144'),('136','145')):
            with self.subTest(bounds=(minimum,maximum)):
                original=copy.deepcopy(service['environment'])
                service['environment'].update(SCHEMA_COMPATIBLE_MIN=minimum,SCHEMA_COMPATIBLE_MAX=maximum)
                row=f.rows[service['container_name']];row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]
                with self.assertRaises(RuntimeError):f.validate()
                service['environment']=original;row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in original.items())]
        service['volumes'][0]['read_only']=False
        f.rows[service['container_name']]['Mounts'][0]['RW']=True
        with self.assertRaises(RuntimeError):f.validate()


class ApplicationDeploymentContractTests(unittest.TestCase):
    def test_no_sql_metadata_is_owned_by_controller_not_changed_application(self):
        import test_completed_normal_compose as f
        from deployment.lib import provider_recovery_runtime as protection
        c=application_contract()
        ops=f.cli.DockerGitOperations(f.WEB.parent,Path('/unused-state'),Path('/unused-env'),
            f.cli.Compatibility.load(f.WEB/'deployment/releases'/APPLICATION.metadata),
            metadata_filename=APPLICATION.metadata)
        ops.completed_normal_admission=c
        ops.release_root=Path('/immutable-accepted-application')
        with patch.object(admission,'require_candidate_authority') as authority, \
                patch.object(protection,'readonly_configuration',side_effect=lambda p,**kw:p):
            self.assertEqual(ops.release_metadata_path(),f.WEB/'deployment/releases'/APPLICATION.metadata)
            self.assertEqual(f.cli.plan_release_migrations(sha=c['candidate']['source_sha'],schema=144,
                compatibility=ops.compatibility,operations=ops),[])
            self.assertTrue(authority.called)
            ops.metadata_filename='schema-136-144-learning-bridge.json'
            with self.assertRaisesRegex(RuntimeError,'application_only_release_contract_changed'):
                ops.release_metadata_path()
        with patch.object(admission,'require_candidate_authority',side_effect=RuntimeError('grant_invalid')):
            with self.assertRaisesRegex(RuntimeError,'grant_invalid'):ops.release_metadata_path()


if __name__=='__main__':unittest.main()
