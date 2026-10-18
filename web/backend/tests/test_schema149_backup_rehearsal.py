import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import schema149_backup_rehearsal as backup


class BackupSafetyTests(unittest.TestCase):
    def test_unknown_mode_refuses_before_host_or_database(self):
        with patch.object(backup.manage,'require_staging_host') as host,self.assertRaises(RuntimeError):backup.run('EXECUTE')
        host.assert_not_called()
    def test_primary_host_refuses_before_effects(self):
        with patch.object(backup.manage.socket,'gethostname',return_value='madar-gpu'),patch.object(backup.manage,'state') as state,self.assertRaises(RuntimeError):backup.run('REHEARSE')
        state.assert_not_called()
    def test_inspect_has_no_dump_or_service_effect(self):
        with patch.object(backup.manage,'require_staging_host'),patch.object(backup.manage,'state'),patch.object(backup.manage,'attest_resources'),patch.object(backup.manage,'require_database_marker'),patch.object(backup.providers,'sql',return_value='149:2:2'),patch.object(backup.manage,'docker') as docker:
            self.assertFalse(backup.run('INSPECT')['mutations_executed'])
        docker.assert_not_called()
