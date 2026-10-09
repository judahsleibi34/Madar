"""Exact source fence tests; synthetic files never become production evidence."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_source import FrozenContinuationSource,REQUIRED
from deployment.lib.provider_recovery_runtime import digest

class FrozenSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        files={}
        for relative in REQUIRED:
            path=self.root/'source'/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic source fixture');path.chmod(0o500)
            files[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest={'version':1,'source_sha':'a'*40,'files':files}
        self.plan=SimpleNamespace(source_sha='a'*40,source_bundle_sha256=digest(self.manifest));self.save()
        self.process=SimpleNamespace(flags=SimpleNamespace(isolated=True,dont_write_bytecode=True),modules={})
        for target,value in [('sys',self.process),('protected',lambda path,**kw:path)]:
            p=patch('deployment.lib.active_recovery_source.'+target,value);p.start();self.addCleanup(p.stop)
        p=patch('deployment.lib.active_recovery_source.os.geteuid',return_value=0);p.start();self.addCleanup(p.stop)
        self.f=FrozenContinuationSource(self.plan,self.root)
    def save(self):
        (self.root/'source-bundle.json').write_text(json.dumps(self.manifest,sort_keys=True))
        self.plan.source_bundle_sha256=digest(self.manifest)
    def test_exact_snapshot_passes_and_preserves_bytes(self):
        self.assertEqual(self.f.verify(),self.manifest)
    def test_mutable_leaf_or_changed_byte_rejected(self):
        path=self.root/'source'/next(iter(REQUIRED));path.chmod(0o700)
        with self.assertRaisesRegex(RuntimeError,'frozen_source_changed'):self.f.verify()
        path.write_bytes(b'changed');path.chmod(0o500)
        with self.assertRaisesRegex(RuntimeError,'frozen_source_changed'):self.f.verify()
    def test_undeclared_bytecode_is_rejected(self):
        (self.root/'source'/'unexpected.pyc').write_bytes(b'fixture')
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.f.verify()
    def test_foreign_privileged_import_is_rejected(self):
        self.process.modules={'deployment.lib.untrusted':SimpleNamespace(__file__='/mutable/untrusted.py')}
        with self.assertRaisesRegex(RuntimeError,'foreign_privileged_import'):self.f.verify()
    def test_missing_module_and_boolean_version_are_rejected(self):
        self.manifest['version']=True;self.save()
        with self.assertRaisesRegex(RuntimeError,'manifest_changed'):self.f.verify()
        self.manifest['version']=1;self.manifest['files'].pop(next(iter(REQUIRED)));self.save()
        with self.assertRaisesRegex(RuntimeError,'inventory_incomplete'):self.f.verify()
    def test_nonisolated_execution_is_denied(self):
        self.process.flags.isolated=False
        with self.assertRaisesRegex(RuntimeError,'isolated_frozen_entry'):self.f.verify()

    def test_changed_manifest_formatting_cannot_reuse_exact_source_approval(self):
        path=self.root/'source-bundle.json';path.write_text(json.dumps(self.manifest,sort_keys=True,indent=2))
        with self.assertRaisesRegex(RuntimeError,'manifest_bytes_changed'):self.f.verify()
