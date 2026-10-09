"""Fresh compensation boundaries, using synthetic inputs only."""
import json
import copy
from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_inputs import KEYS
from deployment.lib.active_recovery_resumption import ResumptionPlan
from deployment.lib.active_recovery_fallback import CurrentDataFallback

class FreshFallbackAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        identity={'container_id':'b'*64,'image_id':'sha256:'+'c'*64,'spec_sha256':'d'*64}
        self.plan=ResumptionPlan('a'*40,'b'*64,{'backend':'sha256:'+'c'*64,'frontend':'sha256:'+'d'*64},
            {key:'e'*64 for key in KEYS},{'backend':identity,'frontend':identity},'f'*64,'1'*64,'2'*64,'3'*64,'4'*64)
        self.root=Path(self.tmp.name)/self.plan.digest;self.root.mkdir();(self.root/'write-authority').mkdir()
        self.receipt={'operation':'active-local-rollback-resumption','plan_sha256':self.plan.digest,'source_bundle_sha256':self.plan.source_bundle_sha256}
        self.event={'phase':'compensation_pending','plan_sha256':self.plan.digest}
        self.authority={'mode':'READ_ONLY','schema':115,'release_sha':self.plan.source_sha}
        self.candidate={'source_sha':self.plan.source_sha,'plan_sha256':self.plan.digest}
        self.save()
        for name,value in [('ROOT',Path(self.tmp.name)),('protected',lambda path,**kw:path)]:
            p=patch('deployment.lib.active_recovery_fallback.'+name,value);p.start();self.addCleanup(p.stop)
        p=patch('deployment.lib.active_recovery_fallback.os.geteuid',return_value=0);p.start();self.addCleanup(p.stop)
        self.f=CurrentDataFallback(self.plan,self.root,runtime=object())
    def save(self):
        for path,value in [('authorization.json',self.receipt),('candidate-identities.json',self.candidate),('write-authority/authority.json',self.authority)]:
            (self.root/path).write_text(json.dumps(value))
        (self.root/'events.jsonl').write_text(json.dumps(self.event)+'\n')
    def test_fresh_compensation_is_allowed_without_old_run_credentials(self):
        self.f.require_compensation_authority()
        self.event['phase']='restricted_fallback';self.save();self.f.require_compensation_authority()
    def test_positive_normal_authority_must_be_revoked_first(self):
        self.authority['mode']='NORMAL';self.save()
        with self.assertRaisesRegex(RuntimeError,'not_fenced'):self.f.require_compensation_authority()
    def test_wrong_plan_source_or_candidate_is_rejected(self):
        for record,key in [(self.receipt,'plan_sha256'),(self.receipt,'source_bundle_sha256'),(self.candidate,'source_sha')]:
            old=record[key];record[key]='0'*64;self.save()
            with self.assertRaises(RuntimeError):self.f.require_compensation_authority()
            record[key]=old;self.save()
    def test_normal_or_failed_compensation_phase_cannot_forward(self):
        for phase in ('normal','write_grant_pending','compensation_failed','controller_resumed'):
            self.event['phase']=phase;self.save()
            with self.assertRaisesRegex(RuntimeError,'not_authorized'):self.f.require_compensation_authority()
    def test_existing_evidence_is_not_rewritten(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.f.require_compensation_authority()
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})


