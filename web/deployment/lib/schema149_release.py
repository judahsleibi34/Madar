"""Explicit146→149 admission through the existing protected coordinator only.

No CLI, authority issuer, database connection factory or arbitrary SQL executor.
Intermediate147/148 are maintenance checkpoints, never NORMAL destinations.
"""
import hashlib
import json
from pathlib import Path

MANIFEST = 'migrations-147-149-coordinated.json'
BRIDGE = 'schema-146-149-coordinated.json'
MANIFEST_SHA256 = '167e908c070679a07a8e16140aa59b0a122c1dbb2a6eb64757c4b9516f548978'
BRIDGE_SHA256 = '6d23503dc0588653ef34625a7bc77d2c8eb4474ddf2a06621aec1d3545781dde'
SQL_SHA256 = {147: 'bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3',
              148: 'a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096',
              149: '8ed767df57f5c02be50d83621fe45d314b3d1fdb42d2b7a470170519bdf1f869'}


def captured_json(path, expected):
    # Metadata is bounded independently; SQL capture lives in the executor.
    import os
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1024 * 1024:
            raise RuntimeError('schema149_metadata_invalid')
        data = source.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('schema149_metadata_changed')
    return json.loads(data)


def source_manifest(root):
    root = Path(root).resolve()
    releases = root / 'web/deployment/releases'
    raw = captured_json(releases / MANIFEST, MANIFEST_SHA256)
    bridge = captured_json(releases / BRIDGE, BRIDGE_SHA256)
    if (bridge['schema'] != {'compatible_min':146,'compatible_max':149,'target':149,
            'migration_class':'coordinated','rollback_compatible_min':149,'rollback_compatible_max':149}
            or bridge['migration_manifest'] != MANIFEST or bridge['migration_policy'] != 'none'
            or [row['number'] for row in raw['migrations']] != [147,148,149]):
        raise RuntimeError('schema149_chain_invalid')
    for row in raw['migrations']:
        number = row['number']
        path = root / 'web/database/historical-architecture-146-150' / Path(row['path']).name
        mirror = root / 'web/supabase/historical-architecture-146-150' / path.name
        if (row['from_schema'] != number-1 or row['to_schema'] != number
                or row['sha256'] != SQL_SHA256[number]
                or root not in path.resolve().parents or path.is_symlink() or mirror.is_symlink()
                or row['compatibility'] != ('forward-compatible' if number == 148 else 'coordinated')):
            raise RuntimeError('schema149_sql_changed')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != SQL_SHA256[number] or data != mirror.read_bytes():
            raise RuntimeError('schema149_sql_changed')
    return raw


def admitted_manifest(root, contract):
    """This divergent historical contract cannot authorize canonical SQL."""
    raise RuntimeError('architecture_history_superseded_non_executable')


QUIESCENCE_SQL = """
select json_build_object(
 'system_identifier',(select system_identifier::text from pg_control_system()),
 'schema',(select schema_version from public.application_schema_state where contract_key='core'),
 'processing_deliveries',(select count(*) from public.notification_deliveries where status='processing'),
 'processing_outbox',(select count(*) from public.notification_outbox where status='processing'),
 'processing_deletions',(select count(*) from public.data_deletion_requests where state='in_progress'),
 'other_client_sessions',(select count(*) from pg_stat_activity where datname=current_database()
    and backend_type='client backend' and pid<>pg_backend_pid()),
 'prepared_transactions',(select count(*) from pg_prepared_xacts where database=current_database()),
 'queue_locks',(select count(*) from pg_locks where relation=any(array[
    'public.notification_deliveries'::regclass,'public.notification_outbox'::regclass,
    'public.data_deletion_requests'::regclass,'public.data_deletion_steps'::regclass])
    and pid is distinct from pg_backend_pid()),
 'delivery_protocol',case when to_regprocedure('public.notification_delivery_protocol()') is null then 1 else 2 end,
 'outbox_protocol',case when to_regprocedure('public.notification_outbox_protocol()') is null then 1 else 2 end)
"""
COUNTERS = ('processing_deliveries','processing_outbox','processing_deletions',
            'other_client_sessions','prepared_transactions','queue_locks')


def require_database_quiescence(observed, contract, expected_schema):
    if (type(expected_schema) is not int or expected_schema not in (146,147,148,149)
            or set(observed) != {'system_identifier','schema','delivery_protocol','outbox_protocol',*COUNTERS}
            or observed['system_identifier'] != contract['database']['system_identifier']
            or type(observed['schema']) is not int or observed['schema'] != expected_schema
            or type(observed['delivery_protocol']) is not int
            or observed['delivery_protocol'] != (1 if expected_schema == 146 else 2)
            or type(observed['outbox_protocol']) is not int
            or observed['outbox_protocol'] != (2 if expected_schema == 149 else 1)
            or any(type(observed[key]) is not int or observed[key] != 0 for key in COUNTERS)):
        raise RuntimeError('schema149_database_not_quiescent')
    return observed


def migration_guard(contract, cursor, migration, *, consumer_guard, provider_guard):
    from deployment.lib.completed_normal_admission import require_fresh_authorization
    from deployment.lib.completed_normal_profile import profile, OUTBOX
    if profile(contract) is not OUTBOX or migration.number not in OUTBOX.migrations or migration.from_schema != migration.number-1:
        raise RuntimeError('schema149_step_invalid')
    require_fresh_authorization(contract)
    consumer_guard()
    # An explicit protected maintenance adapter must observe the persistent
    # barrier. A prior PASS packet or stopped notification container is insufficient.
    provider_guard(migration.from_schema, migration.to_schema)
    cursor.execute("set lock_timeout='5s'; set statement_timeout='60s'")
    cursor.execute(QUIESCENCE_SQL)
    require_database_quiescence(cursor.fetchone()[0], contract, migration.from_schema)
    if migration.from_schema >= 147:
        cursor.execute('select public.notification_delivery_protocol()')
        if cursor.fetchone()[0] != 2:
            raise RuntimeError('schema149_delivery_protocol_invalid')


def require_target_protocols(schema, delivery, outbox):
    if type(schema) is not int or schema != 149 or type(delivery) is not int or delivery != 2 or type(outbox) is not int or outbox != 2:
        raise RuntimeError('schema149_target_protocols_required')
