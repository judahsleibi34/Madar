"""Fixed staging restore configuration; never imports origin Compose inputs."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import manage

TEMPLATES = {
    'compose.yaml': 'e33b30121159b1c8aafe4c1a060bdd885e1803c5d68b38cdc1f10e9a617cb8b2',
    'gateway.conf': 'd987b65a682d8d6520944cfea1590d3e932986d41bc05c032d3d1edd843ffc08',
}
INFRA_IMAGES = {
    'postgres': 'postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73',
    'auth': 'supabase/gotrue:v2.196.0@sha256:c0c25187a6b835e65a6f6e6c6b39d090e832d40e6de5186f2c038e0411944232',
    'rest': 'postgrest/postgrest:v14.17@sha256:c9dc201e555f5d8e37e7f39cdd4df0229774996e213bfd7de8d10ac609030f2c',
    'storage': 'supabase/storage-api:v1.74.0@sha256:f1546fac6d1c7e345428ac904bfaa7be7cecd50a1f549fe1cf38c628a7b15c85',
    'redis': 'redis@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99',
}
BOUNDS = {'postgres': (512, 1), 'redis': (128, .25), 'auth': (192, 1), 'rest': (128, .5),
          'storage': (256, .5), 'gateway': (64, .25), 'backend': (1280, 1.5),
          'notification-worker': (256, .5), 'deletion-worker': (256, .5),
          'frontend': (64, .25), 'accepted-frontend': (128, .5)}


@contextmanager
def private_directory_lock(path):
    """Serialize one fixed staging project without a replaceable lock file."""
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        original = os.fstat(descriptor)
        def require_identity():
            current = Path(path).lstat()
            observed = os.fstat(descriptor)
            if (not stat.S_ISDIR(current.st_mode) or current.st_uid != os.getuid()
                    or stat.S_IMODE(current.st_mode) != 0o700
                    or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)
                    or (observed.st_dev, observed.st_ino) != (original.st_dev, original.st_ino)
                    or observed.st_uid != os.getuid() or stat.S_IMODE(observed.st_mode) != 0o700):
                raise RuntimeError('restore150_project_lock_identity_invalid')
        require_identity()
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('restore150_project_busy') from None
        require_identity()
        try:
            yield
        finally:
            require_identity()
    finally:
        os.close(descriptor)


def regular(path, maximum=4 * 1024 * 1024):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        value = os.fstat(source.fileno())
        if not stat.S_ISREG(value.st_mode) or value.st_size > maximum:
            raise RuntimeError('restore150_configuration_file_invalid')
        data = source.read(maximum + 1)
    if len(data) > maximum: raise RuntimeError('restore150_configuration_file_invalid')
    return data


def templates():
    result = {}
    for name, expected in TEMPLATES.items():
        data = regular(manage.REPOSITORY / 'web/staging/integration' / name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('restore150_trusted_template_changed')
        result[name] = data.decode()
    return result


def live_credentials(rows):
    """Only fixed attested LIVE container values, never mutable origin dotenv."""
    def field(service, key):
        values = [item.split('=', 1)[1] for item in rows[service]['Config'].get('Env', []) if item.startswith(key + '=')]
        if len(values) != 1: raise RuntimeError('restore150_live_provider_environment_invalid')
        return values[0]
    password, jwt = field('postgres', 'POSTGRES_PASSWORD'), field('auth', 'GOTRUE_JWT_SECRET')
    if not all(re.fullmatch('[0-9a-f]{64}', value) for value in (password, jwt)):
        raise RuntimeError('restore150_live_credential_syntax_invalid')
    expected = {
        ('postgres', 'POSTGRES_DB'): 'madar_hardening', ('postgres', 'POSTGRES_USER'): 'postgres',
        ('auth', 'GOTRUE_DB_DATABASE_URL'): 'postgres://supabase_auth_admin:' + password + '@postgres:5432/madar_hardening',
        ('rest', 'PGRST_DB_URI'): 'postgres://authenticator:' + password + '@postgres:5432/madar_hardening',
        ('storage', 'DATABASE_URL'): 'postgres://supabase_storage_admin:' + password + '@postgres:5432/madar_hardening',
        ('rest', 'PGRST_JWT_SECRET'): jwt, ('storage', 'AUTH_JWT_SECRET'): jwt,
        ('storage', 'POSTGREST_URL'): 'http://rest:3000', ('storage', 'STORAGE_BACKEND'): 'file',
        ('storage', 'FILE_STORAGE_BACKEND_PATH'): '/var/lib/storage',
    }
    for service in ('backend', 'notification-worker', 'deletion-worker'):
        expected.update({(service, 'SUPABASE_URL'): 'http://gateway:8081',
                         (service, 'REDIS_URL'): 'redis://redis:6379/0',
                         (service, 'SCHEMA_COMPATIBLE_MIN'): '150', (service, 'SCHEMA_COMPATIBLE_MAX'): '150',
                         (service, 'APP_ENV'): 'staging', (service, 'EMAIL_CHANNEL_ENABLED'): 'false',
                         (service, 'WEB_PUSH_ENABLED'): 'false'})
    if any(field(service, key) != value for (service, key), value in expected.items()):
        raise RuntimeError('restore150_live_provider_endpoint_or_credential_mismatch')
    return {'DATABASE_PASSWORD': password, 'JWT_SECRET': jwt}


def generate(runtime, source_sha, images, receipt, credentials, project, owner):
    """Regenerate from pinned source templates; origin YAML/env are never read."""
    trusted = templates()  # Capture and authenticate before any directory effect.
    if set(credentials) != {'DATABASE_PASSWORD', 'JWT_SECRET'} or any(
            not re.fullmatch('[0-9a-f]{64}', value) for value in credentials.values()):
        raise RuntimeError('restore150_live_credential_syntax_invalid')
    schema = manage.TARGET_SCHEMA
    try:
        manage.TARGET_SCHEMA = 150
        manage.prepare(source_sha)
    finally:
        manage.TARGET_SCHEMA = schema
    signing = credentials['JWT_SECRET']
    anon, service = manage.jwt(signing, 'anon'), manage.jwt(signing, 'service_role')
    values = {'HARDENING_ROOT': str(runtime), 'SOURCE_SHA': source_sha, **credentials,
              'ANON_KEY': anon, 'SERVICE_KEY': service}
    manage.private_write('compose.env', ''.join(key + '=' + value + '\n' for key, value in values.items()))
    # These generated fields come from committed manage.prepare and a fixed
    # override allowlist, rather than an origin application's editable file.
    app = dict(line.split('=', 1) for line in regular(runtime / 'application.env').decode().splitlines())
    app.update({'SUPABASE_ANON_KEY': anon, 'SUPABASE_SERVICE_KEY': service,
                'FRONTEND_URLS': 'http://127.0.0.1:22080,https://127.0.0.1:22443',
                'MADAR_BUILD_TIMESTAMP': receipt['build_timestamp'],
                'DATA_DELETION_WORKER_ENABLED': 'true', 'DATA_DELETION_WORKER_HEALTH_HOST': '0.0.0.0',
                'DATA_DELETION_WORKER_POLL_SECONDS': '2', 'DATA_DELETION_WORKER_REQUIRED': 'true',
                'DATA_DELETION_WORKER_HEALTH_URL': 'http://deletion-worker:8094/health'})
    manage.private_write('application.env', ''.join(key + '=' + value + '\n' for key, value in app.items()))
    manage.private_write('bootstrap.sql', '-- Independent150 restore: no inherited provider roles.\n', mounted=True)
    manage.private_write('trusted-gateway.conf', trusted['gateway.conf'], mounted=True)
    text = trusted['compose.yaml'].replace('architecture-hardening-20261016', owner)
    text = text.replace('image: madar-hardening-application:${SOURCE_SHA:?}', 'image: ' + images['backend'])
    text = text.replace('image: madar-frontend:b0fdfe049510724c06a04706390cd174ea57a1d1', 'image: ' + images['frontend'])
    text = text.replace('./gateway.conf', str(runtime / 'trusted-gateway.conf'))
    text = text.replace('./frontend.conf', str(runtime / 'fresh-edge.conf')).replace('      - ../../frontend/dist:/site:ro\n', '')
    text = text.replace('mem_limit: 768m\n    cpus: 2.0', 'mem_limit: 512m\n    cpus: 1.0')
    for before, after in (('18080', '22080'), ('18443', '22443'), ('18081', '22081')):
        text = text.replace(':' + before, ':' + after)
    manage.private_write('compose.yaml', text)
    edge = '''pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 128; }
http { access_log off; client_body_temp_path /tmp/client; proxy_temp_path /tmp/proxy;
 fastcgi_temp_path /tmp/fastcgi; uwsgi_temp_path /tmp/uwsgi; scgi_temp_path /tmp/scgi;
 server { listen 8080; listen 8443 ssl; ssl_certificate /staging/tls.crt; ssl_certificate_key /staging/tls.key;
 location / { proxy_pass http://accepted-frontend:8080; proxy_set_header Host $http_host; proxy_set_header X-Forwarded-Proto $scheme; } } }
'''
    manage.private_write('fresh-edge.conf', edge, mounted=True)
    common = {'restart': 'no', 'networks': ['isolated'], 'read_only': True,
        'security_opt': ['no-new-privileges:true'], 'cap_drop': ['ALL'], 'pids_limit': 128,
        'labels': {'com.madar.staging.owner': owner}, 'mem_limit': '128m', 'cpus': .5,
        'logging': {'driver': 'json-file', 'options': {'max-size': '2m', 'max-file': '2'}}}
    overlay = {'services': {
        'accepted-frontend': {**common, 'image': images['frontend'], 'pull_policy': 'never', 'user': 'nginx',
            'tmpfs': ['/tmp:rw,noexec,nosuid,size=32m', '/var/cache/nginx:rw,noexec,nosuid,uid=101,gid=101,size=32m', '/etc/nginx/conf.d:rw,noexec,nosuid,uid=101,gid=101,size=2m'],
            'environment': {'APP_ENV': 'staging', 'MADAR_RELEASE_SHA': source_sha, 'MADAR_PUBLIC_SITE_DOMAIN': 'hardening.test', 'MADAR_CSP_CONNECT_SRC': "'self'", 'MADAR_HSTS': ''},
            'depends_on': {'backend': {'condition': 'service_healthy'}}},
        'frontend': {'depends_on': {'accepted-frontend': {'condition': 'service_started'}}},
        'deletion-worker': {**common, 'image': images['backend'], 'pull_policy': 'never', 'user': '65534:65534',
            'command': ['python', '-m', 'workers.data_deletion_worker'], 'env_file': [str(runtime / 'application.env')],
            'tmpfs': ['/tmp:rw,nosuid,nodev,size=128m,mode=1777'], 'mem_limit': '256m',
            'depends_on': {'backend': {'condition': 'service_healthy'}},
            'healthcheck': {'test': ['CMD', 'python', '-c', "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8094/health',timeout=2)"], 'interval': '3s', 'timeout': '3s', 'retries': 30}},
    }}
    manage.private_write('acceptance-compose.json', json.dumps(overlay))
    rendered = manage.docker('compose', '--project-name', project, '--env-file', str(runtime / 'compose.env'),
        '--file', str(runtime / 'compose.yaml'), '--file', str(runtime / 'acceptance-compose.json'), 'config', '--format', 'json')
    plan = json.loads(rendered)
    plan.pop('x-service', None); plan.pop('x-application', None)
    validate(plan, runtime, source_sha, images, project, owner, receipt['build_timestamp'])
    body = json.dumps(plan, sort_keys=True).encode()
    manage.private_write('verified-compose.json', body.decode())
    manage.private_write('configuration-receipt.json', json.dumps({'source_sha': source_sha, 'images': images,
        'sha256': hashlib.sha256(body).hexdigest(), 'template_sha256': TEMPLATES,
        'build_timestamp': receipt['build_timestamp']}) + '\n')


def validate(plan, runtime, source_sha, images, project, owner, build_timestamp=None):
    """Validate the fully resolved, self-contained Docker Compose data plane."""
    def reject(): raise RuntimeError('restore150_unsafe_resolved_configuration')
    if (not isinstance(plan, dict) or set(plan) - {'name', 'services', 'networks', 'volumes', 'x-service', 'x-application'}
            or plan.get('name') != project or set(plan.get('services', {})) != set(BOUNDS)
            or set(plan.get('networks', {})) != {'isolated', 'ingress'}
            or set(plan.get('volumes', {})) != {'database', 'objects'}): reject()
    for name, network in plan['networks'].items():
        if (network.get('name') != project + '_' + name or network.get('external')
                or (network.get('labels') or {}).get('com.madar.staging.owner') != owner): reject()
        if name == 'isolated' and network.get('internal') is not True: reject()
        if name == 'ingress' and (network.get('internal') or str((network.get('driver_opts') or {}).get('com.docker.network.bridge.enable_ip_masquerade')).lower() != 'false'): reject()
    for name, volume in plan['volumes'].items():
        if (volume.get('name') != project + '_' + name or volume.get('external') or volume.get('driver_opts')
                or volume.get('driver', 'local') != 'local'
                or (volume.get('labels') or {}).get('com.madar.staging.owner') != owner): reject()
    allowed_binds = {
        'postgres': {(str(runtime / 'bootstrap.sql'), '/docker-entrypoint-initdb.d/10-hardening.sql')},
        'gateway': {(str(runtime / 'trusted-gateway.conf'), '/staging/nginx.conf')},
        'frontend': {(str(runtime / 'fresh-edge.conf'), '/staging/nginx.conf'),
                     (str(runtime / 'tls.crt'), '/staging/tls.crt'), (str(runtime / 'tls.key'), '/staging/tls.key')},
    }
    expected_ports = {'frontend': {('127.0.0.1', '22080', 8080), ('127.0.0.1', '22443', 8443)},
                      'gateway': {('127.0.0.1', '22081', 8081)}}
    for name, row in plan['services'].items():
        image = INFRA_IMAGES.get(name, images['backend' if name in ('backend', 'notification-worker', 'deletion-worker') else 'frontend'])
        limit, cpu = BOUNDS[name]
        if (row.get('image') != image or row.get('restart') != 'no' or row.get('privileged')
                or any(row.get(key) for key in ('network_mode', 'pid', 'ipc', 'devices', 'device_cgroup_rules', 'volumes_from', 'cap_add', 'env_file', 'extends', 'build', 'external_links', 'extra_hosts'))
                or not 0 < int(row.get('mem_limit', 0)) <= limit * 1024**2
                or not 0 < float(row.get('cpus', 0)) <= cpu or not 0 < int(row.get('pids_limit', 0)) <= 256
                or (row.get('labels') or {}).get('com.madar.staging.owner') != owner
                or set(row.get('networks', {})) != ({'isolated', 'ingress'} if name in ('frontend', 'gateway') else {'isolated'})): reject()
        ports = {(port.get('host_ip'), str(port.get('published')), port.get('target')) for port in row.get('ports', [])}
        if (ports != expected_ports.get(name, set()) or len(ports) != len(row.get('ports', []))
                or any(port.get('protocol', 'tcp') != 'tcp' for port in row.get('ports', []))): reject()
        binds, volume_mounts = set(), []
        for mount in row.get('volumes', []):
            if mount.get('type') == 'bind':
                if mount.get('read_only') is not True: reject()
                binds.add((mount.get('source'), mount.get('target')))
            elif mount.get('type') == 'volume': volume_mounts.append(mount)
            else: reject()
        if binds != allowed_binds.get(name, set()): reject()
        expected_volume = {'postgres': ('database', '/var/lib/postgresql/data'), 'storage': ('objects', '/var/lib/storage')}.get(name)
        if expected_volume:
            if len(volume_mounts) != 1 or volume_mounts[0].get('source') not in (expected_volume[0], project + '_' + expected_volume[0]) or volume_mounts[0].get('target') != expected_volume[1]: reject()
        elif volume_mounts: reject()
        env = row.get('environment') or {}
        if name in ('backend', 'notification-worker', 'deletion-worker'):
            for key, value in {'APP_ENV': 'staging', 'SUPABASE_URL': 'http://gateway:8081', 'REDIS_URL': 'redis://redis:6379/0',
                'SCHEMA_COMPATIBLE_MIN': '150', 'SCHEMA_COMPATIBLE_MAX': '150', 'MADAR_RELEASE_SHA': source_sha,
                'EMAIL_CHANNEL_ENABLED': 'false', 'WEB_PUSH_ENABLED': 'false', 'AI_ALLOW_LOCAL_EXEC': 'false', 'ALLOW_REMOTE_DATASET_URLS': 'false'}.items():
                if env.get(key) != value: reject()
            stamp = env.get('MADAR_BUILD_TIMESTAMP', '')
            if (not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z', stamp)
                    or (build_timestamp is not None and stamp != build_timestamp)): reject()
        if name == 'backend' and (env.get('DATA_DELETION_WORKER_REQUIRED') != 'true'
                or env.get('DATA_DELETION_WORKER_HEALTH_URL') != 'http://deletion-worker:8094/health'): reject()
        if name == 'rest' and not re.fullmatch(r'postgres://authenticator:[0-9a-f]{64}@postgres:5432/madar_hardening', env.get('PGRST_DB_URI', '')): reject()
        if name == 'auth' and not re.fullmatch(r'postgres://supabase_auth_admin:[0-9a-f]{64}@postgres:5432/madar_hardening', env.get('GOTRUE_DB_DATABASE_URL', '')): reject()
        if name == 'storage' and (env.get('POSTGREST_URL') != 'http://rest:3000' or not re.fullmatch(r'postgres://supabase_storage_admin:[0-9a-f]{64}@postgres:5432/madar_hardening', env.get('DATABASE_URL', ''))): reject()
    envs = {name: row.get('environment', {}) for name, row in plan['services'].items()}
    password, jwt = envs['postgres'].get('POSTGRES_PASSWORD', ''), envs['auth'].get('GOTRUE_JWT_SECRET', '')
    if not all(re.fullmatch('[0-9a-f]{64}', value) for value in (password, jwt)): reject()
    required = {
        'postgres': {'POSTGRES_DB': 'madar_hardening', 'POSTGRES_USER': 'postgres'},
        'auth': {'GOTRUE_DB_DATABASE_URL': 'postgres://supabase_auth_admin:' + password + '@postgres:5432/madar_hardening',
                 'API_EXTERNAL_URL': 'http://127.0.0.1:22081/auth/v1', 'GOTRUE_SITE_URL': 'http://127.0.0.1:22080',
                 'GOTRUE_JWT_ISSUER': 'http://127.0.0.1:22081/auth/v1', 'GOTRUE_URI_ALLOW_LIST': 'http://127.0.0.1:22080/**'},
        'rest': {'PGRST_DB_URI': 'postgres://authenticator:' + password + '@postgres:5432/madar_hardening', 'PGRST_JWT_SECRET': jwt},
        'storage': {'DATABASE_URL': 'postgres://supabase_storage_admin:' + password + '@postgres:5432/madar_hardening',
                    'AUTH_JWT_SECRET': jwt, 'POSTGREST_URL': 'http://rest:3000', 'STORAGE_PUBLIC_URL': 'http://127.0.0.1:22081',
                    'STORAGE_BACKEND': 'file', 'FILE_STORAGE_BACKEND_PATH': '/var/lib/storage'},
    }
    if any(envs[name].get(key) != value for name, fields in required.items() for key, value in fields.items()): reject()


def invoke(runtime, args, project, owner, *, timeout=180):
    args = list(args)
    while '--file' in args:
        index = args.index('--file')
        if index + 1 == len(args) or args[index + 1] != str(runtime / 'acceptance-compose.json'):
            raise RuntimeError('restore150_unapproved_compose_overlay')
        del args[index:index + 2]
    forbidden = {'--file', '--env-file', '--project-name', '--project-directory', '--profile'}
    if any(arg.split('=', 1)[0] in forbidden
           or (not arg.startswith('--') and arg.startswith(('-f', '-p'))) for arg in args):
        raise RuntimeError('restore150_unapproved_compose_override')
    manage.state()
    body = regular(runtime / 'verified-compose.json')
    receipt = json.loads(regular(runtime / 'configuration-receipt.json'))
    if hashlib.sha256(body).hexdigest() != receipt['sha256']:
        raise RuntimeError('restore150_verified_configuration_changed')
    validate(json.loads(body), runtime, receipt['source_sha'], receipt['images'], project, owner, receipt['build_timestamp'])
    # Consume these captured resolved bytes over stdin. Docker never reopens the
    # origin/configuration/env paths verified by an earlier operation.
    return manage.docker('compose', '--project-name', project, '--file', '-', *args, data=body, timeout=timeout)
