"""Execution-phase tests of the actual prepare/activate/publish/adopt driver."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_completed_normal_compose import cli
from test_completed_normal_admission import fixture_contract
from deployment.lib import completed_normal_admission as admission
from deployment.lib.runtime_authority import load_worker_authority,write_worker_authority

class Operations:
    def __init__(self,path,contract):
        self.state_root=path;self.completed_normal_admission=contract
        self.old_active=True;self.new_active=False;self.origin_fenced=False;self.route='blue';self.calls=[];self.fail_start=False
    def verify_source(self,sha):self.calls.append(('source',sha))
    def validate_candidate(self,sha,slot):self.calls.append(('normal_validate',sha,slot))
    def validate_candidate_core(self,sha,slot):self.calls.append(('core_validate',sha,slot))
    def schema_version(self):return 115
    def worker_ownership(self,old,new):
        if self.old_active and self.new_active:return 'overlap'
        return 'old' if self.old_active else 'candidate' if self.new_active else 'none'
    def require_completed_normal_origin_fenced(self):
        if not self.origin_fenced:raise RuntimeError('fixture_origin_not_fenced')
    def require_completed_normal_standbys(self,prepared):
        self.calls.append(('standbys_verified',))
    def deactivate_workers(self,release):
        self.calls.append(('stop',release['slot'],load_worker_authority(self.state_root)['owner']))
        if release['slot']=='blue':self.old_active=False
        else:self.new_active=False
    def activate_workers(self,sha,slot,images):
        owner=load_worker_authority(self.state_root)
        if self.old_active or owner['owner']!='CANDIDATE' or owner['candidate']!={'sha':sha,'slot':slot}:
            raise AssertionError('candidate started before exclusive positive ownership')
        self.calls.append(('start',slot,owner['owner']))
        self.new_active=True
        if self.fail_start:raise RuntimeError('injected_worker_start_failure')
    def switch_traffic(self,slot):
        if self.old_active or not self.new_active or not self.origin_fenced:
            raise AssertionError('unfenced or overlapping traffic publication')
        self.route=slot;self.calls.append(('route',slot))
    def _json(self,url):
        if url.endswith('/health/version'):
            return {'release_sha':'c'*40,'release_slot':self.route,'schema_compatible_min':115,'schema_compatible_max':136}
        if url.endswith('/health/recovery'):return {'restricted':True,'business_writes_enabled':False}
        return {'ready':True}

class CompletedNormalReleaseHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.contract=fixture_contract();self.ops=Operations(self.path,self.contract)
        self.original={'active_slot':'blue','known_good_release':{'sha':'a'*40,'slot':'blue','schema':115,
            'images':self.contract['origin']['images'],'worker_generation':'3'*64},'history':[{'phase':'genuine_completed_normal_history'}]}
        (self.path/'state.json').write_text(json.dumps(self.original))
        self.prepared={'release_sha':'c'*40,'candidate_slot':'green','schema':115,'images':{},'prepared_at':'2026-10-11T00:00:00Z',
            'status':'candidate_validated_workers_inactive'}
        (self.path/'prepared-release.json').write_text(json.dumps(self.prepared))
        self.mode='READ_ONLY'
        def require(c,*,mode=None,**kw):
            if mode is not None and mode!=self.mode:raise RuntimeError('fixture_candidate_not_fenced')
            return {'mode':self.mode}
        p=patch.object(admission,'require_candidate_authority',side_effect=require);p.start();self.addCleanup(p.stop)
    def activate(self):
        return cli.activate_prepared_release(sha='c'*40,slot='green',state_root=self.path,operations=self.ops)
    def test_actual_handoff_publishes_none_before_stop_and_exclusive_candidate_before_start(self):
        self.ops.origin_fenced=True;result=self.activate()
        self.assertIn(('stop','blue','NONE'),self.ops.calls)
        self.assertIn(('start','green','CANDIDATE'),self.ops.calls)
        self.assertLess(self.ops.calls.index(('stop','blue','NONE')),self.ops.calls.index(('start','green','CANDIDATE')))
        self.assertLess(self.ops.calls.index(('standbys_verified',)),self.ops.calls.index(('stop','blue','NONE')))
        self.assertEqual(result['business_writes'],'READ_ONLY')
        owner=load_worker_authority(self.path)
        self.assertEqual(owner['old'],{'sha':'a'*40,'slot':'blue'})
        self.assertEqual(self.ops.route,'blue');self.assertEqual(json.loads((self.path/'state.json').read_text()),self.original)
    def test_missing_origin_fence_does_not_stop_old_or_publish_worker_authority(self):
        with self.assertRaisesRegex(RuntimeError,'origin_not_fenced'):self.activate()
        self.assertTrue(self.ops.old_active);self.assertFalse(self.ops.new_active)
        self.assertIsNone(load_worker_authority(self.path))
    def test_partial_worker_start_failure_stops_candidate_and_never_automatically_regrants_origin(self):
        self.ops.origin_fenced=True;self.ops.fail_start=True
        with self.assertRaisesRegex(RuntimeError,'worker_start_failure'):self.activate()
        self.assertFalse(self.ops.old_active);self.assertFalse(self.ops.new_active)
        self.assertEqual(self.mode,'READ_ONLY');self.assertEqual(self.ops.route,'blue')
        self.assertEqual(json.loads((self.path/'state.json').read_text()),self.original)
    def test_publication_requires_positive_candidate_owner_and_readonly_actual_phase(self):
        self.ops.origin_fenced=True;self.activate()
        result=cli.publish_prepared_release(sha='c'*40,slot='green',state_root=self.path,operations=self.ops)
        self.assertEqual(result['business_writes'],'READ_ONLY');self.assertEqual(self.ops.route,'green')
        self.assertEqual(json.loads((self.path/'state.json').read_text()),self.original)
        self.mode='NORMAL'
        with self.assertRaisesRegex(RuntimeError,'candidate_not_fenced'):
            cli.publish_prepared_release(sha='c'*40,slot='green',state_root=self.path,operations=self.ops)
    def test_stale_origin_or_candidate_identity_fails_before_routing(self):
        self.ops.origin_fenced=True;self.activate()
        changed=copy.deepcopy(self.original);changed['known_good_release']['sha']='e'*40
        (self.path/'state.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(RuntimeError,'origin_changed'):
            cli.publish_prepared_release(sha='c'*40,slot='green',state_root=self.path,operations=self.ops)
        self.assertEqual(self.ops.route,'blue')
    def test_adoption_preserves_real_original_release_and_history(self):
        self.ops.origin_fenced=True;self.activate();self.ops.route='green';self.mode='NORMAL'
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch.object(cli.urllib.request,'urlopen',return_value=Response()):
            result=cli.adopt_prepared_release(sha='c'*40,slot='green',state_root=self.path,
                compatibility=cli.Compatibility(115,136,136,'forward-compatible',115,115),operations=self.ops)
        self.assertEqual(result['phase'],'complete');self.assertEqual(result['previous_known_good_release'],self.original['known_good_release'])
        state=json.loads((self.path/'state.json').read_text())
        self.assertEqual(state['history'][0],self.original['history'][0]);self.assertEqual(state['known_good_release']['sha'],'c'*40)
        self.assertNotEqual(state['known_good_release']['sha'],self.contract['candidate']['controller_sha'])

if __name__=='__main__':unittest.main()
