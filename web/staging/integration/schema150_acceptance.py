#!/usr/bin/env python3
"""INSPECT or REHEARSE fresh schema150 on a new, strictly owned staging stack.

The only restore origin is the authenticated synthetic independent148 capture.
This is not the protected production coordinator or a146 release rehearsal.
Interrupted attempts preserve their directory/volumes and cannot be overwritten.
"""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import sys
import tarfile
import time
from uuid import UUID

import manage
import restore
import smoke
import independent_recovery as recovery
import schema149_acceptance as previous
from fresh_artifact_acceptance import authenticated_archive, import_authenticated_image

sys.path.insert(0, str(manage.REPOSITORY / 'web'))
from deployment.lib.schema150_release import captured_source

PROJECT = 'madar-schema150-phase6-20261018'
OWNER = 'schema150-phase6-20261018'
MARKER = 'madar-schema150-phase6-synthetic'
PORTS = {'18080': '21080', '18443': '21443', '18081': '21081'}
PROTOCOL_SQL = "select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol()||':'||data_deletion_ownership_protocol() from public.application_schema_state where contract_key='core';"
SERVICES = ('postgres', 'redis', 'auth', 'rest', 'storage', 'gateway', 'backend',
            'notification-worker', 'deletion-worker', 'accepted-frontend', 'frontend')


def replace_ports(value):
    for ports in (('18080', '19080', '20080'), ('18443', '19443', '20443'), ('18081', '19081', '20081')):
        for old in ports:
            value = value.replace(':' + old, ':' + PORTS[ports[0]])
    return value


@contextmanager
def target(runtime):
    """Reuse149 setup without leaking target identity into any other harness."""
    names = ('PROJECT', 'OWNER', 'MARKER', 'PORTS', 'replace_ports')
    saved = tuple(getattr(previous, name) for name in names)
    previous.PROJECT, previous.OWNER, previous.MARKER = PROJECT, OWNER, MARKER
    previous.PORTS, previous.replace_ports = PORTS, replace_ports
    try:
        with previous.target(runtime):
            smoke.PROVIDER, smoke.APPLICATION = 'http://127.0.0.1:21081', 'http://127.0.0.1:21080/api'
            yield
    finally:
        for name, value in zip(names, saved):
            setattr(previous, name, value)


def prepare(runtime, directory, source, images, receipt, snapshots):
    # Authenticate150 before creating a directory or importing images. The
    # published149 prepare additionally checks149 SQL against its immutable hash.
    if set(snapshots) != {147, 148, 149, 150} or not all(isinstance(data, bytes) for data in snapshots.values()):
        raise RuntimeError('Captured schema150 chain is required')
    captured, checkpoint, migration149 = previous.prepare(runtime, directory, source, images, receipt)
    if migration149 != snapshots[149]:
        raise RuntimeError('Captured migration149 identity differs')
    for name in ('application.env',):
        value = previous.regular(runtime / name).decode()
        value = re.sub(r'^SCHEMA_COMPATIBLE_(MIN|MAX)=149$', r'SCHEMA_COMPATIBLE_\g<1>=150', value, flags=re.M)
        value = '\n'.join(line for line in value.splitlines() if line) + '\n'
        manage.private_write(name, value)
    # prepare149 intentionally creates a future deletion worker;150 is the first
    # compatible target. Keep its fixed restart=no and bounded resources.
    return captured, checkpoint


