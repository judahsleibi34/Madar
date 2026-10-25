"""Independent model validation before the observed runtime is sealed."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
from contextlib import ExitStack, nullcontext

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
            def budget(_,maximum):return maximum
            def inspect(_,names):return {name:fixture.rows[name] for name in names if name in fixture.rows}
            def command(_,args):
                if args[:3]==['docker','image','inspect']:return json.dumps([fixture.images[args[3]]])
                if args[:3]==['docker','network','inspect']:return json.dumps([{'Id':'network-id','Name':args[3],
                    'Driver':'bridge','Internal':True,'IPAM':{'Config':[{'Subnet':'10.249.4.0/24','Gateway':'10.249.4.1'}]}}])
                raise AssertionError(args)
        self.runtime=Runtime()
    def validate(self):return m.validate_model(self.contract,self.model,self.runtime)
    def use_manual_contract(self, contract=None, *, preparation150=False):
        previous=self.selected
        self.contract=manual_contract() if contract is None else contract
        self.selected=allocation(self.contract,'green',preparation150=preparation150)
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
                    SCHEMA_COMPATIBLE_MIN=str(self.contract['candidate']['compatible_min']),
                    SCHEMA_COMPATIBLE_MAX=str(self.contract['candidate']['compatible_max']),
                    SCHEMA_EXCLUDED_VERSIONS='142' if not preparation150 else '')
                if self.contract.get('operation')=='completed-normal-schema146-160-coordinated-release':
                    service['environment'].update(MADAR_RELEASE_CONTROLLER_SHA=self.contract['candidate']['controller_sha'],
                        MADAR_RELEASE_MIGRATION_MANIFEST_SHA256=self.contract['migration_manifest_sha256'])
                source=str(m.ADMISSIONS/digest(self.contract)/'write-authority')
                service['volumes'][0]['source']=source;row['Mounts'][0]['Source']=source
                row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]
            rows[name]=row
        self.rows=rows
        if self.contract.get('operation')=='completed-normal-schema146-160-coordinated-release':
            from test_schema160_private_parser import parser_row
            scope={'context_sha256':digest(self.contract),'source_sha':self.contract['candidate']['source_sha']}
            old=self.rows[self.selected['containers']['parser-worker']]
            row=parser_row(scope,name=old['Name'].lstrip('/'),identifier=old['Id'])
            row['Image']=old['Image'];row['Config']['Labels'].update(old['Config']['Labels'])
            row['Config']['Entrypoint']=[]
            row['Config']['Healthcheck']=old['Config']['Healthcheck']
            row['State']=old['State'];row['Config']['Env'][3]='PATH=/fixture'
            self.rows[row['Name'].lstrip('/')]=row
            network=self.selected['networks']['parser']
            endpoint=row['NetworkSettings']['Networks'][network]
            endpoint.update(NetworkID='network-id',IPAddress='10.249.4.2',Aliases=[row['Name'].lstrip('/'),'parser-worker'])
            self.model['networks']['parser_internal']={'name':network,'internal':True,
                'ipam':{'config':[{'subnet':'10.249.4.0/24'}]}}
            service=self.model['services']['parser-worker']
            service.update(user='65534:65534',working_dir='/app',entrypoint=[],command=row['Config']['Cmd'],
                environment={k:v for k,v in m._environment(row['Config']['Env']).items() if k!='PATH'},
                mem_limit=768*1024*1024,cpus=.75,pids_limit=64,
                tmpfs=['/tmp:rw,noexec,nosuid,size=256m,uid=65534,gid=65534'],networks={'parser_internal':{}},
                volumes=[{'type':'bind','source':'/synthetic-owned/private_uploads',
                    'target':'/app/private_uploads','read_only':True}])

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

    def test_provisional_150_model_has_no_operational_admission_or_live_process(self):
        from test_schema150_admission import deletion_contract
        from deployment.lib.completed_normal_profile import profile
        self.use_manual_contract(deletion_contract(),preparation150=True)
        for row in self.rows.values():
            row['State']={'Running':False,'Restarting':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():
                endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        bindings,_=m.validate_model(self.contract,self.model,self.runtime,phase='provisional')
        self.assertEqual(set(bindings),set(ROLES))
        with self.assertRaisesRegex(RuntimeError,'operation_profile_invalid'):profile(self.contract)
        for phase in ('staged','running','fenced'):
            with self.subTest(phase=phase),self.assertRaisesRegex(RuntimeError,'operation_profile_invalid'):
                m.validate_model(self.contract,self.model,self.runtime,phase=phase)
        for role in ROLES:
            row=self.rows[self.selected['containers'][role]]
            row['State']['Status']='exited'
            with self.subTest(role=role),self.assertRaisesRegex(RuntimeError,'fenced_candidate_started'):
                m.validate_model(self.contract,self.model,self.runtime,phase='provisional')
            row['State']['Status']='created'

    def test_provisional_150_model_does_not_adopt_changed_runtime_or_contract(self):
        from test_schema150_admission import deletion_contract
        self.use_manual_contract(deletion_contract(),preparation150=True)
        for row in self.rows.values():
            row['State']={'Running':False,'Restarting':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():
                endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        target=self.rows[self.selected['containers']['backend']];original=copy.deepcopy(target)
        for change in (lambda:target.update(Image='sha256:'+'f'*64),
                lambda:target['Config']['Env'].append('UNAPPROVED=1'),
                lambda:target['HostConfig'].update(Privileged=True),
                lambda:target['State'].update(Running=True),
                lambda:target['State'].update(Restarting=True)):
            change()
            with self.assertRaises(RuntimeError):m.validate_model(self.contract,self.model,self.runtime,phase='provisional')
            target.clear();target.update(copy.deepcopy(original))
        self.contract['candidate']['compatible_max']=151
        with self.assertRaises(RuntimeError):m.validate_model(self.contract,self.model,self.runtime,phase='provisional')

    def test_maintenance_stage_seals_only_created_fenced_identities_without_starting_workers(self):
        """Real exclusive publication, modeled authority/source transports."""
        from test_schema150_admission import deletion_contract
        from deployment.lib.completed_normal_admission import prepared_path
        self.use_manual_contract(deletion_contract(),preparation150=True)
        for row in self.rows.values():
            row['State']={'Running':False,'Restarting':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);admissions=root/'admissions';context=admissions/digest(self.contract)
            context.mkdir(parents=True,mode=0o700)
            prepared=prepared_path(self.contract,root,preparation150=True)
            record={'release_sha':self.contract['candidate']['source_sha'],'candidate_slot':'green',
                'status':'candidate_created_fenced','prepared_at':'2026-10-21T00:00:00Z'}
            prepared.write_text(json.dumps(record))
            original=root/'origin-runtime.json'
            original.write_text(json.dumps({'runtimes':{role:{'id':str(i)*64} for i,role in enumerate(m.BUSINESS,1)}}))
            owner={'owner':'CANDIDATE','generation':self.contract['origin']['worker_generation'],
                'candidate':{'sha':self.contract['source_roles']['application_sha'],'slot':self.contract['origin']['slot']}}
            authority=stack.enter_context(patch.object(m,'require_fresh_authorization'))
            stack.enter_context(patch('deployment.lib.completed_normal_admission.require_candidate_authority'))
            stack.enter_context(patch('deployment.lib.provider_recovery_runtime.readonly_configuration',side_effect=lambda path,**kw:Path(path)))
            stack.enter_context(patch.object(m,'protected',return_value=original))
            stack.enter_context(patch.object(m.os,'geteuid',return_value=0))
            stack.enter_context(patch.object(m,'runtime_mutation_lock',return_value=nullcontext()))
            stack.enter_context(patch.object(m,'load_worker_authority',return_value=owner))
            proof=m.seal_candidate_stage(self.contract,source_guard=lambda:None,model_loader=lambda:self.model,
                runtime=self.runtime,state_root=root,admissions=admissions)
            self.assertEqual(proof['preparation_mode'],'created-fenced')
            self.assertEqual(set(proof['runtimes']),set(ROLES))
            self.assertEqual(json.loads((context/'candidate-staged-runtime.json').read_text()),proof)
            authority.assert_called()
            with self.assertRaises(FileExistsError):
                m.seal_candidate_stage(self.contract,source_guard=lambda:None,model_loader=lambda:self.model,
                    runtime=self.runtime,state_root=root,admissions=admissions)

    def test_reconciled160_creation_stage_retains_identical_image_configuration_and_worker_fences(self):
        from test_schema160_release import reconciled_contract
        with patch('test_schema150_admission.deletion_contract',reconciled_contract):
            self.test_maintenance_stage_seals_only_created_fenced_identities_without_starting_workers()
        self.assertEqual(self.contract['candidate']['compatible_max'],160)
        self.assertIn('schema160',self.selected['prefix'])

    def test_canonical_authority_pins_cannot_be_substituted_in_both_model_and_runtime(self):
        from test_schema160_release import reconciled_contract
        self.use_manual_contract(reconciled_contract(),preparation150=True)
        for row in self.rows.values():
            row['State']={'Running':False,'Restarting':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        m.validate_model(self.contract,self.model,self.runtime,phase='provisional')
        for role in {'backend',*m.BUSINESS}:
            service=self.model['services'][role];row=self.rows[self.selected['containers'][role]]
            for key in ('MADAR_RELEASE_CONTROLLER_SHA','MADAR_RELEASE_MIGRATION_MANIFEST_SHA256'):
                before=service['environment'][key];service['environment'][key]='f'*len(before)
                row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]
                with self.subTest(role=role,key=key),self.assertRaisesRegex(RuntimeError,'exact_maintenance_authority_changed'):
                    m.validate_model(self.contract,self.model,self.runtime,phase='provisional')
                service['environment'][key]=before
                row['Config']['Env']=['PATH=/fixture',*(k+'='+v for k,v in service['environment'].items())]

    def test_preparation_validation_does_not_allow_sealing_without_existing_fresh_authority(self):
        from test_schema150_admission import deletion_contract
        contract=deletion_contract()
        with tempfile.TemporaryDirectory() as directory,patch.object(m.os,'geteuid',return_value=0),\
                patch.object(m,'require_fresh_authorization',side_effect=RuntimeError('independent_authority_missing')),\
                patch.object(m,'runtime_mutation_lock') as lock:
            with self.assertRaisesRegex(RuntimeError,'independent_authority_missing'):
                m.seal_candidate_stage(contract,source_guard=lambda:None,model_loader=Mock(),runtime=Mock(),
                    state_root=directory,admissions=Path(directory))
            self.assertEqual(list(Path(directory).iterdir()),[])
            lock.assert_not_called()

    def test_canonical_parser_cannot_be_redefined_as_a_consumer_in_the_approved_model(self):
        from test_schema160_release import reconciled_contract
        self.use_manual_contract(reconciled_contract(),preparation150=True)
        for row in self.rows.values():
            row['State']={'Running':False,'Restarting':False,'Status':'created'}
            for endpoint in row['NetworkSettings']['Networks'].values():endpoint.update(NetworkID='',IPAddress='',EndpointID='')
        service=self.model['services']['parser-worker'];row=self.rows[self.selected['containers']['parser-worker']]
        service['environment']['SUPABASE_SERVICE_KEY']='synthetic-forbidden'
        row['Config']['Env'].append('SUPABASE_SERVICE_KEY=synthetic-forbidden')
        with self.assertRaisesRegex(RuntimeError,'private_parser_configuration_invalid'):
            m.validate_model(self.contract,self.model,self.runtime,phase='provisional')

    def test_canonical_parser_requires_internal_network_even_if_model_and_daemon_agree_on_egress(self):
        from test_schema160_release import reconciled_contract
        self.use_manual_contract(reconciled_contract(),preparation150=True)
        self.model['networks']['parser_internal']['internal']=False
        original=self.runtime.command
        def command(args):
            result=original(args)
            if args[:3]==['docker','network','inspect'] and args[3]==self.selected['networks']['parser']:
                values=json.loads(result);values[0]['Internal']=False;return json.dumps(values)
            return result
        self.runtime.command=command
        with self.assertRaisesRegex(RuntimeError,'private_parser_network_invalid'):
            m.validate_model(self.contract,self.model,self.runtime,phase='provisional')

    def test_exact160_normal_seal_requires_handoff_and_retains_accepted_container_ids(self):
        """Actual model comparison/publication; authority and ownership modeled."""
        from test_schema160_release import reconciled_contract
        from deployment.lib.completed_normal_profile import RECONCILED
        from deployment.lib import completed_normal_admission as admission
        self.use_manual_contract(reconciled_contract(),preparation150=True)
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);context=root/digest(self.contract);context.mkdir()
            original=root/'original.json';original.write_text(json.dumps({'runtimes':{k:{'id':str(i)*64}
                for i,k in enumerate(m.BUSINESS,1)}}))
            stack.enter_context(patch.object(m,'profile',return_value=RECONCILED))
            stack.enter_context(patch.object(admission,'profile',return_value=RECONCILED))
            stack.enter_context(patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED))
            stack.enter_context(patch.object(m.os,'geteuid',return_value=0))
            stack.enter_context(patch.object(m,'require_fresh_authorization'))
            grant=stack.enter_context(patch.object(admission,'require_candidate_authority',return_value={'mode':'NORMAL'}))
            witness=stack.enter_context(patch.object(admission,'require_maintenance_handoff'))
            stack.enter_context(patch.object(m,'protected',side_effect=lambda p,**kw:
                original if Path(p).name=='candidate-runtime.json' and Path(p).parent!=context else Path(p)))
            stack.enter_context(patch.object(m,'load_worker_authority',return_value={'generation':'a'*64}))
            owner=stack.enter_context(patch.object(m,'verify_runtime_binding'))
            runtimes,networks=m.validate_model(self.contract,self.model,self.runtime)
            stage=context/'candidate-staged-runtime.json';stage.write_text(json.dumps({'runtimes':runtimes}))
            row=self.rows[self.selected['containers']['backend']];saved=row['Id'];row['Id']='f'*64
            with self.assertRaisesRegex(RuntimeError,'private_candidate_substituted'):
                m.seal_candidate_runtime(self.contract,source_guard=lambda:None,model_loader=lambda:self.model,
                    runtime=self.runtime,state_root=root,admissions=root,mode='NORMAL')
            owner.assert_not_called();self.assertFalse((context/'candidate-runtime.json').exists())
            row['Id']=saved
            result=m.seal_candidate_runtime(self.contract,source_guard=lambda:None,model_loader=lambda:self.model,
                runtime=self.runtime,state_root=root,admissions=root,mode='NORMAL')
            self.assertEqual(result['runtimes'],runtimes);self.assertEqual(result['networks'],networks)
            self.assertEqual(json.loads((context/'candidate-runtime.json').read_bytes()),result)
            witness.assert_called_with(self.contract,admissions=root)
            self.assertTrue(all(c.kwargs.get('mode')=='NORMAL' for c in grant.call_args_list))

    def test_historical_profile_cannot_opt_into_maintenance_normal_sealing(self):
        with patch.object(m.os,'geteuid',return_value=0):
            with self.assertRaisesRegex(RuntimeError,'sealing_mode_invalid'):
                m.seal_candidate_runtime(self.contract,source_guard=lambda:None,model_loader=Mock(),runtime=Mock(),
                    state_root=Path('/never-used'),mode='NORMAL')

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
