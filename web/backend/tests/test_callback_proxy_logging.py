import importlib.util
import os
import unittest
from pathlib import Path

ROOT=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('gateway_safe_logs',ROOT/'precutover/prepare_gateway_logging.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


class CallbackProxyLoggingTests(unittest.TestCase):
    def test_gateway_formatter_drops_query_and_referrer(self):
        result=helper.safe_template('%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)% %REQ(REFERER)%')
        self.assertEqual(result,'%PATH(NQ:ORIG_OR_PATH)% -')
        with self.assertRaises(ValueError):helper.safe_template('unknown format')

    def test_nginx_sources_protect_callback_query_credentials(self):
        for filename in ['frontend/nginx.conf.template','deployment/proxy/nginx.conf','deployment/proxy/madar-release-proxy.conf']:
            source=(ROOT/filename).read_text()
            self.assertIn('$request_method $uri $server_protocol',source)
            self.assertNotIn('$http_referer',source)
            self.assertIn('error_log /dev/stderr crit;',source)
            self.assertIn('location = /api/auth/v1/verify',source)
            if filename.startswith('deployment/'):
                self.assertIn('location = /auth/v1/verify',source)
