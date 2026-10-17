"""Safety boundaries for the dedicated-VM-only, disposable writer drill."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import provider_quiescence_rehearsal as rehearsal


class ProviderQuiescenceSafetyTests(unittest.TestCase):
    def test_nonstaging_host_rejects_every_mode_before_any_docker_operation(self):
        for mode in ('INSPECT', 'REHEARSE', 'RECOVER'):
            with self.subTest(mode=mode), patch.object(rehearsal.manage.socket, 'gethostname', return_value='primary'), \
                    patch.object(rehearsal.manage, 'docker') as docker:
                with self.assertRaises(RuntimeError):
                    rehearsal.main(mode)
                docker.assert_not_called()

    def test_default_inspection_does_not_mutate_or_issue_admission(self):
        with patch.object(rehearsal.manage, 'require_staging_host'), patch.object(rehearsal.manage, 'docker') as docker:
            result = rehearsal.main()
            self.assertEqual(result['mode'], 'INSPECT')
            self.assertTrue(result['controller_admission'].startswith('BLOCKED:'))
            self.assertFalse(result['production_modified'])
            docker.assert_not_called()

    def test_unexpected_mode_or_rehearsal_runtime_cannot_become_a_recovery_target(self):
        with patch.object(rehearsal.manage, 'require_staging_host'), patch.object(rehearsal.manage, 'docker') as docker:
            for mode, runtime in (('EXECUTE', None), ('REHEARSE', Path('/tmp/arbitrary')), ('RECOVER', None)):
                with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                    rehearsal.main(mode, runtime=runtime)
            docker.assert_not_called()

    def test_runtime_is_private_direct_owned_home_child_with_exact_generated_name(self):
        with tempfile.TemporaryDirectory() as raw, patch.object(rehearsal.Path, 'home', return_value=Path(raw)):
            home = Path(raw)
            runtime = home / (rehearsal.PREFIX + 'a' * 12)
            runtime.mkdir(mode=0o700)
            self.assertEqual(rehearsal.runtime_path(runtime), runtime)
            for path in (home, home / 'unrelated', home / 'nested' / runtime.name):
                with self.subTest(path_kind=path.name), self.assertRaises(RuntimeError):
                    rehearsal.runtime_path(path)
            runtime.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, 'untrusted'):
                rehearsal.runtime_path(runtime)
            runtime.chmod(0o700)
            other = home / (rehearsal.PREFIX + 'b' * 12)
            other.symlink_to(runtime, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                rehearsal.runtime_path(other)

    def test_unknown_container_volume_restart_or_network_prevents_cleanup_and_mutation(self):
        state = {'container': 'synthetic-db', 'volume': 'synthetic-data', 'scope': 'synthetic-scope'}
        row = {'Name': '/synthetic-db', 'Id': 'a' * 64,
               'Config': {'Image': rehearsal.IMAGE, 'Labels': {
                   rehearsal.SCOPE_LABEL: 'synthetic-scope', 'com.madar.staging.owner': rehearsal.manage.OWNER}},
               'HostConfig': {'NetworkMode': 'none', 'RestartPolicy': {'Name': 'no'}},
               'Mounts': [{'Destination': '/var/lib/postgresql/data', 'Name': 'synthetic-data'}]}
        for changed in ('owner', 'scope', 'image', 'network', 'restart', 'volume', 'port'):
            import copy
            bad = copy.deepcopy(row)
            if changed == 'owner':
                bad['Config']['Labels']['com.madar.staging.owner'] = 'unrelated'
            elif changed == 'scope':
                bad['Config']['Labels'][rehearsal.SCOPE_LABEL] = 'unrelated'
            elif changed == 'image':
                bad['Config']['Image'] = 'untrusted-image'
            elif changed == 'network':
                bad['HostConfig']['NetworkMode'] = 'host'
            elif changed == 'restart':
                bad['HostConfig']['RestartPolicy']['Name'] = 'always'
            elif changed == 'volume':
                bad['Mounts'][0]['Name'] = 'unrelated-volume'
            else:
                bad['HostConfig']['PortBindings'] = {'5432/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '5432'}]}
            with self.subTest(changed=changed), patch.object(rehearsal.manage, 'require_staging_host'), \
                    patch.object(rehearsal.manage, 'docker', return_value=json.dumps([bad])) as docker:
                with self.assertRaisesRegex(RuntimeError, 'unowned|changed'):
                    rehearsal.owned_container(state)
                docker.assert_called_once_with('inspect', state['container'])

    def test_denial_requires_expected_role_login_error_and_live_positive_control(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for error in ('connection refused', 'permission denied for table sessions',
                          'role "other" is not permitted to log in'):
                (root / 'last-command-error.log').write_text(error)
                with self.subTest(error_kind=error.split()[0]), \
                        patch.object(rehearsal.manage, 'RUNTIME', root), \
                        patch.object(rehearsal, 'owned_container'), \
                        patch.object(rehearsal, 'raw_sql', side_effect=RuntimeError('rejected')), \
                        patch.object(rehearsal, 'database', return_value='1'):
                    with self.assertRaisesRegex(RuntimeError, 'denial_reason_unverified'):
                        rehearsal.deny_new_connection({})


if __name__ == '__main__':
    unittest.main()
