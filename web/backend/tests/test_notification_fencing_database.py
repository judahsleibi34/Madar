"""Native PostgreSQL claim/finish races; requires an owned disposable database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
from tests.disposable_database_support import connect_disposable_database

DSN = os.getenv("NOTIFICATION_SYNTHETIC_DATABASE_DSN")
MARKERS = {"madar-notification-synthetic-rehearsal"}
MIGRATION = Path(os.getenv("NOTIFICATION_MIGRATION_SQL", "/migration147.sql"))


def connect():
    connection = connect_disposable_database(DSN, markers=MARKERS)
    connection.execute("set statement_timeout='8s'")
    return connection


class RpcError(RuntimeError):
    def __init__(self, error):
        self.message = error.diag.message_primary
        super().__init__(self.message)


class SqlRpcClient:
    """Execute real PostgreSQL functions with the same named RPC arguments."""
    def rpc(self, name, body):
        allowed = {"claim_notification_deliveries_v2", "finish_notification_delivery_v2", "notification_delivery_protocol"}
        if name not in allowed:
            raise AssertionError("Unfenced RPC must never be selected")
        from psycopg import sql
        class Response:
            def execute(inner):
                with connect() as db:
                    try:
                        db.execute("set role service_role")
                        arguments = sql.SQL(',').join(sql.SQL('{}=>%s').format(sql.Identifier(key)) for key in body)
                        query = sql.SQL('select to_jsonb(r) from public.{}({}) r').format(sql.Identifier(name), arguments)
                        inner.data = [row[0] for row in db.execute(query, tuple(body.values())).fetchall()]
                        if name == 'notification_delivery_protocol':
                            inner.data = inner.data[0]
                        return inner
                    except psycopg.Error as error:
                        raise RpcError(error) from None
        return Response()


@unittest.skipUnless(DSN, "Requires marked disposable notification PostgreSQL")
class NotificationUpgradeDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],146)
        self.identifier = uuid4()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.db.execute("rollback")
        self.db.execute("delete from public.notification_deliveries where id=%s", (self.identifier,))

    def add_legacy(self):
        self.db.execute("insert into public.notification_deliveries(id,channel,template,deduplication_key) values(%s,'internal','synthetic',%s)", (self.identifier,str(self.identifier)))

    def assert_original(self):
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],146)
        self.assertIsNone(self.db.execute("select to_regprocedure('public.finish_notification_delivery_v2(uuid,bigint,text,text,text,integer,text)')").fetchone()[0])
        self.assertTrue(self.db.execute("select has_table_privilege('service_role','public.notification_deliveries','UPDATE')").fetchone()[0])

    def test_baseline_reproduces_stale_acknowledgement(self):
        self.add_legacy()
        self.db.execute("select public.claim_notification_deliveries(1,clock_timestamp(),30)")
        self.db.execute("update public.notification_deliveries set processing_lease_until=clock_timestamp()-interval '1 second' where id=%s",(self.identifier,))
        self.db.execute("select public.claim_notification_deliveries(1,clock_timestamp(),30)")
        result = self.db.execute("select to_jsonb(public.finish_notification_delivery(%s,'sent'))",(self.identifier,)).fetchone()[0]
        self.assertEqual((result['status'],result['attempts']),('sent',2))
        print("BASELINE schema146 stale attempt1 finish accepted after attempt2 reclaim: reproduced",flush=True)

    def test_live_and_expired_legacy_claims_block_upgrade_without_mutation(self):
        self.add_legacy()
        for expired in (False,True):
            self.db.execute("update public.notification_deliveries set status='processing',processing_lease_until=clock_timestamp()+(%s)::interval where id=%s",('-1 second' if expired else '1 minute',self.identifier))
            with self.assertRaisesRegex(psycopg.Error,'migration_147_requires_drained_deliveries'):
                self.db.execute(MIGRATION.read_text())
            self.db.execute('rollback')
            self.assert_original()
            self.assertEqual(self.db.execute('select status from public.notification_deliveries where id=%s',(self.identifier,)).fetchone()[0],'processing')

    def test_ddl_acl_and_schema_changes_rollback_together(self):
        body=MIGRATION.read_text().removeprefix('begin;').removesuffix('commit;\n')
        self.db.execute('begin;'+body)
        self.assertEqual(self.db.execute("select public.notification_delivery_protocol()").fetchone()[0],2)
        self.db.execute('rollback')
        self.assert_original()

    def test_disconnection_mid_upgrade_rolls_back_then_upgrade_can_resume(self):
        body=MIGRATION.read_text().removeprefix('begin;').removesuffix('commit;\n')
        interrupted=connect()
        interrupted.execute('begin;'+body)
        interrupted.close()  # Real backend disconnect before COMMIT.
        self.assert_original()

    def test_wrong_source_schema_refuses(self):
        self.db.execute("begin;update public.application_schema_state set schema_version=145 where contract_key='core'")
        with self.assertRaisesRegex(psycopg.Error,'migration_147_expected_schema_146'):
            self.db.execute(MIGRATION.read_text())
        self.db.execute('rollback')
        self.assert_original()


@unittest.skipUnless(DSN, "Requires marked disposable notification PostgreSQL")
class NotificationFencingDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connect() as db:
            if db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]!=147:
                raise AssertionError('The coordinated147 rehearsal must execute before fencing tests')
            db.execute('create table if not exists public.notification_fencing_test_receipts(id bigserial primary key,delivery_id uuid,generation bigint,external_key text unique)')

    def setUp(self):
        self.db=connect()
        self.addCleanup(self.db.close)
        self.ids=[]
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.db.execute('rollback')
        self.db.execute('reset role')
        self.db.execute('delete from public.notification_fencing_test_receipts where delivery_id=any(%s)',(self.ids,))
        self.db.execute('delete from public.notification_deliveries where id=any(%s)',(self.ids,))

    def new(self, *, attempts=3):
        identifier=uuid4();self.ids.append(identifier)
        self.db.execute("insert into public.notification_deliveries(id,channel,template,deduplication_key,max_attempts) values(%s,'internal','synthetic',%s,%s)",(identifier,str(identifier),attempts))
        return str(identifier)

    def claim(self, db=None, limit=1):
        return [row[0] for row in (db or self.db).execute('select to_jsonb(d) from public.claim_notification_deliveries_v2(%s,30) d',(limit,))]

    def expire(self, identifier):
        self.db.execute("update public.notification_deliveries set processing_lease_until=clock_timestamp()-interval '1 second' where id=%s",(identifier,))

    def finish(self, identifier, generation, outcome='sent', db=None):
        return (db or self.db).execute('select to_jsonb(public.finish_notification_delivery_v2(%s,%s,%s))',(identifier,generation,outcome)).fetchone()[0]

    def snapshot(self, identifier):
        return self.db.execute('select to_jsonb(d) from public.notification_deliveries d where id=%s',(identifier,)).fetchone()[0]

    def test_original_stale_ack_probe_now_rejects_every_outcome(self):
        for outcome in ('sent','retry','dead','revoked'):
            with self.subTest(outcome=outcome):
                identifier=self.new();old=self.claim()[0];self.expire(identifier);new=self.claim()[0]
                self.assertEqual((old['claim_generation'],new['claim_generation']),(1,2))
                before=self.snapshot(identifier)
                with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):
                    self.finish(identifier,old['claim_generation'],outcome)
                self.assertEqual(self.snapshot(identifier),before)
                self.assertEqual(self.finish(identifier,new['claim_generation'])['status'],'sent')

    def test_expired_unreclaimed_worker_rejected_for_all_outcomes(self):
        for outcome in ('sent','retry','dead','revoked'):
            identifier=self.new();row=self.claim()[0];self.expire(identifier)
            before=self.snapshot(identifier)
            with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):
                self.finish(identifier,row['claim_generation'],outcome)
            self.assertEqual(self.snapshot(identifier),before)
            self.db.execute('delete from public.notification_deliveries where id=%s',(identifier,))

    def test_current_owner_outcomes_and_bounded_retry_are_preserved(self):
        for outcome,expected in [('sent','sent'),('retry','pending'),('dead','dead'),('revoked','dead')]:
            identifier=self.new();row=self.claim()[0]
            result=self.finish(identifier,row['claim_generation'],outcome)
            self.assertEqual(result['status'],expected)
            self.assertIsNone(result['processing_lease_until'])
            if outcome=='retry':
                self.assertEqual(self.claim(),[])
                self.db.execute("update public.notification_deliveries set available_at=clock_timestamp()-interval '1 second' where id=%s",(identifier,))
                next_claim=self.claim()[0]
                self.assertEqual(next_claim['claim_generation'],2)
                self.finish(identifier,2)

    def test_last_attempt_retry_and_crash_exhaustion_dead_letter(self):
        identifier=self.new(attempts=1);self.claim()
        self.assertEqual(self.finish(identifier,1,'retry')['status'],'dead')
        identifier=self.new(attempts=1);self.claim();self.expire(identifier)
        self.assertEqual(self.claim(),[])
        self.assertEqual(self.snapshot(identifier)['status'],'dead')
        with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):
            self.finish(identifier,1,'sent')

    def test_wrong_generation_null_generation_and_foreign_id_do_not_mutate(self):
        identifier=self.new();self.claim();before=self.snapshot(identifier)
        for value in (None,0,-1,2,999):
            with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_(invalid|lost)'):
                self.finish(identifier,value)
        with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):
            self.finish(str(uuid4()),1)
        self.assertEqual(self.snapshot(identifier),before)

    def test_concurrent_completions_have_one_winner(self):
        identifier=self.new();self.claim();gate=threading.Barrier(2)
        def complete(outcome):
            with connect() as db:
                gate.wait(timeout=5)
                try:return self.finish(identifier,1,outcome,db)['status']
                except psycopg.Error as error:return error.diag.message_primary
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(complete,outcome) for outcome in ('sent','retry')]
            results=[f.result(timeout=10) for f in futures]
        self.assertEqual(results.count('notification_delivery_claim_lost'),1)
        self.assertEqual(sum(value in ('sent','pending') for value in results),1)

    def test_concurrent_claimers_do_not_share_rows_or_generations(self):
        for _ in range(20):self.new()
        gate=threading.Barrier(5)
        def claim():
            with connect() as db:
                gate.wait(timeout=5)
                return self.claim(db,4)
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda _:claim(),range(5)))
        rows=[row for batch in results for row in batch]
        self.assertEqual(len(rows),20)
        self.assertEqual(len({row['id'] for row in rows}),20)
        self.assertTrue(all(row['claim_generation']==1 for row in rows))

    def test_stale_finish_racing_reclaim_cannot_win(self):
        identifier=self.new();self.claim();self.expire(identifier);gate=threading.Barrier(2)
        def stale():
            with connect() as db:
                gate.wait(timeout=5)
                try:self.finish(identifier,1,db=db)
                except psycopg.Error as error:return error.diag.message_primary
        def reclaim():
            with connect() as db:
                gate.wait(timeout=5)
                return self.claim(db)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=pool.submit(stale),pool.submit(reclaim)
            self.assertEqual(a.result(timeout=10),'notification_delivery_claim_lost')
            # SKIP LOCKED may legitimately skip the row while stale finish locks it.
            claimed=b.result(timeout=10) or self.claim()
        self.assertEqual(claimed[0]['claim_generation'],2)
        self.assertEqual(self.snapshot(identifier)['status'],'processing')

    def test_lease_time_is_checked_after_database_lock_wait(self):
        identifier=self.new();self.claim()
        with connect() as holder, connect() as waiter:
            holder.execute('begin')
            holder.execute('select id from public.notification_deliveries where id=%s for update',(identifier,))
            waiter_pid=waiter.info.backend_pid
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(self.finish,identifier,1,'sent',waiter)
                try:
                    deadline=time.monotonic()+3
                    while time.monotonic()<deadline:
                        if self.db.execute("select wait_event_type='Lock' from pg_stat_activity where pid=%s",(waiter_pid,)).fetchone()[0]:break
                        time.sleep(.01)
                    else:self.fail('finish did not wait for the held row lock')
                    holder.execute("update public.notification_deliveries set processing_lease_until=clock_timestamp()-interval '1 second' where id=%s",(identifier,))
                finally:holder.execute('commit')
                with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):pending.result(timeout=10)
        self.assertEqual(self.snapshot(identifier)['status'],'processing')

    def test_legacy_calls_and_direct_service_role_writes_rejected(self):
        identifier=self.new();self.claim()
        with connect() as db:
            db.execute('set role service_role')
            for statement,arguments in [
                ('select public.claim_notification_deliveries()',()),
                ("select public.finish_notification_delivery(%s,'sent')",(identifier,)),
                ("update public.notification_deliveries set status='sent' where id=%s",(identifier,)),
                ("insert into public.notification_deliveries(channel,template,deduplication_key) values('internal','bad','bad')",()),
                ('delete from public.notification_deliveries where id=%s',(identifier,))]:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):db.execute(statement,arguments)
        with self.assertRaisesRegex(psycopg.Error,'notification_delivery_fencing_required'):
            self.db.execute("select public.finish_notification_delivery(%s,'sent')",(identifier,))
        self.assertEqual(self.snapshot(identifier)['status'],'processing')

    def test_anon_and_authenticated_cannot_claim_or_finish(self):
        identifier=self.new();self.claim()
        for role in ('anon','authenticated'):
            with connect() as db:
                db.execute('set role '+role)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):self.claim(db)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):self.finish(identifier,1,db=db)

    def test_completed_claim_cannot_be_replayed_as_another_outcome(self):
        identifier=self.new();self.claim();self.finish(identifier,1);before=self.snapshot(identifier)
        for outcome in ('sent','retry','dead','revoked'):
            with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):self.finish(identifier,1,outcome)
            self.assertEqual(self.snapshot(identifier),before)

    def child(self, mode):
        result=subprocess.run([sys.executable,__file__,'--child',mode],capture_output=True,text=True,timeout=20)
        self.assertIn(result.returncode,(0,86),result.stderr)
        return result.returncode

    def test_process_crash_after_claim_then_restart_recovers(self):
        identifier=self.new();self.assertEqual(self.child('claim'),86)
        self.assertEqual(self.snapshot(identifier)['claim_generation'],1)
        self.expire(identifier);self.assertEqual(self.child('normal'),0)
        self.assertEqual((self.snapshot(identifier)['status'],self.snapshot(identifier)['claim_generation']),('sent',2))
        self.assertEqual(self.db.execute('select count(*) from public.notification_fencing_test_receipts where delivery_id=%s',(identifier,)).fetchone()[0],1)

    def test_provider_acceptance_crash_preserves_at_least_once_limitation(self):
        identifier=self.new();self.assertEqual(self.child('accepted'),86)
        self.expire(identifier);self.assertEqual(self.child('normal'),0)
        self.assertEqual(self.snapshot(identifier)['status'],'sent')
        self.assertEqual(self.db.execute('select count(*) from public.notification_fencing_test_receipts where delivery_id=%s',(identifier,)).fetchone()[0],2)

    def test_provider_with_stable_idempotency_key_deduplicates_restart(self):
        identifier=self.new();self.assertEqual(self.child('accepted-idempotent'),86)
        self.expire(identifier);self.assertEqual(self.child('idempotent'),0)
        self.assertEqual(self.snapshot(identifier)['status'],'sent')
        self.assertEqual(self.db.execute('select count(*) from public.notification_fencing_test_receipts where delivery_id=%s',(identifier,)).fetchone()[0],1)

    def test_native_worker_ownership_loss_never_overwrites_new_claim(self):
        from services import notification_delivery_queue_service as queue
        from workers import notification_worker as worker
        identifier=self.new();old=queue.claim_deliveries(limit=1,client=SqlRpcClient())[0]
        def provider_accepts(_row):
            self.expire(identifier)
            self.assertEqual(self.claim()[0]['claim_generation'],2)
        before=worker.STATE['ownership_lost']
        worker.process_batch(limit=1,claim=lambda **_:[old],deliver=provider_accepts,
            finish=lambda identifier,**kwargs:queue.finish_delivery(identifier,client=SqlRpcClient(),**kwargs))
        self.assertEqual(worker.STATE['ownership_lost'],before+1)
        row=self.snapshot(identifier)
        self.assertEqual((row['status'],row['claim_generation']),('processing',2))

    def test_second_migration_application_refuses_without_changes(self):
        with self.assertRaisesRegex(psycopg.Error,'migration_147_expected_schema_146'):self.db.execute(MIGRATION.read_text())
        self.db.execute('rollback')
        self.assertEqual(self.db.execute('select public.notification_delivery_protocol()').fetchone()[0],2)


def worker_child(mode):
    from services import notification_delivery_queue_service as queue
    from workers import notification_worker as worker
    client=SqlRpcClient()
    queue.require_delivery_fencing(client=client)
    def claim(**kwargs):
        rows=queue.claim_deliveries(client=client,**kwargs)
        if mode=='claim':os._exit(86)
        return rows
    def deliver(row):
        key=row['id'] if 'idempotent' in mode else row['id']+':'+str(row['claim_generation'])
        with connect() as db:
            db.execute('insert into public.notification_fencing_test_receipts(delivery_id,generation,external_key) values(%s,%s,%s) on conflict(external_key) do nothing',(row['id'],row['claim_generation'],key))
        if mode.startswith('accepted'):os._exit(86)
    worker.process_batch(limit=1,claim=claim,deliver=deliver,
        finish=lambda identifier,**kwargs:queue.finish_delivery(identifier,client=client,**kwargs))


if __name__=='__main__':
    if '--child' in sys.argv:
        worker_child(sys.argv[-1])
        raise SystemExit(0)
    runner=unittest.TextTestRunner(verbosity=2)
    result=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(NotificationUpgradeDatabaseTests))
    if not result.wasSuccessful():raise SystemExit(1)
    with connect() as db:db.execute(MIGRATION.read_text())
    result=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(NotificationFencingDatabaseTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
