"""Actual route writes raced through independent native PostgreSQL connections.

Authorization and side-effect transports are fixtures; UPDATE predicates, locks,
row versions and commit visibility are real PostgreSQL, not an in-memory mock.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from psycopg import sql

import routes.calendar_routes as routes
from tests import test_native_business_integrity_database as native

DSN, connect = native.DSN, native.connect


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

    def race(self, delete_second=False):
        barrier = threading.Barrier(2)
        local = threading.local()
        context = SimpleNamespace(tenant_id=self.tenant, user_id=self.user)

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


if __name__ == '__main__':
    unittest.main()
