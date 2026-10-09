"""Exact byte-gate regressions using private synthetic source packages."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('continuation_bootstrap_fixture',WEB/'scripts/resume_active_recovery.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        p=patch.object(bootstrap,'BASE',self.base);p.start();self.addCleanup(p.stop)
        # Test user/temp parents differ from production root-private hierarchy.
        p=patch.object(bootstrap,'secured',side_effect=lambda path,**kw:Path(path));p.start();self.addCleanup(p.stop)
        data=b'print("synthetic source only")\n'
        manifest={'version':1,'source_sha':'a'*40,'files':{'web/scripts/entry.py':hashlib.sha256(data).hexdigest()}}
        raw=json.dumps(manifest,sort_keys=True).encode();self.source_sha=hashlib.sha256(raw).hexdigest()
        self.root=self.base/('normal-source-'+self.source_sha);self.root.mkdir()
        target=self.root/'source/web/scripts/entry.py';target.parent.mkdir(parents=True);target.write_bytes(data)
        (self.root/'source-bundle.json').write_bytes(raw)
        plan={'source_sha':'a'*40,'source_bundle_sha256':self.source_sha}
        raw=json.dumps(plan,sort_keys=True).encode();self.plan_sha=hashlib.sha256(raw).hexdigest()
        (self.root/'plan.json').write_bytes(raw)
    def measure(self):return bootstrap.measure(self.root,self.source_sha,self.plan_sha)
    def test_all_bytes_are_measured_before_deployment_import(self):
        saved,source=self.measure();self.assertEqual(saved['source_sha'],'a'*40);self.assertEqual(source,self.root/'source')
    def test_changed_executable_fails_before_import(self):
        (self.root/'source/web/scripts/entry.py').write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'source_hash_changed'):self.measure()
    def test_changed_plan_formatting_cannot_reuse_approval(self):
        with (self.root/'plan.json').open('a') as output:output.write('\n')
        with self.assertRaisesRegex(RuntimeError,'approved_bytes_changed'):self.measure()
    def test_changed_source_inventory_denied(self):
        (self.root/'source/unreviewed.py').write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.measure()
    def test_arbitrary_package_directory_denied(self):
        with self.assertRaisesRegex(RuntimeError,'namespace_invalid'):bootstrap.measure(self.base,self.source_sha,self.plan_sha)
    def test_missing_or_expired_approval_has_no_effect(self):
        for value in ('', 'expired', '0'*63):
            with self.subTest(value=value),self.assertRaisesRegex(RuntimeError,'approval_invalid'):bootstrap.measure(self.root,value,self.plan_sha)
