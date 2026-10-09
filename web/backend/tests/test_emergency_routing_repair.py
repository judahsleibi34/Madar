"""Emergency routing trust, compensation and restart regressions; no production I/O."""
import copy
from contextlib import nullcontext
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

WEB_ROOT = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib import emergency_routing_repair as repair


class FixtureRuntime:
    def __init__(self):
        source = 'a' * 40
        images = {'backend': 'sha256:' + 'b' * 64, 'frontend': 'sha256:' + 'c' * 64}
        contract = {'sha': source, 'images': images, 'rehearsal_digest': 'd' * 64}
        fallback = {'version': 1, 'sha': source, 'schema': 115, 'images': images,
                    'profile': 'provider402-signin', 'supabase_url': 'http://madar-supabase:8000',
                    'network': 'madar-supabase-client', 'database_restore': False}
        contract['rollback_runtime_digest'] = repair.digest(fallback)
        context = repair.digest(contract)
        local_contract = {'sha': source, 'images': images, 'recovery_context': context}
        schema = {'migration_policy': 'none', 'schema': {'compatible_min': 115,
                  'compatible_max': 115, 'target': 115, 'migration_class': 'none',
                  'rollback_compatible_min': 115, 'rollback_compatible_max': 115}}
        local_digest = repair.digest(local_contract)
        docs = {
            'recovery_contract': contract, 'schema_contract': schema,
            'local_contract': local_contract,
            'local_transaction': {'phase': 'local_rollback_active', 'contract_digest': local_digest,
                'sha': source, 'images': images, 'schema': 115, 'database_restore': False,
                'normal_writes_ever_enabled': False, 'migration_policy': 'none'},
            'recovery_transaction': {'phase': 'local_rollback_active', 'context_digest': context,
                'sha': source, 'schema': 115, 'restore_database_on_rollback': False,
                'worker_owner': 'RECOVERY', 'migration_policy': 'none'},
            'fallback': fallback,
            'write_authority': {'version': 1, 'schema': 115, 'release_sha': source,
                'contract_digest': local_digest, 'mode': 'READ_ONLY'},
            'workers': {'owner': 'RECOVERY', 'generation': context, 'candidate': {'sha': source}},
            'traffic': {'database_restore': False, 'provider': 'local', 'schema': 115,
                'sha': source, 'slot': 'local-fallback'}, 'release_state': {'kept': 'original'},
        }
        self.inputs = {k: repair.encoded(v) for k, v in docs.items()}
        self.inputs.update(controller_sha=source.encode(), nginx=b'original-approved-nginx',
            proxy_compose=b'image: nginx:alpine@sha256:' + b'e' * 64,
            gateway_bootstrap=b'approved native gateway bootstrap',
            gateway_lds=b'approved native gateway listener',
            gateway_cds=b''.join(b'address: '+host+b'\nport_value: '+port+b'\n' for host, port in
                [(b'auth', b'9999'), (b'rest', b'3000'), (b'realtime-dev.supabase-realtime', b'4000'),
                 (b'storage', b'5000'), (b'functions', b'9000'), (b'meta', b'8080'), (b'studio', b'3000')]))
        _, _, self.roles, self.network_name = repair.identities(self.inputs)
        self.networks = {self.network_name: {'Id': 'runtime-network', 'Internal': True, 'Driver': 'bridge'},
                         'madar-supabase-client': {'Id': 'client-network', 'Internal': True, 'Driver': 'bridge'}}
        self.rows = {}
        for role in repair.ROLES:
            name = self.roles[role]
            row = self.row(name, images[role])
            row['Config']['Labels'] = {'org.opencontainers.image.revision': source,
                                      'com.madar.recovery.profile': 'provider402-signin'}
            row['NetworkSettings']['Networks'] = {self.network_name: {'NetworkID': 'runtime-network',
                'Aliases': [role], 'IPAddress': '10.254.202.5' if role == 'backend' else '10.254.202.4'}}
            if role == 'backend':
                row['NetworkSettings']['Networks']['madar-supabase-client'] = {
                    'NetworkID': 'client-network', 'IPAddress': '172.28.0.11'}
                row['Config']['Env'] = [k + '=' + v for k, v in {
                    'SUPABASE_URL': 'http://madar-supabase:8000', 'MADAR_RELEASE_SHA': source,
                    'MADAR_RELEASE_SLOT': 'local-fallback', 'MADAR_RECOVERY_PROFILE': 'provider402-signin',
                    'NOTIFICATION_WORKER_ENABLED': 'false', 'CALENDAR_SYNC_WORKER_ENABLED': 'false',
                    'DATA_DELETION_WORKER_ENABLED': 'false', 'ADMIN_MFA_LOGIN_ENFORCEMENT': 'true',
                    'RATE_LIMIT_ENABLED': 'true', 'RATE_LIMIT_FAIL_OPEN': 'false', 'COOKIE_SECURE': 'true'}.items()]
            self.rows[name] = row
        for name in (*repair.NATIVE, *repair.WORKERS):
            row = self.row(name, 'sha256:' + 'f' * 64)
            if name in repair.WORKERS:
                row['State']['Running'] = False
                row['HostConfig']['RestartPolicy']['Name'] = 'no'
            self.rows[name] = row
        for name, alias in (('supabase-db', 'db'), ('supabase-envoy', 'api-gw'),
                             ('supabase-auth', 'auth'), ('supabase-rest', 'rest'), ('supabase-storage', 'storage')):
            self.rows[name]['NetworkSettings']['Networks']['madar-local-supabase_default'] = {
                'NetworkID': 'native-network', 'Aliases': [alias]}
            self.rows[name]['Config']['Labels']['com.docker.compose.project'] = 'madar-local-supabase'
        for name, key in (('supabase-auth', 'GOTRUE_DB_DATABASE_URL'),
                           ('supabase-rest', 'PGRST_DB_URI'), ('supabase-storage', 'DATABASE_URL')):
            self.rows[name]['Config']['Env'] = [key + '=postgres://fixture@db:5432/postgres']
        self.rows['supabase-envoy']['Mounts'] = [
            {'Source': str(repair.NATIVE_CONFIG / file), 'Destination': destination, 'RW': False}
            for file, destination in [('envoy.yaml', '/etc/envoy/envoy.yaml'),
                ('cds.yaml', '/etc/envoy/cds.yaml'), ('lds.template.yaml', '/etc/envoy/lds.template.yaml')]]
        self.rows['supabase-envoy']['NetworkSettings']['Networks']['madar-supabase-client'] = {
            'NetworkID': 'client-network', 'Aliases': ['madar-supabase']}
        proxy = self.row('madar-release-proxy', 'sha256:' + 'e' * 64)
        proxy['HostConfig']['NetworkMode'] = 'host'
        proxy['Mounts'] = [{'Source': str(repair.CONTROL / 'proxy/nginx.conf'),
                          'Destination': '/etc/nginx/nginx.conf', 'RW': False},
                         {'Source': str(repair.UPSTREAM.parent), 'Destination': '/etc/nginx/madar', 'RW': False}]
        self.rows['madar-release-proxy'] = proxy
        self.calls = []
        self.fail = None
        self.mutated = False

    def row(self, name, image):
        return {'Name': '/' + name, 'Id': repair.sha(name.encode()), 'Image': image,
                'State': {'Running': True, 'Health': {'Status': 'healthy'}},
                'Config': {'Labels': {}, 'Env': []},
                'HostConfig': {'RestartPolicy': {'Name': 'unless-stopped'}}, 'Mounts': [],
                'NetworkSettings': {'Networks': {}, 'Ports': {}}}

    def input_bytes(self):
        return self.inputs

    def names(self):
        return list(self.rows)

    def inspect(self, names):
        return copy.deepcopy({name: self.rows[name] for name in names})

    def frontend_headers(self, name):
        return repair.FRONTEND_HEADERS

    def network(self, name):
        return self.networks[name]

    def schema(self):
        self.calls.append('schema_read_only')
        if self.fail == 'schema':
            raise RuntimeError('schema_not_115')

    def json_http(self, url):
        if url.endswith('/health/ready'):
            return {'ready': True, 'components': {k: 'ok' for k in ('database', 'auth', 'schema', 'storage')}}
        if url.endswith('/health/version'):
            return {'release_sha': 'a' * 40, 'release_slot': 'local-fallback',
                    'schema_compatible_min': 115, 'schema_compatible_max': 115}
        return {'restricted': True, 'business_writes_enabled': self.fail == 'fence'}

    def denied(self, base):
        self.calls.append('write_probe_denied')

    def http_status(self, url):
        self.calls.append('frontend_available')

    def nginx_preflight(self, content, directory):
        self.calls.append(('preflight', content))
        if self.fail == 'preflight' and content == repair.ROUTE:
            raise RuntimeError('invalid_candidate')

    def publish(self, content):
        self.calls.append(('publish', content))
        self.mutated = True
        if self.fail == 'publish' and content == repair.ROUTE:
            raise RuntimeError('publication_failed')
        repair.atomic(repair.UPSTREAM, content, 0o644)

    def reload(self):
        self.calls.append('reload')
        if self.fail in {'reload', 'rollback', 'stop'}:
            if self.fail == 'reload':
                self.fail = None
            raise RuntimeError('reload_failed')

    def await_public(self, packet, directory):
        self.verify_public(packet)

    def verify_public(self, packet):
        self.calls.append('verify_public')
        if self.fail in {'public', 'maintenance_verify'}:
            raise RuntimeError('public_check_failed')

    def verify_maintenance(self):
        self.calls.append('verify_maintenance')
        if self.fail == 'maintenance_verify':
            raise RuntimeError('maintenance_not_observed')

    def stop_proxy(self):
        self.calls.append('stop_proxy')
        if self.fail == 'stop':
            raise RuntimeError('stop_failed')


class EmergencyRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root / 'active-upstreams.conf'
        self.upstream.write_bytes(b'upstream madar_backend_active { server 10.254.202.4:8000; }\n'
                                  b'upstream madar_frontend_active { server 10.254.202.5:8080; }\n')
        self.directory = self.root / 'approved'
        self.directory.mkdir()
        (self.directory / 'attempts').mkdir()
        (self.directory / 'audit').mkdir()
        for item in (patch.object(repair, 'UPSTREAM', self.upstream),
                     patch.object(repair, 'trusted', side_effect=lambda p, **kw: p.read_bytes()),
                     patch.object(repair, 'locks', side_effect=nullcontext)):
            item.start()
            self.addCleanup(item.stop)
        self.runtime = FixtureRuntime()
        self.plan = repair.make_plan(self.runtime)
        (self.directory / 'plan.json').write_bytes(repair.encoded(self.plan))
        (self.directory / 'repair.py').write_bytes(Path(repair.__file__).read_bytes())
        (self.directory / 'authorization.json').write_bytes(repair.encoded({
            'scope': repair.SCOPE, 'plan_digest': repair.digest(self.plan),
            'explicit_operator_approval': True, 'operator_approval_text': 'Approved fixture plan only'}))

    def change_doc(self, name, **fields):
        doc = json.loads(self.runtime.inputs[name])
        doc.update(fields)
        self.runtime.inputs[name] = repair.encoded(doc)

    def test_reversed_addresses_publish_stable_role_listeners(self):
        repair.reconcile(self.runtime, self.directory)
        self.assertEqual(self.upstream.read_bytes(), repair.ROUTE)
        self.assertNotIn(b'10.254.', repair.ROUTE)
        calls = self.runtime.calls
        self.assertLess(calls.index(('preflight', repair.ROUTE)), calls.index(('publish', repair.ROUTE)))
        self.assertLess(calls.index(('publish', repair.ROUTE)), calls.index('reload'))
        self.assertIn('verify_public', calls)
        preimages = list((self.directory / 'attempts').glob('*/previous-upstreams.conf'))
        self.assertEqual(len(preimages), 1)
        self.assertIn(b'10.254.202.4:8000', preimages[0].read_bytes())

    def test_reassigned_ips_are_resolved_again_not_taken_from_plan(self):
        backend = self.runtime.rows[self.runtime.roles['backend']]
        frontend = self.runtime.rows[self.runtime.roles['frontend']]
        backend['NetworkSettings']['Networks'][self.runtime.network_name]['IPAddress'] = '10.254.202.20'
        frontend['NetworkSettings']['Networks'][self.runtime.network_name]['IPAddress'] = '10.254.202.21'
        _, endpoints = repair.verify(self.runtime, self.plan)
        self.assertEqual(endpoints, {'backend': ('10.254.202.20', 8000), 'frontend': ('10.254.202.21', 8080)})
        repair.reconcile(self.runtime, self.directory)
        self.assertEqual(self.upstream.read_bytes(), repair.ROUTE)

    def test_missing_old_run_credentials_are_never_consumed(self):
        self.assertFalse(any('/run/' in str(p) for p in repair.INPUTS.values()))
        with patch.object(repair, 'trusted', side_effect=lambda p, **kw: p.read_bytes() if '/run/' not in str(p) else self.fail('old credentials consumed')):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.plan['old_pass_records_consumed'])

    def test_unauthorized_or_revoked_attempt_does_not_mutate_routing(self):
        original = self.upstream.read_bytes()
        approval = self.directory / 'authorization.json'
        data = approval.read_bytes()
        for content in (b'{}', repair.encoded({'scope': repair.SCOPE, 'explicit_operator_approval': True, 'plan_digest': '0' * 64})):
            approval.write_bytes(content)
            with self.assertRaises(RuntimeError):
                repair.reconcile(self.runtime, self.directory)
            self.assertEqual(self.upstream.read_bytes(), original)
        approval.write_bytes(data)
        (self.directory / 'revoked').touch()
        with self.assertRaisesRegex(RuntimeError, 'revoked'):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def test_modified_image_identity_rejected_before_publication(self):
        self.runtime.rows[self.runtime.roles['backend']]['Image'] = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'image_or_runtime_changed'):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def test_invalid_transaction_state_and_write_authority_rejected(self):
        for name, value in (('local_transaction', {'phase': 'normal'}),
                            ('recovery_transaction', {'phase': 'active'}),
                            ('write_authority', {'mode': 'NORMAL'})):
            original = self.runtime.inputs[name]
            self.change_doc(name, **value)
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                repair.reconcile(self.runtime, self.directory)
            self.assertFalse(self.runtime.mutated)
            self.runtime.inputs[name] = original

    def test_consumer_start_native_failure_and_disabled_fence_rejected(self):
        self.runtime.rows[repair.WORKERS[0]]['State']['Running'] = True
        with self.assertRaisesRegex(RuntimeError, 'consumer_not_inhibited'):
            repair.reconcile(self.runtime, self.directory)
        self.runtime.rows[repair.WORKERS[0]]['State']['Running'] = False
        for reason in ('schema', 'fence'):
            self.runtime.fail = reason
            with self.subTest(reason=reason), self.assertRaises(RuntimeError):
                repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def test_hosted_native_database_or_gateway_routes_are_rejected(self):
        row = self.runtime.rows['supabase-auth']
        original = row['Config']['Env']
        row['Config']['Env'] = ['GOTRUE_DB_DATABASE_URL=postgres://fixture@hosted.invalid:5432/postgres']
        with self.assertRaisesRegex(RuntimeError, 'native_database_destination_invalid'):
            repair.reconcile(self.runtime, self.directory)
        row['Config']['Env'] = original
        self.runtime.inputs['gateway_cds'] = b'address: hosted.invalid\nport_value: 443\n'
        with self.assertRaisesRegex(RuntimeError, 'gateway_not_native'):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def test_mounted_native_configuration_change_revokes_previous_scope(self):
        self.runtime.inputs['gateway_lds'] += b'changed listener'
        with self.assertRaisesRegex(RuntimeError, 'approved_inputs_changed'):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def test_publication_failure_preserves_preimage_and_loads_maintenance(self):
        previous = self.upstream.read_bytes()
        self.runtime.fail = 'publish'
        with self.assertRaisesRegex(RuntimeError, 'failed_closed:maintenance'):
            repair.reconcile(self.runtime, self.directory)
        self.assertEqual(self.upstream.read_bytes(), repair.MAINTENANCE)
        saved = next((self.directory / 'attempts').glob('*/previous-upstreams.conf'))
        self.assertEqual(saved.read_bytes(), previous)
        self.assertEqual(json.loads((self.directory / 'status.json').read_bytes())['state'], 'maintenance')

    def test_failed_rollback_stops_only_proxy_and_records_failure(self):
        self.runtime.fail = 'rollback'
        with self.assertRaisesRegex(RuntimeError, 'failed_closed:proxy_stopped'):
            repair.reconcile(self.runtime, self.directory)
        self.assertIn('stop_proxy', self.runtime.calls)
        self.assertEqual(json.loads((self.directory / 'status.json').read_bytes())['state'], 'proxy_stopped')

    def test_unobserved_maintenance_never_records_successful_compensation(self):
        self.runtime.fail = 'maintenance_verify'
        with self.assertRaisesRegex(RuntimeError, 'failed_closed:proxy_stopped'):
            repair.reconcile(self.runtime, self.directory)
        self.assertIn('verify_maintenance', self.runtime.calls)
        self.assertIn('stop_proxy', self.runtime.calls)

    def test_failed_final_proxy_stop_is_reported_as_critical(self):
        self.runtime.fail = 'stop'
        with self.assertRaisesRegex(RuntimeError, 'critical_manual_proxy_stop_required'):
            repair.reconcile(self.runtime, self.directory)
        self.assertEqual(json.loads((self.directory / 'status.json').read_bytes())['state'], 'proxy_stop_required')
        audits = [json.loads(p.read_bytes())['event'] for p in (self.directory / 'audit').iterdir()]
        self.assertIn('critical_proxy_stop_failed', audits)

    def test_repeated_authorized_reconciliation_preserves_original_state_and_approval(self):
        inputs = copy.deepcopy(self.runtime.inputs)
        approval = (self.directory / 'authorization.json').read_bytes()
        repair.reconcile(self.runtime, self.directory)
        repair.reconcile(self.runtime, self.directory)
        self.assertEqual(self.runtime.inputs, inputs)
        self.assertEqual((self.directory / 'authorization.json').read_bytes(), approval)
        self.assertEqual(len(list((self.directory / 'attempts').iterdir())), 2)
        self.assertEqual(self.upstream.read_bytes(), repair.ROUTE)

    def test_safe_previous_loopback_route_is_restored_on_reload_failure(self):
        self.upstream.write_bytes(repair.ROUTE)
        self.runtime.fail = 'reload'
        with self.assertRaisesRegex(RuntimeError, 'failed_closed:rolled_back'):
            repair.reconcile(self.runtime, self.directory)
        self.assertEqual(self.upstream.read_bytes(), repair.ROUTE)

    def test_changed_code_and_unaccounted_route_are_rejected(self):
        original = (self.directory / 'repair.py').read_bytes()
        (self.directory / 'repair.py').write_bytes(b'changed code')
        with self.assertRaisesRegex(RuntimeError, 'approved_code_changed'):
            repair.reconcile(self.runtime, self.directory)
        (self.directory / 'repair.py').write_bytes(original)
        self.upstream.write_bytes(b'unknown routing')
        with self.assertRaisesRegex(RuntimeError, 'unaccounted_routing_change'):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def test_proxy_boot_gate_does_not_accept_a_stale_ip_route(self):
        (self.directory / 'status.json').write_bytes(repair.encoded({'state': 'active', 'plan_digest': repair.digest(self.plan)}))
        with self.assertRaisesRegex(RuntimeError, 'boot_route_changed'):
            repair.gate(self.directory)
        self.upstream.write_bytes(repair.ROUTE)
        repair.gate(self.directory)
        (self.directory / 'status.json').write_bytes(repair.encoded({'state': 'proxy_stopped', 'plan_digest': repair.digest(self.plan)}))
        with self.assertRaisesRegex(RuntimeError, 'boot_gate_closed'):
            repair.gate(self.directory)

    def test_fresh_installation_needs_explicit_exact_approval_before_runtime_or_files(self):
        with patch.object(repair.os, 'geteuid', return_value=0), patch.object(repair, 'Runtime') as runtime:
            for approved, text in ((repair.digest(self.plan), ''), ('0' * 64, 'approved')):
                with self.assertRaisesRegex(RuntimeError, 'explicit_approval_required'):
                    repair.install(self.plan, approved, text)
            runtime.assert_not_called()

    def test_units_persist_only_narrow_repair_and_enforce_startup_order(self):
        service = repair.service_text(self.directory).decode()
        dropin = repair.dropin_text(self.directory).decode()
        self.assertIn('Before=madar-release-proxy.service', service)
        self.assertIn('WantedBy=multi-user.target', service)
        self.assertIn(' -I -B ', service)
        self.assertIn('ProtectSystem=strict', service)
        self.assertIn('Requires=madar-emergency-routing.service', dropin)
        self.assertIn(' gate --approved-plan ', dropin)
        self.assertIn('ExecStartPre=+/usr/bin/python3', dropin)
        self.assertNotIn('/run/madar', service + dropin)

    def test_read_only_schema_command_has_no_mutation_capability(self):
        runtime = repair.Runtime()
        with patch.object(runtime, 'command', return_value='BEGIN\n115\nROLLBACK') as command:
            runtime.schema()
        sql = command.call_args.kwargs['input']
        self.assertEqual(sql, "BEGIN READ ONLY; SELECT schema_version FROM public.application_schema_state WHERE contract_key='core'; ROLLBACK;")

    def test_role_change_during_verification_is_rejected(self):
        inspect = self.runtime.inspect
        calls = 0
        def changing(names):
            nonlocal calls
            calls += 1
            result = inspect(names)
            if calls == 2:
                result[self.runtime.roles['backend']]['NetworkSettings']['Networks'][self.runtime.network_name]['IPAddress'] = '10.254.202.99'
            return result
        with patch.object(self.runtime, 'inspect', side_effect=changing), self.assertRaisesRegex(RuntimeError, 'during_verification'):
            repair.verify(self.runtime, self.plan)

    def test_relay_resolves_current_target_for_each_new_connection_and_denies_invalid_authority(self):
        # Real loopback relay I/O, isolated from production Docker and ports.
        class EchoHandler(repair.socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(self.request.recv(100))
        echo = repair.Relay(('127.0.0.1', 0), EchoHandler)
        threading.Thread(target=echo.serve_forever, daemon=True).start()
        relay = repair.Relay(('127.0.0.1', 0), repair.Forward)
        relay.runtime, relay.plan, relay.role, relay.directory = self.runtime, self.plan, 'backend', self.directory
        threading.Thread(target=relay.serve_forever, daemon=True).start()
        try:
            with patch.object(repair, 'verify', return_value=({}, {'backend': echo.server_address})) as verify:
                for _ in range(2):
                    with socket.create_connection(relay.server_address, timeout=2) as client:
                        client.sendall(b'opaque-test-bytes')
                        self.assertEqual(client.recv(100), b'opaque-test-bytes')
                self.assertEqual(verify.call_count, 2)
            (self.directory / 'revoked').touch()
            with patch.object(repair, 'verify') as verify:
                with socket.create_connection(relay.server_address, timeout=2) as client:
                    self.assertTrue(client.recv(100).startswith(b'HTTP/1.1 503'))
                verify.assert_not_called()
        finally:
            relay.shutdown()
            relay.server_close()
            echo.shutdown()
            echo.server_close()

    def test_frontend_api_bypasses_static_application_dns_and_preserves_policy(self):
        route = repair.ROUTE.decode()
        self.assertIn('location ^~ /api/ {  proxy_pass http://madar_backend_active/;', route)
        self.assertIn('location = /api/auth/v1/verify', route)
        self.assertIn('access_log off; error_log /dev/stderr crit;', route)
        self.assertIn('127.0.0.1:39402', route)
        self.assertNotIn('backend:8000', route)
        self.assertIn(repair.FRONTEND_HEADERS.decode(), route)
        self.assertIn('/public/legacy/site/$1/$2 break;', route)

    def test_modified_frontend_security_policy_denies_before_mutation(self):
        self.runtime.frontend_headers = lambda name: b'add_header X-Frame-Options SAMEORIGIN;'
        with self.assertRaisesRegex(RuntimeError, 'frontend_security_policy_changed'):
            repair.reconcile(self.runtime, self.directory)
        self.assertFalse(self.runtime.mutated)

    def convergence_fixture(self, failures=0, deadline=20):
        clock = [0.0]
        def budget(limit):
            if clock[0] >= deadline:
                raise repair.VerificationDeadline('deadline')
            return min(limit, deadline-clock[0])
        attempts = [0]
        def active(packet):
            attempts[0] += 1
            if attempts[0] <= failures:
                raise repair.AvailabilityFailure('worker_not_ready')
        self.runtime.budget = budget
        self.runtime.active_route = active
        return clock, attempts

    def test_delayed_worker_activation_and_temporary_502_require_sustained_success(self):
        clock, attempts = self.convergence_fixture(failures=3)
        with patch.object(repair.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(repair.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
            repair.await_convergence(self.runtime, self.plan, self.directory)
        self.assertGreaterEqual(clock[0], 8)
        self.assertGreaterEqual(attempts[0], 6)
        events = [json.loads(p.read_bytes()) for p in (self.directory/'audit').glob('*.json')]
        sustained = next(x for x in events if x['event']=='activation_sustained')
        self.assertGreaterEqual(sustained['successful_rounds'], 3)
        self.assertGreaterEqual(sustained['sustained_seconds'], 5)

    def test_persistent_502_expires_strict_budget_without_pass(self):
        clock, _ = self.convergence_fixture(failures=100, deadline=7)
        with patch.object(repair.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(repair.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
            with self.assertRaises(repair.VerificationDeadline):
                repair.await_convergence(self.runtime, self.plan, self.directory)
        self.assertEqual(clock[0], 7)
        self.assertFalse(any(json.loads(p.read_bytes())['event']=='activation_sustained'
                             for p in (self.directory/'audit').glob('*.json')))

    def test_changed_identity_is_fatal_without_availability_retry(self):
        clock, attempts = self.convergence_fixture()
        self.runtime.rows[next(name for name in self.runtime.rows if name.endswith('-backend'))]['Image'] = 'sha256:'+'f'*64
        with self.assertRaises(RuntimeError):
            repair.await_convergence(self.runtime, self.plan, self.directory)
        self.assertEqual(attempts[0], 0)

    def test_unhealthy_or_missing_fallback_never_reports_public_pass(self):
        for failure in ('schema', 'fence'):
            self.runtime.fail = failure
            self.convergence_fixture()
            with self.assertRaises(RuntimeError):
                repair.await_convergence(self.runtime, self.plan, self.directory)
        self.runtime.fail = None
        self.runtime.rows[next(name for name in self.runtime.rows if name.endswith('-backend'))]['State']['Running'] = False
        with self.assertRaises(RuntimeError):
            repair.await_convergence(self.runtime, self.plan, self.directory)

    def test_real_watchdog_interrupts_blocking_verification_and_restores_alarm(self):
        import time
        runtime = repair.Runtime()
        started = time.monotonic()
        with self.assertRaises(repair.VerificationDeadline):
            with repair.verification_window(runtime, 0.02):
                time.sleep(1)
        self.assertLess(time.monotonic()-started, 0.5)
        self.assertIsNone(runtime.deadline)
        self.assertEqual(repair.signal.getitimer(repair.signal.ITIMER_REAL), (0.0,0.0))

    def test_retry_from_maintenance_preserves_exact_preimage_and_original_evidence(self):
        self.upstream.write_bytes(repair.MAINTENANCE)
        self.plan['previous_upstream_sha256'] = repair.sha(repair.MAINTENANCE)
        self.plan['retry_of'] = repair.LEGACY_DIGEST
        self.plan['legacy_installation'] = {'fixture': 'preserved'}
        (self.directory/'plan.json').write_bytes(repair.encoded(self.plan))
        approval=json.loads((self.directory/'authorization.json').read_bytes())
        approval['plan_digest']=repair.digest(self.plan)
        (self.directory/'authorization.json').write_bytes(repair.encoded(approval))
        original=(self.directory/'authorization.json').read_bytes()
        with patch.object(repair,'legacy_installation') as legacy:
            repair.reconcile(self.runtime,self.directory)
        legacy.assert_called_once_with(self.runtime, {'fixture':'preserved'})
        self.assertEqual((self.directory/'authorization.json').read_bytes(), original)
        self.assertEqual(next((self.directory/'attempts').glob('*/previous-upstreams.conf')).read_bytes(),repair.MAINTENANCE)

    def test_deadline_and_failed_reload_record_sanitized_stage_then_compensate(self):
        for failure,stage in (('reload','nginx_reload'),('deadline','activation_convergence')):
            self.upstream.write_bytes(repair.MAINTENANCE)
            self.runtime.fail='reload' if failure=='reload' else None
            def timeout(*_): raise repair.VerificationDeadline('secret must not be logged')
            self.runtime.await_public = timeout if failure=='deadline' else lambda packet,directory: None
            with self.assertRaisesRegex(RuntimeError,'failed_closed:maintenance'):
                repair.reconcile(self.runtime,self.directory)
            events=[json.loads(p.read_bytes()) for p in (self.directory/'audit').glob('*.json')]
            self.assertTrue(any(x['event']=='reconcile_failure' and x['stage']==stage for x in events))
            self.assertFalse(any('secret must not' in str(x) for x in events))
            self.assertEqual(self.upstream.read_bytes(),repair.MAINTENANCE)

    def test_retry_needs_fresh_source_approval_and_refuses_collision(self):
        with patch.object(repair.os,'geteuid',return_value=0), patch.object(repair,'Runtime') as runtime:
            with self.assertRaisesRegex(RuntimeError,'explicit_approval_required'):
                repair.retry_install(self.plan,repair.digest(self.plan),'')
            runtime.assert_not_called()
        self.assertIn('ExecStartPre=\n',repair.retry_dropin_text(self.directory).decode())
        self.assertNotEqual(repair.RETRY_DROPIN,repair.DROPIN)

    def test_retry_existing_namespace_collision_preserves_every_existing_file(self):
        packet=dict(self.plan,retry_of=repair.LEGACY_DIGEST,legacy_installation={},
                    verification_seconds=repair.VERIFY_SECONDS,compensation_seconds=repair.COMPENSATE_SECONDS,
                    sustained_seconds=repair.SUSTAIN_SECONDS,required_success_rounds=repair.SUCCESS_ROUNDS,
                    previous_upstream_sha256=repair.sha(repair.MAINTENANCE))
        self.upstream.write_bytes(repair.MAINTENANCE)
        installed=self.root/repair.digest(packet)
        installed.mkdir()
        evidence=installed/'authorization.json'
        evidence.write_bytes(b'original evidence')
        with patch.object(repair.os,'geteuid',return_value=0), \
             patch.object(repair,'ROOT',self.root),patch.object(repair,'RETRY_DROPIN',self.root/'91.conf'), \
             patch.object(repair,'legacy_installation'),patch.object(repair,'verify'):
            with self.assertRaisesRegex(RuntimeError,'retry_installation_collision'):
                repair.retry_install(packet,repair.digest(packet),'fresh fixture approval')
        self.assertEqual(evidence.read_bytes(),b'original evidence')
        self.assertEqual(self.upstream.read_bytes(),repair.MAINTENANCE)

    def test_audit_storage_failure_cannot_skip_compensation(self):
        self.runtime.fail='reload'
        original_audit=repair.audit
        def audit(directory,event,**fields):
            if event=='reconcile_failure': raise OSError('disk full')
            original_audit(directory,event,**fields)
        with patch.object(repair,'audit',side_effect=audit):
            with self.assertRaisesRegex(RuntimeError,'failed_closed:maintenance'):
                repair.reconcile(self.runtime,self.directory)
        self.assertEqual(self.upstream.read_bytes(),repair.MAINTENANCE)

    def test_retry_boot_gate_requires_completed_success(self):
        self.plan['retry_of']=repair.LEGACY_DIGEST
        self.plan['legacy_installation']={}
        self.upstream.write_bytes(repair.ROUTE)
        with patch.object(repair,'authorized',return_value=self.plan):
            (self.directory/'status.json').write_bytes(repair.encoded({'state':'installing','plan_digest':repair.digest(self.plan)}))
            with self.assertRaisesRegex(RuntimeError,'proxy_boot_gate_closed'):
                repair.gate(self.directory)

    def test_actual_http_502_is_transient_but_auth_or_malformed_identity_is_fatal(self):
        runtime=repair.Runtime()
        with patch.object(runtime,'fetch',return_value=(502,b'old worker')):
            with self.assertRaises(repair.AvailabilityFailure):runtime.json_http('http://loopback/health/version')
            with self.assertRaises(repair.AvailabilityFailure):runtime.denied('http://loopback')
        with patch.object(runtime,'fetch',return_value=(401,b'unauthorized')):
            with self.assertRaises(RuntimeError) as caught:runtime.json_http('http://loopback/health/version')
            self.assertNotIsInstance(caught.exception,repair.AvailabilityFailure)
        with patch.object(runtime,'fetch',return_value=(200,b'not a valid identity')):
            with self.assertRaises(json.JSONDecodeError):runtime.json_http('http://loopback/health/version')

    def test_missing_or_unready_fallback_is_fatal_before_active_route_probe(self):
        _,attempts=self.convergence_fixture()
        with patch.object(self.runtime,'inspect',side_effect=RuntimeError('missing fallback')):
            with self.assertRaises(RuntimeError):repair.await_convergence(self.runtime,self.plan,self.directory)
        original=self.runtime.json_http
        self.runtime.json_http=lambda url: {'ready':False,'components':{}} if url.endswith('/health/ready') else original(url)
        with self.assertRaisesRegex(RuntimeError,'fallback_readiness_failed'):
            repair.await_convergence(self.runtime,self.plan,self.directory)
        self.assertEqual(attempts[0],0)
