"""Native main156→160 reconciliation, not protected release authorization.

The owning harness first executes main's preserved146→156 SQL and functional
checks. Existing ownership/concurrency assertions then run on the actual160 DB.
"""
import hashlib
import json
import os
from pathlib import Path
import unittest

import psycopg
from tests.disposable_database_support import connect_disposable_database
from tests import test_notification_outbox_fencing_database as outbox
from tests import test_notification_fencing_database as delivery
from tests import test_data_deletion_fencing_database as deletion

DSN=os.getenv('RECONCILED_SYNTHETIC_DATABASE_DSN')
ROOT=Path(os.getenv('RECONCILED_SOURCE_ROOT','/release'))


def connect():
    return connect_disposable_database(DSN,markers={'madar-notification-synthetic-rehearsal'})


@unittest.skipUnless(DSN,'Requires owned disposable reconciled PostgreSQL')
class TransitionTests(unittest.TestCase):
    def snapshot(self,db):
        # Actual main tables/data and definitions/ACLs, including vault/sync.
        tables=db.execute("select tablename from pg_tables where schemaname='public' and "
            "(tablename like '%dataset%' or tablename like '%data_source%' or tablename like '%immutable%') order by tablename").fetchall()
        from psycopg import sql
        data={name:db.execute(sql.SQL('select to_jsonb(t) from public.{} t order by to_jsonb(t)::text').format(sql.Identifier(name))).fetchall() for name, in tables}
        functions=db.execute("select proname,pg_get_functiondef(oid),proacl::text from pg_proc where pronamespace='public'::regnamespace and "
            "(proname like '%dataset%' or proname like '%source%' or proname like '%immutable%') order by oid").fetchall()
        return data,functions

    def test_main156_then_all_four_forward_migrations_preserve_main_data_and_acl(self):
        manifest=json.loads((ROOT/'web/deployment/releases/migrations-157-160-reconciled.json').read_bytes())
        with connect() as db:
            self.assertEqual(db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],156)
            before=self.snapshot(db)
            self.assertGreater(len(before[0]),10)
            wrong=(ROOT/manifest['migrations'][-1]['path']).read_text()
            with self.assertRaisesRegex(psycopg.Error,'expected_schema_159'):db.execute(wrong)
            db.execute('rollback')
            self.assertEqual(self.snapshot(db),before)
            for row in manifest['migrations']:
                body=(ROOT/row['path']).read_text()
                self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),row['sha256'])
                self.assertEqual(body.encode(),(ROOT/row['path'].replace('/database/','/supabase/')).read_bytes())
                # Force a genuine error AFTER all DDL/DML/grants but before COMMIT.
                fault=body.rsplit('commit;',1)[0]+'select 1/0; commit;'
                with self.assertRaises(psycopg.errors.DivisionByZero):db.execute(fault)
                db.execute('rollback')
                self.assertEqual(db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],row['from_schema'])
                self.assertEqual(self.snapshot(db),before)
                db.execute(body)
                with connect() as observer:
                    self.assertEqual(observer.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],row['to_schema'])
                with self.assertRaisesRegex(psycopg.Error,'expected_schema_'+str(row['from_schema'])):db.execute(body)
                db.execute('rollback')
                self.assertEqual(self.snapshot(db),before)
            self.assertEqual(db.execute('select notification_delivery_protocol(),notification_outbox_protocol(),data_deletion_ownership_protocol()').fetchone(),(2,2,2))
            for table in ('notification_deliveries','notification_outbox','data_deletion_requests','data_deletion_steps'):
                self.assertFalse(db.execute("select has_table_privilege('service_role',%s,'UPDATE')",('public.'+table,)).fetchone()[0])
            self.assertEqual(self.snapshot(db),before)


class ReconciledDeliveryTests(delivery.NotificationFencingDatabaseTests):
    def test_second_migration_application_refuses_without_changes(self):
        with self.assertRaisesRegex(psycopg.Error,'migration_157_expected_schema_156'):
            self.db.execute((ROOT/'web/database/migrations/157_fence_notification_delivery_claims.sql').read_text())
        self.db.execute('rollback')
        self.assertEqual(self.db.execute('select notification_delivery_protocol()').fetchone()[0],2)


class ReconciledOutboxTests(outbox.OutboxFencingDatabaseTests):
    def test_deletion_notification_cancellation_is_subject_scoped_and_fenced(self):
        #159's temporary legacy cancellation entrypoint is intentionally revoked
        #by160. Accepted deletion uses generation-fenced160 RPCs instead, tested
        #by the retained deletion workflow suite in this same database.
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.execute("set role service_role; select stop_deletion_notification_work(null,'user',1)")
        self.db.execute('reset role')
        self.assertEqual(self.db.execute('select notification_outbox_protocol()').fetchone()[0],2)

    def test_second_migration_refuses_without_weakening_fencing(self):
        if not DSN:self.skipTest('Requires owned reconciled fixture')
        with self.assertRaisesRegex(psycopg.Error,'migration_159_expected_schema_158'):
            self.db.execute((ROOT/'web/database/migrations/159_fence_notification_outbox_claims.sql').read_text())
        self.db.execute('rollback')
        self.assertEqual(self.db.execute('select notification_outbox_protocol()').fetchone()[0],2)


class ReconciledDeletionTests(deletion.Deletion150OwnershipTests):
    def test_new150_pending_request_is_not_classified_as_legacy_backlog(self):
        if not DSN:self.skipTest('Requires owned reconciled fixture')
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],160)
        self.assertEqual(self.db.execute('select data_deletion_ownership_protocol()').fetchone()[0],2)
        self.assertEqual(self.current()['state'],'pending')
        self.assertEqual(self.current()['claim_generation'],0)
