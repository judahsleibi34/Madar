"""Rehearse the unselected144→145 academy admin candidate in a marked disposable DB.

Path: 001–141, then learning143 and forms144 (Exchange142 is never executed),
then 145 — transactional rollback over real schema144 referral rewards, locked
execution from a verified backup, re-entry, and the referral/programme/commerce
and admin-control database suites.
"""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
import psycopg
from psycopg import sql
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
dsn = dotenv_values(root / '.env.database.local')['SUPABASE_DB_URL']
url = urlsplit(dsn)
if url.hostname not in {'localhost', '127.0.0.1', '::1'} or url.port != 54322:
    raise RuntimeError('Rehearsal requires the isolated loopback database')
name = 'madar_academy_admin_rehearsal_145'
marker = 'madar-elearning-synthetic-rehearsal'
with psycopg.connect(dsn, autocommit=True) as db:
    if db.execute('select 1 from pg_database where datname=%s', (name,)).fetchone():
        if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s", (name,)).fetchone()[0] != marker:
            raise RuntimeError('Existing database is not a disposable rehearsal')
        db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
    db.execute(sql.SQL('create database {} template template0').format(sql.Identifier(name)))
    db.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(name), sql.Literal(marker)))
rehearsal = psycopg.conninfo.make_conninfo(dsn, dbname=name)
os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN'] = rehearsal
os.environ['MADAR_ENV_FILE'] = str(root / '.env.database.local')
sys.path.insert(0, str(root / 'backend'))
sys.path.insert(0, str(root / 'backend/tests'))
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'scripts'))
schema = lambda db: db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
try:
    bootstrap = (root / 'scripts/rehearse_migration_115.sh').read_text().split("<<'SQL'\n", 1)[1].split('\nSQL', 1)[0]
    bootstrap = re.sub(r'create role \w+ nologin;\n', '', bootstrap).replace("comment on database postgres is 'madar-commercial-synthetic-rehearsal';", '')
    with psycopg.connect(rehearsal, autocommit=True) as db:
        db.execute('set client_min_messages=warning')
        db.execute(bootstrap)
        db.execute('alter table auth.users add column email text')
        for path in sorted((root / 'database/migrations').glob('*.sql')):
            number = int(path.name.split('_')[0])
            if number in {142, 145}:
                continue
            db.execute(path.read_text())
        assert schema(db) == 144
    print('Fresh schema144 reached through learning143 and forms144; Exchange142 not executed.', flush=True)

    # Real schema144 referral facts: an earned reward from a verified purchase.
    from test_academy_admin_controls_database import AcademyAdminControlsDatabaseTests
    fixture = AcademyAdminControlsDatabaseTests('test_rewards_stay_immediate_without_the_review_setting')
    fixture.setUp()
    fixture.attach(); fixture.activate(); fixture.paid_purchase()
    fixture.db.commit()
    snapshot = lambda db: db.execute("select to_jsonb(w)-'reviewed_by'-'reviewed_at'-'review_note' from public.academy_referral_rewards w where tenant_id=%s order by referral_id", (fixture.tenant,)).fetchall()
    wallet = lambda db: db.execute('select public.academy_wallet_values(%s,%s)', (fixture.tenant, fixture.user)).fetchone()[0]
    before, wallet_before = snapshot(fixture.db), wallet(fixture.db)
    fixture.db.commit()  # release read locks before the migration's ALTER TABLE
    assert before and before[0][0]['status'] == 'earned'
    sql145 = (root / 'database/migrations/145_add_academy_admin_review_controls.sql').read_text()
    with psycopg.connect(rehearsal) as db:
        with db.transaction(force_rollback=True):
            db.execute(sql145.removeprefix('begin;').removesuffix('commit;\n'))
            assert schema(db) == 145
            assert snapshot(db) == before
            after = wallet(db)
            assert {k: after[k] for k in wallet_before} == wallet_before and after['tuition_override'] is None
        assert schema(db) == 144
        assert db.execute("select to_regclass('public.academy_tuition_overrides')").fetchone()[0] is None
        assert snapshot(db) == before
    print('Populated144 rewards and wallet preserved through145; transactional rollback restored schema144.', flush=True)

    from deployment.lib.migration_executor import MigrationManifest, LockedMigrationExecutor
    from academy_admin_candidate import validated_entries
    validated_entries(root.parent)
    backup_root = Path(tempfile.mkdtemp(prefix='academy-admin145-backup-'))
    dump = backup_root / 'schema144.dump'
    with dump.open('wb') as output:
        subprocess.run(['docker', 'exec', 'supabase_db_web', 'pg_dump', '-U', 'postgres', '-Fc', name], stdout=output, check=True)
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    def verify(_path):
        assert hashlib.sha256(dump.read_bytes()).hexdigest() == digest
        listed = subprocess.run(['docker', 'exec', '-i', 'supabase_db_web', 'pg_restore', '--list'], input=dump.read_bytes(), stdout=subprocess.PIPE, check=True)
        assert b'academy_referral_rewards' in listed.stdout
    manifest = MigrationManifest.load(root / 'deployment/releases/migrations-144-145-academy-admin.json', root.parent)
    run = lambda state: LockedMigrationExecutor(connection_factory=lambda: psycopg.connect(rehearsal), manifest=manifest, state_file=backup_root / state, backup_dir=backup_root, backup_verifier=verify).run()
    applied = run('execution145.json')
    assert [item['number'] for item in applied['migrations']] == [145]
    assert run('resume145.json')['migrations'][0]['status'] == 'already_applied'
    with psycopg.connect(rehearsal) as db:
        assert schema(db) == 145 and snapshot(db) == before
    fixture.doCleanups()
    print('Verified schema144 backup; locked executor applied only145 and re-entry was a no-op.', flush=True)

    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in (
        'test_academy_admin_controls_database', 'test_academy_referrals_database', 'test_academy_programmes_database', 'test_elearning_commerce_database'))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError('Schema145 database tests failed')
finally:
    with psycopg.connect(dsn, autocommit=True) as db:
        if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s", (name,)).fetchone()[0] != marker:
            raise RuntimeError('Rehearsal cleanup marker changed')
        db.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(name)))
    print('Disposable rehearsal removed; application data untouched.')
