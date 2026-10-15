"""The backup-only continuation cannot repeat SQL or deployment effects."""
import ast
import importlib.util
import unittest
from test_completed_normal_compose import WEB

class BackupCompletionTests(unittest.TestCase):
    def test_only_current_schema146_backup_and_fresh_positive_boundary_are_available(self):
        path=WEB/'scripts/complete_commercial_backup.py'
        source=path.read_text();tree=ast.parse(source)
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertTrue({'child','run_deploy_service','run_migration','install_controller','installer_apply','stage_candidate','seal_intent','seal_completion'}.isdisjoint(calls))
        self.assertIn('fresh_attempt_root=self.scope',source)
        self.assertIn("'migrations':[]",source)
        self.assertIn('super().validate(plan,root,driver.actor.package)',source)
        self.assertIn("backup.scope=digest({'operation':OPERATION,'plan_sha256':digest(self.plan)",source)
        self.assertIn("'backup.py','write-handoff.py'",source)
        spec=importlib.util.spec_from_file_location('backup_completion_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.OPERATION,'retained-normal-schema146-backup-completion')
        for invalid in ('','a'*63,'x'*64,'../scope'):
            with self.assertRaisesRegex(RuntimeError,'source_hash_invalid'):module.Continuation(invalid)