def restore_origin(captured, checkpoint):
    manage.compose('up', '--detach', '--wait', '--wait-timeout', '90', 'postgres')
    if manage.sql("select count(*) from pg_roles where rolname in ('supabase_auth_admin','supabase_storage_admin','authenticator');") != '0':
        raise RuntimeError('Target did not start as independent provider-role-free cluster')
    roles = '\n'.join(line for line in captured['roles.sql'].decode().splitlines() if line.strip() != 'CREATE ROLE postgres;') + '\n'
    manage.sql(roles, database='postgres')
    if manage.sql(recovery.ROLE_FINGERPRINT) != checkpoint['roles_sha256']:
        raise RuntimeError('Restored original roles/passwords/memberships differ')
    manage.docker('exec', '-i', manage.database_container(), 'pg_restore', '-U', 'postgres', '--exit-on-error',
                  '--single-transaction', '-d', 'madar_hardening', data=captured['database.dump'])
    manage.sql("comment on database madar_hardening is '" + MARKER + "';")
    manage.require_database_marker()
    before = json.loads(manage.sql(restore.FINGERPRINT_SQL))
    if hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest() != checkpoint['rows_sequences_sha256']:
        raise RuntimeError('Independent restored rows/sequences differ')
    if manage.sql(recovery.PRIVILEGE_FINGERPRINT) != checkpoint['privileges_sha256']:
        raise RuntimeError('Independent restored owners/grants/RLS/definers differ')
    if manage.sql("select schema_version from public.application_schema_state where contract_key='core';") != '148':
        raise RuntimeError('Only exact independently captured synthetic148 origin is accepted')
    if manage.sql('select count(*) from public.data_deletion_requests;') != '0':
        raise RuntimeError('Acceptance archive must not contain unfinished deletion work')
    return before


def migrate_and_preserve(before, snapshots):
    outbox = manage.sql(previous.OUTBOX_PREIMAGE)
    for number in (149, 150):
        # Use the authenticated captured bytes, never reopen a mutable SQL path.
        manage.sql("set lock_timeout='5s';set statement_timeout='45s';" + snapshots[number].decode())
        if manage.sql("select schema_version from public.application_schema_state where contract_key='core';") != str(number):
            raise RuntimeError('Unexpected committed migration boundary')
    if manage.sql(PROTOCOL_SQL) != '150:2:2:2':
        raise RuntimeError('Schema150 and all three protocol2 markers are required')
    after = json.loads(manage.sql(restore.FINGERPRINT_SQL))
    changed = {'public.application_schema_state', 'public.notification_outbox',
               'public.data_deletion_requests', 'public.data_deletion_steps'}
    for table, record in before['tables'].items():
        if table not in changed and after['tables'].get(table) != record:
            raise RuntimeError('Migration altered preserved business/Auth/Storage rows')
    # The accepted archive has no deletion requests, hence cascading steps must
    # also be empty. Check explicitly instead of silently excluding new columns.
    if any(after['tables'][table]['rows'] != 0 or before['tables'][table]['rows'] != 0
           for table in ('public.data_deletion_requests', 'public.data_deletion_steps')):
        raise RuntimeError('Unexpected deletion state in acceptance archive')
    if manage.sql(previous.OUTBOX_PREIMAGE) != outbox or before['sequences'] != after['sequences']:
        raise RuntimeError('Migration changed existing outbox business state or sequences')
    if manage.sql('select count(*) from public.data_deletion_effects;') != '0':
        raise RuntimeError('New deletion effect ledger is not empty')
    return {'business_auth_storage_rows_preserved': True, 'existing_outbox_state_preserved': True,
            'existing_sequences_preserved': True, 'deletion_origin_queue_empty': True}


def restore_objects(captured):
    manage.compose('create', 'storage')
    restore.helper(PROJECT + '_objects', "import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); t.extractall('/objects',filter='data')", writable=True, data=captured['objects.tar'])
    with tarfile.open(fileobj=io.BytesIO(captured['objects.tar'])) as archive:
        expected = {str(PurePosixPath(member.name)): hashlib.sha256(archive.extractfile(member).read()).hexdigest()
                    for member in archive.getmembers() if member.isfile()}
    if restore.inventory(PROJECT + '_objects') != expected:
        raise RuntimeError('Restored object bytes differ from authenticated archive')
    return len(expected)


