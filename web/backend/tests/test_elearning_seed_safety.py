import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import seed_elearning_demo as seed


class SeedSafetyTests(unittest.TestCase):
    def test_production_environment_is_rejected_before_any_database_or_docker_access(self):
        with patch.dict(os.environ,{'APP_ENV':'production'}),patch.object(seed,'dotenv_values') as read,patch.object(seed.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'production'):seed.local_configuration()
            read.assert_not_called();run.assert_not_called()

    def test_hosted_database_local_proxy_or_wrong_ports_are_rejected(self):
        config={'APP_ENV':'development','SUPABASE_DB_URL':'postgresql://127.0.0.1:54322/postgres','SUPABASE_URL':'http://127.0.0.1:54321','MADAR_TEST_EMAIL':'test@example.invalid'}
        for changes in ({'SUPABASE_DB_URL':'postgresql://hosted.example/postgres'},{'SUPABASE_DB_URL':'postgresql://127.0.0.1:15432/postgres'},{'SUPABASE_URL':'https://shared.supabase.co'},{'APP_ENV':'production'}):
            with patch.dict(os.environ,{'APP_ENV':'development'}),patch.object(seed,'dotenv_values',return_value={**config,**changes}),patch.object(seed.subprocess,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'generated local'):seed.local_configuration()
                run.assert_not_called()

    def test_stable_ids_are_tenant_scoped(self):
        self.assertEqual(seed.stable_id(17,'english'),seed.stable_id(17,'english'))
        self.assertNotEqual(seed.stable_id(17,'english'),seed.stable_id(18,'english'))
        courses,sections,lessons=seed.expected_ids(17)
        self.assertEqual((len(courses),len(sections),len(lessons)),(4,16,99))
