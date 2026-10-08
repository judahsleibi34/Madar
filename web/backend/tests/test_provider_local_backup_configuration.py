"""Backup publication unit regressions; independent restore is a separate gate."""
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB))
from deployment.lib import provider_local_backup_configuration as configuration
from deployment.lib.environment_file import load_environment_file


@dataclass(frozen=True)
class Contract:
    sha: str = 'a' * 40


class NativeBackupConfigurationTests(unittest.TestCase):
    def test_only_database_fields_change_and_secret_quoting_roundtrips(self):
        native = {'POSTGRES_PASSWORD': "synthetic-only ' quote # value", 'POOLER_TENANT_ID': 'fixture'}
        original = '# retained policy\nMADAR_BACKUP_KEEP_COUNT=2147483647\nPGHOST=hosted.invalid\nPGPORT=5432\n'
        body = configuration.replace_backup_fields(original, configuration.native_backup_changes(native))
        self.assertIn('# retained policy\nMADAR_BACKUP_KEEP_COUNT=2147483647\n', body)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backup.env'; path.write_text(body); path.chmod(0o600)
            values = {}; load_environment_file(path, environ=values)
        self.assertEqual(values['PGPASSWORD'], native['POSTGRES_PASSWORD'])
        self.assertEqual(values['PGUSER'], 'postgres')
        self.assertEqual(values['PGHOST'], 'supabase-db')
        self.assertEqual(values['PGPORT'], '5432')
        self.assertEqual(values['PGSSLMODE'], 'disable')

    def test_invalid_native_inputs_cannot_be_published(self):
        for native in ({}, {'POSTGRES_PASSWORD':'synthetic\nvalue','POOLER_TENANT_ID':'fixture'},
                       {'POSTGRES_PASSWORD':'synthetic','POOLER_TENANT_ID':'fixture/other'}):
            with self.subTest(native_shape=sorted(native)), self.assertRaisesRegex(RuntimeError,'configuration_invalid'):
                configuration.native_backup_changes(native)

    def test_changed_backup_input_requires_exact_publication_receipt_and_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'backup.env'; path.write_text('PGHOST=127.0.0.1\n')
            before = 'b' * 64; observed = configuration.file_digest(path); contract = Contract()
            report = {'backup_configuration_before_digest':before}
            receipt = {'version':1,'contract_digest':configuration.digest({'sha':contract.sha}),
                       'before':before,'after':observed}
            (root / 'backup-configuration.json').write_text(json.dumps(receipt))
            with patch.object(configuration,'BACKUP_ENV',path), patch.object(configuration,'readonly_configuration',side_effect=lambda p,**kw:p), patch.object(configuration,'protected',side_effect=lambda p,**kw:p):
                configuration.verify_backup_input(root,report,contract,'normal')
                for phase in (None,'prepared','serving_read_only'):
                    with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
                        configuration.verify_backup_input(root,report,contract,phase)
                with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
                    configuration.verify_backup_input(root,report,Contract('c'*40),'normal')
                path.write_text('PGHOST=unexpected.invalid\n')
                with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
                    configuration.verify_backup_input(root,report,contract,'normal')

    def test_untrusted_publication_fails_before_any_configuration_read(self):
        with patch.object(configuration.os,'geteuid',return_value=65534), patch.object(configuration,'verify_backup_input') as read:
            with self.assertRaisesRegex(RuntimeError,'root_required'):
                configuration.publish_backup_configuration(Path('/fixture'),{},Contract(),{})
            read.assert_not_called()

    def test_old_hosted_configuration_cannot_reappear_after_local_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'backup.env'; path.write_text('PGHOST=hosted.invalid\n')
            before = configuration.file_digest(path); contract = Contract()
            (root / 'backup-configuration.json').write_text(json.dumps({'version':1,
                'contract_digest':configuration.digest({'sha':contract.sha}), 'before':before, 'after':'f'*64}))
            with patch.object(configuration,'BACKUP_ENV',path), patch.object(configuration,'readonly_configuration',side_effect=lambda p,**kw:p), patch.object(configuration,'protected',side_effect=lambda p,**kw:p):
                with self.assertRaisesRegex(RuntimeError,'configuration_changed'):
                    configuration.verify_backup_input(root,{'backup_configuration_before_digest':before},contract,'normal')


