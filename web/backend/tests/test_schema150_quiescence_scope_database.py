"""Native cluster-wide admission and actual published protocol-horizon probes.

Minimal marked fixture; not full providers or a protected release operation.
All DDL is rolled back. The separate marked restore DB is mutated only inside
one explicitly owned prepared transaction, which is rolled back in cleanup.
"""
import hashlib
import os
from pathlib import Path
import sys
import time
import unittest
from uuid import uuid4
import psycopg
from psycopg import sql

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib import schema150_release as release
from deployment.lib.migration_rehearsal import connect,MARKER

DSN=os.getenv('GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN')

@unittest.skipUnless(DSN,'Requires marked disposable PostgreSQL and marked independent restore database')
class QuiescenceScopeDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(DSN);self.addCleanup(self.db.close);self.addCleanup(lambda:self.db.execute('rollback'))
        self.identifier=self.db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
        self.contract={'database':{'system_identifier':self.identifier}}
        deadline=time.monotonic()+5
        while self.db.execute("select count(*) from pg_stat_activity where backend_type='client backend' and pid<>pg_backend_pid()").fetchone()[0]:
            if time.monotonic()>=deadline:self.fail('Owned fixture client cleanup did not finish')
            time.sleep(.01)
        self.db.execute('begin')
        self.db.execute("update public.application_schema_state set schema_version=150 where contract_key='core'")
        for table,column in (('notification_deliveries','status'),('notification_outbox','status'),
                             ('data_deletion_requests','state'),('data_deletion_steps','state')):
            self.db.execute(sql.SQL('create table public.{}({} text)').format(sql.Identifier(table),sql.Identifier(column)))
        for name in ('notification_delivery_protocol','notification_outbox_protocol'):
            self.db.execute(sql.SQL("create function public.{}() returns integer language sql stable as 'select 2'").format(sql.Identifier(name)))
        body=(WEB/'database/migrations'/release.SQL_NAMES[150]).read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),release.SQL_SHA256[150])
        statement=next(line for line in body.decode().splitlines() if line.startswith('create function public.data_deletion_ownership_protocol()'))
        self.db.execute(statement)
    def other_database(self):
        db=psycopg.connect(self.db.info.dsn,dbname='restored_fixture',hostaddr=self.db.info.hostaddr,
                           autocommit=True,connect_timeout=5)
        self.addCleanup(db.close)
        actual=db.execute("select (select system_identifier::text from pg_control_system()),"
            "pg_catalog.shobj_description(oid,'pg_database') from pg_catalog.pg_database where datname=pg_catalog.current_database()"
        ).fetchone()
        self.assertEqual(actual,(self.identifier,MARKER),'Foreign fixture must be positively marked in the verified cluster')
        return db
    def observation(self):
        with self.db.cursor() as cursor:return release.observe_database_quiescence(cursor,self.contract,150)
    def test_idle_client_in_another_database_is_not_quiescent(self):
        self.assertEqual(self.observation()['other_client_sessions'],0)
        other=self.other_database();other.execute('set default_transaction_read_only=on')
        with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.observation()
    def test_prepared_transaction_in_another_database_is_not_quiescent(self):
        other=self.other_database();gid='phase9-prepared-'+uuid4().hex
        self.assertEqual(other.execute('select payload from public.synthetic_preserved').fetchone(),('retained',))
        self.assertGreater(int(other.execute('show max_prepared_transactions').fetchone()[0]),0)
        other.execute('begin');other.execute("update public.synthetic_preserved set payload='owned prepared fixture'")
        other.execute(sql.SQL('prepare transaction {}').format(sql.Literal(gid)));other.close()
        def recover():
            with self.other_database() as recovery:
                recovery.execute(sql.SQL('rollback prepared {}').format(sql.Literal(gid)))
                self.assertEqual(recovery.execute('select payload from public.synthetic_preserved').fetchone(),('retained',))
        self.addCleanup(recover)
        value=self.db.execute(release.QUIESCENCE_SQL).fetchone()[0]
        self.assertEqual(value['prepared_transactions'],1)
        with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.observation()
    def test_published_deletion_protocol_has_an_exact_schema_horizon(self):
        self.assertEqual(self.db.execute('select public.data_deletion_ownership_protocol()').fetchone()[0],2)
        # Diagnostic synthetic future state only. No new migration is published,
        # no ownership RPC is bypassed and cleanup restores the original state.
        self.db.execute("update public.application_schema_state set schema_version=151 where contract_key='core'")
        self.assertEqual(self.db.execute('select public.data_deletion_ownership_protocol()').fetchone()[0],0)

if __name__=='__main__':unittest.main()