class SyntheticRuntime:
    def __init__(self):
        from deployment.lib.provider_recovery_runtime import SERVICES
        canonical=[f'madar-{slot}-{kind}-worker' for slot in ('blue','green') for kind in ('notification','calendar-sync','data-deletion')]
        self.rows={}
        for index,name in enumerate([*SERVICES,*canonical,'registered-backend','registered-frontend']):
            role=name.removeprefix('registered-')
            self.rows[name]={'Name':'/'+name,'Id':str(index+1).zfill(64),'Image':'sha256:'+'c'*64,
                'Config':{'Labels':{'org.opencontainers.image.revision':'f'*40}},
                'HostConfig':{'RestartPolicy':{'Name':'no'}},'Mounts':[],
                'State':{'Running':name not in canonical,'Health':{'Status':'healthy'}},
                'NetworkSettings':{'Ports':{},'Networks':{'internal':{'NetworkID':'d'*64,'IPAddress':'10.0.0.'+str(index+1),'Aliases':[role]}}}}
        self.published=False
    def inspect(self,names):
        by_id={row['Id']:name for name,row in self.rows.items()}
        return {by_id.get(name,name):copy.deepcopy(self.rows[by_id.get(name,name)]) for name in names}
    def names(self):return list(self.rows)
    def network(self,name):return {'Id':'d'*64,'Internal':True,'Driver':'bridge'}
    def schema(self):pass
    def json_http(self,url):
        if url.endswith('/health/ready'):return {'ready':True,'components':{key:'ok' for key in ('database','auth','schema','storage')}}
        if url.endswith('/health/version'):return {'release_sha':'f'*40,'release_slot':'local-fallback','schema_compatible_min':115,'schema_compatible_max':115}
        return {'restricted':True,'business_writes_enabled':False}
    def denied(self,base):pass
    def http_status(self,url):pass

