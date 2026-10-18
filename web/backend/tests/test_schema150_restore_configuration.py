"""Adversarial origin configuration cannot become restored Docker authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB / 'staging/integration'))
import schema150_restore_configuration as configuration
import schema150_application_restore as rehearsal

PROJECT, OWNER = rehearsal.PROJECT, rehearsal.OWNER
IMAGES = {'backend': 'sha256:' + 'b' * 64, 'frontend': 'sha256:' + 'f' * 64}
SHA = 'a' * 40


def valid_plan(runtime):
    password, jwt = 'a' * 64, 'b' * 64
    services = {}
    for name, (memory, cpu) in configuration.BOUNDS.items():
        image = configuration.INFRA_IMAGES.get(name, IMAGES['backend' if name in ('backend', 'notification-worker', 'deletion-worker') else 'frontend'])
        services[name] = {'image': image, 'restart': 'no', 'mem_limit': memory * 1024**2,
            'cpus': cpu, 'pids_limit': 128, 'labels': {'com.madar.staging.owner': OWNER},
            'networks': dict.fromkeys(('isolated', 'ingress') if name in ('frontend', 'gateway') else ('isolated',), None),
            'environment': {}}
    for name in ('backend', 'notification-worker', 'deletion-worker'):
        services[name]['environment'] = {'APP_ENV': 'staging', 'SUPABASE_URL': 'http://gateway:8081',
            'REDIS_URL': 'redis://redis:6379/0', 'SCHEMA_COMPATIBLE_MIN': '150', 'SCHEMA_COMPATIBLE_MAX': '150',
            'MADAR_RELEASE_SHA': SHA, 'EMAIL_CHANNEL_ENABLED': 'false', 'WEB_PUSH_ENABLED': 'false',
            'AI_ALLOW_LOCAL_EXEC': 'false', 'ALLOW_REMOTE_DATASET_URLS': 'false',
            'MADAR_BUILD_TIMESTAMP': '2026-10-18T00:00:00Z',
            'DATA_DELETION_WORKER_REQUIRED': 'true', 'DATA_DELETION_WORKER_HEALTH_URL': 'http://deletion-worker:8094/health'}
    services['postgres']['environment'] = {'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'madar_hardening', 'POSTGRES_USER': 'postgres'}
    services['auth']['environment'] = {'GOTRUE_JWT_SECRET': jwt,
        'GOTRUE_DB_DATABASE_URL': 'postgres://supabase_auth_admin:' + password + '@postgres:5432/madar_hardening',
        'API_EXTERNAL_URL': 'http://127.0.0.1:22081/auth/v1', 'GOTRUE_SITE_URL': 'http://127.0.0.1:22080',
        'GOTRUE_JWT_ISSUER': 'http://127.0.0.1:22081/auth/v1', 'GOTRUE_URI_ALLOW_LIST': 'http://127.0.0.1:22080/**'}
    services['rest']['environment'] = {'PGRST_DB_URI': 'postgres://authenticator:' + password + '@postgres:5432/madar_hardening', 'PGRST_JWT_SECRET': jwt}
    services['storage']['environment'] = {'DATABASE_URL': 'postgres://supabase_storage_admin:' + password + '@postgres:5432/madar_hardening',
        'POSTGREST_URL': 'http://rest:3000', 'AUTH_JWT_SECRET': jwt, 'STORAGE_PUBLIC_URL': 'http://127.0.0.1:22081',
        'STORAGE_BACKEND': 'file', 'FILE_STORAGE_BACKEND_PATH': '/var/lib/storage'}
    for service, items in {'postgres': [('bootstrap.sql', '/docker-entrypoint-initdb.d/10-hardening.sql')],
            'gateway': [('trusted-gateway.conf', '/staging/nginx.conf')],
            'frontend': [('fresh-edge.conf', '/staging/nginx.conf'), ('tls.crt', '/staging/tls.crt'), ('tls.key', '/staging/tls.key')]}.items():
        services[service]['volumes'] = [{'type': 'bind', 'source': str(runtime / name), 'target': target, 'read_only': True} for name, target in items]
    services['postgres']['volumes'].append({'type': 'volume', 'source': 'database', 'target': '/var/lib/postgresql/data'})
    services['storage']['volumes'] = [{'type': 'volume', 'source': 'objects', 'target': '/var/lib/storage'}]
    for service, values in {'frontend': [('22080', 8080), ('22443', 8443)], 'gateway': [('22081', 8081)]}.items():
        services[service]['ports'] = [{'host_ip': '127.0.0.1', 'published': published, 'target': target, 'protocol': 'tcp'} for published, target in values]
    return {'name': PROJECT, 'services': services, 'networks': {
        'isolated': {'name': PROJECT + '_isolated', 'internal': True, 'labels': {'com.madar.staging.owner': OWNER}},
        'ingress': {'name': PROJECT + '_ingress', 'driver_opts': {'com.docker.network.bridge.enable_ip_masquerade': 'false'}, 'labels': {'com.madar.staging.owner': OWNER}}},
        'volumes': {name: {'name': PROJECT + '_' + name, 'labels': {'com.madar.staging.owner': OWNER}} for name in ('database', 'objects')}}


class RestoreConfigurationTests(unittest.TestCase):
    def test_fixed_resolved_configuration_is_accepted(self):
        root = Path('/private/owned-target')
        configuration.validate(valid_plan(root), root, SHA, IMAGES, PROJECT, OWNER)

    def test_live_credentials_require_internal_provider_agreement(self):
        plan = valid_plan(Path('/private/target'))
        rows = {name: {'Config': {'Env': [key + '=' + value for key, value in service['environment'].items()]}}
                for name, service in plan['services'].items()}
        self.assertEqual(configuration.live_credentials(rows), {'DATABASE_PASSWORD': 'a' * 64, 'JWT_SECRET': 'b' * 64})
        for service, key, value in (('rest', 'PGRST_DB_URI', 'postgres://foreign.invalid/database'),
                ('storage', 'AUTH_JWT_SECRET', 'c' * 64), ('backend', 'SUPABASE_URL', 'https://foreign.invalid')):
            changed = copy.deepcopy(rows)
            changed[service]['Config']['Env'] = [item for item in changed[service]['Config']['Env'] if not item.startswith(key + '=')] + [key + '=' + value]
            with self.subTest(service=service), self.assertRaises(RuntimeError): configuration.live_credentials(changed)

    def test_duplicate_or_injected_live_credentials_reject(self):
        plan = valid_plan(Path('/private/target'))
        original = {name: {'Config': {'Env': [key + '=' + value for key, value in service['environment'].items()]}}
                    for name, service in plan['services'].items()}
        duplicate = copy.deepcopy(original)
        duplicate['postgres']['Config']['Env'].append('POSTGRES_PASSWORD=' + 'a' * 64)
        with self.assertRaises(RuntimeError): configuration.live_credentials(duplicate)
        injected = copy.deepcopy(original)
        injected['postgres']['Config']['Env'] = [item for item in injected['postgres']['Config']['Env'] if not item.startswith('POSTGRES_PASSWORD=')] + ['POSTGRES_PASSWORD=' + 'a' * 64 + '\nEVIL=1']
        with self.assertRaises(RuntimeError): configuration.live_credentials(injected)

    def test_concrete_malicious_compose_mutations_are_rejected_before_docker(self):
        root = Path('/private/owned-target')
        mutations = {
            'extra_service': lambda p: p['services'].update({'unexpected': {}}),
            'foreign_bind': lambda p: p['services']['backend'].update({'volumes': [{'type': 'bind', 'source': '/tmp/unrelated', 'target': '/data', 'read_only': True}]}),
            'docker_socket': lambda p: p['services']['backend'].update({'volumes': [{'type': 'bind', 'source': '/var/run/docker.sock', 'target': '/var/run/docker.sock'}]}),
            'external_volume': lambda p: p['volumes']['objects'].update({'external': True, 'name': 'foreign-objects'}),
            'foreign_database_volume': lambda p: p['services']['postgres']['volumes'][-1].update({'source': 'madar-schema150-phase6-20261018_database'}),
            'source_config_mount': lambda p: p['services']['gateway']['volumes'][0].update({'source': '/private/origin/gateway.conf'}),
            'host_network': lambda p: p['services']['backend'].update({'network_mode': 'host'}),
            'privileged': lambda p: p['services']['backend'].update({'privileged': True}),
            'host_pid': lambda p: p['services']['backend'].update({'pid': 'host'}),
            'restart': lambda p: p['services']['deletion-worker'].update({'restart': 'always'}),
            'public_port': lambda p: p['services']['frontend']['ports'][0].update({'host_ip': '0.0.0.0'}),
            'extra_db_port': lambda p: p['services']['postgres'].update({'ports': [{'host_ip': '127.0.0.1', 'published': '5432', 'target': 5432}]}),
            'unbounded_memory': lambda p: p['services']['backend'].update({'mem_limit': 128 * 1024**3}),
            'egress': lambda p: p['networks']['isolated'].update({'internal': False}),
            'masquerade': lambda p: p['networks']['ingress']['driver_opts'].update({'com.docker.network.bridge.enable_ip_masquerade': 'true'}),
            'wrong_backend_provider': lambda p: p['services']['backend']['environment'].update({'SUPABASE_URL': 'https://unrelated.invalid'}),
            'redirected_db': lambda p: p['services']['auth']['environment'].update({'GOTRUE_DB_DATABASE_URL': 'postgres://unrelated.invalid/live'}),
            'redirected_storage': lambda p: p['services']['storage']['environment'].update({'POSTGREST_URL': 'https://unrelated.invalid'}),
            'changed_password': lambda p: p['services']['postgres']['environment'].update({'POSTGRES_PASSWORD': 'c' * 64}),
            'foreign_env_file': lambda p: p['services']['backend'].update({'env_file': ['/tmp/unrelated.env']}),
            'missing_worker_readiness': lambda p: p['services']['backend']['environment'].pop('DATA_DELETION_WORKER_REQUIRED'),
            'wrong_worker_health_url': lambda p: p['services']['backend']['environment'].update({'DATA_DELETION_WORKER_HEALTH_URL': 'https://unrelated.invalid'}),
            'overlay_build_stamp': lambda p: p['services']['backend']['environment'].update({'MADAR_BUILD_TIMESTAMP': 'source-overlay'}),
        }
        for name, mutate in mutations.items():
            plan = valid_plan(root); mutate(plan)
            with self.subTest(name=name), patch.object(configuration.manage, 'docker') as docker:
                with self.assertRaises(RuntimeError): configuration.validate(plan, root, SHA, IMAGES, PROJECT, OWNER)
                docker.assert_not_called()

    def test_origin_compose_and_application_rewrites_are_not_read_or_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); origin = home / rehearsal.SOURCE; origin.mkdir()
            for name, body in {'compose.yaml': 'services: {evil: {network_mode: host, privileged: true}}',
                'acceptance-compose.json': '{"services":{"backend":{"volumes":["/tmp/unrelated:/host"]}}}',
                'application.env': 'SUPABASE_URL=https://unrelated.invalid\n',
                'compose.env': 'DATABASE_PASSWORD=unsafe\n'}.items(): (origin / name).write_text(body)
            credentials = {'DATABASE_PASSWORD': 'a' * 64, 'JWT_SECRET': 'b' * 64}
            with patch.object(Path, 'home', return_value=home), patch.object(rehearsal.configuration, 'generate') as generate, \
                    patch.object(configuration.manage, 'state'), patch.object(configuration.manage, 'attest_resources'), \
                    patch.object(rehearsal.acceptance.previous, 'regular', side_effect=AssertionError('Do not read origin config')):
                rehearsal.prepare_target(home / PROJECT, origin, SHA, IMAGES, {'build_timestamp': 'fresh'}, IMAGES, credentials)
            generate.assert_called_once()

    def test_live_credential_syntax_rejects_dotenv_injection_before_generation(self):
        for value in ('a' * 64 + '\nFOREIGN=x', '$VARIABLE', 'x#comment', '"quoted"', 'a\x00b'):
            with self.subTest(value=value), patch.object(configuration.manage, 'prepare') as prepare, \
                    patch.object(configuration, 'templates', return_value={}):
                with self.assertRaises(RuntimeError):
                    configuration.generate(Path('/unused'), SHA, IMAGES, {}, {'DATABASE_PASSWORD': value, 'JWT_SECRET': 'b' * 64}, PROJECT, OWNER)
                prepare.assert_not_called()

    def test_verified_compose_bytes_are_consumed_over_stdin_without_origin_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); body = json.dumps(valid_plan(root)).encode()
            (root / 'verified-compose.json').write_bytes(body)
            (root / 'configuration-receipt.json').write_text(json.dumps({'source_sha': SHA, 'images': IMAGES,
                'sha256': hashlib.sha256(body).hexdigest(), 'build_timestamp': '2026-10-18T00:00:00Z'}))
            with patch.object(configuration.manage, 'state'), patch.object(configuration.manage, 'docker', return_value=b'') as docker:
                configuration.invoke(root, ('--file', str(root / 'acceptance-compose.json'), 'up', '--detach', 'postgres'), PROJECT, OWNER)
            self.assertEqual(docker.call_args.kwargs['data'], body)
            self.assertEqual(docker.call_args.args[:5], ('compose', '--project-name', PROJECT, '--file', '-'))
            self.assertNotIn('--env-file', docker.call_args.args)

    def test_modified_plan_rejects_before_any_docker_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'verified-compose.json').write_text('{}')
            (root / 'configuration-receipt.json').write_text(json.dumps({'sha256': '0' * 64}))
            with patch.object(configuration.manage, 'state'), patch.object(configuration.manage, 'docker') as docker:
                with self.assertRaisesRegex(RuntimeError, 'configuration_changed'):
                    configuration.invoke(root, ('up', 'postgres'), PROJECT, OWNER)
                docker.assert_not_called()

    def test_compose_attached_and_equals_overrides_reject_before_state_or_docker(self):
        for argument in ('--file=/tmp/foreign.yml', '-f/tmp/foreign.yml', '-f', '--project-name=foreign',
                         '-pforeign', '-p', '--profile=foreign', '--env-file=/tmp/foreign.env',
                         '--project-directory=/tmp/foreign'):
            with self.subTest(argument=argument), patch.object(configuration.manage, 'state') as state, \
                    patch.object(configuration.manage, 'docker') as docker:
                with self.assertRaisesRegex(RuntimeError, 'unapproved_compose'):
                    configuration.invoke(Path('/private'), (argument, 'up'), PROJECT, OWNER)
                state.assert_not_called(); docker.assert_not_called()


if __name__ == '__main__': unittest.main()
