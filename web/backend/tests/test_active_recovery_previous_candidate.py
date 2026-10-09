"""Bound pre-publication continuation tests; no runtime acceptance claims."""
from dataclasses import asdict
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from tests import test_active_recovery_candidate as candidate_tests
from deployment.lib.active_recovery_candidate import inspect_previous_candidate,KINDS
from deployment.lib.provider_recovery_runtime import digest,file_digest

class PreviousCandidateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=candidate_tests.DetachedCandidateTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.previous=self.fixture.plan;self.root=self.fixture.c.root
        (self.root/'plan.json').write_text(json.dumps(asdict(self.previous),sort_keys=True))
        for name in ('candidate-contract.json','candidate-identities.json'):(self.root/name).write_text('{}')
        (self.root/'write-authority').mkdir();(self.root/'write-authority/authority.json').write_text('{}')
        (self.root/'events.jsonl').write_text(''.join(json.dumps({'phase':p,'plan_sha256':self.previous.digest})+'\n' for p in ('authorized','detached_candidate_pending','detached_candidate_failed')))
        self.rows={k:{'Id':k,'Image':self.previous.candidate_images['frontend' if k=='frontend' else 'backend'],
            'State':{'Running':k not in KINDS,'Status':'created' if k in KINDS else 'running'},
            'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':({'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':'8201'}]} if k=='backend' else {'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'3200'}]} if k=='frontend' else {})}} for k in ('backend','frontend','parser',*KINDS)}
        value=Mock(slot='green',backend_port=8201,frontend_port=3200);value.inspect.side_effect=lambda name:copy.deepcopy(self.rows[name]);value.name.side_effect=lambda kind:kind
        value.health_json.side_effect=lambda url:(200,{'release_sha':self.previous.source_sha} if url.endswith('version') else {'restricted':True,'business_writes_enabled':False})
        value.endpoint.side_effect=lambda kind:'http://127.0.0.1:'+str(8201 if kind=='backend' else 3200)
        self.value=value
        self.plan=SimpleNamespace(digest='0'*64,retained_inputs=self.previous.retained_inputs,fallback=self.previous.fallback,candidate_destination={})
        self.rebind()
        item=patch('deployment.lib.active_recovery_candidate.DetachedRecoveryCandidate.from_saved_runtime',return_value=value);item.start();self.addCleanup(item.stop)
    def rebind(self):
        names=('authorization.json','plan.json','events.jsonl','candidate-contract.json','candidate-identities.json','write-authority/authority.json')
        self.plan.candidate_destination={'previous_candidate':{'plan_sha256':self.previous.digest,'evidence_sha256':digest({n:file_digest(self.root/n) for n in names})}}
    def test_valid_failed_candidate_binds_original_records_and_created_workers(self):
        result=inspect_previous_candidate(self.plan)
        self.assertEqual(result['root'],self.root);self.value.verify_recorded_runtime.assert_called_once();self.value.command.assert_not_called()
    def test_changed_protected_bytes_fail_without_effect(self):
        (self.root/'candidate-identities.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(RuntimeError,'evidence_changed'):inspect_previous_candidate(self.plan)
        self.value.command.assert_not_called()
    def test_postpublication_failure_cannot_use_narrow_retirement(self):
        with (self.root/'events.jsonl').open('a') as f:f.write(json.dumps({'plan_sha256':self.previous.digest,'phase':'read_only_serving'})+'\n')
        self.rebind()
        with self.assertRaisesRegex(RuntimeError,'not_prepublication'):inspect_previous_candidate(self.plan)
    def test_started_business_worker_or_wrong_image_is_rejected(self):
        for defect in ('start','image','restart','port','write_fence'):
            original=copy.deepcopy(self.rows);original_health=self.value.health_json.side_effect
            if defect=='start':self.rows['notification']['State']={'Running':True,'Status':'running'}
            elif defect=='image':self.rows['backend']['Image']='sha256:'+'0'*64
            elif defect=='restart':self.rows['frontend']['HostConfig']['RestartPolicy']['Name']='always'
            elif defect=='port':self.rows['backend']['HostConfig']['PortBindings']={}
            else:self.value.health_json.side_effect=lambda url:(200,{'release_sha':self.previous.source_sha} if url.endswith('version') else {'restricted':False,'business_writes_enabled':True})
            with self.subTest(defect=defect),self.assertRaises(RuntimeError):inspect_previous_candidate(self.plan)
            self.rows=original;self.value.health_json.side_effect=original_health
    def test_runtime_identity_or_network_failure_is_not_ignored(self):
        self.value.verify_recorded_runtime.side_effect=RuntimeError('identity_changed')
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):inspect_previous_candidate(self.plan)
    def test_stopped_nonbusiness_services_remain_valid_without_starting(self):
        for kind in ('backend','frontend','parser'):self.rows[kind]['State']={'Running':False,'Status':'exited'}
        inspect_previous_candidate(self.plan);self.value.command.assert_not_called()
