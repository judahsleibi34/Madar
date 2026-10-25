"""Bootstrap measurements happen before privileged imports or execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('completed_normal_boot_package_fixture',WEB/'scripts/continue_completed_normal_upgrade.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class PackageTests(unittest.TestCase):
    def test_real_installed_library_inventory_imports_forward_resumption(self):
        installer=(WEB/'deployment/bin/madar-install-control-plane').read_text()
        names=re.search(r'declare -a tracked_files=\((.*?)\n\)',installer,re.S).group(1).split()
        self.assertIn('lib/completed_normal_forward.py',names)
        with tempfile.TemporaryDirectory() as raw:
            for name in names:
                if not name.startswith('lib/'):continue
                target=Path(raw)/'deployment'/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(WEB/'deployment'/name,target)
            program='import sys; sys.path.insert(0,sys.argv[1]); from deployment.lib.completed_normal_forward import CompletedNormalForwardResumption, authorized_executor'
            result=subprocess.run([sys.executable,'-I','-B','-c',program,raw],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
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

    def test_capture_mode_measures_again_without_constructing_an_execution_actor(self):
        document = dict(self.document, admission_contract={'synthetic': 'preparation-only'})
        source = self.package/'source'
        flags=SimpleNamespace(**{name:getattr(module.sys.flags,name) for name in dir(module.sys.flags) if not name.startswith('_')})
        flags.isolated=1;flags.dont_write_bytecode=1
        argv=['continue_completed_normal_upgrade.py','capture-inventory','--source-package',str(self.package),
            '--approved-source',self.source_hash,'--approved-plan','b'*64]
        from deployment.lib import schema150_provider_adapter as adapter
        with patch.object(module.sys,'argv',argv),patch.object(module.sys,'flags',flags),\
                patch.object(module.os,'geteuid',return_value=0),\
                patch.object(module,'__file__',str(source/'web/scripts/continue_completed_normal_upgrade.py')),\
                patch.object(module,'measure',return_value=(document,source)) as measure,\
                patch.object(adapter,'capture_original_inventory',return_value={}) as capture,\
                patch('deployment.lib.completed_normal_boot_actor.CompletedNormalBootActor') as actor:
            module.main()
            actor.assert_not_called()
            guard=capture.call_args.kwargs['source_guard'];guard()
            self.assertEqual(measure.call_count,2)
            measure.return_value=(dict(document,changed=True),source)
            with self.assertRaisesRegex(RuntimeError,'capture_source_changed'):guard()

    def test_candidate_verification_is_measured_preparation_without_execution_actor(self):
        document=dict(self.document,admission_contract={'synthetic':'preparation-only'},fixture_only=True)
        source=self.package/'source'
        flags=SimpleNamespace(**{name:getattr(module.sys.flags,name) for name in dir(module.sys.flags) if not name.startswith('_')})
        flags.isolated=1;flags.dont_write_bytecode=1
        argv=['continue_completed_normal_upgrade.py','verify-candidate','--source-package',str(self.package),
            '--approved-source',self.source_hash,'--approved-plan','b'*64]
        with patch.object(module.sys,'argv',argv),patch.object(module.sys,'flags',flags),\
                patch.object(module.os,'geteuid',return_value=0),\
                patch.object(module,'__file__',str(source/'web/scripts/continue_completed_normal_upgrade.py')),\
                patch.object(module,'measure',return_value=(document,source)) as measure,\
                patch('deployment.lib.completed_normal_evidence.verify_reconciled_application_evidence',return_value={}) as verify,\
                patch('deployment.lib.control_plane_upgrade.SystemOperations') as operations,\
                patch('deployment.lib.completed_normal_boot_actor.CompletedNormalBootActor') as actor:
            module.main()
            actor.assert_not_called();verify.assert_called_once()
            self.assertEqual(measure.call_count,3)
            self.assertEqual(verify.call_args.args[0].package,self.package)

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
