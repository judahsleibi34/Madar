"""Real PostgreSQL regression suite. Requires an explicitly marked synthetic DB.

The DSN must be supplied by the isolated rehearsal runner, never by production
configuration. No customer data is needed or copied. Every test cleans its own
synthetic records; the suite refuses an unmarked or non-loopback database.
"""
import concurrent.futures
import json
import os
import threading
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

DSN = os.getenv('COMMERCIAL_SYNTHETIC_DATABASE_DSN')
MARKER = 'madar-commercial-synthetic-rehearsal'


@unittest.skipUnless(DSN, 'explicit synthetic PostgreSQL connection required')
class CommercialLedgerDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = conninfo_to_dict(DSN)
        if params.get('host') not in {'127.0.0.1', 'localhost', '::1'} or params.get('port') not in {'55434','55435'}:
            raise RuntimeError('Refusing a database outside the isolated loopback rehearsal')
        with psycopg.connect(DSN) as conn:
            actual = conn.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]
            if actual != MARKER:
                raise RuntimeError('Refusing an unmarked database')
            if conn.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] != 99:
                raise RuntimeError('Expected rehearsal schema 99')
            # A synthetic bootstrap administrator remains for authenticated E2E.
            # Preserve the real last-administrator safeguard during test cleanup.
            if not conn.execute("select 1 from public.users where user_type='admin' and account_status='active' limit 1").fetchone():
                principal=uuid4()
                conn.execute('insert into auth.users(id) values(%s)', (principal,))
                conn.execute("insert into public.users(auth_id,first_name,last_name,email,user_type,account_status) values(%s,'Synthetic','Bootstrap',%s,'admin','active')", (principal, f'{principal}@example.invalid'))

    def setUp(self):
        self.conn = psycopg.connect(DSN, autocommit=True)
        self.tenants = [self.conn.execute("insert into public.tenants(brand_name,owner_name) values('Synthetic commercial test','Synthetic') returning tenant_id").fetchone()[0] for _ in range(2)]
        self.auth_id = uuid4()
        self.conn.execute('insert into auth.users(id) values(%s)', (self.auth_id,))
        self.actor = self.conn.execute("insert into public.users(auth_id,first_name,last_name,email,user_type,account_status) values(%s,'Synthetic','Admin',%s,'admin','active') returning id", (self.auth_id, f'{self.auth_id}@example.invalid')).fetchone()[0]
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        # Owner-only cleanup in the positively identified disposable database.
        with self.conn.transaction():
            self.conn.execute('delete from public.audit_logs where tenant_id=any(%s)', (self.tenants,))
            self.conn.execute('delete from public.commercial_access_events where tenant_id=any(%s)', (self.tenants,))
            self.conn.execute('delete from public.commercial_access_periods where tenant_id=any(%s)', (self.tenants,))
            self.conn.execute('delete from public.commercial_manual_payments where tenant_id=any(%s)', (self.tenants,))
            self.conn.execute('delete from public.tenant_commercial_state where tenant_id=any(%s)', (self.tenants,))
            self.conn.execute('delete from public.users where id=%s', (self.actor,))
            self.conn.execute('delete from auth.users where id=%s', (self.auth_id,))
            self.conn.execute('delete from public.tenants where tenant_id=any(%s)', (self.tenants,))
        self.conn.close()

    def payload(self, **overrides):
        request = dict(plan_id='business', valid_from=(self.now-timedelta(minutes=1)).isoformat(),
            valid_until=(self.now+timedelta(days=30)).isoformat(), reason='Synthetic regression proof',
            method='cash', actual_minor=2500, currency='USD', billing_months=1,
            paid_at=self.now.isoformat(), receipt_reference='SYNTHETIC-RECEIPT')
        request.update(overrides)
        return {'request': request, 'quote': {'expected_minor':2500,'catalog_version':'test'}}

    def command(self, operation='manual_payment', payload=None, tenant=None, key=None, aal='aal2', conn=None):
        return (conn or self.conn).execute('select public.apply_commercial_access_command(%s,%s,%s,%s,%s,%s,%s)',
            (tenant or self.tenants[0],self.actor,aal,operation,key or uuid4().hex,uuid4().hex,Jsonb(payload or self.payload()))).fetchone()[0]

    def snapshot(self, tenant=None):
        return self.conn.execute('select public.resolve_commercial_access(%s)', (tenant or self.tenants[0],)).fetchone()[0]

    def test_new_tenant_requires_review_and_grants_nothing(self):
        state = self.snapshot()
        self.assertEqual(state['review_state'],'review_required')
        self.assertIsNone(state['period'])
        self.assertEqual(state['addons'],[])

    def test_atomic_payment_period_revision_and_audit(self):
        before = self.snapshot()['revision']
        result = self.command()
        state = self.snapshot()
        self.assertGreater(state['revision'],before)
        self.assertEqual(state['revision'],result['revision'])
        self.assertEqual(state['period']['id'],result['period_id'])
        self.assertEqual(state['period']['manual_payment_id'],result['payment_id'])
        audit = self.conn.execute("select metadata from public.audit_logs where tenant_id=%s and action='admin.commercial.manual_payment'", (self.tenants[0],)).fetchall()
        self.assertEqual(len(audit),1)
        self.assertEqual(audit[0][0]['actual_minor'],2500)
        self.assertNotIn('Synthetic regression proof',json.dumps(audit[0][0]))

    def test_replay_survives_new_connection_and_catalog_change(self):
        key=uuid4().hex; payload=self.payload()
        original=self.command(key=key,payload=payload)
        payload['quote']['expected_minor']=9999
        with psycopg.connect(DSN) as other:
            self.assertEqual(self.command(key=key,payload=payload,conn=other),original)
        self.assertEqual(self.conn.execute('select count(*) from public.commercial_manual_payments where tenant_id=%s',(self.tenants[0],)).fetchone()[0],1)
        payload['request']['actual_minor']=2600
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.command(key=key,payload=payload)

    def test_overlap_rolls_back_receipt_and_revision(self):
        self.command(); state=self.snapshot()
        with self.assertRaises(psycopg.errors.ExclusionViolation): self.command()
        after=self.snapshot()
        self.assertEqual({k:v for k,v in after.items() if k!='effective_at'}, {k:v for k,v in state.items() if k!='effective_at'})
        self.assertEqual(self.conn.execute('select count(*) from public.commercial_manual_payments where tenant_id=%s',(self.tenants[0],)).fetchone()[0],1)

    def test_aal_and_admin_are_both_required(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege): self.command(aal='aal1')
        self.conn.execute("update public.users set user_type='user' where id=%s",(self.actor,))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege): self.command()
        self.assertEqual(self.snapshot()['review_state'],'review_required')

    def test_underpayment_currency_and_invalid_period_fail_atomically(self):
        for changes in ({'actual_minor':1},{'actual_minor':-1},{'currency':'EUR'},
                        {'valid_until':(self.now-timedelta(days=1)).isoformat()}):
            with self.subTest(changes=tuple(changes)):
                with self.assertRaises(psycopg.errors.CheckViolation): self.command(payload=self.payload(**changes))
        self.assertIsNone(self.snapshot()['period'])
        self.command(payload=self.payload(actual_minor=2000,override_reason='Explicit synthetic concession'))

    def test_correction_is_append_only_and_does_not_extend_access(self):
        original=self.command(); period=self.snapshot()['period']
        request=dict(payment_id=original['payment_id'],actual_minor=2000,paid_at=self.now.isoformat(),
                     receipt_reference='CORRECTED',reason='Correct synthetic amount',override_reason='Explicit correction concession')
        correction=self.command('correct_payment',{'request':request,'quote':{}})
        self.assertIsNone(correction['period_id'])
        rows=self.conn.execute('select id,actual_minor,corrects_payment_id from public.commercial_manual_payments where tenant_id=%s order by created_at',(self.tenants[0],)).fetchall()
        self.assertEqual([r[1] for r in rows],[2500,2000])
        self.assertEqual(str(rows[1][2]),original['payment_id'])
        self.assertEqual(self.snapshot()['period'],period)
        with self.assertRaises(psycopg.errors.UniqueViolation): self.command('correct_payment',{'request':request,'quote':{}})

    def test_cross_tenant_references_do_not_disclose_or_mutate(self):
        original=self.command()
        with self.assertRaises(psycopg.errors.NoDataFound):
            self.command('revoke',{'request':{'period_id':original['period_id'],'reason':'Synthetic revoke'},'quote':{}},tenant=self.tenants[1])
        self.assertIsNotNone(self.snapshot()['period'])
        self.assertIsNone(self.snapshot(self.tenants[1])['period'])

    def test_revocation_drops_current_access_and_keeps_history(self):
        original=self.command(); before=self.snapshot()['revision']
        self.command('revoke',{'request':{'period_id':original['period_id'],'reason':'Synthetic revoke'},'quote':{}})
        state=self.snapshot()
        self.assertIsNone(state['period']); self.assertTrue(state['has_history']); self.assertGreater(state['revision'],before)
        self.assertEqual(self.conn.execute('select count(*) from public.commercial_manual_payments where tenant_id=%s',(self.tenants[0],)).fetchone()[0],1)

    def test_complimentary_is_not_a_payment_and_review_inactive_is_explicit(self):
        self.command('review_inactive',{'request':{'reason':'Reviewed synthetic no access'},'quote':{}})
        self.assertEqual(self.snapshot()['review_state'],'reviewed')
        result=self.command('complimentary')
        self.assertIsNone(result['payment_id'])
        self.assertEqual(self.snapshot()['period']['source_type'],'complimentary')
        with self.assertRaises(psycopg.errors.UniqueViolation): self.command('review_inactive',{'request':{'reason':'Cannot bypass active period'},'quote':{}})

    def test_parallel_idempotency_is_one_effect(self):
        barrier=threading.Barrier(4); key=uuid4().hex
        def run():
            with psycopg.connect(DSN) as conn:
                barrier.wait(timeout=10)
                return self.command(key=key,conn=conn)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:run(),range(4)))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(self.conn.execute('select count(*) from public.commercial_access_events where tenant_id=%s',(self.tenants[0],)).fetchone()[0],1)

    def test_parallel_competing_grants_cannot_overlap(self):
        barrier=threading.Barrier(2)
        def run():
            try:
                with psycopg.connect(DSN) as conn:
                    barrier.wait(timeout=10)
                    self.command(conn=conn)
                return 'granted'
            except psycopg.errors.ExclusionViolation: return 'overlap'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _:run(),range(2))),['granted','overlap'])

    def test_financial_deletion_is_rejected_before_freeze_or_purge(self):
        self.command()
        for kind,user_id,tenant_id in [('tenant',None,self.tenants[0]),('user',self.actor,None)]:
            with self.assertRaises(psycopg.errors.RaiseException) as caught:
                self.conn.execute('select public.create_data_deletion_request(%s,%s,%s,%s,null)',(kind,user_id,tenant_id,self.actor))
            self.assertEqual(caught.exception.diag.message_primary,'commercial_financial_retention_review_required')
        self.assertEqual(self.conn.execute('select lifecycle_state from public.tenants where tenant_id=%s',(self.tenants[0],)).fetchone()[0],'active')
        self.assertEqual(self.conn.execute('select account_status from public.users where id=%s',(self.actor,)).fetchone()[0],'active')
        self.assertEqual(self.conn.execute('select count(*) from public.data_deletion_requests where target_tenant_id_snapshot=any(%s) or target_user_id_snapshot=%s',(self.tenants,self.actor)).fetchone()[0],0)
        self.assertIsNotNone(self.snapshot()['period'])

    def test_service_cannot_rewrite_financial_history_and_public_cannot_read(self):
        self.command()
        for role in ['anon','authenticated','service_role']:
            with self.subTest(role=role):
                with self.conn.transaction():
                    self.conn.execute('set local role '+role)
                    if role!='service_role':
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            with self.conn.transaction(): self.conn.execute('select * from public.commercial_manual_payments')
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            with self.conn.transaction(): self.conn.execute('select public.resolve_commercial_access(%s)',(self.tenants[0],))
                    for query in ['delete from public.commercial_manual_payments','update public.commercial_access_events set revision=0', 'update public.commercial_access_periods set revoked_at=now()']:
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            with self.conn.transaction(): self.conn.execute(query)

if __name__=='__main__': unittest.main(verbosity=2)