class CallbackProxyConfigurationTests(unittest.TestCase):
    def test_canonical_proxy_is_safe_and_raw_query_referrer_or_headers_are_rejected(self):
        from deployment.lib.provider_local_proxy_configuration import require_safe_proxy_source
        source = (WEB / 'deployment/proxy/nginx.conf').read_text()
        require_safe_proxy_source(source)
        for unsafe in ('$request', '$request_uri', '$http_referer', '$http_cookie', '$http_authorization', '$args', '$query_string'):
            with self.subTest(field=unsafe), self.assertRaisesRegex(RuntimeError,'logging_unsafe'):
                require_safe_proxy_source(source.replace('$request_method $uri',unsafe))
        with self.assertRaisesRegex(RuntimeError,'callback_logging_unsafe'):
            require_safe_proxy_source(source.replace('access_log off;', 'access_log /dev/stdout madar_path_only;',1))


class ScheduledBackupTransportTests(unittest.TestCase):
    def test_direct_resolver_rejects_wrong_identity_and_unsafe_networks(self):
        spec = importlib.util.spec_from_file_location('backup_support_direct', WEB / 'scripts/backup_support.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        good = {'running': True, 'health': 'healthy', 'service': 'db',
                'directory': '/opt/madar/local-supabase', 'publications': {},
                'networks': {'native': {'IPAddress': '172.19.0.2'}}}
        from subprocess import CompletedProcess
        with patch.object(module.subprocess, 'run', return_value=CompletedProcess([], 0, json.dumps(good))):
            self.assertEqual(module.direct_local_database_address(), '172.19.0.2')
        for change in ({'running': False}, {'health': 'unhealthy'}, {'service': 'pooler'},
                       {'directory': '/other'}, {'publications': {'5432/tcp': [{}]}},
                       {'networks': {}}, {'networks': {'a': {}, 'b': {}}},
                       *({'networks': {'native': {'IPAddress': address}}}
                         for address in ('8.8.8.8', '127.0.0.1', '0.0.0.0', '169.254.1.2', '::1'))):
            with self.subTest(changed_fields=sorted(change)), patch.object(module.subprocess, 'run',
                    return_value=CompletedProcess([], 0, json.dumps({**good, **change}))):
                with self.assertRaisesRegex(module.BackupError, 'direct_database_unavailable'):
                    module.direct_local_database_address()

    def test_scheduled_local_backup_rejects_both_poolers(self):
        spec = importlib.util.spec_from_file_location('backup_support_poolers', WEB / 'scripts/backup_support.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        for port in ('15432', '16543'):
            with patch.dict(os.environ, {'PGHOST': 'supabase-db', 'PGPORT': port,
                'PGUSER': 'postgres', 'PGDATABASE': 'postgres', 'PGSSLMODE': 'disable'}, clear=True):
                self.assertFalse(module.direct_local_database_shape())


    def test_exact_internal_alias_uses_loopback_and_requires_matching_local_database(self):
        spec = importlib.util.spec_from_file_location('backup_support_local_transport', WEB / 'scripts/backup_support.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'production.env').write_text('SUPABASE_URL=http://madar-supabase:8000\nSUPABASE_SERVICE_KEY=synthetic-fixture-placeholder\n')
            (root / 'state.json').write_text(json.dumps({'known_good_release':{'sha':'a'*40}}))
            env = {'CREDENTIALS_DIRECTORY':str(root),'MADAR_DEPLOY_STATE_ROOT':str(root),
                   'PGHOST':'supabase-db','PGPORT':'5432','PGUSER':'postgres','PGDATABASE':'postgres','PGSSLMODE':'disable'}
            class Response:
                def __enter__(self): return self
                def __exit__(self,*_): return False
                def read(self): return json.dumps({'release_sha':'a'*40,'build_timestamp':'fixture'}).encode()
            with patch.dict(os.environ,env,clear=True), patch.object(module.urllib.request,'urlopen',return_value=Response()), patch.object(module.os,'execve') as execute, patch.object(module,'direct_local_database_address',return_value='172.19.0.2'):
                module.scheduled(Path('/fixture/backup_madar.sh'))
                self.assertEqual(execute.call_args.args[2]['SUPABASE_URL'],'http://127.0.0.1:18000')
                self.assertEqual(execute.call_args.args[2]['PGHOSTADDR'],'172.19.0.2')
                os.environ['PGHOST']='hosted.invalid'
                execute.reset_mock()
                with self.assertRaisesRegex(module.BackupError,'database_configuration_mismatch'):
                    module.scheduled(Path('/fixture/backup_madar.sh'))
                execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
