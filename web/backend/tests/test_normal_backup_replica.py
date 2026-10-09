"""Append-only replica fixtures; no customer data, SSH or production mutation."""
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
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB/'scripts'))
import backup_support
import normal_backup_replica as receiver

class AppendOnlyNormalReplicaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.plan='a'*64;self.identifier='madar-20261009T050000Z';self.uuid='a'*8+'-'+ 'b'*4+'-'+ 'c'*4+'-'+ 'd'*4+'-'+ 'e'*12
        self.data=self.root/'source';self.data.mkdir()
        for name in backup_support.FILE_SETS:(self.data/'files'/name).mkdir(parents=True)
        for name in ['database.dump','BACKUP_COMPLETE','MANIFEST.txt','CONFIGURATION-INVENTORY.txt']:(self.data/name).write_bytes(b'unit fixture')
        (self.data/'backup.env').write_text('MADAR_BACKUP_FORMAT=3\n')
        manifest={'backup_id':self.identifier,'created_at':self.identifier[6:],'status':'complete','format_version':3,
            'database':{'dump':'database.dump','schema_version':'115'},'checksums':'SHA256SUMS',
            'configuration':{'values_included':False},'file_sets':list(backup_support.FILE_SETS)}
        (self.data/'manifest.json').write_text(json.dumps(manifest));self.seal()
        self.base=self.root/'backups';self.base.mkdir(mode=0o700);(self.base/'LATEST').write_text('historical fixture')
        self.stream=self.archive()
        original_lstat=Path.lstat
        def fixture_lstat(path,*args,**kwargs):
            if str(path)=='/tmp':return SimpleNamespace(st_uid=0,st_mode=0o40755)
            return original_lstat(path,*args,**kwargs)
        q=patch('normal_backup_replica.Path.lstat',fixture_lstat);q.start();self.addCleanup(q.stop)
        for name,value in [('BASE',self.base),('sys',SimpleNamespace(stdin=SimpleNamespace(buffer=self.stream))),
            ('shutil.disk_usage',lambda *a:SimpleNamespace(free=100*1024**3)),
            ('subprocess.run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='/dev/sdc1 ext4 /srv/data2 '+self.uuid))]:
            p=patch('normal_backup_replica.'+name,value);p.start();self.addCleanup(p.stop)
    def seal(self):
        inventory=backup_support.inventory(self.data);inventory.pop('SHA256SUMS',None)
        (self.data/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in sorted(inventory.items())))
        self.sums=backup_support.digest(self.data/'SHA256SUMS')
    def archive(self):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for path in sorted(self.data.rglob('*')):archive.add(path,arcname=path.relative_to(self.data).as_posix(),recursive=False)
        stream.seek(0);return stream
    def receive(self):return receiver.receive(self.plan,self.identifier,self.sums,self.uuid)
    def test_exact_replica_preserves_history_and_empty_file_sets(self):
        report=self.receive();self.assertFalse(report['latest_modified']);self.assertFalse(report['retention_performed'])
        self.assertEqual((self.base/'LATEST').read_text(),'historical fixture')
        final=Path(report['destination']);self.assertEqual(backup_support.verify(final,dump=False)['backup_id'],self.identifier)
        self.assertTrue(all((final/'files'/name).is_dir() for name in backup_support.FILE_SETS))
        self.assertEqual(final.stat().st_mode&0o777,0o500)
    def test_repeated_transfer_cannot_overwrite_records(self):
        first=self.receive();before=(Path(first['destination'])/'SHA256SUMS').read_bytes()
        with self.assertRaises(FileExistsError):self.receive()
        self.assertEqual((Path(first['destination'])/'SHA256SUMS').read_bytes(),before)
    def test_wrong_filesystem_rejected_before_new_scope(self):
        with patch('normal_backup_replica.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='different filesystem')):
            with self.assertRaisesRegex(RuntimeError,'filesystem_changed'):self.receive()
        self.assertFalse((self.base/'normal-local-production').exists())
    def test_changed_payload_is_rejected_and_partial_evidence_retained(self):
        (self.data/'database.dump').write_bytes(b'changed fixture');stream=self.archive()
        with patch('normal_backup_replica.sys',SimpleNamespace(stdin=SimpleNamespace(buffer=stream))):
            with self.assertRaises(backup_support.BackupError):self.receive()
        self.assertTrue((self.base/'normal-local-production'/self.plan/'incoming').is_dir())
    def test_links_and_traversal_rejected(self):
        for name,kind in [('../escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]:
            stream=io.BytesIO()
            with tarfile.open(fileobj=stream,mode='w') as archive:
                info=tarfile.TarInfo(name);info.type=kind;archive.addfile(info)
            stream.seek(0)
            # A new exact plan scope for each independent synthetic failure.
            with patch('normal_backup_replica.sys',SimpleNamespace(stdin=SimpleNamespace(buffer=stream))):
                with self.assertRaisesRegex(RuntimeError,'member_invalid'):
                    receiver.receive(('b' if kind==tarfile.REGTYPE else 'c')*64,self.identifier,self.sums,self.uuid)
    def test_invalid_binding_rejected_before_any_directory(self):
        with self.assertRaisesRegex(RuntimeError,'binding_invalid'):receiver.receive('bad',self.identifier,self.sums,self.uuid)
        self.assertFalse((self.base/'normal-local-production').exists())

    def test_insufficient_space_fails_without_publishing_backup(self):
        with patch('normal_backup_replica.shutil.disk_usage',return_value=SimpleNamespace(free=1024)):
            with self.assertRaisesRegex(RuntimeError,'capacity_exceeded'):self.receive()
        self.assertFalse((self.base/'normal-local-production'/self.plan/self.identifier).exists())
