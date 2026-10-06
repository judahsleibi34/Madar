"""Remove exact local browser fixture IDs only; never operate on a hosted DB."""
import json
from pathlib import Path
from dotenv import dotenv_values
from urllib.parse import urlsplit
import psycopg
root=Path(__file__).resolve().parents[1]
fixture=json.loads(Path('/tmp/madar-commerce-browser-fixtures.json').read_text())
config=dotenv_values(root/'.env.database.local');url=urlsplit(config['SUPABASE_DB_URL'])
assert url.hostname in ('localhost','127.0.0.1','::1') and url.port==54322
assert fixture['tenant_id']==3 and len(fixture['courses'])<=6 and len(fixture['plans'])<=4
with psycopg.connect(config['SUPABASE_DB_URL']) as db:
 assert db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]==129
 db.execute('select pg_advisory_xact_lock(125,%s)',(fixture['tenant_id'],))
 rows=db.execute('select id,order_id,offering_id from public.ecommerce_checkouts where tenant_id=%s and offering_id=any(%s::uuid[])',(fixture['tenant_id'],fixture['plans'])).fetchall()
 assert all(str(row[0]) in fixture['checkouts'] for row in rows)
 for cid,oid,plan in rows:
  db.execute('delete from public.ecommerce_payment_events where tenant_id=%s and checkout_id=%s',(fixture['tenant_id'],cid))
  db.execute('delete from public.ecommerce_entitlements where tenant_id=%s and checkout_id=%s',(fixture['tenant_id'],cid))
  db.execute('delete from public.ecommerce_checkouts where tenant_id=%s and id=%s',(fixture['tenant_id'],cid))
  db.execute('delete from public.ecommerce_order_status_history where tenant_id=%s and order_id=%s',(fixture['tenant_id'],oid))
  db.execute('delete from public.ecommerce_orders where tenant_id=%s and id=%s',(fixture['tenant_id'],oid))
 for pid in fixture['plans']:
  product=db.execute('select product_id from public.ecommerce_offerings where tenant_id=%s and id=%s',(fixture['tenant_id'],pid)).fetchone()
  if product:
   assert db.execute('select count(*) from public.ecommerce_checkouts where offering_id=%s',(pid,)).fetchone()[0]==0
   db.execute('delete from public.ecommerce_offerings where tenant_id=%s and id=%s',(fixture['tenant_id'],pid))
   db.execute('delete from public.ecommerce_products where tenant_id=%s and id=%s',(fixture['tenant_id'],product[0]))
 for cid in fixture['courses']:
  course=db.execute('select name,description,revision,structure_revision from public.elearning_courses where tenant_id=%s and id=%s',(fixture['tenant_id'],cid)).fetchone()
  if course:
   assert course[1]=='Local commerce verification'
   db.execute('select public.delete_elearning_course(%s,%s,%s,%s,%s,%s,true)',(fixture['tenant_id'],cid,fixture.get('user_id',1),course[2],course[3],course[0]))
 for gid in fixture['groups']:
  group=db.execute('select name from public.elearning_groups where tenant_id=%s and id=%s',(fixture['tenant_id'],gid)).fetchone()
  if group:
   assert group[0].startswith('Commerce Verification ')
   assert db.execute('select count(*) from public.elearning_group_courses where group_id=%s',(gid,)).fetchone()[0]==0
   db.execute('delete from public.elearning_groups where tenant_id=%s and id=%s',(fixture['tenant_id'],gid))
 print('Removed only exact local verification courses, offerings/products, checkouts/orders, payment events, entitlements and groups. Existing users and learning history retained. Schema 129.')