def worker_health():
    identifier = manage.compose('--file', str(manage.RUNTIME / 'acceptance-compose.json'), 'ps', '-q', 'deletion-worker').decode().strip()
    if not identifier:
        raise RuntimeError('Compatible deletion worker is not running')
    value = json.loads(manage.docker('exec', identifier, 'python', '-c',
        "import json,urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8094/health',timeout=3).read().decode())"))
    if value.get('status') != 'ok' or value.get('consuming') is not True:
        raise RuntimeError('Deletion worker is healthy but not consuming')
    return value


def service_values():
    return dict(line.split('=', 1) for line in previous.regular(manage.RUNTIME / 'application.env').decode().splitlines() if line)


def rpc(name, arguments, token):
    value, _ = smoke.http('POST', '/rest/v1/rpc/' + name, token=token, body=arguments)
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def deletion_workflow():
    """Real GoTrue identities/Storage and service-role requests; real worker only.

    No provider mock, synthetic protocol marker, direct lifecycle state update,
    manual step completion or fake acknowledgement can satisfy this probe.
    """
    manage.require_database_marker()
    if manage.sql(PROTOCOL_SQL) != '150:2:2:2':
        raise RuntimeError('Deletion workflow requires exact compatible database')
    values = service_values(); token = values['SUPABASE_SERVICE_KEY']
    fixture = json.loads(previous.regular(manage.RUNTIME / 'smoke-fixture.json'))
    actor = int(fixture['admin_user_id'])
    scope = 'phase6-' + secrets.token_hex(8)
    avatar = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')
    subjects = {}
    for label in ('user', 'tenant', 'foreign'):
        tenant = int(manage.sql("insert into public.tenants(brand_name,owner_name) values(" + smoke.literal(scope + '-' + label) + ",'Synthetic150') returning tenant_id;"))
        email = scope + '-' + label + '@example.com'
        auth, _ = smoke.http('POST', '/auth/v1/admin/users', token=token,
                            body={'email': email, 'password': secrets.token_urlsafe(24), 'email_confirm': True})
        auth_id = str(UUID(auth['id']))
        user = int(manage.sql("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) values(" +
            smoke.literal(auth_id) + ",'Synthetic','Deletion150'," + smoke.literal(email) + f",{tenant},'active',true,now()) returning id;"))
        key = 'users/' + auth_id + '/' + scope + '.png'
        smoke.http('POST', '/storage/v1/object/avatars/' + key, token=token, body=avatar,
                   headers={'Content-Type': 'image/png'})
        manage.sql("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256) values(" +
                   f"{tenant},{user},'avatar'," + smoke.literal(key) + f",{len(avatar)}," + smoke.literal(hashlib.sha256(avatar).hexdigest()) + ');')
        subjects[label] = {'tenant': tenant, 'user': user, 'auth': auth_id, 'key': key}
    # Keep all evidence/identities private. Incomplete probes are retained, never
    # auto-deleted or marked complete to make acceptance pass.
    manage.private_write('deletion-fixtures.json', json.dumps({'scope': scope, 'subjects': subjects}) + '\n')
    foreign = subjects['foreign']
    foreign_sql = ("select md5(jsonb_build_object('tenant',(select to_jsonb(t) from public.tenants t where tenant_id=" + str(foreign['tenant']) +
        "),'user',(select to_jsonb(u) from public.users u where id=" + str(foreign['user']) +
        "),'auth',(select to_jsonb(a) from auth.users a where id=" + smoke.literal(foreign['auth']) +
        "),'objects',(select jsonb_agg(to_jsonb(o) order by o.id) from public.storage_objects o where tenant_id=" + str(foreign['tenant']) + "))::text);")
    foreign_before = manage.sql(foreign_sql)
    results = {}
    for label in ('user', 'tenant'):
        subject = subjects[label]
        arguments = {'p_request_type': label, 'p_target_user_id': subject['user'] if label == 'user' else None,
                     'p_target_tenant_id': subject['tenant'] if label == 'tenant' else None,
                     'p_requested_by_user_id': subject['user'] if label == 'user' else actor, 'p_retention_until': None}
        row = rpc('create_data_deletion_request', arguments, token)
        request_id = str(UUID(row['id']))
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            current = json.loads(manage.sql('select to_jsonb(r) from public.data_deletion_requests r where id=' + smoke.literal(request_id) + ';'))
            if current['state'] in ('completed', 'completed_with_retained_records', 'failed_manual_intervention'):
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Synthetic deletion did not finish within bounded acceptance time')
        if current['state'] not in ('completed', 'completed_with_retained_records') or current['verification_status'] not in ('verified', 'verified_with_retained_records'):
            raise RuntimeError('Synthetic deletion requires intervention; private workflow evidence retained')
        steps = json.loads(manage.sql('select json_agg(jsonb_build_object(\'step\',step_key,\'state\',state,\'attempts\',attempts) order by step_order) from public.data_deletion_steps where request_id=' + smoke.literal(request_id) + ';'))
        if len(steps) != 10 or any(step['state'] != 'completed' for step in steps):
            raise RuntimeError('Deletion finalized without all authoritative steps complete')
        if manage.sql(f"select count(*) from public.users where id={subject['user']};") != '0':
            raise RuntimeError('Deleted application user still exists')
        if label == 'tenant' and manage.sql(f"select count(*) from public.tenants where tenant_id={subject['tenant']};") != '0':
            raise RuntimeError('Deleted tenant still exists')
        smoke.http('GET', '/auth/v1/admin/users/' + subject['auth'], token=token, expected=(404,))
        smoke.http('GET', '/storage/v1/object/avatars/' + subject['key'], token=token, expected=(400, 404))
        effects = json.loads(manage.sql('select json_agg(jsonb_build_object(\'state\',state,\'outcome\',outcome) order by effect_key) from public.data_deletion_effects where request_id=' + smoke.literal(request_id) + ';'))
        if not effects or any(effect['state'] != 'confirmed' for effect in effects):
            raise RuntimeError('Deletion has unresolved external operation intent')
        results[label] = {'state': current['state'], 'all_ten_steps_completed': True,
                          'real_auth_identity_removed': True, 'real_storage_object_removed': True,
                          'effects_confirmed': len(effects), 'attempt_count': current['attempt_count']}
    if manage.sql(foreign_sql) != foreign_before:
        raise RuntimeError('Deletion changed unrelated tenant/application/Auth/metadata')
    data, _ = smoke.http('GET', '/storage/v1/object/avatars/' + foreign['key'], token=token)
    if data != avatar:
        raise RuntimeError('Deletion changed unrelated tenant object bytes')
    args = ('--file', str(manage.RUNTIME / 'acceptance-compose.json'))
    manage.compose(*args, 'stop', '--timeout', '15', 'deletion-worker')
    manage.compose(*args, 'start', '--wait', '--wait-timeout', '60', 'deletion-worker')
    worker_health()
    return {'user': results['user'], 'tenant': results['tenant'], 'foreign_tenant_preserved': True,
            'live_worker_processed_both_requests': True, 'worker_restart_consumption_verified': True,
            'integration_revocation_tested': False, 'host_file_deletion_tested': False,
            'lost_external_response_tested': False}


