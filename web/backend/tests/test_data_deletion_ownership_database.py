"""Opt-in native reproduction of the retained deletion ownership defect.

These assertions intentionally describe required ownership safety. They fail on
schema149's retained deletion lifecycle; no production or provider call is made.
The companion cancellation tests verify149's narrower queue RPC serialization.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from types import SimpleNamespace
import time
import unittest
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from tests.disposable_database_support import connect_disposable_database

DSN = os.getenv('DELETION_OWNERSHIP_SYNTHETIC_DATABASE_DSN')


def connect():
    db = connect_disposable_database(DSN, markers={'madar-notification-synthetic-rehearsal'})
    db.execute("set statement_timeout='8s'")
    return db


class SqlQuery:
    def __init__(self, table):
        if table not in {'data_deletion_requests', 'data_deletion_steps'}:
            raise AssertionError('The reproducer cannot mutate customer tables')
        self.table_name, self.filters, self.payload = table, [], None

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, _maximum):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        where = sql.SQL(' and ').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key, _ in self.filters)
        parameters = [value for _, value in self.filters]
        table = sql.Identifier('public', self.table_name)
        if self.payload is None:
            query = sql.SQL('select to_jsonb(t) from {} t where {}').format(table, where)
        else:
            assignments = sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key in self.payload)
            values = [Jsonb(value) if isinstance(value, (dict, list)) else value for value in self.payload.values()]
            query = sql.SQL('update {} t set {} where {} returning to_jsonb(t)').format(table, assignments, where)
            parameters = values + parameters
        with connect() as db:
            db.execute('set role service_role')
            return SimpleNamespace(data=[row[0] for row in db.execute(query, parameters)])


class SqlClient:
    def table(self, table):
        return SqlQuery(table)


@unittest.skipUnless(DSN, 'Opt-in known-failure reproduction on marked disposable PostgreSQL')
class DeletionOwnershipDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        if self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] != 149:
            self.fail('This reproduction requires exact synthetic schema149')
        self.identifier = str(uuid4())
        self.db.execute("insert into public.data_deletion_requests(id,request_type,target_user_id_snapshot) values(%s,'user',2147483001)", (self.identifier,))
        self.step_id = self.db.execute("insert into public.data_deletion_steps(request_id,step_key,step_order,state,attempts) values(%s,'stop_queued_work',40,'processing',1) returning id", (self.identifier,)).fetchone()[0]
        self.addCleanup(self.cleanup)
        # Two independent database claim calls, with a fixture-only forced expiry.
        self.old = self.claim('synthetic-owner-A')
        self.db.execute("update public.data_deletion_requests set lease_until=clock_timestamp()-interval '1 second' where id=%s", (self.identifier,))
        self.successor = self.claim('synthetic-owner-B')
        self.assertEqual(self.successor['attempt_count'], self.old['attempt_count'] + 1)
        self.client = SqlClient()

    def cleanup(self):
        self.db.execute('rollback')
        self.db.execute('delete from public.data_deletion_requests where id=%s', (self.identifier,))

    def claim(self, worker):
        with connect() as db:
            db.execute('set role service_role')
            rows = [row[0] for row in db.execute('select to_jsonb(r) from public.claim_data_deletion_requests(%s,25,clock_timestamp(),300) r', (worker,))]
        return next(row for row in rows if row['id'] == self.identifier)

    def request(self):
        return self.db.execute('select to_jsonb(r) from public.data_deletion_requests r where id=%s', (self.identifier,)).fetchone()[0]

    def step(self):
        return self.db.execute('select to_jsonb(s) from public.data_deletion_steps s where id=%s', (self.step_id,)).fetchone()[0]

    def test_stale_failure_cannot_clear_successor_request_lease(self):
        from services import data_deletion_service as lifecycle
        original = self.request()
        lifecycle._fail_step(self.old, self.step(), lifecycle.DeletionStepError('synthetic_provider_failure'), client=self.client)
        current = self.request()
        for key in ('state', 'lease_owner', 'lease_until', 'attempt_count'):
            self.assertEqual(current[key], original[key], f'Stale failure changed successor {key}')

    def test_stale_finalization_cannot_complete_successor_request(self):
        from services import data_deletion_service as lifecycle
        self.db.execute("update public.data_deletion_requests set verification_status='verified' where id=%s", (self.identifier,))
        original = self.request()
        lifecycle._step_finalize(self.old, client=self.client)
        current = self.request()
        for key in ('state', 'lease_owner', 'lease_until', 'attempt_count'):
            self.assertEqual(current[key], original[key], f'Stale finalization changed successor {key}')

    def test_stale_step_completion_cannot_overwrite_successor_step(self):
        from services import data_deletion_service as lifecycle
        stale = self.step()
        self.db.execute("update public.data_deletion_steps set attempts=2,output_safe='{}' where id=%s", (self.step_id,))
        original = self.step()
        lifecycle._finish_step(stale, {'synthetic_stale_result': True}, client=self.client)
        current = self.step()
        for key in ('state', 'attempts', 'output_safe', 'completed_at'):
            self.assertEqual(current[key], original[key], f'Stale completion changed successor step {key}')


@unittest.skipUnless(DSN, 'Requires marked disposable schema149 PostgreSQL')
class DeletionCancellationSerializationDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.assertEqual(self.db.execute('select public.notification_outbox_protocol()').fetchone()[0], 2)
        self.tenant = self.db.execute("insert into public.tenants(brand_name,owner_name,lifecycle_state) values('Synthetic cancellation race','Fixture','deletion_pending') returning tenant_id").fetchone()[0]
        self.request_id, self.outbox_id = str(uuid4()), str(uuid4())
        self.db.execute("insert into public.data_deletion_requests(id,request_type,target_tenant_id_snapshot,state,attempt_count,lease_owner,lease_until) values(%s,'tenant',%s,'in_progress',1,'synthetic-cancellation-owner',clock_timestamp()+interval '1 minute')", (self.request_id, self.tenant))
        self.db.execute("insert into public.notification_outbox(id,tenant_id,channel,template,status,claim_generation,processing_lease_until) values(%s,%s,'email','synthetic','processing',1,clock_timestamp()+interval '1 minute')", (self.outbox_id, self.tenant))
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.db.execute('rollback')
        self.db.execute('delete from public.notification_deliveries where outbox_id=%s', (self.outbox_id,))
        self.db.execute('delete from public.notification_outbox where id=%s', (self.outbox_id,))
        self.db.execute('delete from public.data_deletion_requests where id=%s', (self.request_id,))
        self.db.execute('delete from public.tenants where tenant_id=%s', (self.tenant,))

    def cancel(self, db):
        return db.execute("select public.stop_deletion_notification_work(%s,'synthetic-cancellation-owner',1)", (self.request_id,)).fetchone()[0]

    def resolve(self, db):
        return db.execute('select public.resolve_notification_outbox_v3(%s,1,true,false)', (self.outbox_id,)).fetchone()[0]

    def test_resolver_first_then_cancellation_revokes_materialized_delivery(self):
        blocker = connect()
        self.addCleanup(blocker.close)
        blocker.execute('begin')
        self.assertEqual(self.resolve(blocker), 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.cancel_in_new_connection)
            self.wait_for_blocked_session('cancel-' + self.request_id)
            self.assertFalse(future.done(), 'Cancellation must wait on the resolver row lock')
            blocker.execute('commit')
            self.assertEqual(future.result(timeout=5), 1)
        self.assertEqual(self.db.execute('select status from public.notification_deliveries where outbox_id=%s', (self.outbox_id,)).fetchall(), [('dead',)])

    def wait_for_blocked_session(self, application_name):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            rows = self.db.execute(
                "select wait_event_type from pg_stat_activity where application_name=%s",
                (application_name,),
            ).fetchall()
            if any(row[0] == 'Lock' for row in rows):
                return
            time.sleep(.02)
        self.fail('The competing connection did not reach the database row lock')

    def cancel_in_new_connection(self):
        with connect() as db:
            db.execute("select set_config('application_name',%s,false)", ('cancel-' + self.request_id,))
            db.execute('set role service_role')
            return self.cancel(db)

    def test_cancellation_first_rejects_waiting_resolver_without_new_deliveries(self):
        blocker = connect()
        self.addCleanup(blocker.close)
        blocker.execute('begin')
        self.assertEqual(self.cancel(blocker), 1)
        def waiting_resolve():
            with connect() as db:
                db.execute("select set_config('application_name',%s,false)", ('resolve-' + self.request_id,))
                db.execute('set role service_role')
                return self.resolve(db)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(waiting_resolve)
            self.wait_for_blocked_session('resolve-' + self.request_id)
            self.assertFalse(future.done(), 'Resolver must wait for cancellation row lock')
            blocker.execute('commit')
            with self.assertRaisesRegex(psycopg.Error, 'notification_outbox_claim_lost'):
                future.result(timeout=5)
        self.assertEqual(self.db.execute('select count(*) from public.notification_deliveries where outbox_id=%s', (self.outbox_id,)).fetchone()[0], 0)
