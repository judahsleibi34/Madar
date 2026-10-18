#!/usr/bin/env python3
"""Fenced actual150 backup and independent full-application staging restoration.

Default INSPECT never changes services or databases. REHEARSE deliberately keeps
the owned source150 writers paused while the new target runs; RESUME-SOURCE is
an explicit, separately invoked staging recovery and stops the target first.
No production paths, migrations, operator authority, off-host or PITR support.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request

import manage
import restore
import smoke
import independent_recovery as recovery
import schema150_acceptance as acceptance
import schema149_provider_rehearsal as providers
import schema150_restore_configuration as configuration

PROJECT = 'madar-schema150-recovery-phase6-20261018'
OWNER = 'schema150-recovery-phase6-20261018'
MARKER = 'madar-schema150-recovery-phase6-synthetic'
SOURCE = 'madar-schema150-phase6-20261018'
SOURCE_OWNER = 'schema150-phase6-20261018'
PORTS = {'21080': '22080', '21443': '22443', '21081': '22081'}
SCOPE = 'full-application-restore150'
ROLE_NAMES = providers.ROLE_NAMES
INGRESS = providers.INGRESS
WRITERS = providers.BUSINESS + providers.PROVIDERS
SERVICES = set(acceptance.SERVICES)


def replace_ports(value):
    for before, after in PORTS.items(): value = value.replace(':' + before, ':' + after)
    return value


@contextmanager
def target(runtime):
    names = ('PROJECT', 'OWNER', 'MARKER', 'PORTS')
    old = tuple(getattr(acceptance, name) for name in names)
    old_compose = manage.compose
    acceptance.PROJECT, acceptance.OWNER, acceptance.MARKER = PROJECT, OWNER, MARKER
    acceptance.PORTS = {'18080': '22080', '18443': '22443', '18081': '22081'}
    try:
        with acceptance.target(runtime):
            smoke.PROVIDER, smoke.APPLICATION = 'http://127.0.0.1:22081', 'http://127.0.0.1:22080/api'
            manage.compose = lambda *args, timeout=180: configuration.invoke(runtime, args, PROJECT, OWNER, timeout=timeout)
            yield
    finally:
        manage.compose = old_compose
        for name, value in zip(names, old): setattr(acceptance, name, value)


@contextmanager
def source():
    old = providers.PROJECT, providers.OWNER
    old_database_container = manage.database_container
    providers.PROJECT, providers.OWNER = SOURCE, SOURCE_OWNER
    try:
        with acceptance.target(Path.home() / SOURCE):
            # Identify the running DB through attested Docker labels rather
            # than reading editable origin Compose files, even for `ps`.
            manage.database_container = lambda: rows()['postgres']['Id']
            yield
    finally:
        manage.database_container = old_database_container
        providers.PROJECT, providers.OWNER = old


def durable(path, data):
    restore.write_binary(path, data)
    with path.open('rb') as handle: os.fsync(handle.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def rows():
    values = providers.containers()
    if set(values) != SERVICES:
        raise RuntimeError('restore150_unknown_or_missing_source_actor')
    return values


def require_source(source_sha, images):
    state = manage.state(); manage.attest_resources(); manage.require_database_marker()
    if state['source_sha'] != source_sha or manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2':
        raise RuntimeError('restore150_exact_source_schema_required')
    report = providers.private(manage.RUNTIME / 'schema150-acceptance.json')
    if report.get('source_sha') != source_sha or report.get('images') != images or report.get('schema') != 150:
        raise RuntimeError('restore150_source_acceptance_not_exact')
    for role in ('backend', 'frontend'):
        image = json.loads(manage.docker('image', 'inspect', images[role]))[0]
        labels = image['Config'].get('Labels', {})
        if (image['Id'] != images[role] or labels.get('com.madar.release.sha') != source_sha
                or labels.get('org.opencontainers.image.revision') != source_sha
                or labels.get('com.madar.build.mode') != 'fresh-locked-ci'):
            raise RuntimeError('restore150_origin_artifact_image_identity_changed')
    for name, row in rows().items():
        if name in ('backend', 'notification-worker', 'deletion-worker', 'accepted-frontend'):
            if row['Image'] != images['frontend' if name == 'accepted-frontend' else 'backend']:
                raise RuntimeError('restore150_source_image_changed')
            if any(m.get('Destination', '').startswith('/app') for m in row.get('Mounts', [])):
                raise RuntimeError('restore150_source_overlay_forbidden')
    return report


def positive_probes():
    fixture = providers.private(manage.RUNTIME / 'smoke-fixture.json')
    proof = recovery.original_identity_acceptance(fixture)
    token = acceptance.service_values()['SUPABASE_SERVICE_KEY']
    value = acceptance.rpc('data_deletion_ownership_protocol', {}, token)
    if type(value) is not int or value != 2:
        raise RuntimeError('restore150_positive_postgrest_protocol_failed')
    return proof


def capture_preimage(source_sha, images):
    actual = rows()
    known = providers.sessions()
    addresses = {network['IPAddress'] for row in actual.values()
                 for network in row['NetworkSettings']['Networks'].values()}
    if any(session['role'] not in ROLE_NAMES or session['client'] not in addresses for session in known):
        raise RuntimeError('restore150_unknown_database_client')
    if manage.sql("select count(*) from pg_roles where rolcanlogin and rolname not in ('postgres','authenticator','supabase_auth_admin','supabase_storage_admin');") != '0':
        raise RuntimeError('restore150_unknown_login_role')
    if manage.sql('select count(*) from pg_prepared_xacts where database=current_database();') != '0':
        raise RuntimeError('restore150_prepared_transactions_present')
    return {'source_sha': source_sha, 'images': images,
            'system_identifier': manage.sql('select system_identifier::text from pg_control_system();'),
            'roles': providers.roles(), 'all_roles_sha256': manage.sql(recovery.ROLE_FINGERPRINT),
            'runtime_credentials_sha256': hashlib.sha256(json.dumps(configuration.live_credentials(actual), sort_keys=True).encode()).hexdigest(),
            'sessions': known, 'containers': {name: {'id': row['Id'], 'image': row['Image'],
                'running': row['State']['Running'], 'restart': row['HostConfig']['RestartPolicy']['Name']}
                for name, row in actual.items()}}


def require_preimage_identity(preimage):
    actual = rows()
    if manage.sql('select system_identifier::text from pg_control_system();') != preimage['system_identifier']:
        raise RuntimeError('restore150_source_cluster_changed')
    for name, original in preimage['containers'].items():
        row = actual[name]
        if row['Id'] != original['id'] or row['Image'] != original['image'] or row['HostConfig']['RestartPolicy']['Name'] != original['restart']:
            raise RuntimeError('restore150_source_actor_changed')


def fence(preimage, journal):
    """Fixed staging actors only; intent is fsynced before each side effect."""
    for stage, names in (('ingress', INGRESS), ('writers_and_providers', WRITERS)):
        require_preimage_identity(preimage)
        journal.append('effect_intent', {'stage': stage})
        for name in names:
            row = rows()[name]
            if row['State']['Running']: manage.docker('stop', '--time', '15', row['Id'])
        if any(rows()[name]['State']['Running'] or rows()[name]['State'].get('Restarting') for name in names):
            raise RuntimeError('restore150_writer_failed_to_stop')
        journal.append('effect_complete', {'stage': stage})
    journal.append('effect_intent', {'stage': 'provider_roles'})
    if providers.roles() != preimage['roles']:
        raise RuntimeError('restore150_original_role_state_changed')
    manage.sql(';'.join('alter role "' + name + '" nologin' for name in ROLE_NAMES) + ';')
    journal.append('effect_complete', {'stage': 'provider_roles'})
    journal.append('effect_intent', {'stage': 'known_session_drain'})
    known = {row['pid']: row for row in preimage['sessions']}
    current = providers.sessions()
    if any(known.get(row['pid']) != row for row in current):
        raise RuntimeError('restore150_unknown_session_refuse_termination')
    for row in current:
        query = ('select pg_terminate_backend(pid) from pg_stat_activity where pid=' + str(row['pid']) +
                 ' and backend_start::text=' + smoke.literal(row['start']) + ' and usename=' + smoke.literal(row['role']) +
                 ' and application_name=' + smoke.literal(row['application']) + ';')
        if manage.sql(query) not in ('t', ''): raise RuntimeError('restore150_session_drain_failed')
    require_quiescence(preimage)
    journal.append('effect_complete', {'stage': 'known_session_drain'})


def require_quiescence(preimage):
    require_preimage_identity(preimage)
    if manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2':
        raise RuntimeError('restore150_source_schema_changed')
    if providers.sessions() or manage.sql('select count(*) from pg_prepared_xacts where database=current_database();') != '0':
        raise RuntimeError('restore150_sessions_or_prepared_transactions_remain')
    actual = rows()
    if any(actual[name]['State']['Running'] or actual[name]['State'].get('Restarting') for name in INGRESS + WRITERS):
        raise RuntimeError('restore150_source_writer_resurrected')
    require_ingress_fenced()
    expected = {name: {**value, 'login': False} for name, value in preimage['roles'].items()}
    if providers.roles() != expected: raise RuntimeError('restore150_provider_login_fence_changed')
    pending = manage.sql("select (select count(*) from public.notification_deliveries where status='processing')+"
        "(select count(*) from public.notification_outbox where status='processing')+"
        "(select count(*) from public.data_deletion_requests where state='in_progress')+"
        "(select count(*) from public.data_deletion_steps where state='processing');")
    if pending != '0': raise RuntimeError('restore150_processing_work_requires_reconciliation')
    if manage.sql("select count(*) from pg_locks where pid<>pg_backend_pid() and relation=any(array["
                  "'public.notification_deliveries'::regclass,'public.notification_outbox'::regclass,"
                  "'public.data_deletion_requests'::regclass,'public.data_deletion_steps'::regclass]);") != '0':
        raise RuntimeError('restore150_queue_locks_remain')
    running = manage.docker('ps', '-q', '--no-trunc').decode().split()
    objects = json.loads(manage.docker('inspect', *running)) if running else []
    volume = json.loads(manage.docker('volume', 'inspect', SOURCE + '_objects'))[0]
    if (volume.get('Labels') or {}).get('com.madar.staging.owner') != SOURCE_OWNER:
        raise RuntimeError('restore150_object_volume_owner_changed')
    if has_object_writer(objects, SOURCE + '_objects', volume['Mountpoint']):
        raise RuntimeError('restore150_unexpected_object_writer')


def require_ingress_fenced():
    for url in ('http://127.0.0.1:21080/api/health/live', 'http://127.0.0.1:21081/auth/v1/health'):
        try:
            with smoke.OPENER.open(Request(url), timeout=2):
                raise RuntimeError('restore150_source_ingress_still_reachable')
        except HTTPError:
            # Even a denial/redirect/error proves an unexpected responder still
            # owns the supposedly stopped source ingress. Never follow it.
            raise RuntimeError('restore150_source_ingress_still_reachable') from None
        except URLError:
            pass


def has_object_writer(containers, name, mountpoint):
    if not isinstance(mountpoint, str) or not mountpoint.startswith('/'):
        raise RuntimeError('restore150_object_volume_path_invalid')
    def overlap(value):
        if not isinstance(value, str) or not value.startswith('/'): return False
        source, target_path = PurePosixPath(value).parts, PurePosixPath(mountpoint).parts
        return source[:len(target_path)] == target_path or target_path[:len(source)] == source
    return any(m.get('RW') and (m.get('Name') == name or overlap(m.get('Source')))
               for row in containers for m in row.get('Mounts', []))


def capture(files, preimage):
    require_quiescence(preimage)
    before = json.loads(manage.sql(restore.FINGERPRINT_SQL))
    privilege = manage.sql(recovery.PRIVILEGE_FINGERPRINT)
    objects = restore.inventory(SOURCE + '_objects')
    dump = manage.docker('exec', manage.database_container(), 'pg_dump', '-U', 'postgres', '-Fc', 'madar_hardening')
    archive = restore.helper(SOURCE + '_objects', "import sys,tarfile;t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|');t.add('/objects',arcname='.');t.close()")
    acceptance.previous.archive_members(archive)
    require_quiescence(preimage)
    if before != json.loads(manage.sql(restore.FINGERPRINT_SQL)) or objects != restore.inventory(SOURCE + '_objects'):
        raise RuntimeError('restore150_source_changed_while_fenced')
    for name, data in (('database.dump', dump), ('objects.tar', archive)): durable(files / name, data)
    checkpoint = {'source_sha': preimage['source_sha'], 'images': preimage['images'],
                  'rows_sequences': before, 'objects': objects, 'roles_sha256': preimage['all_roles_sha256'],
                  'privileges_sha256': privilege, 'source_system_identifier': preimage['system_identifier'],
                  'archive_sha256': {name: hashlib.sha256(acceptance.previous.regular(files / name)).hexdigest()
                                     for name in ('database.dump', 'roles.sql', 'objects.tar')}}
    durable(files / 'checkpoint.json', json.dumps(checkpoint, sort_keys=True).encode())
    return checkpoint


def prepare_target(runtime, source_runtime, source_sha, images, receipt=None, origin_images=None, credentials=None):
    if runtime.exists() or runtime.is_symlink(): raise RuntimeError('restore150_target_attempt_already_consumed')
    if receipt is None or origin_images is None or credentials is None:
        raise RuntimeError('restore150_target_artifact_preimage_required')
    with target(runtime):
        # source_runtime is an identity/context only: no origin compose, env,
        # TLS or gateway configuration is copied into the future target.
        if source_runtime != Path.home() / SOURCE:
            raise RuntimeError('restore150_origin_runtime_identity_invalid')
        configuration.generate(runtime, source_sha, images, receipt, credentials, PROJECT, OWNER)
        manage.state(); manage.attest_resources()


def import_target_images(runtime, directory, artifact, receipt, images, source_sha):
    with target(runtime):
        root = runtime / 'authenticated-images'; root.mkdir(mode=0o700)
        with acceptance.authenticated_archive(directory / 'candidate.zip', artifact['digest']) as archive:
            for role in ('backend', 'frontend'):
                acceptance.import_authenticated_image(archive, role, receipt['archives'][role], root / (role + '.tar.gz'))
                image = json.loads(manage.docker('image', 'inspect', images[role]))[0]
                labels = image['Config'].get('Labels', {})
                if (image['Id'] != images[role] or labels.get('com.madar.release.sha') != source_sha
                        or labels.get('org.opencontainers.image.revision') != source_sha
                        or labels.get('com.madar.build.mode') != 'fresh-locked-ci'):
                    raise RuntimeError('restore150_target_fresh_artifact_identity_changed')


def restore_target(runtime, files, checkpoint, images, source_sha):
    # Archives remain immutable private files; verify captured bytes once and
    # carry those authenticated bytes through the actual restore calls.
    captured = {name: acceptance.previous.regular(files / name) for name in ('roles.sql', 'database.dump', 'objects.tar')}
    if any(hashlib.sha256(data).hexdigest() != checkpoint['archive_sha256'][name] for name, data in captured.items()):
        raise RuntimeError('restore150_archive_digest_changed')
    acceptance.previous.archive_members(captured['objects.tar'])
    with target(runtime):
        manage.compose('up', '--detach', '--wait', '--wait-timeout', '90', 'postgres')
        if manage.sql('select system_identifier::text from pg_control_system();') == checkpoint['source_system_identifier']:
            raise RuntimeError('restore150_target_is_source_cluster')
        if manage.sql("select count(*) from pg_roles where rolname in ('authenticator','supabase_auth_admin','supabase_storage_admin');") != '0':
            raise RuntimeError('restore150_target_inherited_roles')
        ddl = '\n'.join(line for line in captured['roles.sql'].decode().splitlines() if line.strip() != 'CREATE ROLE postgres;') + '\n'
        manage.sql(ddl, database='postgres')
        if manage.sql(recovery.ROLE_FINGERPRINT) != checkpoint['roles_sha256']:
            raise RuntimeError('restore150_original_role_preimage_not_restored')
        manage.docker('exec', '-i', manage.database_container(), 'pg_restore', '-U', 'postgres', '--exit-on-error',
                      '--single-transaction', '-d', 'madar_hardening', data=captured['database.dump'])
        manage.sql("comment on database madar_hardening is '" + MARKER + "';")
        manage.require_database_marker()
        if json.loads(manage.sql(restore.FINGERPRINT_SQL)) != checkpoint['rows_sequences']:
            raise RuntimeError('restore150_pre_activation_rows_sequences_changed')
        if manage.sql(recovery.PRIVILEGE_FINGERPRINT) != checkpoint['privileges_sha256']:
            raise RuntimeError('restore150_pre_activation_owners_grants_rls_definers_changed')
        if manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2': raise RuntimeError('restore150_restored_protocols_invalid')
        if manage.sql("select has_table_privilege('service_role','public.data_deletion_requests','UPDATE') or has_table_privilege('service_role','public.data_deletion_steps','UPDATE');") != 'f':
            raise RuntimeError('restore150_unsafe_direct_deletion_grants_restored')
        manage.compose('create', 'storage')
        restore.helper(PROJECT + '_objects', "import sys,tarfile;t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|');t.extractall('/objects',filter='data')", writable=True, data=captured['objects.tar'])
        if restore.inventory(PROJECT + '_objects') != checkpoint['objects']:
            raise RuntimeError('restore150_pre_activation_object_bytes_changed')
        manage.private_write('pre-activation-preservation.json', json.dumps({'rows_sequences': True, 'roles': True,
            'grants_owners_rls_definers': True, 'objects': True, 'schema': 150, 'independent_cluster': True}) + '\n')
        args = ('--file', str(runtime / 'acceptance-compose.json'))
        manage.compose(*args, 'up', '--detach', '--wait', '--wait-timeout', '180', *acceptance.SERVICES)
        manage.attest_resources(); manage.require_database_marker()
        source_fixture = providers.private(Path.home() / SOURCE / 'smoke-fixture.json')
        original = recovery.original_identity_acceptance(source_fixture)
        smoke.main()
        acceptance.worker_health()
        deletion = acceptance.deletion_workflow()
        code = acceptance.runtime_identity(images, source_sha)
        return {'pre_activation_rows_sequences': True, 'original_roles_passwords_memberships': True,
                'owners_grants_rls_definers': True, 'object_bytes': True,
                'original_auth_mfa_private_storage': original, 'native_new_auth_mfa_storage_notifications': True,
                'actual_restored_deletion_worker': deletion, 'runtime_code_sha256': code}


def verify_retained_source(preimage, checkpoint):
    """Observe the original source again after every target acceptance effect."""
    with source():
        require_quiescence(preimage)
        if (json.loads(manage.sql(restore.FINGERPRINT_SQL)) != checkpoint['rows_sequences']
                or restore.inventory(SOURCE + '_objects') != checkpoint['objects']):
            raise RuntimeError('restore150_source_changed_during_target_acceptance')
    return {'quiescence_reverified_after_target_acceptance': True,
            'original_rows_sequences_objects_preserved_after_target_acceptance': True}


def resume_source(source_sha, images):
    """Explicitly restore only the recorded original staging preimages."""
    runtime = Path.home() / SOURCE
    with source():
        require_source(source_sha, images)
        journal = providers.Journal(runtime / (SCOPE + '-journal'))
        records = journal.read()
        if not records or records[0]['event'] != 'prepared': raise RuntimeError('restore150_original_preimage_missing')
        if any(row['event'] == 'source_resumed' for row in records): raise RuntimeError('restore150_source_resume_already_consumed')
        preimage = records[0]['payload']['preimage']
        require_preimage_identity(preimage)
        if preimage['source_sha'] != source_sha or preimage['images'] != images:
            raise RuntimeError('restore150_resume_source_changed')
        current_roles = providers.roles()
        if set(current_roles) != set(preimage['roles']) or any(current_roles[name]['other_sha256'] != value['other_sha256'] for name, value in preimage['roles'].items()):
            raise RuntimeError('restore150_nonlogin_role_preimage_changed')
        files = runtime / (SCOPE + '-files')
        checkpoint_path = files / 'checkpoint.json'
        previous_resume = [row for row in records if row['event'] == 'source_resume_intent']
        verified = checkpoint_path.exists() and not previous_resume
        if verified:
            checkpoint = providers.private(checkpoint_path)
            require_quiescence(preimage)
            if json.loads(manage.sql(restore.FINGERPRINT_SQL)) != checkpoint['rows_sequences'] or restore.inventory(SOURCE + '_objects') != checkpoint['objects']:
                raise RuntimeError('restore150_source_changed_before_explicit_resume')
        elif previous_resume:
            # The prior invocation may already have restored some LOGIN flags
            # and restarted providers before its response was lost. Do not
            # pretend their legitimate subsequent writes can be rolled back.
            # Reconcile only the same recorded source identities/preimages.
            addresses = {network['IPAddress'] for row in rows().values()
                         for network in row['NetworkSettings']['Networks'].values()}
            if any(row['role'] not in ROLE_NAMES or row['client'] not in addresses for row in providers.sessions()):
                raise RuntimeError('restore150_unknown_client_during_resume_reentry')
        # Resource bounds: pause the positively owned recovery target before
        # restarting source providers. All target volumes/evidence are retained.
        target_runtime = Path.home() / PROJECT
        if target_runtime.exists():
            with target(target_runtime):
                manage.state(); manage.attest_resources()
                manage.compose('--file', str(target_runtime / 'acceptance-compose.json'), 'stop', '--timeout', '15')
        journal.append('source_resume_intent', {'preservation_checkpoint_verified': verified,
                                              'reconciles_interrupted_resume': bool(previous_resume)})
        manage.sql(';'.join('alter role "' + name + '" ' + ('login' if value['login'] else 'nologin') for name, value in preimage['roles'].items()) + ';')
        if manage.sql(recovery.ROLE_FINGERPRINT) != preimage['all_roles_sha256']:
            raise RuntimeError('restore150_original_roles_not_restored')
        running = [value['id'] for value in preimage['containers'].values() if value['running']]
        if running: manage.docker('start', *running)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                current = rows()
                if any(not current[name]['State']['Running'] or
                       current[name]['State'].get('Health', {}).get('Status', 'healthy') != 'healthy'
                       for name, original in preimage['containers'].items() if original['running']):
                    time.sleep(1); continue
                acceptance.worker_health(); break
            except RuntimeError: time.sleep(1)
        else: raise RuntimeError('restore150_source_provider_resumption_failed')
        positive_probes()
        journal.append('source_resumed', {'original_roles_services_restored': True, 'target_stopped': target_runtime.exists()})
        return {'mode': 'RESUME-SOURCE', 'schema': 150, 'original_roles_and_services_restored': True,
                'target_stopped_preserved': target_runtime.exists(), 'preservation_checkpoint_verified': verified,
                'interrupted_resume_reconciled': bool(previous_resume),
                'production_modified': False, 'production_authorized': False}


def main(mode, directory, source_sha, origin_directory=None, origin_sha=None):
    if mode not in ('INSPECT', 'REHEARSE', 'RESUME-SOURCE') or not re.fullmatch('[0-9a-f]{40}', source_sha or ''):
        raise RuntimeError('restore150_explicit_mode_and_source_required')
    if ((origin_directory is None) != (origin_sha is None)
            or (origin_sha is not None and not re.fullmatch('[0-9a-f]{40}', origin_sha))):
        raise RuntimeError('restore150_paired_exact_origin_identity_required')
    origin_directory, origin_sha = origin_directory or directory, origin_sha or source_sha
    manage.require_staging_host()
    with source():
        artifact, run, images, receipt = acceptance.previous.artifacts(directory, source_sha)
        _, origin_run, origin_images, _ = acceptance.previous.artifacts(origin_directory, origin_sha)
        require_source(origin_sha, origin_images)
        root = manage.RUNTIME / (SCOPE + '-journal'); files = manage.RUNTIME / (SCOPE + '-files')
        runtime = Path.home() / PROJECT
        if mode == 'INSPECT':
            return {'mode': mode, 'source_project': SOURCE, 'target_project': PROJECT, 'schema': 150,
                    'source_sha': source_sha, 'origin_source_sha': origin_sha, 'origin_images': origin_images,
                    'target_images': images, 'ports': PORTS, 'existing_attempt_preserved': root.exists() or runtime.exists(),
                    'mutations_executed': False, 'production_modified': False}
        if mode == 'RESUME-SOURCE': return resume_source(origin_sha, origin_images)
        if any(path.exists() or path.is_symlink() for path in (root, files, runtime)):
            raise RuntimeError('restore150_attempt_already_consumed')
        if shutil.disk_usage(Path.home()).free < 8 * 1024**3:
            raise RuntimeError('restore150_disk_headroom_insufficient')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
        if available < 1300 * 1024: raise RuntimeError('restore150_memory_headroom_insufficient')
        positive_probes()
        preimage = capture_preimage(origin_sha, origin_images)
        credentials = configuration.live_credentials(rows())
        if hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).hexdigest() != preimage['runtime_credentials_sha256']:
            raise RuntimeError('restore150_live_credential_preimage_changed')
        root.mkdir(mode=0o700); files.mkdir(mode=0o700)
        journal = providers.Journal(root)
        journal.append('prepared', {'preimage': preimage, 'synthetic_scope': SCOPE})
        # Original role DDL is fsynced BEFORE any NOLOGIN mutation, and stays out
        # of the strict journal directory. Never restore a fenced-role default.
        roles = manage.docker('exec', manage.database_container(), 'pg_dumpall', '-U', 'postgres', '--roles-only')
        durable(files / 'roles.sql', roles)
        if manage.sql(recovery.ROLE_FINGERPRINT) != preimage['all_roles_sha256']:
            raise RuntimeError('restore150_role_state_changed_before_fence')
        started = time.monotonic()
        fence(preimage, journal)
        checkpoint = capture(files, preimage)
        journal.append('backup_captured', {'archive_sha256': checkpoint['archive_sha256']})
        prepare_target(runtime, Path.home() / SOURCE, source_sha, images, receipt, origin_images, credentials)
    try:
        import_target_images(runtime, directory, artifact, receipt, images, source_sha)
        accepted = restore_target(runtime, files, checkpoint, images, source_sha)
        retained_source = verify_retained_source(preimage, checkpoint)
        report = {'scope': 'actual150 fenced backup and independent fresh-cluster full native application restoration',
                  'source_sha': source_sha, 'images': images, 'run_id': run['id'], 'schema': 150,
                  'origin_source_sha': origin_sha, 'origin_images': origin_images, 'origin_run_id': origin_run['id'],
                  'protocols': [2, 2, 2], 'fresh_exact_source_images': True, 'source_overlay_used': False,
                  'original_roles_captured_before_fence': True, 'independent_postgresql_cluster': True,
                  'accepted': accepted, 'source_writers_retained_paused': True, 'source_database_retained_running': True,
                  'retained_source_final_observation': retained_source,
                  'source_resume_requires_explicit_mode': 'RESUME-SOURCE',
                  'archive_sha256': checkpoint['archive_sha256'], 'elapsed_seconds': round(time.monotonic() - started, 3),
                  'production_modified': False, 'production_authorized': False,
                  'limitations': ['same VM, not off-host or full application PITR', 'not protected production controller or real host reboot',
                    'source writers deliberately paused to bound memory until explicit RESUME-SOURCE',
                    'no automatic recovery or restoration of customer databases',
                    'external integration revocation and host-file deletion not exercised by restored happy-path probes',
                    'writer exclusion checks Docker volume/bind overlap, not arbitrary privileged/socket/host-root actors']}
        with target(runtime): manage.private_write('full-application-restore150.json', json.dumps(report, indent=2) + '\n')
        return report
    except BaseException:
        # Never restore source write authority implicitly on an unknown target
        # acceptance outcome. Preserve source barrier and every target volume.
        if runtime.exists():
            with target(runtime):
                manage.state(); manage.attest_resources()
                manage.compose('--file', str(runtime / 'acceptance-compose.json'), 'stop', '--timeout', '15')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=('INSPECT', 'REHEARSE', 'RESUME-SOURCE'), default='INSPECT')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--origin-artifacts', type=Path, help='Separately authenticated existing150 source artifacts; requires --origin-source-sha')
    parser.add_argument('--origin-source-sha', help='Exact accepted existing150 source commit; requires --origin-artifacts')
    args = parser.parse_args()
    print(json.dumps(main(args.mode, args.artifacts, args.source_sha, args.origin_artifacts, args.origin_source_sha), sort_keys=True))
