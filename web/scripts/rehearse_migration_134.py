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
name='madar_groups_rehearsal_134'
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
  if path.name.startswith('134_'):
   legacy_tenant=db.execute("insert into public.tenants(brand_name,owner_name) values('Legacy groups','Local') returning tenant_id").fetchone()[0]
   db.execute("insert into public.elearning_groups(tenant_id,name) values(%s,'Legacy'),(%s,' LEGACY ')",(legacy_tenant,legacy_tenant))
   # Strip only the outer transaction to prove full DDL rollback on an isolated DB.
   with db.transaction(force_rollback=True): db.execute(path.read_text().removeprefix('begin;').removesuffix('commit;\n'))
   assert db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]==133
   assert db.execute("select count(*) from pg_proc where proname='delete_elearning_group'").fetchone()[0]==0
   print('Migration 134 transaction rollback verified',flush=True)
  db.execute(path.read_text())
 assert db.execute('select count(*) from public.elearning_groups where tenant_id=%s',(legacy_tenant,)).fetchone()[0]==2
 db.execute("update public.elearning_groups set description='Legacy data retained' where tenant_id=%s",(legacy_tenant,))
 print('Legacy duplicate records and non-name edits retained',flush=True)
 print('Fresh migrations 001..134 applied; target',db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],flush=True)
# Connection string remains private; invoke database tests in-process.
os.environ['ELEARNING_SYNTHETIC_DATABASE_DSN']=rehearsal
os.environ['PYTHONPATH']=str(root/'backend')
os.environ['MADAR_ENV_FILE']=str(root/'.env.database.local')
import sys,unittest
sys.path.insert(0,str(root/'backend'));sys.path.insert(0,str(root/'backend/tests'))
modules=['test_elearning_group_management_database.GroupManagementDatabaseTests','test_elearning_relationships_database.RelationshipsDatabaseTests','test_elearning_player_database.ELearningPlayerDatabaseTests']
suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful(): raise SystemExit(1)
with psycopg.connect(dsn,autocommit=True) as db:
 marker=db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s",(name,)).fetchone()[0]
 assert marker=='madar-elearning-synthetic-rehearsal'
 db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
print('Marked rehearsal removed; local application data untouched.')
