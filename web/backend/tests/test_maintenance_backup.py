"""Real filesystem/archive checks; isolated database proof is a separate drill."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from scripts import backup_support as backup
from deployment.lib.maintenance_backup import seal_capture, private_copy
from deployment.lib.schema150_object_inventory import measure_roots,archive_roots
from deployment.lib.schema150_actor_inventory import REQUIRED_OBJECT_ROOTS
from deployment.lib import completed_normal_profile as profiles
from deployment.lib.schema150_release import admitted_manifest
from deployment.lib.completed_normal_admission import digest as profiles_json_digest


class MaintenanceBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'backup';self.data.mkdir()
        self.binding={'operation':profiles.DELETION.operation,'context_sha256':'a'*64,'source_sha':'b'*40,
            'controller_sha':'c'*40,'inventory_sha256':'d'*64,'system_identifier':'731','source_schema':146,'target_schema':150}
        self.roots={}
        for name in sorted(REQUIRED_OBJECT_ROOTS):
            directory=self.root/name;directory.mkdir();self.roots[name]={'type':'bind','source':str(directory),'content_sha256':'e'*64}
            if name!='database':
                (directory/'empty').mkdir();(directory/'nested').mkdir()
                (directory/'nested'/'asset').write_bytes(b'synthetic-'+name.encode())
        # Include xattrs when supported; raw values never enter assertions/logs.
        try:os.setxattr(self.root/'provider_storage/nested/asset','user.synthetic',b'metadata')
        except OSError:pass
        for name in backup.FILE_SETS:(self.data/'files'/name).mkdir(parents=True)
        for name,body in {'backup.env':'MADAR_BACKUP_FORMAT=3\n','database.dump':'synthetic-not-a-dump',
                'BACKUP_COMPLETE':'complete','MANIFEST.txt':'synthetic','CONFIGURATION-INVENTORY.txt':'separate escrow'}.items():
            (self.data/name).write_text(body)
        self.manifest={'format_version':3,'status':'complete','backup_id':'madar-20261020T000000Z',
            'created_at':'20261020T000000Z','release':{'git_sha':'b'*40},'database':{'dump':'database.dump','schema_version':'146'},
            'checksums':'SHA256SUMS','configuration':{'values_included':False},'file_sets':list(backup.FILE_SETS),
            'recovery':{'provider_objects_required':False}}
        (self.data/'manifest.json').write_text(json.dumps(self.manifest));self.reseal()
        self.enterContext(patch.object(backup.subprocess,'run',return_value=SimpleNamespace(returncode=0)))
        self.before=measure_roots(self.roots,phase='fenced')
        self.roles=b'CREATE ROLE postgres;\nALTER ROLE postgres WITH SUPERUSER LOGIN;\n'
    def reseal(self):
        rows=backup.inventory(self.data);rows.pop('SHA256SUMS',None)
        (self.data/'SHA256SUMS').write_text(''.join(d+'  '+n+'\n' for n,d in sorted(rows.items())))
    def seal(self,**changes):
        args=dict(binding=self.binding,stage='pre-migration',original_roles=self.roles,
            roles_snapshot={'roles':{},'memberships':[],'settings':[]},bootstrap_role='postgres',
            roots=self.roots,previous=self.before,database_fingerprint='f'*64,
            recovery={'origin_source_sha':'a'*40,'origin_images':{'backend':'sha256:'+'1'*64,'frontend':'sha256:'+'2'*64},
                'candidate_images':{'backend':'sha256:'+'3'*64,'frontend':'sha256:'+'4'*64},'database_image':'sha256:'+'5'*64,
                'migration_manifest_sha256':'6'*64,'controller_tree_sha256':'7'*64,
                'configuration_sha256':{'synthetic':'8'*64},'configuration_escrow_required':True})
        args.update(changes);return seal_capture(self.data,**args)
    def test_native_forest_and_original_roles_are_bound_in_ordinary_backup(self):
        digest=self.seal();outer=backup.verify(self.data)
        value=backup.verify_maintenance(self.data,expected_sha256=digest)
        self.assertEqual(outer['maintenance_backup'],'maintenance/manifest.json')
        self.assertEqual(value['binding'],self.binding);self.assertFalse(value['authority_issued'])
        self.assertEqual((self.data/'maintenance/roles.sql').read_bytes(),self.roles)
        with tarfile.open(self.data/'maintenance/objects.tar.gz','r:gz') as archive:
            members=archive.getmembers();self.assertFalse(any(m.name.startswith('database/') for m in members))
            self.assertTrue(any('madar.xattrs.base64' in m.pax_headers for m in members))

    def migration_context(self):
        """Actual files/archives/flock, MODEL authority and restore/replica results.

        This exercises the existing backup-to-credential boundary, not an SQL
        executor or a privileged controller acceptance claim.
        """
        from unittest.mock import Mock
        from test_schema150_admission import deletion_contract
        from deployment.lib import completed_normal_backup as context_module
        from deployment.lib import schema150_provider_lifecycle as lifecycle
        from deployment.lib import schema149_provider_lifecycle as journal_module
        contract=deletion_contract()
        contract['candidate'].update(source_sha=self.binding['source_sha'],controller_sha=self.binding['controller_sha'])
        contract['writer_inventory_sha256']=self.binding['inventory_sha256']
        self.binding['context_sha256']=context_module.digest(contract)
        expected=self.seal()
        context=context_module.CompletedNormalBackupContext.__new__(context_module.CompletedNormalBackupContext)
        context.contract=contract;context.profile=profiles.DELETION;context.root=self.root
        context.context=self.binding['context_sha256'];context.stage='pre-migration';context.schema=146
        context.scope=context_module.digest({'operation':profiles.DELETION.operation,'context_sha256':context.context,'backup_stage':context.stage})
        context.receipt_name='pre-migration-backup.json';context.guard=Mock()
        context.plan=SimpleNamespace(source_sha=self.binding['source_sha'],candidate_images={'backend':'synthetic','frontend':'synthetic'})
        context.provider_adapter=SimpleNamespace(binding=self.binding)
        context.document={}
        self.enterContext(patch.object(context_module,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(context_module,'readonly_configuration',lambda p,**kw:Path(p)))
        self.enterContext(patch('deployment.lib.schema150_provider_adapter.protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(journal_module,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(journal_module,'require_root_directory',lambda p:None))
        journal_root=self.root/'provider-journal';journal_root.mkdir(mode=0o700)
        journal=lifecycle.ProtectedProviderJournal(journal_root)
        journal.append('prepared',{'binding':self.binding,'preimage':{'synthetic':'MODEL ONLY'}})
        for step in lifecycle.FENCE_STEPS:
            journal.append('effect_intent',{'step':step});journal.append('effect_complete',{'step':step})
        restored={'status':'logical_database_and_file_restore_passed','backup_schema':146,
            'maintenance_manifest_sha256':expected,**{k:True for k in
                ('role_attributes_restored','ownership_and_acls_restored','database_fingerprint_verified','native_object_bytes_restored')}}
        receipt={'schema':146,'context_sha256':context.context,'plan_sha256':context.scope,
            'source_sha':context.plan.source_sha,'images':context.plan.candidate_images,'restore':restored,
            'node1':{'checksum_exit_code':0,'maintenance_manifest_sha256':expected},'local_path':str(self.data),
            'maintenance_manifest_sha256':expected,'sha256sums_sha256':backup.digest(self.data/'SHA256SUMS')}
        def publish():
            (self.root/context.receipt_name).write_text(json.dumps(receipt))
            (self.root/'pre-migration-maintenance-backup-input.json').write_text(json.dumps({
                'version':1,'context_sha256':context.context,'scope':context.scope,'stage':context.stage,
                'backup_id':self.data.name,'manifest_sha256':expected}))
        publish()
        return context,receipt,journal,publish

    def test_existing_backup_context_seals_original_role_digest_and_fenced_provider_witness(self):
        context,receipt,journal,_=self.migration_context()
        value=context.seal_migration_inputs(receipt)
        self.assertEqual(value['intent']['target_schema'],150)
        self.assertEqual(value['maintenance_manifest_sha256'],receipt['maintenance_manifest_sha256'])
        self.assertEqual(value['provider_maintenance']['binding'],self.binding)
        self.assertEqual(value['provider_maintenance']['journal_sha256'],profiles_json_digest(journal.read()))
        self.assertEqual(json.loads((self.root/'migration-inputs.json').read_bytes()),value)
        self.assertEqual(context.guard.call_count,3)
        with self.assertRaises(FileExistsError):context.seal_migration_inputs(receipt)

    def test_migration_input_seal_refuses_missing_modified_or_incomplete_maintenance_proof(self):
        context,receipt,_,publish=self.migration_context()
        original=copy.deepcopy(receipt)
        mutations=[lambda r:r.pop('maintenance_manifest_sha256'),
            lambda r:r['restore'].update(maintenance_manifest_sha256='0'*64),
            lambda r:r['node1'].update(maintenance_manifest_sha256='0'*64),
            lambda r:r.update(sha256sums_sha256='0'*64)]
        mutations.extend(lambda r,key=key:r['restore'].update({key:False}) for key in
            ('role_attributes_restored','ownership_and_acls_restored','database_fingerprint_verified','native_object_bytes_restored'))
        for mutate in mutations:
            receipt.clear();receipt.update(copy.deepcopy(original));mutate(receipt);publish()
            with self.subTest(receipt=receipt),self.assertRaises(RuntimeError):context.seal_migration_inputs(receipt)
            self.assertFalse((self.root/'migration-inputs.json').exists())

    def test_pending_provider_effect_prevents_migration_credential_publication(self):
        context,receipt,journal,_=self.migration_context()
        journal.append('effect_intent',{'step':'restore_roles_private'})
        with self.assertRaisesRegex(RuntimeError,'provider_fence_incomplete'):context.seal_migration_inputs(receipt)
        self.assertFalse((self.root/'migration-inputs.json').exists())

    def test_changed_journal_during_backup_verification_prevents_publication(self):
        context,receipt,journal,_=self.migration_context()
        def guard():
            if context.guard.call_count==3:journal.append('quiescence',{'synthetic':'MODEL ONLY'})
        context.guard.side_effect=guard
        with self.assertRaisesRegex(RuntimeError,'provider_journal_changed'):context.seal_migration_inputs(receipt)
        self.assertFalse((self.root/'migration-inputs.json').exists())
    def test_changed_source_origin_stage_or_output_cannot_be_resealed(self):
        for changes in ({'binding':dict(self.binding,source_sha='c'*40)}, {'stage':'post-migration'}):
            with self.subTest(changes=changes),self.assertRaisesRegex(RuntimeError,'binding_invalid'):
                self.seal(**changes)
        digest=self.seal()
        with self.assertRaisesRegex(RuntimeError,'extension_already_exists'):self.seal()
        self.assertEqual(backup.verify_maintenance(self.data,expected_sha256=digest)['schema'],146)
    def test_current_nologin_substitution_truncation_and_wrong_digest_refuse(self):
        digest=self.seal()
        for body in (self.roles.replace(b'LOGIN;',b'NOLOGIN;'),self.roles[:-8]):
            (self.data/'maintenance/roles.sql').write_bytes(body)
            with self.assertRaises(backup.BackupError):backup.verify_maintenance(self.data,expected_sha256=digest)
        with self.assertRaisesRegex(backup.BackupError,'manifest_changed'):
            backup.verify_maintenance(self.data,expected_sha256='0'*64)

    def test_expected_inner_digest_and_parsed_metadata_use_the_same_bytes(self):
        expected=self.seal();target=self.data/'maintenance/manifest.json'
        original=backup.digest
        def substitute(path):
            value=original(path)
            if Path(path)==target:
                changed=json.loads(target.read_bytes());changed['database_fingerprint']='0'*64
                target.write_text(json.dumps(changed))
            return value
        with patch.object(backup,'digest',side_effect=substitute):
            observed=backup.verify_maintenance(self.data,expected_sha256=expected)
        self.assertEqual(observed['database_fingerprint'],'f'*64,
                         'Authenticated metadata must not be reopened after checksum validation')
    def test_missing_or_changed_native_object_bytes_refuse(self):
        digest=self.seal();path=self.data/'maintenance/objects.tar.gz'
        body=path.read_bytes();path.write_bytes(body[:-15])
        with self.assertRaises(backup.BackupError):backup.verify_maintenance(self.data,expected_sha256=digest)
        path.unlink()
        with self.assertRaises((backup.BackupError,FileNotFoundError)):
            backup.verify_maintenance(self.data,expected_sha256=digest)
    def test_missing_member_and_undeclared_extension_refuse(self):
        self.seal();(self.data/'maintenance/roles-snapshot.json').unlink()
        with self.assertRaisesRegex(backup.BackupError,'inventory_invalid'):backup.verify_maintenance(self.data)
        manifest=json.loads((self.data/'manifest.json').read_text());manifest.pop('maintenance_backup')
        (self.data/'manifest.json').write_text(json.dumps(manifest));self.reseal()
        with self.assertRaisesRegex(backup.BackupError,'undeclared_maintenance'):backup.verify(self.data,dump=False)
    def test_archive_rejects_special_or_changed_roots_and_keeps_partial_evidence(self):
        (self.root/'provider_storage'/'escape').symlink_to('/etc/passwd')
        path=self.root/'unsafe.tar.gz'
        with self.assertRaisesRegex(RuntimeError,'special_or_linked'):archive_roots(self.roots,path,previous=self.before)
        self.assertFalse(path.exists())
    def test_database_bytes_are_never_archived(self):
        (self.root/'database'/'live').symlink_to('/etc/passwd')
        self.seal()  # Identity-only DB root, even when its bytes cannot be walked.
    def test_protected_profile_still_rejects_operational_admission(self):
        with self.assertRaisesRegex(RuntimeError,'profile_invalid'):
            profiles.profile({'version':7,'operation':profiles.DELETION.operation})
        with self.assertRaisesRegex(RuntimeError,'integration_incomplete'):admitted_manifest(None,None)

    def test_private_copy_has_no_links_and_refuses_replay_or_changed_input(self):
        source=self.root/'incoming';source.mkdir();(source/'dump').write_bytes(b'original')
        target=self.root/'private-copy';private_copy(source,target)
        self.assertEqual((target/'dump').read_bytes(),b'original')
        with self.assertRaises(FileExistsError):private_copy(source,target)
        (source/'escape').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(RuntimeError,'link_or_special'):private_copy(source,self.root/'rejected')
        self.assertTrue((self.root/'rejected').exists())

    def test_acl_order_is_irrelevant_but_privileges_and_null_defaults_are_not(self):
        def query(acl):
            def invoke(body):
                if body.startswith('SELECT coalesce(json_agg'):
                    return json.dumps([{'schema':'public','name':'fixture','kind':'r'}])
                return json.dumps(['fixture',1,'a'*64])+'\n'+json.dumps({'database':['postgres','owner',acl],
                    'relations':[['public','fixture','r','owner',acl,False,False]],
                    'schemas':[['public','owner',acl]],'functions':[]})
            return invoke
        a=backup.database_fingerprint(query(['reader=r/owner','owner=arwdDxt/owner']))
        self.assertEqual(a,backup.database_fingerprint(query(['owner=arwdDxt/owner','reader=r/owner'])))
        self.assertNotEqual(a,backup.database_fingerprint(query(['reader=rw/owner','owner=arwdDxt/owner'])))
        self.assertNotEqual(backup.database_fingerprint(query(None)),backup.database_fingerprint(query([])))

if __name__=='__main__':unittest.main()
