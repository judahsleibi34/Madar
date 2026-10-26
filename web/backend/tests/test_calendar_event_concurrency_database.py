"""Actual route writes raced through independent native PostgreSQL connections.

Authorization and side-effect transports are fixtures; UPDATE predicates, locks,
row versions and commit visibility are real PostgreSQL, not an in-memory mock.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from psycopg import sql
import psycopg

import routes.calendar_routes as routes
from tests import test_native_business_integrity_database as native
from services import calendar_mutation_service as mutations
import os
from uuid import UUID, uuid4

DSN, connect = native.DSN, native.connect
REAL_CALENDAR_CONNECT = mutations.connect


class NativeEventUpdate:
    def __init__(self, db):
        self.db, self.predicates, self.values = db, [], []

    def update(self, changes):
        self.changes = changes
        return self

    def eq(self, field, value):
        self.predicates.append(sql.SQL('{} = %s').format(sql.Identifier(field)))
        self.values.append(value)
        return self

    def is_(self, field, value):
        if value != 'null':
            raise AssertionError('Only SQL NULL is supported by this test transport')
        self.predicates.append(sql.SQL('{} IS NULL').format(sql.Identifier(field)))
        return self

    def execute(self):
        assignments = [sql.SQL('{} = %s').format(sql.Identifier(key)) for key in self.changes]
        query = sql.SQL('UPDATE public.calendar_events AS e SET {} WHERE {} RETURNING to_jsonb(e)').format(
            sql.SQL(', ').join(assignments), sql.SQL(' AND ').join(self.predicates))
        rows = self.db.execute(query, [*self.changes.values(), *self.values]).fetchall()
        return SimpleNamespace(data=[row[0] for row in rows])


@unittest.skipUnless(DSN, 'Requires marked disposable native PostgreSQL')
class CalendarEventConcurrencyDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.tenant, self.user = native.NativeBusinessIntegrityTests.owner(self)
        self.calendar = self.db.execute(
            "insert into public.calendars(tenant_id,owner_user_id,name) values(%s,%s,'Synthetic concurrency') returning id",
            (self.tenant, self.user)).fetchone()[0]
        self.start = datetime.now(timezone.utc) + timedelta(days=2)
        self.end = self.start + timedelta(hours=1)
        self.event = str(self.db.execute(
            "insert into public.calendar_events(tenant_id,calendar_id,created_by,title,starts_at,ends_at) "
            "values(%s,%s,%s,'Original',%s,%s) returning id",
            (self.tenant, self.calendar, self.user, self.start, self.end)).fetchone()[0])
        # Only this already-marked disposable cluster receives test login/grants.
        self.db.execute("do $$ begin if not exists(select from pg_roles where rolname='authenticator') then "
            "create role authenticator nologin nosuperuser nocreatedb nocreaterole noreplication; end if; end $$")
        self.db.execute('grant service_role to authenticator')
        bypass=self.db.execute("select rolbypassrls from pg_roles where rolname='service_role'").fetchone()[0]
        # Supabase's existing backend service role bypasses RLS; tenant/ACL
        # enforcement must therefore be proved by the actual domain queries.
        self.db.execute('alter role service_role bypassrls')
        self.addCleanup(lambda:self.db.execute('alter role service_role '+('bypassrls' if bypass else 'nobypassrls')))
        self.db.execute('grant execute on function pg_catalog.pg_control_system() to service_role')
        identifier=self.db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
        auth_id=str(self.db.execute('select auth_id from public.users where id=%s',(self.user,)).fetchone()[0])
        self.context=SimpleNamespace(tenant_id=self.tenant,user_id=self.user,auth_id=auth_id)
        self.enterContext(patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':identifier}))
        def connection():
            db=connect();db.execute('set session authorization authenticator');return db
        self.enterContext(patch.object(mutations,'connect',side_effect=connection))

    def race(self, delete_second=False):
        barrier = threading.Barrier(2)
        local = threading.local()
        context = self.context

        def read_event(event_id, tenant_id):
            row = local.db.execute(
                'select to_jsonb(e) from public.calendar_events e where id=%s and tenant_id=%s and deleted_at is null',
                (event_id, tenant_id)).fetchone()[0]
            barrier.wait(timeout=5)
            return row

        def table(name):
            self.assertEqual(name, 'calendar_events')
            return NativeEventUpdate(local.db)

        def run(index):
            with connect() as db:
                local.db = db
                try:
                    if index == 1 and delete_second:
                        routes.delete_event(self.event, None, None, expected_version=1)
                    else:
                        payload = routes.EventWrite(calendar_id=self.calendar, title='Writer '+str(index),
                            starts_at=self.start, ends_at=self.end, expected_version=1)
                        routes.update_event(self.event, payload, None, None)
                    return (index, 200)
                except HTTPException as error:
                    return (index, error.status_code)

        with ExitStack() as stack:
            for name in ('require_calendar_feature', 'require_calendar_access', 'replace_event_children',
                         'write_change', 'record_calendar_audit'):
                stack.enter_context(patch.object(routes, name))
            stack.enter_context(patch.object(routes, 'require_active_tenant_member', return_value=context))
            stack.enter_context(patch.object(routes, 'event_conflicts', return_value=[]))
            stack.enter_context(patch.object(routes, 'tenant_event', side_effect=read_event))
            stack.enter_context(patch.object(routes, 'service_supabase', SimpleNamespace(table=table)))
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, range(2)))
        self.assertEqual(sorted(status for _, status in results), [200, 409], results)
        current = self.db.execute('select version,title,deleted_at from public.calendar_events where id=%s',
                                  (self.event,)).fetchone()
        self.assertEqual(current[0], 2)
        winner = next(index for index, status in results if status == 200)
        self.assertEqual(current[2] is not None, delete_second and winner == 1)
        self.assertEqual(current[1], 'Original' if delete_second and winner == 1 else 'Writer '+str(winner))

    def test_two_updates_have_one_atomic_winner(self):
        self.race()

    def test_update_and_delete_have_one_atomic_winner(self):
        self.race(delete_second=True)

    def mutation(self,scope='future',*,version=1,title='Replacement',minutes=10):
        payload=routes.EventWrite(calendar_id=self.calendar,title=title,starts_at=self.start+timedelta(days=1),
            ends_at=self.end+timedelta(days=1),recurrence_rule='FREQ=DAILY;COUNT=9',expected_version=version,
            attendees=[{'email':title.lower().replace(' ','')+'@example.invalid'}],
            reminders=[{'channel':'in_app','minutes_before':minutes}])
        row={'tenant_id':self.tenant,'created_by':self.user,'calendar_id':str(self.calendar),
            'title':title,'starts_at':payload.starts_at.isoformat(),'ends_at':payload.ends_at.isoformat(),
            'recurrence_rule':payload.recurrence_rule}
        return mutations.mutate_event(self.context,self.event,payload,row,expected_version=version,
            scope=scope,occurrence_start=payload.starts_at,audit={})

    def recurring(self):
        self.db.execute("update public.calendar_events set recurrence_rule='FREQ=DAILY;COUNT=10' where id=%s",(self.event,))
        self.db.execute("insert into public.calendar_event_attendees(tenant_id,event_id,email) values(%s,%s,'original@example.invalid')",(self.tenant,self.event))
        self.db.execute("insert into public.calendar_event_reminders(tenant_id,event_id,minutes_before,scheduled_for) values(%s,%s,5,%s)",(self.tenant,self.event,self.start))

    def snapshot(self):
        result={}
        for table in ('calendar_events','calendar_event_attendees','calendar_event_reminders','calendar_event_changes','audit_logs'):
            result[table]=self.db.execute(sql.SQL('select to_jsonb(t) from public.{} t where tenant_id=%s order by id').format(sql.Identifier(table)),(self.tenant,)).fetchall()
        return result

    def inject_failure(self,table):
        name='calendar_test_'+uuid4().hex
        self.db.execute(sql.SQL("create function public.{}() returns trigger language plpgsql as $$ begin "
            "if new.tenant_id={} then raise exception 'synthetic calendar effect failure'; end if; return new; end $$").format(sql.Identifier(name),sql.Literal(self.tenant)))
        self.db.execute(sql.SQL('create trigger {} before insert on public.{} for each row execute function public.{}()').format(sql.Identifier(name),sql.Identifier(table),sql.Identifier(name)))
        def cleanup():
            self.db.execute(sql.SQL('drop trigger {} on public.{}').format(sql.Identifier(name),sql.Identifier(table)))
            self.db.execute(sql.SQL('drop function public.{}()').format(sql.Identifier(name)))
        return cleanup

    def test_actual_configured_scram_transport_accepts_cluster_and_rejects_bad_credentials(self):
        # The canonical harness pins a SCRAM HBA rule for this disposable actor.
        # No patched session authorization or administrator connection is used.
        if not os.getenv('CANONICAL_EXECUTOR_SYNTHETIC_DATABASE_DSN'):
            self.skipTest('Requires canonical harness SCRAM rule')
        import secrets
        password=secrets.token_urlsafe(32)
        self.db.execute(sql.SQL('alter role authenticator login password {}').format(sql.Literal(password)))
        self.addCleanup(lambda:self.db.execute('alter role authenticator nologin password null'))
        parameters=dict(self.db.info.get_parameters(),user='authenticator',password=password)
        dsn=psycopg.conninfo.make_conninfo(**parameters)
        with patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_DSN':dsn}),\
                patch.object(mutations,'connect',side_effect=REAL_CALENDAR_CONNECT):
            self.assertEqual(mutations.transport_status(),'ok')
            self.db.execute('revoke insert on calendar_event_changes from service_role')
            try:self.assertEqual(mutations.transport_status(),'misconfigured')
            finally:self.db.execute('grant insert on calendar_event_changes to service_role')
            self.db.execute('revoke update on tenant_memberships from service_role')
            try:self.assertEqual(mutations.transport_status(),'misconfigured')
            finally:self.db.execute('grant update on tenant_memberships to service_role')
            self.assertEqual(self.mutation('series')['event']['version'],2)
            with patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':'0'}):
                self.assertEqual(mutations.transport_status(),'unavailable')
            bad=psycopg.conninfo.make_conninfo(**dict(parameters,password='incorrect-synthetic-password'))
            with patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_DSN':bad}):
                self.assertEqual(mutations.transport_status(),'unavailable')
                with self.assertRaises(HTTPException):REAL_CALENDAR_CONNECT()

    def test_create_route_rolls_back_parent_when_reminder_insert_fails(self):
        payload=routes.EventWrite(calendar_id=self.calendar,title='New aggregate',starts_at=self.start,
            ends_at=self.end,attendees=[{'email':'new@example.invalid'}],
            reminders=[{'channel':'in_app','minutes_before':5}])
        row={'tenant_id':self.tenant,'created_by':self.user,'calendar_id':str(self.calendar),
            'title':payload.title,'starts_at':self.start.isoformat(),'ends_at':self.end.isoformat()}
        owner=self
        class Insert:
            def insert(inner,values):inner.values=values;return inner
            def execute(inner):return SimpleNamespace(data=[mutations._write(owner.db,inner.values)])
        before=self.snapshot()
        for table in ('calendar_events','calendar_event_attendees','calendar_event_reminders','calendar_event_changes','audit_logs'):
            with self.subTest(table=table):
                cleanup=self.inject_failure(table)
                try:
                    with patch.object(routes,'require_calendar_feature'),patch.object(routes,'require_active_tenant_member',return_value=self.context),\
                            patch.object(routes,'normalized_event_row',return_value=row),patch.object(routes,'event_conflicts',return_value=[]),\
                            patch.object(routes,'service_supabase',SimpleNamespace(table=lambda name:Insert())),\
                            patch.object(routes,'replace_event_children',side_effect=lambda c,e,p:mutations._children(self.db,c,e,p)):
                        try:routes.create_event(payload,None,None)
                        except HTTPException as failure:
                            self.assertEqual(failure.status_code,503)
                            self.assertEqual(failure.__context__.diag.message_primary,'synthetic calendar effect failure')
                        else:self.fail('Injected aggregate failure was ignored')
                    self.assertEqual(self.snapshot(),before,'Creation must not commit any partial aggregate')
                finally:cleanup()

    def test_delete_route_rolls_back_recurrence_when_change_insert_fails(self):
        self.recurring()
        for scope in ('event','occurrence','future'):
            for table in ('calendar_event_changes','audit_logs'):
                with self.subTest(scope=scope,table=table):
                    before=self.snapshot();cleanup=self.inject_failure(table)
                    try:
                        with patch.object(routes,'require_calendar_feature'),patch.object(routes,'require_active_tenant_member',return_value=self.context),\
                                patch.object(routes,'tenant_event',side_effect=lambda *a:self.db.execute(
                                    'select to_jsonb(e) from calendar_events e where id=%s',(self.event,)).fetchone()[0]),\
                                patch.object(routes,'require_calendar_access'),\
                                patch.object(routes,'service_supabase',SimpleNamespace(table=lambda name:NativeEventUpdate(self.db))),\
                                patch.object(routes,'write_change',side_effect=lambda c,e,a,s,b,n:mutations._change(self.db,c,e,a,s,b,n)):
                            try:routes.delete_event(self.event,None,None,expected_version=1,scope=scope,occurrence_start=self.start+timedelta(days=1))
                            except HTTPException as failure:
                                self.assertEqual(failure.status_code,503)
                                self.assertEqual(failure.__context__.diag.message_primary,'synthetic calendar effect failure')
                            else:self.fail('Injected change failure was ignored')
                        self.assertEqual(self.snapshot(),before,'Deletion and its change record must commit together')
                    finally:cleanup()

    def test_create_and_delete_success_publish_atomic_audit_and_refuse_stale_retry(self):
        payload=routes.EventWrite(calendar_id=self.calendar,title='Created',starts_at=self.start,ends_at=self.end,
            attendees=[{'email':'created@example.invalid'}],reminders=[{'channel':'in_app','minutes_before':5}])
        row={'tenant_id':self.tenant,'created_by':self.user,'calendar_id':str(self.calendar),
            'title':payload.title,'starts_at':self.start.isoformat(),'ends_at':self.end.isoformat()}
        event=mutations.create_event(self.context,payload,row,audit={})
        self.assertEqual(self.db.execute('select count(*) from calendar_event_reminders where event_id=%s',(event['id'],)).fetchone()[0],1)
        mutations.delete_event(self.context,event['id'],expected_version=1,scope='event',occurrence_start=None,audit={})
        self.assertEqual(self.db.execute('select count(*) from calendar_event_changes where event_id=%s',(event['id'],)).fetchone()[0],2)
        self.assertEqual(self.db.execute('select count(*) from audit_logs where target_id=%s',(event['id'],)).fetchone()[0],2)
        before=self.snapshot()
        with self.assertRaises(HTTPException) as stale:
            mutations.delete_event(self.context,event['id'],expected_version=1,scope='event',occurrence_start=None,audit={})
        self.assertEqual(stale.exception.status_code,409)
        self.assertEqual(self.snapshot(),before)

    def test_every_recurring_effect_rolls_back_parent_replacement_and_children(self):
        self.recurring();before=self.snapshot()
        for scope in ('future','occurrence','series','event'):
            tables=('calendar_event_attendees','calendar_event_reminders','calendar_event_changes','audit_logs')
            if scope in ('future','occurrence'):tables=('calendar_events',*tables)
            for table in tables:
                with self.subTest(scope=scope,table=table):
                    cleanup=self.inject_failure(table)
                    try:
                        with self.assertRaises(HTTPException) as failure:self.mutation(scope)
                        self.assertEqual(failure.exception.status_code,503)
                        self.assertEqual(failure.exception.__context__.diag.message_primary,'synthetic calendar effect failure')
                        self.assertEqual(self.snapshot(),before)
                    finally:cleanup()

    def test_recurring_success_publishes_every_effect_once_and_stale_retry_conflicts(self):
        for scope in ('future','occurrence'):
            with self.subTest(scope=scope):
                # New source row for each operation; no prior receipt is reused.
                self.event=str(self.db.execute("insert into public.calendar_events(tenant_id,calendar_id,created_by,title,starts_at,ends_at,recurrence_rule) values(%s,%s,%s,'Series',%s,%s,'FREQ=DAILY;COUNT=10') returning id",(self.tenant,self.calendar,self.user,self.start,self.end)).fetchone()[0])
                result=self.mutation(scope)
                self.assertEqual(result['series']['version'],2)
                child=result['event']['id']
                self.assertEqual(self.db.execute('select count(*) from public.calendar_event_attendees where event_id=%s',(child,)).fetchone()[0],1)
                self.assertEqual(self.db.execute('select count(*) from public.calendar_event_reminders where event_id=%s',(child,)).fetchone()[0],1)
                self.assertEqual(self.db.execute('select count(*) from public.calendar_event_changes where event_id=any(%s)',([UUID(self.event),UUID(child)],)).fetchone()[0],2)
                before=self.snapshot()
                with self.assertRaises(HTTPException) as stale:self.mutation(scope)
                self.assertEqual(stale.exception.status_code,409)
                self.assertEqual(self.snapshot(),before)

    def test_concurrent_series_edits_cannot_mix_the_winners_children(self):
        self.recurring();barrier=threading.Barrier(2)
        def run(i):
            barrier.wait(timeout=5)
            try:self.mutation('series',title='Writer'+str(i),minutes=i);return i,200
            except HTTPException as error:return i,error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,(1,2)))
        self.assertEqual(sorted(code for _,code in results),[200,409])
        winner=next(i for i,code in results if code==200)
        self.assertEqual(self.db.execute('select email from public.calendar_event_attendees where event_id=%s',(self.event,)).fetchall(),[(f'writer{winner}@example.invalid',)])
        self.assertEqual(self.db.execute('select minutes_before from public.calendar_event_reminders where event_id=%s',(self.event,)).fetchall(),[(winner,)])

    def test_concurrent_recurring_splits_create_only_one_complete_replacement(self):
        for scope in ('future','occurrence'):
            self.event=str(self.db.execute("insert into public.calendar_events(tenant_id,calendar_id,created_by,title,starts_at,ends_at,recurrence_rule) values(%s,%s,%s,'Series',%s,%s,'FREQ=DAILY;COUNT=10') returning id",(self.tenant,self.calendar,self.user,self.start,self.end)).fetchone()[0])
            before=self.db.execute('select count(*) from public.calendar_events where tenant_id=%s',(self.tenant,)).fetchone()[0]
            barrier=threading.Barrier(2)
            def run(i):
                barrier.wait(timeout=5)
                try:return i,200,self.mutation(scope,title='Writer'+str(i),minutes=i)
                except HTTPException as error:return i,error.status_code,None
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,(1,2)))
            self.assertEqual(sorted(code for _,code,_ in results),[200,409])
            winner=next(row for row in results if row[1]==200)
            self.assertEqual(self.db.execute('select count(*) from public.calendar_events where tenant_id=%s',(self.tenant,)).fetchone()[0],before+1)
            child=winner[2]['event']['id']
            self.assertEqual(self.db.execute('select email from public.calendar_event_attendees where event_id=%s',(child,)).fetchall(),[(f'writer{winner[0]}@example.invalid',)])
            self.assertEqual(self.db.execute('select count(*) from public.audit_logs where target_id=%s',(self.event,)).fetchone()[0],1)

    def test_revoked_or_foreign_membership_cannot_mutate_a_series(self):
        self.recurring();before=self.snapshot()
        self.db.execute('delete from public.tenant_memberships where tenant_id=%s and user_id=%s',(self.tenant,self.user))
        with self.assertRaises(HTTPException) as revoked:self.mutation()
        self.assertEqual(revoked.exception.status_code,403)
        self.assertEqual(self.snapshot(),before)
        self.context.tenant_id=-1
        with self.assertRaises(HTTPException) as foreign:self.mutation()
        self.assertEqual(foreign.exception.status_code,403)

    def test_wrong_cluster_pin_is_rejected_before_any_calendar_effect(self):
        self.recurring();before=self.snapshot()
        with patch.dict(os.environ,{'MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':'0'}):
            with self.assertRaises(HTTPException) as failure:self.mutation()
        self.assertEqual(failure.exception.detail['code'],'calendar_transaction_database_mismatch')
        self.assertEqual(self.snapshot(),before)

    def test_current_database_calendar_acl_overrides_stale_context_role(self):
        self.recurring();self.context.role='owner'
        self.db.execute("update public.tenant_memberships set role='member' where tenant_id=%s and user_id=%s",(self.tenant,self.user))
        self.db.execute('update public.calendars set owner_user_id=null where id=%s',(self.calendar,))
        before=self.snapshot()
        with self.assertRaises(HTTPException) as denied:self.mutation()
        self.assertEqual(denied.exception.status_code,403)
        self.assertEqual(self.snapshot(),before)
        self.db.execute("insert into public.calendar_memberships(tenant_id,calendar_id,user_id,role) values(%s,%s,%s,'viewer')",(self.tenant,self.calendar,self.user))
        with self.assertRaises(HTTPException) as viewer:self.mutation()
        self.assertEqual(viewer.exception.status_code,403)
        self.assertEqual(self.snapshot(),before)
        self.db.execute("update public.calendar_memberships set role='editor' where calendar_id=%s and user_id=%s",(self.calendar,self.user))
        self.assertEqual(self.mutation()['series']['version'],2)

    def test_authorization_rows_remain_locked_until_mutation_commits(self):
        self.recurring();authorize=mutations._authorize
        def locked(db,context,calendars):
            authorize(db,context,calendars)
            # A separate real session cannot revoke membership beneath an
            # already authorized, still uncommitted aggregate mutation.
            with connect() as revoker:
                revoker.execute("set lock_timeout='100ms'")
                with self.assertRaises(psycopg.errors.LockNotAvailable):
                    revoker.execute('delete from public.tenant_memberships where tenant_id=%s and user_id=%s',
                        (self.tenant,self.user))
        with patch.object(mutations,'_authorize',side_effect=locked):result=self.mutation()
        self.assertEqual(result['series']['version'],2)

    def test_lost_commit_reply_is_unknown_and_explicit_version_retry_cannot_duplicate(self):
        self.recurring();factory=mutations.connect.side_effect
        class LostReply:
            def __enter__(inner):
                inner.db=factory();return inner
            def __exit__(inner,*args):inner.db.close()
            def execute(inner,*args,**kwargs):return inner.db.execute(*args,**kwargs)
            @contextmanager
            def transaction(inner):
                with inner.db.transaction():yield
                # The actual PostgreSQL COMMIT succeeded; only its reply is lost.
                raise psycopg.OperationalError('synthetic lost commit reply')
        with patch.object(mutations,'connect',side_effect=LostReply):
            with self.assertRaises(HTTPException) as failure:self.mutation()
        self.assertEqual(failure.exception.detail['code'],'calendar_commit_unknown')
        self.assertEqual(self.db.execute('select version from public.calendar_events where id=%s',(self.event,)).fetchone()[0],2)
        committed=self.snapshot()
        with self.assertRaises(HTTPException) as retry:self.mutation()
        self.assertEqual(retry.exception.status_code,409)
        self.assertEqual(self.snapshot(),committed)


if __name__ == '__main__':
    unittest.main()
