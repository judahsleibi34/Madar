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
    def verify_completed_normal_runtime(self,slot):
        return {'component-model':{'State':{'Running':self.new_active,'Restarting':False,'Health':{'Status':'healthy'}}}}
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
        cli.prepared_release_path(self.path,self.ops).write_text(json.dumps(self.prepared))
        (self.path/'prepared-release.json').write_text('retained prior candidate evidence')
        self.mode='READ_ONLY'
        def require(c,*,mode=None,**kw):
            if mode is not None and mode!=self.mode:raise RuntimeError('fixture_candidate_not_fenced')
            return {'mode':self.mode}
        p=patch.object(admission,'require_candidate_authority',side_effect=require);p.start();self.addCleanup(p.stop)
    def test_prepared_state_is_exclusive_to_this_admission_without_replacing_legacy_record(self):
        path=cli.prepared_release_path(self.path,self.ops)
        self.assertNotEqual(path,cli.prepared_release_path(self.path))
        changed=copy.deepcopy(self.contract);changed['candidate']['controller_sha']='e'*40
        other=Operations(self.path,changed)
        self.assertNotEqual(path,cli.prepared_release_path(self.path,other))
        self.ops.origin_fenced=True;self.activate()
        self.assertEqual((self.path/'prepared-release.json').read_text(),'retained prior candidate evidence')

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

