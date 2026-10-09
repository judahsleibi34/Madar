"""Independent, operator-approved routing repair for an existing local rollback.

Standalone stdlib package: never imports the old controller, consumes its PASS
records, restores /run authority, grants writes, starts consumers or executes SQL
outside BEGIN READ ONLY. Production paths and destinations are fixed. Tests use
injected adapters; the CLI exposes no production path/driver override.
"""
from __future__ import annotations

import sys
if __name__ == '__main__' and (not sys.flags.isolated or not sys.flags.dont_write_bytecode):
    raise SystemExit('isolated_source_only_interpreter_required')

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import ipaddress
import json
import os
import pwd
from pathlib import Path
import re
import select
import signal
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

ROOT = Path('/var/lib/madar-control-plane/emergency-routing')
STATE = Path('/var/lib/madar/releases')
CONTROL = Path('/opt/madar/control-plane/deployment')
RECOVERY = Path('/var/lib/madar-control-plane/provider402')
LOCAL = Path('/var/lib/madar-control-plane/local-provider-transition')
UPSTREAM = Path('/var/lib/madar/proxy/active-upstreams.conf')
UNIT = Path('/etc/systemd/system/madar-emergency-routing.service')
DROPIN = Path('/etc/systemd/system/madar-release-proxy.service.d/90-emergency-routing.conf')
SCOPE = 'restricted-local-fallback-routing-only-v1'
PORTS = {'backend': 29401, 'frontend': 39401}
LEGACY_DIGEST = '87842c3173fe1d6c479f5186d3d0ce59aedbf48cf46515282a925a8cd8365fb6'
LEGACY_CODE = '37c0277da599c28e2257eaa93d825dcf46cd87c0fd20aafe3bea690a1f3e07f0'
RETRY_DROPIN = DROPIN.with_name('91-emergency-routing-retry.conf')
VERIFY_SECONDS = 180
COMPENSATE_SECONDS = 60
SUSTAIN_SECONDS = 5
SUCCESS_ROUNDS = 3
ROLES = ('backend', 'frontend')
NATIVE = ('supabase-db', 'supabase-envoy', 'supabase-auth', 'supabase-rest', 'supabase-storage')
NATIVE_CONFIG = Path('/opt/madar/local-supabase/volumes/api/envoy')
TEXT_INPUTS = {'controller_sha', 'nginx', 'proxy_compose', 'gateway_bootstrap', 'gateway_cds', 'gateway_lds'}
WORKERS = tuple(f'madar-{slot}-{kind}-worker' for slot in ('blue', 'green')
                for kind in ('notification', 'calendar-sync', 'data-deletion'))
INPUTS = {
    'recovery_contract': RECOVERY / 'contract.json',
    'schema_contract': RECOVERY / 'schema-contract.json',
    'local_contract': LOCAL / 'contract.json',
    'local_transaction': LOCAL / 'transaction.json',
    'write_authority': LOCAL / 'write-authority/authority.json',
    'recovery_transaction': STATE / 'provider-recovery.json',
    'fallback': STATE / 'provider-recovery-fallback.json',
    'traffic': STATE / 'provider-recovery-traffic.json',
    'workers': STATE / 'worker-ownership.json',
    'release_state': STATE / 'state.json',
    'controller_sha': CONTROL / 'CONTROL_PLANE_SOURCE_SHA',
    'nginx': CONTROL / 'proxy/nginx.conf',
    'proxy_compose': CONTROL / 'proxy/docker-compose.yml',
    'gateway_bootstrap': NATIVE_CONFIG / 'envoy.yaml',
    'gateway_cds': NATIVE_CONFIG / 'cds.yaml',
    'gateway_lds': NATIVE_CONFIG / 'lds.template.yaml',
}
# Preserve the independently inspected registered frontend policy on bypassed
# backend routes. Verify exact rendered policy before every forwarded connection.
FRONTEND_HEADERS = b"""add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data: https:; connect-src 'self' 'self'; media-src 'self' blob: https:; frame-src 'self' https://*.madarportal.com https://www.youtube.com https://www.youtube-nocookie.com; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; manifest-src 'self'" always;
add_header Strict-Transport-Security "max-age=31536000" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=()" always;
add_header X-Frame-Options "DENY" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
"""
FORWARD_HEADERS = b"""proxy_http_version 1.1;
proxy_request_buffering off;
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $madar_forwarded_proto;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $madar_connection_upgrade;
proxy_set_header X-Request-ID $http_x_request_id;
"""
# The intermediate frontend server prevents the application's static backend
# DNS cache from becoming another stale-IP route after backend restart.
FRONTEND_ROUTER_PORT = 39402
ROUTE = (f'upstream madar_backend_active {{ server 127.0.0.1:{PORTS["backend"]}; }}\n'
         f'upstream madar_emergency_frontend {{ server 127.0.0.1:{PORTS["frontend"]}; }}\n'
         f'upstream madar_frontend_active {{ server 127.0.0.1:{FRONTEND_ROUTER_PORT}; }}\n'
         f'server {{ listen 127.0.0.1:{FRONTEND_ROUTER_PORT};\n').encode()
for match, destination, rewrite in (
    ('= /api/auth/v1/verify', 'http://madar_backend_active/auth/v1/verify', ''),
    ('^~ /api/', 'http://madar_backend_active/', ''),
    ('^~ /uploads/', 'http://madar_backend_active', ''),
    ('~ "^/site/([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:/(.*))?/?$"',
     'http://madar_backend_active', 'rewrite ^/site/([^/]+)(?:/(.*))?/?$ /public/legacy/site/$1/$2 break;'),
    ('~ "^/store/([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:/(.*))?/?$"',
     'http://madar_backend_active', 'rewrite ^/store/([^/]+)(?:/(.*))?/?$ /public/legacy/store/$1/$2 break;'),
    ('~ "^/forms/([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)/([^/]+)/?$"',
     'http://madar_backend_active', 'rewrite ^/forms/([^/]+)/([^/]+)/?$ /public/legacy/forms/$1/$2 break;'),
):
    ROUTE += (f'location {match} {{ {rewrite} proxy_pass {destination};\n').encode()
    ROUTE += FRONTEND_HEADERS + FORWARD_HEADERS
    if match == '= /api/auth/v1/verify':
        ROUTE += b'access_log off; error_log /dev/stderr crit;\n'
    ROUTE += b'}\n'
