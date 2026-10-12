"""Validate EduHope on a marked disposable loopback database; never application data."""
from pathlib import Path
from urllib.parse import urlsplit
import os
import re
import sys
import unittest
import psycopg
from psycopg import sql
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
dsn = dotenv_values(root / '.env.database.local')['SUPABASE_DB_URL']
url = urlsplit(dsn)
if url.hostname not in {'localhost', '127.0.0.1', '::1'} or url.port != 54322:
    raise RuntimeError('Rehearsal requires the isolated loopback database')
name = 'madar_eduhope_rehearsal_138'
marker = 'madar-elearning-synthetic-rehearsal'
with psycopg.connect(dsn, autocommit=True) as db:
    if db.execute('select 1 from pg_database where datname=%s', (name,)).fetchone():
        if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s", (name,)).fetchone()[0] != marker:
            raise RuntimeError('Existing database is not a disposable rehearsal')
        db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
    db.execute(sql.SQL('create database {} template template0').format(sql.Identifier(name)))
    db.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(name), sql.Literal(marker)))
rehearsal = psycopg.conninfo.make_conninfo(dsn, dbname=name)
try:
    bootstrap = (root / 'scripts/rehearse_migration_115.sh').read_text().split("<<'SQL'\n", 1)[1].split('\nSQL', 1)[0]
    bootstrap = re.sub(r'create role \w+ nologin;\n', '', bootstrap).replace("comment on database postgres is 'madar-commercial-synthetic-rehearsal';", '')
    with psycopg.connect(rehearsal, autocommit=True) as db:
        db.execute('set client_min_messages=warning')
        db.execute(bootstrap)
        db.execute('alter table auth.users add column email text')
        for path in sorted((root / 'database/migrations').glob('*.sql')):
            number = int(path.name.split('_')[0])
            if number > 138:
                continue
            if number in {137, 138}:
                with db.transaction(force_rollback=True):
                    db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
                actual = db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
                if actual != number - 1: raise RuntimeError('Migration rollback did not restore schema state')
            db.execute(path.read_text())
        print('Fresh schema138 and transactional rollback verified.', flush=True)
    os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN'] = rehearsal
    os.environ['MADAR_ENV_FILE'] = str(root / '.env.database.local')
    sys.path.insert(0, str(root / 'backend'))
    sys.path.insert(0, str(root / 'backend/tests'))
    suite = unittest.defaultTestLoader.loadTestsFromNames(['test_academy_programmes_database', 'test_academy_referrals_database', 'test_elearning_cefr_database'])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
finally:
    with psycopg.connect(dsn, autocommit=True) as db:
        if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s", (name,)).fetchone()[0] != marker:
            raise RuntimeError('Rehearsal cleanup marker changed')
        db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
    print('Disposable rehearsal removed; application data untouched.')
