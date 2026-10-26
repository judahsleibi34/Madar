#!/usr/bin/env python3
"""INSPECT or REHEARSE fresh schema149 images on a separately restored synthetic stack.

This is a staging-only application acceptance harness, not a privileged migration
executor. Its origin is an existing immutable synthetic schema148 recovery archive.
It never stops, edits, or restarts the source project.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import time
from uuid import uuid4

import manage
import restore
import smoke
import independent_recovery as recovery
from fresh_artifact_acceptance import authenticated_archive, import_authenticated_image, verify_archive, INPUTS

PROJECT = 'madar-schema149-phase5-20261017'
OWNER = 'schema149-phase5-20261017'
MARKER = 'madar-schema149-phase5-synthetic'
SOURCE_PROJECT = 'madar-independent-recovery-20261017-attempt3'
MIGRATION_SHA = '8ed767df57f5c02be50d83621fe45d314b3d1fdb42d2b7a470170519bdf1f869'
PORTS = {'18080': '20080', '18443': '20443', '18081': '20081'}
OUTBOX_PREIMAGE = """select md5(coalesce(jsonb_agg(
 (to_jsonb(o)-'claim_generation'-'processing_lease_until') order by
 (to_jsonb(o)-'claim_generation'-'processing_lease_until')::text)::text,'[]'))
 from public.notification_outbox o;"""


@contextmanager
def target(runtime):
    old = manage.PROJECT, manage.OWNER, manage.MARKER, manage.RUNTIME, manage.HERE, smoke.PROVIDER, smoke.APPLICATION
    manage.PROJECT, manage.OWNER, manage.MARKER = PROJECT, OWNER, MARKER
    manage.RUNTIME, manage.HERE = runtime, runtime
    smoke.PROVIDER, smoke.APPLICATION = 'http://127.0.0.1:20081', 'http://127.0.0.1:20080/api'
    try:
        yield
    finally:
        manage.PROJECT, manage.OWNER, manage.MARKER, manage.RUNTIME, manage.HERE, smoke.PROVIDER, smoke.APPLICATION = old


def replace_ports(value):
    for old, new in PORTS.items():
        value = value.replace(':' + old, ':' + new)
    for old, new in (('19080', '20080'), ('19443', '20443'), ('19081', '20081')):
        value = value.replace(':' + old, ':' + new)
    return value


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Expected regular private fixture file')
    return path.read_bytes()


def archive_members(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('Unsafe synthetic object archive')


def artifacts(directory, source):
    if directory.is_symlink() or directory.parent.resolve() != Path.home().resolve():
        raise RuntimeError('Artifact directory must be private direct staging-home child')
    run = json.loads(regular(directory / 'run.json'))
    artifact = json.loads(regular(directory / 'artifact.json'))
    images = json.loads(regular(directory / 'receipt.json'))['images']
    inputs = {name: hashlib.sha256((manage.REPOSITORY / name).read_bytes()).hexdigest() for name in INPUTS}
    receipt = verify_archive(directory / 'candidate.zip', artifact, run, source_sha=source,
                             images=images, expected_inputs=inputs)
    return artifact, run, images, receipt


def prepare(runtime, directory, source, images, receipt):
    if runtime.exists() or runtime.is_symlink():
        raise RuntimeError('Preserve the existing acceptance project; automatic retry is prohibited')
    if shutil.disk_usage(Path.home()).free < 8 * 1024**3:
        raise RuntimeError('Insufficient bounded synthetic acceptance disk headroom')
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:')))
    if available < 2200 * 1024:
        raise RuntimeError('Insufficient synthetic acceptance memory headroom')
    source_runtime = Path.home() / SOURCE_PROJECT
    source_state = json.loads(regular(source_runtime / 'owner.json'))
    if (source_state.get('project') != SOURCE_PROJECT
            or source_state.get('owner') != 'architecture-hardening-20261016'
            or source_state.get('marker') != 'madar-hardening-synthetic-148-independent'):
        raise RuntimeError('Unrecognized synthetic recovery archive owner')
    checkpoint = json.loads(regular(source_runtime / 'capture-checkpoint.json'))
    captured = {}
    for name in ('database.dump', 'roles.sql', 'objects.tar'):
        captured[name] = regular(source_runtime / name)
        if hashlib.sha256(captured[name]).hexdigest() != checkpoint['archive_sha256'][name]:
            raise RuntimeError('Synthetic recovery archive digest mismatch')
    archive_members(captured['objects.tar'])
    sql = regular(manage.REPOSITORY / 'web/database/migrations/149_fence_notification_outbox_claims.sql')
    mirrored = regular(manage.REPOSITORY / 'web/supabase/migrations/149_fence_notification_outbox_claims.sql')
    if sql != mirrored or hashlib.sha256(sql).hexdigest() != MIGRATION_SHA:
        raise RuntimeError('Published migration149 bytes do not match exact immutable contract')
    runtime.mkdir(mode=0o700)
    manage.private_write('owner.json', json.dumps({'owner': OWNER, 'project': PROJECT, 'source_sha': source,
                          'database': 'madar_hardening', 'marker': MARKER}) + '\n')
    for name in ('database.dump', 'roles.sql', 'objects.tar'):
        restore.write_binary(runtime / name, captured[name])
    manage.private_write('source-checkpoint.json', json.dumps(checkpoint) + '\n')
    for name in ('compose.env', 'application.env'):
        value = regular(source_runtime / name).decode().replace(str(source_runtime), str(runtime))
        value = replace_ports(value)
        value = re.sub(r'^(SOURCE_SHA|MADAR_RELEASE_SHA)=.*$', r'\g<1>=' + source, value, flags=re.M)
        value = re.sub(r'^SCHEMA_COMPATIBLE_(MIN|MAX)=.*$', r'SCHEMA_COMPATIBLE_\g<1>=149', value, flags=re.M)
        value = re.sub(r'^MADAR_BUILD_TIMESTAMP=.*$', 'MADAR_BUILD_TIMESTAMP=' + receipt['build_timestamp'], value, flags=re.M)
        if name == 'application.env':
            value = value.rstrip() + '\nDATA_DELETION_WORKER_ENABLED=true\nDATA_DELETION_WORKER_HEALTH_HOST=0.0.0.0\nDATA_DELETION_WORKER_POLL_SECONDS=2\n'
        manage.private_write(name, value)
    for name in ('tls.crt', 'tls.key'):
        restore.write_binary(runtime / name, regular(source_runtime / name)); (runtime / name).chmod(0o444)
    manage.private_write('bootstrap.sql', '-- Fresh independent cluster: no inherited provider roles.\n', mounted=True)
    base = regular(manage.REPOSITORY / 'web/staging/integration/compose.yaml').decode()
    base = replace_ports(base).replace('architecture-hardening-20261016', OWNER)
    base = base.replace('image: madar-hardening-application:${SOURCE_SHA:?}', 'image: ' + images['backend'])
    base = base.replace('./gateway.conf', str(manage.REPOSITORY / 'web/staging/integration/gateway.conf'))
    base = base.replace('mem_limit: 768m\n    cpus: 2.0', 'mem_limit: 512m\n    cpus: 1.0')
    # The utility TLS edge proxies to the actual freshly built frontend image.
    base = base.replace('./frontend.conf', str(runtime / 'fresh-edge.conf'))
    base = base.replace('      - ../../frontend/dist:/site:ro\n', '')
    manage.private_write('compose.yaml', base)
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
              'labels': {'com.madar.staging.owner': OWNER}, 'mem_limit': '128m', 'cpus': 0.5,
              'logging': {'driver': 'json-file', 'options': {'max-size': '2m', 'max-file': '2'}}}
    extra = {'services': {
        'accepted-frontend': {**common, 'image': images['frontend'], 'pull_policy': 'never', 'user': 'nginx',
          'tmpfs': ['/tmp:rw,noexec,nosuid,size=32m', '/var/cache/nginx:rw,noexec,nosuid,uid=101,gid=101,size=32m', '/etc/nginx/conf.d:rw,noexec,nosuid,uid=101,gid=101,size=2m'],
          'environment': {'APP_ENV': 'staging', 'MADAR_RELEASE_SHA': source, 'MADAR_PUBLIC_SITE_DOMAIN': 'hardening.test', 'MADAR_CSP_CONNECT_SRC': "'self'", 'MADAR_HSTS': ''},
          'depends_on': {'backend': {'condition': 'service_healthy'}}},
        'frontend': {'depends_on': {'accepted-frontend': {'condition': 'service_started'}}},
        'deletion-worker': {**common, 'image': images['backend'], 'pull_policy': 'never', 'user': '65534:65534',
          'command': ['python', '-m', 'workers.data_deletion_worker'], 'env_file': [str(runtime / 'application.env')],
          'tmpfs': ['/tmp:rw,nosuid,nodev,size=128m,mode=1777'], 'mem_limit': '256m',
          'depends_on': {'backend': {'condition': 'service_healthy'}},
          'healthcheck': {'test': ['CMD', 'python', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8094/health',timeout=2)"], 'interval': '3s', 'timeout': '3s', 'retries': 30}}
    }}
    manage.private_write('acceptance-compose.json', json.dumps(extra))
    manage.state(); manage.attest_resources()
    return captured, checkpoint, sql


def cancellation_probe():
    """Real service-role PostgREST cancellation; no complete deletion is run."""
    manage.require_database_marker()
    manage.compose('--file', str(manage.RUNTIME / 'acceptance-compose.json'),
                   'stop', '--timeout', '15', 'deletion-worker', 'notification-worker')
    values = dict(line.split('=', 1) for line in (manage.RUNTIME / 'application.env').read_text().splitlines() if '=' in line)
    identity, request_id, outbox_id, foreign_id, delivery_id = [str(uuid4()) for _ in range(5)]
    tenant = user = None
    try:
        tenant = int(manage.sql("insert into public.tenants(brand_name,owner_name,lifecycle_state) values('Synthetic149 RPC cancellation','Fixture','deletion_pending') returning tenant_id;"))
        manage.sql(f"insert into auth.users(id,email,email_confirmed_at) values('{identity}','{identity}@example.invalid',now());")
        user = int(manage.sql("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status) "
                            f"values('{identity}','Synthetic','Cancellation','{identity}@example.invalid',{tenant},'deletion_pending') returning id;"))
        manage.sql(f"""begin;
insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot,target_tenant_id_snapshot,state,attempt_count,lease_owner,lease_until)
 values('{request_id}','user',{user},{tenant},'in_progress',2,'phase5-rpc-probe',clock_timestamp()+interval '2 minutes');
insert into public.notification_outbox(id,tenant_id,user_id,channel,template,status,claim_generation,processing_lease_until)
 values('{outbox_id}',{tenant},{user},'email','synthetic','processing',1,clock_timestamp()+interval '2 minutes');
insert into public.notification_outbox(id,channel,template,status) values('{foreign_id}','email','synthetic','pending');
insert into public.notification_deliveries(id,outbox_id,tenant_id,user_id,channel,template,deduplication_key,status,claim_generation,processing_lease_until)
 values('{delivery_id}','{outbox_id}',{tenant},{user},'internal','synthetic','{delivery_id}','processing',1,clock_timestamp()+interval '2 minutes');
commit;""")
        arguments = {'p_request_id': request_id, 'p_lease_owner': 'foreign-worker', 'p_claim_attempt': 2}
        denied, _ = smoke.http('POST', '/rest/v1/rpc/stop_deletion_notification_work', token=values['SUPABASE_SERVICE_KEY'], body=arguments, expected=(400,))
        if denied.get('message') != 'deletion_notification_authority_lost':
            raise RuntimeError('Wrong-owner cancellation denial reason was not verified')
        if manage.sql(f"select status from public.notification_outbox where id='{outbox_id}';") != 'processing':
            raise RuntimeError('Rejected cancellation changed work')
        arguments['p_lease_owner'] = 'phase5-rpc-probe'
        stopped, _ = smoke.http('POST', '/rest/v1/rpc/stop_deletion_notification_work', token=values['SUPABASE_SERVICE_KEY'], body=arguments)
        if stopped != 2 or manage.sql(f"select status from public.notification_outbox where id='{foreign_id}';") != 'pending':
            raise RuntimeError('Cancellation scope or changed count invalid')
        denied, _ = smoke.http('POST', '/rest/v1/rpc/finish_notification_outbox_v2', token=values['SUPABASE_SERVICE_KEY'],
                   body={'p_outbox_id': outbox_id, 'p_claim_generation': 1, 'p_outcome': 'sent'}, expected=(400,))
        if denied.get('message') != 'notification_outbox_claim_lost':
            raise RuntimeError('Superseded-owner denial reason was not verified')
        # Check the actual database state independently of HTTP error mapping.
        if manage.sql(f"select status from public.notification_outbox where id='{outbox_id}';") != 'dead':
            raise RuntimeError('Superseded outbox owner acknowledged cancelled work')
        return {'actual_service_role_rpc': True, 'wrong_owner_rejected': True,
                'subject_scoped_outbox_delivery_cancellation': True, 'foreign_work_preserved': True,
                'complete_deletion_workflow_tested': False}
    finally:
        manage.sql(f"begin; delete from public.notification_deliveries where id='{delivery_id}'; "
                   f"delete from public.notification_outbox where id in ('{outbox_id}','{foreign_id}'); "
                   f"delete from public.data_deletion_requests where id='{request_id}'; commit;")
        if user is not None: manage.sql(f'delete from public.users where id={user};')
        manage.sql(f"delete from auth.users where id='{identity}';")
        if tenant is not None: manage.sql(f'delete from public.tenants where tenant_id={tenant};')
        manage.compose('--file', str(manage.RUNTIME / 'acceptance-compose.json'),
                       'start', '--wait', '--wait-timeout', '60', 'notification-worker')


def resume_application(mode, directory, source):
    """Explicit same-source149 recovery after a failed acceptance probe.

    No SQL migration is replayed, no new image is relabeled, and the restore
    origin is not represented as a146 coordinated release rehearsal.
    """
    manage.require_staging_host()
    if mode != 'REHEARSE' or not re.fullmatch('[0-9a-f]{40}', source):
        raise RuntimeError('Application resume requires explicit REHEARSE and exact source')
    runtime = Path.home() / PROJECT
    with target(runtime):
        state = manage.state(); manage.attest_resources()
        if state['source_sha'] != source:
            raise RuntimeError('Cannot adopt a different source during interrupted acceptance')
        artifact, run, images, receipt = artifacts(directory, source)
        for role in ('backend', 'frontend'):
            row = json.loads(manage.docker('image', 'inspect', images[role]))[0]
            labels = row['Config'].get('Labels', {})
            if (row['Id'] != images[role] or labels.get('com.madar.release.sha') != source
                    or labels.get('org.opencontainers.image.revision') != source
                    or labels.get('com.madar.build.mode') != 'fresh-locked-ci'):
                raise RuntimeError('Retained imported image identity changed')
        manage.compose('up', '--detach', '--wait', '--wait-timeout', '90', 'postgres')
        manage.require_database_marker()
        if manage.sql("select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol() from application_schema_state where contract_key='core';") != '149:2:2':
            raise RuntimeError('Application resume requires already committed149 and both protocols2')
        if manage.sql('select count(*) from public.data_deletion_requests;') != '0':
            raise RuntimeError('Deletion startup compatibility probe requires empty synthetic queue')
        # A previous staging-only generator emitted one empty line. Retain the
        # exact nonempty key/value preimage; no credential or source changes.
        lines = [line for line in regular(runtime / 'application.env').decode().splitlines() if line]
        if any('=' not in line for line in lines):
            raise RuntimeError('Unexpected private application configuration syntax')
        manage.private_write('application.env', '\n'.join(lines) + '\n')
        started = time.monotonic()
        try:
            manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'up', '--detach', '--wait', '--wait-timeout', '150')
            fixture = json.loads(regular(Path.home() / 'madar-hardening-20261016/smoke-fixture.json'))
            identity = recovery.original_identity_acceptance(fixture)
            smoke.main()
            cancellation = cancellation_probe()
            values = dict(line.split('=', 1) for line in lines)
            protocols = {}
            for name in ('notification_delivery_protocol', 'notification_outbox_protocol'):
                value, _ = smoke.http('POST', '/rest/v1/rpc/' + name, token=values['SUPABASE_SERVICE_KEY'], body={})
                if value != 2: raise RuntimeError('PostgREST protocol mismatch')
                protocols[name] = value
            result = {'scope': 'native synthetic schema149 application acceptance after explicit interrupted-probe resume',
                'source_sha': source, 'images': images, 'run_id': run['id'], 'artifact_id': artifact['id'],
                'origin_schema': 148, 'schema': 149, 'protocols': protocols, 'source_overlay_used': False,
                'explicit_application_resume': True, 'sql_migration_replayed': False,
                'original_identity_acceptance': identity, 'native_auth_mfa_storage_outbox_delivery_frontend_readiness': True,
                'deletion_cancellation': cancellation, 'deletion_worker_retained_stopped': True,
                'elapsed_seconds': round(time.monotonic() - started, 3), 'production_modified': False,
                'limitations': ['not146 coordinated controller acceptance', 'same VM independent cluster, not off-host',
                  'deletion lifecycle ownership remains release blocking; worker stopped',
                  'not complete product browser E2E', 'not full application PITR or production approval']}
            manage.private_write('schema149-acceptance.json', json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, sort_keys=True))
        except BaseException:
            manage.attest_resources()
            manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'stop', '--timeout', '15')
            raise


def main(mode, directory, source):
    manage.require_staging_host()
    if mode not in {'INSPECT', 'REHEARSE'}:
        raise RuntimeError('Only read-only INSPECT or explicit isolated REHEARSE is supported')
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise RuntimeError('Exact source commit required')
    runtime = Path.home() / PROJECT
    with target(runtime):
        artifact, run, images, receipt = artifacts(directory, source)
        if mode == 'INSPECT':
            print(json.dumps({'mode': mode, 'project': PROJECT, 'source_sha': source, 'images': images,
                              'origin_schema': 148, 'target_schema': 149, 'ports': PORTS,
                              'existing_project_preserved': runtime.exists(), 'production_modified': False}))
            return
        started = time.monotonic()
        captured, checkpoint, migration = prepare(runtime, directory, source, images, receipt)
        try:
            imported = runtime / 'authenticated-images'; imported.mkdir(mode=0o700)
            with authenticated_archive(directory / 'candidate.zip', artifact['digest']) as archive:
                for role in ('backend', 'frontend'):
                    import_authenticated_image(archive, role, receipt['archives'][role], imported / (role + '.tar.gz'))
                    row = json.loads(manage.docker('image', 'inspect', images[role]))[0]
                    labels = row['Config'].get('Labels', {})
                    if (row['Id'] != images[role] or labels.get('com.madar.release.sha') != source
                            or labels.get('org.opencontainers.image.revision') != source
                            or labels.get('com.madar.build.mode') != 'fresh-locked-ci'):
                        raise RuntimeError('Imported exact-source image identity mismatch')
            manage.compose('up', '--detach', '--wait', '--wait-timeout', '90', 'postgres')
            if manage.sql("select count(*) from pg_roles where rolname in ('supabase_auth_admin','supabase_storage_admin','authenticator');") != '0':
                raise RuntimeError('Target did not start as independent provider-role-free cluster')
            roles = '\n'.join(line for line in captured['roles.sql'].decode().splitlines()
                              if line.strip() != 'CREATE ROLE postgres;') + '\n'
            manage.sql(roles, database='postgres')
            if manage.sql(recovery.ROLE_FINGERPRINT) != checkpoint['roles_sha256']:
                raise RuntimeError('Restored provider role/password/membership state differs')
            manage.docker('exec', '-i', manage.database_container(), 'pg_restore', '-U', 'postgres', '--exit-on-error',
                          '--single-transaction', '-d', 'madar_hardening', data=captured['database.dump'])
            manage.sql("comment on database madar_hardening is '" + MARKER + "';")
            manage.require_database_marker()
            before = json.loads(manage.sql(restore.FINGERPRINT_SQL))
            digest = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
            if digest != checkpoint['rows_sequences_sha256']:
                raise RuntimeError('Restored rows/sequences differ from immutable capture')
            if manage.sql(recovery.PRIVILEGE_FINGERPRINT) != checkpoint['privileges_sha256']:
                raise RuntimeError('Restored grants/owners/definer/RLS configuration differs')
            if manage.sql("select schema_version from public.application_schema_state where contract_key='core';") != '148':
                raise RuntimeError('This application acceptance has exact schema148 archive origin')
            outbox_preimage = manage.sql(OUTBOX_PREIMAGE)
            manage.sql("set lock_timeout='5s';set statement_timeout='30s';" + migration.decode())
            if manage.sql("select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol() from application_schema_state where contract_key='core';") != '149:2:2':
                raise RuntimeError('Schema and both ownership protocols must match149/2/2')
            after = json.loads(manage.sql(restore.FINGERPRINT_SQL))
            for name, record in before['tables'].items():
                if name not in {'public.application_schema_state', 'public.notification_outbox'} and after['tables'][name] != record:
                    raise RuntimeError('Unexpected business/Auth/Storage row mutation during149')
            if before['sequences'] != after['sequences']:
                raise RuntimeError('Migration149 changed restored sequence state')
            if manage.sql(OUTBOX_PREIMAGE) != outbox_preimage:
                raise RuntimeError('Migration149 changed existing outbox business state')
            if manage.sql('select count(*) from public.data_deletion_requests;') != '0':
                raise RuntimeError('Deletion startup probe requires an empty synthetic deletion queue')
            manage.compose('create', 'storage')
            restore.helper(PROJECT + '_objects', "import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); t.extractall('/objects',filter='data')", writable=True, data=captured['objects.tar'])
            # Object archive itself was authenticated and all members validated before extraction.
            with tarfile.open(fileobj=io.BytesIO(captured['objects.tar'])) as archive:
                expected_objects = {str(PurePosixPath(member.name)): hashlib.sha256(archive.extractfile(member).read()).hexdigest()
                                    for member in archive.getmembers() if member.isfile()}
            actual_objects = restore.inventory(PROJECT + '_objects')
            if actual_objects != expected_objects:
                raise RuntimeError('Restored object file bytes differ from authenticated archive')
            object_count = len(actual_objects)
            manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'up', '--detach', '--wait', '--wait-timeout', '150')
            manage.attest_resources(); manage.require_database_marker()
            original_fixture = json.loads(regular(Path.home() / 'madar-hardening-20261016/smoke-fixture.json'))
            identity = recovery.original_identity_acceptance(original_fixture)
            smoke.main()
            protocols = {}
            values = dict(line.split('=', 1) for line in (runtime / 'application.env').read_text().splitlines() if '=' in line)
            for name in ('notification_delivery_protocol', 'notification_outbox_protocol'):
                value, _ = smoke.http('POST', '/rest/v1/rpc/' + name, token=values['SUPABASE_SERVICE_KEY'], body={})
                if value != 2: raise RuntimeError('PostgREST ownership protocol mismatch')
                protocols[name] = value
            rows = json.loads(manage.docker('inspect', *manage.compose('ps', '-q').decode().split()))
            image_identity = all(row['Image'] == images['backend'] for row in rows
                                 if row['Config']['Labels']['com.docker.compose.service'] in {'backend', 'notification-worker', 'deletion-worker'})
            if not image_identity: raise RuntimeError('Runtime worker/backend image substitution')
            # The existing149 cancellation RPC does not fence every deletion
            # lifecycle transition. This is only an empty-queue startup probe.
            manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'stop', '--timeout', '15', 'deletion-worker')
            cancellation = cancellation_probe()
            report = {'scope': 'independent synthetic schema148 archive restore then native full-provider schema149 acceptance',
                'source_sha': source, 'images': images, 'run_id': run['id'], 'artifact_id': artifact['id'],
                'origin_schema': 148, 'schema': 149, 'protocols': protocols, 'source_overlay_used': False,
                'roles_passwords_memberships_preserved': True, 'grants_rls_definer_preimage_preserved': True,
                'restored_database_rows_sequences_preserved': True, 'migration149_preservation_checked': True,
                'objects_restored': object_count, 'original_identity_acceptance': identity,
                'native_auth_mfa_storage_outbox_delivery_frontend_readiness': True,
                'deletion_worker_empty_queue_startup_exact_image': image_identity,
                'deletion_worker_retained_stopped': True, 'service_count_during_probe': len(rows),
                'deletion_cancellation': cancellation,
                'elapsed_seconds': round(time.monotonic() - started, 3), 'production_modified': False,
                'limitations': ['origin148, not146 coordinated controller acceptance', 'same VM independent cluster, not off-host',
                  'deletion ownership defect remains a release blocker; worker retained stopped', 'not complete product browser E2E',
                  'not full application PITR or independently authorized production release']}
            manage.private_write('schema149-acceptance.json', json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, sort_keys=True))
        except BaseException:
            # Preserve evidence and every owned volume. Never touch the source project.
            manage.attest_resources()
            manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'stop', '--timeout', '15')
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('INSPECT', 'REHEARSE'), nargs='?', default='INSPECT')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--resume-application', action='store_true', help='Explicitly resume same-source already-committed149 application probes; never reapply migration')
    args = parser.parse_args()
    if args.resume_application:
        resume_application(args.mode, args.artifacts, args.source_sha)
    else:
        main(args.mode, args.artifacts, args.source_sha)