ROUTE += b'location = /api { return 308 /api/; }\nlocation / { proxy_pass http://madar_emergency_frontend;\n' + FORWARD_HEADERS + b'}\n}\n'
MAINTENANCE = b'''upstream madar_backend_active { server 127.0.0.1:29402; }
upstream madar_frontend_active { server 127.0.0.1:29402; }
server { listen 127.0.0.1:29402; access_log off; location / { return 503; } }
'''
DENIED = (b'HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\n'
          b'Cache-Control: no-store\r\nConnection: close\r\nContent-Length: 25\r\n\r\n'
          b'Madar recovery unavailable')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True).encode())


def now():
    return datetime.now(timezone.utc).isoformat()


def trusted(path, *, private=False):
    """Trust executable/authorization hierarchy only when root owns every part."""
    require(path.is_absolute(), 'path_not_absolute')
    for item in (path, *path.parents):
        st = item.lstat()
        require(not item.is_symlink() and st.st_uid == 0 and not st.st_mode & 0o022,
                'protected_path_untrusted')
    require(path.is_file(), 'protected_file_missing')
    if private:
        require(not path.stat().st_mode & 0o077, 'protected_file_not_private')
    return path.read_bytes()


def atomic(path, content, mode=0o600):
    require(not path.is_symlink(), 'atomic_destination_symlink')
    fd, tmp = tempfile.mkstemp(prefix='.emergency-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def exclusive(path, content, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


@contextmanager
def locks():
    # Same order as existing root controller: deploy, then runtime mutation.
    opened = []
    try:
        for name in ('deploy.lock', 'runtime-mutation.lock'):
            path = STATE / name
            require(path.is_file() and not path.is_symlink(), 'existing_lock_missing')
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            opened.append(fd)
        yield
    finally:
        for fd in reversed(opened):
            os.close(fd)


class AvailabilityFailure(RuntimeError):
    pass


class VerificationDeadline(RuntimeError):
    pass


@contextmanager
def verification_window(runtime, seconds):
    # Main-thread hard wall-clock watchdog covers commands, slow HTTP reads and
    # nested checks; each I/O also gets the remaining monotonic budget.
    require(threading.current_thread() is threading.main_thread(), 'deadline_requires_main_thread')
    previous = signal.getsignal(signal.SIGALRM)
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'existing_alarm_refused')
    def expired(*_):
        raise VerificationDeadline('verification_deadline_expired')
    signal.signal(signal.SIGALRM, expired)
    runtime.deadline = time.monotonic() + seconds
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        runtime.deadline = None


def request(url, *, method='GET', timeout=8):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    req = urllib.request.Request(url, method=method, data=b'{}' if method == 'POST' else None,
                                 headers={'User-Agent': 'Madar-emergency-routing/1'})
    try:
        with opener.open(req, timeout=timeout) as response:
            return response.status, response.read(65536)
    except urllib.error.HTTPError as error:
        return error.code, error.read(65536)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise AvailabilityFailure('http_temporarily_unavailable') from None


