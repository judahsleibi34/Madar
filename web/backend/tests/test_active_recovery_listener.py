"""Additive listener installer fixtures; no systemd or network mutations."""
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
from deployment.lib.active_recovery_listener import ActiveRecoveryFallbackInstallation

class ListenerInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.plan=SimpleNamespace(digest='a'*64,source_bundle_sha256='b'*64)
        self.root=base/self.plan.digest;self.root.mkdir();self.package=base/'package';self.package.mkdir()
        entry=self.package/'source/web/scripts/serve_active_recovery_fallback.py';entry.parent.mkdir(parents=True);entry.write_text('synthetic')
        self.units=base/'units';self.units.mkdir();self.calls=[]
        operations=SimpleNamespace(command=lambda label,args:self.calls.append((label,args)),systemctl_state=lambda name:{'enabled':'enabled','active':'active'})
        self.install=ActiveRecoveryFallbackInstallation(self.plan,self.root,self.package,operations=operations)
        self.install.source=SimpleNamespace(verify=lambda:None)
        self.phase='detached_candidate_ready';self.save()
        for name,value in [('ROOT',base),('UNITS',self.units),('protected',lambda path,**kw:path)]:
            q=patch('deployment.lib.active_recovery_listener.'+name,value);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_listener.os.geteuid',return_value=0);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_listener.socket.socket');self.socket=q.start();self.addCleanup(q.stop)
    def save(self):
        (self.root/'authorization.json').write_text(json.dumps({'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}))
        (self.root/'events.jsonl').write_text(json.dumps({'phase':self.phase,'plan_sha256':self.plan.digest})+'\n')
    def test_new_service_is_hash_bound_and_old_installation_untouched(self):
        old=self.units/'madar-emergency-routing.service';old.write_bytes(b'original')
        name=self.install.install();self.assertEqual(old.read_bytes(),b'original')
        body=(self.units/name).read_text();self.assertIn('-I -B',body)
        self.assertIn('--approved-source '+self.plan.source_bundle_sha256,body)
        self.assertIn('ProtectSystem=strict',body)
        self.assertEqual([label for label,args in self.calls],['continuation_listener_validate','continuation_listener_reload','continuation_listener_enable'])
        staged=self.calls[0][1][-1];self.assertTrue(staged.endswith('.service'))
    def test_existing_unit_is_not_overwritten(self):
        target=self.units/self.install.name;target.write_bytes(b'prior')
        with self.assertRaises(FileExistsError):self.install.install()
        self.assertEqual(target.read_bytes(),b'prior');self.assertEqual(self.calls,[])
    def test_wrong_phase_prevents_even_listener_bind(self):
        self.phase='authorized';self.save()
        with self.assertRaisesRegex(RuntimeError,'phase_denied'):self.install.install()
        self.socket.assert_not_called();self.assertEqual(self.calls,[])
    def test_occupied_port_prevents_unit_publication(self):
        self.socket.return_value.__enter__.return_value.bind.side_effect=OSError('fixture occupied')
        with self.assertRaises(OSError):self.install.install()
        self.assertFalse((self.units/self.install.name).exists());self.assertEqual(self.calls,[])
    def test_source_failure_prevents_all_effects(self):
        self.install.source=SimpleNamespace(verify=lambda:(_ for _ in ()).throw(RuntimeError('source_changed')))
        with self.assertRaisesRegex(RuntimeError,'source_changed'):self.install.install()
        self.assertEqual(self.calls,[])
