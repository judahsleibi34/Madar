"""Target refresh stays fenced until the separate root136 grant."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_completed_normal_compose import cli
from test_completed_normal_admission import fixture_contract

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.state={'active_slot':'green','known_good_release':{'sha':'c'*40,'slot':'green','schema':115,'images':{}}}
        (self.root/'state.json').write_text(json.dumps(self.state))
        self.ops=SimpleNamespace(compatibility=cli.Compatibility(115,136,136,'forward-compatible',115,115),
            schema_version=lambda:136,verify_source=Mock(),preflight=Mock(),validate_active_refresh_prerequisites=Mock(),
            refresh_active_runtime_services=Mock(),validate_candidate=Mock(),validate_stable_candidate=Mock(),
            validate_completed_normal_read_only_serving=Mock(),completed_normal_admission=fixture_contract())
    def test_admitted_refresh_does_not_require_normal_consumption_before_root_grant(self):
        result=cli.refresh_active_workers(sha='c'*40,slot='green',state_root=self.root,operations=self.ops)
        self.ops.validate_completed_normal_read_only_serving.assert_called_once_with('c'*40,'green')
        self.ops.validate_candidate.assert_not_called();self.ops.validate_stable_candidate.assert_not_called()
        self.assertEqual(result['schema']['observed'],136)
        self.assertEqual(json.loads((self.root/'state.json').read_text())['known_good_release']['schema'],136)
    def test_ordinary_refresh_retains_full_normal_readiness_requirements(self):
        self.ops.completed_normal_admission=None
        cli.refresh_active_workers(sha='c'*40,slot='green',state_root=self.root,operations=self.ops)
        self.ops.validate_candidate.assert_called_once_with('c'*40,'green')
        self.ops.validate_stable_candidate.assert_called_once_with('c'*40)
        self.ops.validate_completed_normal_read_only_serving.assert_not_called()
    def test_failed_fence_or_runtime_check_preserves_prior_observed_schema(self):
        self.ops.validate_completed_normal_read_only_serving.side_effect=RuntimeError('modified_identity')
        with self.assertRaises(RuntimeError):cli.refresh_active_workers(sha='c'*40,slot='green',state_root=self.root,operations=self.ops)
        self.assertEqual(json.loads((self.root/'state.json').read_text()),self.state)

if __name__=='__main__':unittest.main()
