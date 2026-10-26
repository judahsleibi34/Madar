#!/usr/bin/env python3
"""Fresh candidate acceptance on the fixed, already restored150 staging target.

This does not restore/migrate a database or replay the consumed recovery attempt.
Only the schema150 recovery project's containers/configuration can change. The
original a8fac source and its maintenance barrier are outside this tool's scope.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

import manage
import restore
import smoke
import independent_recovery as recovery
import schema150_acceptance as acceptance
import schema150_application_restore as application_restore
import schema150_restore_configuration as configuration
import schema149_provider_rehearsal as providers

PROJECT, OWNER, MARKER = application_restore.PROJECT, application_restore.OWNER, application_restore.MARKER
ORIGIN_SHA = '8e17a128c0fadfc0f2eb6de95ab35f4a588240d1'
SERVICES = set(acceptance.SERVICES)
WRITERS = ('frontend', 'accepted-frontend', 'gateway', 'notification-worker', 'deletion-worker',
           'backend', 'storage', 'auth', 'rest')


def containers(*, complete=True):
    manage.attest_resources()
    identifiers = manage.docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + PROJECT).decode().split()
    values = json.loads(manage.docker('inspect', *identifiers)) if identifiers else []
    result = {}
    for row in values:
        labels = row['Config'].get('Labels', {})
        name = labels.get('com.docker.compose.service')
        if (labels.get('com.madar.staging.owner') != OWNER or name not in SERVICES or name in result
                or row['HostConfig']['RestartPolicy']['Name'] != 'no'):
            raise RuntimeError('refresh150_unknown_or_uncontrolled_container')
        result[name] = row
    if complete and set(result) != SERVICES: raise RuntimeError('refresh150_missing_container')
    return result


def attest_origin(images):
    if manage.state()['source_sha'] != ORIGIN_SHA or manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2':
        raise RuntimeError('refresh150_wrong_origin_source_or_schema')
    runtime = Path.home() / PROJECT
    report_bytes = configuration.regular(runtime / 'full-application-restore150.json')
    report = json.loads(report_bytes)
    if (report.get('source_sha') != ORIGIN_SHA or report.get('images') != images or report.get('schema') != 150
            or not report.get('accepted', {}).get('actual_restored_deletion_worker', {}).get('live_worker_processed_both_requests')):
        raise RuntimeError('refresh150_origin_application_acceptance_missing')
    rows = containers()
    for name, row in rows.items():
        reference = configuration.INFRA_IMAGES.get(name, images['backend' if name in ('backend', 'notification-worker', 'deletion-worker') else 'frontend'])
        image = json.loads(manage.docker('image', 'inspect', reference))[0]
        if row['Image'] != image['Id']: raise RuntimeError('refresh150_origin_image_substitution')
        if name not in configuration.INFRA_IMAGES:
            labels = image['Config'].get('Labels', {})
            if (image['Id'] != reference or labels.get('com.madar.release.sha') != ORIGIN_SHA
                    or labels.get('org.opencontainers.image.revision') != ORIGIN_SHA
                    or labels.get('com.madar.build.mode') != 'fresh-locked-ci'):
                raise RuntimeError('refresh150_origin_image_source_invalid')
        if any(m.get('Destination', '').startswith('/app') for m in row.get('Mounts', [])):
            raise RuntimeError('refresh150_origin_source_overlay_forbidden')
        limit, cpu = configuration.BOUNDS[name]
        if (not 0 < row['HostConfig'].get('Memory', 0) <= limit * 1024**2
                or not 0 < row['HostConfig'].get('NanoCpus', 0) <= int(cpu * 10**9)
                or not 0 < row['HostConfig'].get('PidsLimit', 0) <= 256):
            raise RuntimeError('refresh150_origin_resource_bound_invalid')
    credentials = configuration.live_credentials(rows)
    fixture = configuration.regular(runtime / 'smoke-fixture.json')
    return rows, credentials, fixture, hashlib.sha256(report_bytes).hexdigest()


def stop_owned(names, *, expected=None):
    rows = containers(complete=False)
    if expected is not None and ({name: (row['Id'], row['Image']) for name, row in rows.items()}
            != {name: (row['Id'], row['Image']) for name, row in expected.items()}):
        raise RuntimeError('refresh150_prepared_container_identity_changed')
    for name in names:
        if name in rows and rows[name]['State']['Running']:
            manage.docker('stop', '--time', '20', rows[name]['Id'])


def require_quiescence():
    if manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2':
        raise RuntimeError('refresh150_database_protocol_changed')
    rows = containers()
    if any(rows[name]['State']['Running'] or rows[name]['State'].get('Restarting') for name in WRITERS):
        raise RuntimeError('refresh150_writer_resurrected')
    if manage.sql("select count(*) from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid() and backend_type='client backend';") != '0':
        raise RuntimeError('refresh150_other_database_session_present')
    if manage.sql('select count(*) from pg_prepared_xacts where database=current_database();') != '0':
        raise RuntimeError('refresh150_prepared_transaction_present')
    if manage.sql("select (select count(*) from notification_deliveries where status='processing')+"
        "(select count(*) from notification_outbox where status='processing')+"
        "(select count(*) from data_deletion_requests where state='in_progress')+"
        "(select count(*) from data_deletion_steps where state='processing');") != '0':
        raise RuntimeError('refresh150_processing_work_requires_reconciliation')
    if manage.sql("select count(*) from pg_locks where pid<>pg_backend_pid() and relation=any(array["
        "'notification_deliveries'::regclass,'notification_outbox'::regclass,"
        "'data_deletion_requests'::regclass,'data_deletion_steps'::regclass]);") != '0':
        raise RuntimeError('refresh150_queue_lock_present')
    volume = json.loads(manage.docker('volume', 'inspect', PROJECT + '_objects'))[0]
    if (volume.get('Labels') or {}).get('com.madar.staging.owner') != OWNER:
        raise RuntimeError('refresh150_object_volume_owner_changed')
    identifiers = manage.docker('ps', '-q', '--no-trunc').decode().split()
    running = json.loads(manage.docker('inspect', *identifiers)) if identifiers else []
    if application_restore.has_object_writer(running, PROJECT + '_objects', volume['Mountpoint']):
        raise RuntimeError('refresh150_unknown_object_writer')


def preservation():
    return {'system_identifier': manage.sql('select system_identifier::text from pg_control_system();'),
            'rows_sequences': json.loads(manage.sql(restore.FINGERPRINT_SQL)),
            'roles_sha256': manage.sql(recovery.ROLE_FINGERPRINT),
            'privileges_sha256': manage.sql(recovery.PRIVILEGE_FINGERPRINT),
            'objects': restore.inventory(PROJECT + '_objects')}


def require_preservation(checkpoint):
    if manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2' or preservation() != checkpoint:
        raise RuntimeError('refresh150_pre_activation_preservation_failed')


def _run(mode, directory, source_sha, origin_directory):
    if (mode not in ('INSPECT', 'REHEARSE') or not re.fullmatch('[0-9a-f]{40}', source_sha or '')
            or source_sha == ORIGIN_SHA):
        raise RuntimeError('refresh150_explicit_new_candidate_required')
    manage.require_staging_host()
    original_runtime = Path.home() / PROJECT
    runtime = Path.home() / (PROJECT + '-candidate-' + source_sha[:12])
    with application_restore.target(original_runtime):
        artifact, run, images, receipt = acceptance.previous.artifacts(directory, source_sha)
        _, origin_run, origin_images, _ = acceptance.previous.artifacts(origin_directory, ORIGIN_SHA)
        origin_rows, credentials, fixture_bytes, origin_report_sha = attest_origin(origin_images)
        scope = original_runtime / ('candidate-refresh-' + source_sha)
        if mode == 'INSPECT':
            return {'mode': mode, 'project': PROJECT, 'source_sha': source_sha, 'origin_source_sha': ORIGIN_SHA,
                'schema': 150, 'target_images': images, 'origin_images': origin_images,
                'new_private_runtime': runtime.name, 'existing_attempt_preserved': scope.exists() or runtime.exists(),
                'mutations_executed': False, 'database_restore_or_migration': False, 'production_modified': False}
        if any(path.exists() or path.is_symlink() for path in (scope, runtime)):
            raise RuntimeError('refresh150_candidate_attempt_already_consumed')
        if shutil.disk_usage(Path.home()).free < 8 * 1024**3:
            raise RuntimeError('refresh150_disk_headroom_insufficient')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:')))
        if available < 1300 * 1024:
            raise RuntimeError('refresh150_memory_headroom_insufficient')
        scope.mkdir(mode=0o700)
        journal_root = scope / 'journal'; journal_root.mkdir(mode=0o700)
        journal = providers.Journal(journal_root)
        journal.append('prepared', {'source_sha': source_sha, 'origin_source_sha': ORIGIN_SHA,
            'origin_images': origin_images, 'target_images': images, 'origin_report_sha256': origin_report_sha,
            'containers': {name: {'id': row['Id'], 'image': row['Image']} for name, row in origin_rows.items()}})
        application_restore.durable(scope / 'original-identity.json', fixture_bytes)
        started = time.monotonic()
        try:
            journal.append('effect_intent', {'stage': 'stop_owned_target_writers'})
            stop_owned(WRITERS, expected=origin_rows)
            require_quiescence()
            checkpoint = preservation()
            require_quiescence()
            if preservation() != checkpoint: raise RuntimeError('refresh150_source_changed_while_capturing')
            application_restore.durable(scope / 'pre-activation.json', json.dumps(checkpoint, sort_keys=True).encode())
            journal.append('writers_quiescent', {'rows_sha256': hashlib.sha256(json.dumps(checkpoint['rows_sequences'], sort_keys=True).encode()).hexdigest()})
            with application_restore.target(runtime):
                configuration.generate(runtime, source_sha, images, receipt, credentials, PROJECT, OWNER)
            application_restore.import_target_images(runtime, directory, artifact, receipt, images, source_sha)
            with application_restore.target(runtime):
                journal.append('effect_intent', {'stage': 'recreate_owned_infrastructure'})
                manage.compose('up', '--detach', '--wait', '--wait-timeout', '90', 'postgres', 'redis')
                manage.attest_resources(); manage.require_database_marker()
                require_quiescence()
                require_preservation(checkpoint)
                journal.append('pre_activation_preservation_verified', {'same_database_cluster': True,
                    'rows_sequences_roles_acl_objects': True})
                manage.compose('up', '--detach', '--wait', '--wait-timeout', '180', *acceptance.SERVICES)
                manage.attest_resources(); manage.require_database_marker()
                original_identity = recovery.original_identity_acceptance(json.loads(fixture_bytes))
                smoke.main()
                acceptance.worker_health()
                deletion = acceptance.deletion_workflow()
                code = acceptance.runtime_identity(images, source_sha)
                if manage.sql(acceptance.PROTOCOL_SQL) != '150:2:2:2': raise RuntimeError('refresh150_post_acceptance_protocol_changed')
                report = {'scope': 'fresh exact-source image refresh on owned already-restored150 staging database',
                    'source_sha': source_sha, 'images': images, 'run_id': run['id'], 'origin_source_sha': ORIGIN_SHA,
                    'origin_images': origin_images, 'origin_run_id': origin_run['id'], 'origin_report_sha256': origin_report_sha,
                    'project': PROJECT, 'runtime': runtime.name, 'schema': 150, 'protocols': [2, 2, 2],
                    'same_database_cluster': True, 'database_restored': False, 'migration_executed': False,
                    'original_restore_attempt_overwritten': False, 'original_roles_and_acl_preserved_before_activation': True,
                    'original_rows_sequences_objects_preserved_before_activation': True,
                    'fresh_exact_source_images': True, 'source_overlay_used': False,
                    'original_identity_acceptance': original_identity, 'new_native_auth_mfa_storage_notifications': True,
                    'deletion_workflow': deletion, 'runtime_code_sha256': code,
                    'elapsed_seconds': round(time.monotonic() - started, 3), 'production_modified': False,
                    'preserved_original_a8fac_source_modified': False, 'production_authorized': False,
                    'limitations': ['same database refresh, not a new restore or full application PITR',
                        'same staging VM; not off-host or production controller acceptance',
                        'no host-root/privileged/socket writer-exclusion claim',
                        'provider roles are unchanged; fixed isolated target writers stopped and sessions checked',
                        'external integrations and host-file deletion not exercised by these native happy-path fixtures']}
                manage.private_write('schema150-candidate-refresh.json', json.dumps(report, indent=2) + '\n')
                journal.append('candidate_accepted', {'source_sha': source_sha, 'schema': 150})
                return report
        except BaseException:
            # Neither restart old images nor undo native writes. Stop only this
            # attested recovery project, preserve its DB/object volumes/evidence.
            selected = runtime if (runtime / 'verified-compose.json').is_file() else original_runtime
            with application_restore.target(selected): stop_owned(tuple(sorted(SERVICES)))
            raise


def main(mode, directory, source_sha, origin_directory):
    if (mode not in ('INSPECT', 'REHEARSE') or not re.fullmatch('[0-9a-f]{40}', source_sha or '')
            or source_sha == ORIGIN_SHA):
        raise RuntimeError('refresh150_explicit_new_candidate_required')
    manage.require_staging_host()
    if mode == 'REHEARSE':
        # Different candidate SHAs share one Docker project, database, ports
        # and volumes. Per-SHA consumed scopes cannot serialize these effects.
        with configuration.private_directory_lock(Path.home() / PROJECT):
            return _run(mode, directory, source_sha, origin_directory)
    return _run(mode, directory, source_sha, origin_directory)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('INSPECT', 'REHEARSE'), nargs='?', default='INSPECT')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--origin-artifacts', type=Path, required=True,
                        help='Authenticated artifacts for fixed accepted8e17a128 restoration origin')
    args = parser.parse_args()
    print(json.dumps(main(args.mode, args.artifacts, args.source_sha, args.origin_artifacts), sort_keys=True))
