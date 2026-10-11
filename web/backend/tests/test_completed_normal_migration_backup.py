"""Installed-layout verification; no customer/database mutation."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from deployment.lib import completed_normal_migration as m

class InstalledBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.helpers=self.root/'deployment/scripts';self.helpers.mkdir(parents=True)
        (self.helpers/'backup_support.py').write_text('raise SystemExit(0)\n')
        self.backup=self.root/'madar-20261011T000000Z';self.backup.mkdir();self.sha='a'*40
        (self.backup/'manifest.json').write_text(json.dumps({'database':{'schema_version':115},'release':{'git_sha':self.sha}}))
        (self.backup/'SHA256SUMS').write_text('fixture\n')
        self.witness={k:hashlib.sha256((self.backup/p).read_bytes()).hexdigest() for k,p in
            [('backup_manifest_sha256','manifest.json'),('backup_checksums_sha256','SHA256SUMS')]}
        self.ops=SimpleNamespace(recovery_helper_root=lambda:self.helpers)
        p=patch.object(m,'readonly_configuration',lambda path,**kw:Path(path));p.start();self.addCleanup(p.stop)
    def check(self):m.verify_migration_backup(self.backup,self.witness,self.sha,self.ops)
    def test_installed_scripts_layout_needs_no_importable_scripts_package(self):self.check()
    def test_verifier_uses_isolated_python_and_bounded_execution(self):
        with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:self.check()
        self.assertEqual(run.call_args.args[0],[m.sys.executable,'-I','-B',str(self.helpers/'backup_support.py'),'verify',str(self.backup)])
        self.assertEqual(run.call_args.kwargs,{'capture_output':True,'timeout':180})
    def test_nonzero_private_output_is_sanitized(self):
        (self.helpers/'backup_support.py').write_text('import sys;sys.stderr.write("PRIVATE SECRET");raise SystemExit(1)\n')
        with self.assertRaisesRegex(RuntimeError,'^completed_migration_backup_verification_failed$'):self.check()
    def test_timeout_does_not_leak_child_output(self):
        with patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired('private',180,output=b'PRIVATE SECRET')):
            with self.assertRaisesRegex(RuntimeError,'^completed_migration_backup_verification_failed$'):self.check()
    def test_checksum_or_release_change_is_rejected_after_verification(self):
        (self.backup/'SHA256SUMS').write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'binding_changed'):self.check()
        (self.backup/'SHA256SUMS').write_text('fixture\n');self.sha='b'*40
        with self.assertRaisesRegex(RuntimeError,'binding_changed'):self.check()

if __name__=='__main__':unittest.main()
