"""Synthetic governed worker handoff; never starts a real worker."""
from dataclasses import asdict,replace
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_resumption import ResumptionPlan
from deployment.lib.active_recovery_inputs import KEYS
from deployment.lib.active_recovery_workers import ActiveRecoveryWorkerHandoff,KINDS
from deployment.lib.provider_local_transition import LocalTransitionContract
from deployment.lib.provider_recovery_runtime import digest
from deployment.lib.emergency_routing_repair import spec

class Candidate:
    slot='green';network_name='normal-network'
    def __init__(self,contract):
        self.recovery=SimpleNamespace(contract=SimpleNamespace(origin_sha='f'*40))
        self.contract=contract;self.calls=[];self.rows={};self.health={'healthy':True,'status':'ok','consuming':False}
        for i,kind in enumerate(('backend','frontend',*KINDS)):
            for prefix in ('old','new'):
                name=(f'madar-green-{kind}'+('-worker' if kind in KINDS else '')) if prefix=='old' else self.name(kind)
                self.rows[name]={'Name':'/'+name,'Id':str(i*2+(1 if prefix=='old' else 2)).zfill(64),
                    'Image':contract.images['frontend' if kind=='frontend' else 'backend'],
                    'Config':{},'HostConfig':{'RestartPolicy':{'Name':'no'}},'Mounts':[],
                    'State':{'Running':prefix=='new' and kind not in KINDS},
                    'NetworkSettings':{'Networks':{self.network_name:{'IPAddress':'10.0.0.1','NetworkID':'d'*64}}}}
    def name(self,kind):return 'madar-normal-fixture-'+kind+('-standby' if kind in KINDS else '')
    def inspect(self,name):
        name=next((key for key,row in self.rows.items() if row['Id']==name),name)
        return copy.deepcopy(self.rows[name])
    def require_write_authority(self,contract,mode):
        if mode!='READ_ONLY':raise RuntimeError('synthetic_mode')
    def command(self,args):
        self.calls.append(args)
        if args[1:3]==['ps','-a']:return '\n'.join(self.rows)
        if args[1]=='rename':
            row=self.rows.pop(args[2]);row['Name']='/'+args[3];self.rows[args[3]]=row
        if args[1] in {'start','stop'}:
            name=next((key for key,row in self.rows.items() if row['Id']==args[2]),args[2]);self.rows[name]['State']['Running']=args[1]=='start'
        return ''
    def health_json(self,url):return 200,self.health

class WorkerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        identity={'container_id':'b'*64,'image_id':'sha256:'+'c'*64,'spec_sha256':'d'*64}
        self.plan=ResumptionPlan('a'*40,'b'*64,{'backend':'sha256:'+'c'*64,'frontend':'sha256:'+'d'*64},
            {key:'e'*64 for key in KEYS},{'backend':identity,'frontend':identity},'f'*64,'1'*64,'2'*64,'3'*64,'4'*64)
        fp={key:'e'*64 for key in ('environment','state','upstream','worker_authority','controller','recovery','traffic')}
        contract=LocalTransitionContract('a'*40,self.plan.candidate_images,'f'*64,'f'*64,'2'*64,'3'*64,fp)
        self.c=Candidate(contract)
        deps={'runtimes':{name:{'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row)} for name,row in self.c.rows.items() if name.startswith('madar-green-')}}
        bindings=dict(self.plan.retained_inputs);bindings['runtime_dependencies']=digest(deps);self.plan=replace(self.plan,retained_inputs=bindings)
        self.root=base/self.plan.digest;self.root.mkdir()
        (self.root/'runtime-dependencies.json').write_text(json.dumps(deps))
        runtimes={kind:{'id':self.c.inspect(self.c.name(kind))['Id'],'image':self.c.inspect(self.c.name(kind))['Image'],
            'spec_sha256':spec(self.c.inspect(self.c.name(kind)))} for kind in ('backend','frontend',*KINDS)}
        (self.root/'candidate-identities.json').write_text(json.dumps({'runtimes':runtimes}))
        (self.root/'authorization.json').write_text(json.dumps({'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}))
        self.phase='controller_resumed';self.save_phase()
        for target,value in [('ROOT',base),('protected',lambda path,**kw:path)]:
            p=patch('deployment.lib.active_recovery_workers.'+target,value);p.start();self.addCleanup(p.stop)
        p=patch('deployment.lib.active_recovery_workers.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid()));p.start();self.addCleanup(p.stop)
        p=patch('deployment.lib.active_recovery_workers.os.geteuid',return_value=0);p.start();self.addCleanup(p.stop)
        self.w=ActiveRecoveryWorkerHandoff(self.plan,self.c,self.root,lambda:None);self.w.state=base/'state';self.w.state.mkdir()
        (self.w.state/'worker-ownership.json').write_text('{"original_fixture":true}')
    def save_phase(self):
        (self.root/'events.jsonl').write_text(json.dumps({'phase':self.phase,'plan_sha256':self.plan.digest})+'\n')
    def test_preserves_old_resources_and_nonconsuming_standbys(self):
        old={name:row['Id'] for name,row in self.c.rows.items() if name.startswith('madar-green-')}
        self.w.establish_owner();self.w.start_standbys()
        self.assertEqual((self.root/'worker-ownership-preimage.json').read_text(),'{"original_fixture":true}')
        for name,identity in old.items():self.assertEqual(self.c.inspect(name+'-retired-'+self.plan.digest[:12])['Id'],identity)
        self.assertEqual(sum(args[1]=='start' for args in self.c.calls),3)
    def test_pre_handoff_phase_cannot_rename_or_start(self):
        self.phase='read_only_handoff_pending';self.save_phase()
        with self.assertRaisesRegex(RuntimeError,'phase_denied'):self.w.establish_owner()
        self.assertEqual(self.c.calls,[])
    def test_modified_old_slot_or_collision_prevents_any_rename(self):
        self.c.rows['madar-green-backend']['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'retained_slot_changed'):self.w.establish_owner()
        self.assertFalse(any(args[1]=='rename' for args in self.c.calls))
    def test_running_old_consumer_aborts_ownership(self):
        self.c.rows['madar-green-notification-worker']['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'retained_slot_changed'):self.w.establish_owner()
    def test_standby_cannot_consume_before_positive_grant(self):
        self.w.establish_owner();self.c.health['consuming']=True
        with self.assertRaisesRegex(RuntimeError,'nonconsuming'):self.w.start_standbys()
    def test_changed_owner_or_candidate_spec_rejected(self):
        self.w.establish_owner();name='madar-green-notification-worker';self.c.rows[name]['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'active_spec_changed'):self.w.verify_owner()
    def test_compensation_stops_by_original_candidate_ids(self):
        self.w.establish_owner();self.w.start_standbys();self.phase='compensation_pending';self.save_phase();self.w.stop_consumers()
        self.assertTrue(all(not self.c.inspect('madar-green-'+kind+'-worker')['State']['Running'] for kind in KINDS))

    def test_audit_append_failure_cannot_prevent_safe_consumer_stop(self):
        self.w.establish_owner();self.w.start_standbys()
        # The old phase remains when compensation reporting cannot append.
        self.phase='write_grant_pending';self.save_phase();self.w.stop_consumers()
        self.assertTrue(all(not self.c.inspect('madar-green-'+kind+'-worker')['State']['Running'] for kind in KINDS))


    def test_real_worker_health_shapes_are_accepted(self):
        self.w.establish_owner()
        def health(url):
            if ':8091/' in url:return 200,{'healthy':True,'consuming':False}
            return 200,{'status':'ok','consuming':False,'last_poll_at':None}
        self.c.health_json=health;self.w.start_standbys()

    def test_incorrect_health_shape_cannot_report_standby_success(self):
        self.w.establish_owner();self.c.health={'healthy':True,'consuming':False}
        with self.assertRaisesRegex(RuntimeError,'nonconsuming'):self.w.start_standbys()


    def test_actual_worker_health_handlers_match_the_handoff_verifier(self):
        import io
        from unittest.mock import Mock
        from workers import notification_worker,calendar_sync_worker,data_deletion_worker
        workers={8090:notification_worker,8091:calendar_sync_worker,8094:data_deletion_worker}
        self.w.establish_owner()
        def health(url):
            port=int(url.split(':')[2].split('/')[0]);module=workers[port]
            with patch.dict(module.STATE,{'healthy':True,'consuming':False}):
                handler=module.HealthHandler.__new__(module.HealthHandler)
                handler.path='/health';handler.wfile=io.BytesIO()
                handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock()
                handler.do_GET();handler.send_response.assert_called_once_with(200)
                return 200,json.loads(handler.wfile.getvalue())
        self.c.health_json=health;self.w.start_standbys()

    def test_one_changed_consumer_cannot_skip_stopping_other_bound_consumers(self):
        self.w.establish_owner();self.w.start_standbys()
        self.c.rows['madar-green-notification-worker']['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'stop_incomplete'):self.w.stop_consumers()
        for kind in ('calendar-sync','data-deletion'):
            self.assertFalse(self.c.inspect('madar-green-'+kind+'-worker')['State']['Running'])
