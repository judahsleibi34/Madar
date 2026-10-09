"""Future boot installation fixtures; never creates real units/drop-ins."""
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
from deployment.lib.active_recovery_boot_installation import ActiveRecoveryBootInstallation

class BootInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.plan=SimpleNamespace(digest='a'*64,source_bundle_sha256='b'*64)
        self.root=base/self.plan.digest;self.root.mkdir();self.package=base/'package';self.package.mkdir()
        entry=self.package/'source/web/scripts/boot_active_recovery.py';entry.parent.mkdir(parents=True);entry.write_text('synthetic only')
        self.units=base/'units';self.units.mkdir();self.dropin=self.units/'madar-release-proxy.service.d/92-normal-local-continuation.conf';self.dropin.parent.mkdir()
        self.old=self.dropin.with_name('91-emergency-routing-retry.conf');self.old.write_bytes(b'original emergency')
        listener='madar-normal-local-fallback-'+self.plan.digest[:12]+'.service';(self.units/listener).write_bytes(b'listener fixture')
        record={'plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256,'service':listener,
            'unit_sha256':hashlib.sha256(b'listener fixture').hexdigest()}
        (self.root/'fallback-listener-installation.json').write_text(json.dumps(record))
        (self.root/'authorization.json').write_text(json.dumps({'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}))
        self.phase='detached_candidate_ready';self.save()
        self.calls=[]
        def command(label,args):self.calls.append((label,args));return SimpleNamespace(stdout='original effective proxy unit')
        ops=SimpleNamespace(command=command,systemctl_state=lambda name:{'enabled':'enabled','active':'active'})
        self.install=ActiveRecoveryBootInstallation(self.plan,self.root,self.package,operations=ops)
        self.install.source=SimpleNamespace(verify=lambda:None)
        for name,value in [('ROOT',base),('UNITS',self.units),('DROPIN',self.dropin),('protected',lambda path,**kwargs:path)]:
            item=patch('deployment.lib.active_recovery_boot_installation.'+name,value);item.start();self.addCleanup(item.stop)
        item=patch('deployment.lib.active_recovery_boot_installation.os.geteuid',return_value=0);item.start();self.addCleanup(item.stop)
    def save(self):
        (self.root/'events.jsonl').write_text(json.dumps({'phase':self.phase,'plan_sha256':self.plan.digest})+'\n')
    def test_additive_override_preserves_old_records_without_running_boot_actor(self):
        self.install.install();self.assertEqual(self.old.read_bytes(),b'original emergency')
        self.assertEqual((self.root/'proxy-unit-preimage.txt').read_text(),'original effective proxy unit')
        content=self.dropin.read_text();self.assertIn('ExecStartPre=\n',content)
        self.assertIn('check-proxy-gate',content)
        self.assertFalse(any('--now' in args for label,args in self.calls))
        self.assertEqual(self.calls[-1][0],'continuation_boot_enable')
    def test_existing_override_is_never_overwritten(self):
        self.dropin.write_bytes(b'prior')
        with self.assertRaises(FileExistsError):self.install.install()
        self.assertEqual(self.dropin.read_bytes(),b'prior');self.assertEqual(self.calls,[])
    def test_wrong_phase_prevents_installation(self):
        self.phase='authorized';self.save()
        with self.assertRaisesRegex(RuntimeError,'phase_denied'):self.install.install()
        self.assertEqual(self.calls,[])
    def test_modified_listener_unit_blocks_preparation(self):
        name='madar-normal-local-fallback-'+self.plan.digest[:12]+'.service';(self.units/name).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'listener_service_changed'):self.install.install()
        self.assertEqual(self.calls,[])
