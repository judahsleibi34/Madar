"""Real disposable Docker lifecycle coverage; explicitly opt in on the host."""
import copy,ipaddress,json,os,subprocess,sys,unittest,uuid
from pathlib import Path
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import verify_lifecycle_networks,worker_spec_matches
from deployment.lib.emergency_routing_repair import spec

@unittest.skipUnless(os.getenv('MADAR_REAL_DOCKER_NETWORK_TEST')=='1','requires explicitly selected disposable host Docker fixture')
class CreatedWorkerDockerTests(unittest.TestCase):
    @classmethod
    def command(cls,*argv):return subprocess.check_output(['docker',*argv],text=True,timeout=40).strip()
    @classmethod
    def setUpClass(cls):
        cls.prefix='madar-created-network-regression-'+uuid.uuid4().hex[:12];cls.networks={};cls.container=None
        image=os.environ['MADAR_CREATED_TEST_IMAGE'];cls.command('image','inspect',image)
        ids=cls.command('network','ls','-q').splitlines()
        rows=json.loads(cls.command('network','inspect',*ids))
        occupied=[ipaddress.ip_network(v['Subnet']) for row in rows for v in row.get('IPAM',{}).get('Config') or [] if v.get('Subnet')]
        occupied += [ipaddress.ip_network(row['dst'],strict=False) for row in json.loads(subprocess.check_output(['ip','-j','route'],text=True)) if row.get('dst') not in (None,'default')]
        free=iter(n for n in ipaddress.ip_network('10.248.0.0/16').subnets(new_prefix=24) if not any(n.overlaps(v) for v in occupied if v.version==4))
        try:
            for role in ('primary','client','redis'):
                name=cls.prefix+'-'+role;identifier=cls.command('network','create','--internal','--subnet',str(next(free)),'--label','com.madar.disposable-test=created-worker-network',name);cls.networks[name]=identifier
            cls.primary=cls.prefix+'-primary'
            cls.container=cls.command('create','--name',cls.prefix,'--network',cls.primary,'--network-alias','notification-worker','--restart','no','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--entrypoint','/bin/sh','--label','com.madar.disposable-test=created-worker-network',image,'-c','sleep 300')
            for name in cls.networks:
                if name!=cls.primary:cls.command('network','connect',name,cls.container)
            cls.created=json.loads(cls.command('inspect',cls.container))[0]
            cls.created_spec=spec(cls.created)
        except Exception:
            cls.tearDownClass();raise
    @classmethod
    def tearDownClass(cls):
        if cls.container:cls.command('rm','-f',cls.container)
        for identifier in reversed(list(cls.networks.values())):cls.command('network','rm',identifier)
    def test_01_actual_created_declarations_pass_without_runtime_ids(self):
        self.assertEqual(self.created['State']['Status'],'created');self.assertFalse(self.created['State']['Running'])
        self.assertTrue(any(not n['NetworkID'] for n in self.created['NetworkSettings']['Networks'].values()))
        for name,identifier in self.networks.items():self.assertEqual(json.loads(self.command('network','inspect',name))[0]['Id'],identifier)
        verify_lifecycle_networks(self.created,self.networks,self.primary,'notification-worker',created_worker=True)
    def test_02_created_negative_cases(self):
        for defect in ('unexpected_network','network_id','alias','secondary_alias','endpoint','running','exited','primary'):
            row=copy.deepcopy(self.created);attached=row['NetworkSettings']['Networks']
            if defect=='unexpected_network':attached['unexpected']={}
            elif defect=='network_id':attached[self.primary]['NetworkID']='0'*64
            elif defect=='alias':attached[self.primary]['Aliases']=['wrong-role']
            elif defect=='secondary_alias':attached[next(n for n in self.networks if n!=self.primary)]['Aliases']=['backend']
            elif defect=='endpoint':attached[self.primary]['EndpointID']='unexpected'
            elif defect=='running':row['State']['Running']=True;row['State']['Status']='running'
            elif defect=='exited':row['State']['Status']='exited'
            else:row['HostConfig']['NetworkMode']='host'
            with self.subTest(defect=defect),self.assertRaises(RuntimeError):verify_lifecycle_networks(row,self.networks,self.primary,'notification-worker',created_worker=True)
    def test_03_running_requires_populated_exact_ids_and_preserves_bound_spec(self):
        self.command('start',self.container);running=json.loads(self.command('inspect',self.container))[0]
        self.assertTrue(running['State']['Running'])
        self.assertTrue(worker_spec_matches(running,self.created_spec,started_worker=True))
        altered=copy.deepcopy(running);altered['HostConfig']['OomKillDisable']=True
        self.assertFalse(worker_spec_matches(altered,self.created_spec,started_worker=True))
        for field in ('Id','Image','Config','Mounts'):
            altered=copy.deepcopy(running);altered[field]=None
            self.assertFalse(worker_spec_matches(altered,self.created_spec,started_worker=True))
        verify_lifecycle_networks(running,self.networks,self.primary,'notification-worker')
        for name in self.networks:
            altered=copy.deepcopy(running);altered['NetworkSettings']['Networks'][name]['NetworkID']=''
            with self.subTest(network=name),self.assertRaises(RuntimeError):verify_lifecycle_networks(altered,self.networks,self.primary,'notification-worker')
        with self.assertRaises(RuntimeError):verify_lifecycle_networks(running,self.networks,self.primary,'notification-worker',created_worker=True)

    def test_04_stopped_after_governed_start_retains_bound_network_ids(self):
        self.command('stop','-t','1',self.container)
        stopped=json.loads(self.command('inspect',self.container))[0]
        self.assertFalse(stopped['State']['Running'])
        verify_lifecycle_networks(stopped,self.networks,self.primary,'notification-worker')
        self.assertTrue(worker_spec_matches(stopped,self.created_spec,started_worker=True))
        with self.assertRaises(RuntimeError):verify_lifecycle_networks(stopped,self.networks,self.primary,'notification-worker',created_worker=True)
