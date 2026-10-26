"""Native cluster-wide admission and actual published protocol-horizon probes.

Minimal marked fixture; not full providers or a protected release operation.
All DDL is rolled back. The separate marked restore DB is mutated only inside
one explicitly owned prepared transaction, which is rolled back in cleanup.
"""
import hashlib
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import time
import tempfile
import unittest
from unittest.mock import Mock,patch
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
        body=(WEB/'database/historical-architecture-146-150'/release.SQL_NAMES[150]).read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),release.SQL_SHA256[150])
        statement=next(line for line in body.decode().splitlines() if line.startswith('create function public.data_deletion_ownership_protocol()'))
        self.db.execute(statement)
    def other_database(self,**options):
        db=psycopg.connect(self.db.info.dsn,dbname='restored_fixture',hostaddr=self.db.info.hostaddr,
                           autocommit=True,connect_timeout=5,**options)
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

    def test_database_replication_connection_can_write_and_must_block_admission(self):
        # PostgreSQL database-mode replication connections accept ordinary SQL
        # but report backend_type=walsender, rather than client backend.
        other=self.other_database(replication='database')
        self.assertEqual(other.execute('select backend_type from pg_stat_activity where pid=pg_backend_pid()').fetchone(),('walsender',))
        other.execute('begin')
        try:
            other.execute("update public.synthetic_preserved set payload='owned replication-mode writer'")
            self.assertEqual(other.execute('select payload from public.synthetic_preserved').fetchone(),('owned replication-mode writer',))
        finally:other.execute('rollback')
        self.assertEqual(other.execute('select payload from public.synthetic_preserved').fetchone(),('retained',))
        with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.observation()

    def test_background_classification_is_null_safe_and_binds_parallel_leader(self):
        own=self.db.execute('select pg_backend_pid()').fetchone()[0]
        statement=release.BACKGROUND_WRITER_SQL.replace('pg_catalog.pg_stat_activity',
            '(select %s::integer as pid,%s::text as backend_type,%s::integer as leader_pid) as actors')
        for kind,leader,expected in ((None,None,1),('unknown extension worker',None,1),
                ('logical replication worker',None,1),('walsender',None,1),
                ('parallel worker',None,1),('parallel worker',own+1,1),
                ('parallel worker',own,0),('checkpointer',None,0),('client backend',None,0)):
            with self.subTest(kind=kind,leader=leader):
                self.assertEqual(self.db.execute(statement,(own+100000,kind,leader)).fetchone()[0],expected)

    def migration_hook_fixture(self,*,preserve_origin=False):
        """Native SQL/locks, real journal/flock, MODEL host/authority boundaries.

        This is not a privileged controller or provider-fencing acceptance test.
        """
        from deployment.lib import schema150_provider_adapter as adapter
        from deployment.lib import schema150_provider_lifecycle as lifecycle
        from deployment.lib import schema149_provider_lifecycle as retained
        from deployment.lib.completed_normal_profile import DELETION
        from deployment.lib.migration_executor import Migration
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700);(root/'provider-journal').mkdir(mode=0o700)
        stack=ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch.object(retained,'require_root_directory',lambda p:None))
        stack.enter_context(patch.object(retained,'protected',lambda p,**kw:Path(p)))
        stack.enter_context(patch.object(adapter,'private_json',lambda p:__import__('json').loads(Path(p).read_bytes())))
        stack.enter_context(patch('deployment.lib.schema149_consumers.verify_host_processes'))
        binding={'operation':DELETION.operation,'context_sha256':'a'*64,'source_sha':'b'*40,'controller_sha':'c'*40,
            'inventory_sha256':'d'*64,'system_identifier':self.identifier,'source_schema':146,'target_schema':150}
        actor=adapter.Schema150ProviderAdapter.__new__(adapter.Schema150ProviderAdapter)
        actor.binding=binding;actor.root=root
        # This adapter fixture tests the exact historical150 operation, even
        # when its enclosing SQL scaffold originated from the148 test class.
        actor.contract={**self.contract,'operation':DELETION.operation,'version':DELETION.version}
        actor.require_authority=Mock();actor._attest=Mock();actor._supervisors_stopped=Mock()
        actor.runtime=Mock();actor.inventory={'containers':{'native:db':{'id':'e'*64}}}
        actor._row=Mock(return_value={'State':{'Pid':os.getpid()}})
        actor._roles=Mock(return_value={});actor._expected_roles=Mock(return_value={})
        actor._object_preservation=Mock();actor.activation_guard=Mock(return_value={'candidate_read_only':True})
        actor.barrier=root/'provider-barrier.json';actor.barrier.write_text('{}')
        actor._sql=Mock(side_effect=AssertionError('Migration must observe its existing cursor, not another database session'))
        journal=lifecycle.ProtectedProviderJournal(root/'provider-journal')
        journal.append('prepared',{'binding':binding,'preimage':{'synthetic':'MODEL ONLY'}})
        for step in lifecycle.FENCE_STEPS:
            journal.append('effect_intent',{'step':step});journal.append('effect_complete',{'step':step})
        if not preserve_origin:
            self.db.execute("update public.application_schema_state set schema_version=149 where contract_key='core'")
            self.db.execute('drop function public.data_deletion_ownership_protocol()')
        return actor,journal,Migration(150,WEB/'database/historical-architecture-146-150'/release.SQL_NAMES[150],release.SQL_SHA256[150],149,150,'coordinated')

    def acquire_migration_lock(self):
        from deployment.lib.migration_executor import LockedMigrationExecutor
        self.assertIs(self.db.execute('select pg_try_advisory_lock(%s)',(LockedMigrationExecutor.LOCK_KEY,)).fetchone()[0],True)

    def test_migration_callback_uses_its_own_real_advisory_locked_session(self):
        actor,journal,migration=self.migration_hook_fixture();self.acquire_migration_lock()
        with self.db.cursor() as cursor:observed=actor.migration_guard(cursor,migration)
        self.assertEqual(observed['schema'],149);self.assertEqual(observed['other_client_sessions'],0)
        self.assertEqual(journal.read()[-1]['event'],'quiescence')
        actor._sql.assert_not_called()

    def test_migration_callback_without_real_advisory_lock_refuses(self):
        actor,journal,migration=self.migration_hook_fixture();before=journal.read()
        with self.db.cursor() as cursor,self.assertRaisesRegex(RuntimeError,'migration_lock_required'):
            actor.migration_guard(cursor,migration)
        self.assertEqual(journal.read(),before)

    def test_migration_callback_does_not_exempt_another_client(self):
        actor,journal,migration=self.migration_hook_fixture();self.acquire_migration_lock();self.other_database()
        before=journal.read()
        with self.db.cursor() as cursor,self.assertRaisesRegex(RuntimeError,'not_quiescent'):
            actor.migration_guard(cursor,migration)
        self.assertEqual(journal.read(),before)

    def test_migration_callback_checks_actual_protocol_before_accepting_boundary(self):
        actor,journal,migration=self.migration_hook_fixture();self.acquire_migration_lock()
        self.db.execute("create or replace function public.notification_outbox_protocol() returns integer language sql stable as 'select 1'")
        before=journal.read()
        with self.db.cursor() as cursor,self.assertRaisesRegex(RuntimeError,'not_quiescent'):
            actor.migration_guard(cursor,migration)
        self.assertEqual(journal.read(),before)

if __name__=='__main__':unittest.main()
