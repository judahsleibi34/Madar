"""Publication prerequisites fail before backup effects or approval consumption."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deployment.lib import active_recovery_backup as operation
from scripts import backup_support
import test_historical_origin as historical_fixture
from test_schema160_release import reconciled_contract


class BackupPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.backups=self.root/'backups';self.backups.mkdir()
        self.journal=self.root/'journal';self.journal.mkdir()
        self.contract=historical_fixture.HistoricalPreparationBindingTests().contract()
        self.context=SimpleNamespace(contract=self.contract,stage='pre-migration',context='a'*64)
        self.enterContext(patch.object(operation,'readonly_configuration',side_effect=lambda p,**kw:Path(p)))

    def test_existing_marker_bytes_are_preserved_without_reinterpretation(self):
        body=b'20261103T200000Z /var/lib/madar/backups/madar-20261103T200000Z\n'
        (self.backups/'LATEST').write_bytes(body)
        operation.preserve_latest_preimage(self.journal,self.backups,self.context,expected=body)
        path=self.journal/operation.latest_preimage_name(self.context)
        self.assertEqual(path.read_bytes(),body)
        with self.assertRaises(FileExistsError):
            operation.preserve_latest_preimage(self.journal,self.backups,self.context,expected=body)
        self.assertEqual((self.backups/'LATEST').read_bytes(),body)

    def test_first_historical_backup_records_absence_without_creating_freshness(self):
        operation.preserve_latest_preimage(self.journal,self.backups,self.context,expected=None)
        name=operation.latest_preimage_name(self.context)
        record=json.loads((self.journal/(name+'-absent.json')).read_bytes())
        self.assertEqual(record,{'version':1,'kind':'absent-before-first-historical-source-backup',
            'context_sha256':self.context.context,'stage':'pre-migration','path':str(self.backups/'LATEST')})
        self.assertFalse((self.backups/'LATEST').exists())
        self.assertFalse((self.journal/name).exists())
        with self.assertRaises(FileExistsError):
            operation.preserve_latest_preimage(self.journal,self.backups,self.context,expected=None)

    def test_ordinary_and_target_backups_cannot_claim_missing_previous_marker(self):
        for contract,stage in ((None,None),(reconciled_contract(),'pre-migration'),
                               (self.contract,'post-migration')):
            with self.subTest(stage=stage,ordinary=contract is None),self.assertRaises(FileNotFoundError):
                operation.latest_preimage(self.backups,contract=contract,stage=stage)

    def test_changed_historical_scope_cannot_use_first_backup_exception(self):
        changed=copy.deepcopy(self.contract);changed['database']['system_identifier']='123456789'
        with self.assertRaisesRegex(RuntimeError,'successor_scope_changed'):
            operation.latest_preimage(self.backups,contract=changed,stage='pre-migration')

    def test_dangling_symlink_is_not_marker_absence(self):
        (self.backups/'LATEST').symlink_to(self.root/'missing')
        with patch.object(operation,'readonly_configuration',side_effect=RuntimeError('untrusted-marker')) as read:
            with self.assertRaisesRegex(RuntimeError,'untrusted-marker'):
                operation.latest_preimage(self.backups,contract=self.contract,stage='pre-migration')
        read.assert_called_once()
        self.assertEqual(list(self.journal.iterdir()),[])

    def test_marker_change_during_capture_refuses_without_publishing_a_preimage(self):
        self.assertIsNone(operation.latest_preimage(self.backups,contract=self.contract,stage='pre-migration'))
        (self.backups/'LATEST').write_bytes(b'actual-intervening-marker\n')
        with self.assertRaisesRegex(RuntimeError,'normal_backup_latest_changed_during_capture'):
            operation.preserve_latest_preimage(self.journal,self.backups,self.context,expected=None)
        self.assertEqual(list(self.journal.iterdir()),[])
        self.assertEqual((self.backups/'LATEST').read_bytes(),b'actual-intervening-marker\n')

    def test_wrong_or_legacy_configuration_refuses_before_database_lease_or_child(self):
        valid={'MADAR_BACKUP_DIR':'/var/lib/madar/backups',
               'MADAR_BACKUP_FRESHNESS_MARKER':'/var/lib/madar/backups/LATEST'}
        operation.verify_publication_configuration(valid,Path('/var/lib/madar/backups'))
        invalid=({'BACKUP_DIR':valid['MADAR_BACKUP_DIR'],'FRESHNESS_MARKER':valid['MADAR_BACKUP_FRESHNESS_MARKER']},
                 {**valid,'MADAR_BACKUP_DIR':'/unrelated'},
                 {**valid,'MADAR_BACKUP_FRESHNESS_MARKER':'/unrelated/LATEST'})
        for cfg in invalid:
            with self.subTest(cfg=cfg):
                configuration=self.root/'backup.env'
                configuration.write_text(''.join(k+'='+v+'\n' for k,v in cfg.items()))
                configuration.chmod(0o600)
                with patch.dict(operation.INPUTS,backup_configuration=configuration),\
                     patch.object(operation.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=1000)),\
                     patch.object(operation,'file_digest',return_value=self.contract['database']['backup_configuration_sha256']),\
                     patch.object(backup_support,'sealed_local_database_binding') as lease,\
                     patch.object(operation,'checked') as child:
                    with self.assertRaisesRegex(RuntimeError,'normal_backup_configured_root_changed'):
                        operation.verify_backup_execution_context(Path('/unused'),expected_schema=146,maintenance_contract=self.contract)
                lease.assert_not_called();child.assert_not_called()


if __name__=='__main__':unittest.main()
