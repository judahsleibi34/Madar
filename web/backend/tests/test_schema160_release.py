"""Canonical source/protocol checks; these tests issue no release authority."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from deployment.lib import schema160_release as release
from deployment.lib import schema150_release as historical
from deployment.lib.completed_normal_admission import validate_provider_preparation
from deployment.lib.completed_normal_profile import RECONCILED, DELETION, profile
from deployment.lib.completed_normal_migration import intent_document
from deployment.lib.migration_executor import MigrationManifest
from deployment.lib.schema150_provider_lifecycle import validate_binding, binding_profile, release_contract
from deployment.lib import schema150_provider_adapter as adapter
from deployment.lib import schema150_provider_lifecycle as lifecycle
from deployment.lib.migration_executor import Migration
from test_schema150_admission import deletion_contract


def reconciled_contract():
    value=deletion_contract()
    value.update(operation=RECONCILED.operation,version=8,migration_manifest_sha256=release.MANIFEST_SHA256)
    value['candidate']['compatible_max']=160
    return value


class Schema160ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        web=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
        shutil.copytree(web/'deployment/releases',self.root/'web/deployment/releases')
        raw=json.loads((web/'deployment/releases'/release.MANIFEST).read_bytes())
        for row in raw['migrations']:
            for tree in ('database','supabase'):
                relative=Path(row['path'].replace('/database/','/'+tree+'/'))
                source=web/relative.relative_to('web')
                if not source.exists():source=Path('/'+tree+'/migrations')/relative.name
                target=self.root/relative;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(source.read_bytes())

    def test_exact_active_chain_with_no_history_or_authority_reinterpretation(self):
        raw, snapshots=release.captured_source(self.root)
        self.assertEqual(list(snapshots),list(range(147,161)))
        self.assertIn(b'public.data_datasets',snapshots[147])
        self.assertIn(b'notification_deliveries',snapshots[157])
        self.assertEqual(validate_provider_preparation(reconciled_contract()),RECONCILED)
        self.assertEqual(intent_document(reconciled_contract())['target_schema'],160)
        for contract in (reconciled_contract(),deletion_contract()):
            with self.assertRaises(RuntimeError):profile(contract)
            with self.assertRaisesRegex(RuntimeError,'integration_incomplete'):
                release.admitted_manifest(self.root,contract)
        with self.assertRaisesRegex(RuntimeError,'integration_incomplete'):
            historical.admitted_manifest(self.root,reconciled_contract())
        manifest=self.root/'web/deployment/releases'/release.MANIFEST
        with self.assertRaisesRegex(ValueError,'not executable'):MigrationManifest.load(manifest,self.root)
        raw['execution_status']='approved';manifest.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError,'not executable'):MigrationManifest.load(manifest,self.root)

    def test_root_authority_parser_binds_v3_without_registering_preparation(self):
        from deployment.lib import completed_normal_admission as admission
        contract=reconciled_contract();root=self.root/admission.digest(contract)
        (root/'write-authority').mkdir(parents=True)
        grant={'version':3,'schema':160,'release_sha':contract['candidate']['source_sha'],
            'contract_digest':admission.digest(contract),'mode':'NORMAL','compatible_min':146,'compatible_max':160,
            'operation':RECONCILED.operation,'origin_schema':146,'controller_sha':contract['candidate']['controller_sha'],
            'migration_manifest_sha256':contract['migration_manifest_sha256']}
        path=root/'write-authority/authority.json'
        # Model-only file ownership and registry; the actual registry stays shut.
        with patch.object(admission,'profile',return_value=RECONCILED),patch.object(admission.os,'geteuid',return_value=0),\
                patch('deployment.lib.provider_recovery_runtime.protected',side_effect=lambda p,**kw:Path(p)):
            path.write_text(json.dumps(grant))
            self.assertEqual(admission.require_candidate_authority(contract,mode='NORMAL',admissions=self.root),grant)
            from services import business_write_authority as backend
            from types import SimpleNamespace
            with patch.object(backend,'AUTHORITY_PATH',path),patch.dict(os.environ,{
                    'MADAR_BUSINESS_WRITE_AUTHORITY':str(path),'MADAR_BUSINESS_WRITE_CONTRACT':grant['contract_digest'],
                    'MADAR_RELEASE_SHA':grant['release_sha'],'SCHEMA_COMPATIBLE_MIN':'146','SCHEMA_COMPATIBLE_MAX':'160',
                    'SCHEMA_EXCLUDED_VERSIONS':'','MADAR_RELEASE_CONTROLLER_SHA':grant['controller_sha'],
                    'MADAR_RELEASE_MIGRATION_MANIFEST_SHA256':grant['migration_manifest_sha256']}),\
                    patch.object(Path,'lstat',return_value=SimpleNamespace(st_uid=0,st_mode=0o100644)),\
                    patch.object(Path,'is_symlink',return_value=False):
                self.assertEqual(backend.read_authority(),grant)
            for field,value in (('version',2),('controller_sha','f'*40),('origin_schema',150),
                    ('operation',DELETION.operation),('migration_manifest_sha256','f'*64),('schema',159)):
                path.write_text(json.dumps(dict(grant,**{field:value})))
                with self.subTest(field=field),self.assertRaises(RuntimeError):
                    admission.require_candidate_authority(contract,admissions=self.root)
        with self.assertRaises(RuntimeError):profile(contract)

    def test_changed_sql_mirror_manifest_and_parent_symlink_refuse(self):
        raw,snapshots=release.captured_source(self.root)
        paths=[self.root/'web/deployment/releases'/release.MANIFEST,
               self.root/'web/deployment/releases'/release.BRIDGE]
        for row in raw['migrations']:
            paths.extend((self.root/row['path'],self.root/row['path'].replace('/database/','/supabase/')))
        for path in paths:
            original=path.read_bytes();path.write_bytes(original+b'\n')
            with self.subTest(path=path),self.assertRaises(RuntimeError):release.captured_source(self.root)
            path.write_bytes(original)
        parent=self.root/'web/database/migrations';parent.rename(self.root/'renamed')
        parent.symlink_to(self.root/'renamed',target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,'path_invalid'):release.captured_source(self.root)
        self.assertEqual(snapshots[160],(self.root/'renamed'/Path(raw['migrations'][-1]['path']).name).read_bytes())

    def test_preparation_rejects_old_manifest_and_numeric_or_operation_widening(self):
        for field,value in (('version',7),('operation',DELETION.operation),
                            ('migration_manifest_sha256',historical.MANIFEST_SHA256)):
            contract=reconciled_contract();contract[field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):validate_provider_preparation(contract)
        for target in (150,159,161,160.0,True):
            contract=reconciled_contract();contract['candidate']['compatible_max']=target
            with self.subTest(target=target),self.assertRaises(RuntimeError):validate_provider_preparation(contract)

    def test_exact_binding_dispatch_never_selects_by_schema_alone(self):
        from test_schema150_actor_inventory import binding
        original=binding();canonical=dict(original,operation=RECONCILED.operation,target_schema=160)
        self.assertEqual(binding_profile(canonical),RECONCILED)
        self.assertIs(release_contract(canonical),release)
        self.assertIs(release_contract(original),historical)
        for mixed in (dict(original,target_schema=160),dict(canonical,target_schema=150),
                      dict(canonical,operation='arbitrary'),dict(canonical,target_schema=160.0)):
            with self.subTest(mixed=mixed),self.assertRaises(RuntimeError):validate_binding(mixed)

    def test_all_fourteen_protocol_boundaries_and_every_quiescence_counter(self):
        contract=reconciled_contract()
        for schema in range(146,161):
            value={'schema':schema,'system_identifier':contract['database']['system_identifier'],
                **release.expected_protocols(schema),**dict.fromkeys(release.COUNTERS,0)}
            release.require_database_quiescence(value,contract,schema)
            for key in value:
                bad=copy.deepcopy(value);bad[key]=True if type(value[key]) is int else 'wrong'
                with self.subTest(schema=schema,key=key),self.assertRaises(RuntimeError):
                    release.require_database_quiescence(bad,contract,schema)
            for key in release.COUNTERS:
                with self.subTest(schema=schema,key=key),self.assertRaises(RuntimeError):
                    release.require_database_quiescence(dict(value,**{key:1}),contract,schema)
        self.assertEqual(release.expected_protocols(156),dict(delivery_protocol=1,outbox_protocol=1,deletion_protocol=0))
        self.assertEqual(release.expected_protocols(158),dict(delivery_protocol=2,outbox_protocol=1,deletion_protocol=0))
        self.assertIn('<160',release.QUIESCENCE_SQL)
        self.assertIn('<150',historical.QUIESCENCE_SQL)
        for schema in (145,161,160.0,True,None):
            with self.subTest(schema=schema),self.assertRaises(RuntimeError):release.expected_protocols(schema)

    def test_only_exact160_three_protocol2_accepts_target(self):
        release.require_target_protocols(160,2,2,2)
        for values in ((150,2,2,2),(159,2,2,2),(161,2,2,2),(160,2,2,1),(160,2,1,2),
                       (160,1,2,2),(160.0,2,2,2),(160,2,True,2)):
            with self.subTest(values=values),self.assertRaises(RuntimeError):release.require_target_protocols(*values)

    def test_existing_concrete_adapter_guards_exact_canonical_rows_on_same_cursor(self):
        from test_schema150_actor_inventory import binding
        actor=adapter.Schema150ProviderAdapter.__new__(adapter.Schema150ProviderAdapter)
        actor.contract=reconciled_contract()
        actor.binding=dict(binding(),operation=RECONCILED.operation,target_schema=160)
        actor.root=self.root;actor.require_authority=Mock();actor._require_migration_session_lock=Mock()
        cursor=object()
        raw,_=release.captured_source(self.root)
        with patch.object(lifecycle,'ProviderMaintenance150') as factory, patch.object(lifecycle,'ProtectedProviderJournal',lambda p:p):
            for row in raw['migrations']:
                migration=Migration(row['number'],self.root/row['path'],row['sha256'],row['from_schema'],row['to_schema'],row['compatibility'])
                actor.migration_guard(cursor,migration)
                factory.return_value.migration_entry.assert_called_with(row['from_schema'],row['to_schema'],cursor=cursor)
                actor._require_migration_session_lock.assert_called_with(cursor)
            calls=actor.require_authority.call_count
            for migration in (Migration(147,Path('historical'),historical.SQL_SHA256[147],146,147,'coordinated'),
                Migration(157,Path('substituted'),'0'*64,156,157,'coordinated'),
                Migration(157,Path('wrong-order'),release.SQL_CONTRACT[157][0],155,157,'coordinated'),
                Migration(161,Path('future'),'0'*64,160,161,'coordinated')):
                with self.subTest(number=migration.number),self.assertRaisesRegex(RuntimeError,'migration_contract_changed'):
                    actor.migration_guard(cursor,migration)
            self.assertEqual(actor.require_authority.call_count,calls)
