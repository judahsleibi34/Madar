"""Runner safeguards with fake subprocess results; no restored customer data."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
SCRIPTS=Path('/scripts') if Path('/scripts').is_dir() else WEB/'scripts'
spec=importlib.util.spec_from_file_location('restore_fixture',SCRIPTS/'restore_coordinated_checkpoint.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class CoordinatedRestoreToolingTests(unittest.TestCase):
    def test_database_error_never_emits_secret_sql_or_copy_rows(self):
        error='role "sensitive-role" does not exist; ALTER ROLE example PASSWORD secret-fixture; COPY private-data'
        result=subprocess.CompletedProcess(['fixture'],1,stdout='',stderr=error)
        with patch.object(runner.subprocess,'run',return_value=result),self.assertRaisesRegex(RuntimeError,'^missing_role$'):
            runner.run(['fixture'])
    def test_no_production_command_runs_from_unisolated_entry(self):
        with patch.object(runner.os,'geteuid',return_value=1000),patch.object(runner.subprocess,'run') as command:
            with self.assertRaisesRegex(RuntimeError,'frozen_root_entry_required'):
                runner.restore(Path('/var/lib/madar-control-plane/normal-local-preparation/fixture'),'0'*64)
            command.assert_not_called()
    def test_psql_uses_socket_and_does_not_publish_or_log_input(self):
        with patch.object(runner,'run',return_value='fixture') as command:
            self.assertEqual(runner.psql('fixture-disposable','SELECT 1;'),'fixture')
        args=command.call_args.args[0]
        self.assertEqual(args[:4],['docker','exec','-i','fixture-disposable'])
        self.assertEqual(args[args.index('-h')+1],'/tmp')
        self.assertNotIn('SELECT 1;',args)

    def test_saved_postgres_role_cannot_demote_restore_session(self):
        with patch.object(runner,'run',return_value='fixture') as command:
            runner.psql('fixture-disposable','ALTER ROLE postgres NOSUPERUSER;')
        args=command.call_args.args[0]
        self.assertEqual(args[args.index('-U')+1],runner.BOOTSTRAP)
        self.assertNotEqual(runner.BOOTSTRAP,'postgres')
        self.assertEqual(runner.BOOTSTRAP,"supabase_admin")

    def test_original_bootstrap_identity_and_all_grants_are_preserved(self):
        saved='CREATE ROLE supabase_admin;\nALTER ROLE supabase_admin WITH SUPERUSER;\nALTER ROLE postgres NOSUPERUSER;\nGRANT example TO postgres WITH ADMIN OPTION GRANTED BY supabase_admin;\n'
        result=runner.role_restore_sql(saved)
        self.assertNotIn('CREATE ROLE supabase_admin;',result)
        self.assertEqual(result,saved.replace('CREATE ROLE supabase_admin;\n','',1))
    def test_wrong_bootstrap_identity_or_privilege_is_rejected(self):
        for saved in ['CREATE ROLE other;','CREATE ROLE supabase_admin;\nALTER ROLE supabase_admin WITH NOSUPERUSER;']:
            with self.subTest(saved=saved),self.assertRaisesRegex(RuntimeError,'bootstrap_identity_invalid'):
                runner.role_restore_sql(saved)
