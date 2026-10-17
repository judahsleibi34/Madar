"""Native reservation, stock/order and payment races on a disposable database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import os
import threading
import time
import unittest
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from tests.disposable_database_support import connect_disposable_database

DSN=os.getenv('BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN')
MARKERS={'madar-notification-synthetic-rehearsal','madar-hardening-synthetic-148-independent'}


def connect():
    db=connect_disposable_database(DSN,markers=MARKERS)
    db.execute("set statement_timeout='8s'")
    return db


def digest(value):return hashlib.sha256(str(value).encode()).hexdigest()


@unittest.skipUnless(DSN,'Requires marked disposable native business PostgreSQL')
class NativeBusinessIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db=connect();self.addCleanup(self.db.close)
        self.tenant,self.user=self.owner()
        token=uuid4().hex
        self.project=self.db.execute("insert into public.builder_projects(tenant_id,owner_user_id,name,slug,status,published_schema,published_version,last_published_at) values(%s,%s,'Synthetic native',%s,'published',%s,1,now()) returning id",(self.tenant,self.user,'native-'+token,Jsonb({'defaultPageId':'home','pages':[{'id':'home','slug':'/','isDefault':True}]}))).fetchone()[0]
        self.db.execute("insert into public.website_settings(tenant_id,user_id,subdomain,ecommerce_currency) values(%s,%s,%s,'USD')",(self.tenant,self.user,'native-'+token))
        self.area=self.db.execute("select id from public.ecommerce_service_areas where active order by sort_order limit 1").fetchone()[0]
        self.db.execute('insert into public.ecommerce_tenant_service_areas(tenant_id,service_area_id,enabled) values(%s,%s,true)',(self.tenant,self.area))
        self.db.execute('insert into public.ecommerce_delivery_pricing(tenant_id,service_area_id,price) values(%s,%s,7.25) on conflict(tenant_id,service_area_id) do update set price=excluded.price',(self.tenant,self.area))
        self.product=self.product_fixture(quantity=5)
        self.start=datetime.now(timezone.utc)+timedelta(days=1)
        self.end=self.start+timedelta(minutes=30)
        self.block='synthetic-slot'

    def owner(self):
        token=uuid4();tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Synthetic integrity','Fixture') returning tenant_id").fetchone()[0]
        self.db.execute('insert into auth.users(id,email,email_confirmed_at) values(%s,%s,now())',(token,str(token)+'@example.invalid'))
        user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Synthetic','Fixture',%s,%s,'active',true) returning id",(token,str(token)+'@example.invalid',tenant)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(tenant,user,token))
        return tenant,user

    def product_fixture(self,quantity=5,price='10.01'):
        token=uuid4().hex
        return self.db.execute("insert into public.ecommerce_products(tenant_id,sku,slug,status,price,currency,track_inventory,inventory_quantity,allow_backorder) values(%s,%s,%s,'active',%s,'USD',true,%s,false) returning id",(self.tenant,'NATIVE-'+token,'native-'+token,Decimal(price),quantity)).fetchone()[0]

    def race(self,action,count=6):
        barrier=threading.Barrier(count)
        def run(index):
            with connect() as db:
                barrier.wait(timeout=5)
                try:return action(db,index)
                except psycopg.Error as error:return {'error':error.diag.message_primary,'sqlstate':error.sqlstate}
        with ThreadPoolExecutor(max_workers=count) as pool:return list(pool.map(run,range(count)))

    def reservation(self, *,db=None,key=None,request=None,start=None,end=None,tenant=None,project=None,exclusive=True):
        key=key or uuid4().hex
        body={'tenant_id':tenant or self.tenant,'project_id':str(project or self.project),'block_id':self.block,'block_type':'reservationBlock','customer_name':'Synthetic','starts_at':(start or self.start).isoformat(),'ends_at':(end or self.end).isoformat(),'cancellation_token_hash':digest(str(self.tenant)+':cancel:'+key),'cancellation_expires_at':(self.start+timedelta(days=1)).isoformat()}
        return (db or self.db).execute('select public.create_builder_reservation_notified_safe(%s,%s,%s,%s,%s)',(Jsonb(body),digest(key),digest(request or key),exclusive,Jsonb({'event_type':'builder_reservation_created','source_type':'reservationBlock','title':'Synthetic reservation','data':{}}))).fetchone()[0]

    def order(self, *,db=None,key=None,request=None,quantity=1,items=None):
        key=key or uuid4().hex
        body={'tenant_id':self.tenant,'payment_method':'cash_on_delivery','service_area_id':str(self.area),'street':'Synthetic Street','customer_name':'Synthetic customer','email':'synthetic@example.invalid','phone':'0000000000','items':items or [{'product_id':str(self.product),'quantity':quantity}]}
        return (db or self.db).execute('select public.create_ecommerce_order_safe(%s,%s,%s,%s)',(Jsonb(body),digest(key),digest(request or key),digest('confirm:'+key))).fetchone()[0]

    def inventory(self,product=None):return self.db.execute('select inventory_quantity from public.ecommerce_products where id=%s',(product or self.product,)).fetchone()[0]

    def test_reservation_concurrent_capacity_one_has_one_winner(self):
        results=self.race(lambda db,i:self.reservation(db=db,key='request-'+str(i)))
        self.assertEqual(sum('reservation' in r for r in results),1,results)
        self.assertEqual(sum(r.get('error')=='reservation_slot_unavailable' for r in results),5,results)
        self.assertEqual(self.db.execute('select count(*) from public.builder_reservations where tenant_id=%s',(self.tenant,)).fetchone()[0],1)

    def test_reservation_duplicate_retry_is_one_booking_and_event(self):
        results=self.race(lambda db,i:self.reservation(db=db,key='same-request'))
        self.assertTrue(all('reservation' in r for r in results),results)
        self.assertEqual(len({r['reservation']['id'] for r in results}),1)
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.assertEqual(self.db.execute('select count(*) from public.notification_events where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        with self.assertRaisesRegex(psycopg.Error,'idempotency_conflict'):self.reservation(key='same-request',request='different')

    def test_reservation_adjacent_slots_cancel_and_reuse(self):
        a=self.reservation(key='a')['reservation'];self.reservation(start=self.end,end=self.end+timedelta(minutes=30))
        self.db.execute('select public.cancel_builder_reservation_safe(%s,%s)',(a['id'],digest(str(self.tenant)+':cancel:a')))
        self.reservation()
        self.assertEqual(self.db.execute("select count(*) from public.builder_reservations where tenant_id=%s and status in ('new','confirmed')",(self.tenant,)).fetchone()[0],2)

    def test_cancelled_reservation_cannot_reactivate_into_occupied_slot(self):
        old=self.reservation(key='old')['reservation']
        self.db.execute('select public.cancel_builder_reservation_safe(%s,%s)',(old['id'],digest(str(self.tenant)+':cancel:old')))
        self.reservation(key='replacement')
        with self.assertRaisesRegex(psycopg.Error,'reservation_slot_unavailable'):
            self.db.execute("select public.update_builder_reservation_status_notified_safe(%s,%s,'confirmed')",(old['id'],self.tenant))
        self.assertEqual(self.db.execute("select count(*) from public.builder_reservations where tenant_id=%s and status in ('new','confirmed')",(self.tenant,)).fetchone()[0],1)

    def test_reservation_reactivation_and_new_booking_serialize_capacity(self):
        old=self.reservation(key='old')['reservation']
        self.db.execute('select public.cancel_builder_reservation_safe(%s,%s)',(old['id'],digest(str(self.tenant)+':cancel:old')))
        def action(db,index):
            if index==0:
                return {'reactivated':db.execute("select public.update_builder_reservation_status_notified_safe(%s,%s,'confirmed')",(old['id'],self.tenant)).fetchone()[0]}
            return self.reservation(db=db,key='replacement')
        results=self.race(action,2)
        self.assertEqual(sum('error' not in r for r in results),1,results)
        self.assertEqual(sum(r.get('error')=='reservation_slot_unavailable' for r in results),1,results)
        self.assertEqual(self.db.execute("select count(*) from public.builder_reservations where tenant_id=%s and status in ('new','confirmed')",(self.tenant,)).fetchone()[0],1)

    def test_reservation_reactivation_held_transaction_blocks_new_booking(self):
        old=self.reservation(key='held-old')['reservation']
        self.db.execute('select public.cancel_builder_reservation_safe(%s,%s)',(old['id'],digest(str(self.tenant)+':cancel:held-old')))
        with connect() as holder,connect() as waiter:
            holder.execute('begin')
            holder.execute("select public.update_builder_reservation_status_notified_safe(%s,%s,'confirmed')",(old['id'],self.tenant))
            def book():
                try:return self.reservation(db=waiter,key='competing')
                except psycopg.Error as error:return {'error':error.diag.message_primary}
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(book)
                try:
                    deadline=time.monotonic()+3
                    while time.monotonic()<deadline:
                        waiting=self.db.execute("select wait_event_type='Lock' from pg_stat_activity where pid=%s",(waiter.info.backend_pid,)).fetchone()[0]
                        if waiting or future.done():break
                        time.sleep(.01)
                    else:self.fail('concurrent booking neither completed nor waited on lock')
                finally:holder.execute('commit')
                result=future.result(timeout=10)
        self.assertEqual(result.get('error'),'reservation_slot_unavailable',result)
        self.assertEqual(self.db.execute("select count(*) from public.builder_reservations where tenant_id=%s and status in ('new','confirmed')",(self.tenant,)).fetchone()[0],1)

    def test_reservation_reactivation_free_slot_and_nonexclusive_slots_preserved(self):
        old=self.reservation(key='available')['reservation']
        self.db.execute('select public.cancel_builder_reservation_safe(%s,%s)',(old['id'],digest(str(self.tenant)+':cancel:available')))
        updated=self.db.execute("select public.update_builder_reservation_status_notified_safe(%s,%s,'confirmed')",(old['id'],self.tenant)).fetchone()[0]
        self.assertEqual(updated['status'],'confirmed')
        self.block='nonexclusive'
        results=self.race(lambda db,i:self.reservation(db=db,key='nonexclusive-'+str(i),exclusive=False))
        self.assertTrue(all('reservation' in r for r in results),results)
        self.assertEqual(len({r['reservation']['id'] for r in results}),6)

    def test_service_role_direct_status_update_is_denied(self):
        row=self.reservation()['reservation']
        with connect() as db:
            db.execute('set role service_role')
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                db.execute("update public.builder_reservations set status='confirmed' where id=%s",(row['id'],))
            result=db.execute("select public.update_builder_reservation_status_notified_safe(%s,%s,'confirmed')",(row['id'],self.tenant)).fetchone()[0]
            self.assertEqual(result['status'],'confirmed')

    def test_reservation_cross_tenant_project_and_status_denied(self):
        other,_=self.owner()
        with self.assertRaisesRegex(psycopg.Error,'builder_project_not_found'):self.reservation(tenant=other)
        row=self.reservation()['reservation']
        self.assertIsNone(self.db.execute("select public.update_builder_reservation_status_notified_safe(%s,%s,'cancelled')",(row['id'],other)).fetchone()[0])
        self.assertEqual(self.db.execute('select status from public.builder_reservations where id=%s',(row['id'],)).fetchone()[0],'new')

    def test_inventory_concurrent_orders_do_not_oversell(self):
        self.db.execute('update public.ecommerce_products set inventory_quantity=2 where id=%s',(self.product,))
        results=self.race(lambda db,i:self.order(db=db,key='stock-'+str(i)))
        self.assertEqual(sum('order' in r for r in results),2,results)
        self.assertEqual(sum(r.get('error')=='ecommerce_inventory_insufficient' for r in results),4,results)
        self.assertEqual(self.inventory(),0)
        self.assertEqual(self.db.execute("select sum(quantity_delta) from public.ecommerce_inventory_movements where tenant_id=%s",(self.tenant,)).fetchone()[0],-2)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_orders where tenant_id=%s',(self.tenant,)).fetchone()[0],2)

    def test_variant_inventory_concurrency_and_restoration_preserve_parent_stock(self):
        option=self.db.execute("insert into public.ecommerce_product_options(tenant_id,product_id,code,name_translations,normalized_name) values(%s,%s,'size',%s,'size') returning id",(self.tenant,self.product,Jsonb({'en':'Size'}))).fetchone()[0]
        value=self.db.execute("insert into public.ecommerce_product_option_values(tenant_id,product_id,option_id,code,value_translations,normalized_value) values(%s,%s,%s,'small',%s,'small') returning id",(self.tenant,self.product,option,Jsonb({'en':'Small'}))).fetchone()[0]
        variant=self.db.execute("insert into public.ecommerce_product_variants(tenant_id,product_id,sku,price_override,inventory_quantity,option_signature) values(%s,%s,%s,12.34,2,%s) returning id",(self.tenant,self.product,'VARIANT-'+uuid4().hex,digest('small'))).fetchone()[0]
        self.db.execute('insert into public.ecommerce_variant_option_values(tenant_id,product_id,variant_id,option_id,option_value_id) values(%s,%s,%s,%s,%s)',(self.tenant,self.product,variant,option,value))
        results=self.race(lambda db,i:self.order(db=db,key='variant-'+str(i),items=[{'product_id':str(self.product),'variant_id':str(variant),'quantity':1}]))
        orders=[r['order'] for r in results if 'order' in r]
        self.assertEqual(len(orders),2,results)
        self.assertEqual(sum(r.get('error')=='ecommerce_inventory_insufficient' for r in results),4,results)
        self.assertEqual(self.inventory(),5)
        self.assertEqual(self.db.execute('select inventory_quantity from public.ecommerce_product_variants where id=%s',(variant,)).fetchone()[0],0)
        self.assertTrue(all(Decimal(str(order['total']))==Decimal('19.59') for order in orders))
        self.db.execute("select public.transition_ecommerce_order_status_safe(%s,%s,'cancelled',%s,'Synthetic',%s)",(self.tenant,orders[0]['id'],self.user,digest('cancel-variant')))
        self.assertEqual(self.db.execute('select inventory_quantity from public.ecommerce_product_variants where id=%s',(variant,)).fetchone()[0],1)
        self.assertEqual(self.inventory(),5)

    def test_order_cannot_allocate_another_tenants_product(self):
        other,_=self.owner()
        self.db.execute('update public.ecommerce_products set tenant_id=%s where id=%s',(other,self.product))
        with self.assertRaisesRegex(psycopg.Error,'ecommerce_product_unavailable'):self.order()
        self.assertEqual(self.inventory(),5)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_orders where tenant_id=%s',(self.tenant,)).fetchone()[0],0)

    def test_duplicate_order_retries_allocate_once(self):
        results=self.race(lambda db,i:self.order(db=db,key='same-order'))
        self.assertTrue(all('order' in r for r in results),results)
        self.assertEqual(len({r['order']['id'] for r in results}),1)
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.assertEqual(self.inventory(),4)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_inventory_movements where tenant_id=%s',(self.tenant,)).fetchone()[0],1)
        with self.assertRaisesRegex(psycopg.Error,'idempotency_conflict'):self.order(key='same-order',request='changed')

    def test_order_failure_rolls_back_partial_inventory_and_notifications(self):
        second=self.product_fixture(quantity=5)
        first,second=sorted((self.product,second),key=str)
        self.db.execute('update public.ecommerce_products set inventory_quantity=0 where id=%s',(second,))
        with self.assertRaisesRegex(psycopg.Error,'ecommerce_inventory_insufficient'):
            self.order(items=[{'product_id':str(first),'quantity':1},{'product_id':str(second),'quantity':1}])
        self.assertEqual(self.inventory(first),5)
        for table in ('ecommerce_orders','ecommerce_order_items','ecommerce_inventory_movements','notification_events','notification_outbox'):
            self.assertEqual(self.db.execute('select count(*) from public.'+table+' where tenant_id=%s',(self.tenant,)).fetchone()[0],0,table)

    def test_cancelled_order_inventory_restoration_is_idempotent(self):
        order=self.order(quantity=3)['order'];self.assertEqual(self.inventory(),2)
        results=self.race(lambda db,i:db.execute("select public.transition_ecommerce_order_status_safe(%s,%s,'cancelled',%s,'Synthetic',%s)",(self.tenant,order['id'],self.user,digest('cancel-'+str(i)))).fetchone()[0])
        self.assertTrue(all('order' in r for r in results),results)
        self.assertEqual(self.inventory(),5)
        self.assertEqual(self.db.execute("select count(*) from public.ecommerce_inventory_movements where tenant_id=%s and movement_type='order_restoration'",(self.tenant,)).fetchone()[0],1)

    def test_order_price_and_delivery_fee_snapshots_are_decimal_and_immutable(self):
        row=self.order(quantity=3)['order']
        self.assertEqual(Decimal(str(row['subtotal'])),Decimal('30.03'))
        self.assertEqual(Decimal(str(row['total'])),Decimal('37.28'))
        self.db.execute('update public.ecommerce_products set price=99.99 where id=%s',(self.product,))
        self.db.execute('update public.ecommerce_delivery_pricing set price=19.99 where tenant_id=%s',(self.tenant,))
        replay=self.order(key='price-replay')['order']
        saved=self.db.execute('select total,delivery_fee from public.ecommerce_orders where id=%s',(row['id'],)).fetchone()
        self.assertEqual(saved,(Decimal('37.28'),Decimal('7.25')))
        self.assertNotEqual(replay['total'],row['total'])

    def test_cod_collection_concurrent_replay_has_one_effect(self):
        order=self.order()['order']
        results=self.race(lambda db,i:db.execute('select public.collect_ecommerce_cod_payment_safe(%s,%s,%s)',(self.tenant,order['id'],self.user)).fetchone()[0])
        self.assertTrue(all('order' in r for r in results),results)
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.assertEqual(self.db.execute('select payment_status from public.ecommerce_orders where id=%s',(order['id'],)).fetchone()[0],'collected')
        self.assertEqual(self.inventory(),4)

    def checkout(self, *,key=None,db=None):
        db=db or self.db
        if not hasattr(self,'offering'):
            course=self.db.execute("insert into public.elearning_courses(tenant_id,name,status,access_type) values(%s,'Synthetic paid course','published','paid') returning id",(self.tenant,)).fetchone()[0]
            result=self.db.execute('select public.manage_elearning_offering(%s,%s,null,1,%s)',(self.tenant,self.user,Jsonb({'name':'Synthetic paid','description':'','status':'active','billing_type':'one_time','amount':'20.00','currency':'USD','access_scope':'single_course','course_ids':[str(course)]}))).fetchone()[0]
            self.offering=result['saved_plan_id']
        return db.execute("select public.create_commerce_learning_checkout(%s,%s,%s,null,%s,'local_test')",(self.tenant,self.user,self.offering,key or uuid4())).fetchone()[0]['checkout']

    def payment(self,ch, *,db=None,event=None,sequence=1,state='paid',amount=None,currency='USD',transaction=None):
        return (db or self.db).execute('select public.apply_commerce_payment_event(%s,%s,%s,%s,%s,%s,%s,%s,%s,null,false)',(self.tenant,ch['id'],'local_test',event or str(uuid4()),transaction or 'synthetic:'+ch['id'],sequence,state,Decimal(str(amount if amount is not None else ch['terms']['amount'])),currency)).fetchone()[0]

    def test_checkout_and_payment_concurrent_replay_do_not_duplicate_effects(self):
        self.checkout() # Build one offering before concurrent use.
        key=uuid4()
        results=self.race(lambda db,i:self.checkout(key=key,db=db))
        self.assertTrue(all('id' in r for r in results),results)
        self.assertEqual(len({r['id'] for r in results}),1)
        ch=results[0];event=str(uuid4())
        paid=self.race(lambda db,i:self.payment(ch,db=db,event=event))
        self.assertTrue(all('checkout_id' in r for r in paid),paid)
        self.assertEqual(sum(bool(r.get('duplicate')) for r in paid),5)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_payment_events where checkout_id=%s',(ch['id'],)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0],1)

    def test_payment_event_tampering_and_stale_events_do_not_regress_authority(self):
        ch=self.checkout();event=str(uuid4());self.payment(ch,event=event,sequence=2)
        for change in ({'state':'refunded'},{'amount':'20.01'},{'currency':'EUR'},{'transaction':'different'}):
            with self.assertRaisesRegex(psycopg.Error,'commerce_(event_conflict|payment_mismatch)'):self.payment(ch,event=event,sequence=2,**change)
        stale=self.payment(ch,state='failed',sequence=1)
        self.assertTrue(stale['stale'])
        self.assertEqual(self.db.execute('select state,event_sequence from public.ecommerce_checkouts where id=%s',(ch['id'],)).fetchone(),('paid',2))
        self.assertEqual(self.db.execute('select status from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0],'active')

    def test_payment_refund_replay_and_late_paid_event_cannot_resurrect_access(self):
        ch=self.checkout();self.payment(ch)
        event=str(uuid4())
        results=self.race(lambda db,i:self.payment(ch,db=db,state='refunded',sequence=2,event=event))
        self.assertTrue(all('checkout_id' in r for r in results),results)
        self.assertEqual(self.db.execute('select status from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0],'revoked')
        with self.assertRaisesRegex(psycopg.Error,'commerce_payment_reversed'):self.payment(ch,sequence=3)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_payment_events where checkout_id=%s',(ch['id'],)).fetchone()[0],2)

    def test_payment_refund_racing_late_paid_event_leaves_revoked_authority(self):
        ch=self.checkout();self.payment(ch)
        results=self.race(lambda db,i:self.payment(ch,db=db,state='refunded' if i==0 else 'paid',sequence=3 if i==0 else 2),2)
        self.assertTrue(any(r.get('state')=='refunded' for r in results),results)
        self.assertTrue(all('checkout_id' in r or r.get('error')=='commerce_payment_reversed' for r in results),results)
        self.assertEqual(self.db.execute('select state,event_sequence from public.ecommerce_checkouts where id=%s',(ch['id'],)).fetchone(),('refunded',3))
        self.assertEqual(self.db.execute('select status from public.ecommerce_entitlements where checkout_id=%s',(ch['id'],)).fetchone()[0],'revoked')

    def test_provider_transaction_cannot_credit_two_checkouts(self):
        first=self.checkout();second=self.checkout();transaction='unique-external:'+str(uuid4())
        self.payment(first,transaction=transaction)
        with self.assertRaises(psycopg.errors.UniqueViolation):self.payment(second,transaction=transaction)
        self.assertEqual(self.db.execute('select state from public.ecommerce_checkouts where id=%s',(second['id'],)).fetchone()[0],'pending')
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_entitlements where checkout_id=%s',(second['id'],)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_payment_events where transaction_id=%s',(transaction,)).fetchone()[0],1)
