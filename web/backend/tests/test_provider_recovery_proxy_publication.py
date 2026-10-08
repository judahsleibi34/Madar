"""Recovery traffic must publish safe canonical logging, not await SMTP."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

WEB_ROOT = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.provider_local_proxy_configuration import publish_callback_safe_proxy
from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths, digest
from deployment.lib.provider_recovery_preparation import PrivatePreparationOperations
from deployment.lib.runtime_authority import runtime_mutation_lock, write_worker_authority
import test_provider_recovery_controller as fixtures


class RecoveryProxyPublicationTests(unittest.TestCase):
    def test_legacy_bind_is_recreated_only_by_installed_service_after_preflight(self):
        source = (WEB_ROOT/'deployment/proxy/nginx.conf').read_text().strip()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proxy = root/'controller/proxy'
            proxy.mkdir(parents=True)
            (proxy/'nginx.conf').write_text(source)
            (proxy/'docker-compose.yml').write_text((WEB_ROOT/'deployment/proxy/docker-compose.yml').read_text())
            calls = []
            published = False
            def command(args):
                nonlocal published
                calls.append(args)
                if args[0]=='git': return source
                if args[:2]==['systemctl','restart']:
                    published = True
                if args[:3]==['docker','exec','madar-release-proxy']:
                    return source if published else 'legacy logging config'
                return ''
            ops = SimpleNamespace(command=command, inspect=lambda name: {
                'HostConfig':{'NetworkMode':'host'}, 'Mounts':[{'Source':str(proxy/'nginx.conf'),
                'Destination':'/etc/nginx/nginx.conf','RW':False}]})
            recovery = SimpleNamespace(paths=SimpleNamespace(controller=root/'controller',
                repository=root/'repository',proxy='madar-release-proxy',
                upstream=root/'upstreams/active-upstreams.conf',prefix='madar-provider402'))
            with patch('deployment.lib.provider_local_proxy_configuration.os.geteuid',return_value=0), patch(
                    'deployment.lib.provider_local_proxy_configuration.protected',side_effect=lambda p:p):
                publish_callback_safe_proxy(ops,recovery,'a'*40)
            preflight=next(i for i,c in enumerate(calls) if c[:2]==['docker','run'])
            restart=calls.index(['systemctl','restart','madar-release-proxy.service'])
            self.assertLess(preflight,restart)
            self.assertIn('--pull=never',calls[preflight])
            self.assertEqual(calls[preflight][calls[preflight].index('--network')+1],'none')
            self.assertIn('/var/cache/nginx:rw,noexec,nosuid,size=32m,uid=101,gid=101',calls[preflight])
            self.assertTrue(published)

    def test_failed_logging_publication_cannot_reload_or_accept_traffic(self):
        with tempfile.TemporaryDirectory() as temp:
            fixtures.RecoveryControllerTests.setUp(self)
            root=Path(temp)
            upstream=root/'proxy/active-upstreams.conf'
            upstream.parent.mkdir()
            upstream.write_text('old fixture upstream')
            ops=ProductionRecoveryOperations.__new__(ProductionRecoveryOperations)
            ops.contract=self.contract
            ops.paths=RecoveryPaths(state=root,upstream=upstream)
            ops.trace=[]
            ops.authorize=Mock()
            ops.require_all_workers_off=Mock()
            ops.validate_runtime=Mock()
            ops.runtime_endpoint=lambda slot,kind:'http://10.0.0.2:'+('8000' if kind=='backend' else '8080')
            ops.command=Mock(return_value='')
            ops.smoke_recovery=Mock()
            with runtime_mutation_lock(root):
                write_worker_authority(root,generation=digest(self.contract.__dict__),owner='RECOVERY',
                    old={'sha':self.contract.origin_sha,'slot':'green'},
                    candidate={'sha':self.contract.sha,'slot':'blue'})
            (root/'provider-recovery.json').write_text(json.dumps({
                'phase':'switch_pending','context_digest':digest(self.contract.__dict__)}))
            with patch('deployment.lib.provider_local_proxy_configuration.publish_callback_safe_proxy',
                       side_effect=RuntimeError('proxy publication failed')) as publish:
                with self.assertRaisesRegex(RuntimeError,'publication failed'):
                    ops.switch('blue')
            publish.assert_called_once_with(ops,ops,self.contract.sha)
            ops.authorize.assert_called_once_with(self.contract)
            ops.require_all_workers_off.assert_called_once()
            ops.validate_runtime.assert_called_once_with('blue')
            ops.command.assert_not_called()
            ops.smoke_recovery.assert_not_called()
            self.assertFalse((root/'provider-recovery-traffic.json').exists())

    def test_private_capability_requires_isolation_and_disabled_logging(self):
        ops=PrivatePreparationOperations.__new__(PrivatePreparationOperations)
        ops.paths=SimpleNamespace(proxy='scoped-proxy')
        ops.require_isolated=Mock()
        ops.inspect=Mock(return_value={'HostConfig':{'LogConfig':{'Type':'json-file'}}})
        with self.assertRaisesRegex(RuntimeError,'private_proxy_logging_enabled'):
            ops.prepare_proxy_publication()
        ops.require_isolated.assert_called_once()
        ops.inspect.return_value={'HostConfig':{'LogConfig':{'Type':'none'}}}
        ops.prepare_proxy_publication()
        ops.require_isolated.side_effect=RuntimeError('private scope invalid')
        with self.assertRaisesRegex(RuntimeError,'private scope invalid'):
            ops.prepare_proxy_publication()

    def test_production_scope_always_uses_canonical_publication(self):
        ops=ProductionRecoveryOperations.__new__(ProductionRecoveryOperations)
        ops.contract=SimpleNamespace(sha='a'*40)
        with patch.dict(os.environ,{'RECOVERY_FIXTURE':'true'}), patch(
                'deployment.lib.provider_local_proxy_configuration.publish_callback_safe_proxy') as publish:
            ops.prepare_proxy_publication()
        publish.assert_called_once_with(ops,ops,'a'*40)


if __name__=='__main__':
    unittest.main()
