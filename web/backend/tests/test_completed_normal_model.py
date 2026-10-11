"""Only measured configuration can influence the privileged Compose renderer."""
import os
from pathlib import Path
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
import base64
from unittest.mock import patch

from deployment.lib import completed_normal_model as m


class AcceptedApplicationPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repository';self.repo.mkdir()
        self.relative=('web/docker-compose.yml','web/precutover/docker-compose.supabase-client.yml')
        for relative in self.relative:
            path=self.repo/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('services: {}\n')
        self.git('init','-q');self.git('add','.');self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','accepted fixture')
        self.sha=self.git('rev-parse','HEAD');self.commands=[]
        def root_git(label,*args,cwd=None):
            self.commands.append(args)
            return SimpleNamespace(stdout=self.git(*args))
        self.actor=SimpleNamespace(package=self.root/'package',contract={'candidate':{'source_sha':self.sha}},
            ops=SimpleNamespace(state_root=self.root/'state',repo=self.repo,root_git=root_git))
        for root in (self.actor.package/'source',self.actor.ops.state_root/'releases'/self.sha):
            for relative in self.relative:
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((self.repo/relative).read_bytes())
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.repo,check=True,capture_output=True,text=True).stdout.strip()
    def test_preflight_uses_frozen_matching_inputs_without_creating_release(self):
        import shutil
        shutil.rmtree(self.actor.ops.state_root)
        self.assertEqual(m.candidate_release_root(self.actor,read_only=True),self.actor.package/'source')
        self.assertFalse(self.actor.ops.state_root.exists())
        self.assertTrue(all(args[0]=='rev-parse' for args in self.commands))
    def test_actual_stage_uses_the_deployment_worktree_location(self):
        self.assertEqual(m.candidate_release_root(self.actor,read_only=False),self.actor.ops.state_root/'releases'/self.sha)
    def source_objects(self):
        rows=[]
        for expression in (self.sha,self.sha+'^{tree}',self.sha+':web',self.sha+':web/precutover'):
            oid=self.git('rev-parse',expression);kind=self.git('cat-file','-t',oid)
            body=subprocess.run(['git','cat-file',kind,oid],cwd=self.repo,check=True,capture_output=True).stdout
            rows.append({'oid':oid,'kind':kind,'body_base64':base64.b64encode(body).decode()})
        return rows
    def test_read_only_preflight_proves_real_git_objects_without_production_fetch(self):
        objects=self.source_objects();self.actor.document={'application_source_objects':objects}
        original=self.actor.ops.root_git;self.actor.ops.root_git=lambda *a,**kw:self.fail('production Git lookup attempted')
        self.assertEqual(m.candidate_release_root(self.actor,read_only=True),self.actor.package/'source')
        self.actor.ops.root_git=original
        self.assertEqual(m.candidate_release_root(self.actor,read_only=False),self.actor.ops.state_root/'releases'/self.sha)
    def test_source_object_corruption_wrong_commit_or_changed_staging_rejects(self):
        objects=self.source_objects();self.actor.document={'application_source_objects':objects}
        wrong=[dict(row) for row in objects];wrong[0]['body_base64']=base64.b64encode(b'fabricated commit').decode()
        with self.assertRaisesRegex(RuntimeError,'objects_invalid'):m.accepted_compose_blobs(self.sha,wrong)
        with self.assertRaisesRegex(RuntimeError,'objects_invalid'):m.accepted_compose_blobs('f'*40,objects)
        with self.assertRaisesRegex(RuntimeError,'objects_invalid'):m.accepted_compose_blobs(self.sha,objects+[objects[0]])
        self.actor.ops.root_git=lambda *a,**kw:SimpleNamespace(stdout='f'*40)
        with self.assertRaisesRegex(RuntimeError,'staged_object_changed'):m.candidate_release_root(self.actor,read_only=False)
    def test_changed_application_input_or_missing_stage_fails(self):
        path=self.actor.package/'source'/self.relative[0];path.write_text('services: {unexpected: {}}\n')
        with self.assertRaisesRegex(RuntimeError,'input_changed'):m.candidate_release_root(self.actor,read_only=True)
        (self.actor.ops.state_root/'releases'/self.sha/self.relative[1]).unlink()
        with self.assertRaisesRegex(RuntimeError,'input_missing'):m.candidate_release_root(self.actor,read_only=False)


class ModelEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths=Path(self.temp.name)/'paths';self.config=Path(self.temp.name)/'production'
        self.paths.write_text('MADAR_RELEASE_STATE_ROOT=/private/releases\n')
        self.config.write_text('SUPABASE_URL=http://private-native:8000\n')
        self.config.chmod(0o600)
        p=patch.object(m,'readonly_configuration',lambda p,**kw:p);p.start();self.addCleanup(p.stop)

    def test_child_loader_environment_is_sanitized_and_restored(self):
        with patch.dict(os.environ,{'PYTHONPATH':'untrusted','DOCKER_HOST':'untrusted','CREDENTIALS_DIRECTORY':'/run/private-fixture'}):
            before=dict(os.environ)
            with m.measured_environment(self.paths,self.config):
                self.assertNotIn('PYTHONPATH',os.environ);self.assertNotIn('DOCKER_HOST',os.environ)
                self.assertEqual(os.environ['CREDENTIALS_DIRECTORY'],'/run/private-fixture')
                self.assertEqual(os.environ['SUPABASE_URL'],'http://private-native:8000')
            self.assertEqual(dict(os.environ),before)

    def test_configuration_cannot_select_code_socket_git_or_credential_directory(self):
        for key in ('LD_PRELOAD','PYTHONPATH','DOCKER_HOST','GIT_CONFIG','PATH','HOME','BASH_ENV','CREDENTIALS_DIRECTORY'):
            with self.subTest(key=key):
                self.config.write_text(key+'=fixture-untrusted\n');before=dict(os.environ)
                with self.assertRaisesRegex(RuntimeError,'environment_invalid'):
                    with m.measured_environment(self.paths,self.config):self.fail('untrusted loader entered')
                self.assertEqual(dict(os.environ),before)

    def test_render_failure_restores_parent_environment(self):
        before=dict(os.environ)
        with self.assertRaisesRegex(RuntimeError,'fixture_failure'):
            with m.measured_environment(self.paths,self.config):raise RuntimeError('fixture_failure')
        self.assertEqual(dict(os.environ),before)

if __name__=='__main__':unittest.main()
