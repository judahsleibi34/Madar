"""Critical candidate privilege boundaries; these are not deployment receipts."""
import copy,unittest
from pathlib import Path
from deployment.lib.automatic_release_execution import (
    ROLES,LIMITS_MIB,validate_candidate_model,grant_directory)
from test_automatic_release_admission import sample


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
