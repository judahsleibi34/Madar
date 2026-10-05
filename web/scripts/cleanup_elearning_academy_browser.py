"""Explicit fixture-only cleanup on loopback DB; no credential deletion API exists."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values
import psycopg
root=Path(__file__).resolve().parents[1]
p=Path('/tmp/madar-academy-browser-fixtures.json');fixture=json.loads(p.read_text())
config=dotenv_values(root/'.env.database.local');url=urlsplit(config['SUPABASE_DB_URL'])
assert url.hostname in {'localhost','127.0.0.1','::1'} and url.port==54322
assert fixture['tenant_id']==3 and fixture['user_id']==1 and len(fixture['courses'])<=7 and len(fixture['templates'])<=1 and len(fixture['plans'])<=3
with psycopg.connect(config['SUPABASE_DB_URL']) as db:
 assert db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]==130
 db.execute('select pg_advisory_xact_lock(125,3)')
 # Privileged deletion is allowed solely for exact temporary local fixtures.
 for cid in fixture['courses']:
  row=db.execute('select name,description,revision,structure_revision from elearning_courses where tenant_id=3 and id=%s',(cid,)).fetchone()
  if not row:continue
  assert row[1]=='Local Academy verification'
  db.execute('delete from elearning_credentials where tenant_id=3 and course_id=%s',(cid,))
  db.execute('delete from elearning_course_certificates where tenant_id=3 and course_id=%s',(cid,))
 for plan in fixture['plans']:
  rows=db.execute('select id,order_id from ecommerce_checkouts where tenant_id=3 and offering_id=%s',(plan,)).fetchall()
  assert all(str(row[0]) in fixture['checkouts'] for row in rows)
  for cid,order in rows:
   db.execute('delete from ecommerce_payment_events where tenant_id=3 and checkout_id=%s',(cid,));db.execute('delete from ecommerce_entitlements where tenant_id=3 and checkout_id=%s',(cid,));db.execute('delete from ecommerce_checkouts where tenant_id=3 and id=%s',(cid,));db.execute('delete from ecommerce_order_status_history where tenant_id=3 and order_id=%s',(order,));db.execute('delete from ecommerce_orders where tenant_id=3 and id=%s',(order,))
  product=db.execute('select product_id from ecommerce_offerings where tenant_id=3 and id=%s',(plan,)).fetchone()
  if product:db.execute('delete from ecommerce_offerings where tenant_id=3 and id=%s',(plan,));db.execute('delete from ecommerce_products where tenant_id=3 and id=%s',(product[0],))
 for cid in fixture['courses']:
  row=db.execute('select name,revision,structure_revision from elearning_courses where tenant_id=3 and id=%s',(cid,)).fetchone()
  if row:db.execute('select public.delete_elearning_course(3,%s,1,%s,%s,%s,true)',(cid,row[1],row[2],row[0]))
 for tid in fixture['templates']:
  row=db.execute('select design from elearning_certificate_templates where tenant_id=3 and id=%s',(tid,)).fetchone()
  if row:assert row[0]['name']=='Academy Standard';db.execute('delete from elearning_certificate_templates where tenant_id=3 and id=%s',(tid,))
 if fixture.get("settings"):
  db.execute("select public.save_elearning_settings(3,%s::jsonb)",(json.dumps(fixture["settings"]),))
print("Exact local Academy fixtures removed; original settings/account and unrelated data preserved.")
