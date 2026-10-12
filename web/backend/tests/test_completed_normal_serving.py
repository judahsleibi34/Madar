"""Stable-route verification observes security and sustained mode; no login claim."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from test_compatible_normal_boot import Clock
from deployment.lib.completed_normal_execution import verify_serving
from deployment.lib.emergency_routing_repair import Runtime,AvailabilityFailure

class ServingTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.runtime=Runtime();self.mode=False;self.changed=False
        def json_http(url):
            if url.endswith('/health/version'):return {'release_sha':'wrong' if self.changed else 'c'*40,'release_slot':'green','schema_compatible_min':115,'schema_compatible_max':136}
            return {'restricted':not self.mode,'business_writes_enabled':self.mode}
        self.runtime.json_http=json_http;self.runtime.denied=Mock();self.runtime.http_status=Mock()
        self.kernel=SimpleNamespace(round=Mock())
        self.actor=SimpleNamespace(runtime=self.runtime,guard=Mock(),proxy_identity=Mock(),native=lambda:115,
            contract={'version':1,'operation':'completed-normal-schema115-136-upgrade',
                'candidate':{'source_sha':'c'*40,'slot':'green'}},candidate=lambda:self.kernel)
        for p in (patch('time.monotonic',self.clock.monotonic),patch('time.sleep',self.clock.sleep)):
            p.start();self.addCleanup(p.stop)
    def test_delayed_complete_rounds_verify_both_routes_and_do_not_claim_customer_login(self):
        self.kernel.round.side_effect=[AvailabilityFailure('activation_pending'),None,None,None,None,None,None]
        result=verify_serving(self.actor,schema=115,normal=False)
        self.assertGreaterEqual(self.clock.value,6);self.assertGreaterEqual(result['complete_rounds'],3)
        self.assertFalse(result['authenticated_customer_mutation_executed'])
        self.assertTrue(self.runtime.denied.called)
    def test_wrong_stable_identity_is_fatal_without_retry(self):
        self.changed=True
        with self.assertRaisesRegex(RuntimeError,'stable_serving_identity_changed'):verify_serving(self.actor,schema=115,normal=False)
        self.assertEqual(self.clock.value,0)
    def test_persistent_unready_or_changed_schema_cannot_pass(self):
        self.kernel.round.side_effect=AvailabilityFailure('pending')
        with self.assertRaisesRegex(RuntimeError,'verification_deadline_expired'):verify_serving(self.actor,schema=115,normal=False)
        self.assertLessEqual(self.clock.value,180)
        self.kernel.round.side_effect=None;self.actor.native=lambda:119
        with self.assertRaisesRegex(RuntimeError,'serving_schema_changed'):verify_serving(self.actor,schema=115,normal=False)