class Runtime:
    deadline = None

    def budget(self, maximum):
        remaining = maximum if self.deadline is None else min(maximum, self.deadline - time.monotonic())
        if remaining <= 0:
            raise VerificationDeadline('verification_deadline_expired')
        return remaining

    def fetch(self, url, *, method='GET'):
        return request(url, method=method, timeout=self.budget(8))

    def command(self, args, *, input=None):
        if args[0] == 'docker':
            args = ['docker', '--host', 'unix:///var/run/docker.sock', *args[1:]]
        result = subprocess.run(args, input=input, text=True, capture_output=True,
                                timeout=self.budget(30), env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                                                'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'})
        require(result.returncode == 0, 'command_failed:' + args[0])
        return result.stdout.strip()

    def inspect(self, names):
        return {row['Name'].lstrip('/'): row for row in json.loads(self.command(['docker', 'inspect', *names]))}

    def input_bytes(self):
        result = {}
        for key, path in INPUTS.items():
            if key.startswith('gateway_'):
                operator = pwd.getpwnam('madar').pw_uid
                for part in (path, *path.parents):
                    st = part.lstat()
                    require(not part.is_symlink() and st.st_uid in {0, operator} and
                            not st.st_mode & 0o002 and (not st.st_mode & 0o020 or st.st_uid == operator),
                            'native_config_untrusted')
                require(path.is_file(), 'native_config_missing')
                result[key] = path.read_bytes()
            elif path.is_relative_to(RECOVERY) or path.is_relative_to(LOCAL) or path.is_relative_to(CONTROL):
                result[key] = trusted(path, private=path.is_relative_to(RECOVERY) or path == INPUTS['local_contract'] or path == INPUTS['local_transaction'])
            else:
                require(path.is_file() and not path.is_symlink(), 'runtime_record_missing')
                result[key] = path.read_bytes()
        return result

    def frontend_headers(self, name):
        return self.command(['docker', 'exec', name, 'cat', '/etc/nginx/conf.d/includes/security_headers.conf']).encode()

    def network(self, name):
        return json.loads(self.command(['docker', 'network', 'inspect', name]))[0]

    def schema(self):
        sql = "BEGIN READ ONLY; SELECT schema_version FROM public.application_schema_state WHERE contract_key='core'; ROLLBACK;"
        value = self.command(['docker', 'exec', '-i', 'supabase-db', 'psql', '-X', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'], input=sql)
        require(value.splitlines() == ['BEGIN', '115', 'ROLLBACK'], 'schema_not_115')

    def json_http(self, url):
        status, data = self.fetch(url)
        if status in {502, 503, 504}:
            raise AvailabilityFailure('http_temporarily_unavailable')
        require(status == 200, 'http_unavailable')
        return json.loads(data)

    def http_status(self, url):
        status, _ = self.fetch(url)
        if status in {502, 503, 504}:
            raise AvailabilityFailure('http_temporarily_unavailable')
        require(status == 200, 'http_unavailable')

    def denied(self, base):
        status, data = self.fetch(base + '/__madar_emergency_write_fence_probe__', method='POST')
        if status in {502, 504}:
            raise AvailabilityFailure('write_probe_transport_pending')
        require(status == 503 and json.loads(data).get('detail', {}).get('code') == 'provider_recovery_read_only', 'business_write_fence_failed')

    def names(self):
        return self.command(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()

    def nginx_preflight(self, content, directory):
        # Test the candidate BEFORE replacing the active file. Only a private
        # transaction-owned config is written. No Docker resource is created.
        main = trusted(INPUTS['nginx'])
        require(sha(main) == self.expected_nginx_sha256, 'approved_nginx_changed')
        needle = b'include /etc/nginx/madar/active-upstreams.conf;'
        require(main.count(needle) == 1, 'nginx_include_contract_changed')
        candidate = main.replace(needle, content)
        p = directory / ('candidate-' + uuid.uuid4().hex + '.conf')
        exclusive(p, candidate)
        inside = '/tmp/madar-emergency-preflight-' + uuid.uuid4().hex + '.conf'
        self.command(['docker', 'exec', '-i', 'madar-release-proxy', 'sh', '-c',
                      'umask 077; cat > "$1"; nginx -t -c "$1"; result=$?; rm -f "$1"; exit "$result"', 'sh', inside], input=candidate.decode())

    def publish(self, content):
        atomic(UPSTREAM, content, 0o644)

    def reload(self):
        self.command(['docker', 'exec', 'madar-release-proxy', 'nginx', '-t'])
        self.command(['docker', 'exec', 'madar-release-proxy', 'nginx', '-s', 'reload'])

    def stop_proxy(self):
        # Persistent fail-closed fallback if even maintenance cannot be loaded.
        self.command(['docker', 'update', '--restart=no', 'madar-release-proxy'])
        self.command(['docker', 'stop', 'madar-release-proxy'])

    def verify_maintenance(self):
        for _ in range(20):
            if all(self.fetch(f'http://127.0.0.1:{port}/')[0] == 503 for port in (3000, 8001)):
                return
            time.sleep(0.25)
        raise RuntimeError('maintenance_not_observed')

    def verify_public(self, plan):
        self.http_status('http://127.0.0.1:3000/')
        self.http_status('http://127.0.0.1:8001/')
        self.http_status('https://madarportal.com/')
        self.http_status('https://api.madarportal.com/')
        for base in ('http://127.0.0.1:8001', 'https://api.madarportal.com',
                     'http://127.0.0.1:3000/api', 'https://madarportal.com/api'):
            require(self.json_http(base + '/health/ready').get('ready') is True, 'public_readiness_failed')
            version = self.json_http(base + '/health/version')
            require(version.get('release_sha') == plan['source_sha'] and
                    version.get('release_slot') == 'local-fallback' and
                    version.get('schema_compatible_min') == version.get('schema_compatible_max') == 115, 'public_identity_failed')
            require(self.json_http(base + '/health/recovery') == {'restricted': True, 'business_writes_enabled': False}, 'public_fence_failed')
            self.denied(base)
        proxy = self.inspect(['madar-release-proxy'])['madar-release-proxy']
        if proxy['State'].get('Health', {}).get('Status') != 'healthy':
            raise AvailabilityFailure('proxy_health_pending')

    def active_route(self, plan):
        require(UPSTREAM.read_bytes() == ROUTE, 'published_route_integrity_failed')
        # This listener is absent in maintenance; a correct identity response
        # proves that a worker has loaded the intended frontend router. nginx -T
        # alone reads disk and cannot prove the running generation is active.
        version = self.json_http(f'http://127.0.0.1:{FRONTEND_ROUTER_PORT}/api/health/version')
        require(version.get('release_sha') == plan['source_sha'] and
                version.get('release_slot') == 'local-fallback' and
                version.get('schema_compatible_min') == version.get('schema_compatible_max') == 115,
                'active_route_identity_failed')

    def await_public(self, plan, directory):
        await_convergence(self, plan, directory)



def spec(row):
    # Hash secret-bearing configuration without recording its values. Exclude
    # ephemeral IPs and State: approved restarts can change both safely.
    return digest({k: row[k] for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')})


def identities(inputs):
    documents = {key: json.loads(value) for key, value in inputs.items()
                 if key not in TEXT_INPUTS}
    contract = documents['recovery_contract']
    source = contract['sha']
    require(re.fullmatch(r'[0-9a-f]{40}', source), 'source_identity_invalid')
    require(inputs['controller_sha'].decode().strip() == source, 'installed_source_changed')
    schema = documents['schema_contract']
    require(schema.get('migration_policy') == 'none' and not schema.get('migration_manifest') and
            schema['schema'] == {'compatible_min': 115, 'compatible_max': 115, 'target': 115,
                                'migration_class': 'none', 'rollback_compatible_min': 115,
                                'rollback_compatible_max': 115}, 'schema_contract_invalid')
    clusters = re.findall(rb'^\s*address:\s*([a-z0-9.-]+)\s*\n\s*port_value:\s*([0-9]+)', inputs['gateway_cds'], re.M)
    require(dict(clusters) == {b'auth': b'9999', b'rest': b'3000', b'realtime-dev.supabase-realtime': b'4000',
                              b'storage': b'5000', b'functions': b'9000', b'meta': b'8080', b'studio': b'3000'} and
            len(clusters) == 7, 'gateway_not_native')
    context = digest(contract)
    recovery = documents['recovery_transaction']
    local = documents['local_transaction']
    local_contract = documents['local_contract']
    require(recovery.get('phase') == local.get('phase') == 'local_rollback_active', 'transaction_state_invalid')
    require(recovery.get('context_digest') == context and local_contract['recovery_context'] == context and
            local['contract_digest'] == digest(local_contract), 'transaction_identity_invalid')
    require(recovery.get('sha') == local.get('sha') == local_contract['sha'] == source and
            recovery.get('schema') == local.get('schema') == 115 and
            recovery.get('restore_database_on_rollback') is False and local.get('database_restore') is False and
            local.get('normal_writes_ever_enabled') is False, 'transaction_scope_invalid')
    require(recovery.get('worker_owner') == 'RECOVERY' and
            recovery.get('migration_policy') == local.get('migration_policy') == 'none', 'transaction_authority_invalid')
    fallback = documents['fallback']
    images = contract['images']
    require(set(images) == set(ROLES) and all(re.fullmatch(r'sha256:[0-9a-f]{64}', x) for x in images.values()), 'image_contract_invalid')
    require(fallback.get('sha') == source and fallback.get('images') == images == local_contract['images'] == local['images'] and
            fallback.get('schema') == 115 and fallback.get('database_restore') is False and
            fallback.get('profile') == 'provider402-signin' and fallback.get('network') == 'madar-supabase-client' and
            fallback.get('supabase_url') == 'http://madar-supabase:8000' and
            digest(fallback) == contract['rollback_runtime_digest'], 'fallback_registration_invalid')
    authority = documents['write_authority']
    require(authority == {'version': 1, 'schema': 115, 'release_sha': source,
                         'contract_digest': digest(local_contract), 'mode': 'READ_ONLY'}, 'write_authority_invalid')
    worker = documents['workers']
    require(worker.get('owner') == 'RECOVERY' and worker.get('generation') == context and
            worker['candidate']['sha'] == source, 'worker_authority_invalid')
    require(documents['traffic'] == {'database_restore': False, 'provider': 'local', 'schema': 115,
                                   'sha': source, 'slot': 'local-fallback'}, 'traffic_identity_invalid')
    # Derive names from immutable preparation INPUTS, not its disputed PASS file.
    fields = dict(contract)
    fields.pop('rehearsal_digest')
    binding = digest({'contract': fields, 'schema_contract': schema})
    prefix = 'madar-provider402-rehearsal-' + binding[:12] + '-candidate-local-fallback'
    return source, images, {role: prefix + '-' + role for role in ROLES}, prefix + '-runtime'


def verify(runtime, plan=None):
    inputs = runtime.input_bytes()
    source, images, names, network_name = identities(inputs)
    hashes = {k: sha(v) for k, v in inputs.items()}
    if plan is not None:
        require(plan.get('scope') == SCOPE and plan.get('source_sha') == source and
                plan.get('input_hashes') == hashes, 'approved_inputs_changed')
    all_names = runtime.names()
    consumers = [n for n in all_names if n.startswith('madar-') and
                 any(k + '-worker' in n for k in ('notification', 'calendar-sync', 'data-deletion'))]
    require(set(WORKERS).issubset(all_names), 'six_consumers_missing')
    selected = [*names.values(), *NATIVE, 'madar-release-proxy', *consumers]
    rows = runtime.inspect(selected)
    for name in consumers:
        row = rows[name]
        require(not row['State']['Running'] and row['HostConfig']['RestartPolicy']['Name'] == 'no', 'consumer_not_inhibited')
    for name in NATIVE:
        row = rows[name]
        require(row['State']['Running'] and row['State'].get('Health', {}).get('Status') == 'healthy', 'native_provider_unhealthy')
        require(all(b['HostIp'] == '127.0.0.1' for bindings in row['NetworkSettings']['Ports'].values() for b in bindings or []), 'native_provider_public_port')
    native_network = rows['supabase-db']['NetworkSettings']['Networks']['madar-local-supabase_default']
    require('db' in native_network.get('Aliases', []), 'native_database_alias_invalid')
    for name, alias, key in (('supabase-auth', 'auth', 'GOTRUE_DB_DATABASE_URL'),
                             ('supabase-rest', 'rest', 'PGRST_DB_URI'),
                             ('supabase-storage', 'storage', 'DATABASE_URL')):
        row = rows[name]
        require(row['Config'].get('Labels', {}).get('com.docker.compose.project') == 'madar-local-supabase', 'native_service_identity_invalid')
        attachment = row['NetworkSettings']['Networks']['madar-local-supabase_default']
        require(attachment['NetworkID'] == native_network['NetworkID'] and alias in attachment.get('Aliases', []), 'native_service_network_invalid')
        env = dict(item.split('=', 1) for item in row['Config']['Env'])
        database = urlsplit(env.get(key, ''))
        require(database.scheme in {'postgres', 'postgresql'} and database.hostname == 'db' and
                database.port == 5432 and database.path == '/postgres', 'native_database_destination_invalid')
    gateway = rows['supabase-envoy']
    require(gateway['NetworkSettings']['Networks']['madar-local-supabase_default']['NetworkID'] == native_network['NetworkID'], 'gateway_native_network_invalid')
    for file, destination in (('envoy.yaml', '/etc/envoy/envoy.yaml'),
                              ('cds.yaml', '/etc/envoy/cds.yaml'), ('lds.template.yaml', '/etc/envoy/lds.template.yaml')):
        require(any(m['Source'] == str(NATIVE_CONFIG / file) and m['Destination'] == destination and not m['RW'] for m in gateway['Mounts']), 'gateway_native_mount_invalid')
    network = runtime.network(network_name)
    client = runtime.network('madar-supabase-client')
    require(network.get('Internal') is True and client.get('Internal') is True and
            network.get('Driver') == client.get('Driver') == 'bridge', 'network_not_internal')
    endpoints = {}
    for role in ROLES:
        row = rows[names[role]]
        require(row['Image'] == images[role] and row['State']['Running'], 'fallback_image_or_runtime_changed')
        labels = row['Config'].get('Labels', {})
        require(labels.get('org.opencontainers.image.revision') == source and
                labels.get('com.madar.recovery.profile') == 'provider402-signin', 'fallback_source_or_profile_changed')
        nets = row['NetworkSettings']['Networks']
        require(set(nets) == ({network_name, 'madar-supabase-client'} if role == 'backend' else {network_name}), 'fallback_network_roles_changed')
        require(nets[network_name]['NetworkID'] == network['Id'] and role in nets[network_name].get('Aliases', []), 'fallback_role_invalid')
        ip = nets[network_name]['IPAddress']
        require(isinstance(ip, str) and ipaddress.ip_address(ip).version == 4 and ipaddress.ip_address(ip).is_private, 'fallback_ip_not_private')
        require(not any(row['NetworkSettings']['Ports'].values()), 'fallback_public_binding')
        endpoints[role] = (ip, 8000 if role == 'backend' else 8080)
        if role == 'backend':
            env = dict(item.split('=', 1) for item in row['Config']['Env'])
            expected = {'SUPABASE_URL': 'http://madar-supabase:8000', 'MADAR_RELEASE_SHA': source,
                        'MADAR_RELEASE_SLOT': 'local-fallback', 'MADAR_RECOVERY_PROFILE': 'provider402-signin',
                        'NOTIFICATION_WORKER_ENABLED': 'false', 'CALENDAR_SYNC_WORKER_ENABLED': 'false',
                        'DATA_DELETION_WORKER_ENABLED': 'false', 'ADMIN_MFA_LOGIN_ENFORCEMENT': 'true',
                        'RATE_LIMIT_ENABLED': 'true', 'RATE_LIMIT_FAIL_OPEN': 'false', 'COOKIE_SECURE': 'true'}
            require(all(env.get(k) == v for k, v in expected.items()), 'fallback_security_or_provider_changed')
            require(nets['madar-supabase-client']['NetworkID'] == client['Id'] and
                    rows['supabase-envoy']['NetworkSettings']['Networks']['madar-supabase-client']['NetworkID'] == client['Id'] and
                    'madar-supabase' in rows['supabase-envoy']['NetworkSettings']['Networks']['madar-supabase-client'].get('Aliases', []), 'local_provider_connectivity_changed')
    require(runtime.frontend_headers(names['frontend']).strip() == FRONTEND_HEADERS.strip(), 'frontend_security_policy_changed')
    require(endpoints['backend'][0] != endpoints['frontend'][0], 'fallback_roles_collide')
    proxy = rows['madar-release-proxy']
    match = re.search(rb'image:\s*(nginx:alpine@sha256:[0-9a-f]{64})', inputs['proxy_compose'])
    require(match is not None and proxy['Image'] == match[1].decode().split('@')[1] and
            proxy['State']['Running'] and proxy['HostConfig']['NetworkMode'] == 'host', 'proxy_identity_invalid')
    require(any(m['Source'] == str(CONTROL / 'proxy/nginx.conf') and m['Destination'] == '/etc/nginx/nginx.conf' and not m['RW'] for m in proxy['Mounts']) and
            any(m['Source'] == str(UPSTREAM.parent) and m['Destination'] == '/etc/nginx/madar' and not m['RW'] for m in proxy['Mounts']), 'proxy_mount_invalid')
    runtime.schema()
    base = 'http://%s:%d' % endpoints['backend']
    ready = runtime.json_http(base + '/health/ready')
    version = runtime.json_http(base + '/health/version')
    require(ready.get('ready') is True and all(ready.get('components', {}).get(k) == 'ok' for k in ('database', 'auth', 'schema', 'storage')), 'fallback_readiness_failed')
    require(version.get('release_sha') == source and version.get('release_slot') == 'local-fallback' and
            version.get('schema_compatible_min') == version.get('schema_compatible_max') == 115, 'fallback_version_invalid')
    require(runtime.json_http(base + '/health/recovery') == {'restricted': True, 'business_writes_enabled': False}, 'fallback_unfenced')
    runtime.denied(base)
    runtime.http_status('http://%s:%d/' % endpoints['frontend'])
    runtime_ids = {name: {'id': row['Id'], 'image': row['Image'], 'spec_sha256': spec(row)} for name, row in rows.items()}
    network_ids = {network_name: network['Id'], 'madar-supabase-client': client['Id']}
    if plan is not None:
        require(plan.get('runtimes') == runtime_ids and plan.get('networks') == network_ids, 'approved_runtime_changed')
    # Re-read addresses after health checks; return no stale health-checked mapping.
    latest = runtime.inspect(list(names.values()))
    for role in ROLES:
        require(spec(latest[names[role]]) == spec(rows[names[role]]) and
                latest[names[role]]['State']['Running'] and
                latest[names[role]]['NetworkSettings']['Networks'][network_name]['IPAddress'] == endpoints[role][0], 'runtime_changed_during_verification')
    return {'source_sha': source, 'input_hashes': hashes, 'runtimes': runtime_ids,
            'networks': network_ids, 'observed_endpoints': {k: list(v) for k, v in endpoints.items()}}, endpoints


def make_plan(runtime):
    observed, _ = verify(runtime)
    return dict(observed, version=1, scope=SCOPE, nonce=uuid.uuid4().hex,
                created_at=now(), code_sha256=sha(Path(__file__).read_bytes()),
                previous_upstream_sha256=sha(UPSTREAM.read_bytes()),
                route_sha256=sha(ROUTE), automatic_scope='same-approved-identities-until-revoked-or-bound-state-changes',
                old_pass_records_consumed=False)


def authorized(directory):
    packet = json.loads(trusted(directory / 'plan.json', private=True))
    approval = json.loads(trusted(directory / 'authorization.json', private=True))
    require(approval.get('scope') == SCOPE and approval.get('plan_digest') == digest(packet) and
            approval.get('explicit_operator_approval') is True and bool(approval.get('operator_approval_text')),
            'emergency_authorization_missing_or_invalid')
    require(not (directory / 'revoked').exists(), 'emergency_authorization_revoked')
    require(sha(trusted(directory / 'repair.py')) == packet['code_sha256'], 'approved_code_changed')
    require(packet.get('version') == 1 and packet.get('route_sha256') == sha(ROUTE) and
            packet.get('old_pass_records_consumed') is False and packet.get('scope') == SCOPE,
            'emergency_scope_invalid')
    return packet


def audit(directory, event, **fields):
    path = directory / 'audit' / (str(time.time_ns()) + '-' + uuid.uuid4().hex + '.json')
    exclusive(path, encoded(dict(event=event, recorded_at=now(), **fields)))


def failure_audit(directory, event, **fields):
    # Audit storage failure must never prevent the safe compensation operation.
    try:
        audit(directory, event, **fields)
    except OSError:
        pass


def await_convergence(runtime, packet, directory):
    first_success = None
    consecutive = 0
    rounds = 0
    started = time.monotonic()
    while True:
        runtime.budget(1)
        rounds += 1
        # Genuine identity/state/fence failures are never retried. Only explicit
        # availability failures from HTTP/connectivity are transient.
        verify(runtime, packet)
        authorized(directory)
        if 'retry_of' in packet:
            legacy_installation(runtime, packet['legacy_installation'], live=False)
        try:
            runtime.active_route(packet)
            runtime.verify_public(packet)
        except AvailabilityFailure as error:
            consecutive, first_success = 0, None
            audit(directory, 'activation_pending', round=rounds,
                  exception_type=type(error).__name__, elapsed_seconds=round(time.monotonic()-started, 3))
        else:
            consecutive += 1
            if first_success is None:
                first_success = time.monotonic()
            if consecutive >= SUCCESS_ROUNDS and time.monotonic()-first_success >= SUSTAIN_SECONDS:
                audit(directory, 'activation_sustained', rounds=rounds,
                      successful_rounds=consecutive, sustained_seconds=round(time.monotonic()-first_success, 3),
                      elapsed_seconds=round(time.monotonic()-started, 3))
                return
        time.sleep(runtime.budget(1))


def old_route_safe(previous, endpoints):
    expected = (f'upstream madar_backend_active {{ server {endpoints["backend"][0]}:8000; }}\n'
                f'upstream madar_frontend_active {{ server {endpoints["frontend"][0]}:8080; }}\n').encode()
    return previous == ROUTE or previous == expected


def reconcile(runtime, directory):
    packet = authorized(directory)
    runtime.expected_nginx_sha256 = packet['input_hashes']['nginx']
    with locks():
        if 'retry_of' in packet:
            legacy_installation(runtime, packet['legacy_installation'])
        _, endpoints = verify(runtime, packet)
        previous = UPSTREAM.read_bytes()
        require(sha(previous) in {packet['previous_upstream_sha256'], sha(ROUTE), sha(MAINTENANCE)}, 'unaccounted_routing_change')
        transaction = directory / 'attempts' / (str(time.time_ns()) + '-' + uuid.uuid4().hex)
        transaction.mkdir(mode=0o700)
        exclusive(transaction / 'previous-upstreams.conf', previous)
        exclusive(transaction / 'inputs-before.json', encoded(packet['input_hashes']))
        audit(directory, 'reconcile_started', transaction=transaction.name, endpoints=endpoints)
        started = time.monotonic()
        stage = 'candidate_validation'
        try:
            with verification_window(runtime, VERIFY_SECONDS):
                runtime.nginx_preflight(ROUTE, transaction)
                stage = 'prepublication_integrity'
                # Final fresh identity/address checks immediately before publication.
                _, endpoints = verify(runtime, packet)
                authorized(directory)
                stage = 'publication'
                runtime.publish(ROUTE)
                stage = 'nginx_reload'
                runtime.reload()
                stage = 'activation_convergence'
                runtime.await_public(packet, directory)
                stage = 'final_integrity'
                verify(runtime, packet)
                authorized(directory)
                atomic(directory / 'status.json', encoded({'state': 'active', 'plan_digest': digest(packet), 'route_sha256': sha(ROUTE)}))
                audit(directory, 'reconcile_complete', transaction=transaction.name,
                      endpoints=endpoints, public_frontend=200, public_backend=200,
                      proxy_health='healthy', business_writes=False, consumers='stopped', database_restore=False)
                return
        except Exception as failure:
            failure_audit(directory, 'reconcile_failure', stage=stage, exception_type=type(failure).__name__,
                  elapsed_seconds=round(time.monotonic()-started, 3), verification_deadline_seconds=VERIFY_SECONDS)
            # Restore a pre-image only if its target is independently safe now.
            # The known reversed outage pre-image is preserved but never trusted.
            try:
                with verification_window(runtime, COMPENSATE_SECONDS):
                    try:
                        _, current = verify(runtime, packet)
                        target = previous if old_route_safe(previous, current) else MAINTENANCE
                    except Exception:
                        target = MAINTENANCE
                    runtime.nginx_preflight(target, transaction)
                    runtime.publish(target)
                    runtime.reload()
                    if target == MAINTENANCE:
                        runtime.verify_maintenance()
                    else:
                        runtime.verify_public(packet)
                    state = 'maintenance' if target == MAINTENANCE else 'rolled_back'
            except Exception as compensation_failure:
                failure_audit(directory, 'compensation_failure', stage='compensation',
                      exception_type=type(compensation_failure).__name__,
                      elapsed_seconds=round(time.monotonic()-started, 3))
                state = 'proxy_stop_required'
                try:
                    atomic(directory / 'status.json', encoded({'state': state, 'plan_digest': digest(packet)}))
                except OSError:
                    pass
                try:
                    runtime.stop_proxy()
                    state = 'proxy_stopped'
                except Exception:
                    failure_audit(directory, 'critical_proxy_stop_failed', transaction=transaction.name)
                    raise RuntimeError('critical_manual_proxy_stop_required') from None
            atomic(directory / 'status.json', encoded({'state': state, 'plan_digest': digest(packet)}))
            audit(directory, 'reconcile_failed_closed', transaction=transaction.name, state=state)
            raise RuntimeError('routing_repair_failed_closed:' + state) from None


class Relay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, *args, **kwargs):
        self.capacity = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def verify_request(self, connection, address):
        if self.capacity.acquire(blocking=False):
            return True
        try:
            connection.sendall(DENIED)
        except OSError:
            pass
        return False

    def process_request_thread(self, *args):
        try:
            super().process_request_thread(*args)
        finally:
            self.capacity.release()


class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        remote = None
        try:
            authorized(self.server.directory)
            # Every new connection checks current authority, stopped consumers,
            # identities, health and schema; no Docker IP cache survives restart.
            _, endpoints = verify(self.server.runtime, self.server.plan)
            remote = socket.create_connection(endpoints[self.server.role], timeout=8)
            remote.settimeout(30)
            self.request.settimeout(30)
            # Raw TCP preserves HTTP streaming, WebSocket upgrades and cookies.
            sockets = [self.request, remote]
            while sockets:
                readable, _, _ = select.select(sockets, [], [], 300)
                if not readable:
                    return
                for incoming in readable:
                    data = incoming.recv(65536)
                    if not data:
                        return
                    other = remote if incoming is self.request else self.request
                    other.sendall(data)
        except Exception:
            print('emergency_routing_connection_denied', flush=True)
            try:
                self.request.sendall(DENIED)
            except OSError:
                pass
        finally:
            if remote is not None:
                remote.close()


def serve(directory):
    packet = authorized(directory)
    runtime = Runtime()
    servers = []
    try:
        for role in ROLES:
            server = Relay(('127.0.0.1', PORTS[role]), Forward)
            server.runtime, server.plan, server.role, server.directory = runtime, packet, role, directory
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        # Service stays available in fail-closed maintenance when a pinned
        # runtime is temporarily down at boot. It never forwards unchecked bytes.
        while True:
            time.sleep(30)
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


def gate(directory):
    packet = authorized(directory)
    status = json.loads(trusted(directory / 'status.json', private=True))
    allowed_states = {'active'} if 'retry_of' in packet else {'active', 'installing'}
    require(status.get('state') in allowed_states and status.get('plan_digest') == digest(packet), 'proxy_boot_gate_closed')
    require(UPSTREAM.read_bytes() == ROUTE, 'proxy_boot_route_changed')
    if 'retry_of' in packet:
        legacy_installation(Runtime(), packet['legacy_installation'], live=False)


def service_text(directory):
    return f'''[Unit]
Description=Madar independently authorized restricted fallback routing
Requires=docker.service
After=docker.service
Before=madar-release-proxy.service
[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/bin/python3 -I -B {directory}/repair.py serve --approved-plan {directory.name}
Restart=on-failure
RestartSec=2
UMask=0077
MemoryMax=512M
TasksMax=256
CPUQuota=200%
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=yes
ProtectSystem=strict
ReadOnlyPaths=/var/lib/madar /var/lib/madar-control-plane /opt/madar/control-plane
[Install]
WantedBy=multi-user.target
'''.encode()


def dropin_text(directory):
    return f'''[Unit]
Requires=madar-emergency-routing.service
After=madar-emergency-routing.service
[Service]
ExecStartPre=+/usr/bin/python3 -I -B {directory}/repair.py gate --approved-plan {directory.name}
'''.encode()


def install(packet, approved_digest, approval_text):
    require(os.geteuid() == 0, 'root_required')
    require(digest(packet) == approved_digest and bool(approval_text.strip()), 'explicit_approval_required')
    reviewed_code = Path(__file__).read_bytes()
    require(sha(reviewed_code) == packet['code_sha256'], 'reviewed_source_changed')
    created = datetime.fromisoformat(packet['created_at'])
    require(created.tzinfo is not None and created <= datetime.now(timezone.utc), 'proposal_timestamp_invalid')
    # Freshness is independently re-established below, not inferred from age.
    runtime = Runtime()
    verify(runtime, packet)
    require(sha(UPSTREAM.read_bytes()) == packet['previous_upstream_sha256'], 'preimage_changed')
    require(not any(p.exists() or p.is_symlink() for p in (UNIT, DROPIN, ROOT)), 'emergency_installation_already_exists')
    for parent in (ROOT.parent, UNIT.parent, DROPIN.parent if DROPIN.parent.exists() or DROPIN.parent.is_symlink() else DROPIN.parent.parent):
        for item in (parent, *parent.parents):
            st = item.lstat()
            require(item.is_dir() and not item.is_symlink() and st.st_uid == 0 and not st.st_mode & 0o022, 'installation_parent_untrusted')
    for port in (*PORTS.values(), FRONTEND_ROUTER_PORT, 29402):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    # New independent namespace only; nothing in the old authority is changed.
    ROOT.mkdir(mode=0o700)
    staging = ROOT / ('.staging-' + approved_digest)
    staging.mkdir(mode=0o700)
    exclusive(staging / 'repair.py', reviewed_code, 0o500)
    require(sha((staging / 'repair.py').read_bytes()) == packet['code_sha256'], 'staged_code_changed')
    exclusive(staging / 'plan.json', encoded(packet))
    exclusive(staging / 'authorization.json', encoded({'version': 1, 'scope': SCOPE,
        'plan_digest': approved_digest, 'explicit_operator_approval': True,
        'operator_approval_text': approval_text, 'issued_at': now(),
        'historical_authorizations_reused': False, 'allows_business_writes': False,
        'allows_consumer_start': False, 'allows_data_restore': False}))
    (staging / 'audit').mkdir(mode=0o700)
    (staging / 'attempts').mkdir(mode=0o700)
    exclusive(staging / 'status.json', encoded({'state': 'installing', 'plan_digest': approved_digest}))
    directory = ROOT / approved_digest
    os.rename(staging, directory)
    fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        exclusive(UNIT, service_text(directory), 0o644)
        DROPIN.parent.mkdir(mode=0o755, exist_ok=True)
        exclusive(DROPIN, dropin_text(directory), 0o644)
        audit(directory, 'fresh_authorization_installed', approval_scope=SCOPE)
        runtime.command(['systemctl', 'daemon-reload'])
        runtime.command(['systemctl', 'enable', '--now', UNIT.name])
        # Prove that both listeners enforce all live checks before route publication.
        for _ in range(20):
            try:
                require(runtime.json_http(f'http://127.0.0.1:{PORTS["backend"]}/health/recovery') ==
                        {'restricted': True, 'business_writes_enabled': False}, 'relay_not_ready')
                runtime.http_status(f'http://127.0.0.1:{PORTS["frontend"]}/')
                break
            except Exception:
                time.sleep(1)
        else:
            audit(directory, 'relay_start_failed_no_routing_mutation')
            atomic(directory / 'status.json', encoded({'state': 'maintenance', 'plan_digest': approved_digest}))
            raise RuntimeError('relay_start_failed_no_routing_mutation')
        reconcile(runtime, directory)
    except Exception:
        status = json.loads((directory / 'status.json').read_bytes())
        if status.get('state') == 'installing':
            atomic(directory / 'status.json', encoded({'state': 'installation_failed', 'plan_digest': approved_digest}))
        audit(directory, 'installation_failed', state=json.loads((directory / 'status.json').read_bytes())['state'])
        raise


def legacy_installation(runtime, expected=None, *, live=True):
    directory = ROOT / LEGACY_DIGEST
    original = authorized(directory)
    require(original['code_sha256'] == LEGACY_CODE, 'legacy_source_changed')
    require(json.loads(trusted(directory / 'status.json', private=True)) ==
            {'plan_digest': LEGACY_DIGEST, 'state': 'maintenance'}, 'legacy_not_in_maintenance')
    files = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'legacy_symlink_refused')
        if path.is_file():
            files[str(path)] = sha(trusted(path, private=True))
    require(trusted(UNIT) == service_text(directory) and trusted(DROPIN) == dropin_text(directory),
            'legacy_service_changed')
    files[str(UNIT)] = sha(trusted(UNIT))
    files[str(DROPIN)] = sha(trusted(DROPIN))
    result = {'plan_digest': LEGACY_DIGEST, 'source_sha256': LEGACY_CODE, 'files': files}
    if expected is not None:
        require(result == expected, 'legacy_installation_changed')
    allowed_dropins = [str(DROPIN)]
    if RETRY_DROPIN.exists():
        content = trusted(RETRY_DROPIN)
        match = re.search(rb'/emergency-routing/([0-9a-f]{64})/repair.py', content)
        require(match is not None, 'retry_gate_invalid')
        retry_directory = ROOT / match[1].decode()
        fresh = authorized(retry_directory)
        require(fresh.get('retry_of') == LEGACY_DIGEST and fresh.get('legacy_installation') == result and
                content == retry_dropin_text(retry_directory), 'retry_gate_unbound')
        allowed_dropins.append(str(RETRY_DROPIN))
    if live:
        effective = dict(line.split('=', 1) for line in runtime.command(
            ['systemctl', 'show', 'madar-release-proxy.service', '--property=FragmentPath,DropInPaths']).splitlines())
        require(effective.get('FragmentPath') == '/etc/systemd/system/madar-release-proxy.service' and
                effective.get('DropInPaths', '').split() == allowed_dropins, 'proxy_startup_controls_changed')
        verify(runtime, original)
        props = dict(line.split('=', 1) for line in runtime.command(
            ['systemctl', 'show', UNIT.name, '--property=ActiveState,SubState,MainPID']).splitlines())
        require(props.get('ActiveState') == 'active' and props.get('SubState') == 'running' and
                re.fullmatch('[1-9][0-9]*', props.get('MainPID', '')), 'legacy_helper_not_running')
        pid = props['MainPID']
        require(Path('/proc/' + pid + '/cmdline').read_bytes().rstrip(b'\0').split(b'\0') ==
                [b'/usr/bin/python3', b'-I', b'-B', str(directory / 'repair.py').encode(),
                 b'serve', b'--approved-plan', LEGACY_DIGEST.encode()], 'legacy_process_changed')
        listeners = runtime.command(['ss', '-ltnp']).splitlines()
        for port in PORTS.values():
            require(any(re.search(r'127\.0\.0\.1:' + str(port) + r'\s', line) and
                        'pid=' + pid + ',' in line for line in listeners), 'legacy_listener_changed')
        require(runtime.json_http('http://127.0.0.1:29401/health/recovery') ==
                {'restricted': True, 'business_writes_enabled': False}, 'legacy_relay_unfenced')
        runtime.http_status('http://127.0.0.1:39401/')
    return result


def make_retry_plan(runtime):
    require(UPSTREAM.read_bytes() == MAINTENANCE, 'retry_requires_current_maintenance')
    legacy = legacy_installation(runtime)
    packet = make_plan(runtime)
    return dict(packet, retry_of=LEGACY_DIGEST, legacy_installation=legacy,
                verification_seconds=VERIFY_SECONDS, compensation_seconds=COMPENSATE_SECONDS,
                sustained_seconds=SUSTAIN_SECONDS, required_success_rounds=SUCCESS_ROUNDS)


def retry_dropin_text(directory):
    # Reset only the reviewed old startup gate; all original unit files remain
    # unchanged. The fresh gate independently validates the preserved old helper.
    return f'''[Service]
ExecStartPre=
ExecStartPre=+/usr/bin/python3 -I -B {directory}/repair.py gate --approved-plan {directory.name}
'''.encode()


def retry_install(packet, approved_digest, approval_text):
    require(os.geteuid() == 0, 'root_required')
    require(digest(packet) == approved_digest and bool(approval_text.strip()), 'explicit_approval_required')
    reviewed = Path(__file__).read_bytes()
    require(sha(reviewed) == packet['code_sha256'] and packet.get('retry_of') == LEGACY_DIGEST and
            packet.get('verification_seconds') == VERIFY_SECONDS and
            packet.get('compensation_seconds') == COMPENSATE_SECONDS and
            packet.get('sustained_seconds') == SUSTAIN_SECONDS and
            packet.get('required_success_rounds') == SUCCESS_ROUNDS, 'retry_approval_scope_invalid')
    runtime = Runtime()
    legacy_installation(runtime, packet['legacy_installation'])
    verify(runtime, packet)
    require(UPSTREAM.read_bytes() == MAINTENANCE and
            sha(MAINTENANCE) == packet['previous_upstream_sha256'], 'retry_preimage_changed')
    directory = ROOT / approved_digest
    require(not directory.exists() and not directory.is_symlink() and
            not RETRY_DROPIN.exists() and not RETRY_DROPIN.is_symlink(), 'retry_installation_collision')
    for parent in (ROOT, RETRY_DROPIN.parent):
        for part in (parent, *parent.parents):
            st = part.lstat()
            require(part.is_dir() and not part.is_symlink() and st.st_uid == 0 and not st.st_mode & 0o022,
                    'retry_parent_untrusted')
    # New exclusive namespace; never replace the legacy package/authorization,
    # status, audits, pre-images, service or first drop-in.
    directory.mkdir(mode=0o700)
    exclusive(directory / 'repair.py', reviewed, 0o500)
    exclusive(directory / 'plan.json', encoded(packet))
    exclusive(directory / 'authorization.json', encoded({'version': 1, 'scope': SCOPE,
        'plan_digest': approved_digest, 'explicit_operator_approval': True,
        'operator_approval_text': approval_text, 'issued_at': now(),
        'historical_authorizations_reused': False, 'allows_business_writes': False,
        'allows_consumer_start': False, 'allows_data_restore': False}))
    (directory / 'audit').mkdir(mode=0o700)
    (directory / 'attempts').mkdir(mode=0o700)
    exclusive(directory / 'status.json', encoded({'state': 'installing', 'plan_digest': approved_digest}))
    started = time.monotonic()
    stage = 'retry_gate_installation'
    try:
        exclusive(RETRY_DROPIN, retry_dropin_text(directory), 0o644)
        audit(directory, 'fresh_retry_authorization_installed', retry_of=LEGACY_DIGEST)
        stage = 'daemon_reload'
        runtime.command(['systemctl', 'daemon-reload'])
        stage = 'routing_reconcile'
        reconcile(runtime, directory)
    except Exception as failure:
        state = json.loads((directory / 'status.json').read_bytes())['state']
        if state == 'installing':
            atomic(directory / 'status.json', encoded({'state': 'installation_failed', 'plan_digest': approved_digest}))
        failure_audit(directory, 'retry_installation_failed', stage=stage,
                      exception_type=type(failure).__name__, elapsed_seconds=round(time.monotonic()-started, 3))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('plan', 'retry-plan', 'install', 'retry', 'reconcile', 'serve', 'gate'))
    parser.add_argument('--approved-plan')
    parser.add_argument('--operator-approval-text')
    args = parser.parse_args()
    require(os.geteuid() == 0, 'root_required')
    os.umask(0o077)
    if args.operation in {'plan', 'retry-plan'}:
        packet = make_retry_plan(Runtime()) if args.operation == 'retry-plan' else make_plan(Runtime())
        print(json.dumps(packet, sort_keys=True, indent=2))
        return
    require(args.approved_plan and re.fullmatch(r'[0-9a-f]{64}', args.approved_plan), 'approved_plan_required')
    if args.operation in {'install', 'retry'}:
        packet = json.load(sys.stdin)
        operation = retry_install if args.operation == 'retry' else install
        operation(packet, args.approved_plan, args.operator_approval_text or '')
    else:
        directory = ROOT / args.approved_plan
        # No source, destination, ref or driver may be substituted on the CLI.
        require(Path(__file__).resolve() == directory / 'repair.py', 'installed_entrypoint_required')
        if args.operation == 'reconcile':
            reconcile(Runtime(), directory)
        else:
            globals()[args.operation](directory)
    print('emergency_routing_operation_complete')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print Docker/libpq/HTTP exception contents or customer payloads.
        print('emergency_routing_failed:' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
