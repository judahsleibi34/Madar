"""Private compute sidecar is not a database/queue consumer.

Synthetic Docker observations exercise the actual inventory/model/adapter code.
These tests do not grant authority or establish protected application acceptance.
"""
import copy
import json
import os
from pathlib import Path
import hashlib
import ipaddress
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from deployment.lib import schema150_actor_inventory as inventory
from deployment.lib import completed_normal_runtime as runtime
from deployment.lib.completed_normal_resources import measured_spec, measured_spec_matches
from deployment.lib.completed_normal_profile import RECONCILED
from test_schema150_actor_inventory import fixture, repin, phase_rows


def parser_row(scope, *, name='madar-schema160-private-parser', identifier='f'*64,
               uploads='/synthetic-owned/private_uploads'):
    network='madar-schema160-'+scope['context_sha256'][:16]+'-green-parser'
    env={'APP_ENV':'production', 'MADAR_RELEASE_SHA':scope['source_sha'],
         'MADAR_BUILD_TIMESTAMP':'2026-10-25T00:00:00Z', 'PATH':'/usr/local/bin:/usr/bin:/bin',
         'DATA_UPLOAD_DIR':'/app/private_uploads', 'MADAR_UPLOAD_WORKSPACE_DIR':'/tmp/madar_parser',
         'PARSER_WORKER_PROCESS':'true', 'PARSER_WORKER_HEALTH_HOST':'0.0.0.0',
         'PARSER_WORKER_PORT':'8092', 'PARSER_JOB_TIMEOUT_SECONDS':'55',
         'ALLOW_REMOTE_DATASET_URLS':'false', 'STRUCTURED_LOGS':'true'}
    return {'Id':identifier, 'Name':'/'+name, 'Image':'sha256:'+'e'*64,
        'Config':{'Env':[k+'='+v for k,v in env.items()], 'User':'65534:65534',
            'Cmd':['python','-m','workers.parser_worker'], 'Entrypoint':None, 'WorkingDir':'/app',
            'Labels':{'org.opencontainers.image.revision':scope['source_sha']}},
        'HostConfig':{'RestartPolicy':{'Name':'no','MaximumRetryCount':0}, 'Privileged':False,
            'ReadonlyRootfs':True, 'CapDrop':['ALL'], 'SecurityOpt':['no-new-privileges:true'],
            'Init':True, 'Memory':768*1024*1024, 'NanoCpus':750_000_000, 'PidsLimit':64,
            'NetworkMode':network, 'Tmpfs':{'/tmp':'rw,noexec,nosuid,size=256m,uid=65534,gid=65534'}},
        'Mounts':[{'Type':'bind','Source':uploads,'Destination':'/app/private_uploads','RW':False}],
        'State':{'Running':False,'Restarting':False,'Status':'created','Health':{'Status':'healthy'}},
        'NetworkSettings':{'Networks':{network:{'NetworkID':'9'*64,'IPAddress':'','EndpointID':'','Aliases':[]}}}}


def canonical_parser(data, scope, rows):
    """Give the canonical fixture the real bounded parser specification."""
    scope=dict(scope,operation=RECONCILED.operation,target_schema=160)
    record=data['containers'].get('candidate:parser-worker')
    if record:
        actual=parser_row(scope,name=record['name'],identifier=record['id'],
            uploads=data['object_roots']['private_uploads']['source'])
        rows[:]=[actual if r['Id']==record['id'] else r for r in rows]
        record.update(spec_sha256=measured_spec(actual),mounts=inventory._actual_mounts(actual),
            networks={k:v['NetworkID'] for k,v in actual['NetworkSettings']['Networks'].items()})
        record['states']['private']['running']=True
    return repin(data,scope)


def unused_parser_subnet(networks, routes):
    """Bounded test-only pool; never retire an existing network to make room."""
    occupied=[]
    for network in networks:
        for config in network.get('IPAM',{}).get('Config') or []:
            if config.get('Subnet'):occupied.append(ipaddress.ip_network(config['Subnet']))
    for route in routes:
        if route.get('dst') not in (None,'default'):
            occupied.append(ipaddress.ip_network(route['dst'],strict=False))
    for candidate in ipaddress.ip_network('10.254.240.0/20').subnets(new_prefix=28):
        if not any(candidate.version==other.version and candidate.overlaps(other) for other in occupied):
            return str(candidate)
    raise RuntimeError('owned_parser_subnet_unavailable')


