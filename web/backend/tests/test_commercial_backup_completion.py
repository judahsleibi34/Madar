"""The backup-only continuation cannot repeat SQL or deployment effects."""
import ast
import importlib.util
import unittest
import tempfile
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_completed_normal_compose import WEB

class BackupCompletionTests(unittest.TestCase):
    def test_only_current_schema146_backup_and_fresh_positive_boundary_are_available(self):
        path=WEB/'scripts/complete_commercial_backup.py'
        source=path.read_text();tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertTrue({'child','run_deploy_service','run_migration','install_controller','installer_apply','stage_candidate','seal_intent','seal_completion'}.isdisjoint(calls))
        self.assertIn('fresh_attempt_root=self.scope',source)
        self.assertIn("publication_name='candidate-runtime.json'",source)
        self.assertIn("constructor.CompletedNormalWriteHandoff(self.contract,kernel",source)
        self.assertIn('BINDING_FAILURE_PLAN',source)
        self.assertIn("'migrations':[]",source)
        self.assertIn('super().validate(plan,root,driver.actor.package)',source)
        self.assertIn("backup.scope=digest({'operation':OPERATION,'plan_sha256':digest(self.plan)",source)
        self.assertIn("'backup.py','write-handoff.py'",source)
        spec=importlib.util.spec_from_file_location('backup_completion_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.OPERATION,'retained-normal-schema146-backup-completion')
        for invalid in ('','a'*63,'x'*64,'../scope'):
            with self.assertRaisesRegex(RuntimeError,'source_hash_invalid'):module.Continuation(invalid)

    def test_preparation_guard_verifies_source_before_plan_exists(self):
        path=WEB/'scripts/complete_commercial_backup.py'
        spec=importlib.util.spec_from_file_location('backup_completion_guard_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            package=Path(directory);payload=b'exact reviewed executable';(package/'driver.py').write_bytes(payload)
            manifest={'files':{'driver.py':hashlib.sha256(payload).hexdigest()}}
            raw=module.encoded(manifest);(package/'source-bundle.json').write_bytes(raw)
            actor=SimpleNamespace(guard=Mock())
            subject=object.__new__(module.Continuation)
            subject.package=package;subject.source_hash=hashlib.sha256(raw).hexdigest()
            subject.manifest=manifest;subject.actor=actor;subject.plan=None;subject.active=False
            with patch.object(module,'secure',side_effect=lambda p:p):
                subject.guard();actor.guard.assert_called_once()
                subject.active=True
                with self.assertRaisesRegex(RuntimeError,'frozen_plan_required'):subject.guard()
                subject.active=False;(package/'driver.py').write_bytes(b'altered')
                with self.assertRaisesRegex(RuntimeError,'executable_changed'):subject.guard()
