"""Synthetic positive-boundary regressions; do not grant production writes."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_write_authority import ActiveRecoveryWriteAuthority

class WriteBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.plan=SimpleNamespace(digest='a'*64,source_sha='b'*40,source_bundle_sha256='c'*64)
        self.root=base/self.plan.digest;self.root.mkdir();(self.root/'write-authority').mkdir()
        (self.root/'write-authority'/'authority.json').write_text('{"fixture":"READ_ONLY"}')
        self.auth={'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}
        (self.root/'authorization.json').write_text(json.dumps(self.auth))
        self.events=[{'phase':phase,'plan_sha256':self.plan.digest} for phase in ('read_only_serving','controller_resumed','standby_ready','write_grant_pending')]
        self.events[-1]['normal_writes_may_have_occurred']=True;self.save()
        installed={'plan_sha256':self.plan.digest,'source_sha':self.plan.source_sha,'source_bundle_sha256':self.plan.source_bundle_sha256,
            'historical_authorization_reused':False,'volatile_credential_reconstructed':False}
        (self.root/'installed-controller.json').write_text(json.dumps(installed))
        self.mode='READ_ONLY';self.effects=[];self.verifications=[];self.fail_guard=False;self.fail_publication=False
        def require(contract,mode):
            if self.mode!=mode:raise RuntimeError('fixture_authority_changed')
        def publish(contract,mode):
            self.effects.append(mode)
            if self.fail_publication:raise OSError('fixture_publication_failed')
            self.mode=mode
        def prerequisites():
            self.verifications.append('prerequisites')
            if self.fail_guard:raise RuntimeError('fixture_prerequisite_failed')
        self.c=SimpleNamespace(contract=object(),state=self.root/'state',require_write_authority=require,_publish_write_authority=publish)
        self.c.state.mkdir()
        runtime=SimpleNamespace(read_only=lambda **kw:self.verifications.append('actual_runtime'))
        self.g=ActiveRecoveryWriteAuthority(self.plan,self.c,self.root,lambda:None,runtime,prerequisites)
        for name,value in [('ROOT',base),('protected',lambda path,**kw:path)]:
            patcher=patch('deployment.lib.active_recovery_write_authority.'+name,value);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('deployment.lib.active_recovery_write_authority.os.geteuid',return_value=0);patcher.start();self.addCleanup(patcher.stop)
    def save(self):
        (self.root/'events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in self.events))
    def test_grant_is_last_after_actual_guards_and_preserves_preimage(self):
        self.g.grant();self.assertEqual(self.effects,['NORMAL'])
        self.assertEqual(self.verifications,['prerequisites','actual_runtime']*2)
        self.assertEqual((self.root/'pre-grant-authority.json').read_text(),'{"fixture":"READ_ONLY"}')
        boundary=json.loads((self.root/'write-boundary.json').read_text());self.assertTrue(boundary['normal_writes_may_have_occurred'])
        self.assertFalse(boundary['customer_database_restore_permitted'])
    def test_wrong_phase_or_missing_durable_boundary_blocks_grant(self):
        self.events[-1]['normal_writes_may_have_occurred']=False;self.save()
        with self.assertRaisesRegex(RuntimeError,'phase_denied'):self.g.grant()
        self.assertEqual(self.effects,[])
    def test_changed_auth_or_controller_blocks_grant(self):
        (self.root/'installed-controller.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'attestation_changed'):self.g.grant()
        self.assertEqual(self.effects,[])
    def test_prerequisite_failure_never_publishes(self):
        self.fail_guard=True
        with self.assertRaisesRegex(RuntimeError,'prerequisite_failed'):self.g.grant()
        self.assertFalse((self.root/'write-boundary.json').exists());self.assertEqual(self.effects,[])
    def test_authority_publication_failure_preserves_boundary_for_compensation(self):
        self.fail_publication=True
        with self.assertRaises(OSError):self.g.grant()
        self.assertTrue((self.root/'write-boundary.json').exists());self.assertEqual(self.mode,'READ_ONLY')
        self.fail_publication=False;self.g.revoke();self.assertEqual(self.mode,'READ_ONLY')
    def test_revocation_does_not_depend_on_compensation_journal(self):
        self.g.grant();(self.root/'events.jsonl').unlink();self.fail_guard=True
        self.g.revoke();self.assertEqual(self.mode,'READ_ONLY')
    def test_previous_boundary_is_never_overwritten(self):
        (self.root/'write-boundary.json').write_bytes(b'prior')
        with self.assertRaises(FileExistsError):self.g.grant()
        self.assertEqual((self.root/'write-boundary.json').read_bytes(),b'prior');self.assertEqual(self.effects,[])
    def test_revocation_still_requires_fresh_source_and_receipt(self):
        (self.root/'authorization.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'authorization_changed'):self.g.revoke()
        self.assertEqual(self.effects,[])