class PrivateParserInventoryTests(unittest.TestCase):
    def setUp(self):
        (self.data,self.scope),self.rows=fixture(candidates=True)
        self.data,self.scope=canonical_parser(self.data,self.scope,self.rows)

    def test_canonical_private_parser_runs_while_every_consuming_worker_stays_stopped(self):
        inventory.validate_inventory(self.data,self.scope)
        rows=phase_rows(self.data,self.rows,'private')
        inventory.attest_containers(self.data,rows,phase='private',binding=self.scope)
        consumers=inventory.consuming_worker_roles(self.scope)
        self.assertEqual(consumers,inventory.WORKER_ROLES-{'parser-worker'})
        for role in consumers:
            bad=copy.deepcopy(rows)
            next(r for r in bad if r['Id']==self.data['containers']['candidate:'+role]['id'])['State']['Running']=True
            with self.subTest(role=role),self.assertRaisesRegex(RuntimeError,'state_changed'):
                inventory.attest_containers(self.data,bad,phase='private',binding=self.scope)

    def test_parser_requires_exact_canonical_scope_and_historical_profiles_stay_closed(self):
        rows=phase_rows(self.data,self.rows,'private')
        with self.assertRaises(RuntimeError):inventory.attest_containers(self.data,rows,phase='private')
        for field,value in (('context_sha256','0'*64),('operation','unknown'),('target_schema',159)):
            with self.subTest(field=field),self.assertRaises(RuntimeError):
                inventory.attest_containers(self.data,rows,phase='private',binding=dict(self.scope,**{field:value}))
        (data,scope),rows=fixture(candidates=True)
        data['containers']['candidate:parser-worker']['states']['private']['running']=True
        data,scope=repin(data,scope)
        with self.assertRaises(RuntimeError):inventory.validate_inventory(data,scope)

    def test_private_boundary_permits_only_the_sidecar_and_existing_private_roles(self):
        rows=phase_rows(self.data,self.rows,'fenced')
        parser=next(r for r in rows if r['Id']==self.data['containers']['candidate:parser-worker']['id'])
        parser['State']['Running']=True
        inventory.attest_containers(self.data,rows,phase='private-boundary',binding=self.scope)
        for logical in ('native:gateway','proxy','candidate:remote-ingestion-worker','candidate:notification-worker'):
            bad=copy.deepcopy(rows)
            next(r for r in bad if r['Id']==self.data['containers'][logical]['id'])['State']['Running']=True
            with self.subTest(logical=logical),self.assertRaises(RuntimeError):
                inventory.attest_containers(self.data,bad,phase='private-boundary',binding=self.scope)

    def test_parser_cannot_acquire_credentials_writable_mounts_egress_or_host_authority(self):
        actual=parser_row(self.scope)
        def check(row):
            return runtime.verify_private_parser(row,source_sha=self.scope['source_sha'],image=actual['Image'],
                network_name=actual['HostConfig']['NetworkMode'],uploads_root='/synthetic-owned/private_uploads')
        check(actual)
        faults={
            'credential':lambda r:r['Config']['Env'].append('SUPABASE_SERVICE_KEY=synthetic-forbidden'),
            'dsn':lambda r:r['Config']['Env'].append('DATABASE_URL=postgresql://synthetic'),
            'duplicate_env':lambda r:r['Config']['Env'].append('APP_ENV=production'),
            'command':lambda r:r['Config'].update(Cmd=['python','-m','workers.remote_ingestion_worker']),
            'root':lambda r:r['Config'].update(User='0:0'),
            'entrypoint':lambda r:r['Config'].update(Entrypoint=['sh','-c']),
            'source':lambda r:r['Config']['Env'].__setitem__(1,'MADAR_RELEASE_SHA='+'0'*40),
            'mount':lambda r:r['Mounts'][0].update(RW=True),
            'foreign_root':lambda r:r['Mounts'][0].update(Source='/foreign/private_uploads'),
            'extra_mount':lambda r:r['Mounts'].append({'Type':'bind','Source':'/var/run/docker.sock','Destination':'/sock','RW':False}),
            'egress':lambda r:r['NetworkSettings']['Networks'].update({'egress':{'NetworkID':'8'*64}}),
            'publish':lambda r:r['HostConfig'].update(PortBindings={'8092/tcp':[{'HostIp':'0.0.0.0','HostPort':'8092'}]}),
            'privileged':lambda r:r['HostConfig'].update(Privileged=True),
            'capability':lambda r:r['HostConfig'].update(CapAdd=['NET_ADMIN']),
            'unbounded':lambda r:r['HostConfig'].update(Memory=0),
            'pid_host':lambda r:r['HostConfig'].update(PidMode='host'),
            'restart':lambda r:r['HostConfig'].update(RestartPolicy={'Name':'always'}),
        }
        for name,mutate in faults.items():
            bad=copy.deepcopy(actual);mutate(bad)
            with self.subTest(fault=name),self.assertRaises(RuntimeError):check(bad)

    def test_native_allocation_excludes_existing_networks_and_host_routes(self):
        networks=[{'IPAM':{'Config':[{'Subnet':'10.254.240.0/28'}]}}]
        routes=[{'dst':'default'},{'dst':'10.254.240.16/32'}]
        self.assertEqual(unused_parser_subnet(networks,routes),'10.254.240.32/28')
        with self.assertRaisesRegex(RuntimeError,'subnet_unavailable'):
            unused_parser_subnet(networks,[{'dst':'10.254.240.0/20'}])


