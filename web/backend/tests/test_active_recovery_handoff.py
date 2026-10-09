"""Fake runtime tests for bounded handoff; no routing or production effects."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_handoff import ReadOnlyRoutingHandoff
from deployment.lib.emergency_routing_repair import AvailabilityFailure,VerificationDeadline


class Clock:
    value=0
    def now(self):return self.value
    def sleep(self,seconds):self.value+=seconds

class Runtime:
    def __init__(self,clock):self.clock=clock;self.deadline=180;self.calls=[];self.fail=None
    def budget(self,maximum):
        if self.clock.value>=self.deadline:raise VerificationDeadline('deadline')
        return min(maximum,self.deadline-self.clock.value)
    def __getattr__(self,name):
        def call(*args):
            self.calls.append(name)
            if self.fail==name:raise RuntimeError('fixture_failure')
        return call

class Candidate:
    backend_port=8201;frontend_port=3200;contract=object()
    def __init__(self):self.calls=[];self.fail=None
    def __getattr__(self,name):
        def call(*args):
            self.calls.append(name)
            if self.fail==name:raise RuntimeError('fixture_integrity_failed')
        return call

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.runtime=Runtime(self.clock);self.candidate=Candidate()
        plan=SimpleNamespace(digest='a'*64,source_bundle_sha256='b'*64,retained_inputs={'proxy_configuration':'c'*64,'upstream':'d'*64,'controller':'e'*64})
        self.handoff=ReadOnlyRoutingHandoff(plan,self.candidate,Path('/unused'),runtime=self.runtime,observer=lambda:dict(plan.retained_inputs))
        self.snapshots=0
        def snapshot(runtime):
            self.snapshots+=1
            return {'container_id':'a'*64,'image_id':'sha256:'+'b'*64,'spec_sha256':'c'*64,'started_at':'fixed','pid':10,
                'workers':[11] if self.snapshots==1 else [12]}
        item=patch('deployment.lib.active_recovery_proxy.worker_snapshot',side_effect=snapshot);item.start();self.addCleanup(item.stop)
        item=patch('deployment.lib.active_recovery_handoff.exclusive',lambda *args:None);item.start();self.addCleanup(item.stop)
        self.handoff.authorize_phase=lambda phase:None;self.events=[]
        self.handoff.event=lambda name,**fields:self.events.append((name,fields))
        for target,value in [('time.monotonic',self.clock.now),('time.sleep',self.clock.sleep)]:
            item=patch('deployment.lib.active_recovery_handoff.'+target,value);item.start();self.addCleanup(item.stop)
        @contextmanager
        def window(runtime,seconds):runtime.deadline=self.clock.value+seconds;yield
        item=patch('deployment.lib.active_recovery_handoff.verification_window',window);item.start();self.addCleanup(item.stop)

    def test_validated_before_publish_and_reload_before_checks(self):
        def verify(route):self.assertEqual(self.runtime.calls[-1],'reload')
        self.handoff.publish(verify)
        self.assertEqual(self.runtime.calls,['nginx_preflight','publish','reload'])
        self.assertEqual(self.events[-1][0],'previous_workers_drained');self.assertGreaterEqual(self.clock.value,5)

    def test_temporary_old_worker_502_does_not_compensate_immediately(self):
        rounds=0
        def verify(route):
            nonlocal rounds
            rounds+=1
            if rounds<=3:raise AvailabilityFailure('old_worker_502')
        self.handoff.publish(verify)
        self.assertGreaterEqual(self.clock.value,8)
        self.assertEqual([e[0] for e in self.events[:3]],['activation_pending']*3)
        self.assertEqual(self.events[-1][0],'previous_workers_drained')

    def test_success_streak_resets_after_transient_failure(self):
        rounds=0
        def verify(route):
            nonlocal rounds
            rounds+=1
            if rounds==5:raise AvailabilityFailure('transient_502')
        self.handoff.publish(verify)
        self.assertGreaterEqual(self.clock.value,10)
        self.assertGreaterEqual(next(fields for event,fields in self.events if event=='activation_sustained')['sustained_seconds'],5)

    def test_persistent_502_hits_hard_deadline(self):
        def verify(route):raise AvailabilityFailure('persistent_502')
        with self.assertRaises(VerificationDeadline):self.handoff.publish(verify)
        self.assertEqual(self.clock.value,180)
        self.assertNotIn('activation_sustained',[e[0] for e in self.events])

    def test_changed_identity_or_write_fence_fails_immediately(self):
        for method in ('verify_identities','verify_recorded_runtime','verify_read_only'):
            self.candidate.fail=method
            with self.subTest(method=method),self.assertRaisesRegex(RuntimeError,'integrity_failed'):
                self.handoff.publish(lambda route:None)
            self.assertEqual(self.clock.value,0)
            self.assertNotIn('activation_sustained',[e[0] for e in self.events])

    def test_failed_configuration_validation_never_publishes(self):
        self.runtime.fail='nginx_preflight'
        with self.assertRaises(RuntimeError):self.handoff.publish(lambda route:None)
        self.assertEqual(self.runtime.calls,['nginx_preflight'])

    def test_failed_reload_does_not_report_success(self):
        self.runtime.fail='reload'
        with self.assertRaises(RuntimeError):self.handoff.publish(lambda route:None)
        self.assertNotIn('activation_sustained',[e[0] for e in self.events])

    def test_changed_retained_input_prevents_publication(self):
        self.handoff.observer=lambda:{'controller':'changed'}
        with self.assertRaisesRegex(RuntimeError,'retained_inputs_changed'):self.handoff.publish(lambda route:None)
        self.assertEqual(self.runtime.calls,[])

    def test_old_route_compensation_rejects_controller_or_worker_change(self):
        self.handoff.observer=lambda:{**self.handoff.plan.retained_inputs,'controller':'changed'}
        with self.assertRaisesRegex(RuntimeError,'no_longer_safe'):
            self.handoff.restore_emergency_before_controller_change(lambda:None)
        self.assertEqual(self.runtime.calls,[])


    def test_old_keepalive_workers_must_drain_before_handoff_returns(self):
        calls=[0]
        def snapshot(runtime):
            calls[0]+=1
            return {'container_id':'a'*64,'image_id':'sha256:'+'b'*64,'spec_sha256':'c'*64,'started_at':'fixed','pid':10,
                'workers':[11] if calls[0]==1 else [11,12] if calls[0]<5 else [12]}
        with patch('deployment.lib.active_recovery_proxy.worker_snapshot',side_effect=snapshot):
            self.handoff.publish(lambda route:None)
        self.assertGreaterEqual(self.clock.value,8);self.assertEqual(self.events[-1][0],'previous_workers_drained')

    def test_undrained_workers_expire_same_overall_deadline(self):
        snapshot={'container_id':'a'*64,'image_id':'sha256:'+'b'*64,'spec_sha256':'c'*64,'started_at':'fixed','pid':10,'workers':[11]}
        with patch('deployment.lib.active_recovery_proxy.worker_snapshot',return_value=snapshot):
            with self.assertRaises(VerificationDeadline):self.handoff.publish(lambda route:None)
        self.assertEqual(self.clock.value,180)
        self.assertNotIn('previous_workers_drained',[event for event,fields in self.events])

    def test_proxy_restart_during_handoff_is_integrity_failure(self):
        calls=[0]
        def snapshot(runtime):
            calls[0]+=1
            return {'container_id':'a'*64,'image_id':'sha256:'+'b'*64,'spec_sha256':'c'*64,'started_at':'fixed' if calls[0]==1 else 'changed','pid':10,'workers':[11] if calls[0]==1 else [12]}
        with patch('deployment.lib.active_recovery_proxy.worker_snapshot',side_effect=snapshot):
            with self.assertRaisesRegex(RuntimeError,'instance_changed'):self.handoff.publish(lambda route:None)


    def test_transient_502_during_worker_drain_remains_bounded(self):
        rounds=[0]
        def verify(route):
            rounds[0]+=1
            if rounds[0]==7:raise AvailabilityFailure('drain_502')
        self.handoff.publish(verify)
        self.assertIn('worker_drain_activation_pending',[event for event,fields in self.events])
        self.assertEqual(self.events[-1][0],'previous_workers_drained')