class FreshFallbackRuntimeTests(FreshFallbackAuthorityTests):
    def setUp(self):
        super().setUp()
        from deployment.lib.active_recovery_fallback import UNCHANGED
        from deployment.lib.provider_recovery_runtime import SERVICES,digest
        from deployment.lib.emergency_routing_repair import spec
        self.r=SyntheticRuntime()
        bindings=dict(self.plan.retained_inputs);paths={}
        import hashlib
        for key in UNCHANGED:
            path=Path(self.tmp.name)/(key+'.json')
            path.write_text(json.dumps({'phase':'local_rollback_active'}) if key.endswith('transaction') else '{}')
            paths[key]=path;bindings[key]=hashlib.sha256(path.read_bytes()).hexdigest()
        deps={'runtimes':{name:{'container_id':row['Id'],'image_id':row['Image'],'spec_sha256':spec(row),
            'running':row['State']['Running'],'networks':{key:value['NetworkID'] for key,value in row['NetworkSettings']['Networks'].items()}}
            for name,row in self.r.rows.items() if name in SERVICES or name.startswith('madar-')},'networks':{}}
        (self.root/'runtime-dependencies.json').write_text(json.dumps(deps));bindings['runtime_dependencies']=digest(deps)
        fallback={role:{'container_id':self.r.rows['registered-'+role]['Id'],'image_id':self.r.rows['registered-'+role]['Image'],
            'spec_sha256':spec(self.r.rows['registered-'+role])} for role in ('backend','frontend')}
        self.plan=replace(self.plan,retained_inputs=bindings,fallback=fallback)
        newroot=self.root.with_name(self.plan.digest);self.root.rename(newroot);self.root=newroot
        self.receipt['plan_sha256']=self.plan.digest;self.event['plan_sha256']=self.plan.digest;self.candidate['plan_sha256']=self.plan.digest;self.save()
        for name,value in [('INPUTS',paths),('readonly_configuration',lambda path,**kw:path)]:
            p=patch('deployment.lib.active_recovery_fallback.'+name,value);p.start();self.addCleanup(p.stop)
        self.f=CurrentDataFallback(self.plan,self.root,runtime=self.r)
    def test_resolves_actual_role_addresses(self):
        result=self.f.verify();self.assertEqual(result['backend'][1],8000);self.assertEqual(result['frontend'][1],8080)
        self.r.rows['registered-backend']['NetworkSettings']['Networks']['internal']['IPAddress']='10.0.0.88'
        self.assertEqual(self.f.verify()['backend'][0],'10.0.0.88')
    def test_modified_native_or_fallback_image_rejected(self):
        for name in ('supabase-auth','registered-frontend'):
            original=self.r.rows[name]['Image'];self.r.rows[name]['Image']='sha256:'+'a'*64
            with self.subTest(name=name),self.assertRaises(RuntimeError):self.f.verify()
            self.r.rows[name]['Image']=original
    def test_any_started_old_or_new_consumer_rejected(self):
        self.r.rows['madar-blue-notification-worker']['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'consumer_not_stopped'):self.f.verify()
    def test_public_destination_rejected(self):
        self.r.rows['registered-backend']['NetworkSettings']['Networks']['internal']['IPAddress']='8.8.8.8'
        with self.assertRaisesRegex(RuntimeError,'not_private'):self.f.verify()
    def test_changed_retained_transaction_rejected(self):
        from deployment.lib.active_recovery_fallback import INPUTS
        INPUTS['local_transaction'].write_text('{"phase":"normal"}')
        with self.assertRaisesRegex(RuntimeError,'input_changed'):self.f.verify()


class CompensationPublicationTests(unittest.TestCase):
    def setUp(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from tests.test_active_recovery_handoff import Clock,Runtime
        from deployment.lib.active_recovery_fallback import CompensationPublication
        self.clock=Clock();self.runtime=Runtime(self.clock)
        self.verifier=SimpleNamespace(plan=SimpleNamespace(retained_inputs={'proxy_configuration':'a'*64}),verify=lambda:None)
        self.pub=CompensationPublication(self.verifier,Path('/synthetic'),runtime=self.runtime)
        for target,value in [('time.monotonic',self.clock.now),('time.sleep',self.clock.sleep)]:
            p=patch('deployment.lib.active_recovery_fallback.'+target,value);p.start();self.addCleanup(p.stop)
        @contextmanager
        def window(runtime,seconds):runtime.deadline=self.clock.value+seconds;yield
        p=patch('deployment.lib.active_recovery_fallback.verification_window',window);p.start();self.addCleanup(p.stop)
    def test_compensation_validates_then_reloads_and_sustains(self):
        self.pub.publish(lambda route:None)
        self.assertEqual(self.runtime.calls,['nginx_preflight','publish','reload']);self.assertGreaterEqual(self.clock.value,5)
    def test_transient_502_then_success_has_no_immediate_maintenance(self):
        from deployment.lib.emergency_routing_repair import AvailabilityFailure
        count=[0]
        def request(route):
            count[0]+=1
            if count[0]<3:raise AvailabilityFailure('synthetic')
        self.pub.publish(request);self.assertGreaterEqual(self.clock.value,7)
        self.assertNotIn('stop_proxy',self.runtime.calls)
    def test_failed_integrity_never_publishes(self):
        def reject():raise RuntimeError('changed_image')
        self.verifier.verify=reject
        with self.assertRaisesRegex(RuntimeError,'changed_image'):self.pub.publish(lambda route:None)
        self.assertEqual(self.runtime.calls,[])
    def test_failed_compensation_deadline_is_sixty_seconds(self):
        from deployment.lib.emergency_routing_repair import AvailabilityFailure,VerificationDeadline
        def pending(route):raise AvailabilityFailure('synthetic')
        with self.assertRaises(VerificationDeadline):self.pub.publish(pending)
        self.assertEqual(self.clock.value,60)
    def test_failed_maintenance_stops_only_proxy(self):
        self.runtime.fail='reload';self.pub.maintenance_or_stop_proxy()
        self.assertEqual(self.runtime.calls,['nginx_preflight','publish','reload','stop_proxy'])
    def test_missing_source_guard_cannot_bind_listener(self):
        from deployment.lib.active_recovery_fallback import restricted_listeners
        with patch('deployment.lib.active_recovery_fallback.Relay') as listener:
            with self.assertRaisesRegex(RuntimeError,'source_guard_required'):restricted_listeners(self.verifier,None)
            listener.assert_not_called()