class MaintenanceWorkerOwnerTests(unittest.TestCase):
    """Actual child/owner files and intent transitions; modeled live runtime."""
    def setUp(self):
        import hashlib
        from test_schema160_release import reconciled_contract
        from deployment.lib.completed_normal_resources import candidate_roles
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name);self.contract=reconciled_contract()
        self.sha=self.contract['candidate']['source_sha'];self.slot=self.contract['candidate']['slot']
        self.ops=Operations(self.path,self.contract);self.ops.old_active=False;self.ops.origin_fenced=True
        self.ops.schema_version=lambda:160
        original={'active_slot':self.contract['origin']['slot'],'known_good_release':{
            'sha':self.contract['source_roles']['application_sha'],'slot':self.contract['origin']['slot'],'schema':146},'history':[]}
        (self.path/'state.json').write_text(json.dumps(original))
        self.prepared={'release_sha':self.sha,'candidate_slot':self.slot,'schema':146,
            'images':{k:'fixture@'+self.contract['candidate']['images'][image] for k,image in
                (('backend','backend'),('frontend','frontend'),('worker','backend'))},
            'prepared_at':'2026-10-23T00:00:00Z','status':'candidate_created_fenced'}
        self.record=cli.prepared_release_path(self.path,self.ops);self.record.write_text(json.dumps(self.prepared))
        self.generation=hashlib.sha256(f"bootstrap:{self.sha}:{self.slot}:{self.prepared['prepared_at']}".encode()).hexdigest()
        self.stage={'worker_generation':self.generation}
        self.rows={role:{'State':{'Running':not role.endswith('-worker'),'Restarting':False,
            'Status':'created' if role.endswith('-worker') else 'running'}} for role in candidate_roles(self.contract)}
        self.rows['parser-worker']['State']={'Running':True,'Restarting':False,'Status':'running',
            'Health':{'Status':'healthy'}}
        self.rows['provider-gateway']['State']={'Running':True,'Restarting':False,'Status':'running',
            'Health':{'Status':'healthy'}}
        write_worker_authority(self.path,generation=self.contract['origin']['worker_generation'],owner='CANDIDATE',
            old={'sha':'f'*40,'slot':self.slot},candidate={'sha':self.contract['source_roles']['application_sha'],
                'slot':self.contract['origin']['slot']})
        from unittest.mock import Mock
        self.proof=Mock(return_value={'authenticated_projection':'component-only'})
        for p in (patch.object(admission,'require_maintenance_handoff',self.proof),
                  patch.object(admission,'credential_witness',return_value=self.stage),
                  patch('deployment.lib.completed_normal_resources.verify_runtime_resources',return_value=self.rows)):
            p.start();self.addCleanup(p.stop)

    def activate(self):
        return cli.activate_prepared_release(sha=self.sha,slot=self.slot,state_root=self.path,operations=self.ops)

    def test_existing_child_transfers_only_owner_and_preserves_stopped_workers_and_route(self):
        original=(self.path/'state.json').read_bytes();result=self.activate()
        self.assertEqual(result['status'],'candidate_worker_owner_accepted');self.assertFalse(result['workers_started'])
        self.assertEqual(result['business_writes'],'NORMAL');self.assertFalse(self.ops.old_active);self.assertFalse(self.ops.new_active)
        self.assertFalse(any(call[0] in ('start','stop','route') for call in self.ops.calls))
        owner=load_worker_authority(self.path)
        self.assertEqual(owner['generation'],self.generation)
        self.assertEqual(owner['candidate'],{'sha':self.sha,'slot':self.slot})
        self.assertEqual(owner['owner'],'CANDIDATE');self.assertEqual((self.path/'state.json').read_bytes(),original)
        with self.assertRaisesRegex(RuntimeError,'owner_stage_invalid'):self.activate()

    def test_missing_proof_wrong_schema_substitution_and_consumer_start_refuse_before_owner_change(self):
        initial=load_worker_authority(self.path)
        for fault in ('proof','schema','image','generation','started','origin'):
            saved=copy.deepcopy(self.prepared);self.record.write_text(json.dumps(saved))
            with self.subTest(fault=fault):
                self.proof.side_effect=None;self.ops.schema_version=lambda:160;self.ops.origin_fenced=True
                self.stage['worker_generation']=self.generation
                self.rows['notification-worker']['State']['Running']=False
                if fault=='proof':self.proof.side_effect=RuntimeError('missing_independent_handoff')
                elif fault=='schema':self.ops.schema_version=lambda:159
                elif fault=='image':saved['images']['backend']='fixture@sha256:'+'0'*64;self.record.write_text(json.dumps(saved))
                elif fault=='generation':self.stage['worker_generation']='0'*64
                elif fault=='started':self.rows['notification-worker']['State']['Running']=True
                else:self.ops.origin_fenced=False
                with self.assertRaises(RuntimeError):self.activate()
                self.assertEqual(load_worker_authority(self.path),initial)
                self.assertEqual(json.loads(self.record.read_text())['status'],'candidate_created_fenced')

    def test_interrupted_owner_write_keeps_durable_pending_intent_and_refuses_blind_replay(self):
        writer=cli.write_worker_authority
        def fail(root,**kw):
            writer(root,**kw)
            if kw['owner']=='NONE':raise OSError('lost_owner_write_reply')
        with patch.object(cli,'write_worker_authority',side_effect=fail),self.assertRaises(OSError):self.activate()
        self.assertEqual(load_worker_authority(self.path)['owner'],'NONE')
        self.assertEqual(json.loads(self.record.read_text())['status'],'maintenance_owner_transfer_pending')
        with self.assertRaisesRegex(RuntimeError,'prepared_release_state_invalid'):self.activate()
        self.assertFalse(self.ops.new_active)

    def test_private_parser_must_remain_running_healthy_before_owner_transfer(self):
        initial=load_worker_authority(self.path)
        good=copy.deepcopy(self.rows['parser-worker']['State'])
        for change in ({'Running':False},{'Restarting':True},{'Status':'exited'},
                       {'Health':{'Status':'starting'}},{'Health':{'Status':'unhealthy'}}):
            self.rows['parser-worker']['State']={**good,**change}
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'parser_unready'):self.activate()
            self.assertEqual(load_worker_authority(self.path),initial)
            self.assertEqual(json.loads(self.record.read_text())['status'],'candidate_created_fenced')

    def test_normal_adoption_waits_for_running_candidate_without_readonly_bridge(self):
        from deployment.lib.completed_normal_profile import RECONCILED
        self.activate()
        version={'release_sha':self.sha,'release_slot':self.slot,'schema_compatible_min':146,'schema_compatible_max':160}
        self.ops._json=lambda url:version if url.endswith('/health/version') else {'ready':True}
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch.object(admission,'require_candidate_authority',return_value={'mode':'NORMAL'}),\
                patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED),\
                patch.object(cli.urllib.request,'urlopen',return_value=Response()):
            arguments=dict(sha=self.sha,slot=self.slot,state_root=self.path,
                compatibility=cli.Compatibility(146,160,160,'coordinated',160,160),operations=self.ops)
            with self.assertRaisesRegex(RuntimeError,'promotion_origin_changed'):cli.adopt_prepared_release(**arguments)
            self.ops.new_active=True;self.ops.route=self.slot
            result=cli.adopt_prepared_release(**arguments)
        self.assertEqual(result['schema']['observed'],160)
        self.assertEqual(json.loads((self.path/'state.json').read_bytes())['known_good_release']['schema'],160)
        self.assertIn(('normal_validate',self.sha,self.slot),self.ops.calls)

    def test_changed_sealed_runtime_cannot_be_adopted_from_green_http_alone(self):
        from unittest.mock import Mock
        from deployment.lib.completed_normal_profile import RECONCILED
        self.activate();self.ops.new_active=True;self.ops.route=self.slot
        self.ops._json=lambda url:{'release_sha':self.sha,'ready':True}
        self.ops.verify_completed_normal_runtime=Mock(side_effect=RuntimeError('changed_sealed_runtime'))
        original=(self.path/'state.json').read_bytes()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch.object(admission,'require_candidate_authority',return_value={'mode':'NORMAL'}),\
                patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED),\
                patch.object(cli.urllib.request,'urlopen',return_value=Response()):
            with self.assertRaisesRegex(RuntimeError,'changed_sealed_runtime'):
                cli.adopt_prepared_release(sha=self.sha,slot=self.slot,state_root=self.path,
                    compatibility=cli.Compatibility(146,160,160,'coordinated',160,160),operations=self.ops)
        self.assertEqual((self.path/'state.json').read_bytes(),original)


if __name__=='__main__':unittest.main()
