"""Rehearse Academy projection migration and SQL tests only on a marked loopback database."""
from pathlib import Path
from urllib.parse import urlsplit
import os,re
import psycopg
from psycopg import sql
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
dsn=dotenv_values(root/'.env.database.local')['SUPABASE_DB_URL'];url=urlsplit(dsn)
assert url.hostname in {'localhost','127.0.0.1','::1'} and url.port==54322
name='madar_academy_rehearsal_133'
with psycopg.connect(dsn,autocommit=True) as db:
 if db.execute('select 1 from pg_database where datname=%s',(name,)).fetchone():
  marker=db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s",(name,)).fetchone()[0]
  assert marker=='madar-elearning-synthetic-rehearsal'
  db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
 db.execute(sql.SQL('create database {} template template0').format(sql.Identifier(name)))
 db.execute(sql.SQL("comment on database {} is 'madar-elearning-synthetic-rehearsal'").format(sql.Identifier(name)))
rehearsal=psycopg.conninfo.make_conninfo(dsn,dbname=name)
bootstrap=(root/'scripts/rehearse_migration_115.sh').read_text().split("<<'SQL'\n",1)[1].split('\nSQL',1)[0]
bootstrap=re.sub(r'create role \w+ nologin;\n','',bootstrap).replace("comment on database postgres is 'madar-commercial-synthetic-rehearsal';",'')
with psycopg.connect(rehearsal,autocommit=True) as db:
 db.execute('set client_min_messages=warning');db.execute(bootstrap);db.execute('alter table auth.users add column email text')
 for path in sorted((root/'database/migrations').glob('*.sql')):
  if path.name.startswith('133_'):
   # Strip only the outer transaction to prove full DDL rollback on an isolated DB.
   with db.transaction(force_rollback=True): db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
   assert db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]==132
   assert db.execute("select count(*) from information_schema.columns where table_schema='public' and table_name='website_settings' and column_name='academy_editor_project_id'").fetchone()[0]==0
   print('Migration 133 transaction rollback verified',flush=True)
  db.execute(path.read_text())
 print('Fresh migrations 001..133 applied; target',db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],flush=True)
# Connection string remains private; invoke database tests in-process.
os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN']=rehearsal
os.environ['PYTHONPATH']=str(root/'backend')
import sys,unittest
sys.path.insert(0,str(root/'backend'));sys.path.insert(0,str(root/'backend/tests'))
modules=['test_academy_integration_database','test_elearning_academy_database','test_elearning_credentials_database','test_elearning_commerce_database','test_elearning_placements_database','test_elearning_assessments_database','test_elearning_relationships_database','test_elearning_player_database','test_elearning_content_database','test_elearning_structure_database','test_elearning_course_deletion_database','test_elearning_enrollment_management_database']
if '--academy-only' in sys.argv:
 modules=['test_academy_integration_database','test_elearning_academy_database']
suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful(): raise SystemExit(1)
with psycopg.connect(dsn,autocommit=True) as db:
 marker=db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s",(name,)).fetchone()[0]
 assert marker=='madar-elearning-synthetic-rehearsal'
 db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
print('Marked rehearsal removed; local application data untouched.')
