"""Read-only exact schema150 release preparation; never operational authority.

The existing protected coordinator remains authoritative. This successor is not
registered as executable while its concrete provider/boot/backup/write adapters
are incomplete. Historical148/149 profiles and migration bytes remain unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

# Keep source validation stdlib-only: check_forward_release loads this file
# directly without importing operational deployment modules.
MANIFEST = 'migrations-147-150-coordinated.json'
BRIDGE = 'schema-146-150-coordinated.json'
MANIFEST_SHA256 = '45308e8b7a1769e0cb3bded92eaf0f3a631fdc33aba52e79db4ebe37865660bb'
BRIDGE_SHA256 = '1295a481ec649b0bf87d6123186930fa04d5bfb1c955c6384a8e2943edfb4ee0'
SQL_SHA256 = {
    147: 'bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3',
    148: 'a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096',
    149: '8ed767df57f5c02be50d83621fe45d314b3d1fdb42d2b7a470170519bdf1f869',
    150: '63d4d0c7af93bd3c3e93158a2e281b41eed23b83bfafd4b3f1ba22313533b722',
}
SQL_NAMES = {
    147: '147_fence_notification_delivery_claims.sql',
    148: '148_guard_reservation_reactivation_capacity.sql',
    149: '149_fence_notification_outbox_claims.sql',
    150: '150_fence_data_deletion_ownership.sql',
}


def _captured_file(path, expected, *, maximum, kind):
    """Bounded regular-file bytes, authenticated on the same file descriptor."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
            raise RuntimeError('schema150_' + kind + '_invalid')
        body = source.read(maximum + 1)
    if len(body) > maximum or hashlib.sha256(body).hexdigest() != expected:
        raise RuntimeError('schema150_' + kind + '_changed')
    try:
        body.decode('utf-8')
    except UnicodeDecodeError:
        raise RuntimeError('schema150_' + kind + '_encoding_invalid') from None
    return body


def captured_json(path, expected):
    return json.loads(_captured_file(path, expected, maximum=1024 * 1024, kind='metadata'))


def _captured_sql(path, expected):
    return _captured_file(path, expected, maximum=16 * 1024 * 1024, kind='sql')


def captured_source(root):
    """Return authenticated metadata and immutable SQL snapshots for inspection.

    These bytes are useful evidence and test inputs. They do not admit an SQL
    executor, issue a grant, select the active descriptor or activate workers.
    """
    root = Path(root).resolve()
    releases = root / 'web/deployment/releases'
    raw = captured_json(releases / MANIFEST, MANIFEST_SHA256)
    bridge = captured_json(releases / BRIDGE, BRIDGE_SHA256)
    if (bridge['schema'] != {'compatible_min': 146, 'compatible_max': 150, 'target': 150,
            'migration_class': 'coordinated', 'rollback_compatible_min': 150,
            'rollback_compatible_max': 150}
            or bridge['migration_manifest'] != MANIFEST or bridge['migration_policy'] != 'none'
            or [row['number'] for row in raw['migrations']] != [147, 148, 149, 150]):
        raise RuntimeError('schema150_chain_invalid')
    snapshots = {}
    for row in raw['migrations']:
        number = row['number']
        if (type(number) is not int or row['from_schema'] != number - 1
                or row['to_schema'] != number
                or row['path'] != 'web/database/migrations/' + SQL_NAMES[number]
                or row['sha256'] != SQL_SHA256[number]
                or row['compatibility'] != ('forward-compatible' if number == 148 else 'coordinated')):
            raise RuntimeError('schema150_chain_invalid')
        path = root / row['path']
        mirror = root / 'web/supabase/migrations' / SQL_NAMES[number]
        if any(parent.is_symlink() for parent in (path.parent, mirror.parent,
                path.parent.parent, mirror.parent.parent)):
            raise RuntimeError('schema150_sql_path_invalid')
        data = _captured_sql(path, SQL_SHA256[number])
        if data != _captured_sql(mirror, SQL_SHA256[number]):
            raise RuntimeError('schema150_sql_mirror_changed')
        snapshots[number] = data
    return raw, snapshots


def source_manifest(root):
    return captured_source(root)[0]


def admitted_manifest(root, contract):
    # There is intentionally no caller-controlled adapter/receipt override.
    # Leave the operation out of the runtime profile registry until the full
    # protected lifecycle has independent implementation and acceptance.
    raise RuntimeError('schema150_protected_controller_integration_incomplete')


