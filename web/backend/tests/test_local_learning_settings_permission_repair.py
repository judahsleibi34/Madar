"""The local ACL repair must never identify production by loopback alone."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

script = Path('/test-repository/scripts/repair_local_learning_settings_permissions.py')
if not script.exists():
    script = Path(__file__).resolve().parents[2] / 'scripts/repair_local_learning_settings_permissions.py'
spec = importlib.util.spec_from_file_location('local_settings_acl_repair', script)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class LocalSettingsPermissionRepairTests(unittest.TestCase):
    def test_rejects_the_production_ssh_tunnel_before_database_or_docker_access(self):
        for config in [
            {'APP_ENV':'development','SUPABASE_DB_URL':'postgresql://judah_crud@127.0.0.1:15433/postgres'},
            {'APP_ENV':'production','SUPABASE_DB_URL':'postgresql://postgres@127.0.0.1:54322/postgres'},
            {'APP_ENV':'development','SUPABASE_DB_URL':'postgresql://postgres@remote.example:54322/postgres'},
        ]:
            with self.subTest(config=config), patch.object(repair,'dotenv_values',return_value=config), patch.object(repair.psycopg,'connect') as connect, patch.object(repair.subprocess,'check_output') as docker:
                with self.assertRaises(RuntimeError): repair.repair(apply=True)
                connect.assert_not_called(); docker.assert_not_called()

    def test_rejects_a_remote_docker_context(self):
        config={'APP_ENV':'development','SUPABASE_DB_URL':'postgresql://postgres@127.0.0.1:54322/postgres'}
        with patch.object(repair,'dotenv_values',return_value=config), patch.dict(repair.os.environ,{'DOCKER_HOST':''}), patch.object(repair.subprocess,'check_output',return_value='tcp://remote.example:2375'), patch.object(repair.psycopg,'connect') as connect:
            with self.assertRaises(RuntimeError): repair.repair(apply=True)
            connect.assert_not_called()

    def test_cluster_mismatch_is_rejected_before_permission_grants(self):
        config={'APP_ENV':'development','SUPABASE_DB_URL':'postgresql://postgres@127.0.0.1:54322/postgres'}
        labels={'com.supabase.cli.project':'web','com.supabase.cli.workdir':str(repair.ROOT/'web')}
        db=MagicMock();db.execute.return_value.fetchone.return_value=('another-cluster',)
        source='create function public.normalize_academy_programme_settings(cfg jsonb) returns jsonb language plpgsql immutable as $$ begin return cfg; end $$;'
        with patch.object(repair,'dotenv_values',return_value=config), patch.dict(repair.os.environ,{'DOCKER_HOST':''}), patch.object(repair.subprocess,'check_output',side_effect=['unix:///var/run/docker.sock',json.dumps([{'Config':{'Labels':labels}}]),'local-cluster']), patch.object(Path,'read_text',return_value=source), patch.object(repair.psycopg,'connect') as connect:
            connect.return_value.__enter__.return_value=db
            with self.assertRaises(RuntimeError):repair.repair(apply=True)
            self.assertEqual([call.args[0] for call in db.execute.call_args_list],['select system_identifier from pg_control_system()'])
