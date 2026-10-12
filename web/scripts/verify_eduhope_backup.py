#!/usr/bin/env python3
"""Capture and actually restore the marked preview in a NEW isolated database."""
import argparse,hashlib,json,os,secrets,subprocess
from pathlib import Path
from urllib.parse import urlsplit
import psycopg
from psycopg import sql
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
MARKER='madar-eduhope-local-preview-v1'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--local-env',type=Path,default=ROOT/'web/.eduhope-preview.local/backend.env');p.add_argument('--verify',action='store_true');a=p.parse_args()
 if not a.verify:print('Dry-run: backup only marked preview144; restore into new marked isolated database; never replace current data.');return
 v=dotenv_values(a.local_env);u=urlsplit(v['SUPABASE_DB_URL']);assert v['APP_ENV']=='development' and u.hostname=='127.0.0.1' and u.port==54322 and u.path=='/madar_eduhope_preview_144'
 def roots(db):
  return {table:db.execute(sql.SQL("select count(*),md5(coalesce(string_agg(to_jsonb(t)::text,'' order by to_jsonb(t)::text),'')) from {} t").format(sql.Identifier(table))).fetchone() for table in ['builder_projects','elearning_forms','elearning_form_versions','elearning_form_responses','elearning_form_reviews','elearning_courses','elearning_lessons','elearning_content_blocks','elearning_assessments']}
 with psycopg.connect(v['SUPABASE_DB_URL']) as db:
  db.execute('set transaction read only');assert db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]==MARKER
  expected=roots(db);assert db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]==144
 folder=a.local_env.parent/'backups';folder.mkdir(mode=0o700,exist_ok=True);name='madar_eduhope_restore_check_'+secrets.token_hex(6)
 data=subprocess.check_output(['docker','exec','supabase_db_web','pg_dump','-U','postgres','-Fc','madar_eduhope_preview_144']);dump=folder/(name+'.dump');fd=os.open(dump,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as out:out.write(data)
 dsn=psycopg.conninfo.make_conninfo(v['SUPABASE_DB_URL'],dbname='postgres')
 with psycopg.connect(dsn,autocommit=True) as admin:
  assert not admin.execute('select 1 from pg_database where datname=%s',(name,)).fetchone()
  admin.execute(sql.SQL('create database {} template template0').format(sql.Identifier(name)));admin.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(name),sql.Literal(MARKER+'-restore-check')))
 try:
  subprocess.run(['docker','exec','-i','supabase_db_web','pg_restore','-U','supabase_admin','-d',name,'--exit-on-error'],input=data,check=True,stdout=subprocess.DEVNULL)
  with psycopg.connect(psycopg.conninfo.make_conninfo(dsn,dbname=name)) as restored:
   restored.execute('set transaction read only');assert roots(restored)==expected
   assert restored.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]==144
  report={'schema':144,'sha256':hashlib.sha256(data).hexdigest(),'restored_table_roots_match':True,'tables':{k:v[0] for k,v in expected.items()},'production_touched':False}
  out=folder/(name+'.json');out.write_text(json.dumps(report,indent=2)+'\n');out.chmod(0o600);print(json.dumps(report,indent=2))
 finally:
  with psycopg.connect(dsn,autocommit=True) as admin:
   assert name.startswith('madar_eduhope_restore_check_') and admin.execute("select shobj_description(oid,'pg_database') from pg_database where datname=%s",(name,)).fetchone()[0]==MARKER+'-restore-check'
   admin.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
if __name__=='__main__':main()
