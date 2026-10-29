"""Real canonical SQL, protocol observations and advisory locks on owned PG.

This is executor acceptance, NOT a privileged preserved-application release.
Backup/authority/provider/host acceptance are not supplied by these fixtures.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

import psycopg
from psycopg import sql

from deployment.lib import schema160_release as release
from deployment.lib.migration_executor import Migration, MigrationManifest, LockedMigrationExecutor
from deployment.lib.schema150_provider_adapter import Schema150ProviderAdapter
from tests.disposable_database_support import connect_disposable_database
from tests import test_calendar_event_concurrency_database as calendar

DSN=os.getenv('CANONICAL_EXECUTOR_SYNTHETIC_DATABASE_DSN')
ROOT=Path(os.getenv('RECONCILED_SOURCE_ROOT','/release'))
MARKER='madar-notification-synthetic-rehearsal'


def connect(dsn=DSN):
    return connect_disposable_database(dsn,markers={MARKER})


@unittest.skipUnless(DSN,'Requires an owned schema146 disposable PostgreSQL')
class CanonicalExecutorDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owned_databases=set()
        with connect() as db:
            cls.identifier=db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
            if db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]!=146:
                raise RuntimeError('canonical_executor_requires_schema146')
            cls.parameters=dict(db.info.get_parameters())
        cls.baseline='canonical146_'+uuid4().hex
        with cls.admin() as db:
            db.execute(sql.SQL('create database {} template postgres').format(sql.Identifier(cls.baseline)))
            cls.owned_databases.add(cls.baseline)
            db.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(cls.baseline),sql.Literal(MARKER)))
        cls.addClassCleanup(cls.drop,cls.baseline)

    @classmethod
    def admin(cls):
        # Pin the already verified owned loopback cluster again before DDL.
        with connect() as db:
            if db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]!=cls.identifier:
                raise RuntimeError('canonical_executor_cluster_changed')
        db=psycopg.connect(**dict(cls.parameters,dbname='template1',connect_timeout='5'),autocommit=True)
        if db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]!=cls.identifier:
            db.close();raise RuntimeError('canonical_executor_cluster_changed')
        return db

    @classmethod
    def drop(cls,name):
        if name not in cls.owned_databases or not name.startswith(('canonical146_','canonical_fault_')):
            raise RuntimeError('canonical_executor_cleanup_scope_invalid')
        with cls.admin() as db:
            row=db.execute("select shobj_description(oid,'pg_database'),pg_get_userbyid(datdba)=current_user "
                           "from pg_database where datname=%s",(name,)).fetchone()
            if row!=(MARKER,True):raise RuntimeError('canonical_executor_cleanup_identity_changed')
            db.execute(sql.SQL('drop database {}').format(sql.Identifier(name)))
            cls.owned_databases.remove(name)

    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        raw,_=release.captured_source(ROOT)
        self.manifest=MigrationManifest('b'*40,tuple(Migration(r['number'],ROOT/r['path'],r['sha256'],
            r['from_schema'],r['to_schema'],r['compatibility']) for r in raw['migrations']),coordinated=True)
        self.contract={'database':{'system_identifier':self.identifier}}

    def fault_dsn(self):
        name='canonical_fault_'+uuid4().hex
        with self.admin() as db:
            db.execute(sql.SQL('create database {} template {}').format(sql.Identifier(name),sql.Identifier(self.baseline)))
            self.owned_databases.add(name)
            db.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(name),sql.Literal(MARKER)))
        self.addCleanup(self.drop,name)
        return psycopg.conninfo.make_conninfo(**dict(self.parameters,dbname=name))

    def executor(self,dsn,*,factory=None,guard=None):
        self.boundaries=[]
        def observe(cursor,migration):
            Schema150ProviderAdapter._require_migration_session_lock(cursor)
            value=release.observe_database_quiescence(cursor,self.contract,migration.from_schema)
            self.boundaries.append((value['schema'],migration.number))
            if guard:guard(cursor,migration)
        def complete(cursor):
            Schema150ProviderAdapter._require_migration_session_lock(cursor)
            release.observe_database_quiescence(cursor,self.contract,160)
        return LockedMigrationExecutor(connection_factory=factory or (lambda:connect(dsn)),manifest=self.manifest,
            state_file=self.root/'execution.json',backup_dir=self.root,
            # No protected backup claim: this test isolates SQL/observation.
            backup_verifier=lambda path:None,migration_guard=observe,completion_guard=complete,expected_origin=146)

    def test_00_inventory_publication_reobserves_native_read_only_role_and_cluster_state(self):
        # Native SQL and durable publication; Docker/systemd/filesystem-root
        # observations remain explicit models, not privileged host acceptance.
        from tests.test_schema160_inventory_capture import OriginalInventoryCaptureTests
        from test_schema150_actor_inventory import repin
        from deployment.lib import schema150_provider_adapter as adapter
        fixture=OriginalInventoryCaptureTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        dsn=self.fault_dsn()
        with connect(dsn) as db:
            # This SQL-only cluster has no provider services. Add inert provider
            # role names so the inventory parser tests its real required scope;
            # do not substitute model role rows for the native observation.
            for role in ('authenticator', 'supabase_auth_admin', 'supabase_storage_admin'):
                if not db.execute('select 1 from pg_roles where rolname=%s',(role,)).fetchone():
                    db.execute(sql.SQL('create role {} nologin').format(sql.Identifier(role)))
            roles=db.execute(adapter.ROLE_SQL).fetchone()[0]
        fixture.roles=roles
        fixture.inventory['roles']=adapter.role_measurements(roles)
        fixture.inventory['session_scope']['writer_roles']=sorted(name for name, value in fixture.inventory['roles'].items()
            if value['login'] and name!='postgres')
        fixture.contract['database']['system_identifier']=self.identifier
        scope={'operation':fixture.contract['operation'],'context_sha256':'0'*64,
            'source_sha':fixture.contract['candidate']['source_sha'],'controller_sha':fixture.contract['candidate']['controller_sha'],
            'inventory_sha256':'0'*64,'system_identifier':self.identifier,'source_schema':146,'target_schema':160}
        fixture.inventory,scope=repin(fixture.inventory,scope)
        fixture.contract['writer_inventory_sha256']=scope['inventory_sha256']
        from deployment.lib.completed_normal_admission import encoded
        (fixture.package/'provider-inventory-input.json').write_bytes(encoded(fixture.inventory))
        original=fixture.command
        def command(args,**kwargs):
            if args[:2]!=['docker','exec']:return original(args,**kwargs)
            with connect(dsn) as db:
                cursor=db.execute(kwargs['input'])
                observations=[]
                while True:
                    if cursor.description:observations.append(cursor.fetchone()[0])
                    if not cursor.nextset():break
                self.assertEqual(len(observations),1)
                return json.dumps(observations[0])
        fixture.runtime.command.side_effect=command
        result=fixture.capture()
        self.assertFalse(result['authority_issued'])
        self.assertEqual(result['schema'],146)
        with connect(dsn) as db:
            self.assertEqual(db.execute(adapter.ROLE_SQL).fetchone()[0],roles)
            self.assertEqual(db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0],146)

    def test_01_existing_executor_requires_its_actual_advisory_locked_connection(self):
        with connect(self.fault_dsn()) as db:
            with self.assertRaisesRegex(RuntimeError,'migration_lock_required'):
                Schema150ProviderAdapter._require_migration_session_lock(db.cursor())

    def test_02_lost_committed147_reply_consumes_attempt_without_blind_replay(self):
        dsn=self.fault_dsn()
        class LostCursor:
            def __init__(self,cursor):self.cursor=cursor
            def __enter__(self):self.cursor.__enter__();return self
            def __exit__(self,*args):return self.cursor.__exit__(*args)
            def __getattr__(self,name):return getattr(self.cursor,name)
            def execute(self,query,*args,**kwargs):
                result=self.cursor.execute(query,*args,**kwargs)
                if isinstance(query,str) and 'migration_147_expected_schema_146' in query:
                    raise psycopg.OperationalError('synthetic lost committed reply')
                return result
        class LostConnection:
            def __init__(self):self.db=connect(dsn)
            def cursor(self):return LostCursor(self.db.cursor())
            def __getattr__(self,name):return getattr(self.db,name)
            @property
            def autocommit(self):return self.db.autocommit
            @autocommit.setter
            def autocommit(self,value):self.db.autocommit=value
        executor=self.executor(dsn,factory=LostConnection)
        with self.assertRaises(psycopg.OperationalError):executor.run()
        with connect(dsn) as observer:
            self.assertEqual(observer.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0],147)
        receipt=json.loads((self.root/'execution.json').read_bytes())
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['migrations'][0]['status'],'applying')
        self.assertEqual(receipt['observed_schema'],146) # Not a false commit acknowledgment.
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):executor.run()

    def test_04_each_canonical_irreversible_boundary_survives_lost_commit_reply(self):
        # Distinct disposable snapshots; an acknowledgment loss is never proof
        # that the SQL rolled back. A fresh origin146 retry must also refuse.
        for boundary in (156,157,158,159,160):
            with self.subTest(boundary=boundary):
                dsn=self.fault_dsn()
                token='migration_'+str(boundary)+'_expected_schema_'+str(boundary-1)
                class LostCursor:
                    def __init__(self,cursor):self.cursor=cursor
                    def __enter__(self):self.cursor.__enter__();return self
                    def __exit__(self,*args):return self.cursor.__exit__(*args)
                    def __getattr__(self,name):return getattr(self.cursor,name)
                    def execute(self,query,*args,**kwargs):
                        result=self.cursor.execute(query,*args,**kwargs)
                        if isinstance(query,str) and token in query:
                            raise psycopg.OperationalError('synthetic lost committed reply')
                        return result
                class LostConnection:
                    def __init__(self):self.db=connect(dsn)
                    def cursor(self):return LostCursor(self.db.cursor())
                    def __getattr__(self,name):return getattr(self.db,name)
                    @property
                    def autocommit(self):return self.db.autocommit
                    @autocommit.setter
                    def autocommit(self,value):self.db.autocommit=value
                case=self.root/str(boundary);case.mkdir()
                previous=self.root;self.root=case
                try:
                    executor=self.executor(dsn,factory=LostConnection)
                    with self.assertRaises(psycopg.OperationalError):executor.run()
                    with connect(dsn) as observer:
                        self.assertEqual(observer.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0],boundary)
                        release.observe_database_quiescence(observer.cursor(),self.contract,boundary)
                    receipt=json.loads((case/'execution.json').read_bytes())
                    self.assertEqual(receipt['status'],'failed')
                    self.assertEqual(receipt['observed_schema'],boundary-1)
                    self.assertEqual(receipt['migrations'][-1]['status'],'applying')
                    with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):executor.run()
                    self.root=case/'fresh';self.root.mkdir()
                    with self.assertRaisesRegex(RuntimeError,'origin_changed'):self.executor(dsn).run()
                finally:self.root=previous


    def test_03_foreign_idle_session_blocks_before_sql(self):
        dsn=self.fault_dsn()
        with connect(dsn) as foreign:
            with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor(dsn).run()
            self.assertEqual(foreign.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0],146)

    def test_05_actual_coordinator_runs_native_canonical_sql_and_refuses_unaccepted_private_handoff(self):
        """Real coordinator method + SQL; authority/providers/backup are MODEL.

        Carries the retained150 native parent assertions to all14 canonical
        boundaries. This is not full protected or real-provider acceptance.
        """
        dsn=self.fault_dsn();user=uuid4();bucket='canonical-'+uuid4().hex;obj=uuid4()
        def preserved(db):
            return [db.execute(query,parameters).fetchone()[0] for query,parameters in (
                ('select to_jsonb(t) from auth.users t where id=%s',(user,)),
                ('select to_jsonb(t) from storage.buckets t where id=%s',(bucket,)),
                ('select to_jsonb(t) from storage.objects t where id=%s',(obj,)),
                ('select to_jsonb(t) from public.synthetic_canonical_preserved t where id=1',()))]
        with connect(dsn) as db:
            db.execute("insert into auth.users(id,email) values(%s,'synthetic-canonical@example.invalid')",(user,))
            db.execute('insert into storage.buckets(id,name) values(%s,%s)',(bucket,bucket))
            db.execute("insert into storage.objects(id,bucket_id,name) values(%s,%s,'original-private-object')",(obj,bucket))
            db.execute('create table public.synthetic_canonical_preserved(id integer primary key,payload jsonb)')
            db.execute("insert into public.synthetic_canonical_preserved values(1,'{\"retained\":true}')")
            original=preserved(db)
        executor=self.executor(dsn)
        sys.path.insert(0,str(Path(__file__).parent))
        from test_completed_normal_maintenance_execution import maintenance_fixture
        from deployment.lib.completed_normal_profile import RECONCILED
        fixture=maintenance_fixture(self,RECONCILED,system_identifier=self.identifier)
        fixture.failure='private_acceptance'
        def migrate(*,provider_adapter):
            self.assertIs(provider_adapter,fixture.provider)
            self.assertEqual(provider_adapter.binding['system_identifier'],self.identifier)
            for step in ('provider_fence','backup_pre-migration','seal_stage'):self.assertIn(step,fixture.calls)
            self.assertNotIn('grant_160',fixture.calls)
            result=executor.run()
            with connect(dsn) as db:
                fixture.schema=db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]
            self.assertEqual(fixture.schema,160)
            return result
        fixture.driver.migrate=migrate
        with self.assertRaisesRegex(RuntimeError,'PRIVATE VALUE MUST NOT APPEAR'):fixture.driver._execute()
        self.assertIn('private_acceptance',fixture.calls)
        self.assertNotIn('grant_160',fixture.calls);self.assertNotIn('service_activate',fixture.calls)
        self.assertFalse((fixture.root/'normal-completion.json').exists());self.assertEqual(fixture.mode,'READ_ONLY')
        with connect(dsn) as db:
            self.assertEqual(preserved(db),original)
            self.assertEqual(db.execute('select public.notification_delivery_protocol(),public.notification_outbox_protocol(),public.data_deletion_ownership_protocol()').fetchone(),(2,2,2))
            self.assertIsNotNone(db.execute("select to_regclass('public.data_datasets')").fetchone()[0])
        receipt=json.loads((self.root/'execution.json').read_bytes())
        self.assertEqual(receipt['status'],'completed');self.assertEqual(receipt['observed_schema'],160)
        self.assertEqual([r['number'] for r in receipt['migrations']],list(range(147,161)))
        self.assertEqual(self.boundaries,[(n-1,n) for n in range(147,161)])

    def test_99_complete_canonical_chain_observes_all_fourteen_boundaries(self):
        executor=self.executor(DSN)
        result=executor.run()
        self.assertEqual(result['observed_schema'],160)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(self.boundaries,[(n-1,n) for n in range(147,161)])
        self.assertEqual([r['status'] for r in result['migrations']],['applied']*14)
        with connect() as db:
            observed=release.observe_database_quiescence(db.cursor(),self.contract,160)
            self.assertEqual([observed[k] for k in ('delivery_protocol','outbox_protocol','deletion_protocol')],[2,2,2])
            self.assertIsNotNone(db.execute("select to_regclass('public.data_datasets')").fetchone()[0])
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):executor.run()


@unittest.skipUnless(DSN,'Requires the canonical executor fixture')
class ZCanonicalCalendarDatabaseTests(calendar.CalendarEventConcurrencyDatabaseTests):
    def setUp(self):
        with connect() as db:
            self.assertEqual(db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0],160,
                'Calendar acceptance requires the successful canonical160 execution first')
        super().setUp()
