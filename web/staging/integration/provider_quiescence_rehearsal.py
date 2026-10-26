#!/usr/bin/env python3
"""Synthetic provider-writer fence proof; never a production executor.

This creates its own network-none PostgreSQL instance. It does not stop retained
providers, change the governed coordinator, or satisfy production admission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shutil
import subprocess
import sys
import time

import manage

IMAGE = 'postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
PREFIX = 'madar-provider-quiescence-'
SCOPE_LABEL = 'com.madar.rehearsal.scope'
MARKER = 'madar-provider-quiescence-synthetic-20261017'
ROLE = 'synthetic_provider'
ROOTS_SQL = """SELECT encode(sha256(convert_to(jsonb_build_object(
 'sessions',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM auth.sessions t),
 'mfa',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM auth.mfa_factors t),
 'objects',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM storage.objects t),
 'business',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM public.business_probe t)
 )::text,'UTF8')),'hex');"""


def runtime_path(raw):
    path = Path(raw)
    if (not path.is_absolute() or path.is_symlink() or path.parent.resolve() != Path.home().resolve()
            or not re.fullmatch(PREFIX + '[0-9a-f]{12}', path.name)):
        raise RuntimeError('provider_rehearsal_runtime_invalid')
    if path.exists():
        stat = path.stat()
        if not path.is_dir() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise RuntimeError('provider_rehearsal_runtime_untrusted')
    return path


def read_state(runtime):
    runtime = runtime_path(runtime)
    state = private_json(runtime, 'owner.json')
    if (set(state) != {'scope', 'owner', 'container', 'volume', 'marker', 'system_identifier', 'source_sha256'}
            or state['scope'] != runtime.name or state['owner'] != manage.OWNER
            or state['container'] != runtime.name + '-db' or state['volume'] != runtime.name + '-data'
            or state['marker'] != MARKER or not re.fullmatch('[0-9]+', state['system_identifier'])
            or not re.fullmatch('[0-9a-f]{64}', state['source_sha256'])):
        raise RuntimeError('provider_rehearsal_owner_invalid')
    return state


def private_json(runtime, name):
    path = runtime / name
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise RuntimeError('provider_rehearsal_owner_untrusted')
    if path.stat().st_size > 65536:
        raise RuntimeError('provider_rehearsal_record_oversized')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError('provider_rehearsal_record_invalid')
    return value


def owned_container(state):
    manage.require_staging_host()
    rows = json.loads(manage.docker('inspect', state['container']))
    if len(rows) != 1:
        raise RuntimeError('provider_rehearsal_container_ambiguous')
    row = rows[0]
    labels = row.get('Config', {}).get('Labels', {})
    if (row.get('Name') != '/' + state['container'] or row['Config'].get('Image') != IMAGE
            or labels.get(SCOPE_LABEL) != state['scope']
            or labels.get('com.madar.staging.owner') != manage.OWNER
            or row.get('HostConfig', {}).get('NetworkMode') != 'none'
            or row['HostConfig'].get('RestartPolicy', {}).get('Name') != 'no'
            or not re.fullmatch('[0-9a-f]{64}', row.get('Id', ''))
            or row['HostConfig'].get('PortBindings')):
        raise RuntimeError('provider_rehearsal_container_unowned')
    volumes = [mount for mount in row.get('Mounts', []) if mount.get('Destination') == '/var/lib/postgresql/data']
    if len(volumes) != 1 or volumes[0].get('Name') != state['volume']:
        raise RuntimeError('provider_rehearsal_volume_changed')
    metadata = json.loads(manage.docker('volume', 'inspect', state['volume']))
    if (len(metadata) != 1 or metadata[0].get('Labels', {}).get(SCOPE_LABEL) != state['scope']
            or metadata[0]['Labels'].get('com.madar.staging.owner') != manage.OWNER):
        raise RuntimeError('provider_rehearsal_volume_unowned')
    return row


def raw_sql(state, statement, *, user='postgres'):
    return manage.docker('exec', state['container'], 'psql', '-h', '127.0.0.1', '-U', user,
                         '-d', 'postgres', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-c', statement,
                         timeout=15).decode().strip()


def wait_ready(state):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        owned_container(state)
        try:
            if raw_sql(state, 'SELECT 1;') == '1':
                return
        except RuntimeError:
            pass
        time.sleep(0.5)
    raise RuntimeError('provider_rehearsal_database_unavailable')


def database(state, statement):
    owned_container(state)
    identity = json.loads(raw_sql(state, "SELECT json_build_object('system',system_identifier::text,'marker',"
        "(SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='postgres')) "
        "FROM pg_control_system();"))
    if identity != {'system': state['system_identifier'], 'marker': MARKER}:
        raise RuntimeError('provider_rehearsal_database_identity_changed')
    return raw_sql(state, statement)


def role_state(state):
    return json.loads(database(state, "SELECT json_build_object('login',rolcanlogin,'other_sha256',"
        "encode(sha256(convert_to((to_jsonb(r)-'rolcanlogin')::text,'UTF8')),'hex')) "
        "FROM pg_authid r WHERE rolname='" + ROLE + "';"))


def sessions(state):
    return json.loads(database(state, "SELECT coalesce(json_agg(json_build_object('pid',pid,'role',usename,"
        "'application',application_name,'state',state) ORDER BY pid),'[]'::json) FROM pg_stat_activity "
        "WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid();"))


def deny_new_connection(state):
    owned_container(state)
    try:
        raw_sql(state, "INSERT INTO auth.sessions VALUES(100,'new-writer-must-be-denied');", user=ROLE)
    except RuntimeError:
        # A timeout, unavailable database or SQL permission failure is not proof
        # of login fencing. The postgres positive control must still work.
        if database(state, 'SELECT 1;') != '1':
            raise RuntimeError('provider_rehearsal_denial_positive_control_failed')
        error = (manage.RUNTIME / 'last-command-error.log').read_text()
        if 'is not permitted to log in' not in error or ROLE not in error:
            raise RuntimeError('provider_rehearsal_denial_reason_unverified')
        return
    raise RuntimeError('provider_rehearsal_new_writer_not_fenced')


def crash_after_fence(runtime):
    """Only the labelled synthetic fixture can reach this injected crash."""
    manage.require_staging_host()
    runtime = runtime_path(runtime)
    manage.RUNTIME = runtime
    state = read_state(runtime)
    preimage = private_json(runtime, 'role-preimage.json')
    if role_state(state) != preimage or preimage.get('login') is not True:
        raise RuntimeError('provider_rehearsal_role_preimage_changed')
    database(state, 'ALTER ROLE ' + ROLE + ' NOLOGIN;')
    os._exit(83)


def recover(runtime):
    """Explicit synthetic recovery, never an automatic finally-block un-fence."""
    manage.require_staging_host()
    runtime = runtime_path(runtime)
    previous = manage.RUNTIME
    manage.RUNTIME = runtime
    try:
        state = read_state(runtime)
        preimage = private_json(runtime, 'role-preimage.json')
        snapshot = private_json(runtime, 'fenced-snapshot.json')
        if (set(preimage) != {'login', 'other_sha256'} or preimage['login'] is not True
                or not re.fullmatch('[0-9a-f]{64}', str(preimage['other_sha256']))
                or set(snapshot) != {'scope', 'roots_sha256'} or snapshot['scope'] != state['scope']
                or not re.fullmatch('[0-9a-f]{64}', str(snapshot['roots_sha256']))):
            raise RuntimeError('provider_rehearsal_recovery_preimage_invalid')
        row = owned_container(state)
        if not row.get('State', {}).get('Running'):
            if row.get('State', {}).get('Status') != 'exited' or row['State'].get('OOMKilled'):
                raise RuntimeError('provider_rehearsal_recovery_container_state_invalid')
            manage.docker('start', state['container'])
        wait_ready(state)
        if role_state(state) != dict(preimage, login=False) or sessions(state):
            raise RuntimeError('provider_rehearsal_recovery_not_quiescent')
        if database(state, ROOTS_SQL) != snapshot['roots_sha256']:
            raise RuntimeError('provider_rehearsal_customer_values_changed')
        deny_new_connection(state)
        database(state, 'ALTER ROLE ' + ROLE + ' LOGIN;')
        if role_state(state) != preimage:
            raise RuntimeError('provider_rehearsal_exact_role_restore_failed')
        raw_sql(state, "BEGIN; INSERT INTO auth.sessions VALUES(101,'recovered-writer'); "
                "UPDATE auth.mfa_factors SET value='synthetic-recovery-update' WHERE id=1; "
                "INSERT INTO storage.objects VALUES(101,'recovered-object-metadata'); "
                "INSERT INTO public.business_probe VALUES(101,'recovered-business-write'); ROLLBACK;", user=ROLE)
        if database(state, ROOTS_SQL) != snapshot['roots_sha256']:
            raise RuntimeError('provider_rehearsal_recovery_validation_changed_data')
        result = {'mode': 'RECOVER', 'exact_role_preimage_restored': True,
                  'customer_roots_preserved': True, 'provider_writes_resume': True,
                  'production_modified': False}
        manage.private_write('recovery.json', json.dumps(result, indent=2) + '\n')
        return result
    finally:
        manage.RUNTIME = previous


def writer_line(process, sql):
    process.stdin.write((sql + '\n').encode())
    process.stdin.flush()
    deadline = time.monotonic() + 10
    data = b''
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            if not selector.select(max(0, deadline - time.monotonic())):
                break
            char = os.read(process.stdout.fileno(), 1)
            if not char:
                break
            if char == b'\n':
                return data.decode()
            data += char
            if len(data) > 256:
                break
    raise RuntimeError('provider_rehearsal_idle_writer_unavailable')


def rehearse():
    manage.require_staging_host()
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:')))
    if available < 1024 * 1024 or shutil.disk_usage(Path.home()).free < 1024 ** 3:
        raise RuntimeError('provider_rehearsal_insufficient_headroom')
    scope = PREFIX + secrets.token_hex(6)
    runtime = runtime_path(Path.home() / scope)
    runtime.mkdir(mode=0o700)
    previous = manage.RUNTIME
    manage.RUNTIME = runtime
    labels = ['--label', SCOPE_LABEL + '=' + scope, '--label', 'com.madar.staging.owner=' + manage.OWNER]
    state = {'scope': scope, 'owner': manage.OWNER, 'container': scope + '-db', 'volume': scope + '-data',
             'marker': MARKER, 'system_identifier': '0',
             'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    started = time.monotonic()
    writer = None
    created = False
    successful = False
    try:
        manage.docker('volume', 'create', *labels, state['volume'])
        manage.docker('run', '--rm', '--network=none', '--memory=64m', '--cpus=0.25', '--pids-limit=32',
                      *labels, '--volume', state['volume'] + ':/data', '--entrypoint', 'sh', IMAGE,
                      '-ec', 'chown 70:70 /data')
        manage.docker('run', '--detach', '--name', state['container'], '--network=none', '--restart=no',
                      '--memory=256m', '--cpus=0.5', '--pids-limit=96', '--read-only', '--user=70:70',
                      '--security-opt', 'no-new-privileges:true', '--cap-drop=ALL', *labels,
                      '--log-opt', 'max-size=2m', '--log-opt', 'max-file=2',
                      '--tmpfs', '/tmp:rw,nosuid,nodev,size=16m,uid=70,gid=70',
                      '--tmpfs', '/var/run/postgresql:rw,nosuid,nodev,size=8m,uid=70,gid=70',
                      '--volume', state['volume'] + ':/var/lib/postgresql/data',
                      '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', IMAGE, 'postgres',
                      '-c', 'shared_buffers=32MB', '-c', 'max_connections=12', '-c', 'max_wal_size=64MB')
        created = True
        owned_container(state)
        wait_ready(state)
        raw_sql(state, "COMMENT ON DATABASE postgres IS '" + MARKER + "'; CREATE ROLE " + ROLE + " LOGIN; "
                "CREATE SCHEMA auth; CREATE SCHEMA storage; CREATE TABLE auth.sessions(id int primary key,value text); "
                "CREATE TABLE auth.mfa_factors(id int primary key,value text); "
                "CREATE TABLE storage.objects(id int primary key,value text); "
                "CREATE TABLE public.business_probe(id int primary key,value text); "
                "INSERT INTO auth.sessions VALUES(1,'synthetic-session'); "
                "INSERT INTO auth.mfa_factors VALUES(1,'synthetic-factor-placeholder'); "
                "INSERT INTO storage.objects VALUES(1,'synthetic-object-metadata'); "
                "INSERT INTO public.business_probe VALUES(1,'synthetic-business'); "
                "GRANT USAGE ON SCHEMA auth,storage,public TO " + ROLE + "; "
                "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA auth,storage,public TO " + ROLE + ";")
        state['system_identifier'] = raw_sql(state, 'SELECT system_identifier::text FROM pg_control_system();')
        manage.private_write('owner.json', json.dumps(state, indent=2) + '\n')
        preimage = role_state(state)
        manage.private_write('role-preimage.json', json.dumps(preimage) + '\n')
        original = database(state, ROOTS_SQL)
        writer = subprocess.Popen(manage.DOCKER + ['exec', '--interactive', '--env', 'PGAPPNAME=' + scope + ':idle',
            state['container'], 'psql', '-h', '127.0.0.1', '-U', ROLE, '-d', 'postgres', '-XqAt',
            '-v', 'ON_ERROR_STOP=1'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={'PATH': os.defpath, 'HOME': str(Path.home())}, bufsize=0)
        pid = writer_line(writer, 'SELECT pg_backend_pid();')
        if not pid.isdigit() or writer_line(writer, "BEGIN; INSERT INTO auth.sessions VALUES(99,'uncommitted'); SELECT 'idle';") != 'idle':
            raise RuntimeError('provider_rehearsal_idle_transaction_not_established')
        observed = sessions(state)
        if observed != [{'pid': int(pid), 'role': ROLE, 'application': scope + ':idle', 'state': 'idle in transaction'}]:
            raise RuntimeError('provider_rehearsal_unexpected_session')
        child = subprocess.run([sys.executable, '-c', 'from pathlib import Path; import sys; '
            'from provider_quiescence_rehearsal import crash_after_fence; crash_after_fence(Path(sys.argv[1]))', str(runtime)],
            capture_output=True, timeout=30, env={'PATH': os.defpath, 'HOME': str(Path.home()),
            'PYTHONPATH': str(Path(__file__).resolve().parent)})
        if child.returncode != 83 or role_state(state) != dict(preimage, login=False):
            manage.private_write('crash-child-error.log', child.stderr.decode(errors='replace'))
            raise RuntimeError('provider_rehearsal_crash_checkpoint_failed')
        deny_new_connection(state)
        if writer_line(writer, "INSERT INTO storage.objects VALUES(99,'still-connected'); SELECT 'existing-can-write';") != 'existing-can-write':
            raise RuntimeError('provider_rehearsal_existing_session_control_failed')
        # NOLOGIN alone is insufficient: drain only the positively identified
        # fixture session, including rollback of its uncommitted customer data.
        if sessions(state) != observed:
            raise RuntimeError('provider_rehearsal_session_changed_before_drain')
        if database(state, 'SELECT pg_terminate_backend(' + pid + ');') != 't':
            raise RuntimeError('provider_rehearsal_idle_session_not_drained')
        writer.communicate(timeout=10)
        if sessions(state) or database(state, ROOTS_SQL) != original:
            raise RuntimeError('provider_rehearsal_drain_did_not_rollback')
        manage.private_write('fenced-snapshot.json', json.dumps({'scope': scope, 'roots_sha256': original}) + '\n')
        owned_container(state)
        manage.docker('restart', '--time', '10', state['container'])
        wait_ready(state)
        if role_state(state) != dict(preimage, login=False):
            raise RuntimeError('provider_rehearsal_restart_lost_fence')
        deny_new_connection(state)
        if database(state, ROOTS_SQL) != original:
            raise RuntimeError('provider_rehearsal_restart_changed_customer_state')
        recovery = recover(runtime)
        report = {'scope': 'isolated synthetic PostgreSQL provider-writer fence', 'source_sha256': state['source_sha256'],
                  'login_fence_committed_before_orchestrator_crash': True, 'new_connections_denied': True,
                  'existing_session_survives_login_fence': True, 'identified_idle_transaction_drained': True,
                  'uncommitted_auth_storage_changes_rolled_back': True, 'fence_survives_database_restart': True,
                  **recovery, 'mode': 'REHEARSE', 'elapsed_seconds': round(time.monotonic() - started, 3),
                  'runtime': str(runtime), 'retained_volume': state['volume'], 'production_modified': False,
                  'limitations': ['synthetic tables, not real GoTrue/Storage services',
                    'no protected-controller integration or source admission',
                    'postgres superuser deliberately remains the isolated maintenance channel',
                    'no production login policy, pg_hba policy, writer inventory or supervisor fencing proven',
                    'no full application restore, object bytes, production authorization or RPO/RTO claim']}
        manage.private_write('result.json', json.dumps(report, indent=2) + '\n')
        successful = True
        return report
    finally:
        if writer is not None and writer.poll() is None:
            writer.kill()
            writer.communicate(timeout=10)
        if created:
            owned_container(state)
            # Successful fixture is removed; on failure stop it and preserve
            # its role fence/data for explicit investigation, never un-fence.
            manage.docker(*(['rm', '--force'] if successful else ['stop', '--time', '10']), state['container'])
        manage.RUNTIME = previous


def main(mode='INSPECT', *, runtime=None):
    manage.require_staging_host()
    if mode == 'INSPECT' and runtime is None:
        return {'mode': mode, 'image': IMAGE, 'network': 'none', 'production_modified': False,
                'controller_admission': 'BLOCKED: provider lifecycle is not integrated'}
    if mode == 'REHEARSE' and runtime is None:
        return rehearse()
    if mode == 'RECOVER' and runtime is not None:
        return recover(runtime)
    raise RuntimeError('provider_rehearsal_mode_invalid')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', default='INSPECT', choices=('INSPECT', 'REHEARSE', 'RECOVER'))
    parser.add_argument('--runtime', type=Path)
    args = parser.parse_args()
    print(json.dumps(main(args.mode, runtime=args.runtime), sort_keys=True))
