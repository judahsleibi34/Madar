"""Opt-in real Docker lifecycle checks; never a full deployment acceptance.

Only nonce-named containers/networks created here are affected. Entrypoints are
idle shells, networks are private/internal, and no production configuration,
database, volumes or host listeners are attached. Real HTTP/DB/boot and complete
deployment rehearsal are separate mandatory gates.
"""
import copy
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import compatible_normal_boot as m
from deployment.lib import completed_normal_admission as admission
from deployment.lib.emergency_routing_repair import Runtime
from deployment.lib.completed_normal_resources import measured_spec as spec
from deployment.lib.runtime_authority import write_worker_authority
from test_completed_normal_admission import fixture_contract

@unittest.skipUnless(os.getenv('MADAR_REAL_DOCKER_TESTS')=='1','explicit isolated Docker lifecycle execution required')
class RealDockerCompatibleBootTests(unittest.TestCase):
    def command(self,*args):
        return subprocess.check_output(self.docker()+list(args),text=True,stderr=subprocess.PIPE,timeout=60).strip()
    def docker(self):
        endpoint=os.getenv('MADAR_DOCKER_FIXTURE_ENDPOINT','')
        if endpoint and not endpoint.startswith('unix:///tmp/madar-schema136-private-'):
            raise RuntimeError('isolated_fixture_endpoint_invalid')
        return ['docker','--host',endpoint] if endpoint else ['docker']
    def create_network(self,name):
        ids=self.command('network','ls','-q').splitlines()
        used=[ipaddress.ip_network(item['Subnet']) for n in json.loads(self.command('network','inspect',*ids))
            for item in (n.get('IPAM',{}).get('Config') or []) if item.get('Subnet')]
        for index in range(240,250):
            candidate=ipaddress.ip_network('10.247.'+str(index)+'.0/24')
            if not any(n.version==4 and n.overlaps(candidate) for n in used):
                identity=self.command('network','create','--internal','--subnet',str(candidate),name)
                self.networks.append(name);return identity
        raise RuntimeError('isolated_fixture_subnet_unavailable')
    def setUp(self):
        self.prefix='madar-schema136-boot-fixture-'+uuid.uuid4().hex[:12]
        self.containers=[];self.networks=[]
        self.addCleanup(self.remove_fixture)
        self.network=self.prefix+'-internal'
        self.network_id=self.create_network(self.network)
        backend=self.command('image','inspect','madar-backend:81cebfeb024341cd8d784402ba1f92ed2e63fb3d','--format','{{.Id}}')
        frontend=self.command('image','inspect','madar-frontend:81cebfeb024341cd8d784402ba1f92ed2e63fb3d-production','--format','{{.Id}}')
        self.contract=fixture_contract();self.contract['candidate']['images']={'backend':backend,'frontend':frontend}
        self.contract['candidate']['redis_image']=backend
        self.temp=tempfile.TemporaryDirectory(dir=str(WEB.parent/'.incident-response'));self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name);self.root=self.state/admission.digest(self.contract);self.root.mkdir()
        publication={'operation':admission.OPERATION,'context_sha256':admission.digest(self.contract),
            'source_sha':self.contract['candidate']['source_sha'],'images':self.contract['candidate']['images'],
            'runtimes':{},'networks':{self.network:self.network_id},'worker_generation':'f'*64,'origin_workers':[]}
        for kind in (*m.ROLES,'old1','old2','old3'):
            image=frontend if kind=='frontend' else backend
            cid=self.command('create','--name',self.prefix+'-'+kind,'--network',self.network,
                '--network-alias',kind,'--restart=no','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
                '--pids-limit=16','--memory=64m','--cpus=0.1','--entrypoint=/bin/sh',image,'-c','sleep 600')
            self.containers.append(cid)
            if kind.startswith('old'):publication['origin_workers'].append(cid)
            else:
                row=json.loads(self.command('inspect',cid))[0]
                publication['runtimes'][kind]={'id':cid,'image':image,'spec_sha256':spec(row),
                    'networks':{self.network:self.network_id},'network_aliases':{self.network:row['NetworkSettings']['Networks'][self.network].get('Aliases') or []}}
        self.publication=publication
        (self.root/'normal-publication.json').write_text(json.dumps(publication))
        (self.root/'admission.json').write_text(json.dumps({'operation':admission.OPERATION,'contract':self.contract}))
        write_worker_authority(self.state,generation='f'*64,owner='CANDIDATE',
            old={'sha':'a'*40,'slot':'blue'},candidate={'sha':'c'*40,'slot':'green'})
        def no_effect(*a,**kw):raise AssertionError('binding verification attempted authority or compensation effect')
        self.kernel=m.CompatibleNormalBoot(self.contract,source_guard=lambda:None,native_verifier=lambda:115,
            normal_resume_guard=lambda schema:None,publish_authority=no_effect,compensate_current_data=no_effect,admissions=self.state,state_root=self.state)
        test=self
        class FixtureRuntime(Runtime):
            def command(self,args,*,input=None):
                if args[0]!='docker':raise AssertionError('unexpected non-Docker fixture command')
                return test.command(*args[1:])
        self.kernel.runtime=FixtureRuntime()
        # Fixture-only path ownership adapter. Docker runtime, image/spec/network
        # inspection, state transition and production verifier are real.
        p=patch.object(m,'protected',lambda path,**kw:path);p.start();self.addCleanup(p.stop)
        p=patch.object(m.os,'geteuid',return_value=0);p.start();self.addCleanup(p.stop)
    def remove_fixture(self):
        for cid in self.containers:
            subprocess.run(self.docker()+['rm','-f',cid],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30,check=True)
        for name in self.networks:
            subprocess.run(self.docker()+['network','rm',name],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30,check=True)
    def test_created_then_running_then_stopped_bindings(self):
        self.kernel.bindings()
        candidates=[r['id'] for r in self.publication['runtimes'].values()]
        self.command('start',*candidates)
        # Seal RUNNING specs at the real governed publication phase. Created
        # records are declarations, not NORMAL runtime publication evidence.
        for kind,identity in self.publication['runtimes'].items():
            row=json.loads(self.command('inspect',identity['id']))[0]
            self.assertTrue(row['State']['Running'])
            self.assertEqual(row['NetworkSettings']['Networks'][self.network]['NetworkID'],self.network_id)
            identity['spec_sha256']=spec(row)
        (self.root/'normal-publication.json').write_text(json.dumps(self.publication))
        self.kernel.bindings()
        self.command('stop','--time','1',*candidates)
        self.kernel.bindings()
    def test_actual_extra_network_attachment_rejected(self):
        extra=self.prefix+'-unexpected';self.create_network(extra)
        cid=self.publication['runtimes']['backend']['id'];self.command('network','connect',extra,cid)
        # The complete specification hash may reject the extra attachment
        # before the narrower network inventory check.
        with self.assertRaisesRegex(RuntimeError,'runtime_identity_changed|network_changed'):self.kernel.bindings()
    def test_actual_old_worker_start_and_restart_policy_rejected(self):
        cid=self.publication['origin_workers'][0];self.command('start',cid)
        with self.assertRaisesRegex(RuntimeError,'old_workers_not_inhibited'):self.kernel.bindings()
        self.command('stop','--time','1',cid);self.command('update','--restart=always',cid)
        with self.assertRaisesRegex(RuntimeError,'old_workers_not_inhibited'):self.kernel.bindings()
    def test_actual_security_specification_change_rejected(self):
        cid=self.publication['runtimes']['backend']['id'];self.command('update','--pids-limit=17',cid)
        with self.assertRaisesRegex(RuntimeError,'runtime_identity_changed'):self.kernel.bindings()

if __name__=='__main__':unittest.main()
