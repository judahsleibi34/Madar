"""Synthetic internal-hardlink recovery fixtures, never backup evidence."""
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.coordinated_archive_restore import restore_archive,verify_restored_archive
class ArchiveHardlinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def archive(self,target='scope/source',*,forward=False):
        path=self.root/'fixture.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            file=tarfile.TarInfo('scope/source');file.size=7
            link=tarfile.TarInfo('scope/copy');link.type=tarfile.LNKTYPE;link.linkname=target
            if forward:archive.addfile(link)
            archive.addfile(file,io.BytesIO(b'fixture'))
            if not forward:archive.addfile(link)
        return path
    def test_backward_internal_hardlink_restores_independent_bytes(self):
        result=restore_archive(self.archive(),self.root/'restore')
        self.assertEqual(result['hardlinks_materialized'],1)
        a=self.root/'restore/scope/source';b=self.root/'restore/scope/copy'
        self.assertEqual(a.read_bytes(),b.read_bytes());self.assertNotEqual(a.stat().st_ino,b.stat().st_ino)
    def test_external_forward_and_missing_link_targets_denied(self):
        for i,(target,forward) in enumerate([('/etc/madar/production.env',False),('../outside',False),('missing',False),('scope/source',True)]):
            with self.subTest(target=target,forward=forward),self.assertRaises(RuntimeError):restore_archive(self.archive(target,forward=forward),self.root/f'denied-{i}')
            self.assertFalse((self.root/f'denied-{i}').exists())
    def test_hardlink_expansion_respects_total_byte_budget(self):
        with self.assertRaisesRegex(RuntimeError,'size_limit'):restore_archive(self.archive(),self.root/'limited',max_bytes=10)

    def test_existing_quarantine_is_independently_verified_without_overwrite(self):
        source=self.archive();destination=self.root/'restore';restore_archive(source,destination)
        result=verify_restored_archive(source,destination)
        self.assertTrue(result['restored_bytes_verified'])
        target=destination/'scope/copy';target.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'restore_mismatch'):verify_restored_archive(source,destination)
        self.assertEqual(target.read_bytes(),b'changed')
    def test_existing_quarantine_extra_file_or_symlink_rejected(self):
        source=self.archive();destination=self.root/'restore';restore_archive(source,destination)
        extra=destination/'extra';extra.write_bytes(b'fixture')
        with self.assertRaisesRegex(RuntimeError,'inventory_inexact'):verify_restored_archive(source,destination)
        extra.unlink();target=destination/'scope/copy';target.unlink();target.symlink_to('source')
        with self.assertRaisesRegex(RuntimeError,'restore_mismatch'):verify_restored_archive(source,destination)
