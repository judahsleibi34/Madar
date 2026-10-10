"""Retained schema115 release must remain independently fenced and measured."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from deployment.lib.active_recovery_retained_fallback import verify_release
from deployment.lib.emergency_routing_repair import spec

class RetainedReleaseTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);(self.root/'write-authority').mkdir()
        self.old=SimpleNamespace(source_sha='a'*40,candidate_images={'backend':'sha256:'+'b'*64,'frontend':'sha256:'+'c'*64})
        self.authority={'mode':'READ_ONLY','schema':115,'release_sha':self.old.source_sha};self.save()
        self.rows={};self.owned={};self.resources={}
        for i,kind in enumerate(('backend','frontend','notification','calendar-sync','data-deletion')):
            role=kind if kind in ('backend','frontend') else kind+'-worker';name='madar-green-'+role
            cid=('%064x'%(i+1));image=self.old.candidate_images['frontend' if kind=='frontend' else 'backend']
            ports={('8080' if kind=='frontend' else '8000')+'/tcp':[{'HostIp':'127.0.0.1','HostPort':str(3200 if kind=='frontend' else 8201)}]} if kind in ('backend','frontend') else {}
            row={'Id':cid,'Image':image,'Config':{'Labels':{'org.opencontainers.image.revision':self.old.source_sha}},
                'HostConfig':{'RestartPolicy':{'Name':'no'},'PortBindings':ports},'Mounts':[],
                'State':{'Running':kind in ('backend','frontend')},'NetworkSettings':{'Networks':{'runtime':{'NetworkID':'d'*64}}}}
            self.rows[name]=row;self.owned[kind]=cid
            self.resources[name]={'container_id':cid,'image_id':image,'spec_sha256':spec(row),'networks':{'runtime':'d'*64}}
        self.records={'worker-owner.json':{'authority':{'candidate':{'slot':'green'}},'active':self.owned}}
        self.components={key:'ok' for key in ('environment','database','redis','auth','storage','schema','admin_mfa_policy','parser_isolation','backup_freshness')}
        self.components.update({key:'unavailable' for key in ('notification_worker','calendar_sync_worker','data_deletion_worker')})
        self.denials=[]
        self.runtime=SimpleNamespace(inspect=self.inspect,network=lambda name:{'Id':'d'*64,'Driver':'bridge'},schema=lambda:115,
            fetch=lambda url:(503,json.dumps({'ready':False,'components':self.components})),json_http=self.http,
            denied=lambda base:self.denials.append(base),http_status=lambda url:200)
        change=patch('deployment.lib.active_recovery_retained_fallback.protected',lambda path,**kw:Path(path));change.start();self.addCleanup(change.stop)
    def save(self):
        (self.root/'write-authority/authority.json').write_text(json.dumps(self.authority))
    def inspect(self,names):
        return {name:self.rows[name] if name in self.rows else next(row for row in self.rows.values() if row['Id']==name) for name in names}
    def http(self,url):
        if url.endswith('/health/recovery'):return {'restricted':True,'business_writes_enabled':False}
        return {'release_sha':self.old.source_sha,'release_slot':'green','schema_compatible_min':115,'schema_compatible_max':115}
    def verify(self):return verify_release(self.old,self.root,self.records,self.resources,self.runtime)
    def test_stopped_workers_do_not_prevent_restricted_compensation(self):
        self.assertEqual(self.verify(),{'backend':('127.0.0.1',8201),'frontend':('127.0.0.1',3200)})
        self.assertEqual(len(self.denials),2)
    def test_no_normal_or_foreign_authority_can_forward(self):
        for key,value in (('mode','NORMAL'),('schema',135),('release_sha','0'*40)):
            old=self.authority[key];self.authority[key]=value;self.save()
            with self.assertRaisesRegex(RuntimeError,'authority_changed'):self.verify()
            self.authority[key]=old;self.save()
    def test_stale_backup_and_other_readiness_failures_are_rejected(self):
        for key in ('backup_freshness','database','auth','storage','schema','parser_isolation'):
            old=self.components[key];self.components[key]='stale'
            with self.assertRaisesRegex(RuntimeError,'core_unready'):self.verify()
            self.components[key]=old
        self.components['unexpected']='unavailable'
        with self.assertRaisesRegex(RuntimeError,'core_unready'):self.verify()
    def test_changed_container_image_spec_network_or_port_is_rejected(self):
        original=copy.deepcopy(self.rows)
        for row_key,path,value in (
            ('madar-green-backend',('Id',),'0'*64),('madar-green-frontend',('Image',),'sha256:'+'0'*64),
            ('madar-green-backend',('Config','Labels','org.opencontainers.image.revision'),'0'*40),
            ('madar-green-backend',('NetworkSettings','Networks','runtime','NetworkID'),'0'*64),
            ('madar-green-backend',('HostConfig','PortBindings'),{}),
            ('madar-green-notification-worker',('Image',),'sha256:'+'0'*64)):
            current=self.rows[row_key]
            for key in path[:-1]:current=current[key]
            current[path[-1]]=value
            with self.assertRaises(RuntimeError):self.verify()
            self.rows=copy.deepcopy(original)
    def test_unauthorized_worker_start_rejected(self):
        self.rows['madar-green-notification-worker']['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'consumer_running'):self.verify()
    def test_runtime_change_during_verification_rejected(self):
        count=[0];original=self.inspect
        def inspect(names):
            count[0]+=1
            if count[0]==3:self.rows['madar-green-backend']['State']['Running']=False
            return original(names)
        self.runtime.inspect=inspect
        with self.assertRaisesRegex(RuntimeError,'during_verification'):self.verify()

class RetainedListenerInstallationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_active_recovery_listener import ListenerInstallationTests
        self.fixture=ListenerInstallationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        self.old_service='madar-normal-local-fallback-'+('c'*12)+'.service'
        self.old=f.units/self.old_service;self.old.write_bytes(b'previous immutable unit')
        f.plan.candidate_destination={'post_compensation':{'baseline':{'previous_plan_sha256':'c'*64},'retained_fallback':{'operation':'reuse-verified-compensated-local-release'}}}
        from deployment.lib.provider_recovery_runtime import file_digest
        self.records={'fallback-listener-installation.json':{'service':self.old_service,'unit_sha256':file_digest(self.old)}}
        for target,value in (
            ('deployment.lib.active_recovery_compensated.verify_compensated_binding',lambda *a,**kw:None),
            ('deployment.lib.active_recovery_compensated.inspect_history',lambda *a:(object(),Path('/private-fixture'),self.records,{})),
            ('deployment.lib.active_recovery_retained_fallback.verify_backup',lambda *a:None),
            ('deployment.lib.active_recovery_retained_fallback.verify_runtime',lambda *a:None)):
            p=patch(target,value);p.start();self.addCleanup(p.stop)
    def test_attested_listener_is_superseded_on_same_ports_without_touching_old_bytes(self):
        f=self.fixture;old=self.old.read_bytes();name=f.install.install()
        self.assertEqual(self.old.read_bytes(),old)
        self.assertEqual((f.root/'fallback-unit-preimage.service').read_bytes(),old)
        intent=json.loads((f.root/'fallback-supersession-intent.json').read_text())
        self.assertEqual(intent['previous_service'],self.old_service)
        self.assertEqual(intent['replacement_service'],name)
        labels=[label for label,args in f.calls]
        self.assertLess(labels.index('continuation_listener_validate'),labels.index('continuation_listener_disable_consumed'))
        self.assertLess(labels.index('continuation_listener_disable_consumed'),labels.index('continuation_listener_enable'))
        f.socket.assert_not_called()
    def test_failed_new_listener_restores_exact_old_service_and_retains_failure_evidence(self):
        f=self.fixture
        def command(label,args):
            f.calls.append((label,args))
            if label=='continuation_listener_enable':raise RuntimeError('injected_activation_failure')
        f.install.ops.command=command
        with self.assertRaisesRegex(RuntimeError,'activation_failure'):f.install.install()
        labels=[label for label,args in f.calls]
        self.assertEqual(labels[-2:],['continuation_listener_stop_failed','continuation_listener_restore_previous'])
        self.assertEqual(self.old.read_bytes(),b'previous immutable unit')
        self.assertTrue((f.root/'fallback-supersession-intent.json').exists())
    def test_altered_preimage_cannot_stop_old_listener(self):
        self.old.write_bytes(b'altered old unit')
        with self.assertRaisesRegex(RuntimeError,'preimage_changed'):self.fixture.install.install()
        self.assertEqual(self.fixture.calls,[])
