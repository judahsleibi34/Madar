"""Exact source/admission gates; transport fixtures never confer real authority."""
import copy
import json
import os
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from test_completed_normal_commercial_release import commercial_contract
import test_completed_normal_manual_execution as execution_fixture
from deployment.lib import completed_normal_admission as admission
from deployment.lib import schema148_release as release
from deployment.lib.completed_normal_profile import FENCED,COMMERCIAL,profile,expected_origin_grant
from deployment.lib.migration_executor import MigrationManifest,LockedMigrationExecutor
from test_completed_normal_compose import WEB,cli


def fenced_contract():
    value=commercial_contract()
    value.update(version=5,operation=FENCED.operation,notification_cutover_sha256='d'*64,
                 migration_manifest_sha256=release.MANIFEST_SHA256)
    value['source_roles']['schema']=146;value['database']['schema']=146
    value['candidate'].update(compatible_min=146,compatible_max=148)
    return value


class FencedAdmissionTests(unittest.TestCase):
    def setUp(self):
        import shutil
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.source_root=Path(temporary.name)
        shutil.copytree(WEB/'deployment/releases',self.source_root/'web/deployment/releases')
        for tree in ('database','supabase'):
            for number,name in ((147,'147_fence_notification_delivery_claims.sql'),(148,'148_guard_reservation_reactivation_capacity.sql')):
                source=WEB/tree/'migrations'/name
                if not source.exists():source=Path('/'+tree+'/migrations')/name
                target=self.source_root/'web'/tree/'migrations'/name
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())

    def test_new_profile_is_exact_and_historical_profiles_stay_fixed(self):
        value=fenced_contract();admission.validate_contract(value)
        self.assertIs(profile(value),FENCED)
        self.assertEqual((FENCED.source,FENCED.target,FENCED.migrations),(146,148,(147,148)))
        self.assertEqual((COMMERCIAL.source,COMMERCIAL.target),(144,146))
        self.assertEqual(expected_origin_grant(value,'NORMAL')['compatible_max'],146)
        for field in ('version','operation','notification_cutover_sha256','database_structure_sha256'):
            bad=copy.deepcopy(value);bad.pop(field)
            with self.subTest(field=field),self.assertRaises(RuntimeError):admission.validate_contract(bad)
        for source in (145,147,148,True):
            bad=copy.deepcopy(value);bad['database']['schema']=source
            with self.subTest(schema=source),self.assertRaises(RuntimeError):admission.validate_contract(bad)

    def test_ordinary_manifest_loader_still_rejects_coordinated_sql(self):
        with self.assertRaisesRegex(ValueError,'automatic executor'):
            MigrationManifest.load(WEB/'deployment/releases'/release.MANIFEST,WEB.parent)

    def test_source_and_fresh_authorization_required_before_manifest_admission(self):
        with patch.object(admission,'require_fresh_authorization',side_effect=RuntimeError('unapproved')):
            with self.assertRaisesRegex(RuntimeError,'unapproved'):release.admitted_manifest(self.source_root,fenced_contract())
        with patch.object(admission,'require_fresh_authorization') as authorized:
            manifest=release.admitted_manifest(self.source_root,fenced_contract())
            self.assertTrue(manifest.coordinated)
            self.assertEqual(tuple(m.number for m in manifest.migrations),(147,148));authorized.assert_called_once()
            with self.assertRaisesRegex(RuntimeError,'guard_required'):
                LockedMigrationExecutor(connection_factory=lambda:None,manifest=manifest,state_file=Path('/unused'),backup_dir=Path('/unused'),backup_verifier=lambda _:None)

    def test_manifest_order_bridge_sql_mirror_and_checksum_tamper_refuse(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(WEB/'deployment/releases',root/'web/deployment/releases')
            for row in release.source_manifest(self.source_root)['migrations']:
                for tree in ('database','supabase'):
                    source=WEB/tree/'migrations'/Path(row['path']).name
                    if not source.exists():source=Path('/'+tree+'/migrations')/source.name
                    target=root/'web'/tree/'migrations'/source.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            release.source_manifest(root)
            paths=[root/'web/deployment/releases'/release.MANIFEST,root/'web/deployment/releases'/release.BRIDGE,
                   root/'web/database/migrations/147_fence_notification_delivery_claims.sql',root/'web/supabase/migrations/148_guard_reservation_reactivation_capacity.sql']
            for path in paths:
                original=path.read_bytes();path.write_bytes(original+b'\n')
                with self.subTest(path=path.name),self.assertRaises(RuntimeError):release.source_manifest(root)
                path.write_bytes(original)

    def test_quiescence_missing_unknown_schema_protocol_sessions_locks_and_prepared_refuse(self):
        value={'system_identifier':fenced_contract()['database']['system_identifier'],'schema':146,'protocol':1,
               'processing':0,'expired_processing':0,'other_transactions':0,'prepared_transactions':0,'queue_locks':0}
        release.require_database_quiescence(value,fenced_contract(),146)
        for key in value:
            bad=dict(value);bad[key]=True if isinstance(value[key],int) else 'different-cluster'
            with self.subTest(key=key),self.assertRaises(RuntimeError):release.require_database_quiescence(bad,fenced_contract(),146)
        with self.assertRaises(RuntimeError):release.require_database_quiescence({},fenced_contract(),146)

    def test_consumer_restart_running_missing_unknown_and_policy_tampering_refuse(self):
        old,new='a'*64,'b'*64;image='sha256:'+'c'*64
        policy={'version':1,'operation':'notification-protocol2-exclusive-cutover','legacy_consumers':{old:image}}
        observed={old:{'image':image,'running':False,'restart':'no'},new:{'image':image,'running':True,'restart':'no'}}
        self.assertEqual(release.verify_consumer_inventory(observed,policy,{new})['unknown_consumers'],0)
        for changed in ('running','restart','image','unknown','missing'):
            bad=copy.deepcopy(observed)
            if changed=='unknown':bad['d'*64]=dict(bad[old])
            elif changed=='missing':bad.pop(old)
            else:bad[old][changed]={'running':True,'restart':'always','image':'sha256:'+'d'*64}[changed]
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):release.verify_consumer_inventory(bad,policy,{new})

    def test_installer_and_frozen_entrypoint_measure_new_admission_module(self):
        self.assertIn('lib/schema148_release.py',(WEB/'deployment/bin/madar-install-control-plane').read_text())
        self.assertIn("'schema148_release'",(WEB/'scripts/continue_completed_normal_upgrade.py').read_text())
        self.assertIn('releases/'+FENCED.metadata,(WEB/'deployment/bin/madar-install-control-plane').read_text())

    def test_real_deployment_dispatch_requires_exact_selected_bounds(self):
        value=fenced_contract();sha=value['candidate']['source_sha']
        ops=SimpleNamespace(completed_normal_admission=value,release_root=WEB.parent,verify_source=lambda _:None)
        compatibility=cli.Compatibility.load(WEB/'deployment/releases'/FENCED.metadata)
        with patch('deployment.lib.completed_normal_migration.run_migration',return_value={'verified':True}) as run:
            cli.automatic_migrate_known_good(sha=sha,state_root=Path('/fixture'),compatibility=compatibility,operations=ops)
            run.assert_called_once_with(value,WEB.parent,Path('/fixture'),ops)
        with patch('deployment.lib.completed_normal_migration.run_migration') as run:
            with self.assertRaises(RuntimeError):cli.automatic_migrate_known_good(sha=sha,state_root=Path('/fixture'),compatibility=cli.Compatibility.load(WEB/'deployment/releases'/COMMERCIAL.metadata),operations=ops)
            run.assert_not_called()


