"""Rehearse the exact learning-only141→143 candidate; never application data."""
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
name = 'madar_learning_rehearsal_143'
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
    from test_elearning_placements_database import PlacementDatabaseTests
    fixture=PlacementDatabaseTests('test_section_then_course_completion_and_sequence')
    fixture.setUp()
    placement=fixture.create()
    fixture.snapshot(fixture.lesson,complete=True);fixture.snapshot(fixture.second,complete=True)
    original=fixture.submit(placement)['attempt'];fixture.db.commit()
    def history(db):
        return {
            'attempt':db.execute("select to_jsonb(t)-'review_revision' from public.elearning_assessment_attempts t where id=%s",(original['id'],)).fetchone()[0],
            'answers':db.execute('select to_jsonb(a) from public.elearning_assessment_answers a where attempt_id=%s order by question_id',(original['id'],)).fetchall(),
            'completion':db.execute('select to_jsonb(e) from public.elearning_completion_events e where course_id=%s order by id',(fixture.course,)).fetchall(),
        }
    before=history(fixture.db)
    candidate_sql=(root/'database/migrations/143_complete_learning_capabilities.sql').read_text()
    with fixture.db.transaction(force_rollback=True):
        fixture.db.execute(candidate_sql.removeprefix('begin;').removesuffix('commit;\n'))
        assert history(fixture.db)==before
        assert fixture.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]==143
    assert fixture.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]==141
    assert fixture.db.execute("select to_regclass('public.elearning_assessment_recordings')").fetchone()[0] is None
    assert history(fixture.db)==before
    fixture.db.commit()
    print('Populated141 attempt/answer/completion preservation and complete143 transactional rollback verified.',flush=True)
    import hashlib,subprocess,tempfile
    sys.path.insert(0,str(root))
    from deployment.lib.migration_executor import Migration,MigrationManifest,LockedMigrationExecutor
    backup_root=Path(tempfile.mkdtemp(prefix='learning143-backup-'))
    dump=backup_root/'schema141.dump'
    with dump.open('wb') as output:
        subprocess.run(['docker','exec','supabase_db_web','pg_dump','-U','postgres','-Fc',name],stdout=output,check=True)
    digest=hashlib.sha256(dump.read_bytes()).hexdigest()
    def verify_backup(_path):
        assert hashlib.sha256(dump.read_bytes()).hexdigest()==digest
        completed=subprocess.run(['docker','exec','-i','supabase_db_web','pg_restore','--list'],input=dump.read_bytes(),stdout=subprocess.PIPE,check=True)
        assert b'elearning_assessment_attempts' in completed.stdout
    manifest_path=root/'deployment/releases/migrations-141-143-learning.json'
    manifest=MigrationManifest.load(manifest_path,root.parent)
    result=LockedMigrationExecutor(connection_factory=lambda:psycopg.connect(rehearsal),manifest=manifest,state_file=backup_root/'execution.json',backup_dir=backup_root,backup_verifier=verify_backup).run()
    assert [m['number'] for m in result['migrations']]==[143]
    assert history(fixture.db)==before
    fixture.db.commit();fixture.doCleanups()
    # Reject the excluded state before any SQL. This is a synthetic state flag,
    # not an installation or execution of Exchange142.
    with psycopg.connect(rehearsal,autocommit=True) as db:db.execute("update public.application_schema_state set schema_version=142 where contract_key='core'")
    try:
        LockedMigrationExecutor(connection_factory=lambda:psycopg.connect(rehearsal),manifest=manifest,state_file=backup_root/'reject142.json',backup_dir=backup_root,backup_verifier=verify_backup).run()
        raise AssertionError('Excluded142 accepted')
    except RuntimeError as error:assert str(error)=='unexpected_schema:142'
    with psycopg.connect(rehearsal,autocommit=True) as db:db.execute("update public.application_schema_state set schema_version=143 where contract_key='core'")
    resumed=LockedMigrationExecutor(connection_factory=lambda:psycopg.connect(rehearsal),manifest=manifest,state_file=backup_root/'resume143.json',backup_dir=backup_root,backup_verifier=verify_backup).run()
    assert resumed['migrations'][0]['status']=='already_applied'
    print('Verified real schema141 dump; locked executor applied only143, rejected142 and resumed143 without executing SQL.',flush=True)
    suite=unittest.defaultTestLoader.loadTestsFromName('test_learning143_database')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise RuntimeError('Learning143 transactional tests failed')
finally:
    with psycopg.connect(dsn, autocommit=True) as db:
        if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s", (name,)).fetchone()[0] != marker:
            raise RuntimeError('Rehearsal cleanup marker changed')
        db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
    print('Disposable rehearsal removed; application data untouched.')
