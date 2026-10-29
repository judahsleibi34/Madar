"""Disposable-host admission only; native services use the opt-in VM harness."""
from datetime import datetime,timedelta,timezone
import json,os
from pathlib import Path
import subprocess,sys
import unittest
from unittest.mock import patch

ROOT=Path(os.environ.get('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(ROOT/'staging/integration'))
import private_provider_transport as fixture


class DisposableProviderFixtureTests(unittest.TestCase):
    uuid='12345678-1234-1234-1234-123456789abc'

    def marker(self):
        return {'guest_uuid':self.uuid,'disposable':True,'production_authority':False,
            'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}

    def invoke(self,*,marker=None,metadata='0:600:1:regular file',guest=None,containers=b''):
        value=self.marker() if marker is None else marker
        responses=[(guest or self.uuid).encode(),metadata.encode(),json.dumps(value).encode(),containers]
        with patch.object(fixture.subprocess,'check_output',side_effect=responses) as commands, \
                patch.object(fixture.subprocess,'run') as isolation:
            fixture.require_disposable_guest(self.uuid)
        self.assertEqual(commands.call_args_list[-1].args[0],['sudo','docker','ps','-aq'])
        isolation.assert_called_once_with(['sudo','systemctl','is-active','--quiet','codex-test-isolation.service'],check=True)

    def test_admits_only_empty_expiring_root_marked_guest(self):self.invoke()

    def test_refuses_wrong_guest_owner_permissions_symlink_or_nonempty_daemon(self):
        for args in ({'guest':'00000000-0000-0000-0000-000000000000'},
                {'metadata':'1000:600:1:regular file'},{'metadata':'0:644:1:regular file'},
                {'metadata':'0:600:2:regular file'},{'metadata':'0:777:1:symbolic link'},
                {'containers':b'accepted-staging-container'}):
            with self.subTest(args=args),self.assertRaises(RuntimeError):self.invoke(**args)

    def test_root_marker_is_not_production_authority_and_must_expire(self):
        for changes in ({'production_authority':True},{'disposable':False},{'guest_uuid':'foreign'},
                {'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()},
                {'caller_says_pass':True}):
            value={**self.marker(),**changes}
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):self.invoke(marker=value)

    def test_inactive_isolation_service_refuses_before_docker_inspection(self):
        with patch.object(fixture.subprocess,'check_output',side_effect=[self.uuid.encode(),
                b'0:600:1:regular file',json.dumps(self.marker()).encode()]) as commands, \
                patch.object(fixture.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'systemctl')):
            with self.assertRaises(subprocess.CalledProcessError):fixture.require_disposable_guest(self.uuid)
        self.assertEqual(commands.call_count,3)