COUNTERS = ('processing_deliveries', 'processing_outbox', 'processing_deletions',
            'processing_steps', 'legacy_deletion_backlog', 'other_client_sessions',
            'prepared_transactions', 'queue_locks')
QUIESCENCE_SQL = """
select json_build_object(
 'system_identifier',(select system_identifier::text from pg_control_system()),
 'schema',(select schema_version from public.application_schema_state where contract_key='core'),
 'processing_deliveries',(select count(*) from public.notification_deliveries where status='processing'),
 'processing_outbox',(select count(*) from public.notification_outbox where status='processing'),
 'processing_deletions',(select count(*) from public.data_deletion_requests where state='in_progress'),
 'processing_steps',(select count(*) from public.data_deletion_steps where state='processing'),
 'legacy_deletion_backlog',case when
    (select schema_version from public.application_schema_state where contract_key='core')<150
    then (select count(*) from public.data_deletion_requests where state not in
      ('completed','completed_with_retained_records','cancelled_before_execution'))
    else 0 end,
 'other_client_sessions',(select count(*) from pg_stat_activity where datname=current_database()
    and backend_type='client backend' and pid<>pg_backend_pid()),
 'prepared_transactions',(select count(*) from pg_prepared_xacts where database=current_database()),
 'queue_locks',(select count(*) from pg_locks where relation=any(array[
    'public.notification_deliveries'::regclass,'public.notification_outbox'::regclass,
    'public.data_deletion_requests'::regclass,'public.data_deletion_steps'::regclass])
    and pid is distinct from pg_backend_pid()))
"""


def require_database_quiescence(observed, contract, expected_schema):
    if type(expected_schema) is not int or expected_schema not in (146, 147, 148, 149, 150):
        raise RuntimeError('schema150_database_not_quiescent')
    protocols = {'delivery_protocol': 1 if expected_schema == 146 else 2,
                 'outbox_protocol': 2 if expected_schema >= 149 else 1,
                 'deletion_protocol': 2 if expected_schema == 150 else 0}
    if (not isinstance(observed, dict)
            or set(observed) != {'system_identifier', 'schema', *protocols, *COUNTERS}
            or observed['system_identifier'] != contract['database']['system_identifier']
            or type(observed['schema']) is not int or observed['schema'] != expected_schema
            or any(type(observed[key]) is not int or observed[key] != expected for key, expected in protocols.items())
            or any(type(observed[key]) is not int or observed[key] != 0 for key in COUNTERS)):
        raise RuntimeError('schema150_database_not_quiescent')
    return observed


def observe_database_quiescence(cursor, contract, expected_schema):
    """Call actual protocol functions; their presence alone is insufficient."""
    if type(expected_schema) is not int or expected_schema not in (146, 147, 148, 149, 150):
        raise RuntimeError('schema150_database_not_quiescent')
    # PostgreSQL retains activity/statistics snapshots inside a transaction.
    # Refresh before EVERY admission observation: cached zero can miss a newly
    # connected writer, and cached one can retain an already closed backend.
    # This clears only this session's statistics cache, not business state.
    cursor.execute('select pg_catalog.pg_stat_clear_snapshot()')
    cursor.execute(QUIESCENCE_SQL)
    observed = cursor.fetchone()[0]
    for key, function, available in (
            ('delivery_protocol', 'notification_delivery_protocol', expected_schema >= 147),
            ('outbox_protocol', 'notification_outbox_protocol', expected_schema >= 149),
            ('deletion_protocol', 'data_deletion_ownership_protocol', expected_schema == 150)):
        if available:
            # Fixed module-owned identifiers only; no operator SQL interpolation.
            cursor.execute('select public.' + function + '()')
            observed[key] = cursor.fetchone()[0]
        else:
            cursor.execute('select to_regprocedure(%s)', ('public.' + function + '()',))
            if cursor.fetchone()[0] is not None:
                raise RuntimeError('schema150_unexpected_protocol_before_migration')
            observed[key] = 0 if key == 'deletion_protocol' else 1
    return require_database_quiescence(observed, contract, expected_schema)


def require_target_protocols(schema, delivery, outbox, deletion):
    if any(type(value) is not int for value in (schema, delivery, outbox, deletion)) or (schema, delivery, outbox, deletion) != (150, 2, 2, 2):
        raise RuntimeError('schema150_target_protocols_required')
