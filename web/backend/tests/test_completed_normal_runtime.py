"""Independent model validation before the observed runtime is sealed."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_runtime as m
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_resources import allocation,ROLES
from test_completed_normal_admission import fixture_contract
from test_completed_normal_manual_profile import manual_contract

class RuntimeModelTests(unittest.TestCase):
    def setUp(self):
        self.contract=fixture_contract();self.selected=allocation(self.contract,'green')
        self.model={'services':{},'networks':{'default':{'name':self.selected['networks']['default'],
            'internal':True,'ipam':{'config':[{'subnet':'10.249.4.0/24'}]}}}}
        self.rows={};self.images={}
        for role in ROLES:
            image=self.contract['candidate']['redis_image'] if role=='redis' else self.contract['candidate']['images']['frontend' if role=='frontend' else 'backend']
            base={'Env':['PATH=/fixture'],'User':'1000:1000','Cmd':['fixture'],'Entrypoint':['/fixture'],
                'WorkingDir':'/app','Labels':{'org.opencontainers.image.revision':'c'*40}}
            self.images[image]={'Id':image,'Config':base}
            env={};volumes=[]
            if role in {'backend',*m.BUSINESS}:
                env={'MADAR_BUSINESS_WRITE_AUTHORITY':'/run/madar/business-write-authority/authority.json',
                    'MADAR_BUSINESS_WRITE_CONTRACT':digest(self.contract),'SCHEMA_COMPATIBLE_MIN':'115','SCHEMA_COMPATIBLE_MAX':'136'}
                volumes=[{'type':'bind','source':str(m.ADMISSIONS/digest(self.contract)/'write-authority'),
                    'target':'/run/madar/business-write-authority','read_only':True,'bind':{'create_host_path':False}}]
            name=self.selected['containers'][role];network=self.selected['networks']['default']
            self.model['services'][role]={'container_name':name,'restart':'no','environment':env,'volumes':volumes,
                'networks':{'default':{}},'mem_limit':1024,'cpus':1,'init':True,'tmpfs':['/tmp:rw,nosuid,size=1m'],
                'healthcheck':{'test':['CMD','true'],'interval':'1s'}}
            row={'Id':digest({'role':role}),'Name':'/'+name,'Image':image,
                'State':{'Running':True,'Health':{'Status':'healthy'}},
                'Config':dict(base,Env=[*base['Env'],*(k+'='+v for k,v in env.items())],
                    Labels={'com.docker.compose.service':role,'com.docker.compose.project':self.selected['project']},
                    Healthcheck={'Test':['CMD','true'],'Interval':1_000_000_000}),
                'HostConfig':{'NetworkMode':network,'RestartPolicy':{'Name':'no'},'Privileged':False,
                    'ReadonlyRootfs':True,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],
                    'Dns':None,'Init':True,'Memory':1024,'NanoCpus':1_000_000_000,
                    'Tmpfs':{'/tmp':'rw,nosuid,size=1m'}},
                'Mounts':[{'Type':'bind','Source':v['source'],'Destination':v['target'],'RW':False} for v in volumes],
                'NetworkSettings':{'Networks':{network:{'NetworkID':'network-id','IPAddress':'10.249.4.2','Aliases':[name,role]}}}}
            self.rows[name]=row
        fixture=self
        class Runtime:
            def inspect(_,names):return {name:fixture.rows[name] for name in names if name in fixture.rows}
            def command(_,args):
                if args[:3]==['docker','image','inspect']:return json.dumps([fixture.images[args[3]]])
                if args[:3]==['docker','network','inspect']:return json.dumps([{'Id':'network-id','Name':args[3],
                    'Driver':'bridge','Internal':True,'IPAM':{'Config':[{'Subnet':'10.249.4.0/24','Gateway':'10.249.4.1'}]}}])
                raise AssertionError(args)
        self.runtime=Runtime()
    def validate(self):return m.validate_model(self.contract,self.model,self.runtime)
    def use_manual_contract(self):
        previous=self.selected
        self.contract=manual_contract();self.selected=allocation(self.contract,'green')
        old_network=previous['networks']['default'];network=self.selected['networks']['default']
        self.model['networks']['default']['name']=network
        rows={}
        for role,service in self.model['services'].items():
            old_name=previous['containers'][role];name=self.selected['containers'][role]
            row=self.rows[old_name];service['container_name']=name
            row.update(Name='/'+name)
            row['Config']['Labels']['com.docker.compose.project']=self.selected['project']
            row['HostConfig']['NetworkMode']=network
            endpoint=row['NetworkSettings']['Networks'].pop(old_network)
            endpoint['Aliases']=[name,role];row['NetworkSettings']['Networks'][network]=endpoint
            if role in {'backend',*m.BUSINESS}:
                service['environment'].update(MADAR_BUSINESS_WRITE_CONTRACT=digest(self.contract),
                    SCHEMA_COMPATIBLE_MIN='136',SCHEMA_COMPATIBLE_MAX='144',SCHEMA_EXCLUDED_VERSIONS='142')
                source=str(m.ADMISSIONS/digest(self.contract)/'write-authority')
                service['volumes'][0]['source']=source;row['Mounts'][0]['Source']=source
                row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]
            rows[name]=row
        self.rows=rows

    def test_manual_profile_accepts_exact_136_144_excluding_142(self):
        self.use_manual_contract();self.validate()
        for role in m.BUSINESS:
            row=self.rows[self.selected['containers'][role]]
            row['State']={'Running':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():
                endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        m.validate_model(self.contract,self.model,self.runtime,phase='staged')

    def test_manual_environment_cannot_supply_arbitrary_authority_bounds(self):
        for key,value in [('SCHEMA_COMPATIBLE_MIN','115'),('SCHEMA_COMPATIBLE_MAX','136'),
                ('SCHEMA_COMPATIBLE_MAX','145'),('SCHEMA_EXCLUDED_VERSIONS',''),('SCHEMA_EXCLUDED_VERSIONS','143')]:
            self.setUp();self.use_manual_contract()
            service=self.model['services']['backend'];service['environment'][key]=value
            self.rows[self.selected['containers']['backend']]['Config']['Env']=[
                'PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]
            with self.subTest(key=key,value=value),self.assertRaisesRegex(RuntimeError,'authority_mount_changed'):
                self.validate()

    def test_manual_profile_preserves_exact_authority_mount_guards(self):
        for change in ('source','writable','create_host_path'):
            self.setUp();self.use_manual_contract()
            volume=self.model['services']['backend']['volumes'][0]
            actual=self.rows[self.selected['containers']['backend']]['Mounts'][0]
            if change=='source':volume['source']=actual['Source']='/unapproved/authority'
            elif change=='writable':volume['read_only']=False;actual['RW']=True
            else:volume['bind']['create_host_path']=True
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'authority_mount_changed'):
                self.validate()

    def test_unapproved_contract_range_is_rejected_before_runtime_inspection(self):
        self.use_manual_contract();self.contract['candidate']['compatible_max']=145
        with self.assertRaisesRegex(RuntimeError,'admission_runtime_invalid'):self.validate()

    def test_exact_model_seals_all_role_specs_and_actual_network_objects(self):
        bindings,networks=self.validate()
        self.assertEqual(set(bindings),set(ROLES));self.assertEqual(len(networks),1)
        self.assertTrue(all(len(value['spec_sha256'])==64 for value in bindings.values()))
    def test_compose_null_command_and_entrypoint_inherit_exact_image_defaults(self):
        for service in self.model['services'].values():
            service.update(command=None,entrypoint=None,user=None,working_dir=None)
        self.validate()
        self.rows[self.selected['containers']['backend']]['Config']['Cmd']=['unexpected']
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):self.validate()
    def test_explicit_command_and_entrypoint_do_not_inherit(self):
        for key,image_key in (('command','Cmd'),('entrypoint','Entrypoint')):
            with self.subTest(key=key):
                self.model['services']['backend'][key]=[]
                with self.assertRaisesRegex(RuntimeError,'configuration_changed'):self.validate()
                self.rows[self.selected['containers']['backend']]['Config'][image_key]=[]
                self.validate()
                self.model['services']['backend'].pop(key)
                self.rows[self.selected['containers']['backend']]['Config'][image_key]=self.images[self.contract['candidate']['images']['backend']]['Config'][image_key]
    def test_created_standbys_require_declarations_and_objects_without_live_endpoints(self):
        for role in m.BUSINESS:
            row=self.rows[self.selected['containers'][role]]
            row['State']={'Running':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():
                endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        bindings,_=m.validate_model(self.contract,self.model,self.runtime,phase='staged')
        self.assertEqual(len(bindings),8)
        with self.assertRaisesRegex(RuntimeError,'not_running'):self.validate()
        row=self.rows[self.selected['containers'][m.BUSINESS[0]]]
        row['State'].update(Running=True,Status='running')
        with self.assertRaisesRegex(RuntimeError,'standby_started'):
            m.validate_model(self.contract,self.model,self.runtime,phase='staged')
    def test_created_phase_cannot_hide_exited_worker_wrong_network_or_alias(self):
        for role in m.BUSINESS:
            row=self.rows[self.selected['containers'][role]]
            row['State']={'Running':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        row=self.rows[self.selected['containers'][m.BUSINESS[0]]]
        row['State']['Status']='exited'
        with self.assertRaisesRegex(RuntimeError,'standby_started'):
            m.validate_model(self.contract,self.model,self.runtime,phase='staged')
        row['State']['Status']='created'
        endpoint=next(iter(row['NetworkSettings']['Networks'].values()));endpoint['NetworkID']='unexpected'
        with self.assertRaisesRegex(RuntimeError,'network_role_changed'):
            m.validate_model(self.contract,self.model,self.runtime,phase='staged')

    def fenced(self):
        for role in ROLES:
            row=self.rows[self.selected['containers'][role]]
            row['State']={'Running':False,'Restarting':False,'Status':'created' if role in m.BUSINESS else 'exited'}
            for endpoint in row['NetworkSettings']['Networks'].values():
                endpoint.update(IPAddress='',EndpointID='')
        return m.validate_model(self.contract,self.model,self.runtime,phase='fenced')

    def test_fenced_model_validates_every_stopped_role_without_probing_public_health(self):
        bindings,_=self.fenced()
        self.assertEqual(set(bindings),set(ROLES))
        with self.assertRaisesRegex(RuntimeError,'not_running'):self.validate()

    def test_fenced_candidate_rejects_any_running_restarting_or_ambiguous_role(self):
        self.fenced()
        for role in ROLES:
            row=self.rows[self.selected['containers'][role]];original=copy.deepcopy(row['State'])
            for change in ({'Running':True},{'Restarting':True},{'Status':'paused'},
                    {'Status':'removing'},{'Running':None},{'Restarting':None}):
                row['State'].update(change)
                with self.subTest(role=role,change=change),self.assertRaisesRegex(RuntimeError,'fenced_candidate_started'):
                    m.validate_model(self.contract,self.model,self.runtime,phase='fenced')
                row['State']=copy.deepcopy(original)

    def test_fenced_candidate_retains_full_image_configuration_and_security_validation(self):
        self.fenced();row=self.rows[self.selected['containers']['backend']];original=copy.deepcopy(row)
        for change in (lambda:row.update(Image='sha256:'+'f'*64),
                lambda:row['Config']['Env'].append('UNAPPROVED=1'),
                lambda:row['HostConfig'].update(Privileged=True),
                lambda:row['HostConfig']['RestartPolicy'].update(Name='always')):
            change()
            with self.assertRaises(RuntimeError):m.validate_model(self.contract,self.model,self.runtime,phase='fenced')
            row.clear();row.update(copy.deepcopy(original))

    def test_fenced_candidate_rejects_live_or_substituted_network_endpoints(self):
        self.fenced();row=self.rows[self.selected['containers']['backend']]
        endpoint=next(iter(row['NetworkSettings']['Networks'].values()));original=copy.deepcopy(endpoint)
        for change in ({'IPAddress':'10.249.4.2'},{'EndpointID':'live-endpoint'},{'NetworkID':'substituted'}):
            endpoint.update(change)
            with self.assertRaisesRegex(RuntimeError,'network_role_changed'):
                m.validate_model(self.contract,self.model,self.runtime,phase='fenced')
            endpoint.clear();endpoint.update(original)
    def test_unapproved_environment_command_user_or_mount_never_becomes_trusted_hash(self):
        row=self.rows[self.selected['containers']['backend']];original=copy.deepcopy(row)
        for mutate in (lambda r:r['Config']['Env'].append('UNAPPROVED=1'),lambda r:r['Config'].update(User='0:0'),
                lambda r:r['Config'].update(Cmd=['unauthorized']),
                lambda r:r['Mounts'].append({'Destination':'/var/run/docker.sock','Source':'/var/run/docker.sock','Type':'bind','RW':True})):
            mutate(row)
            with self.assertRaises(RuntimeError):self.validate()
            row.clear();row.update(copy.deepcopy(original))
    def test_privilege_caps_dns_restart_and_resource_changes_reject(self):
        host=self.rows[self.selected['containers']['backend']]['HostConfig'];original=copy.deepcopy(host)
        for key,value in [('Privileged',True),('CapAdd',['NET_ADMIN']),('Dns',['1.1.1.1']),('Memory',2048),
                ('SecurityOpt',[]),('PidMode','host'),('RestartPolicy',{'Name':'always'})]:
            host[key]=value
            with self.assertRaisesRegex(RuntimeError,'security_changed'):self.validate()
            host.clear();host.update(copy.deepcopy(original))
    def test_healthcheck_and_tmpfs_security_cannot_be_mutated_before_sealing(self):
        row=self.rows[self.selected['containers']['backend']]
        row['Config']['Healthcheck']['Test']=['CMD','false']
        with self.assertRaisesRegex(RuntimeError,'healthcheck_changed'):self.validate()
        row['Config']['Healthcheck']['Test']=['CMD','true'];row['HostConfig']['Tmpfs']['/tmp']='rw,suid'
        with self.assertRaisesRegex(RuntimeError,'tmpfs_changed'):self.validate()
    def test_role_alias_attachment_and_authority_mount_mismatch_reject(self):
        row=self.rows[self.selected['containers']['backend']];network=self.selected['networks']['default']
        row['NetworkSettings']['Networks'][network]['Aliases'].append('unauthorized')
        with self.assertRaisesRegex(RuntimeError,'network_role_changed'):self.validate()
        row['NetworkSettings']['Networks'][network]['Aliases'].pop();row['Mounts'][0]['RW']=True
        with self.assertRaisesRegex(RuntimeError,'mount_changed'):self.validate()
    def test_image_source_and_missing_role_are_not_acceptance(self):
        image=self.contract['candidate']['images']['backend'];self.images[image]['Config']['Labels']={}
        with self.assertRaisesRegex(RuntimeError,'image_source_changed'):self.validate()
        self.images[image]['Config']['Labels']={'org.opencontainers.image.revision':'c'*40}
        self.rows.pop(self.selected['containers']['parser-worker'])
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.validate()

    def test_starting_health_is_transient_only_after_full_security_validation(self):
        row=self.rows[self.selected['containers'][m.BUSINESS[0]]]
        row['State']['Health']['Status']='starting'
        with self.assertRaisesRegex(m.AvailabilityFailure,'health_activation_pending'):self.validate()
        row['HostConfig']['Privileged']=True
        with self.assertRaisesRegex(RuntimeError,'security_changed'):self.validate()
        row['HostConfig']['Privileged']=False;row['Image']='unexpected'
        with self.assertRaisesRegex(RuntimeError,'running_identity_changed'):self.validate()
        row['Image']=self.contract['candidate']['images']['backend']
        row['State']['Health']['Status']='unhealthy'
        with self.assertRaisesRegex(RuntimeError,'running_identity_changed'):self.validate()
        row['State']['Health']['Status']='healthy';self.validate()

    def test_bounded_running_seal_rechecks_authority_after_delayed_health(self):
        row=self.rows[self.selected['containers'][m.BUSINESS[0]]]
        row['State']['Health']['Status']='starting'
        runtime=m.Runtime() if hasattr(m,'Runtime') else __import__('deployment.lib.emergency_routing_repair',fromlist=['Runtime']).Runtime()
        source=Mock();loader=Mock(return_value=self.model)
        with patch.object(m,'require_fresh_authorization') as authorization,patch('deployment.lib.completed_normal_admission.require_candidate_authority') as authority,patch.object(m.time,'sleep',side_effect=lambda _:row['State']['Health'].update(Status='healthy')):
            # Retain the genuine model validator and its Docker inspection.
            runtime.inspect=self.runtime.inspect;runtime.command=self.runtime.command
            bindings,_=m.converge_running_model(self.contract,loader,runtime,source)
        self.assertEqual(len(bindings),8)
        self.assertEqual(source.call_count,2);self.assertEqual(loader.call_count,2)
        self.assertEqual(authorization.call_count,2);self.assertEqual(authority.call_count,2)
        self.assertIsNone(runtime.deadline)

    def test_pending_health_deadline_and_integrity_failures_never_seal(self):
        from deployment.lib.emergency_routing_repair import Runtime,VerificationDeadline
        row=self.rows[self.selected['containers'][m.BUSINESS[0]]];row['State']['Health']['Status']='starting'
        runtime=Runtime();runtime.inspect=self.runtime.inspect;runtime.command=self.runtime.command
        runtime.budget=Mock(side_effect=[1,1,VerificationDeadline('verification_deadline_expired')])
        with patch.object(m,'require_fresh_authorization'),patch('deployment.lib.completed_normal_admission.require_candidate_authority'),patch.object(m.time,'sleep'):
            with self.assertRaisesRegex(VerificationDeadline,'verification_deadline_expired'):
                m.converge_running_model(self.contract,lambda:self.model,runtime,lambda:None)
        self.assertIsNone(runtime.deadline)
        runtime.budget=Mock(return_value=1);row['HostConfig']['Privileged']=True
        with patch.object(m,'require_fresh_authorization'),patch('deployment.lib.completed_normal_admission.require_candidate_authority'),patch.object(m.time,'sleep') as pause:
            with self.assertRaisesRegex(RuntimeError,'security_changed'):
                m.converge_running_model(self.contract,lambda:self.model,runtime,lambda:None)
            pause.assert_not_called()

if __name__=='__main__':unittest.main()
