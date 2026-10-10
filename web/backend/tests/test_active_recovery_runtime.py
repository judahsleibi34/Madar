"""Synthetic identity regressions; never authorization or runtime evidence."""
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
from deployment.lib.active_recovery_runtime import ActiveRecoveryRuntime,ROLES,KINDS
from deployment.lib.emergency_routing_repair import spec

class ActiveRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.plan=SimpleNamespace(digest='a'*64,source_sha='b'*40,candidate_images={'backend':'sha256:'+'c'*64,'frontend':'sha256:'+'d'*64})
        self.networks={'normal':'e'*64,'madar-supabase-client':'f'*64,'redis':'1'*64}
        self.rows={}
        for i,kind in enumerate(sorted(ROLES)):
            attached={'normal','madar-supabase-client','redis'} if kind in {'backend',*KINDS} else {'normal'}
            row={'Id':str(i).zfill(64),'Image':self.plan.candidate_images['frontend' if kind=='frontend' else 'backend'],
                 'Name':'/renamed-'+kind,'Config':{},'Mounts':[], 'HostConfig':{'RestartPolicy':{'Name':'no'},'NetworkMode':'normal'},
                 'State':{'Running':True},'NetworkSettings':{'Networks':{name:{'NetworkID':self.networks[name],
                 'IPAddress':'10.0.0.5','Aliases':(['backend' if kind=='backend' else kind+'-worker'] if name=='normal' else [])} for name in attached}}}
            self.rows[kind]=row
        self.record={'version':1,'plan_sha256':self.plan.digest,'source_sha':self.plan.source_sha,'mode':'READ_ONLY',
            'loopback_ports':{'backend':8201,'frontend':3200},'networks':self.networks,
            'runtimes':{kind:{'id':row['Id'],'image':row['Image'],'spec_sha256':spec(row)} for kind,row in self.rows.items()}}
        self.save()
        self.owner={'active':{kind:row['Id'] for kind,row in self.rows.items() if kind!='parser'}}
        def command(args):return json.dumps([{'Id':self.networks[args[-1]],'Driver':'bridge'}])
        def inspect(identity):return copy.deepcopy(next(row for row in self.rows.values() if row['Id']==identity))
        self.c=SimpleNamespace(backend_port=8201,frontend_port=3200,network_name='normal',redis_network='redis',command=command,inspect=inspect)
        self.w=SimpleNamespace(verify_owner=lambda:self.owner)
        self.verifier=ActiveRecoveryRuntime(self.plan,self.c,self.root,lambda:None,self.w,runtime=object())
        p=patch('deployment.lib.active_recovery_runtime.protected',lambda path,**kw:path);p.start();self.addCleanup(p.stop)
    def save(self):
        (self.root/'candidate-identities.json').write_text(json.dumps(self.record))
    def test_canonical_rename_and_ip_reassignment_preserve_identity(self):
        for kind,row in self.rows.items():
            row['Name']='/madar-green-'+kind
            for network in row['NetworkSettings']['Networks'].values():network['IPAddress']='10.0.0.99'
        self.assertEqual(set(self.verifier.identities(workers_started=True)),ROLES)
    def test_modified_image_or_spec_fails(self):
        self.rows['backend']['Image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):self.verifier.identities(workers_started=True)
    def test_changed_network_id_or_role_fails(self):
        self.rows['backend']['NetworkSettings']['Networks']['normal']['NetworkID']='0'*64
        with self.assertRaisesRegex(RuntimeError,'attachment_changed'):self.verifier.identities(workers_started=True)
    def test_missing_role_alias_fails(self):
        self.rows['backend']['NetworkSettings']['Networks']['normal']['Aliases']=[]
        with self.assertRaisesRegex(RuntimeError,'role_changed'):self.verifier.identities(workers_started=True)
    def test_changed_worker_owner_fails(self):
        self.owner['active']['notification']='0'*64
        with self.assertRaisesRegex(RuntimeError,'owner_changed'):self.verifier.identities(workers_started=True)
    def test_workers_must_remain_stopped_before_handoff(self):
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):self.verifier.identities(workers_started=False)
        for kind in KINDS:
            self.rows[kind]['State']={'Running':False,'Status':'created'}
            for network in self.rows[kind]['NetworkSettings']['Networks'].values():network['NetworkID']='';network['IPAddress']=''
        self.verifier.identities(workers_started=False)
    def test_missing_parser_or_changed_receipt_fails(self):
        self.record['runtimes'].pop('parser');self.save()
        with self.assertRaisesRegex(RuntimeError,'receipt_changed'):self.verifier.identities(workers_started=True)
    def test_source_failure_precedes_any_runtime_observation(self):
        def denied():raise RuntimeError('source_changed')
        self.verifier.source_guard=denied
        with self.assertRaisesRegex(RuntimeError,'source_changed'):self.verifier.identities(workers_started=True)


    def test_boot_inspection_can_bind_stopped_ids_without_starting_them(self):
        for row in self.rows.values():row['State']['Running']=False
        self.verifier.identities(workers_started=True,require_running=False)
        self.assertTrue(all(not row['State']['Running'] for row in self.rows.values()))

    def test_boot_accepts_only_default_dns_serialization_on_same_stopped_ids(self):
        for kind,row in self.rows.items():
            row['HostConfig']['Dns']=None
            self.record['runtimes'][kind]['spec_sha256']=spec(row)
            row['HostConfig']['Dns']=[]
            row['State']['Running']=False
        self.save()
        self.verifier.identities(workers_started=True,require_running=False)
        self.assertTrue(all(not row['State']['Running'] for row in self.rows.values()))
        self.rows['backend']['HostConfig']['Dns']=['1.1.1.1']
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):
            self.verifier.identities(workers_started=True,require_running=False)