def runtime_identity(images, source):
    code = {}
    args = ('--file', str(manage.RUNTIME / 'acceptance-compose.json'))
    for service in ('backend', 'notification-worker', 'deletion-worker', 'accepted-frontend'):
        identifier = manage.compose(*args, 'ps', '-q', service).decode().strip()
        if not identifier:
            raise RuntimeError('Missing accepted runtime component')
        row = json.loads(manage.docker('inspect', identifier))[0]
        if row['Image'] != images['frontend' if service == 'accepted-frontend' else 'backend']:
            raise RuntimeError('Actual runtime image substitution')
        if any(m.get('Destination', '').startswith('/app') for m in row.get('Mounts', [])):
            raise RuntimeError('Source overlay cannot satisfy fresh-image acceptance')
        if service == 'backend':
            for name in ('services/data_deletion_service.py', 'workers/data_deletion_worker.py', 'workers/notification_worker.py'):
                actual = manage.docker('exec', identifier, 'python', '-c', "import hashlib;print(hashlib.sha256(open('/app/" + name + "','rb').read()).hexdigest())").decode().strip()
                expected = hashlib.sha256((manage.REPOSITORY / 'web/backend' / name).read_bytes()).hexdigest()
                if actual != expected:
                    raise RuntimeError('Runtime source bytes differ from exact acceptance source')
                code[name] = actual
    return code


