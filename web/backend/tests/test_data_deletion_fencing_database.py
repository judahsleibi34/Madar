"""Native150 ownership acceptance; all DB effects use independent connections.

Only the marked disposable harness may run this module. External Auth/Storage
boundaries in full workflow tests are synthetic, never production credentials.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import os
import time
import unittest
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from tests.disposable_database_support import connect_disposable_database

DSN = os.getenv('DELETION_FENCING_SYNTHETIC_DATABASE_DSN')
MIGRATION = Path(os.getenv('DELETION_MIGRATION_SQL', '/migration150.sql'))


def connect():
    db = connect_disposable_database(DSN, markers={'madar-notification-synthetic-rehearsal'})
    db.execute("set statement_timeout='10s'")
    return db


RPCS = {'claim_data_deletion_requests_v2', 'transition_data_deletion_v2',
        'run_data_deletion_local_step_v2', 'data_deletion_effect_v2',
        'cancel_data_deletion_request_v2', 'create_data_deletion_request',
        'data_deletion_ownership_protocol'}


def rpc(name, body, db=None):
    if name not in RPCS:
        raise AssertionError('Unknown or legacy deletion RPC')
    owned = db is None
    db = db or connect()
    try:
        db.execute('set role service_role')
        args = sql.SQL(',').join(sql.SQL('{}=>%s').format(sql.Identifier(key)) for key in body)
        values = [Jsonb(value) if isinstance(value, (dict, list)) else value for value in body.values()]
        query = sql.SQL('select to_jsonb(x) from public.{}({}) x').format(sql.Identifier(name), args)
        rows = [row[0] for row in db.execute(query, values)]
        return rows if name == 'claim_data_deletion_requests_v2' else rows[0]
    finally:
        if owned:
            db.close()


class SqlQuery:
    def __init__(self, table):
        self.table_name, self.filters, self.sort, self.maximum = table, [], None, None
        if table not in {'data_deletion_requests','data_deletion_steps','data_deletion_subjects','data_deletion_resources','users','tenants','website_settings','calendar_sync_connections'}:
            raise AssertionError('Read-only synthetic bridge table outside workflow')
    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append((key, '=', value)); return self
    def in_(self, key, values): self.filters.append((key, '= any', values)); return self
    def limit(self, n): self.maximum = n; return self
    def order(self, key, **_kwargs): self.sort = key; return self
    def execute(self):
        query = sql.SQL('select to_jsonb(t) from public.{} t').format(sql.Identifier(self.table_name))
        values=[]
        if self.filters:
            query += sql.SQL(' where ') + sql.SQL(' and ').join(sql.SQL('{} {} (%s)').format(sql.Identifier(k),sql.SQL(op)) for k,op,_ in self.filters)
            values = [v for _,_,v in self.filters]
        if self.sort: query += sql.SQL(' order by {}').format(sql.Identifier(self.sort))
        if self.maximum is not None: query += sql.SQL(' limit %s'); values.append(self.maximum)
        with connect() as db:
            db.execute('set role service_role')
            return SimpleNamespace(data=[row[0] for row in db.execute(query,values)])


class SqlClient:
    def __init__(self):
        self.deleted_auth=[]
        self.auth=SimpleNamespace(admin=SimpleNamespace(delete_user=self.deleted_auth.append,
            get_user_by_id=lambda _id: (_ for _ in ()).throw(type('SyntheticAbsent',(Exception,),{'status_code':404})())))
    def table(self,name): return SqlQuery(name)
    def rpc(self,name,body): return SimpleNamespace(execute=lambda: SimpleNamespace(data=rpc(name,body)))


@unittest.skipUnless(DSN,'Requires marked disposable PostgreSQL')
class Deletion150UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(); self.addCleanup(self.db.close)
        self.assertEqual(self.version(),149)
    def version(self): return self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
    def body(self):
        return MIGRATION.read_text().replace('begin;','',1).rsplit('commit;',1)[0]
    def test_processing_request_and_orphan_step_reject(self):
        for processing_step in (False,True):
            key=uuid4()
            self.db.execute("insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot,state) values(%s,'user',2147483005,%s)",(key,'pending' if processing_step else 'in_progress'))
            if processing_step: self.db.execute("insert into public.data_deletion_steps(request_id,step_key,step_order,state) values(%s,'freeze',10,'processing')",(key,))
            try:
                with self.assertRaisesRegex(psycopg.Error,'migration_150_requires_reconciled_deletion_work'): self.db.execute(MIGRATION.read_text())
                self.db.execute('rollback'); self.assertEqual(self.version(),149)
            finally: self.db.execute('delete from public.data_deletion_requests where id=%s',(key,))
    def test_rollback_and_disconnect_preserve_schema_acl_and_functions(self):
        for disconnect in (False,True):
            db=connect(); db.execute('begin;'+self.body())
            self.assertEqual(db.execute('select public.data_deletion_ownership_protocol()').fetchone()[0],2)
            if disconnect: db.close()
            else: db.execute('rollback'); db.close()
            self.assertEqual(self.version(),149)
            self.assertIsNone(self.db.execute("select to_regprocedure('public.data_deletion_ownership_protocol()')").fetchone()[0])
            self.assertTrue(self.db.execute("select has_table_privilege('service_role','public.data_deletion_requests','UPDATE')").fetchone()[0])
    def test_wrong_origin_refuses(self):
        self.db.execute("begin;update public.application_schema_state set schema_version=148 where contract_key='core'")
        with self.assertRaisesRegex(psycopg.Error,'migration_150_expected_schema_149'): self.db.execute(MIGRATION.read_text())
        self.db.execute('rollback'); self.assertEqual(self.version(),149)
    def test_zz_apply_and_reentry_reject(self):
        self.db.execute(MIGRATION.read_text())
        self.assertEqual(self.version(),150)
        with self.assertRaisesRegex(psycopg.Error,'migration_150_expected_schema_149'): self.db.execute(MIGRATION.read_text())
        self.db.execute('rollback'); self.assertEqual(self.version(),150)


@unittest.skipUnless(DSN,'Requires marked disposable PostgreSQL')
class Deletion150OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(); self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute('select public.data_deletion_ownership_protocol()').fetchone()[0],2)
        self.key=str(uuid4()); self.ids=[self.key]
        self.db.execute("insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot) values(%s,'user',2147483001)",(self.key,))
        self.step_id=self.db.execute("insert into public.data_deletion_steps(request_id,step_key,step_order) values(%s,'revoke_integrations',30) returning id",(self.key,)).fetchone()[0]
        self.addCleanup(self.cleanup)
    def cleanup(self):
        self.db.execute('rollback'); self.db.execute('reset role')
        for key in self.ids: self.db.execute('delete from public.data_deletion_requests where id=%s',(key,))
    def claim(self,owner='A'):
        return next(x for x in rpc('claim_data_deletion_requests_v2',{'p_worker_id':owner,'p_limit':25,'p_lease_seconds':300}) if x['id']==self.key)
    def expire(self): self.db.execute("update public.data_deletion_requests set lease_until=clock_timestamp()-interval '1 second' where id=%s",(self.key,))
    def args(self,r): return {'p_request_id':r['id'],'p_owner':r['lease_owner'],'p_generation':r['claim_generation'],'p_attempt':r['attempt_count']}
    def transition(self,r,action,step=None,data=None,db=None):
        return rpc('transition_data_deletion_v2',{**self.args(r),'p_action':action,'p_step_id':(step or {}).get('id'),'p_step_attempt':(step or {}).get('attempts'),'p_data':data or {}},db)
    def current(self): return self.db.execute('select to_jsonb(r) from public.data_deletion_requests r where id=%s',(self.key,)).fetchone()[0]
    def step(self): return self.db.execute('select to_jsonb(s) from public.data_deletion_steps s where id=%s',(self.step_id,)).fetchone()[0]
    def successor(self):
        old=self.claim(); oldstep=self.transition(old,'begin'); self.expire(); new=self.claim('B'); newstep=self.transition(new,'begin')
        return old,oldstep,new,newstep
    def test_stale_failure_cannot_clear_successor_request_lease(self):
        a,sa,b,sb=self.successor(); before=self.current(); stepbefore=self.step()
        with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'): self.transition(a,'fail',sa,{'code':'synthetic_failure','retryable':True})
        self.assertEqual(self.current(),before); self.assertEqual(self.step(),stepbefore)
    def test_stale_finalization_cannot_complete_successor_request(self):
        a,sa,b,sb=self.successor(); self.db.execute("update public.data_deletion_steps set step_key='finalize' where id=%s",(self.step_id,)); self.db.execute("update public.data_deletion_requests set verification_status='verified' where id=%s",(self.key,)); before=self.current()
        with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'): self.transition(a,'complete',sa)
        self.assertEqual(self.current(),before)
    def test_stale_step_completion_cannot_overwrite_successor_step(self):
        a,sa,b,sb=self.successor(); before=self.step()
        with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'): self.transition(a,'complete',sa,{'stale_output':True})
        self.assertEqual(self.step(),before)
    def test_wrong_missing_generation_owner_attempt_and_step_attempt_reject(self):
        a=self.claim(); sa=self.transition(a,'begin'); before=(self.current(),self.step())
        for key,value in [('claim_generation',None),('claim_generation',0),('claim_generation',a['claim_generation']+1),('attempt_count',a['attempt_count']+1),('lease_owner','wrong')]:
            with self.subTest(key=key,value=value),self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'): self.transition({**a,key:value},'complete',sa)
        with self.assertRaisesRegex(psycopg.Error,'deletion_step_claim_lost'): self.transition(a,'complete',{**sa,'attempts':sa['attempts']+1})
        self.assertEqual((self.current(),self.step()),before)
    def test_two_claimers_only_one_owner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(lambda owner:rpc('claim_data_deletion_requests_v2',{'p_worker_id':owner,'p_limit':25,'p_lease_seconds':300}),['A','B']))
        claimed=[r for batch in rows for r in batch if r['id']==self.key]
        self.assertEqual(len(claimed),1);self.assertEqual(claimed[0]['claim_generation'],1)
    def test_lease_expiry_during_request_lock_wait_rejects(self):
        a=self.claim();sa=self.transition(a,'begin')
        self.db.execute("update public.data_deletion_requests set lease_until=clock_timestamp()+interval '.4 seconds' where id=%s",(self.key,))
        lock=connect();lock.execute('begin');lock.execute('select 1 from public.data_deletion_requests where id=%s for update',(self.key,))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.transition,a,'complete',sa)
            time.sleep(.6);lock.execute('commit');lock.close()
            with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'):future.result(timeout=5)
        self.assertEqual(self.step()['state'],'processing')
    def test_lease_expiry_during_step_lock_wait_rejects_and_rolls_back(self):
        a=self.claim();sa=self.transition(a,'begin')
        self.db.execute("update public.data_deletion_requests set lease_until=clock_timestamp()+interval '.4 seconds' where id=%s",(self.key,))
        lock=connect();lock.execute('begin');lock.execute('select 1 from public.data_deletion_steps where id=%s for update',(self.step_id,))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.transition,a,'complete',sa)
            time.sleep(.6);lock.execute('commit');lock.close()
            with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'):future.result(timeout=5)
        self.assertEqual(self.step()['state'],'processing')
    def test_duplicate_and_concurrent_completion_do_not_overwrite_output(self):
        a=self.claim();sa=self.transition(a,'begin')
        def complete(value):
            try:self.transition(a,'complete',sa,{'winner':value});return True
            except psycopg.Error:return False
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(complete,[1,2]))
        self.assertEqual(results.count(True),1);before=self.step()
        with self.assertRaisesRegex(psycopg.Error,'deletion_step_claim_lost'):self.transition(a,'complete',sa,{'overwrite':True})
        self.assertEqual(self.step(),before)
    def test_crash_before_commit_rolls_back_and_lost_reply_after_commit_not_replayed(self):
        a=self.claim();sa=self.transition(a,'begin');db=connect();db.execute('begin');self.transition(a,'complete',sa,{'result':1},db);db.close()
        self.assertEqual(self.step()['state'],'processing')
        db=connect();db.execute('begin');self.transition(a,'complete',sa,{'result':2},db);db.execute('commit');db.close()
        with self.assertRaisesRegex(psycopg.Error,'deletion_step_claim_lost'): self.transition(a,'complete',sa,{'result':3})
        self.assertEqual(self.step()['output_safe'],{'result':2})
    def test_retry_and_exhaustion_do_not_reset_attempts(self):
        a=self.claim();sa=self.transition(a,'begin');self.transition(a,'fail',sa,{'code':'synthetic_retry','retryable':True})
        self.assertEqual(self.current()['state'],'waiting_retry');self.assertIsNotNone(self.current()['retry_after'])
        self.db.execute("update public.data_deletion_requests set retry_after=clock_timestamp()-interval '1second' where id=%s",(self.key,))
        b=self.claim('B');sb=self.transition(b,'begin');self.assertEqual(sb['attempts'],sa['attempts']+1)
        self.transition(b,'fail',sb,{'code':'synthetic_manual','retryable':False});self.assertEqual(self.current()['state'],'failed_manual_intervention')
    def test_same_worker_id_restart_cannot_reuse_old_generation(self):
        a=self.claim('same');self.expire();b=self.claim('same');self.assertGreater(b['claim_generation'],a['claim_generation'])
        with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'):self.transition(a,'begin')
    def test_finalization_requires_all_steps_and_authoritative_verification(self):
        self.db.execute("update public.data_deletion_steps set step_key='finalize',step_order=100 where id=%s",(self.step_id,))
        a=self.claim();sa=self.transition(a,'begin')
        with self.assertRaisesRegex(psycopg.Error,'deletion_verification_required'):self.transition(a,'complete',sa)
        self.db.execute("update public.data_deletion_requests set verification_status='verified' where id=%s",(self.key,))
        self.db.execute("insert into public.data_deletion_steps(request_id,step_key,step_order) values(%s,'verify',90)",(self.key,))
        with self.assertRaisesRegex(psycopg.Error,'deletion_verification_required'):self.transition(a,'complete',sa)
    def test_direct_mutations_and_legacy_rpc_denied_to_actual_service_role(self):
        for table in ('data_deletion_requests','data_deletion_steps','data_deletion_resources','data_deletion_subjects','data_deletion_effects'):
            with connect() as db:
                db.execute('set role service_role')
                for permission in ('INSERT','UPDATE','DELETE','TRUNCATE'):
                    self.assertFalse(db.execute('select has_table_privilege(current_user,%s,%s)',('public.'+table,permission)).fetchone()[0])
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):db.execute(sql.SQL('delete from public.{} where false').format(sql.Identifier(table)))
        with connect() as db:
            db.execute('set role service_role')
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):db.execute("select public.claim_data_deletion_requests('legacy',1,clock_timestamp(),30)")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):db.execute('select public.deletion_owned_150(%s,%s,1,1)',(self.key,'A'))
    def test_cancellation_before_claim_and_claim_first_are_atomic(self):
        result=rpc('cancel_data_deletion_request_v2',{'p_request_id':self.key});self.assertEqual(result['state'],'cancelled_before_execution')
        rows=rpc('claim_data_deletion_requests_v2',{'p_worker_id':'B','p_limit':25,'p_lease_seconds':300});self.assertNotIn(self.key,[x['id'] for x in rows])
    def test_cancellation_after_claim_cannot_unfreeze_or_clear_owner(self):
        a=self.claim();before=self.current()
        with self.assertRaisesRegex(psycopg.Error,'deletion_cannot_be_cancelled'):rpc('cancel_data_deletion_request_v2',{'p_request_id':self.key})
        self.assertEqual(self.current(),before)
    def test_cross_request_step_rejected_and_step_order_preserved(self):
        foreign=str(uuid4());self.ids.append(foreign)
        self.db.execute("insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot) values(%s,'user',2147483002)",(foreign,))
        fid=self.db.execute("insert into public.data_deletion_steps(request_id,step_key,step_order) values(%s,'revoke_integrations',30) returning id",(foreign,)).fetchone()[0]
        a=self.claim();sa=self.transition(a,'begin')
        with self.assertRaisesRegex(psycopg.Error,'deletion_step_claim_lost'):self.transition(a,'complete',{'id':fid,'attempts':1})
        self.assertEqual(sa['step_key'],'revoke_integrations')
    def test_repeated_begin_preserves_same_claim_step_attempt(self):
        a=self.claim();first=self.transition(a,'begin');second=self.transition(a,'begin')
        self.assertEqual(second,first);self.assertEqual(self.current()['state'],'in_progress')
    def test_finalization_rejects_missing_authoritative_plan_even_when_verified(self):
        self.db.execute("update public.data_deletion_steps set step_key='finalize',step_order=100 where id=%s",(self.step_id,))
        self.db.execute("update public.data_deletion_requests set verification_status='verified' where id=%s",(self.key,))
        a=self.claim();sa=self.transition(a,'begin')
        with self.assertRaisesRegex(psycopg.Error,'deletion_verification_required'):self.transition(a,'complete',sa)
        self.assertEqual(self.current()['state'],'in_progress')
    def test_durable_intent_unknown_outcome_is_not_retried_after_reclaim(self):
        self.db.execute("update public.data_deletion_steps set step_key='delete_auth_identities' where id=%s",(self.step_id,))
        self.db.execute("insert into public.data_deletion_subjects(request_id,user_id_snapshot,subject_kind) values(%s,2147483001,'primary_user')",(self.key,))
        a=self.claim();sa=self.transition(a,'begin')
        args={**self.args(a),'p_step_id':sa['id'],'p_step_attempt':sa['attempts'],'p_kind':'subject','p_target':'2147483001','p_action':'intent'}
        intent=rpc('data_deletion_effect_v2',args);self.assertIn('idempotency_key',intent)
        with self.assertRaisesRegex(psycopg.Error,'deletion_external_outcome_uncertain'):rpc('data_deletion_effect_v2',args)
        self.expire();rows=rpc('claim_data_deletion_requests_v2',{'p_worker_id':'B','p_limit':25,'p_lease_seconds':300});self.assertNotIn(self.key,[x['id'] for x in rows])
        self.assertEqual(self.current()['state'],'failed_manual_intervention')
        with self.assertRaisesRegex(psycopg.Error,'deletion_claim_lost'):rpc('data_deletion_effect_v2',{**args,'p_action':'confirm','p_outcome':'deleted'})
    def test_confirmed_effect_is_replay_safe_and_foreign_target_rejected(self):
        self.db.execute("update public.data_deletion_steps set step_key='delete_auth_identities' where id=%s",(self.step_id,))
        self.db.execute("insert into public.data_deletion_subjects(request_id,user_id_snapshot,subject_kind) values(%s,2147483001,'primary_user')",(self.key,))
        a=self.claim();sa=self.transition(a,'begin');args={**self.args(a),'p_step_id':sa['id'],'p_step_attempt':sa['attempts'],'p_kind':'subject','p_target':'2147483001','p_action':'intent'}
        with self.assertRaisesRegex(psycopg.Error,'deletion_effect_scope_invalid'):rpc('data_deletion_effect_v2',{**args,'p_target':'2147483002'})
        rpc('data_deletion_effect_v2',args);rpc('data_deletion_effect_v2',{**args,'p_action':'confirm','p_outcome':'absent'})
        self.assertTrue(rpc('data_deletion_effect_v2',args)['already_confirmed']);self.transition(a,'complete',sa,{'confirmed':True})
    def test_stale_application_service_helpers_never_mutate_successor(self):
        from services import data_deletion_service as lifecycle
        a,sa,b,sb=self.successor();before=(self.current(),self.step());client=SqlClient()
        for action in ('failure','finish'):
            with self.subTest(action=action),self.assertRaises(lifecycle.DeletionOwnershipLost):
                if action=='failure':lifecycle._fail_step(a,sa,lifecycle.DeletionStepError('synthetic_failure'),client=client)
                else:lifecycle._finish_step({**sa,'_claim':a},{'stale':True},client=client)
        self.assertEqual((self.current(),self.step()),before)

    def test_effect_identity_aliases_cannot_create_duplicate_intents(self):
        self.db.execute("update public.data_deletion_steps set step_key='delete_provider_objects' where id=%s",(self.step_id,))
        token=uuid4()
        self.db.execute("insert into public.data_deletion_subjects(request_id,user_id_snapshot,auth_id,subject_kind) values(%s,2147483001,%s,'primary_user')",(self.key,token))
        resource=self.db.execute("insert into public.data_deletion_resources(request_id,resource_kind,resource_key) values(%s,'supabase_avatar',%s) returning id",(self.key,'users/'+str(token)+'/avatar.png')).fetchone()[0]
        a=self.claim();sa=self.transition(a,'begin');args={**self.args(a),'p_step_id':sa['id'],'p_step_attempt':sa['attempts'],'p_kind':'resource','p_target':str(resource),'p_action':'intent'}
        rpc('data_deletion_effect_v2',args)
        with self.assertRaisesRegex(psycopg.Error,'deletion_external_outcome_uncertain'):rpc('data_deletion_effect_v2',{**args,'p_target':'000'+str(resource)})
        self.assertEqual(self.db.execute('select count(*) from public.data_deletion_effects where request_id=%s',(self.key,)).fetchone()[0],1)
        rpc('data_deletion_effect_v2',{**args,'p_action':'confirm','p_outcome':'deleted'})
        self.assertTrue(rpc('data_deletion_effect_v2',{**args,'p_target':'000'+str(resource)})['already_confirmed'])
    def test_request_attempt_exhaustion_and_step_exhaustion_require_manual(self):
        self.db.execute('update public.data_deletion_requests set attempt_count=max_attempts where id=%s',(self.key,))
        self.assertNotIn(self.key,[x['id'] for x in rpc('claim_data_deletion_requests_v2',{'p_worker_id':'A','p_limit':25,'p_lease_seconds':300})])
        self.assertEqual(self.current()['state'],'failed_manual_intervention')
    def test_resource_scope_cannot_cross_host_tenant_namespace(self):
        self.db.execute("update public.data_deletion_steps set step_key='delete_host_files' where id=%s",(self.step_id,))
        resource=self.db.execute("insert into public.data_deletion_resources(request_id,resource_kind,resource_key) values(%s,'host_dataset','tenant_44/user_12/synthetic.csv') returning id",(self.key,)).fetchone()[0]
        a=self.claim();sa=self.transition(a,'begin')
        with self.assertRaisesRegex(psycopg.Error,'deletion_effect_scope_invalid'):rpc('data_deletion_effect_v2',{**self.args(a),'p_step_id':sa['id'],'p_step_attempt':sa['attempts'],'p_kind':'resource','p_target':str(resource),'p_action':'intent'})
        self.assertEqual(self.db.execute('select count(*) from public.data_deletion_effects where request_id=%s',(self.key,)).fetchone()[0],0)


@unittest.skipUnless(DSN,'Requires marked disposable PostgreSQL')
class Deletion150WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db=connect();self.addCleanup(self.db.close);self.request_ids=[];self.owners=[]
        self.addCleanup(self.cleanup)
        self.tenant,self.user,self.auth=self.owner()
        self.other_tenant,self.other_user,self.other_auth=self.owner()
    def owner(self,status='active'):
        token=uuid4();tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Synthetic deletion150','Fixture') returning tenant_id").fetchone()[0]
        self.db.execute('insert into auth.users(id,email,email_confirmed_at) values(%s,%s,clock_timestamp())',(token,str(token)+'@example.invalid'))
        user=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified) values(%s,'Synthetic','Fixture',%s,%s,%s,true) returning id",(token,str(token)+'@example.invalid',tenant,status)).fetchone()[0]
        self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(tenant,user,token))
        self.owners.append((tenant,user,token));return tenant,user,token
    def cleanup(self):
        self.db.execute('rollback');self.db.execute('reset role')
        for key in self.request_ids:self.db.execute('delete from public.data_deletion_requests where id=%s',(key,))
        for tenant,user,token in self.owners:
            self.db.execute('delete from public.users where tenant_id=%s',(tenant,));self.db.execute('delete from public.tenants where tenant_id=%s',(tenant,));self.db.execute('delete from auth.users where id=%s',(token,))
    def request(self,kind='user',requester=None):
        if kind=='user':
            # Retained last-owner invariant requires transfer before self closure.
            self.db.execute("update public.tenant_memberships set role='member' where user_id=%s",(self.user,))
        result=rpc('create_data_deletion_request',{'p_request_type':kind,'p_target_user_id':self.user if kind=='user' else None,'p_target_tenant_id':self.tenant if kind=='tenant' else None,'p_requested_by_user_id':requester or self.user,'p_retention_until':None})
        self.request_ids.append(result['id']);return result
    def claimed(self,key):
        return next(x for x in rpc('claim_data_deletion_requests_v2',{'p_worker_id':'workflow-worker','p_limit':25,'p_lease_seconds':300}) if x['id']==key)
    def verify_foreign_unchanged(self):
        self.assertEqual(self.db.execute('select account_status from public.users where id=%s',(self.other_user,)).fetchone()[0],'active')
        self.assertEqual(self.db.execute('select lifecycle_state from public.tenants where tenant_id=%s',(self.other_tenant,)).fetchone()[0],'active')
    def test_user_full_workflow_real_database_synthetic_auth(self):
        from services import data_deletion_service as lifecycle
        request=self.request();client=SqlClient();result=lifecycle.process_deletion_request(self.claimed(request['id']),client=client)
        self.assertEqual(result['state'],'completed_with_retained_records');self.assertEqual(result['verification_status'],'verified_with_retained_records')
        self.assertEqual(client.deleted_auth,[str(self.auth)]);self.assertIsNone(self.db.execute('select id from public.users where id=%s',(self.user,)).fetchone())
        self.assertEqual(self.db.execute("select count(*) from public.data_deletion_steps where request_id=%s and state='completed'",(request['id'],)).fetchone()[0],10)
        self.assertEqual(self.db.execute("select count(*) from public.data_deletion_effects where request_id=%s and state='confirmed'",(request['id'],)).fetchone()[0],1)
        self.verify_foreign_unchanged()
    def test_tenant_full_workflow_and_notification_cancellation(self):
        from services import data_deletion_service as lifecycle
        own,foreign=uuid4(),uuid4()
        self.db.execute("insert into public.notification_outbox(id,tenant_id,channel,template) values(%s,%s,'email','synthetic'),(%s,%s,'email','synthetic')",(own,self.tenant,foreign,self.other_tenant))
        request=self.request('tenant');client=SqlClient();result=lifecycle.process_deletion_request(self.claimed(request['id']),client=client)
        self.assertEqual(result['state'],'completed_with_retained_records');self.assertIsNone(self.db.execute('select tenant_id from public.tenants where tenant_id=%s',(self.tenant,)).fetchone())
        # Tenant deletion may cascade owned outbox; foreign queue must survive.
        self.assertEqual(self.db.execute('select status from public.notification_outbox where id=%s',(foreign,)).fetchone()[0],'pending')
        self.assertEqual(client.deleted_auth,[str(self.auth)]);self.verify_foreign_unchanged()
    def test_auth_lost_response_blocks_without_automatic_replay(self):
        from services import data_deletion_service as lifecycle
        request=self.request();client=SqlClient();calls=[]
        def accepted_then_lost(auth_id):calls.append(auth_id);raise TimeoutError('synthetic lost response')
        client.auth.admin.delete_user=accepted_then_lost
        result=lifecycle.process_deletion_request(self.claimed(request['id']),client=client)
        self.assertEqual(result['state'],'failed_manual_intervention');self.assertEqual(result['last_error_code'],'auth_outcome_uncertain')
        self.assertEqual(len(calls),1);self.assertEqual(self.db.execute('select state from public.data_deletion_effects where request_id=%s',(request['id'],)).fetchone()[0],'intent')
        self.assertNotIn(request['id'],[x['id'] for x in rpc('claim_data_deletion_requests_v2',{'p_worker_id':'restarted','p_limit':25,'p_lease_seconds':300})]);self.assertEqual(len(calls),1)
        self.verify_foreign_unchanged()
    def test_tenant_cancellation_preserves_original_disabled_status(self):
        token=uuid4()
        self.db.execute('insert into auth.users(id,email) values(%s,%s)',(token,str(token)+'@example.invalid'))
        disabled=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status) values(%s,'Synthetic','Disabled',%s,%s,'disabled') returning id",(token,str(token)+'@example.invalid',self.tenant)).fetchone()[0]
        self.owners.append((self.tenant,disabled,token))
        request=self.request('tenant')
        self.assertEqual(self.db.execute('select account_status_snapshot from public.data_deletion_subjects where request_id=%s and user_id_snapshot=%s',(request['id'],disabled)).fetchone()[0],'disabled')
        rpc('cancel_data_deletion_request_v2',{'p_request_id':request['id']})
        self.assertEqual(self.db.execute('select account_status from public.users where id=%s',(disabled,)).fetchone()[0],'disabled')
        self.assertEqual(self.db.execute('select lifecycle_state from public.tenants where tenant_id=%s',(self.tenant,)).fetchone()[0],'active')
    def test_foreign_requester_and_revoked_owner_denied(self):
        with self.assertRaisesRegex(psycopg.Error,'deletion_request_unauthorized'):self.request('tenant',self.other_user)
        self.db.execute("update public.tenant_memberships set status='disabled' where user_id=%s",(self.user,))
        with self.assertRaisesRegex(psycopg.Error,'deletion_request_unauthorized'):self.request('tenant')
        self.verify_foreign_unchanged()
    def test_local_step_cannot_complete_without_authoritative_operation(self):
        request=self.request();claim=self.claimed(request['id']);args={'p_request_id':claim['id'],'p_owner':claim['lease_owner'],'p_generation':claim['claim_generation'],'p_attempt':claim['attempt_count']}
        step=rpc('transition_data_deletion_v2',{**args,'p_action':'begin'})
        with self.assertRaisesRegex(psycopg.Error,'deletion_local_step_not_applied'):rpc('transition_data_deletion_v2',{**args,'p_action':'complete','p_step_id':step['id'],'p_step_attempt':step['attempts']})
        self.assertEqual(self.db.execute('select state from public.data_deletion_steps where id=%s',(step['id'],)).fetchone()[0],'processing')
    def test_idempotent_freeze_crash_can_resume_under_successor(self):
        request=self.request();a=self.claimed(request['id']);args={'p_request_id':a['id'],'p_owner':a['lease_owner'],'p_generation':a['claim_generation'],'p_attempt':a['attempt_count']}
        first=rpc('transition_data_deletion_v2',{**args,'p_action':'begin'})
        self.assertEqual(first['step_key'],'freeze')
        self.db.execute("update public.data_deletion_requests set lease_until=clock_timestamp()-interval '1 second' where id=%s",(request['id'],))
        b=self.claimed(request['id']);second=rpc('transition_data_deletion_v2',{'p_request_id':b['id'],'p_owner':b['lease_owner'],'p_generation':b['claim_generation'],'p_attempt':b['attempt_count'],'p_action':'begin'})
        self.assertFalse(second.get('blocked',False),'Idempotent freeze must not become permanently stuck after a crash')
        self.assertEqual(second['step_key'],'freeze');self.assertGreater(second['claim_generation'],first['claim_generation'])
    def test_two_owners_cannot_both_enter_user_deletion(self):
        token=uuid4();self.db.execute('insert into auth.users(id,email) values(%s,%s)',(token,str(token)+'@example.invalid'))
        second=self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status) values(%s,'Synthetic','SecondOwner',%s,%s,'active') returning id",(token,str(token)+'@example.invalid',self.tenant)).fetchone()[0]
        self.owners.append((self.tenant,second,token));self.db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(self.tenant,second,token))
        first=rpc('create_data_deletion_request',{'p_request_type':'user','p_target_user_id':self.user,'p_target_tenant_id':None,'p_requested_by_user_id':self.user,'p_retention_until':None});self.request_ids.append(first['id'])
        with self.assertRaisesRegex(psycopg.Error,'tenant_owner_requires_tenant_deletion'):
            result=rpc('create_data_deletion_request',{'p_request_type':'user','p_target_user_id':second,'p_target_tenant_id':None,'p_requested_by_user_id':second,'p_retention_until':None});self.request_ids.append(result['id'])
        self.assertEqual(self.db.execute('select account_status from public.users where id=%s',(second,)).fetchone()[0],'active')
    def test_user_resource_confirmation_releases_tenant_quota_and_registry(self):
        from services import data_deletion_service as lifecycle
        key='users/'+str(self.auth)+'/synthetic.png'
        self.db.execute("insert into public.storage_accounts(tenant_id,scope_key,quota_bytes,used_bytes) values(%s,'tenant',100,5)",(self.tenant,))
        self.db.execute("insert into public.storage_objects(tenant_id,user_id,category,storage_key,size_bytes) values(%s,%s,'avatar',%s,5)",(self.tenant,self.user,key))
        request=self.request();client=SqlClient();client.storage=SimpleNamespace(from_=lambda _bucket:SimpleNamespace(remove=lambda _keys:None,list=lambda *_args:[]))
        result=lifecycle.process_deletion_request(self.claimed(request['id']),client=client)
        self.assertEqual(result['state'],'completed_with_retained_records')
        self.assertEqual(self.db.execute("select used_bytes from public.storage_accounts where tenant_id=%s and scope_key='tenant'",(self.tenant,)).fetchone()[0],0)
        self.assertEqual(self.db.execute('select status from public.storage_objects where tenant_id=%s and storage_key=%s',(self.tenant,key)).fetchone()[0],'deleted')
        self.verify_foreign_unchanged()

def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite([loader.loadTestsFromTestCase(Deletion150UpgradeTests),loader.loadTestsFromTestCase(Deletion150OwnershipTests),loader.loadTestsFromTestCase(Deletion150WorkflowTests)])


if __name__=='__main__':unittest.main(verbosity=2)
