"""Actual PostgreSQL resolver ownership and atomic materialization tests."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from uuid import uuid4

import psycopg
from tests.disposable_database_support import connect_disposable_database

DSN = os.getenv('OUTBOX_SYNTHETIC_DATABASE_DSN')
MIGRATION = Path(os.getenv('OUTBOX_MIGRATION_SQL', '/migration149.sql'))


def connect():
    db = connect_disposable_database(DSN, markers={'madar-notification-synthetic-rehearsal'})
    db.execute("set statement_timeout='12s'")
    return db


class RpcError(RuntimeError):
    def __init__(self, error):
        self.message = error.diag.message_primary
        super().__init__(self.message)


class SqlRpcClient:
    def rpc(self, name, body):
        allowed = {'notification_outbox_protocol', 'notification_delivery_protocol',
                   'claim_notification_outbox_v2', 'finish_notification_outbox_v2',
                   'resolve_notification_outbox_v3'}
        if name not in allowed:
            raise AssertionError('Legacy RPC fallback is forbidden')
        from psycopg import sql
        class Response:
            def execute(inner):
                with connect() as db:
                    db.execute('set role service_role')
                    arguments = sql.SQL(',').join(sql.SQL('{}=>%s').format(sql.Identifier(key)) for key in body)
                    query = sql.SQL('select to_jsonb(r) from public.{}({}) r').format(sql.Identifier(name), arguments)
                    try:
                        inner.data = [row[0] for row in db.execute(query, tuple(body.values()))]
                        if name.endswith('_protocol') or name.startswith('resolve_'):
                            inner.data = inner.data[0]
                        return inner
                    except psycopg.Error as error:
                        raise RpcError(error) from None
        return Response()


@unittest.skipUnless(DSN, 'Requires marked disposable PostgreSQL')
class OutboxUpgradeDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0], 148)

    def original(self):
        self.db.execute('rollback')
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0], 148)
        self.assertIsNone(self.db.execute("select to_regprocedure('public.notification_outbox_protocol()')").fetchone()[0])
        self.assertTrue(self.db.execute("select has_table_privilege('service_role','public.notification_outbox','UPDATE')").fetchone()[0])

    def test_active_and_expired_processing_refuse_cutover(self):
        for age in ('1 minute', '16 minutes'):
            identifier = str(uuid4())
            self.db.execute("insert into public.notification_outbox(id,channel,template,status,processing_started_at) values(%s,'email','synthetic','processing',clock_timestamp()-(%s)::interval)", (identifier, age))
            try:
                with self.assertRaisesRegex(psycopg.Error, 'migration_149_requires_drained_outbox'):
                    self.db.execute(MIGRATION.read_text())
                self.original()
            finally:
                self.db.execute('delete from public.notification_outbox where id=%s', (identifier,))

    def test_ddl_acl_schema_rollback_together(self):
        body = MIGRATION.read_text().removeprefix('begin;').removesuffix('commit;\n')
        self.db.execute('begin;'+body)
        self.assertEqual(self.db.execute('select public.notification_outbox_protocol()').fetchone()[0], 2)
        self.db.execute('rollback')
        self.original()

    def test_connection_loss_before_commit_preserves148(self):
        body = MIGRATION.read_text().removeprefix('begin;').removesuffix('commit;\n')
        interrupted = connect()
        interrupted.execute('begin;'+body)
        interrupted.close()
        self.original()

    def test_wrong_schema_and_missing_state_reject(self):
        for statement in ("update public.application_schema_state set schema_version=147 where contract_key='core'",
                          "delete from public.application_schema_state where contract_key='core'"):
            self.db.execute('begin;'+statement)
            with self.assertRaisesRegex(psycopg.Error, 'migration_149_(expected_schema_148|schema_state_missing)'):
                self.db.execute(MIGRATION.read_text())
            self.original()

    def test_successor_worker_protocol_is_unavailable_before_cutover(self):
        from services.notification_outbox_service import require_outbox_fencing
        with self.assertRaises(RpcError):
            require_outbox_fencing(client=SqlRpcClient())


@unittest.skipUnless(DSN, 'Requires marked disposable PostgreSQL')
class OutboxFencingDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connect() as db:
            if db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] != 149:
                raise AssertionError('The successor149 rehearsal must execute first')
            # Earlier native business cases intentionally enqueue synthetic
            # notifications. This suite exclusively owns these two queues in
            # the independently marked disposable database; clear their fixture
            # work so claim order cannot select another suite's notifications.
            db.execute('delete from public.notification_deliveries')
            db.execute('delete from public.notification_outbox')
            # Match the native provider's service role. BYPASSRLS does not bypass
            # table ACLs, which the direct-mutation adversarial cases still test.
            db.execute('alter role service_role bypassrls')

    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.ids = []
        self.addCleanup(self.cleanup)
        self.assertEqual(self.db.execute('select public.notification_outbox_protocol()').fetchone()[0], 2)

    def cleanup(self):
        self.db.execute('rollback')
        self.db.execute('reset role')
        self.db.execute('delete from public.notification_deliveries where outbox_id=any(%s::uuid[])', (self.ids,))
        self.db.execute('delete from public.notification_outbox where id=any(%s::uuid[])', (self.ids,))

    def new(self, attempts=5):
        identifier = str(uuid4())
        self.ids.append(identifier)
        self.db.execute("insert into public.notification_outbox(id,channel,template,max_attempts) values(%s,'email','synthetic',%s)", (identifier, attempts))
        return identifier

    def snapshot(self, identifier):
        return self.db.execute('select to_jsonb(o) from public.notification_outbox o where id=%s', (identifier,)).fetchone()[0]

    def claim(self, db=None, limit=1):
        return [row[0] for row in (db or self.db).execute('select to_jsonb(o) from public.claim_notification_outbox_v2(%s,30) o', (limit,))]

    def expire(self, identifier):
        self.db.execute("update public.notification_outbox set processing_lease_until=clock_timestamp()-interval '1 second' where id=%s", (identifier,))

    def finish(self, identifier, generation, outcome='sent', db=None):
        return (db or self.db).execute('select to_jsonb(public.finish_notification_outbox_v2(%s,%s,%s))', (identifier, generation, outcome)).fetchone()[0]

    def resolve(self, identifier, generation, enabled=True, db=None):
        return (db or self.db).execute('select public.resolve_notification_outbox_v3(%s,%s,%s,false)', (identifier, generation, enabled)).fetchone()[0]

    def test_stale_owner_cannot_finish_any_outcome_after_reclaim(self):
        for outcome in ('sent', 'retry', 'dead', 'revoked'):
            identifier = self.new(); old = self.claim()[0]; self.expire(identifier); new = self.claim()[0]
            self.assertEqual((old['claim_generation'], new['claim_generation']), (1, 2))
            before = self.snapshot(identifier)
            with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
                self.finish(identifier, 1, outcome)
            self.assertEqual(self.snapshot(identifier), before)
            self.finish(identifier, 2)

    def test_expired_unreclaimed_finish_and_resolve_reject(self):
        for operation in ('sent', 'retry', 'dead', 'revoked', 'resolve'):
            identifier = self.new(); self.claim(); self.expire(identifier)
            before = self.snapshot(identifier)
            with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
                self.resolve(identifier, 1) if operation == 'resolve' else self.finish(identifier, 1, operation)
            self.assertEqual(self.snapshot(identifier), before)
            self.db.execute('delete from public.notification_outbox where id=%s', (identifier,))

    def test_stale_disabled_channel_resolver_cannot_discard_successor_work(self):
        identifier = self.new(); self.claim(); self.expire(identifier); self.claim()
        before = self.snapshot(identifier)
        with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
            self.resolve(identifier, 1, False)
        self.assertEqual(self.snapshot(identifier), before)
        self.assertEqual(self.resolve(identifier, 2), 1)
        self.assertEqual(self.snapshot(identifier)['status'], 'sent')
        self.assertEqual(self.db.execute('select count(*) from public.notification_deliveries where outbox_id=%s', (identifier,)).fetchone()[0], 1)

    def test_current_owner_outcomes_retry_generation_and_exhaustion(self):
        for outcome, status in [('sent', 'sent'), ('retry', 'failed'), ('dead', 'dead'), ('revoked', 'dead')]:
            identifier = self.new(); self.claim()
            self.assertEqual(self.finish(identifier, 1, outcome)['status'], status)
            if outcome == 'retry':
                self.assertEqual(self.claim(), [])
                self.db.execute("update public.notification_outbox set available_at=clock_timestamp()-interval '1 second' where id=%s", (identifier,))
                self.assertEqual(self.claim()[0]['claim_generation'], 2)
                self.finish(identifier, 2)
        identifier = self.new(1); self.claim(); self.expire(identifier)
        self.assertEqual(self.claim(), [])
        self.assertEqual(self.snapshot(identifier)['status'], 'dead')
        with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
            self.finish(identifier, 1)

    def test_concurrent_claimers_never_share_claims(self):
        expected = {self.new() for _ in range(8)}; gate = threading.Barrier(2)
        def claim():
            with connect() as db:
                db.execute('set role service_role'); gate.wait(timeout=5)
                return self.claim(db, 8)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        actual = [row['id'] for rows in results for row in rows]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))
        for identifier in actual: self.finish(identifier, 1)

    def test_concurrent_finish_and_resolution_have_only_one_winner(self):
        identifier = self.new(); self.claim(); gate = threading.Barrier(2)
        def finish(resolve):
            with connect() as db:
                db.execute('set role service_role'); gate.wait(timeout=5)
                try:
                    self.resolve(identifier, 1, db=db) if resolve else self.finish(identifier, 1, 'retry', db)
                    return 'accepted'
                except psycopg.Error as error:
                    return error.diag.message_primary
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(finish, (True, False)))
        self.assertEqual(sorted(results), ['accepted', 'notification_outbox_claim_lost'])

    def test_clock_is_sampled_after_row_lock_wait(self):
        identifier = self.new(); self.claim()
        self.db.execute("update public.notification_outbox set processing_lease_until=clock_timestamp()+interval '700 milliseconds' where id=%s", (identifier,))
        locker = connect(); locker.execute('begin'); locker.execute('select 1 from public.notification_outbox where id=%s for update', (identifier,))
        entered = threading.Event()
        def finish():
            with connect() as db:
                entered.set()
                try: self.finish(identifier, 1, db=db)
                except psycopg.Error as error: return error.diag.message_primary
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(finish); self.assertTrue(entered.wait(5)); time.sleep(1)
                locker.execute('commit')
                self.assertEqual(future.result(timeout=5), 'notification_outbox_claim_lost')
        finally: locker.close()
        self.assertEqual(self.snapshot(identifier)['status'], 'processing')

    def test_expiry_during_materialization_rolls_back_deliveries_and_status(self):
        identifier = self.new(); self.claim()
        self.db.execute("create function public.phase4_delay_insert() returns trigger language plpgsql as $$begin perform pg_sleep(3);return new;end$$")
        self.db.execute('create trigger phase4_delay before insert on public.notification_deliveries for each row execute function public.phase4_delay_insert()')
        try:
            self.db.execute("update public.notification_outbox set processing_lease_until=clock_timestamp()+interval '2 seconds' where id=%s", (identifier,))
            before = self.snapshot(identifier)
            with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
                self.resolve(identifier, 1)
            self.assertEqual(self.snapshot(identifier), before)
            self.assertEqual(self.db.execute('select count(*) from public.notification_deliveries where outbox_id=%s', (identifier,)).fetchone()[0], 0)
        finally:
            self.db.execute('drop trigger phase4_delay on public.notification_deliveries')
            self.db.execute('drop function public.phase4_delay_insert()')

    def test_legacy_rpc_and_direct_mutation_are_denied_but_enqueue_cleanup_work(self):
        identifier = self.new()
        with connect() as db:
            db.execute('set role service_role')
            for query in ["select public.claim_notification_outbox(1)",
                          f"select public.finish_notification_outbox('{identifier}',true)",
                          f"select public.resolve_notification_outbox('{identifier}')",
                          f"select public.resolve_notification_outbox_v2('{identifier}',now(),true,false)",
                          f"update public.notification_outbox set status='sent' where id='{identifier}'",
                          f"delete from public.notification_outbox where id='{identifier}'"]:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege): db.execute(query)
            enqueued = str(uuid4()); self.ids.append(enqueued)
            db.execute("insert into public.notification_outbox(id,channel,template,status,retention_until) values(%s,'email','synthetic','sent',clock_timestamp()-interval '1 day')", (enqueued,))
            db.execute('select public.cleanup_notification_delivery_data(clock_timestamp(),1000)')
            self.assertEqual(db.execute('select count(*) from public.notification_outbox where id=%s', (enqueued,)).fetchone()[0], 0)
            for role in ('anon','authenticated'):
                self.assertFalse(db.execute("select has_function_privilege(%s,'public.stop_deletion_notification_work(uuid,text,integer)','EXECUTE')",(role,)).fetchone()[0])
            self.assertFalse(db.execute("select has_function_privilege('service_role','public.notification_outbox_materialize_149(uuid,timestamptz,boolean,boolean)','EXECUTE')").fetchone()[0])
        with self.assertRaisesRegex(psycopg.Error,'notification_outbox_fenced_protocol_required'):
            self.db.execute('select public.resolve_notification_outbox_v2(%s)',(identifier,))

    def test_invalid_foreign_and_repeated_claims_do_not_mutate(self):
        identifier = self.new(); self.claim(); before = self.snapshot(identifier)
        for generation in (None, 0, -1, 2, 999):
            with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_(lost|invalid)'):
                self.finish(identifier, generation)
        with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
            self.finish(str(uuid4()), 1)
        self.assertEqual(self.snapshot(identifier), before)
        self.resolve(identifier, 1)
        after = self.snapshot(identifier)
        for operation in (lambda: self.resolve(identifier, 1), lambda: self.finish(identifier, 1)):
            with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'): operation()
        self.assertEqual(self.snapshot(identifier), after)

    def test_worker_crash_restart_reclaims_with_new_generation(self):
        identifier = self.new()
        result = subprocess.run([sys.executable, __file__, '--claim-crash'], env=os.environ.copy(), timeout=10)
        self.assertEqual(result.returncode, 86)
        old = self.snapshot(identifier); self.assertEqual(old['claim_generation'], 1)
        self.expire(identifier)
        from services import notification_outbox_service as outbox
        from services import notification_delivery_queue_service as queue
        client = SqlRpcClient(); outbox.require_outbox_fencing(client=client)
        new = outbox.claim_notifications(limit=1, client=client)[0]
        self.assertEqual(new['claim_generation'], 2)
        with self.assertRaises(outbox.OutboxOwnershipLost):
            outbox.mark_notification_result(identifier, claim_generation=1, succeeded=True, client=client)
        self.assertEqual(queue.resolve_outbox_notification(new, client=client), 0)  # disabled deployment email
        self.assertEqual(self.snapshot(identifier)['status'], 'sent')

    def test_native_worker_stale_resolution_never_finalizes_reminder(self):
        from unittest.mock import Mock, patch
        from services import notification_delivery_queue_service as queue
        from services import notification_outbox_service as outbox
        from workers import notification_worker as worker
        identifier = self.new(); old = self.claim()[0]; self.expire(identifier); self.claim()
        old['template'] = 'calendar_reminder'
        finalizer, finish = Mock(), Mock()
        before = worker.STATE['ownership_lost']
        with patch.object(worker, 'mark_calendar_reminder_delivery', finalizer):
            worker.process_resolution_batch(limit=1, claim=lambda **_: [old],
                resolve=lambda row: queue.resolve_outbox_notification(row, client=SqlRpcClient()), finish=finish)
        self.assertEqual(worker.STATE['ownership_lost'], before+1)
        finish.assert_not_called(); finalizer.assert_not_called()
        self.assertEqual(self.snapshot(identifier)['status'], 'processing')

    def test_lost_resolver_response_cannot_undo_committed_materialization(self):
        from services import notification_outbox_service as outbox
        from workers import notification_worker as worker
        identifier = self.new(); old = self.claim()[0]
        def committed_but_response_lost(_row):
            self.assertEqual(self.resolve(identifier, 1), 1)
            raise RuntimeError('synthetic connection lost after commit')
        before = worker.STATE['ownership_lost']
        worker.process_resolution_batch(limit=1, claim=lambda **_: [old], resolve=committed_but_response_lost,
            finish=lambda key, **kwargs: outbox.mark_notification_result(key, client=SqlRpcClient(), **kwargs))
        self.assertEqual(worker.STATE['ownership_lost'], before+1)
        self.assertEqual(self.snapshot(identifier)['status'], 'sent')
        self.assertEqual(self.claim(), [])
        self.assertEqual(self.db.execute('select count(*) from public.notification_deliveries where outbox_id=%s', (identifier,)).fetchone()[0], 1)

    def test_second_migration_refuses_without_weakening_fencing(self):
        with self.assertRaisesRegex(psycopg.Error, 'migration_149_expected_schema_148'):
            self.db.execute(MIGRATION.read_text())
        self.db.execute('rollback')
        self.assertEqual(self.db.execute('select public.notification_outbox_protocol()').fetchone()[0], 2)
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.notification_outbox','UPDATE')").fetchone()[0])

    def deletion_subjects(self):
        tenant = self.db.execute("insert into public.tenants(brand_name,owner_name,lifecycle_state) values('Synthetic deletion fence','Fixture','deletion_pending') returning tenant_id").fetchone()[0]
        auths=[uuid4(),uuid4()]
        for identity in auths:
            self.db.execute('insert into auth.users(id,email,email_confirmed_at) values(%s,%s,now())',(identity,str(identity)+'@example.invalid'))
        users = [self.db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status) values(%s,'Synthetic','Deletion',%s,%s,'deletion_pending') returning id", (identity,str(identity)+'@example.invalid',tenant)).fetchone()[0] for identity in auths]
        requests = []
        def cleanup():
            self.db.execute('reset role');self.db.execute('rollback')
            self.db.execute('delete from public.data_deletion_requests where id=any(%s::uuid[])',(requests,))
            self.db.execute('delete from public.users where id=any(%s)',(users,))
            self.db.execute('delete from auth.users where id=any(%s)',(auths,))
            self.db.execute('delete from public.tenants where tenant_id=%s',(tenant,))
        self.addCleanup(cleanup)
        def request(kind):
            identifier=str(uuid4());requests.append(identifier)
            self.db.execute("insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot,target_tenant_id_snapshot,state,attempt_count,lease_owner,lease_until) values(%s,%s,%s,%s,'in_progress',2,'synthetic-deletion-worker',clock_timestamp()+interval '1 minute')",(identifier,kind,users[0],tenant))
            return identifier
        def queued(user):
            identifier=self.new()
            self.db.execute("update public.notification_outbox set tenant_id=%s,user_id=%s,status='processing',claim_generation=1,processing_lease_until=clock_timestamp()+interval '1 minute' where id=%s",(tenant,user,identifier))
            self.db.execute("insert into public.notification_deliveries(outbox_id,tenant_id,user_id,channel,template,deduplication_key,status,claim_generation,processing_lease_until) values(%s,%s,%s,'internal','synthetic',%s,'processing',1,clock_timestamp()+interval '1 minute')",(identifier,tenant,user,str(uuid4())))
            return identifier
        return tenant,users,request,queued

    def test_deletion_notification_cancellation_is_subject_scoped_and_fenced(self):
        tenant,users,request,queued=self.deletion_subjects()
        own,other=queued(users[0]),queued(users[1]);identifier=request('user')
        foreign_tenant=self.db.execute("insert into public.tenants(brand_name,owner_name) values('Synthetic unrelated deletion tenant','Fixture') returning tenant_id").fetchone()[0]
        self.addCleanup(lambda:self.db.execute('delete from public.tenants where tenant_id=%s',(foreign_tenant,)))
        foreign=self.new();self.db.execute('update public.notification_outbox set tenant_id=%s where id=%s',(foreign_tenant,foreign))
        self.db.execute('set role service_role')
        changed=self.db.execute("select public.stop_deletion_notification_work(%s,'synthetic-deletion-worker',2)",(identifier,)).fetchone()[0]
        self.assertEqual(changed,2)
        self.assertEqual(self.snapshot(own)['status'],'dead')
        self.assertEqual(self.snapshot(other)['status'],'processing')
        delivery=self.db.execute('select id,status,processing_lease_until from public.notification_deliveries where outbox_id=%s',(own,)).fetchone()
        self.assertEqual(delivery[1:],('dead',None))
        with self.assertRaisesRegex(psycopg.Error,'notification_delivery_claim_lost'):
            self.db.execute("select public.finish_notification_delivery_v2(%s,1,'sent')",(delivery[0],))
        with self.assertRaisesRegex(psycopg.Error,'notification_outbox_claim_lost'):self.finish(own,1)
        # A separate tenant request may cancel remaining work in that tenant.
        self.db.execute('reset role');identifier=request('tenant');self.db.execute('set role service_role')
        self.assertEqual(self.db.execute("select public.stop_deletion_notification_work(%s,'synthetic-deletion-worker',2)",(identifier,)).fetchone()[0],2)
        self.assertEqual(self.snapshot(other)['status'],'dead')
        self.assertEqual(self.snapshot(foreign)['status'],'pending')
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.notification_deliveries','UPDATE')").fetchone()[0])

    def test_deletion_wrong_owner_generation_expiry_or_unfrozen_subject_cannot_cancel(self):
        tenant,users,request,queued=self.deletion_subjects()
        work=queued(users[0]);identifier=request('user');original=self.snapshot(work)
        for owner,attempt in (('foreign-worker',2),('synthetic-deletion-worker',1)):
            with self.assertRaisesRegex(psycopg.Error,'deletion_notification_authority_lost'):
                self.db.execute('select public.stop_deletion_notification_work(%s,%s,%s)',(identifier,owner,attempt))
            self.assertEqual(self.snapshot(work),original)
        self.db.execute("update public.users set account_status='active' where id=%s",(users[0],))
        with self.assertRaisesRegex(psycopg.Error,'deletion_notification_target_not_frozen'):
            self.db.execute("select public.stop_deletion_notification_work(%s,'synthetic-deletion-worker',2)",(identifier,))
        self.db.execute("update public.users set account_status='deletion_pending' where id=%s",(users[0],))
        self.db.execute("update public.data_deletion_requests set lease_until=clock_timestamp()-interval '1 second' where id=%s",(identifier,))
        with self.assertRaisesRegex(psycopg.Error,'deletion_notification_authority_lost'):
            self.db.execute("select public.stop_deletion_notification_work(%s,'synthetic-deletion-worker',2)",(identifier,))
        self.assertEqual(self.snapshot(work),original)


if __name__ == '__main__':
    if '--claim-crash' in sys.argv:
        from services.notification_outbox_service import claim_notifications
        claim_notifications(limit=1, client=SqlRpcClient())
        os._exit(86)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(OutboxUpgradeDatabaseTests))
    if not result.wasSuccessful(): raise SystemExit(1)
    with connect() as db: db.execute(MIGRATION.read_text())
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(OutboxFencingDatabaseTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
