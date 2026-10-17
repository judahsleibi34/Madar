import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import independent_recovery as recovery

class IndependentRecoverySafetyTests(unittest.TestCase):
    def test_ports_private_mounts_and_limits_are_separate(self):
        original=(WEB/'staging/integration/compose.yaml').read_text()
        rendered=recovery.render_compose(original,Path('/owned/source'),Path('/owned/dist'))
        self.assertNotIn(':18080',rendered);self.assertNotIn(':18443',rendered);self.assertNotIn(':18081',rendered)
        self.assertIn('127.0.0.1:19080:8080',rendered);self.assertIn('127.0.0.1:19081:8081',rendered)
        self.assertIn('/owned/dist:/site:ro',rendered)
        self.assertIn('mem_limit: 512m',rendered);self.assertIn('mem_limit: 768m',rendered)
        self.assertIn('internal: true',rendered)
    def test_existing_or_nonhome_runtime_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError,'Preserve existing'):
                recovery.prepare_target(Path(directory),{'project':'fixture'},Path('/unused'),Path('/unused'))
    def test_context_restores_original_identities_even_on_failure(self):
        original=(recovery.manage.PROJECT,recovery.manage.RUNTIME,recovery.manage.MARKER,recovery.smoke.PROVIDER)
        with self.assertRaises(RuntimeError):
            with recovery.target_context(Path('/tmp/owned-test')):
                self.assertEqual(recovery.manage.PROJECT,recovery.TARGET_PROJECT)
                self.assertEqual(recovery.smoke.application_origin(),'http://127.0.0.1:19080')
                self.assertNotEqual(recovery.manage.MARKER,original[2])
                raise RuntimeError('synthetic')
        self.assertEqual((recovery.manage.PROJECT,recovery.manage.RUNTIME,recovery.manage.MARKER,recovery.smoke.PROVIDER),original)
    def test_rehearsal_rejects_primary_before_any_source_stop(self):
        with patch.object(recovery.manage.socket,'gethostname',return_value='madar-gpu'),patch.object(recovery.manage,'compose') as compose:
            with self.assertRaises(RuntimeError):recovery.main('REHEARSE')
            compose.assert_not_called()
