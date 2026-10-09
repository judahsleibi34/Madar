"""Synthetic archive tests; never authorization or customer recovery evidence."""
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB))
from deployment.lib.coordinated_checkpoint import KINDS, seal, verify_inventory, restore_archive


class CoordinatedCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def packet(self):
        root=self.root/'checkpoint'; root.mkdir()
        binding={}
        for kind in KINDS:
            name=kind+'.fixture'; (root/name).write_bytes(b'synthetic checkpoint fixture'); binding[name]=kind
        seal(root,created_at='2026-10-09T00:00:00+00:00',binding=binding)
        self.addCleanup(root.chmod,0o700)
        return root

    def test_sealed_exact_inventory_and_no_inherited_restore(self):
        root=self.packet(); record,inventory=verify_inventory(root)
        self.assertFalse(record['restore_verified']); self.assertEqual(len(inventory),len(KINDS))
        with self.assertRaisesRegex(RuntimeError,'already_sealed'):
            seal(root,created_at='later',binding={})

    def test_changed_bytes_and_unlisted_supplement_rejected(self):
        root=self.packet(); file=next(p for p in root.iterdir() if p.name!='manifest.json'); file.chmod(0o600); file.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'bytes_changed'):verify_inventory(root)
        root=self.root/'other'; root.mkdir(); binding={}
        for kind in KINDS:
            name=kind+'.fixture';(root/name).write_bytes(b'fixture');binding[name]=kind
        seal(root,created_at='today',binding=binding);root.chmod(0o700)
        (root/'unverified-supplement').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError,'inventory_inexact'):verify_inventory(root)

    def archive(self, entries):
        path=self.root/'archive.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            for name,kind,body in entries:
                member=tarfile.TarInfo(name); member.type=kind; member.size=len(body) if kind==tarfile.REGTYPE else 0
                member.linkname='/etc/madar/production.env' if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE) else ''
                archive.addfile(member,io.BytesIO(body) if kind==tarfile.REGTYPE else None)
        return path

    def test_archive_bytes_restored_without_code_execution(self):
        path=self.archive([('scope/fixture.py',tarfile.REGTYPE,b'raise RuntimeError("must never execute")')])
        result=restore_archive(path,self.root/'restored')
        self.assertEqual(result['files'],1);self.assertTrue(result['restored_bytes_verified']);self.assertFalse(result['code_executed'])
        with self.assertRaisesRegex(RuntimeError,'destination_exists'):restore_archive(path,self.root/'restored')

    def test_traversal_links_devices_and_duplicates_denied(self):
        for i,(name,kind) in enumerate([('../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),('link',tarfile.SYMTYPE),('hard',tarfile.LNKTYPE),('device',tarfile.CHRTYPE)]):
            with self.subTest(name=name),self.assertRaises(RuntimeError):
                restore_archive(self.archive([(name,kind,b'fixture')]),self.root/f'restore-{i}')
            self.assertFalse((self.root/f'restore-{i}').exists())
        with self.assertRaises(RuntimeError):restore_archive(self.archive([('dup',tarfile.REGTYPE,b'a'),('dup',tarfile.REGTYPE,b'b')]),self.root/'duplicates')

    def test_archive_resource_limit_denied_before_creation(self):
        path=self.archive([('fixture',tarfile.REGTYPE,b'1234')])
        with self.assertRaisesRegex(RuntimeError,'size_limit'):restore_archive(path,self.root/'limited',max_bytes=3)
        self.assertFalse((self.root/'limited').exists())
