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
