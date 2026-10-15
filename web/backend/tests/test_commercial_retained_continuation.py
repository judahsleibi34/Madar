"""Fresh retained continuation guards; no production effects in these tests."""
import ast
import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_completed_normal_compose import WEB

spec=importlib.util.spec_from_file_location('commercial_retained_driver',WEB/'scripts/continue_commercial_release.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class RetainedContinuationTests(unittest.TestCase):
    def test_no_rebuild_reinstall_retirement_or_historical_restore(self):
        tree=ast.parse((WEB/'scripts/continue_commercial_release.py').read_text())
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertTrue({'installer_apply','install_controller','resolve_candidate','stage_candidate','rollback_application_origin','retire_bound_resources'}.isdisjoint(calls))
        self.assertIn('child',calls);self.assertIn('grant',calls)
        self.assertEqual(module.OPERATION,'retained-normal-schema144-146-pre-sql-continuation')

    def test_invalid_source_and_changed_live_bindings_reject_before_execution(self):
        for value in ('','x'*64,'a'*63,'../other'):
            with self.assertRaisesRegex(RuntimeError,'source_hash_invalid'):module.Continuation(value)
        driver=object.__new__(module.Continuation)
        driver.plan={'initial':{'bound':'original'}};driver.measurement=lambda:{'bound':'changed'}
        with self.assertRaisesRegex(RuntimeError,'live_bindings_changed'):driver.preflight()

    def test_consumed_attempt_is_rejected_and_fresh_witness_requires_active_authorization(self):
        driver=object.__new__(module.Continuation)
        with tempfile.TemporaryDirectory() as d:
            driver.plan={'initial':{}};driver.measurement=lambda:{};driver.scope=Path(d)/'attempt'
            self.assertEqual(driver.preflight()['authorization_consumed'],False)
            driver.scope.mkdir()
            with self.assertRaisesRegex(RuntimeError,'authorization_consumed'):driver.preflight()
        driver.guard=lambda:None;driver.active=False
        with self.assertRaisesRegex(RuntimeError,'fresh_authorization_required'):driver.witness()

    def test_migration_child_retains_schema_image_controller_and_credential_validation(self):
        source=(WEB/'scripts/continue_commercial_release_child.py').read_text()
        for required in ('require_admission','require_fresh_authorization','controller_tree_digest','migration_sha256','(144,146,146,())','operations.verify_source','deployment_lock','migration.run_migration'):
            self.assertIn(required,source)
        self.assertNotIn("sys.argv[1]=='activate'",source)
