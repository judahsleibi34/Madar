import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import fresh_artifact_acceptance as acceptance


class FreshArtifactAcceptanceSafetyTests(unittest.TestCase):
    def test_primary_host_cannot_load_images_or_stop_services(self):
        with patch.object(acceptance.manage.socket,'gethostname',return_value='madar-gpu'), \
                patch.object(acceptance.manage,'docker') as docker,patch.object(acceptance.manage,'compose') as compose:
            with self.assertRaises(RuntimeError):
                acceptance.main(Path.home()/'unused-artifact-scope','a'*40,3,'REHEARSE')
            docker.assert_not_called();compose.assert_not_called()

    def test_ambiguous_scope_or_source_fails_before_resource_inspection(self):
        for path,source in ((Path('/tmp/unknown'),'a'*40),(Path.home()/'unused','development')):
            with patch.object(acceptance.manage,'require_staging_host'),patch.object(acceptance.manage,'state') as state:
                with self.subTest(path=str(path)),self.assertRaises(RuntimeError):
                    acceptance.main(path,source,3,'INSPECT')
                state.assert_not_called()

    def test_explicit_resume_cannot_adopt_a_different_selected_source(self):
        with patch.object(acceptance.manage,'require_staging_host'), \
                patch.object(acceptance.manage,'state',return_value={'source_sha':'b'*40}), \
                patch.object(acceptance.manage,'attest_resources'),patch.object(acceptance.manage,'require_database_marker'), \
                patch.object(acceptance.manage,'compose') as compose:
            with self.assertRaisesRegex(RuntimeError,'already selected exact'):
                acceptance.main(Path.home()/'unused-artifact-scope','a'*40,3,'REHEARSE',resume=True)
            compose.assert_not_called()