def main(mode, directory, source):
    manage.require_staging_host()
    if mode not in ('INSPECT', 'REHEARSE') or not re.fullmatch('[0-9a-f]{40}', source or ''):
        raise RuntimeError('Explicit mode and exact source commit required')
    runtime = Path.home() / PROJECT
    with target(runtime):
        _, snapshots = captured_source(manage.REPOSITORY)
        artifact, run, images, receipt = previous.artifacts(directory, source)
        if mode == 'INSPECT':
            return {'mode': mode, 'project': PROJECT, 'source_sha': source, 'images': images,
                    'origin_schema': 148, 'target_schema': 150, 'ports': PORTS,
                    'existing_project_preserved': runtime.exists(), 'mutations_executed': False,
                    'migration_sha256': {str(n): hashlib.sha256(snapshots[n]).hexdigest() for n in (149, 150)}}
        started = time.monotonic()
        captured, checkpoint = prepare(runtime, directory, source, images, receipt, snapshots)
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
                        raise RuntimeError('Imported exact-source fresh image identity mismatch')
            before = restore_origin(captured, checkpoint)
            preservation = migrate_and_preserve(before, snapshots)
            objects = restore_objects(captured)
            args = ('--file', str(runtime / 'acceptance-compose.json'))
            manage.compose(*args, 'up', '--detach', '--wait', '--wait-timeout', '180', *SERVICES)
            manage.attest_resources(); manage.require_database_marker()
            fixture = json.loads(previous.regular(Path.home() / 'madar-hardening-20261016/smoke-fixture.json'))
            identity = recovery.original_identity_acceptance(fixture)
            smoke.main()
            worker_health()
            deletion = deletion_workflow()
            code = runtime_identity(images, source)
            report = {'scope': 'independent synthetic148 archive restore, captured149/150 and fresh full native150 runtime',
                'source_sha': source, 'images': images, 'run_id': run['id'], 'artifact_id': artifact['id'],
                'origin_schema': 148, 'schema': 150, 'delivery_protocol': 2, 'outbox_protocol': 2, 'deletion_protocol': 2,
                'migration_sha256': {str(n): hashlib.sha256(snapshots[n]).hexdigest() for n in (149, 150)},
                'source_overlay_used': False, 'preservation': preservation, 'objects_restored': objects,
                'original_identity_acceptance': identity, 'native_auth_mfa_storage_notifications_readiness': True,
                'deletion_workflow': deletion, 'runtime_code_sha256': code,
                'elapsed_seconds': round(time.monotonic() - started, 3), 'production_modified': False,
                'production_authorized': False, 'limitations': ['not146 protected controller acceptance',
                    'same VM, not off-host/full application PITR', 'not complete product browser E2E',
                    'real integration revocation and host-file deletion not exercised',
                    'external outcome ambiguity covered separately by native tests, not this happy-path probe']}
            manage.private_write('schema150-acceptance.json', json.dumps(report, indent=2) + '\n')
            return report
        except BaseException:
            # Preserve archives and incomplete queue evidence; stop ONLY this
            # positively attested150 project. Never alter source148/149 services.
            manage.attest_resources()
            manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'stop', '--timeout', '15')
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('INSPECT', 'REHEARSE'), nargs='?', default='INSPECT')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    args = parser.parse_args()
    print(json.dumps(main(args.mode, args.artifacts, args.source_sha), sort_keys=True))
