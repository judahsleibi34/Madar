"""Only measured configuration can influence the privileged Compose renderer."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.lib import completed_normal_model as m


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
