"""Explicit fixture-only cleanup on loopback DB; no credential deletion API exists."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values
import psycopg
root=Path(__file__).resolve().parents[1]
p=Path('/tmp/madar-academy131-browser-fixtures.json');fixture=json.loads(p.read_text())
config=dotenv_values(root/'.env.database.local');url=urlsplit(config['SUPABASE_DB_URL'])
assert url.hostname in {'localhost','127.0.0.1','::1'} and url.port==54322
assert fixture['tenant_id']==3 and fixture['user_id']==1 and len(fixture['courses'])<=7 and len(fixture['templates'])<=1 and len(fixture['plans'])<=3
with psycopg.connect(config['SUPABASE_DB_URL']) as db:
 assert db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]in (131,132)
 db.execute('select pg_advisory_xact_lock(125,3)')
 if fixture.get('builder_project'):
  # Legacy QA did not record provenance. Fail closed rather than delete an
  # existing tenant project or leave a stale binding.
  if not fixture.get('builder_project_created') or 'original_academy_bindings' not in fixture:
   raise ValueError('Legacy Academy cleanup lacks project/binding provenance')
  from academy_builder_fixture_cleanup import restore_academy_fixture_binding
  restore_academy_fixture_binding(db, fixture)

 # Assessment UI smoke checks create exact temporary definitions; retain any shared definition.
 assessment_ids=[]
 for cid in fixture['courses']:
  assessment_ids += [row[0] for row in db.execute("select distinct a.id from elearning_assessments a join elearning_assessment_placements p on p.assessment_id=a.id and p.tenant_id=a.tenant_id join elearning_courses c on c.id=p.course_id and c.tenant_id=p.tenant_id where a.tenant_id=3 and c.id=%s and c.description='Local Academy verification' and a.title='Local Level Review' and a.created_by=1",(cid,)).fetchall()]

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
 for aid in set(assessment_ids):
  if not db.execute('select 1 from elearning_assessment_placements where tenant_id=3 and assessment_id=%s',(aid,)).fetchone() and not db.execute('select 1 from elearning_content_blocks where tenant_id=3 and assessment_id=%s',(aid,)).fetchone():
   assert not db.execute('select 1 from elearning_assessment_attempts where tenant_id=3 and assessment_id=%s',(aid,)).fetchone()
   db.execute('delete from elearning_assessments where tenant_id=3 and id=%s',(aid,))
 for tid in fixture['templates']:
  row=db.execute('select design from elearning_certificate_templates where tenant_id=3 and id=%s',(tid,)).fetchone()
  if row:assert row[0]['name']=='Academy Standard';db.execute('delete from elearning_certificate_templates where tenant_id=3 and id=%s',(tid,))
 if fixture.get("settings"):
  db.execute("select public.save_elearning_settings(3,%s::jsonb)",(json.dumps(fixture["settings"]),))
 if fixture.get('registered_email'):
  email=fixture['registered_email']
  assert email.startswith('academy131-learner-') and email.endswith('@example.com')
  account=db.execute("select id,auth_id,first_name,last_name from users where tenant_id=3 and email=%s",(email,)).fetchone()
  if account:
   assert account[2:]==('Academy131','Learner') and account[0]!=1
   if fixture.get('registered_user'): assert account[0]==fixture['registered_user']
   db.execute('delete from elearning_learners where tenant_id=3 and user_id=%s',(account[0],))
   db.execute('delete from tenant_memberships where tenant_id=3 and user_id=%s and role=\'learner\'',(account[0],))
   db.execute('delete from users where tenant_id=3 and id=%s and email=%s',(account[0],email))
   # This exact local provider fixture has no commercial history or external identity.
   db.execute('delete from auth.users where id=%s and email=%s',(account[1],email))
print("Exact local Academy fixtures removed; original settings/account and unrelated data preserved.")
