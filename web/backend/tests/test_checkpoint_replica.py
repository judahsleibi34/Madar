"""Local fixture replica tests; no SSH, backup-host or production mutation."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
SCRIPTS=Path('/scripts') if Path('/scripts').is_dir() else WEB/'scripts'
spec=importlib.util.spec_from_file_location('replica_fixture',SCRIPTS/'checkpoint_replica.py')
replica=importlib.util.module_from_spec(spec);spec.loader.exec_module(replica)

class CheckpointReplicaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.entries=[{'path':kind+'.fixture','kind':kind,'size':7,'sha256':hashlib.sha256(b'fixture').hexdigest()} for kind in sorted(replica.KINDS)]
        self.manifest=(json.dumps({'version':1,'schema':115,'sealed':True,'files':self.entries})+'\n').encode()
        self.sha=hashlib.sha256(self.manifest).hexdigest();self.id='checkpoint-20261009T000000Z'
        self.addCleanup(patch.stopall)
        patch.object(replica,'storage',return_value=self.root).start()

    def stream(self, changed=False):
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w') as archive:
            for name,body in [('manifest.json',self.manifest)]+[(e['path'],b'changed' if changed else b'fixture') for e in self.entries]:
                member=tarfile.TarInfo(name);member.size=len(body);archive.addfile(member,io.BytesIO(body))
        data.seek(0)
        return data

    def receive(self, changed=False):
        stdin=type('Input',(),{'buffer':self.stream(changed)})()
        with patch.object(replica.sys,'stdin',stdin):return replica.receive(self.id,self.sha)

    def test_append_only_replica_and_no_latest_or_retention(self):
        (self.root/'LATEST').write_text('historical pointer')
        record=self.receive();self.assertEqual(record['files'],len(replica.KINDS))
        self.assertFalse(record['restore_verified']);self.assertFalse(record['latest_modified']);self.assertFalse(record['retention_run'])
        self.assertEqual((self.root/'LATEST').read_text(),'historical pointer')
        with self.assertRaisesRegex(RuntimeError,'destination_exists'):self.receive()

    def test_changed_payload_retains_partial_attempt_and_no_final(self):
        with self.assertRaisesRegex(RuntimeError,'bytes_mismatch'):self.receive(changed=True)
        self.assertFalse((self.root/'normal-local-preparation'/self.id).exists())
        self.assertTrue((self.root/'normal-local-preparation'/('.'+self.id+'.incomplete')).exists())
        with self.assertRaises(FileExistsError):self.receive()

    def test_invalid_arguments_and_untrusted_namespace_denied(self):
        with self.assertRaisesRegex(RuntimeError,'argument_invalid'):replica.receive('../escape',self.sha)
        parent=self.root/'normal-local-preparation';parent.mkdir();parent.chmod(0o777)
        with self.assertRaisesRegex(RuntimeError,'namespace_untrusted'):self.receive()

    def test_manifest_symlink_is_not_verified(self):
        root=self.root/'fixture';root.mkdir();(self.root/'external').write_bytes(self.manifest);(root/'manifest.json').symlink_to(self.root/'external')
        with self.assertRaisesRegex(RuntimeError,'manifest_mismatch'):replica.verify(root,self.sha)
