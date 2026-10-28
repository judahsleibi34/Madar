"""Critical candidate privilege boundaries; these are not deployment receipts."""
import copy,unittest
from pathlib import Path
from deployment.lib.automatic_release_execution import (
    ROLES,LIMITS_MIB,validate_candidate_model,grant_directory)
from test_automatic_release_admission import sample


class TrafficDriverPreflightTests(unittest.TestCase):
    def check(self,*,owner=1000,mode=0o100644,links=1,docker_exit=0,running='true\n'):
        from types import SimpleNamespace
        from unittest.mock import patch
        from deployment.lib.automatic_release_execution import verify_traffic_driver_access
        metadata=SimpleNamespace(st_uid=owner,st_mode=mode,st_nlink=links)
        parent=SimpleNamespace(st_uid=1000,st_mode=0o40755)
        with patch('pwd.getpwnam',return_value=SimpleNamespace(pw_uid=1000)),\
                patch.object(Path,'lstat',side_effect=[metadata,parent]),\
                patch('deployment.lib.automatic_release_execution.subprocess.run',
                    return_value=SimpleNamespace(returncode=docker_exit,stdout=running)) as run:
            try:verify_traffic_driver_access()
            finally:self.last_probe=run.call_args

    def test_canonical_child_identity_and_daemon_are_probed_without_mutation(self):
        self.check()
        command=self.last_probe.args[0]
        self.assertEqual(command[:5],['/usr/sbin/runuser','-u','madar','--','/usr/bin/docker'])
        self.assertIn('unix:///var/run/docker.sock',command)
        self.assertEqual(command[-1],'madar-release-proxy')
        self.assertEqual(self.last_probe.kwargs['timeout'],5)

    def test_root_daemon_access_cannot_substitute_for_denied_or_stopped_child_proxy(self):
        for change in ({'docker_exit':1},{'running':'false\n'}):
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'driver_unavailable'):
                self.check(**change)

    def test_foreign_owner_symlink_shared_inode_or_unsafe_mode_refuses_before_probe(self):
        for change in ({'owner':0},{'mode':0o120777},{'links':2},{'mode':0o100666}):
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'permissions_invalid'):
                self.check(**change)
            self.assertIsNone(self.last_probe)


class CandidatePrivilegesTests(unittest.TestCase):
    def setUp(self):
        self.value=sample();self.source=Path('/var/lib/madar/releases/releases')/self.value['source_sha']
        images=self.value['candidate']['images']
        self.model={'services':{r:{'container_name':'madar-green-'+r,'read_only':True,
            'restart':'no','mem_limit':LIMITS_MIB[r]*1024**2,'cpus':.5,'pids_limit':128,
            'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
            'image':('redis@sha256:'+'c'*64 if r=='redis' else images['frontend' if r=='frontend' else 'backend'].split('@',1)[1])}
            for r in ROLES}}
        self.model['services']['backend']['volumes']=[{'type':'bind','source':str(self.source/'web/database'),
            'target':'/app/database','read_only':True},{'type':'bind','source':str(grant_directory(self.value)),
            'target':'/run/madar/business-write-authority','read_only':True}]

    def test_source_and_authority_inputs_are_read_only(self):
        validate_candidate_model(self.model,self.value,self.source)
        for role,row in self.model['services'].items():row['mem_limit']=str(LIMITS_MIB[role]*1024**2)
        validate_candidate_model(self.model,self.value,self.source) # native Compose JSON uses decimal strings
        self.model['services']['backend']['volumes'][0]['read_only']=False
        with self.assertRaisesRegex(RuntimeError,'control_mount_writable'):
            validate_candidate_model(self.model,self.value,self.source)

    def test_docker_socket_root_credential_and_foreign_mounts_refuse(self):
        for path in ('/var/run/docker.sock','/etc/madar/automatic-database.dsn','/srv/madar/production/.git','/root'):
            self.model['services']['backend']['volumes'][0]['source']=path
            with self.subTest(path=path),self.assertRaisesRegex(RuntimeError,'host_mount_not_admitted'):
                validate_candidate_model(self.model,self.value,self.source)

    def test_elevated_runtime_unbounded_resources_or_mutable_images_refuse(self):
        for patch in ({'privileged':True},{'network_mode':'host'},{'pid':'host'},
                {'devices':['/dev/kvm']},{'cap_add':['SYS_ADMIN']},{'mem_limit':0},
                {'pids_limit':-1},{'cpus':99},{'read_only':False},{'image':'backend:latest'},
                {'cap_drop':[]},{'security_opt':[]}):
            model=copy.deepcopy(self.model);model['services']['backend'].update(patch)
            with self.subTest(patch=patch),self.assertRaises(RuntimeError):validate_candidate_model(model,self.value,self.source)

    def test_extra_actor_or_public_port_refuse(self):
        model=copy.deepcopy(self.model);model['services']['unexpected-writer']=model['services']['backend']
        with self.assertRaisesRegex(RuntimeError,'roles_changed'):validate_candidate_model(model,self.value,self.source)
        self.model['services']['backend']['ports']=[{'host_ip':'0.0.0.0','published':'80','target':8000}]
        with self.assertRaisesRegex(RuntimeError,'public_port_refused'):validate_candidate_model(self.model,self.value,self.source)


