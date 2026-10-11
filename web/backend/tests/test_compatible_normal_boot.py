import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import compatible_normal_boot as m
from deployment.lib import completed_normal_admission as admission
from deployment.lib.emergency_routing_repair import Runtime, spec, AvailabilityFailure
from deployment.lib.runtime_authority import write_worker_authority
from test_completed_normal_admission import fixture_contract


class Clock:
    value=0.0
    def monotonic(self):return self.value
    def sleep(self,seconds):self.value += seconds


class FixtureRuntime(Runtime):
    def __init__(self,contract):
        self.contract=contract;self.rows={};self.mode='NORMAL';self.starts=[];self.pending=0
    def inspect(self,names):return {n:self.rows[n] for n in names if n in self.rows}
    def command(self,args,**kw):
        if args[:3]==['docker','network','inspect']:return json.dumps([{'Id':'network-object'}])
        if args[:2]==['docker','start']:
            self.starts.append(args[2]);self.rows[args[2]]['State']['Running']=True;return ''
        raise AssertionError('unexpected fixture command')
    def json_http(self,url):
        if self.pending:
            self.pending-=1;raise AvailabilityFailure('worker_activation_pending')
        if url.endswith('/health/version'):
            return {'release_sha':'c'*40,'release_slot':'green','schema_compatible_min':115,'schema_compatible_max':136}
        if url.endswith('/health/recovery'):
            return {'restricted':self.mode=='READ_ONLY','business_writes_enabled':self.mode=='NORMAL'}
        return {'healthy':True,'status':'ok','consuming':self.mode=='NORMAL'}
    def denied(self,url):
        if self.mode!='READ_ONLY':raise RuntimeError('fixture_fence_failed')
    def http_status(self,url):return None
    def fetch(self,url,**kw):
        return 200,json.dumps({'ready':True,'components':{k:'ok' for k in (
            'database','auth','schema','storage','redis','environment','admin_mfa_policy','parser_isolation')}}).encode()


class CompatibleBootTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.contract=fixture_contract();self.runtime=FixtureRuntime(self.contract)
        self.root=self.path/admission.digest(self.contract);self.root.mkdir()
        self.schema=136;self.compensations=[];self.publications=[]
        self.owner=write_worker_authority(self.path,generation='f'*64,owner='CANDIDATE',
            old={'sha':'a'*40,'slot':'blue'},candidate={'sha':'c'*40,'slot':'green'})
        publication={'operation':admission.OPERATION,'context_sha256':admission.digest(self.contract),
            'source_sha':'c'*40,'images':self.contract['candidate']['images'],'runtimes':{},
            'networks':{'fixture-primary':'network-object'},'worker_generation':'f'*64,'origin_workers':['old1','old2','old3']}
        for index,kind in enumerate(m.ROLES):
            cid='candidate-'+str(index)
            image=self.contract['candidate']['images']['frontend' if kind=='frontend' else 'backend']
            row={'Id':cid,'Image':image,'Config':{'Env':['fixture=true']},'HostConfig':{'RestartPolicy':{'Name':'no'},'Dns':None,'NetworkMode':'fixture-primary'},
                'Mounts':[],'State':{'Running':False,'Status':'exited','Health':{'Status':'healthy'}},
                'NetworkSettings':{'Networks':{'fixture-primary':{'NetworkID':'network-object','IPAddress':'10.0.0.2'}}}}
            self.runtime.rows[cid]=row
            publication['runtimes'][kind]={'id':cid,'image':image,'spec_sha256':spec(row),'networks':{'fixture-primary':'network-object'},'network_aliases':{'fixture-primary':[]}}
        for cid in publication['origin_workers']:
            self.runtime.rows[cid]={'Id':cid,'State':{'Running':False},'HostConfig':{'RestartPolicy':{'Name':'no'}}}
        (self.root/'normal-publication.json').write_text(json.dumps(publication))
        (self.root/'admission.json').write_text(json.dumps({'operation':admission.OPERATION,'contract':self.contract}))
        self.kernel=m.CompatibleNormalBoot(self.contract,source_guard=lambda:None,native_verifier=lambda:self.schema,
            normal_resume_guard=lambda schema:None,publish_authority=self.publish,compensate_current_data=self.compensate,runtime=self.runtime,admissions=self.path,state_root=self.path)
        def authority(contract,*,mode=None,**kw):
            if mode is not None and mode!=self.runtime.mode:raise RuntimeError('candidate_authority_changed')
            return {'mode':self.runtime.mode}
        self.clock=Clock()
        for p in (patch.object(m,'protected',lambda p,**kw:p),patch.object(m.os,'geteuid',return_value=0),
                  patch.object(m,'require_candidate_authority',side_effect=authority),
                  patch.object(m.time,'monotonic',self.clock.monotonic),patch.object(m.time,'sleep',self.clock.sleep)):
            p.start();self.addCleanup(p.stop)

    def publish(self,mode):self.publications.append(mode);self.runtime.mode=mode
    def compensate(self):self.compensations.append('current-data-preserving');self.runtime.mode='READ_ONLY'

    def test_schema115_and136_boot_fence_then_start_only_exact_compatible_ids(self):
        for schema in (115,136):
            with self.subTest(schema=schema):
                self.schema=schema;self.runtime.mode='NORMAL';self.publications.clear()
                result=self.kernel.execute()
                self.assertEqual(result['schema'],schema);self.assertFalse(result['database_restored'])
                self.assertEqual(self.publications,['READ_ONLY','NORMAL'])
                self.assertFalse(any(name.startswith('old') for name in self.runtime.starts))
                self.assertGreaterEqual(self.clock.value,10)

    def test_delayed_activation_requires_consecutive_rounds(self):
        self.runtime.pending=2
        self.kernel.execute()
        self.assertGreaterEqual(self.clock.value,12)
        self.assertEqual(self.compensations,[])

    def test_revocation_verification_waits_without_starts_or_positive_publication(self):
        self.runtime.mode='READ_ONLY';self.runtime.pending=2
        for row in self.runtime.rows.values():
            if row.get('Id','').startswith('candidate'):row['State']['Running']=True
        self.kernel.verify_mode(normal=False)
        self.assertGreaterEqual(self.clock.value,7)
        self.assertEqual(self.runtime.starts,[]);self.assertEqual(self.publications,[])
        self.assertEqual(self.compensations,[])

    def test_revocation_verification_deadline_or_changed_identity_cannot_pass(self):
        self.runtime.mode='READ_ONLY';self.runtime.pending=1000
        for row in self.runtime.rows.values():
            if row.get('Id','').startswith('candidate'):row['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'verification_deadline_expired'):
            self.kernel.verify_mode(normal=False)
        self.assertLessEqual(self.clock.value,180)
        self.assertEqual(self.runtime.starts,[]);self.assertEqual(self.publications,[])
        self.runtime.pending=0;self.runtime.rows['candidate-0']['Image']='changed'
        with self.assertRaises(RuntimeError):self.kernel.verify_mode(normal=False)
        self.assertEqual(self.runtime.starts,[]);self.assertEqual(self.publications,[])

    def test_schema_advancement_never_selects_old115_application(self):
        self.schema=120;self.kernel.execute()
        self.assertTrue(all(cid.startswith('candidate') for cid in self.runtime.starts))

    def test_revoked_or_interrupted_previous_boot_cannot_regrant(self):
        self.runtime.mode='READ_ONLY'
        with self.assertRaisesRegex(RuntimeError,'candidate_authority_changed'):self.kernel.execute()
        self.assertEqual(self.publications,[]);self.assertEqual(self.runtime.starts,[])

    def test_stopped_declaration_must_acquire_exact_attachment_after_start(self):
        row=self.runtime.rows['candidate-0']
        endpoint=row['NetworkSettings']['Networks']['fixture-primary']
        endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        self.kernel.bindings()
        row['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'network_changed'):self.kernel.bindings()
        endpoint.update(NetworkID='network-object',IPAddress='10.0.0.2')
        self.kernel.bindings()

    def test_declared_alias_or_replaced_network_object_fails_before_start(self):
        row=self.runtime.rows['candidate-0']
        row['NetworkSettings']['Networks']['fixture-primary']['Aliases']=['unexpected']
        with self.assertRaisesRegex(RuntimeError,'alias_changed'):self.kernel.execute()
        self.assertEqual(self.runtime.starts,[])

    def test_incompatible_database_fails_before_writes_or_container_start(self):
        for value in (114,137,True,'136'):
            self.schema=value
            with self.assertRaisesRegex(RuntimeError,'native_schema_invalid'):self.kernel.execute()
            self.assertEqual(self.publications,[]);self.assertEqual(self.runtime.starts,[])

    def test_changed_image_spec_network_and_owner_are_security_failures(self):
        row=self.runtime.rows['candidate-0'];original=copy.deepcopy(row)
        for mutation in (lambda r:r.update(Image='unexpected'),lambda r:r['Config'].update(Env=['altered=true']),
                         lambda r:r['NetworkSettings']['Networks']['fixture-primary'].update(NetworkID='new-object')):
            mutation(row)
            with self.assertRaises(RuntimeError):self.kernel.execute()
            self.assertEqual(self.publications,[])
            row.clear();row.update(copy.deepcopy(original))
        write_worker_authority(self.path,generation='e'*64,owner='CANDIDATE',old={'sha':'a'*40,'slot':'blue'},candidate={'sha':'c'*40,'slot':'green'})
        with self.assertRaisesRegex(RuntimeError,'worker_owner_changed'):self.kernel.execute()

    def test_two_owner_generations_or_restartable_old_worker_reject(self):
        old=self.runtime.rows['old1'];old['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'old_workers_not_inhibited'):self.kernel.execute()
        old['State']['Running']=False;old['HostConfig']['RestartPolicy']['Name']='always'
        with self.assertRaisesRegex(RuntimeError,'old_workers_not_inhibited'):self.kernel.execute()
        self.assertEqual(self.publications,[])

    def test_persistent_unready_deadline_compensates_without_old_start_or_restore(self):
        self.runtime.pending=1000
        with self.assertRaises(RuntimeError):self.kernel.execute()
        self.assertEqual(self.compensations,['current-data-preserving']);self.assertEqual(self.runtime.mode,'READ_ONLY')
        self.assertLessEqual(self.clock.value,180)

    def test_integrity_failure_after_fencing_compensates(self):
        original=self.runtime.command
        def bad_start(args,**kw):
            if args[:2]==['docker','start']:raise RuntimeError('injected_start_failure')
            return original(args,**kw)
        self.runtime.command=bad_start
        with self.assertRaisesRegex(RuntimeError,'injected_start_failure'):self.kernel.execute()
        self.assertEqual(self.compensations,['current-data-preserving']);self.assertEqual(self.publications,['READ_ONLY'])

    def test_interrupted_migration_never_regrants_historical_normal(self):
        def denied(schema):raise RuntimeError('migration_forward_repair_required')
        self.kernel.normal_resume_guard=denied
        with self.assertRaisesRegex(RuntimeError,'forward_repair_required'):self.kernel.execute()
        self.assertEqual(self.publications,[]);self.assertEqual(self.runtime.starts,[])

    def test_readonly_forward_recovery_never_uses_positive_grant(self):
        self.runtime.mode='READ_ONLY';self.schema=119
        result=self.kernel.execute_read_only()
        self.assertEqual(result['mode'],'READ_ONLY');self.assertEqual(result['schema'],119)
        self.assertEqual(self.publications,[])
        self.assertTrue(all(cid.startswith('candidate') for cid in self.runtime.starts))

    def test_native_cold_start_shares_the_same_overall_deadline(self):
        pending=[3]
        def native():
            if pending[0]:
                pending[0]-=1;raise AvailabilityFailure('native_start_pending')
            return self.schema
        self.kernel.native_verifier=native
        self.kernel.execute();self.assertGreaterEqual(self.clock.value,13)
        self.assertEqual(self.compensations,[])

    def test_native_integrity_failure_does_not_retry_or_publish(self):
        def native():raise RuntimeError('native_identity_changed')
        self.kernel.native_verifier=native
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):self.kernel.execute()
        self.assertEqual(self.clock.value,0);self.assertEqual(self.publications,[])

    def test_migration_boundary_rechecked_immediately_before_normal(self):
        calls=[]
        def boundary(schema):
            calls.append(schema)
            if len(calls)>1:raise RuntimeError('migration_intent_changed')
        self.kernel.normal_resume_guard=boundary
        with self.assertRaisesRegex(RuntimeError,'intent_changed'):self.kernel.execute()
        self.assertEqual(self.publications,['READ_ONLY']);self.assertEqual(self.runtime.mode,'READ_ONLY')
        self.assertEqual(self.compensations,['current-data-preserving'])


if __name__=='__main__':unittest.main()
