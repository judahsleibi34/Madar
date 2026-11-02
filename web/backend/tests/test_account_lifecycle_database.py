"""Candidate167 real HTTP/SQL lifecycle tests; admission remains disabled."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
from postgrest.exceptions import APIError
from supabase import create_client, ClientOptions
from tests.disposable_database_support import connect_disposable_database
from tests import test_schema166_deletion_compatibility_database as fixtures
from tests.account_lifecycle_provider_fixture import ProviderFixture


@unittest.skipUnless(os.getenv('DELETION166_REST_URL'), 'Requires disposable candidate167 harness')
class AccountLifecycleDatabaseTests(unittest.TestCase):
    add_user=fixtures.Schema166DeletionCompatibilityTests.add_user
    dataset=fixtures.Schema166DeletionCompatibilityTests.dataset
    rpc=fixtures.Schema166DeletionCompatibilityTests.rpc

    def setUp(self):
        self.db=connect_disposable_database(os.environ['DELETION_FENCING_SYNTHETIC_DATABASE_DSN'],markers={'madar-notification-synthetic-rehearsal'})
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],167)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'DATA_UPLOAD_DIR':str(self.root/'uploads'),'PRIVATE_CHARTS_DIR':str(self.root/'charts'),'PUBLIC_UPLOADS_DIR':str(self.root/'builder-files')})
        self.env.start();self.addCleanup(self.env.stop)
        self.provider=ProviderFixture(self.root/'provider');self.addCleanup(self.provider.close)
        self.client=create_client(self.provider.url,os.environ['DELETION166_SERVICE_JWT'],options=ClientOptions(auto_refresh_token=False,persist_session=False))
        self.database_client=patch('database.service_supabase',self.client);self.database_client.start();self.addCleanup(self.database_client.stop)
        self.tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Lifecycle167','Fixture') returning tenant_id").fetchone()[0]
        self.user=self.add_user('member');self.owner=self.add_user('owner');self.admin=self.add_user('member')
        self.db.execute("update public.users set user_type='admin' where id=%s",(self.admin,))
        self.project=str(uuid4())
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Lifecycle167',%s,'draft','{}')",(self.project,self.tenant,self.user,self.project))
        from services import account_erasure_service
        self.service=account_erasure_service
        self.auth_id=str(self.db.execute('select auth_id from public.users where id=%s',(self.user,)).fetchone()[0])

    def enroll(self,action='deactivate'):
        return self.service.enroll_authorized(user_id=self.user,actor_id=self.user,action=action,client=self.client)

    def row(self,request):
        value=self.db.execute('select to_jsonb(h) from public.account_lifecycles167 h where id=%s',(request['id'],)).fetchone()
        return value[0] if value else None

    def claim(self):
        return self.rpc('claim_account_erasure167',{'p_owner':'disposable167','p_limit':5,'p_lease_seconds':120})

    def test_distinct_actions_duplicate_and_escalation(self):
        row=self.enroll();again=self.enroll()
        self.assertEqual(row['id'],again['id']);self.assertEqual(row['recovery_deadline'],again['recovery_deadline'])
        self.assertEqual(self.db.execute('select extract(epoch from recovery_deadline-requested_at) from public.account_lifecycles167 where id=%s',(row['id'],)).fetchone()[0],7776000)
        self.assertEqual(self.claim(),[])
        deleted=self.enroll('delete');self.assertEqual(deleted['id'],row['id']);self.assertIsNone(deleted['recovery_deadline'])
        self.assertEqual(deleted['action'],'delete');self.assertTrue(self.claim())
        with self.assertRaises(APIError):self.enroll('deactivate')

    def test_day0_session_revocation_reactivation_and_public_admission(self):
        sid=str(uuid4());self.db.execute('insert into auth.sessions(id,user_id) values(%s,%s)',(sid,self.auth_id))
        self.db.execute('insert into auth.refresh_tokens(token,user_id,session_id) values(%s,%s,%s)',(str(uuid4()),self.auth_id,sid))
        self.assertTrue(self.rpc('account_session_allowed167',{'p_auth_id':self.auth_id,'p_session_id':sid}))
        row=self.enroll()
        self.assertEqual(self.db.execute('select count(*) from auth.sessions where user_id=%s',(self.auth_id,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from auth.refresh_tokens where user_id=%s',(self.auth_id,)).fetchone()[0],0)
        self.assertFalse(self.rpc('account_session_allowed167',{'p_auth_id':self.auth_id,'p_session_id':sid}))
        result=self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        self.assertEqual(result['state'],'reactivated');self.assertEqual(self.claim(),[])
        self.assertFalse(self.rpc('account_session_allowed167',{'p_auth_id':self.auth_id,'p_session_id':sid}))
        self.assertEqual(self.db.execute('select account_status from public.users where id=%s',(self.user,)).fetchone()[0],'active')
        with self.assertRaises(HTTPException) as denied:self.service.request_action(user_id=self.user,actor_id=self.user,action='delete',client=self.client)
        self.assertEqual(denied.exception.status_code,503)

    def test_immediate_local_immutable_erasure(self):
        content,digest,key,storage,dataset,version=self.dataset()
        path=self.root/'uploads'/key;path.parent.mkdir(parents=True);path.write_bytes(content)
        other=self.root/'uploads'/f'tenant_{self.tenant}'/f'user_{self.owner}'/'keep.csv';other.parent.mkdir(parents=True);other.write_bytes(b'private independent')
        row=self.enroll('delete');self.assertIsNone(row['recovery_deadline'])
        claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result)
        self.assertFalse(path.exists());self.assertEqual(other.read_bytes(),b'private independent')
        self.assertEqual(self.db.execute('select count(*) from public.data_dataset_versions where id=%s',(version,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.storage_objects where id=%s',(storage,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.users where id=%s',(self.user,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from auth.users where id=%s',(self.auth_id,)).fetchone()[0],0)

    def test_day90_boundary_and_closed_recovery(self):
        row=self.enroll()
        self.db.execute("with t as materialized(select clock_timestamp() as now) update public.account_lifecycles167 set requested_at=t.now-interval '90 days',deactivated_at=t.now-interval '90 days',recovery_deadline=t.now,eligible_at=t.now from t where id=%s",(row['id'],))
        with self.assertRaises(APIError):self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result)

    def test_shared_project_blocks_without_destroying_content(self):
        self.db.execute('update public.builder_projects set owner_user_id=%s where id=%s',(self.owner,self.project))
        content,_digest,key,*_=self.dataset();path=self.root/'uploads'/key;path.parent.mkdir(parents=True);path.write_bytes(content)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released']);self.assertEqual(path.read_bytes(),content)
        self.assertEqual(self.db.execute('select owner_user_id from public.builder_projects where id=%s',(self.project,)).fetchone()[0],self.owner)

    def seed_provider(self):
        import hashlib
        content=b'group,amount\na,1\n';digest=hashlib.sha256(content).hexdigest()
        key=f'tenant_{self.tenant}/dataset/{uuid4()}/{digest}.csv'
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256,storage_backend,storage_bucket,provider_object_key,verified_size_bytes,verified_sha256,integrity_verified_at) values(%s,%s,'dataset',%s,%s,%s,'supabase_private','madar-data-immutable',%s,%s,%s,now())",(self.tenant,self.user,f'tenant_{self.tenant}/user_{self.user}/provider.csv',len(content),digest,key,len(content),digest))
        return self.provider.put_object('madar-data-immutable',key,content,self.auth_id)

    def seed_commerce(self, provider='local_test'):
        """Create one customer-linked mixed ledger and one unrelated order."""
        from psycopg.types.json import Jsonb
        product=str(self.db.execute("insert into public.ecommerce_products(tenant_id,sku,slug,translations,status,price,currency,inventory_quantity,created_by) values(%s,%s,%s,%s,'active',20,'USD',9,%s) returning id",(self.tenant,'SKU-'+uuid4().hex[:12],uuid4().hex,Jsonb({'en':{'name':'Independent catalog product'}}),self.owner)).fetchone()[0])
        order=str(uuid4())
        self.db.execute("""insert into public.ecommerce_orders(id,tenant_id,customer_id,order_number,status,payment_status,payment_method,currency,subtotal,total,
          customer_name,customer_email,customer_phone,address_line_1,address_line_2,city,postal_code,country,notes,street,building,floor_apartment,address_description,delivery_notes,
          confirmation_token_hash,idempotency_key_hash,request_hash,payment_collected_by)
          values(%s,%s,%s,%s,'delivered','collected','cash_on_delivery','USD',20,20,'Private Customer',%s,'+970000000','Private street','Private unit','Private city','00000','PS','Private note','Private street','Private building','Private floor','Private directions','Private delivery',%s,%s,%s,%s)""",
          (order,self.tenant,self.user,'ORDER-'+uuid4().hex[:12],self.db.execute('select email from public.users where id=%s',(self.user,)).fetchone()[0],'a'*64,'b'*64,'c'*64,self.owner))
        item=str(self.db.execute("""insert into public.ecommerce_order_items(tenant_id,order_id,product_id,sku,product_name,product_slug,product_snapshot,quantity,unit_price,list_unit_price,line_total,inventory_allocated_quantity)
          values(%s,%s,%s,%s,'Independent catalog product','catalog-product',%s,1,20,20,20,1) returning id""",
          (self.tenant,order,product,'SKU-SNAPSHOT',Jsonb({'images':[],'merchant_field':'preserve'}))).fetchone()[0])
        history=str(self.db.execute("insert into public.ecommerce_order_status_history(tenant_id,order_id,previous_status,new_status,actor_id,note,idempotency_key_hash) values(%s,%s,'confirmed','delivered',%s,'Merchant delivery record',%s) returning id",(self.tenant,order,self.owner,'d'*64)).fetchone()[0])
        movement=str(self.db.execute("insert into public.ecommerce_inventory_movements(tenant_id,product_id,order_id,order_item_id,movement_type,quantity_delta,idempotency_key_hash,reason) values(%s,%s,%s,%s,'order_allocation',-1,%s,'Merchant inventory record') returning id",(self.tenant,product,order,item,'e'*64)).fetchone()[0])
        account=str(self.db.execute("insert into public.ecommerce_loyalty_accounts(tenant_id,customer_id,current_balance,lifetime_earned) values(%s,%s,10,10) returning id",(self.tenant,self.user)).fetchone()[0])
        rule=str(self.db.execute("insert into public.ecommerce_loyalty_rules(tenant_id,rule_key,version,enabled,is_current,currency,earning_rate_basis_points,threshold_points,reward_product_id,reward_discount_basis_points,validity_mode,created_by) values(%s,%s,1,true,true,'USD',500,10,%s,1000,'lifetime',%s) returning id",(self.tenant,str(uuid4()),product,self.owner)).fetchone()[0])
        entitlement=str(self.db.execute("insert into public.ecommerce_loyalty_entitlements(tenant_id,account_id,customer_id,rule_id,rule_key,rule_version,reward_product_id,threshold_points,reward_discount_basis_points,validity_mode,status) select %s,%s,%s,id,rule_key,version,reward_product_id,threshold_points,reward_discount_basis_points,validity_mode,'active' from public.ecommerce_loyalty_rules where id=%s returning id",(self.tenant,account,self.user,rule)).fetchone()[0])
        transaction=str(self.db.execute("insert into public.ecommerce_loyalty_transactions(tenant_id,account_id,customer_id,transaction_type,points_delta,balance_after,order_id,rule_id,rule_version,entitlement_id,idempotency_key,metadata) values(%s,%s,%s,'earn',10,10,%s,%s,1,%s,%s,%s) returning id",(self.tenant,account,self.user,order,rule,entitlement,'commerce-'+uuid4().hex,Jsonb({'merchant_reward':'preserve only until customer erasure'}))).fetchone()[0])
        self.db.execute('update public.ecommerce_order_items set loyalty_entitlement_id=%s where id=%s',(entitlement,item))
        offering=str(self.db.execute("insert into public.ecommerce_offerings(tenant_id,product_id,billing_type,resource_type,access_scope) values(%s,%s,'one_time','elearning_course','all_courses') returning id",(self.tenant,product)).fetchone()[0])
        checkout=str(self.db.execute("insert into public.ecommerce_checkouts(tenant_id,user_id,offering_id,order_id,provider,provider_transaction_id,idempotency_key,terms,state,event_sequence) values(%s,%s,%s,%s,%s,%s,%s,%s,'paid',1) returning id",(self.tenant,self.user,offering,order,provider,'txn-'+uuid4().hex,str(uuid4()),Jsonb({'name':'Catalog purchase','amount':20,'currency':'USD','billing_type':'one_time','access_scope':'all_courses','course_ids':[]}))).fetchone()[0])
        payment_event='event-'+uuid4().hex
        self.db.execute("insert into public.ecommerce_payment_events(provider,event_id,tenant_id,checkout_id,transaction_id,sequence,state,amount,currency) values(%s,%s,%s,%s,%s,1,'paid',20,'USD')",(provider,payment_event,self.tenant,checkout,'txn-event-'+uuid4().hex))
        access=str(self.db.execute("insert into public.ecommerce_entitlements(tenant_id,user_id,checkout_id,resource_type,terms,status) values(%s,%s,%s,'elearning_course',%s,'active') returning id",(self.tenant,self.user,checkout,Jsonb({'name':'Private customer access'}))).fetchone()[0])
        other_order=str(uuid4());other_email=self.db.execute('select email from public.users where id=%s',(self.owner,)).fetchone()[0]
        self.db.execute("insert into public.ecommerce_orders(id,tenant_id,customer_id,order_number,status,payment_status,payment_method,currency,subtotal,total,customer_name,customer_email,customer_phone,address_line_1,city,country) values(%s,%s,%s,%s,'pending','unpaid','cash_on_delivery','USD',20,20,'Independent customer',%s,'keep-phone','Keep address','Keep city','PS')",(other_order,self.tenant,self.owner,'KEEP-'+uuid4().hex[:12],other_email))
        return {'product':product,'order':order,'item':item,'history':history,'movement':movement,'account':account,'rule':rule,'entitlement':entitlement,'transaction':transaction,'offering':offering,'checkout':checkout,'payment_event':payment_event,'access':access,'other_order':other_order}

    def test_commerce_customer_erasure_preserves_merchant_ledger_and_unrelated_order(self):
        commerce=self.seed_commerce()
        with self.assertRaisesRegex(Exception,'append_only'):
            self.db.execute('delete from public.ecommerce_loyalty_transactions where id=%s',(commerce['transaction'],))
        merchant_before=self.db.execute('select total,status,payment_status,delivery_fee from public.ecommerce_orders where id=%s',(commerce['order'],)).fetchone()
        other_before=self.db.execute('select to_jsonb(o) from public.ecommerce_orders o where id=%s',(commerce['other_order'],)).fetchone()[0]
        product_before=self.db.execute('select to_jsonb(p) from public.ecommerce_products p where id=%s',(commerce['product'],)).fetchone()[0]
        row=self.enroll('delete');self.run_worker();self.assertIsNone(self.row(row))
        erased=self.db.execute("select customer_id,customer_name,customer_email,customer_phone,address_line_1,city,notes,confirmation_token_hash,idempotency_key_hash,request_hash,total,status,payment_status,delivery_fee from public.ecommerce_orders where id=%s",(commerce['order'],)).fetchone()
        self.assertEqual(erased[:10],(None,'Erased customer','','','','','',None,None,None))
        self.assertEqual(erased[10:],merchant_before)
        self.assertEqual(self.db.execute('select user_id,state,provider_transaction_id from public.ecommerce_checkouts where id=%s',(commerce['checkout'],)).fetchone()[0],None)
        self.assertEqual(self.db.execute('select count(*) from public.ecommerce_payment_events where event_id=%s',(commerce['payment_event'],)).fetchone()[0],1)
        for table,key in (('ecommerce_entitlements',commerce['access']),('ecommerce_loyalty_transactions',commerce['transaction']),('ecommerce_loyalty_entitlements',commerce['entitlement']),('ecommerce_loyalty_accounts',commerce['account'])):
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where id=%s',(key,)).fetchone()[0],0,table)
        for table,key in (('ecommerce_order_items',commerce['item']),('ecommerce_order_status_history',commerce['history']),('ecommerce_inventory_movements',commerce['movement'])):
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where id=%s',(key,)).fetchone()[0],1,table)
        self.assertIsNone(self.db.execute('select loyalty_entitlement_id from public.ecommerce_order_items where id=%s',(commerce['item'],)).fetchone()[0])
        self.assertEqual(self.db.execute('select to_jsonb(o) from public.ecommerce_orders o where id=%s',(commerce['other_order'],)).fetchone()[0],other_before)
        product_after=self.db.execute('select to_jsonb(p) from public.ecommerce_products p where id=%s',(commerce['product'],)).fetchone()[0]
        product_before['updated_at']=product_after['updated_at']
        self.assertEqual(product_after,product_before)

    def test_live_commerce_provider_refuses_before_merchant_or_customer_change(self):
        commerce=self.seed_commerce(provider='stripe')
        before=self.db.execute('select to_jsonb(o) from public.ecommerce_orders o where id=%s',(commerce['order'],)).fetchone()[0]
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error_code'],'account_commerce_provider_erasure_required')
        self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select to_jsonb(o) from public.ecommerce_orders o where id=%s',(commerce['order'],)).fetchone()[0],before)
        self.assertEqual(self.db.execute('select user_id from public.ecommerce_checkouts where id=%s',(commerce['checkout'],)).fetchone()[0],self.user)

    def test_deactivation_fences_customer_order_and_payment_work_until_reactivation(self):
        row=self.enroll()
        with self.assertRaisesRegex(Exception,'account_processing_frozen'):
            self.db.execute("insert into public.ecommerce_orders(tenant_id,customer_id,order_number,status,payment_status,payment_method,currency,subtotal,total,customer_name,customer_email,customer_phone,address_line_1,city,country) values(%s,%s,%s,'pending','unpaid','cash_on_delivery','USD',1,1,'Frozen','frozen@example.invalid','x','x','x','PS')",(self.tenant,self.user,'FROZEN-'+uuid4().hex[:12]))
        self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        inserted=self.db.execute("insert into public.ecommerce_orders(tenant_id,customer_id,order_number,status,payment_status,payment_method,currency,subtotal,total,customer_name,customer_email,customer_phone,address_line_1,city,country) values(%s,%s,%s,'pending','unpaid','cash_on_delivery','USD',1,1,'Active','active@example.invalid','x','x','x','PS') returning id",(self.tenant,self.user,'ACTIVE-'+uuid4().hex[:12])).fetchone()[0]
        self.assertIsNotNone(inserted)

    def test_guest_order_email_similarity_refuses_without_claiming_merchant_record(self):
        email=self.db.execute('select email from public.users where id=%s',(self.user,)).fetchone()[0]
        order=str(self.db.execute("insert into public.ecommerce_orders(tenant_id,order_number,status,payment_status,payment_method,currency,subtotal,total,customer_name,customer_email,customer_phone,address_line_1,city,country) values(%s,%s,'pending','unpaid','cash_on_delivery','USD',1,1,'Ambiguous guest',%s,'private','private','private','PS') returning id",(self.tenant,'GUEST-'+uuid4().hex[:12],email)).fetchone()[0])
        before=self.db.execute('select to_jsonb(o) from public.ecommerce_orders o where id=%s',(order,)).fetchone()[0]
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error_code'],'account_commerce_identity_unresolved')
        self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select to_jsonb(o) from public.ecommerce_orders o where id=%s',(order,)).fetchone()[0],before)

    def test_commerce_catalog_asset_is_shared_and_preserved_on_refusal(self):
        import hashlib
        from psycopg.types.json import Jsonb
        filename=uuid4().hex+'.png';key=f'tenant_{self.tenant}/builder_assets/{filename}';url='/uploads/'+key;content=b'independent merchant catalog bytes';digest=hashlib.sha256(content).hexdigest()
        asset=str(self.db.execute("insert into public.builder_assets(tenant_id,owner_user_id,ownership_status,uploader_user_id,storage_backend,storage_bucket,provider_object_key,storage_key,managed_filename,mime_type,size_bytes,sha256,status) values(%s,%s,'verified',%s,'supabase_builder_private','builder-assets',%s,%s,%s,'image/png',%s,%s,'active') returning id",(self.tenant,self.user,self.user,key,key,filename,len(content),digest)).fetchone()[0])
        product=str(self.db.execute("insert into public.ecommerce_products(tenant_id,sku,slug,translations,status,price,currency,images,created_by) values(%s,%s,%s,%s,'active',1,'USD',%s,%s) returning id",(self.tenant,'MEDIA-'+uuid4().hex[:12],uuid4().hex,Jsonb({'en':{'name':'Merchant media'}}),Jsonb([url]),self.owner)).fetchone()[0])
        provider=self.provider.put_object('builder-assets',key,content,self.auth_id)
        cache=self.root/'builder-files'/key;cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(content)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error_code'],'shared_commerce_ownership')
        self.assertFalse(self.row(row)['database_released']);self.assertEqual(provider.read_bytes(),content);self.assertEqual(cache.read_bytes(),content)
        self.assertEqual(self.db.execute('select images from public.ecommerce_products where id=%s',(product,)).fetchone()[0],[url])
        self.assertEqual(self.db.execute('select owner_user_id from public.builder_assets where id=%s',(asset,)).fetchone()[0],self.user)

    def test_provider_lost_ack_is_independently_verified(self):
        path=self.seed_provider();self.provider.fail_storage='after';self.provider.fail_auth='after'
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result);self.assertFalse(path.exists())
        self.assertEqual(self.provider.storage_removes,1);self.assertEqual(self.provider.auth_removes,1)

    def test_uncertain_provider_failure_requires_independent_resolution(self):
        path=self.seed_provider();self.provider.fail_storage='before'
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertTrue(path.exists())
        self.assertEqual(self.provider.auth_removes,0)
        # An operator independently resolves the exact provider object. Resume
        # preserves the durable intent; the worker must observe absence, not
        # repeat an uncertain destructive operation.
        path.unlink()
        self.db.execute('delete from storage.objects where owner_id=%s',(self.auth_id,))
        self.rpc('resume_account_erasure167',{'p_request_id':row['id'],'p_actor_id':self.admin})
        claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result);self.assertEqual(self.provider.storage_removes,1)

    def seed_reports(self):
        from services import bi_reporting_service as reports,bi_report_export_service as exports
        from tests.test_bi_report_export_service import immutable_report
        paths=[]
        for archived in (False,True):
            report_id=str(uuid4());artifact=reports._write_csv_artifact(run={'id':report_id,'tenant_id':self.tenant},results=[])
            paths.append(self.root/'charts'/artifact['storage_key'])
            snapshot=immutable_report();snapshot['id']=report_id;snapshot['creator_user_id']=self.user
            for fmt in ('pdf','xlsx'):
                path,_,_=exports.write_export(report=snapshot,tenant_id=self.tenant,root=self.root/'charts',export_format=fmt,language='en');paths.append(path)
            self.db.execute("insert into public.bi_report_runs(id,tenant_id,project_id,creator_user_id,dashboard_revision,trigger_type,deduplication_key,status,definition_snapshot,version_vector,result_snapshot,artifact_storage_key,artifact_filename,artifact_content_type,artifact_size_bytes,artifact_sha256,completed_at,archived_at) values(%s,%s,%s,%s,1,'manual',%s,'completed','{}','[]','{}',%s,%s,%s,%s,%s,now(),case when %s then now() end)",(report_id,self.tenant,self.project,self.user,report_id,artifact['storage_key'],artifact['filename'],artifact['content_type'],artifact['size_bytes'],artifact['sha256'],archived))
        return paths

    def worker_environment(self):
        return {**os.environ,'SUPABASE_URL':self.provider.url,'SUPABASE_SERVICE_KEY':os.environ['DELETION166_SERVICE_JWT'],'SUPABASE_ANON_KEY':os.environ['DELETION166_ANON_JWT'],'MADAR_ENV_FILE':'/dev/null','MADAR_ENV_OVERRIDE':'false','ACCOUNT_LIFECYCLE_WORKER_ENABLED':'true','ACCOUNT_LIFECYCLE_WORKER_ONCE':'true'}

    def run_worker(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'-m','workers.account_lifecycle_worker'],env=self.worker_environment(),capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])

    def test_real_worker_process_cleans_active_archived_reports_and_exports(self):
        import subprocess,sys
        paths=self.seed_reports()
        self.assertTrue(all(p.is_file() for p in paths));row=self.enroll('delete')
        env={**os.environ,'SUPABASE_URL':self.provider.url,'SUPABASE_SERVICE_KEY':os.environ['DELETION166_SERVICE_JWT'],'SUPABASE_ANON_KEY':os.environ['DELETION166_ANON_JWT'],'MADAR_ENV_FILE':'/dev/null','MADAR_ENV_OVERRIDE':'false','ACCOUNT_LIFECYCLE_WORKER_ENABLED':'true','ACCOUNT_LIFECYCLE_WORKER_ONCE':'true'}
        completed=subprocess.run([sys.executable,'-m','workers.account_lifecycle_worker'],env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(completed.returncode,0,completed.stderr[-2000:])
        self.assertIsNone(self.row(row));self.assertFalse(any(p.exists() for p in paths))

    def test_symlink_refusal_preserves_database_and_other_owner(self):
        content,_digest,key,*_=self.dataset();path=self.root/'uploads'/key;path.parent.mkdir(parents=True)
        independent=self.root/'independent';independent.write_bytes(content);path.symlink_to(independent)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released']);self.assertEqual(independent.read_bytes(),content)

    def test_stale_lease_cannot_transition_new_owner(self):
        row=self.enroll('delete');old=next(c for c in self.claim() if c['id']==row['id'])
        self.db.execute("update public.account_lifecycles167 set lease_until=clock_timestamp()-interval '1 second' where id=%s",(row['id'],))
        new=next(c for c in self.claim() if c['id']==row['id'])
        self.assertGreater(new['generation'],old['generation'])
        with self.assertRaises(APIError):self.service._transition(self.client,old,'renew')
        self.assertEqual(self.service.process_claim(new,client=self.client)['state'],'completed')

    def test_revoked_jwt_rls_remains_denied_after_reactivation(self):
        import httpx
        email=self.db.execute('select email from public.users where id=%s',(self.user,)).fetchone()[0]
        login=httpx.post(self.provider.url+'/auth/v1/token?grant_type=password',json={'email':email,'password':'fixture-password'},timeout=10)
        self.assertEqual(login.status_code,200);token=login.json()['access_token']
        url=os.environ['DELETION166_REST_URL']+'/users'
        def visible(jwt):
            response=httpx.get(url,params={'id':f'eq.{self.user}','select':'id'},headers={'Authorization':'Bearer '+jwt},timeout=10)
            self.assertEqual(response.status_code,200,response.text);return response.json()
        self.assertEqual(visible(token),[{'id':self.user}])
        row=self.enroll();self.assertEqual(visible(token),[])
        self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        self.assertEqual(visible(token),[])
        fresh=httpx.post(self.provider.url+'/auth/v1/token?grant_type=password',json={'email':email,'password':'fixture-password'},timeout=10)
        self.assertEqual(fresh.status_code,200);self.assertEqual(visible(fresh.json()['access_token']),[{'id':self.user}])
        denied=httpx.post(os.environ['DELETION166_REST_URL']+'/rpc/claim_account_erasure167',headers={'Authorization':'Bearer '+fresh.json()['access_token']},json={'p_owner':'unprivileged','p_limit':1,'p_lease_seconds':120},timeout=10)
        self.assertIn(denied.status_code,(401,403,404))

    def test_unregistered_provider_object_blocks_before_metadata_release(self):
        path=self.provider.put_object('private-unsupported','unknown/object',b'private',self.auth_id)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released']);self.assertTrue(path.is_file())

    def test_real_parquet_is_preserved_during_recovery_and_erased_with_source(self):
        from services import parquet_cache_service as cache
        content,digest,key,storage,dataset,version=self.dataset();source=self.root/'uploads'/key;source.parent.mkdir(parents=True);source.write_bytes(content)
        with patch.object(cache,'MIN_SOURCE_BYTES',1):
            artifact=cache.get_or_create(source_path=str(source),tenant_id=self.tenant,user_id=self.user,project_id=self.project,dataset_id=str(dataset),version_id=str(version),source_hash=digest,source_size=len(content),declared_rows=2)
        self.assertIsNotNone(artifact);path=artifact.path
        row=self.enroll();self.assertTrue(path.exists());self.assertTrue(source.exists());self.assertEqual(self.claim(),[])
        self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed');self.assertFalse(path.exists());self.assertFalse(source.exists())

    def test_crash_during_durable_file_intent_recovers_in_new_worker_process(self):
        import subprocess,sys,time,signal
        path=self.root/'uploads'/f'tenant_{self.tenant}'/f'user_{self.user}'/'orphan.csv';path.parent.mkdir(parents=True)
        with path.open('wb') as output:
            for _ in range(64):output.write(b'x'*1024*1024)
        row=self.enroll('delete')
        env={**os.environ,'SUPABASE_URL':self.provider.url,'SUPABASE_SERVICE_KEY':os.environ['DELETION166_SERVICE_JWT'],'SUPABASE_ANON_KEY':os.environ['DELETION166_ANON_JWT'],'MADAR_ENV_FILE':'/dev/null','MADAR_ENV_OVERRIDE':'false','ACCOUNT_LIFECYCLE_WORKER_ENABLED':'true','ACCOUNT_LIFECYCLE_WORKER_ONCE':'true'}
        process=subprocess.Popen([sys.executable,'-m','workers.account_lifecycle_worker'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        observed=False
        try:
            deadline=time.monotonic()+30
            while process.poll() is None and time.monotonic()<deadline:
                observed=self.db.execute("select exists(select 1 from public.account_lifecycle_resources167 where request_id=%s and kind='file' and state='intent')",(row['id'],)).fetchone()[0]
                if observed:process.send_signal(signal.SIGSTOP);break
                time.sleep(.002)
            self.assertTrue(observed,'Did not observe durable intent; crash acceptance was not exercised')
            old=self.row(row)
        finally:
            if process.poll() is None:process.kill()
            process.wait(timeout=5)
        self.assertTrue(path.exists(),'Crash must occur before the observed file removal')
        self.db.execute("update public.account_lifecycles167 set lease_until=clock_timestamp()-interval '1 second' where id=%s",(row['id'],))
        restarted=subprocess.run([sys.executable,'-m','workers.account_lifecycle_worker'],env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(restarted.returncode,0,restarted.stderr[-2000:]);self.assertIsNone(self.row(row));self.assertFalse(path.exists())
        with self.assertRaises(APIError):self.service._transition(self.client,old,'renew')

    def test_day89_preserves_content_and_duplicate_does_not_extend_deadline(self):
        content,_digest,key,*_=self.dataset();path=self.root/'uploads'/key;path.parent.mkdir(parents=True);path.write_bytes(content)
        row=self.enroll()
        self.db.execute("with t as materialized(select clock_timestamp() as now) update public.account_lifecycles167 set requested_at=t.now-interval '89 days',deactivated_at=t.now-interval '89 days',recovery_deadline=t.now+interval '1 day',eligible_at=t.now+interval '1 day' from t where id=%s",(row['id'],))
        deadline=self.row(row)['recovery_deadline'];again=self.enroll()
        self.assertEqual(self.row(again)['recovery_deadline'],deadline);self.assertEqual(self.claim(),[]);self.assertEqual(path.read_bytes(),content)
        self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        self.assertEqual(self.claim(),[]);self.assertTrue(path.exists())

    def test_concurrent_duplicate_and_reactivation_delete_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        binding=self.service.storage_binding()
        def enroll(action):return self.rpc('create_account_action167',{'p_user_id':self.user,'p_actor_id':self.user,'p_action':action,'p_storage_binding':binding})
        with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(lambda _:enroll('deactivate'),range(6)))
        self.assertEqual(len({r['id'] for r in rows}),1);self.assertEqual(len({r['recovery_deadline'] for r in rows}),1)
        def recover():
            try:return self.rpc('reactivate_account167',{'p_request_id':rows[0]['id'],'p_actor_id':self.admin})
            except APIError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(recover);b=pool.submit(enroll,'delete');a.result();deleted=b.result()
        self.assertEqual(deleted['action'],'delete');self.assertIsNone(deleted['recovery_deadline'])
        self.assertEqual(self.db.execute('select account_status from public.users where id=%s',(self.user,)).fetchone()[0],'deletion_pending')
        claim=next(c for c in self.claim() if c['id']==deleted['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result)

    def test_unknown_owned_resource_blocks_before_irreversible_release(self):
        from psycopg import sql
        name='fixture_retention_'+uuid4().hex
        self.db.execute(sql.SQL('create table public.{}(id integer primary key, actor_id integer references public.users(id) on delete set null, payload text)').format(sql.Identifier(name)))
        self.addCleanup(self.db.execute,sql.SQL('drop table public.{}').format(sql.Identifier(name)))
        self.db.execute(sql.SQL('insert into public.{} values(1,%s,%s)').format(sql.Identifier(name)),(self.user,'ownership adapter required'))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute(sql.SQL('select actor_id,payload from public.{}').format(sql.Identifier(name))).fetchone(),(self.user,'ownership adapter required'))

    def test_credential_history_erases_only_through_fenced_owner_contract(self):
        source=self.db.execute("insert into public.data_sources(tenant_id,project_id,creator_user_id,source_type,display_name) values(%s,%s,%s,'spreadsheet_upload','Owned history') returning id",(self.tenant,self.project,self.user)).fetchone()[0]
        event=self.db.execute("insert into public.data_source_credential_events(tenant_id,project_id,source_id,actor_user_id,event_type) values(%s,%s,%s,%s,'provisioned') returning id",(self.tenant,self.project,source,self.admin)).fetchone()[0]
        # Normal service-role mutation remains forbidden even for an admin actor.
        with self.assertRaisesRegex(APIError,'credential_events_are_append_only'):
            self.client.table('data_source_credential_events').delete().eq('id',event).execute()
        with self.assertRaisesRegex(APIError,'credential_events_are_append_only'):
            self.client.table('data_source_credential_events').update({'event_code':'changed'}).eq('id',event).execute()
        self.db.execute("insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata) values(%s,%s,'auth.fixture','user',%s,'{}'),(%s,%s,'admin.fixture','user',%s,'{}'),(%s,%s,'other.fixture','user',%s,'{}')",(self.tenant,self.user,str(self.user),self.tenant,self.admin,str(self.user),self.tenant,self.owner,str(self.owner)))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result)
        self.assertEqual(self.db.execute('select count(*) from public.data_source_credential_events where id=%s',(event,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.audit_logs where actor_user_id=%s or target_id=%s',(self.user,str(self.user))).fetchone()[0],0)
        self.assertEqual(self.db.execute("select count(*) from public.audit_logs where actor_user_id=%s and action='other.fixture'",(self.owner,)).fetchone()[0],1)
        self.assertIsNone(self.row(row))
        self.assertEqual(self.db.execute('select count(*) from public.data_deletion_requests where id=%s',(row['id'],)).fetchone()[0],0)

    @unittest.skipUnless(os.getenv('MADAR_ERASURE_VAULT')=='YES','Requires disposable real Vault transit fixture')
    def test_complete_account_inventory_erases_with_real_vault_and_worker(self):
        from services import data_source_credential_service as credentials,parquet_cache_service as cache
        from psycopg import sql
        self.db.execute("update public.builder_projects set draft_schema='{\"workspaceKind\":\"data\"}' where id=%s",(self.project,))
        def provision(user,project,label):
            source=self.db.execute("insert into public.data_sources(tenant_id,project_id,creator_user_id,source_type,provider_key,display_name) values(%s,%s,%s,'api_provider','http_fixture',%s) returning id",(self.tenant,project,user,label)).fetchone()[0]
            row=credentials.provision_credential(tenant_id=self.tenant,project_id=str(project),source_id=str(source),user_id=user,provider_key='http_fixture',credential_type='bearer',secret='disposable-private-'+label,client=self.client)
            resolved=credentials.resolve_persistent_credential(tenant_id=self.tenant,project_id=str(project),source_id=str(source),user_id=user,provider_key='http_fixture',client=self.client)
            self.assertEqual(resolved.secret.reveal_for_request(),'disposable-private-'+label)
            return source,row['credential_id']
        source,credential=provision(self.user,self.project,'erased')
        email=self.db.execute('select email from public.users where id=%s',(self.user,)).fetchone()[0]
        from services.audit_service import hash_audit_identifier
        email_hash=hash_audit_identifier(email)
        self.db.execute("insert into public.email_verification_attempts(user_id,auth_id,email_hash,status) values(%s,%s,%s,'sent'),(null,null,%s,'limited')",(self.user,self.auth_id,email_hash,email_hash))
        self.db.execute("insert into public.pending_account_onboarding(auth_id,user_id,business_name,status) values(%s,%s,'Private onboarding','provisioned')",(self.auth_id,self.user))
        self.db.execute("insert into public.password_reset_requests(user_id,auth_id,nonce_hash,expires_at) values(%s,%s,%s,now()+interval '1 hour')",(self.user,self.auth_id,uuid4().hex))
        access=self.db.execute("insert into public.admin_account_access_requests(admin_user_id,target_user_id,target_email,expires_at) values(%s,%s,%s,now()+interval '1 hour') returning id",(self.admin,self.user,email)).fetchone()[0]
        self.db.execute("insert into public.admin_account_access_sessions(access_request_id,admin_user_id,target_user_id,expires_at) values(%s,%s,%s,now()+interval '1 hour')",(access,self.admin,self.user))
        from psycopg.types.json import Jsonb
        self.db.execute("insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,metadata) values(%s,%s,'admin.email_lookup','account_access',%s)",(self.tenant,self.admin,Jsonb({'target_email_hash':email_hash})))

        independent_project=str(uuid4())
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Keep',%s,'draft','{\"workspaceKind\":\"data\"}')",(independent_project,self.tenant,self.owner,independent_project))
        other_source,other_credential=provision(self.owner,independent_project,'kept')
        independent_before=self.db.execute('select to_jsonb(p) from public.builder_projects p where id=%s',(independent_project,)).fetchone()[0]
        content,digest,key,storage,dataset,version=self.dataset();csv=self.root/'uploads'/key;csv.parent.mkdir(parents=True);csv.write_bytes(content)
        self.db.execute('update public.data_datasets set source_id=%s where id=%s',(source,dataset))
        self.db.execute('update public.data_sources set latest_dataset_id=%s,latest_version_id=%s where id=%s',(dataset,version,source))
        with patch.object(cache,'MIN_SOURCE_BYTES',1):
            parquet=cache.get_or_create(source_path=str(csv),tenant_id=self.tenant,user_id=self.user,project_id=self.project,dataset_id=str(dataset),version_id=str(version),source_hash=digest,source_size=len(content),declared_rows=2)
        self.assertIsNotNone(parquet)
        exports=self.seed_reports();provider=self.seed_provider()
        archived_key=f'tenant_{self.tenant}/user_{self.user}/archived.csv'
        archived=self.root/'uploads'/archived_key;archived.write_bytes(content)
        archived_storage=self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256) values(%s,%s,'dataset',%s,%s,%s) returning id",(self.tenant,self.user,archived_key,len(content),digest)).fetchone()[0]
        archived_dataset=self.db.execute("insert into public.data_datasets(tenant_id,project_id,creator_user_id,display_name,status) values(%s,%s,%s,'Archived','archived') returning id",(self.tenant,self.project,self.user)).fetchone()[0]
        archived_version=self.db.execute("insert into public.data_dataset_versions(tenant_id,dataset_id,version_number,storage_object_id,created_by_user_id,original_filename,content_type,file_extension,size_bytes,content_hash) values(%s,%s,1,%s,%s,'archived.csv','text/csv','.csv',%s,%s) returning id",(self.tenant,archived_dataset,archived_storage,self.user,len(content),digest)).fetchone()[0]
        self.db.execute("insert into public.bi_report_lifecycle_settings(tenant_id,project_id,owner_user_id,retention_days,cleanup_enabled) values(%s,%s,%s,365,false)",(self.tenant,self.project,self.user))
        other_tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Independent tenant','Keep') returning tenant_id").fetchone()[0]
        other_user=self.add_user('owner',tenant=other_tenant)
        other_auth=str(self.db.execute('select auth_id from public.users where id=%s',(other_user,)).fetchone()[0])
        other_provider=self.provider.put_object('private-independent','keep/object',b'Independent tenant bytes',other_auth)

        orphan=csv.parent/'interrupted-upload.tmp';orphan.write_bytes(b'private interrupted body')
        self.db.execute("insert into public.audit_logs(tenant_id,actor_user_id,action,target_type,target_id,metadata,ip) values(%s,%s,'auth.fixture','user',%s,'{}','192.0.2.1')",(self.tenant,self.user,str(self.user)))
        # Reactivation history is also account data, not an audit exemption.
        prior=self.enroll();self.service.reactivate(request_id=prior['id'],actor_id=self.admin,client=self.client)
        row=self.enroll('delete');self.run_worker()
        self.assertIsNone(self.row(row));self.assertIsNone(self.row(prior))
        for table,column,value in [('users','id',self.user),('data_sources','id',source),('data_source_credentials','id',credential),('data_source_credential_events','source_id',source),('data_datasets','id',dataset),('data_dataset_versions','id',version),('storage_objects','id',storage),('bi_report_runs','creator_user_id',self.user),('audit_logs','actor_user_id',self.user),('data_deletion_requests','target_user_id_snapshot',self.user)]:
            count=self.db.execute(sql.SQL('select count(*) from public.{} where {}=%s').format(sql.Identifier(table),sql.Identifier(column)),(value,)).fetchone()[0]
            self.assertEqual(count,0,(table,count))
        for table,column,value in [('email_verification_attempts','email_hash',email_hash),('pending_account_onboarding','user_id',self.user),('password_reset_requests','user_id',self.user),('admin_account_access_requests','target_user_id',self.user),('admin_account_access_sessions','target_user_id',self.user)]:
            self.assertEqual(self.db.execute(sql.SQL('select count(*) from public.{} where {}=%s').format(sql.Identifier(table),sql.Identifier(column)),(value,)).fetchone()[0],0,table)
        self.assertEqual(self.db.execute("select count(*) from public.audit_logs where metadata->>'target_email_hash'=%s",(email_hash,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from auth.users where id=%s',(self.auth_id,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from storage.objects where owner_id=%s',(self.auth_id,)).fetchone()[0],0)
        self.assertFalse(any(p.exists() for p in [archived,csv,orphan,parquet.path,provider,*exports]))
        self.assertEqual(self.db.execute('select count(*) from public.data_dataset_versions where id=%s',(archived_version,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.data_datasets where id=%s',(archived_dataset,)).fetchone()[0],0)
        self.assertEqual(other_provider.read_bytes(),b'Independent tenant bytes')
        self.assertEqual(self.db.execute('select count(*) from auth.users where id=%s',(other_auth,)).fetchone()[0],1)
        from services.account_work_fence import _paths
        lock,marker=_paths(self.tenant,self.user);self.assertFalse(lock.exists());self.assertFalse(marker.exists())
        self.assertEqual(self.db.execute('select to_jsonb(p) from public.builder_projects p where id=%s',(independent_project,)).fetchone()[0],independent_before)
        kept=credentials.resolve_persistent_credential(tenant_id=self.tenant,project_id=independent_project,source_id=str(other_source),user_id=self.owner,provider_key='http_fixture',client=self.client)
        self.assertEqual(kept.secret.reveal_for_request(),'disposable-private-kept')

    def test_completion_lost_ack_does_not_restore_account_history(self):
        self.provider.fail_complete_ack=True
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed');self.assertIsNone(self.row(row))
        self.assertEqual(self.db.execute('select count(*) from public.data_deletion_requests where id=%s',(row['id'],)).fetchone()[0],0)
        from services.account_work_fence import _paths
        lock,marker=_paths(self.tenant,self.user);self.assertFalse(lock.exists());self.assertFalse(marker.exists())

    def test_provider_upload_after_freeze_is_rejected_before_private_bytes(self):
        path=self.seed_provider();key=path.relative_to(self.provider.root/'madar-data-immutable').as_posix()
        path.unlink();self.db.execute('delete from storage.objects where owner_id=%s',(self.auth_id,))
        self.enroll()
        with self.assertRaises(Exception):self.client.storage.from_('madar-data-immutable').upload(key,b'private late upload',{'content-type':'text/csv'})
        self.assertEqual(self.provider.storage_upload_attempts,1);self.assertFalse(path.exists())
        self.assertEqual(self.db.execute('select count(*) from storage.objects where bucket_id=%s and name=%s',('madar-data-immutable',key)).fetchone()[0],0)

    def test_transient_verification_retry_is_durable_without_repeating_effect(self):
        path=self.seed_provider();self.provider.fail_storage_list=True
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'retry_pending');self.assertTrue(path.exists());self.assertEqual(self.provider.storage_removes,0)
        self.assertEqual(self.claim(),[],'Infrastructure retry must respect its bounded backoff')
        self.db.execute('update public.account_lifecycles167 set eligible_at=clock_timestamp() where id=%s',(row['id'],))
        claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed');self.assertEqual(self.provider.storage_removes,1)

    def test_auth_session_cannot_resurrect_after_public_subject_removed(self):
        self.provider.fail_auth='before'
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertTrue(self.row(row)['subject_removed'])
        with self.assertRaisesRegex(Exception,'account_session_frozen'):
            self.db.execute('insert into auth.sessions(id,user_id) values(%s,%s)',(str(uuid4()),self.auth_id))
        self.assertEqual(self.provider.auth_removes,1)
        # Unknown Auth outcome is not blindly repeated. Resolve independently.
        self.db.execute('delete from auth.users where id=%s',(self.auth_id,))
        self.rpc('resume_account_erasure167',{'p_request_id':row['id'],'p_actor_id':self.admin})
        claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed');self.assertEqual(self.provider.auth_removes,1)

    def test_calendar_worker_and_claims_are_fenced_without_starving_independent_owner(self):
        from workers import calendar_sync_worker as worker
        import database
        def job(user):
            connection=self.db.execute("insert into public.calendar_sync_connections(tenant_id,user_id,provider,status,inbound_sync_enabled,encrypted_credentials) values(%s,%s,'google','connected',true,'private fixture') returning id",(self.tenant,user)).fetchone()[0]
            queued=self.rpc('enqueue_calendar_connection_sync_job',{'p_tenant_id':self.tenant,'p_connection_id':str(connection),'p_operation':'incremental'})
            return connection,queued
        connection,_=job(self.user)
        claims=self.rpc('claim_calendar_connection_sync_jobs',{'p_worker_id':'disposable-calendar','p_limit':2,'p_now':self.db.execute('select clock_timestamp()::text').fetchone()[0]})
        claimed=next(c for c in claims if c['connection_id']==str(connection))
        self.enroll()
        with patch.object(database,'service_supabase',self.client),patch.object(worker,'process_connection_sync_job') as provider:
            with self.assertRaises(HTTPException):worker.process_connection_job(claimed)
            provider.assert_not_called()
        other,_=job(self.owner)
        current=self.rpc('claim_calendar_connection_sync_jobs',{'p_worker_id':'independent-calendar','p_limit':2,'p_now':self.db.execute('select clock_timestamp()::text').fetchone()[0]})
        self.assertEqual([c['connection_id'] for c in current],[str(other)])

    def test_authenticated_http_request_holds_work_scope_until_response_completion(self):
        import asyncio,httpx,threading
        from concurrent.futures import ThreadPoolExecutor
        from fastapi import FastAPI,Request
        from fastapi.testclient import TestClient
        from services import auth_service
        from services.account_work_fence import AccountWorkFenceMiddleware,AccountWorkBusy
        email=self.db.execute('select email from public.users where id=%s',(self.user,)).fetchone()[0]
        login=httpx.post(self.provider.url+'/auth/v1/token?grant_type=password',json={'email':email,'password':'fixture-password'},timeout=10).json()
        app=FastAPI();app.add_middleware(AccountWorkFenceMiddleware)
        ready=threading.Event();release=threading.Event()
        @app.get('/private-work')
        async def private_work(request:Request):
            auth_service.get_authenticated_user_row(request,allow_admin_account_access=False)
            ready.set();await asyncio.to_thread(release.wait,10)
            return {'ok':True}
        cookies={'madar_access_token':login['access_token'],'madar_session_activity':auth_service.create_session_activity_value()}
        with patch.object(auth_service,'supabase',self.client),patch.object(auth_service,'service_supabase',self.client),TestClient(app) as browser,ThreadPoolExecutor(max_workers=1) as pool:
            browser.cookies.update(cookies);running=pool.submit(browser.get,'/private-work')
            try:
                self.assertTrue(ready.wait(10))
                with self.assertRaises(AccountWorkBusy):self.enroll()
                self.assertEqual(self.db.execute('select account_status from public.users where id=%s',(self.user,)).fetchone()[0],'active')
            finally:release.set()
            self.assertEqual(running.result(timeout=10).status_code,200)
            self.enroll()
            self.assertIn(browser.get('/private-work').status_code,(401,409))

    def test_unmapped_indirect_version_payload_cannot_survive_set_null(self):
        from psycopg import sql
        content,_digest,key,_storage,_dataset,version=self.dataset();path=self.root/'uploads'/key;path.parent.mkdir(parents=True);path.write_bytes(content)
        name='fixture_indirect_'+uuid4().hex
        self.db.execute(sql.SQL('create table public.{}(id integer primary key, version_ref uuid references public.data_dataset_versions(id) on delete set null, payload text)').format(sql.Identifier(name)))
        self.addCleanup(self.db.execute,sql.SQL('drop table public.{}').format(sql.Identifier(name)))
        self.db.execute(sql.SQL('insert into public.{} values(1,%s,%s)').format(sql.Identifier(name)),(version,'private payload with indirect ownership'))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released']);self.assertEqual(path.read_bytes(),content)
        self.assertEqual(self.db.execute(sql.SQL('select version_ref from public.{}').format(sql.Identifier(name))).fetchone()[0],version)

    def test_ownerless_provider_metadata_prevents_false_completion(self):
        path=self.seed_provider();path.unlink()
        self.db.execute('update storage.objects set owner_id=null where owner_id=%s',(self.auth_id,))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(self.row(row)['error_code'],'account_provider_object_remains')
        from services.account_work_fence import _paths
        lock,marker=_paths(self.tenant,self.user);self.assertTrue(lock.exists());self.assertTrue(marker.exists())
        key=path.relative_to(self.provider.root/'madar-data-immutable').as_posix()
        self.db.execute('delete from storage.objects where bucket_id=%s and name=%s',('madar-data-immutable',key))
        self.rpc('resume_account_erasure167',{'p_request_id':row['id'],'p_actor_id':self.admin})
        claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed');self.assertIsNone(self.row(row))

    def test_version_bound_provider_scratch_is_erased_after_interrupted_read(self):
        from services import immutable_object_storage as objects
        import hashlib
        path=self.seed_provider();key=path.relative_to(self.provider.root/'madar-data-immutable').as_posix()
        descriptor=objects.ImmutableObject(backend='supabase_private',bucket='madar-data-immutable',object_key=key,size_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        root=objects.private_scratch_root(tenant_id=self.tenant,descriptor=descriptor)
        leftover=root/'verify-interrupted';leftover.mkdir();copy=leftover/'object.part';copy.write_bytes(path.read_bytes())
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed');self.assertFalse(root.exists());self.assertFalse(path.exists())

    def test_legacy_unattributed_scratch_blocks_without_removing_unknown_files(self):
        legacy=self.root/'legacy-tmp';legacy.mkdir();private=legacy/'madar-immutable-read-old';private.mkdir();data=private/'object';data.write_bytes(b'unattributed private content')
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        with patch('tempfile.gettempdir',return_value=str(legacy)):
            result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released']);self.assertEqual(data.read_bytes(),b'unattributed private content')

    def test_multipart_receiving_is_fenced_before_any_body_is_consumed(self):
        import asyncio,httpx,threading
        from concurrent.futures import ThreadPoolExecutor
        from services import auth_service
        from services.account_work_fence import AccountWorkFenceMiddleware,AccountWorkBusy
        from starlette.responses import JSONResponse
        import database
        email=self.db.execute('select email from public.users where id=%s',(self.user,)).fetchone()[0]
        login=httpx.post(self.provider.url+'/auth/v1/token?grant_type=password',json={'email':email,'password':'fixture-password'},timeout=10).json()
        ready=threading.Event();release=threading.Event();messages=[]
        cookie='madar_access_token='+login['access_token']+'; madar_session_activity='+auth_service.create_session_activity_value()
        def scope():return {'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','scheme':'http','server':('fixture',80),'client':('127.0.0.1',1),'method':'POST','path':f'/users/{self.user}/data/upload','query_string':b'','headers':[(b'content-type',b'multipart/form-data; boundary=fixture'),(b'cookie',cookie.encode())]}
        async def receive():
            ready.set();await asyncio.to_thread(release.wait,10)
            return {'type':'http.request','body':b'--fixture--\r\n','more_body':False}
        async def send(message):messages.append(message)
        async def parser_boundary(scope,receive,send):
            await receive();await JSONResponse({'ok':True})(scope,receive,send)
        app=AccountWorkFenceMiddleware(parser_boundary)
        with patch.object(database,'service_supabase',self.client),patch.object(auth_service,'supabase',self.client),patch.object(auth_service,'service_supabase',self.client),ThreadPoolExecutor(max_workers=1) as pool:
            request=pool.submit(asyncio.run,app(scope(),receive,send))
            try:
                self.assertTrue(ready.wait(10))
                with self.assertRaises(AccountWorkBusy):self.enroll()
            finally:release.set()
            request.result(timeout=10)
            self.assertEqual(messages[0]['status'],200)
            self.enroll();messages.clear();ready.clear()
            asyncio.run(app(scope(),receive,send))
            self.assertFalse(ready.is_set(),'A frozen upload must not consume a multipart body')
            self.assertIn(messages[0]['status'],(401,409))

    def test_scheduler_selection_excludes_held_work_before_its_limit(self):
        def dashboard(user,project):
            self.db.execute("update public.builder_projects set draft_schema='{\"workspaceKind\":\"data\"}' where id=%s",(project,))
            dashboard=self.db.execute("insert into public.bi_dashboards(tenant_id,project_id,creator_user_id,name,auto_refresh_enabled) values(%s,%s,%s,'Scheduler fixture',true) returning id",(self.tenant,project,user)).fetchone()[0]
            schedule=self.db.execute("insert into public.bi_report_schedules(tenant_id,project_id,creator_user_id,dashboard_id,name,cadence,timezone,local_time,next_run_at) values(%s,%s,%s,%s,'Due','daily','UTC','09:00',now()-interval '1 day') returning id",(self.tenant,project,user,dashboard)).fetchone()[0]
            return dashboard,schedule
        target_dashboard,target_schedule=dashboard(self.user,self.project)
        other_project=str(uuid4());self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Independent scheduler',%s,'draft','{}')",(other_project,self.tenant,self.owner,other_project))
        kept_dashboard,kept_schedule=dashboard(self.owner,other_project)
        self.enroll()
        now=self.db.execute('select clock_timestamp()::text').fetchone()[0]
        for kind,expected in [('schedules',kept_schedule),('dashboards',kept_dashboard)]:
            selected=self.rpc('list_account_work167',{'p_kind':kind,'p_limit':1,'p_before':now})
            self.assertEqual([item['id'] for item in selected],[str(expected)])
        self.assertTrue(self.db.execute('select enabled from public.bi_report_schedules where id=%s',(target_schedule,)).fetchone()[0])

    def test_unclassified_workspace_cannot_be_certified_with_data_only_adapters(self):
        self.db.execute("update public.builder_projects set draft_schema='{\"workspaceKind\":\"website\",\"privatePayload\":\"must not guess storage ownership\"}' where id=%s",(self.project,))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select count(*) from public.builder_projects where id=%s',(self.project,)).fetchone()[0],1)

    def test_provider_registry_owner_disagreement_never_deletes_independent_bytes(self):
        path=self.seed_provider();before=path.read_bytes()
        other_auth=self.db.execute('select auth_id from public.users where id=%s',(self.owner,)).fetchone()[0]
        self.db.execute('update storage.objects set owner_id=%s where owner_id=%s',(other_auth,self.auth_id))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.provider.storage_removes,0);self.assertEqual(self.provider.auth_removes,0)

    def seed_local_calendar(self, user=None, *, archived=False):
        user=user or self.user
        calendar=str(uuid4());event=str(uuid4());task=str(uuid4())
        self.db.execute("insert into public.calendars(id,tenant_id,owner_user_id,name) values(%s,%s,%s,'Private local')",(calendar,self.tenant,user))
        self.db.execute("insert into public.calendar_events(id,tenant_id,calendar_id,created_by,title,starts_at,ends_at,deleted_at) values(%s,%s,%s,%s,'Private event',now(),now()+interval '1 hour',case when %s then now() end)",(event,self.tenant,calendar,user,archived))
        self.db.execute("insert into public.calendar_tasks(id,tenant_id,calendar_id,owner_user_id,title,archived_at) values(%s,%s,%s,%s,'Private task',case when %s then now() end)",(task,self.tenant,calendar,user,archived))
        self.db.execute("insert into public.calendar_event_changes(tenant_id,event_id,changed_by,action,before_data) values(%s,%s,%s,'created','{\"private\":true}')",(self.tenant,event,user))
        self.db.execute("insert into public.calendar_event_attendees(tenant_id,event_id,email) values(%s,%s,'guest@example.invalid')",(self.tenant,event))
        self.db.execute("insert into public.calendar_event_reminders(tenant_id,event_id,minutes_before) values(%s,%s,10)",(self.tenant,event))
        self.db.execute("insert into public.calendar_task_reminders(tenant_id,task_id,minutes_before) values(%s,%s,10)",(self.tenant,task))
        notice=str(uuid4())
        self.db.execute("insert into public.notification_events(id,tenant_id,event_type,source_type,source_id,title,body) values(%s,%s,'reminder','calendar_event',%s,'Private event','Private body')",(notice,self.tenant,event))
        self.db.execute("insert into public.user_notifications(event_id,tenant_id,user_id,event_type,title,body) values(%s,%s,%s,'reminder','Private event','Private body')",(notice,self.tenant,self.owner))
        return calendar,event,task,notice

    def test_multimodule_local_erasure_real_worker_preserves_independent_project(self):
        from services.account_restore_boundary import capture_boundary,seal_snapshot,verify_restore,RestoreBoundaryError
        before=capture_boundary(self.client);manifest=seal_snapshot(before,before,'a'*64)
        owned=[self.seed_local_calendar(),self.seed_local_calendar(archived=True)]
        keep=self.seed_local_calendar(self.owner)
        reports=self.seed_reports();provider=self.seed_provider()
        _content,_digest,key,*_=self.dataset();csv=self.root/'uploads'/key;csv.parent.mkdir(parents=True);csv.write_bytes(_content)
        for state in ('new','archived'):
            self.db.execute("insert into public.builder_form_submissions(tenant_id,project_id,form_id,status,answers) values(%s,%s,'private-form',%s,'{\"secret\":true}')",(self.tenant,self.project,state))
        self.db.execute("insert into public.builder_reservations(tenant_id,project_id,customer_email,status) values(%s,%s,'private@example.invalid','cancelled')",(self.tenant,self.project))
        self.db.execute("insert into public.builder_form_drafts(tenant_id,project_id,form_id,draft_name,site_user_id,answers) values(%s,%s,'draft','Private draft',%s,'{\"secret\":true}')",(self.tenant,self.project,self.user))
        independent=str(uuid4())
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Independent project',%s,'draft','{}')",(independent,self.tenant,self.owner,independent))
        kept_project=self.db.execute('select to_jsonb(p) from public.builder_projects p where id=%s',(independent,)).fetchone()[0]
        quiz=str(uuid4())
        self.db.execute("insert into public.public_quiz_attempts(id,tenant_id,project_id,form_id,publication_version,publication_hash,subject_hash,deadline_at,question_order,private_form_snapshot) values(%s,%s,%s,'quiz',1,%s,%s,now()+interval '10 minutes','[]','{\"private\":true}')",(quiz,self.tenant,self.project,'a'*64,'b'*64))
        self.db.execute('insert into public.user_security_settings(user_id,auth_id) values(%s,%s)',(self.user,self.auth_id))
        self.db.execute("insert into public.app_installations(installation_id,user_id,current_tenant_id,platform,display_mode,notification_permission) values(%s,%s,%s,'linux','browser','default')",(str(uuid4()),self.user,self.tenant))
        self.db.execute('insert into public.workspace_screen_time_daily(tenant_id,user_id,activity_date,active_seconds) values(%s,%s,current_date,31)',(self.tenant,self.user))
        row=self.enroll('delete');self.run_worker()
        for table in ('user_security_settings','app_installations','workspace_screen_time_daily'):
            self.assertEqual(self.db.execute('select count(*) from public.'+table+' where user_id=%s',(self.user,)).fetchone()[0],0,table)
        self.assertIsNone(self.row(row));self.assertFalse(csv.exists());self.assertFalse(provider.exists());self.assertTrue(all(not path.exists() for path in reports))
        for calendar,event,task,notice in owned:
            for table,ident in [('calendars',calendar),('calendar_events',event),('calendar_tasks',task),('notification_events',notice)]:
                self.assertEqual(self.db.execute('select count(*) from public.'+table+' where id=%s',(ident,)).fetchone()[0],0,table)
            self.assertEqual(self.db.execute('select count(*) from public.user_notifications where event_id=%s',(notice,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.calendars where id=%s',(keep[0],)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from public.calendar_event_changes where event_id=%s',(keep[1],)).fetchone()[0],1)
        for table in ('builder_form_drafts','builder_form_submissions','builder_reservations'):
            self.assertEqual(self.db.execute('select count(*) from public.'+table+' where project_id=%s',(self.project,)).fetchone()[0],0,table)
        self.assertEqual(self.db.execute('select count(*) from public.public_quiz_attempts where id=%s',(quiz,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select to_jsonb(p) from public.builder_projects p where id=%s',(independent,)).fetchone()[0],kept_project)
        after=capture_boundary(self.client);self.assertGreater(after['epoch'],before['epoch'])
        with self.assertRaisesRegex(RestoreBoundaryError,'resurrect'):verify_restore(manifest,'a'*64,self.client)
        fresh=seal_snapshot(after,after,'b'*64)
        self.assertEqual(verify_restore(fresh,'b'*64,self.client),{'suppression_verified':True,'restore_execution_authorized':False})
        with self.assertRaisesRegex(RestoreBoundaryError,'crossed'):seal_snapshot(before,after,'c'*64)

    def test_calendar_shared_and_provider_paths_refuse_without_destructive_effects(self):
        calendar,event,task,notice=self.seed_local_calendar()
        self.db.execute("update public.calendars set visibility='team' where id=%s",(calendar,))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select count(*) from public.calendar_events where id=%s',(event,)).fetchone()[0],1)

    def test_calendar_external_connection_is_not_local_erasure_acceptance(self):
        calendar,*_=self.seed_local_calendar()
        self.db.execute("insert into public.calendar_sync_connections(tenant_id,user_id,local_calendar_id,provider,encrypted_credentials) values(%s,%s,%s,'google','opaque-provider-secret')",(self.tenant,self.user,calendar))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.provider.auth_removes,0)

    def test_calendar_parent_fences_and_reactivation_preserve_archive(self):
        calendar,event,task,notice=self.seed_local_calendar(archived=True)
        row=self.enroll('deactivate')
        with self.assertRaisesRegex(Exception,'frozen'):
            self.db.execute("insert into public.calendar_event_changes(tenant_id,event_id,action) values(%s,%s,'deleted')",(self.tenant,event))
        with self.assertRaisesRegex(Exception,'frozen'):
            self.db.execute("insert into public.calendar_event_reminders(tenant_id,event_id,minutes_before) values(%s,%s,20)",(self.tenant,event))
        self.assertEqual(self.claim(),[])
        self.service.reactivate(request_id=row['id'],actor_id=self.admin,client=self.client)
        self.assertIsNotNone(self.db.execute('select deleted_at from public.calendar_events where id=%s',(event,)).fetchone()[0])
        self.assertEqual(self.db.execute('select count(*) from public.calendar_tasks where id=%s',(task,)).fetchone()[0],1)

    def test_builder_shared_asset_is_preserved_and_not_certified_erased(self):
        import hashlib
        asset=str(uuid4());filename=uuid4().hex+'.png';key=f'tenant_{self.tenant}/builder_assets/{filename}';content=b'private shared builder payload'
        project=str(uuid4())
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Independent',%s,'draft','{}')",(project,self.tenant,self.owner,project))
        self.db.execute("insert into public.builder_assets(id,tenant_id,owner_user_id,ownership_status,uploader_user_id,storage_backend,storage_bucket,provider_object_key,storage_key,managed_filename,mime_type,size_bytes,sha256,status) values(%s,%s,%s,'verified',%s,'supabase_builder_private','builder-assets',%s,%s,%s,'image/png',%s,%s,'soft_deleted')",(asset,self.tenant,self.user,self.user,key,key,filename,len(content),hashlib.sha256(content).hexdigest()))
        self.db.execute("insert into public.builder_asset_references(asset_id,project_id,reference_path) values(%s,%s,'draft.image')",(asset,project))
        provider=self.provider.put_object('builder-assets',key,content,self.auth_id)
        cache=self.root/'builder-files'/key;cache.parent.mkdir(parents=True);cache.write_bytes(content)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(provider.read_bytes(),content);self.assertEqual(cache.read_bytes(),content)
        self.assertEqual(self.db.execute('select owner_user_id from public.builder_projects where id=%s',(project,)).fetchone()[0],self.owner)
        self.assertEqual(self.db.execute('select status from public.builder_assets where id=%s',(asset,)).fetchone()[0],'soft_deleted')

    def test_owned_builder_assets_remove_exact_provider_and_cache_bytes(self):
        import hashlib
        assets=[]
        for project,status,payload in ((self.project,'draft',b'active builder bytes'),(str(uuid4()),'archived',b'archived builder bytes')):
            if project!=self.project:
                self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Archived',%s,%s,'{}')",(project,self.tenant,self.user,project,status))
            filename=uuid4().hex+'.png';key=f'tenant_{self.tenant}/builder_assets/{filename}';asset=str(uuid4());digest=hashlib.sha256(payload).hexdigest()
            self.db.execute("insert into public.builder_assets(id,tenant_id,project_id,owner_user_id,ownership_status,uploader_user_id,storage_backend,storage_bucket,provider_object_key,storage_key,managed_filename,mime_type,size_bytes,sha256,status) values(%s,%s,%s,%s,'verified',%s,'supabase_builder_private','builder-assets',%s,%s,%s,'image/png',%s,%s,'active')",(asset,self.tenant,project,self.user,self.user,key,key,filename,len(payload),digest))
            self.db.execute("insert into public.builder_asset_references(asset_id,project_id,reference_path) values(%s,%s,'draft.image')",(asset,project))
            provider=self.provider.put_object('builder-assets',key,payload,self.auth_id)
            cache=self.root/'builder-files'/key;cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(payload)
            assets.append((asset,provider,cache))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        self.provider.fail_storage='after'
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result)
        for asset,provider,cache in assets:
            self.assertFalse(provider.exists());self.assertFalse(cache.exists())
            self.assertEqual(self.db.execute('select count(*) from public.builder_assets where id=%s',(asset,)).fetchone()[0],0)

    def test_independent_owner_asset_uploaded_by_departing_user_is_preserved(self):
        import hashlib
        project=str(uuid4());asset=str(uuid4());filename=uuid4().hex+'.png';key=f'tenant_{self.tenant}/builder_assets/{filename}';content=b'independent owner bytes'
        self.db.execute("insert into public.builder_projects(id,tenant_id,owner_user_id,name,slug,status,draft_schema) values(%s,%s,%s,'Independent',%s,'draft','{}')",(project,self.tenant,self.owner,project))
        self.db.execute("insert into public.builder_assets(id,tenant_id,project_id,owner_user_id,ownership_status,uploader_user_id,storage_backend,storage_bucket,provider_object_key,storage_key,managed_filename,mime_type,size_bytes,sha256,status) values(%s,%s,%s,%s,'verified',%s,'supabase_builder_private','builder-assets',%s,%s,%s,'image/png',%s,%s,'active')",(asset,self.tenant,project,self.owner,self.user,key,key,filename,len(content),hashlib.sha256(content).hexdigest()))
        self.db.execute("insert into public.builder_asset_references(asset_id,project_id,reference_path) values(%s,%s,'draft.image')",(asset,project))
        provider=self.provider.put_object('builder-assets',key,content,str(self.db.execute('select auth_id from public.users where id=%s',(self.owner,)).fetchone()[0]))
        cache=self.root/'builder-files'/key;cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(content)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed')
        self.assertEqual(provider.read_bytes(),content);self.assertEqual(cache.read_bytes(),content)
        self.assertEqual(self.db.execute('select owner_user_id,uploader_user_id from public.builder_assets where id=%s',(asset,)).fetchone(),(self.owner,None))

    def test_learning_and_academy_personal_history_erases_without_independent_form(self):
        import hashlib
        form=str(uuid4());response=str(uuid4())
        self.db.execute("insert into public.elearning_forms(id,tenant_id,name,created_by) values(%s,%s,'Independent form',%s)",(form,self.tenant,self.owner))
        self.db.execute("insert into public.elearning_form_versions(tenant_id,form_id,version,schema,created_by) values(%s,%s,1,'{}',%s)",(self.tenant,form,self.owner))
        self.db.execute("insert into public.elearning_form_responses(id,tenant_id,form_id,version,user_id,answers,idempotency_key,request_hash) values(%s,%s,%s,1,%s,'{\"private\":true}',%s,%s)",(response,self.tenant,form,self.user,str(uuid4()),'a'*64))
        file_id=str(uuid4());file_key=f'elearning-private/tenant_{self.tenant}/response_{response}/{file_id}';file_bytes=b'private learning form bytes';file_digest=hashlib.sha256(file_bytes).hexdigest()
        self.db.execute("insert into public.elearning_form_files(id,tenant_id,response_id,field_id,storage_key,filename,mime_type,size_bytes,sha256) values(%s,%s,%s,'identity',%s,%s,'application/pdf',%s,%s)",(file_id,self.tenant,response,file_key,'document-'+file_id[:8]+'.pdf',len(file_bytes),file_digest))
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256) values(%s,%s,'elearning_form',%s,%s,%s)",(self.tenant,self.user,file_key,len(file_bytes),file_digest))
        form_object=self.provider.put_object('builder-assets',file_key,file_bytes,self.auth_id)
        self.db.execute("insert into public.elearning_form_decision_history(tenant_id,response_id,revision,actor_id,old_status,new_status,note) values(%s,%s,2,%s,'submitted','under_review','Private review')",(self.tenant,response,self.owner))
        application=str(self.db.execute("insert into public.academy_applications(tenant_id,user_id,kind,details,idempotency_key,learning_form_response_id) values(%s,%s,'affiliate','{\"private\":true}',%s,%s) returning id",(self.tenant,self.user,str(uuid4()),response)).fetchone()[0])
        self.db.execute("insert into public.academy_workflow_history(tenant_id,entity_type,entity_id,actor_id,new_status,note) values(%s,'application',%s,%s,'submitted','Private workflow')",(self.tenant,application,self.owner))
        document=str(uuid4());document_key=f'academy-private/tenant_{self.tenant}/application_{application}/{document}';document_bytes=b'private academy document';document_digest=hashlib.sha256(document_bytes).hexdigest()
        self.db.execute("insert into public.academy_application_documents(id,tenant_id,application_id,uploaded_by,storage_key,filename,mime_type,size_bytes,sha256) values(%s,%s,%s,%s,%s,%s,'application/pdf',%s,%s)",(document,self.tenant,application,self.user,document_key,'document-'+document[:8]+'.pdf',len(document_bytes),document_digest))
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256) values(%s,%s,'academy_document',%s,%s,%s)",(self.tenant,self.user,document_key,len(document_bytes),document_digest))
        document_object=self.provider.put_object('builder-assets',document_key,document_bytes,self.auth_id)
        with self.assertRaisesRegex(Exception,'immutable'):
            self.db.execute('delete from public.elearning_form_responses where id=%s',(response,))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result)
        self.assertFalse(form_object.exists());self.assertFalse(document_object.exists())
        self.assertEqual(self.db.execute('select count(*) from public.elearning_form_responses where id=%s',(response,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.academy_applications where id=%s',(application,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select created_by from public.elearning_forms where id=%s',(form,)).fetchone()[0],self.owner)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_form_versions where form_id=%s',(form,)).fetchone()[0],1)

    def test_learner_attempt_review_recording_and_progress_erase_but_course_remains(self):
        import hashlib
        course=str(self.db.execute("insert into public.elearning_courses(tenant_id,name,status,created_by) values(%s,'Owner course','published',%s) returning id",(self.tenant,self.owner)).fetchone()[0])
        learner=str(self.db.execute("insert into public.elearning_learners(tenant_id,name,email,user_id) values(%s,'Departing learner','learner@example.invalid',%s) returning id",(self.tenant,self.user)).fetchone()[0])
        enrollment=str(self.db.execute("insert into public.elearning_enrollments(tenant_id,course_id,learner_id,status,access_source,created_by) values(%s,%s,%s,'active','manual',%s) returning id",(self.tenant,course,learner,self.owner)).fetchone()[0])
        assessment=str(self.db.execute("insert into public.elearning_assessments(tenant_id,title,status,created_by) values(%s,'Owner assessment','published',%s) returning id",(self.tenant,self.owner)).fetchone()[0])
        question=str(self.db.execute("insert into public.elearning_assessment_questions(tenant_id,assessment_id,type,prompt,points,position,config) values(%s,%s,'written','Private answer',1,0,'{\"rubric\":\"Private\",\"max_characters\":1000}') returning id",(self.tenant,assessment)).fetchone()[0])
        placement=str(self.db.execute("insert into public.elearning_assessment_placements(tenant_id,course_id,assessment_id,placement_type) values(%s,%s,%s,'course') returning id",(self.tenant,course,assessment)).fetchone()[0])
        attempt=str(uuid4())
        self.db.execute("insert into public.elearning_assessment_attempts(id,tenant_id,assessment_id,user_id,course_id,enrollment_id,placement_id,attempt_number,status,private_snapshot,submitted_at,total_points) values(%s,%s,%s,%s,%s,%s,%s,1,'pending_review','{}',now(),1)",(attempt,self.tenant,assessment,self.user,course,enrollment,placement))
        self.db.execute("insert into public.elearning_assessment_answers(tenant_id,attempt_id,question_id,response) values(%s,%s,%s,'{\"text\":\"private response\"}')",(self.tenant,attempt,question))
        self.db.execute("insert into public.elearning_assessment_reviews(tenant_id,attempt_id,question_id,reviewer_id,points,feedback) values(%s,%s,%s,%s,1,'private feedback')",(self.tenant,attempt,question,self.owner))
        recording=str(uuid4());key=f'elearning-assessments/tenant_{self.tenant}/attempt_{attempt}/{recording}.wav';content=b'R'*128;digest=hashlib.sha256(content).hexdigest()
        self.db.execute("insert into public.elearning_assessment_recordings(id,tenant_id,attempt_id,question_id,storage_key,sha256,size_bytes,duration_ms,mime_type) values(%s,%s,%s,%s,%s,%s,%s,10,'audio/wav')",(recording,self.tenant,attempt,question,key,digest,len(content)))
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes,sha256) values(%s,%s,'elearning_assessment',%s,%s,%s)",(self.tenant,self.user,key,len(content),digest))
        provider=self.provider.put_object('elearning-assessment-recordings',key,content,self.auth_id)
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'completed',result);self.assertFalse(provider.exists())
        for table,column,value in (('elearning_assessment_attempts','id',attempt),('elearning_enrollments','id',enrollment),('elearning_learners','id',learner)):
            self.assertEqual(self.db.execute(f'select count(*) from public.{table} where {column}=%s',(value,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_courses where id=%s',(course,)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select count(*) from public.elearning_assessments where id=%s',(assessment,)).fetchone()[0],1)

    def test_instructor_assignment_is_independent_and_blocks_personal_erasure(self):
        course=str(self.db.execute("insert into public.elearning_courses(tenant_id,name,created_by) values(%s,'Independent course',%s) returning id",(self.tenant,self.owner)).fetchone()[0])
        instructor=str(self.db.execute("insert into public.elearning_instructors(tenant_id,name,email,user_id) values(%s,'Departing instructor','departing@example.invalid',%s) returning id",(self.tenant,self.user)).fetchone()[0])
        self.db.execute("insert into public.elearning_course_instructors(tenant_id,course_id,instructor_id) values(%s,%s,%s)",(self.tenant,course,instructor))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error_code'],'shared_learning_ownership')
        self.assertEqual(self.db.execute('select count(*) from public.elearning_courses where id=%s',(course,)).fetchone()[0],1)
        self.assertEqual(self.db.execute('select user_id from public.elearning_instructors where id=%s',(instructor,)).fetchone()[0],self.user)

    def test_learning_review_of_another_account_blocks_without_erasing_response(self):
        form=str(uuid4());response=str(uuid4())
        self.db.execute("insert into public.elearning_forms(id,tenant_id,name,created_by) values(%s,%s,'Independent review form',%s)",(form,self.tenant,self.owner))
        self.db.execute("insert into public.elearning_form_versions(tenant_id,form_id,version,schema,created_by) values(%s,%s,1,'{}',%s)",(self.tenant,form,self.owner))
        self.db.execute("insert into public.elearning_form_responses(id,tenant_id,form_id,version,user_id,answers,idempotency_key,request_hash) values(%s,%s,%s,1,%s,'{\"private\":true}',%s,%s)",(response,self.tenant,form,self.owner,str(uuid4()),'b'*64))
        self.db.execute('update public.elearning_form_reviews set reviewer_id=%s where response_id=%s',(self.user,response))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error_code'],'shared_learning_ownership')
        self.assertEqual(self.db.execute('select count(*) from public.elearning_form_responses where id=%s',(response,)).fetchone()[0],1)

    def test_academy_referral_finance_blocks_as_mixed_ownership(self):
        referral=str(self.db.execute("insert into public.academy_referrals(tenant_id,sender_id,referred_id,amount,currency) values(%s,%s,%s,10,'USD') returning id",(self.tenant,self.user,self.owner)).fetchone()[0])
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select count(*) from public.academy_referrals where id=%s',(referral,)).fetchone()[0],1)

    def test_notification_paused_before_fence_cannot_send_after_erasure(self):
        from contextlib import contextmanager
        from services import account_work_fence as fence
        *_,notice=self.seed_local_calendar()
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        original=fence.account_lock;erased=[];sent=[]
        @contextmanager
        def paused(*identity,**kwargs):
            if not erased:
                erased.append(True)
                self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed')
            with original(*identity,**kwargs):yield
        @fence.notification_work
        def deliver(row,*,client):sent.append('provider effect')
        with patch.object(fence,'account_lock',paused):
            with self.assertRaises(HTTPException):deliver({'event_id':notice,'user_id':self.owner,'tenant_id':self.tenant},client=self.client)
        self.assertEqual(sent,[]);self.assertIsNone(self.row(row))
        with self.assertRaises(HTTPException):deliver({'event_id':notice,'user_id':self.owner,'tenant_id':self.tenant},client=self.client)
        self.assertEqual(sent,[])
        account_name=__import__('hashlib').sha256(f'{self.tenant}:{self.user}'.encode()).hexdigest()
        folder=self.root/'uploads'/'.account_fences'
        self.assertFalse((folder/(account_name+'.lock')).exists());self.assertFalse((folder/(account_name+'.hold')).exists())

    def test_restore_floor_publication_failure_recovers_under_new_lease(self):
        from services import account_restore_boundary as boundary
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        with patch.object(boundary,'publish_floor',side_effect=OSError('fixture disk failure')):
            with self.assertRaisesRegex(OSError,'fixture'):self.service.process_claim(claim,client=self.client)
        h=self.row(row);self.assertTrue(h['subject_removed']);self.assertNotEqual(h['state'],'completed')
        with self.assertRaisesRegex(boundary.RestoreBoundaryError,'in_progress'):boundary.capture_boundary(self.client)
        self.db.execute("update public.account_lifecycles167 set lease_until=clock_timestamp()-interval '1 second' where id=%s",(row['id'],))
        successor=next(c for c in self.claim() if c['id']==row['id'])
        self.assertGreater(successor['generation'],claim['generation'])
        self.assertEqual(self.service.process_claim(successor,client=self.client)['state'],'completed')
        self.assertIsNone(self.row(row));boundary.capture_boundary(self.client)

    def test_concurrent_real_workers_erase_two_accounts_with_shared_control_root(self):
        import subprocess,sys
        other=self.add_user('member')
        first_calendar=self.seed_local_calendar()[0];second_calendar=self.seed_local_calendar(other)[0]
        first=self.enroll('delete');second=self.service.enroll_authorized(user_id=other,actor_id=other,action='delete',client=self.client)
        processes=[subprocess.Popen([sys.executable,'-m','workers.account_lifecycle_worker'],env=self.worker_environment(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        try:
            for process in processes:
                stdout,stderr=process.communicate(timeout=45)
                self.assertEqual(process.returncode,0,stderr[-1800:])
        finally:
            for process in processes:
                if process.poll() is None:process.kill();process.communicate(timeout=5)
        # Cross-account finalization contention is a durable retry, not false
        # completion. Advance only this disposable retry clock, then resume.
        for _ in range(2):
            if self.row(first) is None and self.row(second) is None:break
            self.db.execute("update public.account_lifecycles167 set eligible_at=clock_timestamp() where id in(%s,%s) and state='retry_pending'",(first['id'],second['id']))
            self.run_worker()
        self.assertIsNone(self.row(first));self.assertIsNone(self.row(second))
        self.assertEqual(self.db.execute('select count(*) from public.calendars where id in(%s,%s)',(first_calendar,second_calendar)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from public.users where id=%s',(self.owner,)).fetchone()[0],1)
        from services.account_restore_boundary import capture_boundary
        capture_boundary(self.client)

    def test_unclassified_notification_is_blocked_before_recipient_erasure(self):
        event=str(uuid4())
        self.db.execute("insert into public.notification_events(id,tenant_id,event_type,source_type,title,body) values(%s,%s,'private','unclassified','Private','Private history')",(event,self.tenant))
        self.db.execute("insert into public.user_notifications(tenant_id,event_id,user_id,event_type,title,body) values(%s,%s,%s,'private','Private','Private history')",(self.tenant,event,self.user))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select count(*) from public.user_notifications where event_id=%s',(event,)).fetchone()[0],1)

    def test_calendar_inventory_limit_refuses_before_deleting_rows(self):
        self.db.execute("insert into public.calendar_tasks(tenant_id,owner_user_id,title) select %s,%s,'Bounded fixture '||n from generate_series(1,20001) n",(self.tenant,self.user))
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        result=self.service.process_claim(claim,client=self.client)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error_code'],'account_inventory_limit')
        self.assertFalse(self.row(row)['database_released'])
        self.assertEqual(self.db.execute('select count(*) from public.calendar_tasks where owner_user_id=%s',(self.user,)).fetchone()[0],20001)

    def test_calendar_stale_notification_insert_cannot_recreate_erased_history(self):
        calendar,event,task,notice=self.seed_local_calendar()
        row=self.enroll('delete');claim=next(c for c in self.claim() if c['id']==row['id'])
        self.assertEqual(self.service.process_claim(claim,client=self.client)['state'],'completed')
        with self.assertRaisesRegex(Exception,'resource_unavailable'):
            self.db.execute("insert into public.notification_events(tenant_id,event_type,source_type,source_id,title,body) values(%s,'private','calendar_event',%s,'Stale private','Stale private')",(self.tenant,event))
