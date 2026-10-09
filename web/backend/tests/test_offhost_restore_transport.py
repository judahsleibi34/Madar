"""Synthetic transport fixtures; no off-host backup proof is issued."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
SCRIPTS=Path('/scripts') if Path('/scripts').is_dir() else WEB/'scripts'
spec=importlib.util.spec_from_file_location('offhost_fixture',SCRIPTS/'restore_node1_checkpoint.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class OffhostRestoreTransportTests(unittest.TestCase):
    def archive(self,entries):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for name,kind,data in entries:
                member=tarfile.TarInfo(name);member.type=kind;member.size=len(data) if kind==tarfile.REGTYPE else 0
                archive.addfile(member,io.BytesIO(data) if kind==tarfile.REGTYPE else None)
        stream.seek(0);return stream
    def test_exact_bytes_recovered_and_hashed(self):
        data=b'synthetic';expected={'manifest.json':{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}}
        with tempfile.TemporaryDirectory() as d:
            result=runner.receive(self.archive([('manifest.json',tarfile.REGTYPE,data)]),Path(d),expected)
            self.assertEqual(result,{'manifest.json':expected['manifest.json']['sha256']})
            self.assertEqual((Path(d)/'manifest.json').read_bytes(),data)
    def test_extra_link_duplicate_partial_and_changed_bytes_denied(self):
        expected={'manifest.json':{'size':1,'sha256':hashlib.sha256(b'a').hexdigest()}}
        fixtures=[[('../escape',tarfile.REGTYPE,b'a')],[('manifest.json',tarfile.SYMTYPE,b'')],
            [('manifest.json',tarfile.REGTYPE,b'a')]*2,[],[('manifest.json',tarfile.REGTYPE,b'b')]]
        for entries in fixtures:
            with self.subTest(entries=entries),tempfile.TemporaryDirectory() as d,self.assertRaises(RuntimeError):
                runner.receive(self.archive(entries),Path(d),expected)