class FencedExecutionTests(execution_fixture.ManualExecutionTests):
    source_schema=146;target_schema=148;make_contract=staticmethod(fenced_contract)
    # Historical subclass assertions deliberately remain in their original tests.
    test_only_target_grant_follows_verified_backup_and_actual_sql_completion=None
    test_pre_migration_failures_never_grant_normal=None
    test_post_migration_failure_preserves144_and_revokes_writes=None
    test_changed_retirement_stops_before_candidate_and_sql=None

    def setUp(self):
        super().setUp()
        patcher=patch.object(release,'seal_quiescence',lambda actor:self.effect('quiescence'))
        patcher.start();self.addCleanup(patcher.stop)

    def test_target_grant_requires_quiescence_backup_sql_preservation_and_acceptance(self):
        result=self.driver.execute();self.assertEqual((result['schema'],result['mode']),(148,'NORMAL'))
        for earlier,later in (('quiescence','backup_pre-migration'),('backup_pre-migration','service_migrate'),('customer_preservation','grant_148'),('seal_sql_completion','grant_148')):
            self.assertLess(self.calls.index(earlier),self.calls.index(later))
        self.assertNotIn('grant_146',self.calls)

    def test_every_interrupted_effect_revokes_or_keeps_read_only_without_database_restore(self):
        for failure in ('quiescence','backup_pre-migration','service_migrate','customer_preservation','seal_sql_completion','backup_post-migration'):
            with self.subTest(failure=failure):
                # Each independent attempt uses a new isolated fixture and nonce.
                case=FencedExecutionTests('test_target_grant_requires_quiescence_backup_sql_preservation_and_acceptance')
                case.setUp()
                try:
                    case.failure=failure
                    with self.assertRaises(RuntimeError):case.driver.execute()
                    self.assertEqual(case.mode,'READ_ONLY')
                    self.assertNotIn('grant_146',case.calls)
                    if failure in ('quiescence','backup_pre-migration'):self.assertNotIn('service_migrate',case.calls)
                    self.assertFalse(json.loads((case.root/'failure.json').read_text())['customer_database_restored'])
                finally:case.doCleanups()
