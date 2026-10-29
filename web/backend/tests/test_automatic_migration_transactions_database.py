"""Native PostgreSQL transaction-hook acceptance, NOT full release acceptance."""
import hashlib,json,os,tempfile,threading,time,unittest
from pathlib import Path
from deployment.lib.migration_executor import LockedMigrationExecutor,Migration,MigrationManifest
from deployment.lib.migration_risk import scaffold

DSN=os.getenv('MADAR_AUTOMATIC_SQL_COMPONENT_DSN')
IDENTIFIER=os.getenv('MADAR_AUTOMATIC_SQL_COMPONENT_IDENTIFIER')

@unittest.skipUnless(DSN and IDENTIFIER,'Requires exact owned PostgreSQL17 component cluster')
class AutomaticTransactionDatabaseTests(unittest.TestCase):
    def connect(self):
        import psycopg
        c=psycopg.connect(DSN,autocommit=True)
        if c.execute("select system_identifier::text,shobj_description(oid,'pg_database') from pg_control_system(),pg_database where datname=current_database()").fetchone()!=(IDENTIFIER,'madar-automatic-sql-native-component'):
            c.close();raise RuntimeError('native_component_database_refused')
        return c
    def setUp(self):
        self.db=self.connect();self.addCleanup(self.db.close)
        self.db.execute('drop table if exists public.native_budget,public.application_schema_state;create table public.application_schema_state(contract_key text primary key,schema_version integer);insert into public.application_schema_state values(\'core\',1);create table public.native_budget(id bigint);insert into public.native_budget values(7)')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def execute(self,*,guard=None,sql=None,factory=None):
        body=sql or scaffold(1,2,'ALTER TABLE public.native_budget ADD COLUMN note pg_catalog.text;')
        path=self.root/'migration.sql';path.write_bytes(body)
        m=Migration(2,path,hashlib.sha256(body).hexdigest(),1,2,'expand-only')
        return LockedMigrationExecutor(connection_factory=factory or self.connect,manifest=MigrationManifest('a'*40,(m,),coordinated=True),state_file=self.root/'execution.json',backup_dir=self.root,backup_verifier=lambda _:None,expected_origin=1,transaction_guard=guard or (lambda *_:None),migration_guard=lambda cursor,_:cursor.execute("set statement_timeout='2s';set lock_timeout='100ms';set transaction_timeout='2s'")).run()
    def test_audited_additive_transaction_commits_and_preserves_data(self):
        body=scaffold(1,2,'CREATE TABLE public.native_new (id pg_catalog.int8);')
        self.addCleanup(lambda:self.db.execute('drop table if exists public.native_new'))
        result=self.execute(sql=body)
        self.assertEqual(result['observed_schema'],2)
        self.assertEqual(self.db.execute('select id from public.native_budget').fetchone(),(7,))
        self.assertTrue(self.db.execute("select to_regclass('public.native_new') is not null").fetchone()[0])
    def test_guard_holds_table_lock_and_advisory_lock_on_same_session_through_sql(self):
        pids=[]
        def guard(cursor,_):
            cursor.execute('lock table public.native_budget in access exclusive mode')
            cursor.execute("select pg_backend_pid(),count(*) from pg_locks where pid=pg_backend_pid() and granted and (locktype='advisory' or mode='AccessExclusiveLock')")
            pid,count=cursor.fetchone();pids.append(pid);self.assertGreaterEqual(count,2)
            with self.connect() as other:
                other.execute("set lock_timeout='50ms'")
                with self.assertRaises(Exception):other.execute('insert into public.native_budget values(8)')
        result=self.execute(guard=guard)
        self.assertEqual(len(pids),1);self.assertEqual(result['status'],'completed')
        self.assertEqual(self.db.execute('select id,note from public.native_budget').fetchall(),[(7,None)])
    def test_guard_failure_rolls_back_before_schema_or_ddl_changes(self):
        def guard(cursor,_):
            cursor.execute('lock table public.native_budget in access exclusive mode')
            raise RuntimeError('live_budget_exceeded')
        with self.assertRaisesRegex(RuntimeError,'live_budget_exceeded'):self.execute(guard=guard)
        self.assertEqual(self.db.execute("select schema_version from public.application_schema_state").fetchone(),(1,))
        self.assertEqual(self.db.execute("select count(*) from information_schema.columns where table_name='native_budget' and column_name='note'").fetchone(),(0,))
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):self.execute()
    def test_contended_lock_refuses_without_sql_or_schema_advance(self):
        with self.connect() as blocker:
            blocker.execute('begin;lock table public.native_budget in access exclusive mode')
            with self.assertRaises(Exception):self.execute(guard=lambda c,_:c.execute('lock table public.native_budget in access exclusive mode'))
            blocker.rollback()
        self.assertEqual(self.db.execute('select schema_version from public.application_schema_state').fetchone(),(1,))
    def test_lost_commit_reply_does_not_replay_committed_sql(self):
        actual=self.connect()
        class Cursor:
            def __init__(self,c):self.real=c
            def __enter__(self):self.real.__enter__();return self
            def __exit__(self,*a):return self.real.__exit__(*a)
            def execute(self,query,params=None):
                self.real.execute(query,params)
                if str(query).rstrip().endswith('COMMIT;'):raise ConnectionError('deliberately lost reply AFTER real COMMIT')
            def fetchone(self):return self.real.fetchone()
        class Connection:
            autocommit=True
            def cursor(self):return Cursor(actual.cursor())
            def rollback(self):actual.rollback()
            def close(self):actual.close()
        with self.assertRaises(ConnectionError):self.execute(factory=Connection)
        self.assertEqual(self.db.execute('select schema_version from public.application_schema_state').fetchone(),(2,))
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):self.execute()
