"""Canonical checkpoint bytes and transport refusals, not restoration acceptance."""
import json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from deployment.lib import active_recovery_backup as pipeline
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_profile import RECONCILED
from deployment.lib.schema160_release import MANIFEST_SHA256
from scripts import backup_support as backup
with patch.dict(sys.modules,{'backup_support':backup}):
    from scripts import normal_backup_replica as receiver


class CanonicalCheckpointTests(unittest.TestCase):
    def fixture(self,schema=160,*,operation=RECONCILED.operation,manifest=MANIFEST_SHA256):
        from test_maintenance_backup import MaintenanceBackupTests
        f=MaintenanceBackupTests();f.setUp();self.addCleanup(f.doCleanups)
        f.binding.update(operation=operation,target_schema=160)
        f.manifest['database']['schema_version']=str(schema)
        (f.data/'manifest.json').write_text(json.dumps(f.manifest));f.reseal()
        recovery={'origin_source_sha':'a'*40,'origin_images':{'backend':'sha256:'+'1'*64,'frontend':'sha256:'+'2'*64},
            'candidate_images':{'backend':'sha256:'+'3'*64,'frontend':'sha256:'+'4'*64},'database_image':'sha256:'+'5'*64,
            'migration_manifest_sha256':manifest,'controller_tree_sha256':'7'*64,
            'configuration_sha256':{'synthetic':'8'*64},'configuration_escrow_required':True}
        stage='pre-migration' if schema==146 else 'post-migration'
        checksum=f.seal(stage=stage,recovery=recovery)
        scope=digest({'operation':operation,'context_sha256':f.binding['context_sha256'],'backup_stage':stage})
        return f,checksum,scope

    def test_source_and_target_checkpoints_bind_canonical_manifest_and_transfer_scope(self):
        for schema in (146,160):
            f,checksum,scope=self.fixture(schema)
            value=backup.verify_reconciled_maintenance(f.data,expected_sha256=checksum,schema=schema,scope=scope)
            self.assertEqual(value['schema'],schema);self.assertEqual(value['binding'],f.binding)
            self.assertFalse(value['authority_issued'])

    def test_wrong_or_missing_approval_digest_scope_schema_and_manifest_refuse(self):
        f,checksum,scope=self.fixture()
        for changes in ({'expected_sha256':None},{'expected_sha256':'f'*64},{'scope':'f'*64},
                        {'schema':146},{'schema':159},{'schema':True}):
            args=dict(expected_sha256=checksum,schema=160,scope=scope);args.update(changes)
            with self.subTest(changes=changes),self.assertRaises(backup.BackupError):backup.verify_reconciled_maintenance(f.data,**args)
        for changes in ({'manifest':'6'*64},):
            f,checksum,scope=self.fixture(**changes)
            with self.subTest(changes=changes),self.assertRaises(backup.BackupError):
                backup.verify_reconciled_maintenance(f.data,expected_sha256=checksum,schema=160,scope=scope)
        f,checksum,scope=self.fixture()
        path=f.data/'maintenance/manifest.json';value=json.loads(path.read_bytes())
        value['binding']['operation']='completed-normal-schema146-150-coordinated-release'
        path.write_text(json.dumps(value));checksum=backup.digest(path)
        with self.assertRaisesRegex(backup.BackupError,'checkpoint_binding_invalid'):
            backup.verify_reconciled_maintenance(f.data,expected_sha256=checksum,schema=160,scope=scope)

    def test_corrupt_roles_and_objects_never_become_receiver_evidence(self):
        for name in ('roles.sql','roles-snapshot.json','objects.tar.gz'):
            f,checksum,scope=self.fixture();(f.data/'maintenance'/name).write_bytes(b'truncated')
            with self.subTest(name=name),self.assertRaises(backup.BackupError):
                backup.verify_reconciled_maintenance(f.data,expected_sha256=checksum,schema=160,scope=scope)

    def test_sender_rejects_number_only160_and_checks_actual_archive_before_ssh(self):
        f,checksum,scope=self.fixture()
        with self.assertRaises(backup.BackupError):
            pipeline.remote_receiver(f.root,SimpleNamespace(digest=scope),f.data,'a'*64,'b'*36,expected_schema=160)
        # No remote command or credential use occurs during this builder test.
        files={name:f.root/'source/web/scripts'/name for name in ('normal_backup_replica.py','backup_support.py')}
        for name,path in files.items():
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((Path(backup.__file__).parent/name).read_bytes())
        args=pipeline.remote_receiver(f.root,SimpleNamespace(digest=scope),f.data,'a'*64,'12345678-1234-1234-1234-123456789abc',
            expected_schema=160,maintenance_manifest_sha256=checksum)
        self.assertIn('madar-node1-lan',args)
        with self.assertRaises(backup.BackupError):
            pipeline.remote_receiver(f.root,SimpleNamespace(digest='f'*64),f.data,'a'*64,'b'*36,
                expected_schema=160,maintenance_manifest_sha256=checksum)

    def test_receiver_refuses160_without_exact_checkpoint_before_opening_any_backup_path(self):
        with patch.object(receiver,'BASE',Path('/must-not-be-opened')):
            with self.assertRaisesRegex(RuntimeError,'binding_invalid'):
                receiver.receive('a'*64,'madar-20261020T000000Z','b'*64,'12345678-1234-1234-1234-123456789abc',160)


class ExecutionContextTests(unittest.TestCase):
    def test_number_or_caller_packet_cannot_enable160_backup_context(self):
        for context in (None,{'PASS':True},SimpleNamespace(schema=160,stage='post-migration')):
            with patch.object(pipeline,'checked') as command:
                with self.subTest(context=context),self.assertRaisesRegex(RuntimeError,'canonical_context_required'):
                    pipeline.verify_backup_execution_context(Path('/unused'),expected_schema=160,completed_context=context)
                command.assert_not_called()


if __name__=='__main__':unittest.main()