@unittest.skipUnless(os.getenv('MADAR_NATIVE_PRIVATE_PARSER_IMAGE'), 'owned native parser image required')
class NativePrivateParserTests(unittest.TestCase):
    """Real Docker/HTTP/RO object access; no database, issuer or controller.

    Supply an immutable image built from the tested source. All temporary
    resources have one unique label and are removed on success AND failure.
    Failed cleanup retains the private directory with an explicit review marker.
    """
    def test_native_parser_has_no_consumer_credentials_and_preserves_upload_bytes(self):
        import base64
        import re
        image=os.environ['MADAR_NATIVE_PRIVATE_PARSER_IMAGE']
        self.assertRegex(image,r'^sha256:[0-9a-f]{64}$')
        base=Path(os.environ.get('MADAR_NATIVE_RUN_ROOT','/opt/madar-development/scratch/codex-runs'))
        self.assertEqual(base.resolve(),Path('/opt/madar-development/scratch/codex-runs'))
        self.assertGreater(shutil.disk_usage(base).free,1024**3)
        run='codex-parser-'+uuid.uuid4().hex
        root=Path(tempfile.mkdtemp(prefix=run+'-',dir=base));root.chmod(0o700)
        identity=root.stat();label='com.madar.codex.run'
        name=run;context=hashlib.sha256(run.encode()).hexdigest()
        network='madar-schema160-'+context[:16]+'-green-parser'
        container_id=network_id=None
        def command(*args,input=None,timeout=45):
            result=subprocess.run(['docker',*args],input=input,text=True,capture_output=True,timeout=timeout)
            if result.returncode:raise RuntimeError('owned_parser_command_failed:'+args[0])
            return result.stdout.strip()
        def inspect():return json.loads(command('inspect',container_id))[0]
        try:
            image_row=json.loads(command('image','inspect',image))[0]
            source=image_row['Config']['Labels']['org.opencontainers.image.revision']
            self.assertRegex(source,r'^[0-9a-f]{40}$')
            uploads=root/'uploads';uploads.mkdir(mode=0o755)
            content=b'year,value\n2026,42\n';(uploads/'original.csv').write_bytes(content)
            (uploads/'original.csv').chmod(0o444)
            identifiers=command('network','ls','-q').split()
            if len(identifiers)>1024:raise RuntimeError('owned_parser_network_inventory_limit')
            networks=json.loads(command('network','inspect',*identifiers)) if identifiers else []
            routes=json.loads(subprocess.check_output(['ip','-json','route','show','table','all'],text=True,timeout=10))
            subnet=unused_parser_subnet(networks,routes)
            network_id=command('network','create','--internal','--subnet',subnet,'--label',label+'='+run,network)
            env={k:v for k,v in runtime._environment(parser_row({'source_sha':source,'context_sha256':context})['Config']['Env']).items()
                if k not in {'PATH','MADAR_BUILD_TIMESTAMP'}}
            args=['create','--name',name,'--label',label+'='+run,'--network',network,'--network-alias','parser-worker',
                '--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true',
                '--init','--memory','768m','--cpus','0.75','--pids-limit','64','--restart','no',
                '--tmpfs','/tmp:rw,noexec,nosuid,size=256m,uid=65534,gid=65534',
                '--mount','type=bind,source='+str(uploads)+',target=/app/private_uploads,readonly',
                '--health-cmd',"python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8092/health', timeout=2)\"",
                '--health-interval','1s','--health-timeout','3s','--health-retries','30']
            for key,value in env.items():args+=['--env',key+'='+value]
            container_id=command(*args,image,'python','-m','workers.parser_worker')
            def verify():
                row=inspect()
                runtime.verify_private_parser(row,source_sha=source,image=image,network_name=network,uploads_root=str(uploads))
                return row
            created=verify();sealed_spec=measured_spec(created);command('start',container_id)
            deadline=time.monotonic()+90
            while True:
                row=verify()
                if row['State'].get('Health',{}).get('Status')=='healthy':break
                self.assertTrue(row['State']['Running'])
                if time.monotonic()>=deadline:self.fail('native parser health timeout')
                time.sleep(.25)
            self.assertTrue(measured_spec_matches(row,sealed_spec,started_worker=True))
            self.assertTrue(json.loads(command('network','inspect',network))[0]['Internal'])
            # Execute requests from the same isolated namespace; no host port or
            # external credentials. The real child process parses real bytes.
            probe='''import hashlib,json,os,urllib.request
from pathlib import Path
payload=json.loads(input())
health=json.load(urllib.request.urlopen('http://127.0.0.1:8092/health',timeout=5))
request=urllib.request.Request('http://127.0.0.1:8092/parse',json.dumps(payload).encode(),{'Content-Type':'application/json'})
result=json.load(urllib.request.urlopen(request,timeout=70))
try: Path('/app/private_uploads/original.csv').write_bytes(b'forbidden')
except OSError: denied=True
else: denied=False
print(json.dumps({'health':health,'result':result,'write_denied':denied,'uid':os.getuid(),
 'parser_sha256':hashlib.sha256(Path('/app/workers/parser_worker.py').read_bytes()).hexdigest()}))'''
            payload={'content_b64':base64.b64encode(content).decode(),'source_url':'https://synthetic.invalid/original.csv',
                'content_type':'text/csv','tenant_id':'synthetic-tenant','user_id':'synthetic-user'}
            result=json.loads(command('exec','-i',container_id,'python','-c',probe,input=json.dumps(payload)+'\n',timeout=80))
            self.assertEqual(result['health'],{'status':'ok','isolation':'parser_worker'})
            self.assertEqual(result['uid'],65534);self.assertTrue(result['write_denied'])
            self.assertEqual((uploads/'original.csv').read_bytes(),content)
            web=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
            self.assertEqual(result['parser_sha256'],hashlib.sha256((web/'backend/workers/parser_worker.py').read_bytes()).hexdigest())
            self.assertIn('42',json.dumps(result['result']))
            receipt={'source_sha':source,'image':image,'parser_sha256':result['parser_sha256'],
                'native_http_parser':'PASS','readonly_original_upload':'PASS','uid':result['uid'],
                'subnet':subnet,'context_sha256':context,'sealed_spec_sha256':sealed_spec,
                'created_oom_kill_disable':created['HostConfig'].get('OomKillDisable'),
                'running_oom_kill_disable':row['HostConfig'].get('OomKillDisable'),
                'spec_equal_after_start':measured_spec(row)==sealed_spec,'protected_upgrade_accepted':False}
        finally:
            try:
                if container_id:
                    row=inspect()
                    self.assertEqual(row['Config']['Labels'].get(label),run)
                    self.assertEqual(row['Name'],'/'+name)
                    command('stop','--time','5',container_id);command('rm',container_id)
                if network_id:
                    net=json.loads(command('network','inspect',network_id))[0]
                    self.assertEqual(net['Labels'].get(label),run);self.assertEqual(net['Name'],network)
                    self.assertFalse(net.get('Containers'));command('network','rm',network_id)
                self.assertFalse(command('ps','-aq','--filter','label='+label+'='+run))
                self.assertFalse(command('network','ls','-q','--filter','label='+label+'='+run))
                current=root.lstat()
                self.assertEqual((current.st_dev,current.st_ino,current.st_uid),(identity.st_dev,identity.st_ino,identity.st_uid))
                shutil.rmtree(root)
            except Exception:
                if root.is_dir() and not root.is_symlink():
                    (root/'cleanup-retained.json').write_text(json.dumps({'owner':run,'container_id':container_id,
                        'network_id':network_id,'reason':'cleanup requires independent ownership/absence recheck',
                        'review_condition':'Remove only after owned Docker resources are proven absent'}))
                raise
        print(json.dumps(dict(receipt,owned_resources_removed=True),sort_keys=True))