class SourceCheckGitIndexTests(unittest.TestCase):
    def test_linked_worktree_index_without_repository_metadata(self):
        import os,subprocess,tempfile
        from deployment.lib.automatic_release_execution import source_check_git_index
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);repo=base/'repo';repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            (repo/'tracked.txt').write_text('public source')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            environment=dict(os.environ,GIT_AUTHOR_NAME='fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',
                GIT_COMMITTER_NAME='fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid')
            subprocess.run(['git','-C',str(repo),'commit','-qm','fixture'],check=True,env=environment)
            sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip()
            worktree=base/'worktree'
            subprocess.run(['git','-C',str(repo),'worktree','add','--detach','-q',str(worktree),sha],check=True)
            index=base/'index';index.mkdir()
            source_check_git_index(index,repo,sha)
            self.assertEqual(set(p.name for p in index.iterdir()),{'HEAD','config','index','objects','refs'})
            self.assertEqual(list((index/'objects').iterdir()),[])
            result=subprocess.check_output(['git','ls-files','-z'],cwd=worktree,
                env=dict(os.environ,GIT_DIR=str(index),GIT_WORK_TREE=str(worktree)))
            self.assertEqual(result,b'tracked.txt\0')
            self.assertEqual((index/'index').stat().st_mode&0o777,0o444)
            with self.assertRaisesRegex(RuntimeError,'source_invalid'):
                source_check_git_index(index,repo,'HEAD')


class SealedOriginRestoreTests(unittest.TestCase):
    def adapter(self):
        import json,tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from deployment.lib.automatic_release_execution import operations_adapter
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        policy=Path(temporary.name)/'policy.json'
        scope={role:{'name':'/madar-blue-'+role} for role in ROLES}
        policy.write_text(json.dumps({'runtime_scope':scope}))
        class Base:
            def __init__(self,*args):self.state_root=Path(temporary.name);self.commands=[]
            def restore_workers(self,*args):raise AssertionError('historical restart-policy mutation forbidden')
            def run(self,command,**kwargs):self.commands.append(command);return ''
            def _require_worker_authority(self,sha,slot):
                if (sha,slot)!=('b'*40,'blue'):raise RuntimeError('wrong old owner')
            def _require_other_worker_slot_inactive(self,slot):pass
        value=sample()
        with patch('deployment.lib.automatic_release_execution.protected',return_value=policy):
            instance=operations_adapter(Base,SimpleNamespace(repo=Path(temporary.name),state_root=Path(temporary.name)),value)
        instance._origin_fenced=['backend','parser-worker','remote-ingestion-worker']
        instance.guard=lambda:None
        instance.verify_actor_scope=lambda:[{'Id':role,'State':{'Running':True,'Health':{'Status':'healthy'}}} for role in ROLES]
        return instance,value

    def test_recovery_revokes_target_and_starts_only_exact_old_ids_without_configuration_changes(self):
        from unittest.mock import patch
        instance,value=self.adapter();release={'sha':value['origin']['source_sha'],'slot':'blue','images':dict(value['origin']['images'],artifact_reused=True)}
        with patch('deployment.lib.automatic_release_execution.publish_candidate_grant') as grant:
            instance.restore_workers(release)
            self.assertEqual(grant.call_args.args[1],'READ_ONLY')
            self.assertEqual(grant.call_count,1)
        self.assertEqual(instance.commands,[
            ['/usr/bin/docker','start','parser-worker','remote-ingestion-worker','backend'],
            ['/usr/bin/docker','start','notification-worker','calendar-sync-worker','data-deletion-worker']])

    def test_substituted_source_slot_image_or_foreign_origin_id_refuses(self):
        from unittest.mock import patch
        for change in ({'sha':'e'*40},{'slot':'green'},{'images':dict(sample()['origin']['images'],backend='foreign')}):
            instance,value=self.adapter();release=dict(sha=value['origin']['source_sha'],slot='blue',images=value['origin']['images']);release.update(change)
            with patch('deployment.lib.automatic_release_execution.publish_candidate_grant') as grant,self.assertRaisesRegex(RuntimeError,'origin_substituted'):
                instance.restore_workers(release)
            grant.assert_not_called();self.assertEqual(instance.commands,[])
        instance,value=self.adapter();instance._origin_fenced=['foreign-id']
        with patch('deployment.lib.automatic_release_execution.publish_candidate_grant'),self.assertRaisesRegex(RuntimeError,'inventory_incomplete'):
            instance.restore_workers(dict(sha=value['origin']['source_sha'],slot='blue',images=value['origin']['images']))
        self.assertEqual(instance.commands,[])


