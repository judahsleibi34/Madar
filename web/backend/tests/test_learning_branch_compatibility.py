"""The learning143 branch must never accept or advertise Exchange142."""
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from services.runtime_config import schema_excluded_versions
from services import readiness_service,elearning_settings_service
WEB_ROOT=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB_ROOT))
from deployment.lib.release_deployer import Compatibility

class LearningBranchCompatibilityTests(unittest.TestCase):
    def test_branch_exclusions_are_narrow_and_mandatory(self):
        with patch.dict(os.environ,{'SCHEMA_EXCLUDED_VERSIONS':'142'}):
            self.assertEqual(schema_excluded_versions(141,143),(142,))
            with self.assertRaises(ValueError):schema_excluded_versions(140,143)
        with patch.dict(os.environ,{'SCHEMA_EXCLUDED_VERSIONS':''}):
            with self.assertRaises(ValueError):schema_excluded_versions(141,143)
            self.assertEqual(schema_excluded_versions(143,143),())
        with patch.dict(os.environ,{'SCHEMA_EXCLUDED_VERSIONS':'140,142'}):
            with self.assertRaises(ValueError):schema_excluded_versions(141,143)

    def test_release_bridge_rejects142_and_unknown_gap_metadata(self):
        path=WEB_ROOT/'deployment/releases/schema-141-143-learning-bridge.json'
        compatibility=Compatibility.load(path)
        self.assertTrue(compatibility.accepts_schema(141));self.assertTrue(compatibility.accepts_schema(143));self.assertFalse(compatibility.accepts_schema(142))
        self.assertFalse(compatibility.accepts_schema(143,rollback=True))
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'release.json';raw=json.loads(path.read_text());raw['schema'].pop('excluded_versions');target.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,'exclude schema142'):Compatibility.load(target)

    def test_readiness_rejects_excluded_live_state(self):
        env={'SUPABASE_URL':'http://localhost:54321','SUPABASE_SERVICE_KEY':'synthetic','SCHEMA_COMPATIBLE_MIN':'141','SCHEMA_COMPATIBLE_MAX':'143','SCHEMA_EXCLUDED_VERSIONS':'142'}
        for version,expected in [(141,'ok'),(142,'incompatible'),(143,'ok')]:
            response=SimpleNamespace(status_code=200,json=lambda:[{'schema_version':version}])
            with patch.dict(os.environ,env),patch.object(readiness_service.requests,'get',return_value=response):self.assertEqual(readiness_service.check_schema(),expected)

    def test_numeric143_does_not_enable_exchange142(self):
        with patch.object(elearning_settings_service.service_supabase,'table') as table:
            table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data=[{'schema_version':143}]
            self.assertFalse(elearning_settings_service.settings_available(142))
            self.assertTrue(elearning_settings_service.settings_available(143))
            self.assertTrue(elearning_settings_service.settings_available(141))
