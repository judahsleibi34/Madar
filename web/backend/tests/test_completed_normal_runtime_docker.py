"""Real Compose serialization on a PRIVATE daemon; idle runtime, not app acceptance.

The original Compose merge is rendered, then private paths and idle commands
replace all application/customer I/O. No production socket, data, mount or
listener is used. This proves the independent model checker handles actual
Docker/Compose fields; it does not claim the full database/controller rehearsal.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from test_completed_normal_compose import CompletedNormalComposeTests
from deployment.lib import completed_normal_runtime as runtime_module
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_resources import allocation

@unittest.skipUnless(os.getenv('MADAR_REAL_DOCKER_TESTS')=='1','private real Docker fixture opt-in required')
class PrivateComposeRuntimeTests(CompletedNormalComposeTests):
    # Do not rerun inherited render-only cases inside this separate real fixture.
    test_actual_environment_always_carries_root_fence_for_candidate_and_workers=None
    test_changed_context_rejected_before_any_compose_command=None
    test_modified_image_and_wrong_slot_fail_before_staging=None
    test_missing_or_modified_grant_rejected_before_staging=None
    test_real_compose_merge_keeps_security_and_root_mount_on_all_business_roles=None
    test_bridge_uses_current_backup_state_mount_instead_of_legacy_provider_marker=None
    def command(self,*args):
        result=subprocess.run(['docker','--host',self.endpoint,*args],capture_output=True,text=True,timeout=180)
        if result.returncode:raise RuntimeError('private_compose_operation_failed_'+args[0])
        return result.stdout.strip()
    def setUp(self):
        self.endpoint=os.getenv('MADAR_DOCKER_FIXTURE_ENDPOINT','')
        if not self.endpoint.startswith('unix:///tmp/madar-schema136-private-'):
            raise RuntimeError('private_compose_daemon_required')
        # Check the actual socket's engine identity, not merely caller env.
        root=self.command('info','--format','{{.DockerRootDir}}')
        if not root.startswith('/opt/madar-development/repository/.incident-response/schema136-execution-gates/private-deployment-'):
            raise RuntimeError('private_compose_daemon_identity_invalid')
        super().setUp()
        import uuid
        self.contract['rehearsal_sha256']=uuid.uuid4().hex*2
        source='81cebfeb024341cd8d784402ba1f92ed2e63fb3d'
        backend='sha256:12f513c1adfa36032098667ef9941bd03f7db49d25ffd3bbd1557e3456cbf16a'
        frontend='sha256:1513fa7545f272d4cc975ccae2cc2fda74abb5e8ea001ae5fe50ebf839782e12'
        self.contract['candidate'].update(source_sha=source,images={'backend':backend,'frontend':frontend},redis_image=backend)
        self.images.update(backend='madar-backend:'+source+'@'+backend,worker='madar-backend:'+source+'@'+backend,
            frontend='madar-frontend:'+source+'-production@'+frontend)
        selected=allocation(self.contract,'green');self.project=selected['project']
        def render(args,**kwargs):
            result=subprocess.run(args,capture_output=True,text=True,timeout=30,**kwargs)
            if result.returncode:raise RuntimeError('private_source_compose_render_failed')
            self.model=json.loads(result.stdout);return result.stdout
        self.ops.run=render
        self.ops._compose(source,'green',self.images,'config','--format','json',workers_active=True)
        # Rehearsal-only substitutions. No protected record is issued here.
        self.authorities=Path(self.temp.name)/'authorities'
        authority=self.authorities/digest(self.contract)/'write-authority';authority.mkdir(parents=True)
        (authority/'authority.json').write_text('{}')
        p=patch.object(runtime_module,'ADMISSIONS',self.authorities);p.start();self.addCleanup(p.stop)
        for role,service in self.model['services'].items():
            service.pop('build',None);service['entrypoint']=['/bin/sh'];service['command']=['-c','sleep 600']
            service['healthcheck']={'test':['CMD','/bin/sh','-c','exit 0'],'interval':'200ms','timeout':'1s','retries':3}
            if role=='redis':service['image']=self.images['backend']
            for index,volume in enumerate(service.get('volumes',[])):
                if volume['target']=='/run/madar/business-write-authority':volume['source']=str(authority)
                else:
                    directory=Path(self.temp.name)/('mount-'+role+'-'+str(index));directory.mkdir()
                    volume['source']=str(directory)
            service.setdefault('environment',{}).update(MADAR_RELEASE_SHA=source)
        # Actual kernel has no host egress. All candidate networks are internal
        # in this idle fixture; accepted deployment policy is tested separately.
        for declaration in self.model['networks'].values():declaration['internal']=True
        self.model['name']=self.project
        self.model_file=Path(self.temp.name)/'private-compose.json';self.model_file.write_text(json.dumps(self.model))
        self.addCleanup(self.stop_fixture)
        self.command('compose','--project-name',self.project,'-f',str(self.model_file),'--profile','workers',
            '--profile','deletion-worker','up','-d','--no-build','--pull','never','--wait','--wait-timeout','60')
        fixture=self
        class Runtime:
            def command(_,args):return fixture.command(*args[1:])
            def inspect(_,names):return {r['Name'].lstrip('/'):r for r in json.loads(fixture.command('inspect',*names))}
        self.runtime=Runtime()
    def stop_fixture(self):
        self.command('compose','--project-name',self.project,'-f',str(self.model_file),'--profile','workers',
            '--profile','deletion-worker','down','--timeout','1')
    def test_actual_rendered_config_matches_running_docker_security_and_images(self):
        bindings,networks=runtime_module.validate_model(self.contract,self.model,self.runtime)
        self.assertEqual(len(bindings),8);self.assertEqual(len(networks),4)
        self.assertEqual(bindings['backend']['image'],self.contract['candidate']['images']['backend'])
    def test_actual_running_configuration_does_not_accept_modified_model(self):
        changed=copy.deepcopy(self.model);changed['services']['backend']['environment']['MADAR_RELEASE_SHA']='0'*40
        with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
            runtime_module.validate_model(self.contract,changed,self.runtime)
    def test_real_created_standbys_and_exact_started_attachments(self):
        selected=allocation(self.contract,'green')
        names=[selected['containers'][role] for role in runtime_module.BUSINESS]
        # Only this nonce-scoped idle fixture's three workers are replaced.
        ids=[row['Id'] for row in self.runtime.inspect(names).values()]
        self.command('stop','--timeout','1',*ids);self.command('rm',*ids)
        compose=['compose','--project-name',self.project,'-f',str(self.model_file),
            '--profile','workers','--profile','deletion-worker']
        self.command(*compose,'create','--no-build','--pull','never',*runtime_module.BUSINESS)
        rows=self.runtime.inspect(names)
        self.assertTrue(all(r['State']['Status']=='created' and not r['State']['Running'] for r in rows.values()))
        bindings,_=runtime_module.validate_model(self.contract,self.model,self.runtime,phase='staged')
        self.assertEqual(len(bindings),8)
        with self.assertRaisesRegex(RuntimeError,'not_running'):
            runtime_module.validate_model(self.contract,self.model,self.runtime)
        changed=copy.deepcopy(self.model)
        key=next(iter(changed['services']['notification-worker']['networks']))
        changed['services']['notification-worker']['networks'][key]={'aliases':['wrong']}
        with self.assertRaisesRegex(RuntimeError,'network_role_changed'):
            runtime_module.validate_model(self.contract,changed,self.runtime,phase='staged')
        # Exercise the actual governed child start path against this daemon.
        # Synthetic credentials remain fixture-only; actual image/spec/network
        # and singleton-owner validation are not mocked.
        from deployment.lib import completed_normal_admission as admission
        from deployment.lib import emergency_routing_repair
        from deployment.lib.runtime_authority import write_worker_authority
        origin=[]
        for index in range(3):
            cid=self.command('create','--name',self.project+'-origin-'+str(index),'--restart','no',
                '--network','none','--entrypoint','/bin/sh',self.images['backend'],'-c','sleep 600')
            origin.append(cid)
        self.addCleanup(lambda:self.command('rm','--force',*origin))
        generation='1'*64
        publication={'operation':admission.OPERATION,'context_sha256':digest(self.contract),
            'source_sha':self.contract['candidate']['source_sha'],'images':self.contract['candidate']['images'],
            'runtimes':bindings,'networks':runtime_module.validate_model(self.contract,self.model,self.runtime,phase='staged')[1],
            'worker_generation':generation,'origin_workers':origin}
        write_worker_authority(self.ops.state_root,generation=generation,owner='CANDIDATE',
            old={'sha':self.contract['source_roles']['application_sha'],'slot':'blue'},
            candidate={'sha':self.contract['candidate']['source_sha'],'slot':'green'})
        with patch.object(admission,'credential_witness',return_value=publication),\
                patch.object(emergency_routing_repair,'Runtime',return_value=self.runtime),\
                patch.object(self.ops,'_require_worker_authority'):
            self.ops.activate_workers(self.contract['candidate']['source_sha'],'green',self.images)
        self.assertEqual({r['Id'] for r in self.runtime.inspect(names).values()},
            {bindings[role]['id'] for role in runtime_module.BUSINESS})
        with self.assertRaisesRegex(RuntimeError,'standby_started'):
            runtime_module.validate_model(self.contract,self.model,self.runtime,phase='staged')
        import time
        deadline=time.monotonic()+15
        while True:
            states=self.runtime.inspect(names)
            if all(r['State'].get('Health',{}).get('Status')=='healthy' for r in states.values()):break
            if time.monotonic()>=deadline:self.fail('private idle worker health deadline expired')
            time.sleep(0.2)
        runtime_module.validate_model(self.contract,self.model,self.runtime)

if __name__=='__main__':unittest.main()