class ExceptionalCompletionPublicationTests(unittest.TestCase):
    def test_verified_inventory_precedes_policy_observation_and_completion_receipt(self):
        import os,tempfile
        from types import SimpleNamespace
        from unittest.mock import patch,MagicMock
        from deployment.lib import automatic_release_execution as e
        from deployment.lib import exceptional_release_approval as approval
        from deployment.lib import automatic_release_recovery as recovery
        from deployment.lib import runtime_authority
        events=[];v=sample();v['exceptional']={'request_id':'model-request'}
        adapter=SimpleNamespace(_credential_root=None,compatibility=None,
            accept_runtime_inventory=lambda:events.append('inventory'))
        def event(*args):
            self.assertIn('inventory',events);events.append(args[2])
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ):
            root=Path(tmp);system=SimpleNamespace(upgrade_root=root,state_root=root,
                clear_authorization=MagicMock(),clear_interlock=MagicMock())
            with patch.object(e.os,'geteuid',return_value=0),patch.object(e.admission,'sealed'),patch.object(e.admission,'ROOT',root),patch.object(e.admission,'finish_operation'),patch.object(e,'acquire_lock',side_effect=lambda *args,**kw:os.open(root/'lock',os.O_CREAT|os.O_RDWR,0o600)),patch.object(e,'operations_adapter',return_value=adapter),patch.object(e,'ReleaseDeployer') as deployer,patch.object(e,'atomic_json',side_effect=lambda *args,**kw:events.append('receipt')),patch.object(approval,'execution_event',side_effect=event),patch.object(recovery,'seal_known_good',side_effect=lambda *args:events.append('seal')),patch.object(runtime_authority,'open_deployment_lock',side_effect=lambda *_:tempfile.TemporaryFile()):
                deployer.return_value.deploy.return_value={'status':'known_good'}
                e.execute(system,v,object)
        self.assertEqual(events,['inventory','VERIFYING','receipt','COMPLETED','seal'])


class FencedOriginRouteTests(unittest.TestCase):
    def probe(self,*,slot='blue',port=8101,frontend=b'accepted immutable frontend',status=502,running=False,log=True):
        import hashlib,io
        from types import SimpleNamespace
        from unittest.mock import patch
        from deployment.lib.automatic_release_execution import observe_fenced_origin_route
        nonce='11111111-1111-4111-8111-111111111111'
        path='/health/version?madar_maintenance_probe='+nonce
        rows=[{'Id':role,'Name':'/madar-blue-'+role,'State':{'Running':role in {'frontend','redis'} or running}} for role in ROLES]
        rows.append({'Id':'sealed-proxy','Name':'/madar-release-proxy','State':{'Running':True}})
        class Response(io.BytesIO):
            code=200
        def open_response(request,timeout):
            response=Response(frontend)
            if 'health/version' in request.full_url:response.code=status
            return response
        def docker(command,**kw):
            self.command=command
            if log:kw['stdout'].write(('connect() failed (111: Connection refused), request: "GET '+path+' HTTP/1.1", upstream: "http://127.0.0.1:'+str(port)+path+'"\n').encode())
            return SimpleNamespace(returncode=0)
        with patch('uuid.uuid4',return_value=nonce),patch('urllib.request.build_opener',return_value=SimpleNamespace(open=open_response)),patch('deployment.lib.automatic_release_execution.subprocess.run',side_effect=docker):
            return observe_fenced_origin_route(rows,slot,lambda *a,**kw:hashlib.sha256(b'accepted immutable frontend').hexdigest()+'  index.html')

    def test_loaded_fenced_backend_and_immutable_frontend_observed(self):
        self.assertEqual(self.probe(),'blue')
        self.assertEqual(self.command[-1],'sealed-proxy')
        self.assertIn('--since',self.command)

    def test_wrong_loaded_upstream_missing_nonce_unfenced_backend_or_foreign_frontend_refuses(self):
        for change in ({'port':8201},{'log':False},{'status':200},{'running':True},{'frontend':b'foreign'}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):self.probe(**change)
