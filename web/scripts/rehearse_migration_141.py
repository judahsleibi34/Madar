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
name = 'madar_eduhope_rehearsal_141'
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
try:
    bootstrap = (root / 'scripts/rehearse_migration_115.sh').read_text().split("<<'SQL'\n", 1)[1].split('\nSQL', 1)[0]
    bootstrap = re.sub(r'create role \w+ nologin;\n', '', bootstrap).replace("comment on database postgres is 'madar-commercial-synthetic-rehearsal';", '')
    with psycopg.connect(rehearsal, autocommit=True) as db:
        db.execute('set client_min_messages=warning')
        db.execute(bootstrap)
        db.execute('alter table auth.users add column email text')
        for path in sorted((root / 'database/migrations').glob('*.sql')):
            number = int(path.name.split('_')[0])
            if number > 141:
                continue
            if number == 115:
                print('Production schema115 checkpoint reached; upgrading retained immutable history.', flush=True)
            if number == 139:
                # Test real schema138 records through the correction, including
                # generated history ownership, without seeding application data.
                from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests
                fixture = AcademyProgrammeDatabaseTests('test_affiliate_approval_reuses_codes_without_staff_role')
                try:
                    fixture.setUp()
                    application = fixture.apply()
                    fixture.review('application', application, 'approved', 1)
                    purchase = fixture.purchase()
                    before = fixture.db.execute('select terms from public.ecommerce_checkouts where id=%s', (purchase['id'],)).fetchone()[0]
                    with fixture.db.transaction(force_rollback=True):
                        fixture.db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
                        config = fixture.db.execute('select settings from public.elearning_settings where tenant_id=%s', (fixture.tenant,)).fetchone()[0]
                        assert config['programmes_enabled'] and 'eduhope_enabled' not in config
                        assert config['support_programme_name'] == 'Tuition Support'
                        assert config['tuition_sales_threshold'] == 4
                        assert fixture.db.execute('select terms from public.ecommerce_checkouts where id=%s', (purchase['id'],)).fetchone()[0] == before
                        history = fixture.db.execute('select application_id from public.academy_workflow_history where entity_id=%s', (application,)).fetchall()
                        assert history and all(str(row[0]) == str(application) for row in history)
                    assert fixture.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] == 138
                    print('Populated schema138 upgrade preserves configuration, financial terms and immutable history; rollback verified.', flush=True)
                finally:
                    fixture.doCleanups()
            if number == 140:
                from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests
                fixture = AcademyProgrammeDatabaseTests('test_affiliate_approval_reuses_codes_without_staff_role')
                try:
                    fixture.setUp()
                    application = fixture.apply()
                    before = fixture.db.execute('select to_jsonb(a) from public.academy_applications a where id=%s', (application,)).fetchone()[0]
                    with fixture.db.transaction(force_rollback=True):
                        fixture.db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
                        after = fixture.db.execute('select to_jsonb(a) from public.academy_applications a where id=%s', (application,)).fetchone()[0]
                        assert after.pop('opportunity_id') is None and after == before
                    assert fixture.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] == 139
                    print('Populated schema139 application preservation and upgrade rollback verified.', flush=True)
                finally:
                    fixture.doCleanups()
            if number == 141:
                from tests.test_academy_programmes_database import AcademyProgrammeDatabaseTests
                fixture=AcademyProgrammeDatabaseTests('test_affiliate_approval_reuses_codes_without_staff_role')
                try:
                    fixture.setUp(); application=fixture.apply(); purchase=fixture.purchase()
                    before=fixture.db.execute('select to_jsonb(a) from public.academy_applications a where id=%s',(application,)).fetchone()[0]
                    financial=fixture.db.execute('select terms from public.ecommerce_checkouts where id=%s',(purchase['id'],)).fetchone()[0]
                    with fixture.db.transaction(force_rollback=True):
                        fixture.db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
                        assert fixture.db.execute('select to_jsonb(a) from public.academy_applications a where id=%s',(application,)).fetchone()[0]==before
                        assert fixture.db.execute('select terms from public.ecommerce_checkouts where id=%s',(purchase['id'],)).fetchone()[0]==financial
                    assert fixture.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]==140
                    print('Populated schema140 application/payment preservation and rollback verified.',flush=True)
                finally:fixture.doCleanups()
            if number in {137, 138, 139, 140, 141}:
                with db.transaction(force_rollback=True):
                    db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
                actual = db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
                if actual != number - 1: raise RuntimeError('Migration rollback did not restore schema state')
            db.execute(path.read_text())
        print('Fresh schema141 and transactional rollback verified.', flush=True)
    os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN'] = rehearsal
    os.environ['MADAR_ENV_FILE'] = str(root / '.env.database.local')
    sys.path.insert(0, str(root / 'backend'))
    sys.path.insert(0, str(root / 'backend/tests'))
    suite = unittest.defaultTestLoader.loadTestsFromNames(['test_academy_programmes_database', 'test_academy_referrals_database', 'test_elearning_cefr_database', 'test_academy_multitenant_database', 'test_academy_owner_database', 'test_academy_integration_database', 'test_elearning_forms_database'])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
finally:
    with psycopg.connect(dsn, autocommit=True) as db:
        if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s", (name,)).fetchone()[0] != marker:
            raise RuntimeError('Rehearsal cleanup marker changed')
        db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
    print('Disposable rehearsal removed; application data untouched.')
