import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import schema149_image_acceptance as acceptance


class ImageAcceptanceSafetyTests(unittest.TestCase):
    def test_unknown_mode_or_mutable_source_rejects_before_host(self):
        for mode,source in (('EXECUTE','a'*40),('REHEARSE','main')):
            with patch.object(acceptance.manage,'require_staging_host') as host,self.assertRaises(RuntimeError):
                acceptance.inspect(mode,Path('/unused'),source)
            host.assert_not_called()

    def test_primary_host_refuses_before_any_configuration_database_or_image_effect(self):
        with patch.object(acceptance.manage.socket,'gethostname',return_value='madar-gpu'),patch.object(acceptance.manage,'state') as state,self.assertRaises(RuntimeError):
            acceptance.inspect('REHEARSE',Path('/unused'),'a'*40)
        state.assert_not_called()

    def test_unsupported_schema_refuses_before_artifact_or_service_mutation(self):
        with patch.object(acceptance.manage,'require_staging_host'),patch.object(acceptance.manage,'state',return_value={'source_sha':'b'*40}),patch.object(acceptance.manage,'attest_resources'),patch.object(acceptance.manage,'require_database_marker'),patch.object(acceptance.manage,'sql',return_value='148:2:1'),patch.object(acceptance.acceptance,'artifacts') as artifacts,self.assertRaises(RuntimeError):
            acceptance.inspect('REHEARSE',Path('/unused'),'a'*40)
        artifacts.assert_not_called()

    def test_inspect_authenticates_without_effects(self):
        with patch.object(acceptance.manage,'require_staging_host'),patch.object(acceptance.manage,'state',return_value={'source_sha':'b'*40}),patch.object(acceptance.manage,'attest_resources'),patch.object(acceptance.manage,'require_database_marker'),patch.object(acceptance.manage,'sql',return_value='149:2:2'),patch.object(acceptance.acceptance,'artifacts',return_value=({}, {}, {'backend':'image'},{})),patch.object(acceptance.manage,'compose') as compose,patch.object(acceptance.manage,'select_source') as select:
            result=acceptance.inspect('INSPECT',Path('/unused'),'a'*40)
        self.assertFalse(result['mutations_executed']);compose.assert_not_called();select.assert_not_called()
