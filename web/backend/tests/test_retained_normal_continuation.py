"""Stopped-origin and fresh-receipt component tests; no production mutations.

These transport fixtures do not claim a Docker/systemd deployment rehearsal.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch

import test_completed_normal_compose as fixture
from test_completed_normal_manual_profile import manual_contract
from deployment.lib import completed_normal_admission as admission
from deployment.lib import completed_normal_resources as resources
from deployment.lib import runtime_authority as authority
from deployment.lib.completed_normal_profile import expected_origin_grant


def script(name):
    path=fixture.WEB/'scripts'/name
    spec=importlib.util.spec_from_file_location('retained_test_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


child=script('retained_normal_continuation_child.py')
root=script('continue_retained_normal_upgrade.py')


class StoppedOriginTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.contract=manual_contract();c=self.contract
        self.record={'prepared_at':'2026-10-12T00:00:00Z','images':{'backend':'fixture'},'status':'candidate_validated_workers_inactive'}
        self.owner={'owner':'CANDIDATE','generation':c['origin']['worker_generation'],
            'candidate':{'sha':c['source_roles']['application_sha'],'slot':c['origin']['slot']}}
        (self.path/'worker-ownership.json').write_text(json.dumps(self.owner))
        self.state={'active_slot':c['origin']['slot'],'known_good_release':{'sha':c['source_roles']['application_sha'],
            'slot':c['origin']['slot'],'schema':136}}
        self.module=SimpleNamespace(load_prepared_release=lambda *a:copy.deepcopy(self.record),
            _json_file=lambda *a:copy.deepcopy(self.state),hashlib=hashlib,
            atomic_json=Mock(),prepared_release_path=lambda *a:self.path/'prepared.json',
            utc_now=lambda:SimpleNamespace(isoformat=lambda:'2026-10-12T00:01:00Z'))
        self.ops=SimpleNamespace(state_root=self.path,verify_source=Mock(),validate_candidate_core=Mock(),
            worker_ownership=Mock(return_value='none'),require_completed_normal_standbys=Mock(),
            deactivate_workers=Mock(),activate_workers=Mock())
        self.witness={'worker_owner_sha256':root.sha(self.path/'worker-ownership.json'),
            'origin_grant':expected_origin_grant(c,'READ_ONLY'),
            'worker_generation':hashlib.sha256(f"bootstrap:{c['candidate']['source_sha']}:{c['candidate']['slot']}:{self.record['prepared_at']}".encode()).hexdigest()}
        self.original={'runtimes':{k:{'id':str(i)*64,'image':'fixture-image','spec_sha256':'fixture-spec'}
            for i,k in enumerate(('notification-worker','calendar-sync-worker','data-deletion-worker'),1)}}
        self.rows={v['id']:{'Id':v['id'],'Image':v['image'],'State':{'Running':False}}
            for v in self.original['runtimes'].values()}
        runtime=SimpleNamespace(inspect=lambda ids:{key:self.rows[key] for key in ids})
        self.writes=Mock()
        for p in (patch.object(admission,'require_candidate_authority'),patch.object(admission,'credential_witness',return_value=self.original),
                  patch.object(authority,'load_worker_authority',side_effect=lambda *a:copy.deepcopy(self.owner)),
                  patch.object(authority,'write_worker_authority',self.writes),
                  patch.object(resources,'measured_spec_matches',return_value=True),
                  patch('deployment.lib.emergency_routing_repair.Runtime',return_value=runtime)):
            p.start();self.addCleanup(p.stop)

    def activate(self):return child.activate_stopped_origin(self.module,self.ops,self.witness,self.contract)

    def test_both_stopped_handoff_is_none_then_one_candidate_read_only(self):
        result=self.activate()
        self.assertEqual([c.kwargs['owner'] for c in self.writes.call_args_list],['NONE','CANDIDATE'])
        self.assertEqual(result['business_writes'],'READ_ONLY');self.assertEqual(result['worker_generation'],self.witness['worker_generation'])
        self.ops.activate_workers.assert_called_once()

    def test_an_active_or_ambiguous_generation_cannot_be_reinterpreted_as_stopped(self):
        for owner in ('old','candidate','both','ambiguous'):
            self.ops.worker_ownership.return_value=owner
            with self.subTest(owner=owner),self.assertRaisesRegex(RuntimeError,'stopped_origin_required'):self.activate()
        self.writes.assert_not_called();self.ops.activate_workers.assert_not_called()

    def test_stale_owner_and_wrong_grant_rejected_before_handoff(self):
        for change in ({'worker_owner_sha256':'f'*64},{'worker_generation':'f'*64},
                       {'origin_grant':expected_origin_grant(self.contract,'NORMAL')}):
            old=self.witness;self.witness=dict(old,**change)
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.activate()
            self.witness=old
        self.writes.assert_not_called()

    def test_changed_original_spec_or_running_original_worker_rejected(self):
        with patch.object(resources,'measured_spec_matches',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'origin_worker_changed'):self.activate()
        next(iter(self.rows.values()))['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'origin_worker_changed'):self.activate()
        self.writes.assert_not_called()

    def test_interrupted_startup_fences_candidate_and_never_marks_it_active(self):
        self.ops.activate_workers.side_effect=RuntimeError('fixture_interruption')
        with self.assertRaisesRegex(RuntimeError,'fixture_interruption'):self.activate()
        self.assertEqual(self.ops.deactivate_workers.call_count,2)
        self.assertTrue(all(c.args[1]['status']=='candidate_validated_workers_inactive' for c in self.module.atomic_json.call_args_list))

    def test_replay_after_state_adoption_rejected(self):
        self.state['known_good_release']['sha']=self.contract['candidate']['source_sha']
        with self.assertRaisesRegex(RuntimeError,'stopped_origin_required'):self.activate()
        self.writes.assert_not_called()


class FreshContinuationGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.package=self.path/'package';self.package.mkdir()
        self.manifest={'files':{'child.py':hashlib.sha256(b'fixture').hexdigest()}}
        (self.package/'child.py').write_bytes(b'fixture');(self.package/'source-bundle.json').write_bytes(root.encoded(self.manifest))
        self.d=root.Continuation.__new__(root.Continuation);self.d.package=self.package;self.d.manifest=self.manifest
        self.d.source_hash=root.sha(self.package/'source-bundle.json');self.d.actor=SimpleNamespace(root=self.path,guard=Mock())
        self.d.plan={'initial':{'bindings':{'records':{}}}};self.d.active=True;self.d.scope=self.path/'scope';self.d.scope.mkdir()
        self.expected={'operation':root.OPERATION,'plan_sha256':root.digest(self.d.plan),'source_sha256':self.d.source_hash,
            'parent_context_sha256':self.path.name,'historical_authorization_reused':False}
        self.receipt=self.d.scope/'operator-authorization.json';self.receipt.write_bytes(root.encoded(self.expected))
        p=patch.object(root,'secure',side_effect=lambda path:path);p.start();self.addCleanup(p.stop)

    def test_fresh_scope_receipt_required_and_consumed_failure_rejected(self):
        self.d.guard();self.receipt.write_bytes(root.encoded(dict(self.expected,historical_authorization_reused=True)))
        with self.assertRaisesRegex(RuntimeError,'fresh_authorization_changed'):self.d.guard()
        self.receipt.write_bytes(root.encoded(self.expected));(self.d.scope/'failure.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'authorization_consumed'):self.d.guard()

    def test_changed_executable_rejected_before_existing_controller_guard(self):
        (self.package/'child.py').write_bytes(b'altered')
        with self.assertRaisesRegex(RuntimeError,'executable_changed'):self.d.guard()
        self.d.actor.guard.assert_not_called()

    def test_ci_binds_both_workflows_to_new_execution_commit(self):
        git='a'*40;self.d.manifest['source_git']=git
        rows=[{'databaseId':i,'headSha':git,'status':'completed','conclusion':'success','workflowName':name,
               'url':'https://github.com/judahsleibi34/Madar/actions/runs/'+str(i)}
              for i,name in enumerate(('Backend Check','Frontend Check'),1)]
        self.d.actor.ops=SimpleNamespace(command=Mock(side_effect=lambda *a:SimpleNamespace(stdout=json.dumps(rows))))
        self.assertEqual(len(self.d.execution_ci()),2)
        rows[1]['headSha']='b'*40
        with self.assertRaisesRegex(RuntimeError,'exact_source_ci_missing'):self.d.execution_ci()
        rows[1]['headSha']=git;rows[1]['conclusion']='failure'
        with self.assertRaisesRegex(RuntimeError,'exact_source_ci_incomplete'):self.d.execution_ci()


class LiveWriteTransportTests(unittest.TestCase):
    def test_real_login_shape_committed_readback_and_only_new_identity_disabled(self):
        probe=script('retained_normal_live_write_probe.py')
        with tempfile.TemporaryDirectory() as tmp:
            scope=Path(tmp);plan_hash='a'*64;email='release-check-'+plan_hash[:16]+'@madar.example.com'
            auth_id='11111111-1111-4111-8111-111111111111';phone='970590111111';requests=[]
            class Response:
                status=200
                def __init__(self,value):self.value=value
                def __enter__(self):return self
                def __exit__(self,*a):return False
                def read(self,*a):return json.dumps(self.value).encode()
            class Opener:
                def open(self,request,**kw):
                    body=json.loads(request.data) if request.data else None
                    requests.append((request.full_url,request.method,body))
                    if request.full_url.endswith('/admin/users'):
                        return Response({'id':auth_id,'email':email})
                    if '/admin/users/' in request.full_url:return Response({'id':auth_id})
                    if request.full_url.endswith('/login'):return Response({'user':{'id':9},'csrf_token':'fixture-csrf'})
                    if request.full_url.endswith('/info'):return Response({'user':{'phone':phone}})
                    return Response({'success':True})
            gateway={'Id':'gateway','Image':'gateway-image','State':{'Running':True},
                'Config':{'Labels':{'com.docker.compose.service':'api-gw','com.docker.compose.project':'madar-local-supabase'}},
                'NetworkSettings':{'Networks':{'native':{'NetworkID':'native-id','IPAddress':'192.0.2.4'}}}}
            kernel=SimpleNamespace(round=Mock(),bindings=lambda:{'backend':{'Config':{'Env':['SUPABASE_SERVICE_KEY=fixture-service']}}})
            commands=[]
            def command(args):
                commands.append(args)
                return '0\n' if 'count(*)' in args[-1] else phone+'\n'
            actor=SimpleNamespace(candidate=lambda:kernel,contract={'database':{'container_id':'private-native',
                'network_name':'native','network_id':'native-id'}},runtime=SimpleNamespace(command=command,inspect=lambda names:{'supabase-envoy':gateway}))
            with patch.object(probe.urllib.request,'build_opener',side_effect=lambda *a:Opener()),patch.object(resources,'measured_spec',return_value='gateway-spec'):
                result=probe.run(actor,scope,plan_hash,{'id':'gateway','image':'gateway-image','spec_sha256':'gateway-spec'})
            self.assertTrue(result['fresh_session_readback']);self.assertTrue(result['native_database_readback'])
            self.assertEqual(requests[-1],('http://192.0.2.4:8000/auth/v1/admin/users/'+auth_id,'PUT',{'ban_duration':'87600h'}))
            self.assertEqual(sum(url.endswith('/login') for url,_,_ in requests),2)
            self.assertTrue(all('BEGIN READ ONLY' in command[-1] for command in commands))
            self.assertNotIn('password',json.dumps(result));self.assertNotIn('fixture-service',json.dumps(result))
            self.assertFalse(result['customer_account_used'])


if __name__=='__main__':unittest.main()
