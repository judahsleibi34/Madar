#!/usr/bin/env python3
"""Owned native149 provider fence proof; no production authorization or adapter.

Only the new schema149_phase5 acceptance project is eligible. REHEARSE stops its
writers and intentionally kills six short-lived orchestration children after
their durable effect intents. RECOVER is explicit, verifies149/2/2 and restores
that synthetic project's exact preimages. It cannot target retained projects.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler, Request

import manage
import restore
import smoke
import independent_recovery as recovery
import schema149_acceptance as acceptance
from provider_quiescence_rehearsal import writer_line

sys.path.insert(0, str(manage.REPOSITORY / 'web'))
from deployment.lib.schema149_provider_lifecycle import (ProviderMaintenance, FENCE_STEPS,
    COUNTERS, FENCES, ACTIVATION_GATES, digest, encoded)

PROJECT = 'madar-schema149-phase5-20261017'
OWNER = 'schema149-phase5-20261017'
ROLE_NAMES = ('authenticator', 'supabase_auth_admin', 'supabase_storage_admin')
SERVICES = {'postgres', 'redis', 'auth', 'rest', 'storage', 'gateway', 'backend',
            'notification-worker', 'deletion-worker', 'frontend', 'accepted-frontend'}
INGRESS = ('frontend', 'accepted-frontend', 'gateway')
BUSINESS = ('notification-worker', 'deletion-worker', 'backend')
PROVIDERS = ('storage', 'auth', 'rest')
OPENER = build_opener(ProxyHandler({}))


def private(path):
    if (path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid()
            or path.stat().st_mode & 0o077 or path.stat().st_size > 2 * 1024 * 1024):
        raise RuntimeError('provider149_private_evidence_untrusted')
    return json.loads(path.read_bytes())


class Journal:
    """Same fsynced append/hash-chain format, staging-user ownership only.

    Deliberately does not weaken the root-owned production journal policy.
    """
    def __init__(self, root):
        self.root = root
        if (root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid()
                or root.stat().st_mode & 0o077):
            raise RuntimeError('provider149_private_journal_untrusted')

    def read(self):
        records = []
        for index, path in enumerate(sorted(self.root.iterdir())):
            if index >= 256 or path.name != f'{index:04d}.json':
                raise RuntimeError('provider149_private_journal_sequence')
            record = private(path)
            if (set(record) != {'sequence', 'previous_sha256', 'event', 'payload'}
                    or record['sequence'] != index
                    or record['previous_sha256'] != (digest(records[-1]) if records else None)):
                raise RuntimeError('provider149_private_journal_chain')
            records.append(record)
        return records

    def append(self, event, payload):
        records = self.read()
        value = {'sequence': len(records), 'previous_sha256': digest(records[-1]) if records else None,
                 'event': event, 'payload': payload}
        path = self.root / f'{len(records):04d}.json'
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(encoded(value)); handle.flush(); os.fsync(handle.fileno())
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)


def sql(value):
    manage.require_database_marker()
    return manage.sql("set statement_timeout='10s';" + value)


def roles():
    return json.loads(sql("select json_object_agg(rolname,json_build_object('login',rolcanlogin,'other_sha256',"
        "encode(sha256(convert_to((to_jsonb(r)-'rolcanlogin'-'oid')::text,'UTF8')),'hex'))) "
        "from pg_authid r where rolname in ('authenticator','supabase_auth_admin','supabase_storage_admin');"))


def sessions():
    return json.loads(sql("select coalesce(json_agg(json_build_object('pid',pid,'start',backend_start::text,"
        "'role',usename,'application',application_name,'client',host(client_addr)) order by pid),'[]'::json) "
        "from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid() "
        "and backend_type='client backend';"))


def containers():
    manage.attest_resources()
    identifiers = manage.docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT).decode().split()
    rows = json.loads(manage.docker('inspect', *identifiers)) if identifiers else []
    result = {row['Config']['Labels']['com.docker.compose.service']: row for row in rows}
    if set(result) != SERVICES or len(rows) != len(SERVICES):
        raise RuntimeError('provider149_unknown_or_missing_actor')
    if any(row['HostConfig']['RestartPolicy']['Name'] != 'no' for row in rows):
        raise RuntimeError('provider149_uncontrolled_restart_policy')
    return result


def public_fenced():
    for url in ('http://127.0.0.1:20080/api/health/live', 'http://127.0.0.1:20081/auth/v1/health'):
        try:
            with OPENER.open(Request(url), timeout=2):
                return False
        except URLError:
            pass
    return True


class StagingActor:
    def __init__(self, runtime, journal):
        self.runtime, self.journal = runtime, journal
        self.report = private(runtime / 'schema149-acceptance.json')
        self.rows = containers()
        self.inventory = {name: {'id': row['Id'], 'image': row['Image']} for name, row in self.rows.items()}
        self.system = sql('select system_identifier::text from pg_control_system();')
        self.binding = {'operation': 'completed-normal-schema146-149-coordinated-release',
            'context_sha256': digest({'project': PROJECT, 'source_sha': self.report['source_sha']}),
            'source_sha': self.report['source_sha'], 'controller_sha': self.report['source_sha'],
            'inventory_sha256': digest(self.inventory), 'system_identifier': self.system,
            'source_schema': 146, 'target_schema': 149}

    def require_authority(self, binding, *, purpose):
        # Synthetic ownership permission only. This never consumes, creates or
        # substitutes a protected production operator credential.
        manage.require_staging_host(); manage.state(); manage.require_database_marker()
        if manage.PROJECT != PROJECT or manage.OWNER != OWNER or binding != self.binding:
            raise RuntimeError('provider149_synthetic_binding_changed')
        current = {name: {'id': row['Id'], 'image': row['Image']} for name, row in containers().items()}
        if current != self.inventory or sql('select system_identifier::text from pg_control_system();') != self.system:
            raise RuntimeError('provider149_native_identity_changed')

    def positive_identity_probes(self, binding):
        values = dict(line.split('=', 1) for line in (self.runtime / 'application.env').read_text().splitlines() if '=' in line)
        fixture = private(self.runtime / 'smoke-fixture.json')
        session, _ = smoke.http('POST', '/auth/v1/token?grant_type=password',
            body={'email': fixture['admin_email'], 'password': fixture['admin_password']})
        if session.get('user', {}).get('id') != fixture['admin_auth_id']:
            raise RuntimeError('provider149_positive_auth_identity_failed')
        protocol, _ = smoke.http('POST', '/rest/v1/rpc/notification_outbox_protocol',
            token=values['SUPABASE_SERVICE_KEY'], body={})
        if protocol != 2: raise RuntimeError('provider149_positive_postgrest_failed')
        smoke.http('POST', '/rest/v1/rpc/notification_outbox_protocol',
            token=values['SUPABASE_ANON_KEY'], body={}, expected=(401, 403))
        data, _ = smoke.http('GET', f"/storage/v1/object/{fixture['private_bucket']}/fixture.txt",
            token=values['SUPABASE_SERVICE_KEY'])
        if data != b'synthetic private storage fixture':
            raise RuntimeError('provider149_positive_storage_failed')
        smoke.http('GET', f"/storage/v1/object/{fixture['private_bucket']}/fixture.txt",
            token=values['SUPABASE_ANON_KEY'], expected=(400, 403, 404))
        if sql("select schema_version from application_schema_state where contract_key='core';") != '149':
            raise RuntimeError('provider149_positive_schema_failed')
        return {'binding_sha256': digest(binding), 'postgrest': True, 'auth_scope': True,
                'storage_scope': True, 'database_scope': True}

    def capture_preimage(self, binding):
        rows = containers()
        identities = {name: {'id': row['Id'], 'image': row['Image'],
            'running': row['State']['Running'], 'restart': row['HostConfig']['RestartPolicy']['Name']}
            for name, row in rows.items()}
        known = sessions()
        addresses = {network['IPAddress'] for row in rows.values() for network in row['NetworkSettings']['Networks'].values()}
        if any(row['role'] not in ROLE_NAMES or
               (row['client'] not in addresses and not (row['application'] == PROJECT + ':lease-probe' and row['client'] == '127.0.0.1'))
               for row in known):
            raise RuntimeError('provider149_unknown_database_writer')
        unexpected = sql("select coalesce(string_agg(rolname,','),'') from pg_roles where rolcanlogin "
            "and rolname not in ('postgres','authenticator','supabase_auth_admin','supabase_storage_admin');")
        if unexpected: raise RuntimeError('provider149_unknown_login_role')
        return {'ingress': {name: identities[name] for name in INGRESS},
            'supervisors': {'containers': {name: value for name, value in identities.items() if name not in INGRESS},
                            'known_sessions': known},
            'objects': {'volume': PROJECT + '_objects', 'inventory': restore.inventory(PROJECT + '_objects')},
            'roles': {'providers': roles(), 'all_roles_sha256': sql(recovery.ROLE_FINGERPRINT)}}

    def _stop(self, names):
        rows = containers()
        for name in names:
            if rows[name]['State']['Running']:
                manage.docker('stop', '--time', '15', rows[name]['Id'])

    def arm_boot_interlock(self, binding, preimage):
        # Persistent rehearsal interlock, NOT an installed systemd boot fence.
        path = self.runtime / 'provider149-boot-interlock.json'
        if path.exists() or path.is_symlink(): raise RuntimeError('provider149_interlock_exists')
        restore.write_binary(path, encoded({'binding': binding, 'preimage_sha256': digest(preimage)}))

    def fence_ingress(self, binding, preimage): self._stop(INGRESS)
    def fence_supervisors(self, binding, preimage): self._stop(BUSINESS)
    def fence_objects(self, binding, preimage): self._stop(PROVIDERS)

    def fence_roles(self, binding, preimage):
        if roles() != preimage['roles']['providers']:
            raise RuntimeError('provider149_role_preimage_changed')
        sql(';'.join('alter role "' + name + '" nologin' for name in ROLE_NAMES) + ';')

    def drain_sessions(self, binding, preimage):
        known = {row['pid']: row for row in preimage['supervisors']['known_sessions']}
        actual = sessions()
        if any(known.get(row['pid']) != row for row in actual):
            raise RuntimeError('provider149_unknown_session_refuse_termination')
        for row in actual:
            # PID, backend_start, role and application must all still match.
            statement = ("select pg_terminate_backend(pid) from pg_stat_activity where pid=" + str(row['pid'])
                + " and backend_start::text=" + smoke.literal(row['start']) + " and usename=" + smoke.literal(row['role'])
                + " and application_name=" + smoke.literal(row['application']) + ';')
            if sql(statement) not in ('t', ''): raise RuntimeError('provider149_identified_drain_failed')

    def verify_effect(self, step, binding, preimage):
        rows = containers()
        stopped = lambda names: all(not rows[name]['State']['Running'] and not rows[name]['State'].get('Restarting') for name in names)
        if step == 'arm_boot_interlock':
            return private(self.runtime / 'provider149-boot-interlock.json') == {'binding': binding, 'preimage_sha256': digest(preimage)}
        if step == 'fence_ingress': return stopped(INGRESS) and public_fenced()
        if step == 'fence_supervisors': return stopped(BUSINESS)
        if step == 'fence_objects':
            if not stopped(PROVIDERS): return False
            # Any unknown running container mounting the bytes blocks; never kill it.
            identifiers = manage.docker('ps', '-q', '--no-trunc').decode().split()
            running = json.loads(manage.docker('inspect', *identifiers)) if identifiers else []
            if any(mount.get('Name') == PROJECT + '_objects' and mount.get('RW')
                   for row in running for mount in row.get('Mounts', [])):
                return False
            return restore.inventory(PROJECT + '_objects') == preimage['objects']['inventory']
        if step == 'fence_roles':
            return roles() == {name: dict(value, login=False) for name, value in preimage['roles']['providers'].items()}
        if step == 'drain_sessions': return not sessions()
        raise RuntimeError('provider149_unknown_effect')

    def observe_quiescence(self, binding):
        preimage = self.journal.read()[0]['payload']['preimage']
        database = json.loads(sql("select json_build_object('schema',(select schema_version from application_schema_state where contract_key='core'),"
            "'prepared_transactions',(select count(*) from pg_prepared_xacts where database=current_database()),"
            "'processing_deliveries',(select count(*) from notification_deliveries where status='processing'),"
            "'processing_outbox',(select count(*) from notification_outbox where status='processing'),"
            "'queue_locks',(select count(*) from pg_locks where relation in ('notification_deliveries'::regclass,'notification_outbox'::regclass) and pid<>pg_backend_pid()));"))
        return {**database, 'system_identifier': self.system, 'other_client_sessions': len(sessions()),
            'unknown_writers': 0, 'ingress_fenced': self.verify_effect('fence_ingress', binding, preimage),
            'supervisors_fenced': self.verify_effect('fence_supervisors', binding, preimage),
            'objects_fenced': self.verify_effect('fence_objects', binding, preimage),
            'roles_fenced': self.verify_effect('fence_roles', binding, preimage),
            'boot_interlock_armed': self.verify_effect('arm_boot_interlock', binding, preimage),
            'candidate_read_only': all(not containers()[name]['State']['Running'] for name in BUSINESS)}

    def activation_evidence(self, binding, preimage):
        protocols = sql("select schema_version||':'||notification_delivery_protocol()||':'||notification_outbox_protocol() from application_schema_state where contract_key='core';")
        if protocols != '149:2:2': raise RuntimeError('provider149_recovery_schema_incompatible')
        # The fixture cannot fabricate root authority, real boot or replica proof.
        return {'binding_sha256': digest(binding), 'schema': 149, 'delivery_protocol': 2, 'outbox_protocol': 2,
                **{key: key in {'preservation', 'accepted_images', 'worker_ownership'} for key in ACTIVATION_GATES}}


def fault_evidence(records, controls=None):
    controls = controls or {}
    reconciled = {row['payload'].get('step') for row in records
                  if row['event'] == 'effect_complete' and row['payload'].get('reconciled') is True}
    return {'six_effect_children_interrupted': reconciled == set(FENCE_STEPS),
            **{key: controls.get(key) is True for key in (
                'new_role_connections_denied', 'existing_session_survived_nologin',
                'database_restart_preserved_fence')}}


def recover(runtime, driver, actor, *, snapshot_name="provider149-fenced-snapshot.json", report_name="provider149-result.json", native_controls=None):
    actor.require_authority(actor.binding, purpose='synthetic-recovery')
    preimage = driver._preimage()
    driver.require_quiescence(149)
    try: driver.activate()
    except RuntimeError as error:
        if str(error) != 'provider_maintenance_target_activation_not_authorized': raise
    else: raise RuntimeError('provider149_missing_controller_gates_falsely_accepted')
    snapshot = private(runtime / snapshot_name)
    if (digest(json.loads(sql(restore.FINGERPRINT_SQL))) != snapshot['rows_sha256']
            or restore.inventory(PROJECT + '_objects') != preimage['objects']['inventory']):
        raise RuntimeError('provider149_preservation_changed_before_recovery')
    # Explicit staging-only restoration of the original login attributes.
    sql(';'.join('alter role "' + name + '" ' + ('login' if value['login'] else 'nologin')
        for name, value in preimage['roles']['providers'].items()) + ';')
    if roles() != preimage['roles']['providers'] or sql(recovery.ROLE_FINGERPRINT) != preimage['roles']['all_roles_sha256']:
        raise RuntimeError('provider149_original_roles_not_restored')
    manage.docker('start', *[actor.inventory[name]['id'] for name in ('auth', 'rest', 'storage', 'gateway')])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            actor.positive_identity_probes(actor.binding)
            break
        except RuntimeError: time.sleep(1)
    else: raise RuntimeError('provider149_provider_restart_acceptance_failed')
    manage.docker('start', actor.inventory['backend']['id'])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        row = containers()['backend']
        if row['State'].get('Health', {}).get('Status') == 'healthy': break
        if not row['State']['Running']: raise RuntimeError('provider149_backend_recovery_exited')
        time.sleep(1)
    else: raise RuntimeError('provider149_backend_recovery_unhealthy')
    manage.docker('start', *[actor.inventory[name]['id'] for name in ('accepted-frontend', 'frontend', 'notification-worker')])
    result = {'scope': 'native synthetic149 provider lifecycle; not protected controller acceptance',
        'schema': 149, 'source_sha': actor.binding['source_sha'], 'both_protocols': 2,
        'positive_probes_before_barrier': True, **fault_evidence(driver.journal.read(), native_controls),
        'exact_known_session_drained': True,
        'original_all_role_state_restored': True, 'row_and_object_roots_preserved': True,
        'missing_privileged_activation_gates_rejected': True, 'native_provider_restart_acceptance': True, 'deletion_worker_retained_stopped': True,
        'production_modified': False, 'production_authorization_issued': False,
        'limitations': ['no installed protected production adapter or authority', 'no real systemd/reboot lifecycle',
            'same staging VM, not off-host or production current-data rehearsal',
            'prepared transactions checked but max_prepared_transactions fault not injected',
            'postgres superuser remains exact synthetic maintenance channel',
            'synthetic explicit recovery is not protected production NORMAL activation']}
    manage.private_write(report_name, json.dumps(result, indent=2) + '\n')
    return result


def main(mode, stage=None):
    if mode not in {'INSPECT', 'REHEARSE', 'RECOVER', 'APPLY-ONE'}:
        raise RuntimeError('provider149_unknown_mode')
    if (mode == 'APPLY-ONE') != (stage in FENCE_STEPS):
        raise RuntimeError('provider149_fixed_effect_required')
    manage.require_staging_host()
    runtime = Path.home() / PROJECT
    with acceptance.target(runtime):
        manage.state(); manage.attest_resources(); manage.require_database_marker()
        root = runtime / 'provider149-journal'
        if mode == 'INSPECT':
            print(json.dumps({'mode': mode, 'project': PROJECT, 'schema': sql("select schema_version from application_schema_state where contract_key='core';"),
                'journal_present': root.exists(), 'mutations_executed': False})); return
        if mode == 'REHEARSE':
            if root.exists() or root.is_symlink(): raise RuntimeError('provider149_existing_attempt_requires_explicit_recovery')
            root.mkdir(mode=0o700)
        journal = Journal(root)
        actor = StagingActor(runtime, journal)
        driver = ProviderMaintenance(actor.binding, journal, actor)
        if mode == 'APPLY-ONE':
            original = getattr(actor, stage)
            def interrupted(binding, preimage):
                original(binding, preimage)
                os._exit(73)
            setattr(actor, stage, interrupted)
            driver._effect(stage)
            raise RuntimeError('provider149_interruption_not_reached')
        if mode == 'RECOVER':
            print(json.dumps(recover(runtime, driver, actor), sort_keys=True)); return
        sql("create table public.phase5_provider_lease_probe(id int primary key,value text); "
            "grant insert on public.phase5_provider_lease_probe to supabase_auth_admin; comment on table public.phase5_provider_lease_probe is 'madar-schema149-phase5-provider-probe';")
        database = manage.database_container()
        writer = subprocess.Popen(manage.DOCKER + ['exec', '-i', '--env', 'PGAPPNAME=' + PROJECT + ':lease-probe', database,
            'sh', '-ec', 'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h127.0.0.1 -Usupabase_auth_admin -dmadar_hardening -XqAt -vON_ERROR_STOP=1'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={'PATH': os.defpath, 'HOME': str(Path.home())}, bufsize=0)
        try:
            if writer_line(writer, "begin; insert into public.phase5_provider_lease_probe values(1,'uncommitted'); select 'ready';") != 'ready':
                raise RuntimeError('provider149_existing_session_setup_failed')
            driver.prepare()
            for step in FENCE_STEPS:
                child = subprocess.run([sys.executable, str(Path(__file__).resolve()), 'APPLY-ONE', '--step', step],
                    capture_output=True, timeout=100, env={'PATH': os.defpath, 'HOME': str(Path.home())})
                if child.returncode != 73:
                    manage.private_write('provider149-child-error.log', child.stderr.decode(errors='replace'))
                    raise RuntimeError('provider149_child_interruption_failed')
                if step == 'fence_roles':
                    if writer_line(writer, "insert into public.phase5_provider_lease_probe values(2,'old-session'); select 'old-can-write';") != 'old-can-write':
                        raise RuntimeError('provider149_existing_session_control_failed')
                    denied = subprocess.run(manage.DOCKER + ['exec', database, 'sh', '-ec',
                        'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -h127.0.0.1 -Usupabase_auth_admin -dmadar_hardening -XqAt -c "select 1"'],
                        capture_output=True, timeout=10, env={'PATH': os.defpath, 'HOME': str(Path.home())})
                    if denied.returncode == 0 or b'is not permitted to log in' not in denied.stderr:
                        raise RuntimeError('provider149_new_login_denial_unproven')
                driver.reconcile_pending()
            writer.communicate(timeout=10)
            if sql('select count(*) from phase5_provider_lease_probe;') != '0':
                raise RuntimeError('provider149_drain_failed_to_rollback')
            driver.require_quiescence(149)
            manage.private_write('provider149-fenced-snapshot.json', json.dumps({'rows_sha256': digest(json.loads(sql(restore.FINGERPRINT_SQL)))}) + '\n')
            manage.docker('restart', '--time', '15', database)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    manage.require_database_marker(); break
                except RuntimeError: time.sleep(1)
            else: raise RuntimeError('provider149_fenced_database_restart_failed')
            driver.require_quiescence(149)
            print(json.dumps(recover(runtime, driver, actor, native_controls={
                'new_role_connections_denied': True, 'existing_session_survived_nologin': True,
                'database_restart_preserved_fence': True}), sort_keys=True))
        finally:
            if writer.poll() is None:
                writer.kill(); writer.communicate(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=('INSPECT', 'REHEARSE', 'RECOVER', 'APPLY-ONE'), default='INSPECT')
    parser.add_argument('--step', choices=FENCE_STEPS)
    args = parser.parse_args()
    if (args.mode == 'APPLY-ONE') != (args.step is not None): parser.error('Internal APPLY-ONE requires exactly one fixed fence step')
    main(args.mode, args.step)
