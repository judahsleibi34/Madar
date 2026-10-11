"""Independent model validation before the observed runtime is sealed."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import completed_normal_runtime as m
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_resources import allocation,ROLES
from test_completed_normal_admission import fixture_contract

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
    def test_exact_model_seals_all_role_specs_and_actual_network_objects(self):
        bindings,networks=self.validate()
        self.assertEqual(set(bindings),set(ROLES));self.assertEqual(len(networks),1)
        self.assertTrue(all(len(value['spec_sha256'])==64 for value in bindings.values()))
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

if __name__=='__main__':unittest.main()
