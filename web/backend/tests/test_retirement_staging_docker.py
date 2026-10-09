"""Real isolated retirement/replacement lifecycle; never production acceptance.

Only test-owned containers/networks/ports/lock files are used. Authority and native
configuration seams are synthetic: no protected production receipt or customer
DB is read, modified or presented as authorization proof. Fixture teardown removes
only exact resources created here, never retained production resources.
"""
import ast,copy,fcntl,hashlib,ipaddress,json,os,socket,subprocess,sys,tempfile,time,unittest,urllib.request,uuid
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import DetachedRecoveryCandidate,require_unreserved_ports,verify_lifecycle_networks,KINDS
from deployment.lib.emergency_routing_repair import spec
from deployment.lib.provider_local_transition import LocalTransitionContract
from deployment.lib.provider_recovery_runtime import digest

@unittest.skipUnless(os.getenv('MADAR_REAL_DOCKER_STAGING_TEST')=='1','requires isolated Docker host fixtures')
class RetirementStagingDockerTests(unittest.TestCase):
    backend='sha256:01135c50821122f78ebbbfa46495bd633db5cbad791e4ae17cda49a6dc927f91'
    frontend='sha256:048c88eff6d72bb4eb109f3f44b9bd0d791fd87039e1263dae040f3ab7d56559'
    def shell(self,args,env=None):return subprocess.check_output(args,text=True,timeout=40,env=env).strip()
    def row(self,cid):return json.loads(self.shell(['docker','inspect',cid]))[0]
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.prefix='madar-staging-fixture-'+uuid.uuid4().hex[:12];self.containers=[];self.networks=[];self.volumes=[]
        self.addCleanup(self.cleanup);self.shell(['docker','image','inspect',self.backend,self.frontend])
        ids=self.shell(['docker','network','ls','-q']).splitlines()
        rows=json.loads(self.shell(['docker','network','inspect',*ids]))
        occupied=[ipaddress.ip_network(v['Subnet']) for r in rows for v in r.get('IPAM',{}).get('Config') or [] if v.get('Subnet')]
        occupied += [ipaddress.ip_network(r['dst'],strict=False) for r in json.loads(self.shell(['ip','-j','route'])) if r.get('dst') not in (None,'default')]
        self.subnets=iter(n for n in ipaddress.ip_network('10.248.0.0/16').subnets(new_prefix=24) if not any(n.overlaps(v) for v in occupied if v.version==4))
        self.client=self.make_network('client');self.redis_network=self.make_network('redis',internal=True);self.old_network=self.make_network('old')
        self.ports=[]
        for _ in range(3):
            with socket.socket() as listener:listener.bind(('127.0.0.1',0));self.ports.append(listener.getsockname()[1])
        self.source='2a9926c753908e6c0bcb3ca6fa937627b0e06291';self.images={'backend':self.backend,'frontend':self.frontend}
        self.contract=LocalTransitionContract(self.source,self.images,'a'*64,'b'*64,'c'*64,'d'*64,{k:'e'*64 for k in ('environment','state','upstream','worker_authority','controller','recovery','traffic')})
        self.server="import socket; s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('0.0.0.0',8000));s.listen();\nwhile True:\n c,a=s.accept();c.recv(4096);c.sendall(b'HTTP/1.0 200 OK\\r\\nContent-Length: 2\\r\\nConnection: close\\r\\n\\r\\nOK');c.shutdown(socket.SHUT_WR);c.close()"
        self.fallback=self.http_container('fallback',self.client,self.ports[2]);self.wait_http(self.ports[2])
        self.old={kind:self.http_container('old-'+kind,self.old_network,self.ports[i]) if kind in ('frontend','backend') else self.sleep_container('old-'+kind,self.old_network,start=kind=='parser') for i,kind in enumerate(('frontend','backend','parser',*KINDS))}
        for port in self.ports[:2]:self.wait_http(port)
        self.old_specs={k:spec(self.row(cid)) for k,cid in self.old.items()}
        self.retired={self.row(self.old[k])['Name'].lstrip('/'):{'container_id':self.old[k],'image_id':self.backend,'spec_sha256':self.old_specs[k]} for k in ('frontend','backend')}
        volume=self.prefix+'-redis-data';self.shell(['docker','volume','create','--label','com.madar.disposable-test=staging',volume]);self.volumes.append(volume)
        self.redis=self.start_container(['run','-d','--name',self.prefix+'-redis','--network',self.redis_network,'--restart','no','--label','com.madar.recovery.profile=provider402-signin','--mount','type=volume,src='+volume+',dst=/data',self.backend,'sleep','300'])
        c=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate);self.c=c;c.root=Path(self.tmp.name)/'new';c.root.mkdir(mode=0o700)
        c.plan=SimpleNamespace(digest='f'*64,source_sha=self.source,candidate_images=self.images,candidate_destination={'subnet':str(next(self.subnets)),'retired_port_declarations':self.retired})
        c.prefix=self.prefix+'-replacement';c.network_name=c.prefix+'-runtime';c.slot='green';c.backend_port,c.frontend_port=self.ports[:2][::-1]
        c.redis_name=self.prefix+'-redis';c.redis_network=self.redis_network;c.contract=self.contract
        c.command=self.command;c.inspect=self.inspect;c.require_authorization=self.authorize;c.verify_image_source=lambda:None;c.verify_retained_inputs=lambda:None
        c.require_feasible=self.feasible;c._create_application=self.create_application
        self.phase='pending';self.guard_bytes=b'fixture-authority';(c.root/'fixture-authority').write_bytes(self.guard_bytes)
        def fixture_file(path,**kw):
            path=Path(path);path.resolve().relative_to(Path(self.tmp.name).resolve())
            if path.is_symlink() or not path.is_file():raise RuntimeError('fixture_file_untrusted')
            return path
        for module in ('deployment.lib.active_recovery_candidate','deployment.lib.provider_local_transition_runtime'):
            patched=patch(module+'.protected',side_effect=fixture_file);patched.start();self.addCleanup(patched.stop)
        self.patcher=patch('deployment.lib.active_recovery_candidate.inspect_previous_candidate',side_effect=self.previous);self.patcher.start();self.addCleanup(self.patcher.stop)
    def start_container(self,args):
        cid=self.shell(['docker',*args]);self.containers.append(cid);return cid
    def make_network(self,role,internal=False):
        name=self.prefix+'-'+role;self.shell(['docker','network','create',*(['--internal'] if internal else []),'--subnet',str(next(self.subnets)),name]);self.networks.append(name);return name
    def http_container(self,role,network,port):return self.start_container(['run','-d','--name',self.prefix+'-'+role,'--network',network,'--restart','no','--publish',f'127.0.0.1:{port}:8000',self.backend,'python','-u','-c',self.server])
    def sleep_container(self,role,network,start=False):
        cid=self.start_container(['create','--name',self.prefix+'-'+role,'--network',network,'--restart','no',self.backend,'sleep','300'])
        if start:self.shell(['docker','start',cid])
        return cid
    def cleanup(self):
        for cid in reversed(self.containers):self.shell(['docker','rm','-f',cid])
        for name in reversed(self.networks):self.shell(['docker','network','rm',name])
        for name in self.volumes:self.shell(['docker','volume','rm',name])
    def wait_http(self,port):
        for _ in range(100):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}',timeout=1) as response:self.assertEqual(response.status,200);response.read()
                return
            except OSError:time.sleep(.05)
        self.fail('fixture HTTP activation deadline')
    def authorize(self,contract):
        if self.phase!='pending' or (self.c.root/'fixture-authority').read_bytes()!=self.guard_bytes:raise RuntimeError('fixture_authorization_denied')
    def previous(self,plan):
        for kind,cid in self.old.items():
            r=self.row(cid)
            if spec(r)!=self.old_specs[kind] or r['HostConfig']['RestartPolicy']['Name']!='no' or (kind in KINDS and r['State']['Status']!='created'):raise RuntimeError('fixture_previous_identity_changed')
            verify_lifecycle_networks(r,{self.old_network:self.shell(['docker','network','inspect','--format','{{.Id}}',self.old_network])},self.old_network,created_worker=kind in KINDS)
        return {'binding':{'plan_sha256':'a'*64,'evidence_sha256':'b'*64},'rows':{k:self.row(cid) for k,cid in self.old.items()}}
    def inspect(self,name):
        row=self.row(name)
        if self.client in row['NetworkSettings']['Networks']:row['NetworkSettings']['Networks']['madar-supabase-client']=row['NetworkSettings']['Networks'].pop(self.client)
        return row
    def command(self,args,**kwargs):
        # Map logical native dependency only into this fixture's isolated client
        # bridge. Never connect to production networks or use production paths.
        args=list(args)
        if args[1:3]==['network','inspect']:args=[self.client if a=='madar-supabase-client' else a for a in args]
        if args[1:3]==['ps','-aq']:return '\n'.join(self.containers)
        if args[1:3]==['ps','-a']:return '\n'.join(self.row(cid)['Name'].lstrip('/') for cid in self.containers)
        value=self.shell(args,env=kwargs.get('env'))
        if args[1] in ('run','create'):self.containers.append(value)
        if args[1:3]==['network','create']:self.networks.append(args[-1])
        return value
    def feasible(self):
        known=self.shell(['docker','ps','-a','--format','{{.Names}}']).splitlines()
        if any(self.c.name(k) in known for k in ('backend','frontend','parser',*KINDS)):raise RuntimeError('fixture_name_collision')
        previous=self.previous(self.c.plan)
        require_unreserved_ports(self.c,(self.c.backend_port,self.c.frontend_port),self.retired,{r['Id']:r for k,r in previous['rows'].items() if k in ('backend','frontend')})
    def create_application(self,contract,name,role,network,worker=None,loopback_port=None):
        args=['docker','create','--name',name,'--network',network,'--network-alias',role,'--restart','no','--env','MADAR_RELEASE_SHA='+contract.sha,'--env','MADAR_BUSINESS_WRITE_CONTRACT='+digest(asdict(contract)),'--mount','type=bind,src='+str(self.c.root/'write-authority')+',dst=/run/madar/business-write-authority,readonly']
        if loopback_port:args+=['--publish',f'127.0.0.1:{loopback_port}:8000']
        args+=[self.backend,*(['sleep','300'] if worker else ['python','-u','-c',self.server])]
        cid=self.command(args)
        for name in (self.client,self.redis_network):self.command(['docker','network','connect',name,cid])
    def locked_stage(self):
        with (Path(self.tmp.name)/'upgrade.lock').open('w') as upgrade,(Path(self.tmp.name)/'deploy.lock').open('w') as deploy:
            for f in (upgrade,deploy):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:self.c.stage()
            except Exception:
                print('FIXTURE_STAGING_STATE='+json.dumps([{'name':r['Name'],'image':r['Image'],'state':r['State']['Status'],'running':r['State']['Running'],'ports':r['HostConfig'].get('PortBindings'),'restart':r['HostConfig']['RestartPolicy']['Name']} for r in (self.row(cid) for cid in self.containers)],sort_keys=True),flush=True)
                raise
    def test_complete_retirement_and_real_replacement_created_workers(self):
        self.locked_stage();self.c.verify_recorded_runtime();self.wait_http(self.c.frontend_port);self.wait_http(self.c.backend_port)
        for kind in KINDS:self.assertEqual(self.row(self.c.name(kind))['State']['Status'],'created');self.assertEqual(self.row(self.old[kind])['State']['Status'],'created')
        for kind in ('frontend','backend','parser'):self.assertFalse(self.row(self.old[kind])['State']['Running'])
        self.wait_http(self.ports[2]);self.assertTrue((self.c.root/'previous-candidate-retirement.json').exists())
    def test_frozen_probe_fails_time_wait_but_corrected_probe_and_replacement_pass(self):
        raw=self.shell(['git','show','2a9926c753908e6c0bcb3ca6fa937627b0e06291:web/deployment/lib/active_recovery_candidate.py'])
        fn=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='require_unreserved_ports')
        namespace={'socket':socket,'json':json,'spec':spec};exec(compile(ast.Module(body=[fn],type_ignores=[]),'frozen-port-probe','exec'),namespace)
        self.c.retire_previous_candidate()
        with self.assertRaisesRegex(RuntimeError,'errno_98'):namespace['require_unreserved_ports'](self.c,(self.c.frontend_port,),self.retired)
        require_unreserved_ports(self.c,(self.c.backend_port,self.c.frontend_port),self.retired)
        self.assertFalse(self.shell(['ss','-ltn',f'( sport = :{self.c.frontend_port} )']).splitlines()[1:])
        self.assertTrue(self.shell(['ss','-tan','state','time-wait',f'( sport = :{self.c.frontend_port} )']).splitlines()[1:])
        with socket.socket() as live:
            live.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);live.bind(('127.0.0.1',self.c.frontend_port));live.listen(1)
            with self.assertRaisesRegex(RuntimeError,'errno_98'):require_unreserved_ports(self.c,(self.c.frontend_port,),self.retired)
        self.wait_http(self.ports[2])
    def test_interruption_after_retirement_cannot_replay_and_preserves_fallback(self):
        original=self.c.command
        def injected(args,**kw):
            if args[1:3]==['network','create']:raise RuntimeError('fixture_interrupted')
            return original(args,**kw)
        self.c.command=injected
        with self.assertRaisesRegex(RuntimeError,'fixture_interrupted'):self.locked_stage()
        self.phase='failed'
        with self.assertRaisesRegex(RuntimeError,'authorization_denied'):self.locked_stage()
        self.wait_http(self.ports[2]);self.assertEqual((self.c.root/'fixture-authority').read_bytes(),self.guard_bytes)
        self.assertTrue(all(self.row(cid)['State']['Status']=='created' for k,cid in self.old.items() if k in KINDS))

    def test_changed_identity_or_name_collision_prevents_retirement(self):
        self.shell(['docker','update','--restart','always',self.old['backend']])
        with self.assertRaisesRegex(RuntimeError,'identity_changed'):self.locked_stage()
        self.assertTrue(self.row(self.old['backend'])['State']['Running']);self.wait_http(self.ports[2])
        self.shell(['docker','update','--restart','no',self.old['backend']])
        collision=self.start_container(['create','--name',self.c.name('backend'),'--network',self.client,'--restart','no',self.backend,'sleep','300'])
        with self.assertRaisesRegex(RuntimeError,'name_collision'):self.locked_stage()
        self.assertTrue(self.row(self.old['frontend'])['State']['Running']);self.wait_http(self.ports[2])
