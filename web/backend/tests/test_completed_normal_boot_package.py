"""Bootstrap measurements happen before privileged imports or execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('completed_normal_boot_package_fixture',WEB/'scripts/continue_completed_normal_upgrade.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.files={p:hashlib.sha256(b'# fixture only\n').hexdigest() for p in module.REQUIRED_FILES}
        self.manifest={'version':1,'source_sha':'a'*40,'files':self.files}
        body=self.encode(self.manifest);self.source_hash=self.sha(body)
        self.package=self.base/('normal-source-'+self.source_hash);self.package.mkdir()
        for p in self.files:
            target=self.package/'source'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'# fixture only\n')
        (self.package/'source-bundle.json').write_bytes(body)
        self.document={'controller_source_sha':'a'*40,'source_bundle_sha256':self.source_hash}
        (self.package/'plan.json').write_bytes(self.encode(self.document))
        for p in (patch.object(module,'BASE',self.base),patch.object(module,'secured',lambda p,**kw:p)):
            p.start();self.addCleanup(p.stop)
    @staticmethod
    def sha(body):return hashlib.sha256(body).hexdigest()
    @staticmethod
    def encode(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    def measure(self,plan_hash=None):
        return module.measure(self.package,self.source_hash,plan_hash or self.sha((self.package/'plan.json').read_bytes()))
    def test_exact_complete_package_and_canonical_plan_pass_without_imports(self):
        document,source=self.measure()
        self.assertEqual(document,self.document);self.assertEqual(source,self.package/'source')
    def test_noncanonical_plan_cannot_have_a_second_authorization_digest(self):
        raw=json.dumps(self.document).encode();(self.package/'plan.json').write_bytes(raw)
        with self.assertRaisesRegex(RuntimeError,'noncanonical_package'):self.measure(self.sha(raw))
    def test_source_mutation_missing_inventory_or_wrong_approval_fails(self):
        with self.assertRaisesRegex(RuntimeError,'approved_bytes_changed'):self.measure('b'*64)
        target=self.package/'source'/next(iter(self.files));target.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'source_bytes_changed'):self.measure()
        target.write_bytes(b'# fixture only\n');(self.package/'source/unreviewed.py').write_bytes(b'new')
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.measure()

    def test_fixture_package_cannot_be_used_by_production_preflight_or_execute(self):
        self.document['fixture_only']=True
        (self.package/'plan.json').write_bytes(self.encode(self.document))
        flags=SimpleNamespace(**{name:getattr(module.sys.flags,name) for name in dir(module.sys.flags) if not name.startswith('_')})
        flags.isolated=1;flags.dont_write_bytecode=1
        for mode in ('preflight','execute'):
            argv=['continue_completed_normal_upgrade.py',mode,'--source-package',str(self.package),
                '--approved-source',self.source_hash,'--approved-plan',self.sha(self.encode(self.document))]
            with patch.object(module.sys,'argv',argv),patch.object(module.sys,'flags',flags),patch.object(module.os,'geteuid',return_value=0),patch.object(module,'__file__',str(self.package/'source/web/scripts/continue_completed_normal_upgrade.py')):
                with self.assertRaisesRegex(RuntimeError,'fixture_cannot_authorize_production'):module.main()

if __name__=='__main__':unittest.main()
