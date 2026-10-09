"""Prospective boot ordering with fake runtimes; no host mutation."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_boot import ActiveRecoveryNormalBoot
from deployment.lib.emergency_routing_repair import AvailabilityFailure

class BootTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.plan=SimpleNamespace(digest='a'*64,source_bundle_sha256='b'*64)
        self.root=base/self.plan.digest;self.root.mkdir();self.phase='normal';self.write()
        self.calls=[];self.mode='NORMAL';self.now=0;self.read_rounds=0;self.fail_live=False;self.pending_rounds=0
        self.bound={kind:{'Id':kind} for kind in ('parser','backend','frontend','notification','calendar-sync','data-deletion')}
        def publish(contract,mode):self.calls.append('publish_'+mode);self.mode=mode
        def require(contract,mode):self.assertEqual(self.mode,mode)
        self.c=SimpleNamespace(contract=object(),_publish_write_authority=publish,require_write_authority=require,
            inspect=lambda identity:{'Id':identity,'State':{'Running':False}},command=lambda args:self.calls.append('start_'+args[-1]))
        def readonly(**kwargs):
            self.calls.append('read_only_round');self.assertFalse(kwargs['require_public']);self.assertEqual(self.mode,'READ_ONLY')
            self.read_rounds+=1
            if self.read_rounds<=self.pending_rounds:raise AvailabilityFailure('fixture_wait')
        def normal(**kwargs):self.calls.append('verify_normal');self.assertEqual(self.mode,'NORMAL')
        verifier=SimpleNamespace(identities=lambda **kwargs:self.bound,read_only=readonly,normal=normal)
        def live():
            self.calls.append('native')
            if self.fail_live:raise RuntimeError('fixture_image_changed')
        @contextmanager
        def window(runtime,seconds):yield
        runtime=SimpleNamespace(budget=lambda maximum:maximum)
        self.boot=ActiveRecoveryNormalBoot(self.plan,self.root,self.c,verifier,lambda:None,
            lambda:self.calls.append('actual_evidence'),live,lambda:self.calls.append('compensate'),runtime=runtime)
        for name,value in [('ROOT',base),('protected',lambda path,**kw:path),('verification_window',window)]:
            q=patch('deployment.lib.active_recovery_boot.'+name,value);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_boot.os.geteuid',return_value=0);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_boot.time.monotonic',side_effect=lambda:self.now);q.start();self.addCleanup(q.stop)
        q=patch('deployment.lib.active_recovery_boot.time.sleep',side_effect=lambda seconds:setattr(self,'now',self.now+seconds));q.start();self.addCleanup(q.stop)
    def write(self):
        (self.root/'authorization.json').write_text(json.dumps({'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}))
        (self.root/'events.jsonl').write_text(json.dumps({'phase':self.phase,'plan_sha256':self.plan.digest})+'\n')
    def test_fence_precedes_starts_and_sustained_checks_precede_grant(self):
        self.boot.execute()
        self.assertLess(self.calls.index('publish_READ_ONLY'),self.calls.index('start_parser'))
        self.assertGreaterEqual(self.read_rounds,3);self.assertGreaterEqual(self.now,5)
        self.assertLess(self.calls.index('read_only_round'),self.calls.index('publish_NORMAL'))
        self.assertEqual(self.calls[-1],'verify_normal');self.assertNotIn('compensate',self.calls)
    def test_delayed_worker_readiness_resets_convergence(self):
        self.pending_rounds=2;self.boot.execute()
        self.assertGreaterEqual(self.read_rounds,5);self.assertGreaterEqual(self.now,7)
    def test_changed_native_identity_compensates_before_normal(self):
        self.fail_live=True
        with self.assertRaisesRegex(RuntimeError,'image_changed'):self.boot.execute()
        self.assertEqual(self.mode,'READ_ONLY');self.assertIn('compensate',self.calls)
        self.assertNotIn('publish_NORMAL',self.calls)
    def test_incomplete_continuation_cannot_fence_start_or_grant(self):
        self.phase='write_grant_pending';self.write()
        with self.assertRaisesRegex(RuntimeError,'completed_continuation'):self.boot.execute()
        self.assertEqual(self.calls,[])
    def test_missing_authorization_never_modifies_runtime(self):
        (self.root/'authorization.json').unlink()
        with self.assertRaises(FileNotFoundError):self.boot.execute()
        self.assertEqual(self.calls,[])
    def test_failed_compensation_is_not_reported_as_normal(self):
        self.fail_live=True
        def failure():raise RuntimeError('fixture_compensation_failed')
        self.boot.compensate_current_data=failure
        with self.assertRaisesRegex(RuntimeError,'compensation_failed'):self.boot.execute()
        self.assertNotIn('publish_NORMAL',self.calls)


    def test_post_grant_audit_failure_invokes_compensation(self):
        original=self.boot.event
        def event(stage,**fields):
            if stage=='normal_verified':raise OSError('fixture disk full')
            return original(stage,**fields)
        self.boot.event=event
        with self.assertRaises(OSError):self.boot.execute()
        self.assertIn('publish_NORMAL',self.calls);self.assertIn('compensate',self.calls)

    def test_native_startup_pending_waits_before_candidate_start(self):
        original=self.boot.live_native_verifier;attempts=[0]
        def native():
            attempts[0]+=1
            if attempts[0]<3:raise AvailabilityFailure('fixture_native_starting')
            return original()
        self.boot.live_native_verifier=native;self.boot.execute()
        self.assertGreaterEqual(self.now,7);self.assertIn('verify_normal',self.calls)

    def test_compensated_authority_cannot_replay_retained_normal_journal(self):
        self.mode='READ_ONLY'
        # Fake require uses AssertionError; real positive-authority validation
        # raises RuntimeError. Either must occur before any boot effect.
        with self.assertRaises(AssertionError):self.boot.execute()
        self.assertNotIn('publish_NORMAL',self.calls)
        self.assertNotIn('publish_READ_ONLY',self.calls)
