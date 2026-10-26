"""Disposable-only rehearsal adapter to the existing migration executor.

This module cannot target a production database: explicit loopback address and
an exact database ownership comment are required on every connection. It is
not installed as a privileged release command, does not accept SQL arguments,
and creates no operational approval. Production dispatch remains unavailable.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
from .migration_inventory import discover
from .migration_executor import Migration, MigrationManifest, LockedMigrationExecutor
from .migration_plan import verify

MARKER='madar-generic-migration-synthetic-rehearsal'


def connect(dsn):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    try:
        args=conninfo_to_dict(dsn)
        if (args.get('host')!='127.0.0.1' or args.get('service') or args.get('hostaddr','127.0.0.1')!='127.0.0.1'
                or args.get('dbname')!='postgres' or args.get('user')!='postgres'):
            raise RuntimeError('disposable_address_required')
        connection=psycopg.connect(dsn,hostaddr='127.0.0.1',autocommit=True,connect_timeout=5,
            options='-c search_path=pg_catalog,public,extensions')
        try:
            row=connection.execute("select pg_catalog.shobj_description(oid,'pg_database') from pg_catalog.pg_database where datname OPERATOR(pg_catalog.=) pg_catalog.current_database()").fetchone()
            if row!=(MARKER,): raise RuntimeError('disposable_marker_required')
            connection.execute("set statement_timeout='10s'")
            connection.execute("set lock_timeout='1500ms'")
            return connection
        except BaseException:
            connection.close(); raise
    except Exception:
        raise RuntimeError('generic_rehearsal_database_not_verified') from None


def run(root, inventory, plan, *, dsn, state_file, backup_dir, backup_verifier):
    """A failed/consumed attempt requires new inspection and a fresh attempt.

    SQL comes only from rediscovered Git objects. Rehearsal uses the production
    executor's captured-byte and session-lock code, without registering a
    completed-NORMAL operation or providing production authorization.
    """
    inventory=discover(root,source_sha=inventory.source_sha,history_base_sha=inventory.history_base_sha)
    plan=verify(root,inventory,encoded=plan.encoded)
    value=plan.document()
    if (value['risk_class']!='A' or not value['compatibility_covers_path']
            or value['execution_class']!='transactional' or value['protected_control_plane_changed']):
        raise RuntimeError('generic_rehearsal_routine_plan_required')
    if not value['migrations']: raise RuntimeError('generic_rehearsal_no_database_work')
    state_file=Path(state_file)
    state_file.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Exclusive attempt reservation survives a killed process. No auto-replay
    # after an ambiguous commit, even if the executor journal was not written.
    reservation=state_file.with_name(state_file.name+'.consumed')
    fd=os.open(reservation,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(plan.encoded); stream.flush(); os.fsync(stream.fileno())
    directory=os.open(reservation.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    with connect(dsn) as database:
        observed=database.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()
        if observed!=(value['origin_schema'],): raise RuntimeError('generic_rehearsal_schema_drift')
    with tempfile.TemporaryDirectory(prefix='madar-captured-migrations-') as temporary:
        migrations=[]
        for migration,row in zip(inventory.forward(value['origin_schema'],value['target_schema']),value['migrations']):
            path=Path(temporary)/f'{migration.number:03d}.sql'
            with path.open('xb') as stream: stream.write(migration.sql)
            migrations.append(Migration(migration.number,path,migration.sha256,row['from_schema'],row['to_schema'],'expand-only'))
        executor=LockedMigrationExecutor(connection_factory=lambda:connect(dsn),
            manifest=MigrationManifest(value['source_sha'],tuple(migrations)),
            state_file=state_file,backup_dir=Path(backup_dir),backup_verifier=backup_verifier,
            expected_origin=value['origin_schema'])
        return executor.run()
