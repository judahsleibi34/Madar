"""Negative environment observations. This suite grants no operation authority."""
import copy,json,tempfile,unittest,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from deployment.lib import isolated_release_environment as env


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.policy=Path(temp.name)/'policy.json'
        self.p={'version':1,'realm_id':str(uuid.uuid4()),'guest_uuid':str(uuid.uuid4()),'machine_id':'a'*32,
            'root_filesystem_uuid':str(uuid.uuid4()),'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
            'database_container_id':'b'*64,'database_system_identifier':'123456789','denied_database_identifiers':['987654321']}
        self.virt='kvm';self.hostname='madar-release-test';self.interface='ens3'
        self.chains=[{'chain':{'name':name,'hook':name,'type':'filter','prio':200,'policy':'accept'}} for name in ('output','forward')]
        self.rules=[{'rule':{'chain':chain,'expr':expr}} for chain,rows in env.required_rules(self.interface).items() for expr in rows]
        self.actors=[{'Id':self.p['database_container_id'],'Name':'/supabase-db','Config':{'Labels':{env.REALM_LABEL:self.p['realm_id']}},
            'HostConfig':{'NetworkMode':'owned-test','PortBindings':{},'Privileged':False,'CapAdd':[]},
            'Mounts':[{'Type':'volume','Name':'owned-db'}],
            'NetworkSettings':{'Networks':{'owned':{'NetworkID':'c'*64}}}}]
        self.networks=[{'Id':'c'*64,'Driver':'bridge','EnableIPv6':False,'Labels':{env.REALM_LABEL:self.p['realm_id']}}]
        self.volumes=[{'Name':'owned-db','Driver':'local','Options':None,'Labels':{env.REALM_LABEL:self.p['realm_id']}}]
        self.observed=[self.p['database_system_identifier'],'madar-isolated-'+self.p['realm_id']]
        self.enterContext(patch.object(env.os,'geteuid',return_value=0))
        self.enterContext(patch.object(env,'protected',lambda p,**kw:p))
        self.commands=[];self.enterContext(patch.object(env,'run',side_effect=self.command))
        original=Path.read_text
        def identity(path,*args,**kwargs):
            if str(path)=='/sys/class/dmi/id/product_uuid':return self.p['guest_uuid']
            if str(path)=='/etc/machine-id':return self.p['machine_id']
            return original(path,*args,**kwargs)
        self.enterContext(patch.object(Path,'read_text',identity))

    def command(self,args):
        self.commands.append(args)
        if args==['/usr/bin/systemd-detect-virt']:return self.virt.encode()
        if args==['/bin/hostname']:return self.hostname.encode()
        if args[0]=='/usr/bin/findmnt':return ('/dev/vda1 ext4 '+self.p['root_filesystem_uuid']).encode()
        if args[0]=='/usr/sbin/ip':return json.dumps([{'dev':self.interface}]).encode()
        if args[0]=='/usr/sbin/nft':return json.dumps({'nftables':self.chains+self.rules}).encode()
        if args[1:3]==['ps','-aq']:return ('\n'.join(r['Id'] for r in self.actors)).encode()
        if args[1]=='inspect':return json.dumps(self.actors).encode()
        if args[1:3]==['network','inspect']:return json.dumps(self.networks).encode()
        if args[1:3]==['volume','inspect']:return json.dumps(self.volumes).encode()
        if args[1]=='exec':
            self.assertIn('BEGIN READ ONLY;',args[-1]);self.assertIn('pg_control_system()',args[-1])
            return json.dumps(self.observed).encode()
        self.fail('unexpected command '+str(args))

    def observe(self):
        self.policy.write_text(json.dumps(self.p));return env.observe(self.policy)

    def test_exact_owned_guest_database_network_volumes_and_firewall_are_measured(self):
        observed=self.observe()
        self.assertEqual(observed['realm_id'],self.p['realm_id']);self.assertEqual(observed['control_interface'],'ens3')
        self.assertNotIn('authority',observed);self.assertFalse(any(x in self.commands for x in (['docker','start'],['systemctl','start'])))

    def test_wrong_guest_and_expired_or_production_database_refuse(self):
        for change in ('virt','hostname','expiry','db','production','realm'):
            old=copy.deepcopy(self.p);old_observed=list(self.observed)
            if change=='virt':self.virt='none'
            elif change=='hostname':self.hostname='madar-staging'
            elif change=='expiry':self.p['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
            elif change=='db':self.observed[0]='987654321'
            elif change=='production':self.p['denied_database_identifiers'].append(self.p['database_system_identifier'])
            elif change=='realm':self.p['realm_id']='z'*36
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.observe()
            self.p=old;self.observed=old_observed;self.virt='kvm';self.hostname='madar-release-test'

    def test_missing_or_relaxed_firewall_rules_refuse(self):
        original=copy.deepcopy(self.rules)
        for change in ('missing','accept','priority','extra'):
            if change=='missing':self.rules.pop()
            elif change=='accept':self.rules[0]['rule']['expr'][-1]={'accept':None}
            elif change=='priority':self.chains[0]['chain']['prio']=-200
            else:self.rules.append({'rule':{'chain':'forward','expr':[{'accept':None}]}})
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'effect_fencing_invalid'):self.observe()
            self.rules=copy.deepcopy(original);self.chains[0]['chain']['prio']=200

    def test_foreign_exposed_privileged_shared_or_unowned_resources_refuse(self):
        mutations=[lambda:self.actors[0]['Config']['Labels'].clear(),
            lambda:self.actors[0]['HostConfig'].update(Privileged=True),
            lambda:self.actors[0]['HostConfig'].update(NetworkMode='container:foreign'),
            lambda:self.actors[0]['HostConfig'].update(PidMode='host'),
            lambda:self.actors[0]['HostConfig'].update(CapAdd=['NET_ADMIN']),
            lambda:self.actors[0]['HostConfig'].update(PortBindings={'5432/tcp':[{'HostIp':'0.0.0.0','HostPort':'5432'}]}),
            lambda:self.actors[0]['Mounts'].append({'Type':'bind','Source':'/var/run/docker.sock'}),
            lambda:self.networks[0]['Labels'].clear(),
            lambda:self.networks[0].update(EnableIPv6=True),
            lambda:self.volumes[0]['Labels'].clear(),
            lambda:self.volumes[0].update(Options={'device':'/production'})]
        for mutate in mutations:
            original=copy.deepcopy((self.actors,self.networks,self.volumes));mutate()
            with self.subTest(mutate=mutate),self.assertRaises(RuntimeError):self.observe()
            self.actors,self.networks,self.volumes=original

    def enroll_v2_model(self):
        from deployment.lib.completed_normal_resources import measured_spec
        self.p['version']=2
        for row in self.actors:
            for mount in row['Mounts']:
                if mount['Type']=='volume':mount.setdefault('Destination','/var/lib/postgresql/data')
            row['Image']='sha256:'+'e'*64
            row['HostConfig'].update(Memory=256*1024**2,NanoCpus=500000000,PidsLimit=64)
        self.p['runtime_scope']={row['Id']:{'name':row['Name'],'image':row['Image'],
            'spec_sha256':measured_spec(row),'binds':{}} for row in self.actors}
        wanted=env.required_rules(self.interface,execution=True)
        self.chains=[{'chain':{'name':name,'hook':name,'type':'filter','prio':200,'policy':'accept'}} for name in wanted]
        self.rules=[{'rule':{'chain':chain,'expr':expr}} for chain,rows in wanted.items() for expr in rows]

    def test_v2_exact_runtime_uses_stricter_execution_fence_not_preparation_internet_rules(self):
        self.enroll_v2_model()
        self.assertEqual(self.observe()['version'],2)
        self.rules=[{'rule':{'chain':chain,'expr':expr}} for chain,rows in env.required_rules(self.interface).items() for expr in rows]
        with self.assertRaisesRegex(RuntimeError,'effect_fencing_invalid'):self.observe()

    def test_v2_substitution_unenrolled_actor_and_unbounded_runtime_refuse(self):
        self.enroll_v2_model();original=copy.deepcopy((self.actors,self.p))
        changes=[lambda:self.actors[0].update(Image='sha256:'+'f'*64),
                 lambda:self.actors[0]['Config'].update(Cmd=['substituted']),
                 lambda:self.actors[0]['HostConfig'].update(Memory=0),
                 lambda:self.actors[0]['HostConfig'].update(NanoCpus=0),
                 lambda:self.actors[0]['HostConfig'].update(PidsLimit=0),
                 lambda:self.actors.append(dict(self.actors[0],Id='d'*64))]
        for change in changes:
            change()
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.observe()
            self.actors,self.p=copy.deepcopy(original)

    def test_v2_exact_readonly_bind_is_measured_not_enrolled_by_container_label(self):
        self.actors[0]['Mounts'].append({'Type':'bind','Source':'/etc/madar/test-input',
            'Destination':'/app/test-input','RW':False,'Propagation':'rprivate'})
        self.enroll_v2_model()
        with self.assertRaisesRegex(RuntimeError,'mount_inventory_changed'):self.observe()
        expected={'source':'/etc/madar/test-input','mutable_data':False,'contents_sha256':'d'*64}
        self.p['runtime_scope'][self.actors[0]['Id']]['binds']['/app/test-input']=expected
        with patch.object(env,'measure_bind_source',return_value=expected) as measure:
            self.assertEqual(self.observe()['version'],2)
            measure.assert_called_once_with('/etc/madar/test-input',mutable=False)
        with patch.object(env,'measure_bind_source',return_value=dict(expected,contents_sha256='f'*64)):
            with self.assertRaisesRegex(RuntimeError,'bind_source_changed'):self.observe()

    def test_v2_host_network_restricted_to_exact_bounded_proxy_and_strict_firewall(self):
        self.actors[0]['HostConfig']['NetworkMode']='host'
        self.enroll_v2_model()
        with self.assertRaisesRegex(RuntimeError,'foreign_or_exposed_actor'):self.observe()
        # Actual fixture database stays bridged; only proxy may share guest loopback.
        proxy=copy.deepcopy(self.actors[0]);proxy.update(Id='d'*64,Name='/madar-release-proxy')
        proxy['Mounts']=[];proxy['NetworkSettings']['Networks']={}
        self.actors[0]['HostConfig']['NetworkMode']='owned-test';self.actors.append(proxy);self.enroll_v2_model()
        self.assertEqual(self.observe()['version'],2)

    def test_ordinary_user_cannot_activate_environment_observation(self):
        with patch.object(env.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(RuntimeError,'root_required'):self.observe()
        self.assertEqual(self.commands,[])


if __name__=='__main__':unittest.main()
