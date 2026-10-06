"""Explicit fixture-only cleanup on loopback DB; no credential deletion API exists."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values
import psycopg
root=Path(__file__).resolve().parents[1]
p=Path('/tmp/madar-credential-browser-fixtures.json');fixture=json.loads(p.read_text())
config=dotenv_values(root/'.env.database.local');url=urlsplit(config['SUPABASE_DB_URL'])
assert url.hostname in {'localhost','127.0.0.1','::1'} and url.port==54322
assert fixture['tenant_id']==3 and fixture['user_id']==1 and len(fixture['courses'])<=3 and len(fixture['templates'])<=2 and len(fixture['plans'])<=1
with psycopg.connect(config['SUPABASE_DB_URL']) as db:
 assert db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]==130
 db.execute('select pg_advisory_xact_lock(125,3)')
 # Privileged deletion is allowed solely for exact temporary local fixtures.
 for cid in fixture['courses']:
  row=db.execute('select name,description,revision,structure_revision from elearning_courses where tenant_id=3 and id=%s',(cid,)).fetchone()
  if not row:continue
  assert row[1]=='Local credential verification'
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
  if row:assert row[0]['name'].startswith('Credential Test ');db.execute('delete from elearning_certificate_templates where tenant_id=3 and id=%s',(tid,))
 security=fixture.get('security')
 if security:
  assert security['foreign_tenant']!=3 and security['same_tenant_user']!=1 and security['foreign_user']!=1
  tid=security['foreign_tenant'];cid=security['foreign_course']
  tenant=db.execute('select brand_name from tenants where tenant_id=%s',(tid,)).fetchone()
  if tenant:
   assert tenant[0]=='Credential Isolation Fixture'
   db.execute('delete from elearning_credentials where tenant_id=%s and course_id=%s',(tid,cid))
   db.execute('delete from elearning_course_certificates where tenant_id=%s and course_id=%s',(tid,cid))
   db.execute('delete from elearning_certificate_templates where tenant_id=%s and id=%s',(tid,security['foreign_template']))
   course=db.execute('select name,revision,structure_revision from elearning_courses where tenant_id=%s and id=%s',(tid,cid)).fetchone()
   if course:
    assert course[0]=='Credential Isolation Fixture'
    db.execute('select public.delete_elearning_course(%s,%s,%s,%s,%s,%s,true)',(tid,cid,security['foreign_user'],course[1],course[2],course[0]))
  for uid,auth,owner in [(security['same_tenant_user'],security['same_tenant_auth'],3),(security['foreign_user'],security['foreign_auth'],tid)]:
   user=db.execute('select first_name,last_name,auth_id from users where id=%s and tenant_id=%s',(uid,owner)).fetchone()
   if user:
    assert user[0:2]==('Credential','Fixture') and str(user[2])==auth
    db.execute('delete from elearning_learners where tenant_id=%s and user_id=%s',(owner,uid))
    db.execute('delete from users where tenant_id=%s and id=%s',(owner,uid));db.execute('delete from auth.users where id=%s',(auth,))
  if tenant:db.execute('delete from tenants where tenant_id=%s',(tid,))
 if fixture.get('profile'):
  db.execute('update users set first_name=%s,last_name=%s where id=1 and tenant_id=3',(fixture['profile']['first_name'],fixture['profile']['last_name']))
print('Exact local credential fixtures removed; original test account and unrelated learning data preserved.')
