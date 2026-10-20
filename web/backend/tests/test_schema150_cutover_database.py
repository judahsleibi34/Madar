"""Native146→150 executor/provider-cursor integration and lost commit replies.

Real published SQL, advisory locks, journal/flock, committed schema and selected
original Auth/Storage/application rows. Authority, supervisors, object writers,
roles/backup and activation remain MODEL fixtures. This is NOT the complete
privileged release, full-provider acceptance or a production admission.
"""
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import Mock,patch
from uuid import uuid4

from psycopg import sql
from tests.disposable_database_support import connect_disposable_database
from tests import test_schema148_cutover_database as native
from tests import test_schema150_quiescence_scope_database as scope
from deployment.lib import schema150_release as release
from deployment.lib.migration_executor import LockedMigrationExecutor,MigrationManifest,Migration

@unittest.skipUnless(native.DSN,'Requires marked disposable schema146 PostgreSQL')
class Schema150CutoverDatabaseTests(unittest.TestCase):
    connect=native.CoordinatedCutoverDatabaseTests.connect
    migration_hook_fixture=scope.QuiescenceScopeDatabaseTests.migration_hook_fixture

    def setUp(self):
        native.CoordinatedCutoverDatabaseTests.setUp(self)
        self.identifier=self.contract['database']['system_identifier']
        self.user=uuid4();self.bucket='phase10-'+uuid4().hex;self.object=uuid4()
        self.db.execute("insert into auth.users(id,email) values(%s,'synthetic-phase10@example.invalid')",(self.user,))
        self.db.execute('insert into storage.buckets(id,name) values(%s,%s)',(self.bucket,self.bucket))
        self.db.execute("insert into storage.objects(id,bucket_id,name) values(%s,%s,'original-object')",(self.object,self.bucket))
        self.db.execute("create table public.synthetic_phase10_preserved(id integer primary key,payload jsonb)")
        self.db.execute("insert into public.synthetic_phase10_preserved values(1,'{\"retained\":true}')")
        self.original=self.preserved(self.db)
        self.actor,self.journal,_=self.migration_hook_fixture(preserve_origin=True)
        raw,_=release.captured_source(native.ROOT)
        self.manifest=MigrationManifest('a'*40,tuple(Migration(row['number'],native.ROOT/row['path'],
            row['sha256'],row['from_schema'],row['to_schema'],row['compatibility']) for row in raw['migrations']),coordinated=True)
        # Cluster-wide quiescence must not exempt this fixture's idle admin or
        # setup connection. Only the executor connection may remain at entry.
        self.db.close();self.admin.close()

    def drop_owned(self):
        self.assertRegex(self.name,r'^madar_cutover_[0-9a-f]{32}$')
        with self.connect() as db:self.assertEqual(db.execute('select current_database()').fetchone()[0],self.name)
        with connect_disposable_database(native.DSN,markers={native.MARKER}) as admin:
            admin.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(self.name)))

    def preserved(self,db):
        return [db.execute(query,parameters).fetchone()[0] for query,parameters in (
            ('select to_jsonb(t) from auth.users t where id=%s',(self.user,)),
            ('select to_jsonb(t) from storage.buckets t where id=%s',(self.bucket,)),
            ('select to_jsonb(t) from storage.objects t where id=%s',(self.object,)),
            ('select to_jsonb(t) from public.synthetic_phase10_preserved t where id=1',()))]

    def executor(self,*,factory=None,name='execution.json'):
        return LockedMigrationExecutor(connection_factory=factory or self.connect,manifest=self.manifest,
            state_file=self.directory/name,backup_dir=self.directory,backup_verifier=lambda _:None,
            migration_guard=self.actor.migration_guard,failure_formatter=lambda e:type(e).__name__)

    def test_full_published_chain_records_each_boundary_and_preserves_original_rows(self):
        result=self.executor().run()
        self.assertEqual(result['observed_schema'],150)
        self.assertEqual([(row['number'],row['status'],row['checksum']) for row in result['migrations']],
            [(n,'applied',release.SQL_SHA256[n]) for n in (147,148,149,150)])
        with self.connect() as db:
            self.assertEqual(self.preserved(db),self.original)
            self.assertEqual(db.execute('select public.notification_delivery_protocol(),public.notification_outbox_protocol(),public.data_deletion_ownership_protocol()').fetchone(),(2,2,2))
            for table in ('notification_deliveries','notification_outbox','data_deletion_requests','data_deletion_steps'):
                self.assertFalse(db.execute('select has_table_privilege(%s,%s,%s)',('service_role','public.'+table,'UPDATE')).fetchone()[0])
        self.assertEqual([r['payload']['schema'] for r in self.journal.read() if r['event']=='quiescence'],[146,147,148,149])
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):self.executor().run()

    def interrupted(self,number,*,crash=False):
        parent=self;statement=self.manifest.migrations[number-147].path.read_text()
        class Cursor:
            def __init__(self,inner):self.inner=inner
            def __getattr__(self,name):return getattr(self.inner,name)
            def __enter__(self):self.inner.__enter__();return self
            def __exit__(self,*args):return self.inner.__exit__(*args)
            def execute(self,body,*args):
                value=self.inner.execute(body,*args)
                if body==statement:
                    if crash:os._exit(83)
                    raise OSError('synthetic_lost_commit_reply')
                return value
        class Connection:
            def __init__(self):self.inner=parent.connect()
            def __getattr__(self,name):return getattr(self.inner,name)
            @property
            def autocommit(self):return self.inner.autocommit
            @autocommit.setter
            def autocommit(self,value):self.inner.autocommit=value
            def cursor(self):return Cursor(self.inner.cursor())
        if crash:
            child=multiprocessing.get_context('fork').Process(target=lambda:self.executor(factory=Connection).run())
            child.start();child.join(30)
            if child.is_alive():child.kill();child.join(5);self.fail('Owned migration process did not exit at injection point')
            self.assertEqual(child.exitcode,83)
        else:
            with self.assertRaisesRegex(OSError,'lost_commit_reply'):self.executor(factory=Connection).run()
        with self.connect() as observed:
            self.assertEqual(observed.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],number)
            self.assertEqual(self.preserved(observed),self.original)
        state=json.loads((self.directory/'execution.json').read_bytes())
        self.assertEqual(state['status'],'running' if crash else 'failed')
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):self.executor().run()
        # A distinct attempt models separately admitted forward repair. No old
        # SQL is replayed: the executor observes the database and skips by schema.
        repaired=self.executor(name='separate-model-authorized-forward.json').run()
        self.assertEqual(repaired['observed_schema'],150)
        self.assertEqual([r['number'] for r in repaired['migrations'] if r['status']=='already_applied'],list(range(147,number+1)))

    def test_lost147_commit_reply_requires_fresh_observation_and_separate_attempt(self):self.interrupted(147)
    def test_lost148_commit_reply_requires_fresh_observation_and_separate_attempt(self):self.interrupted(148)
    def test_lost149_commit_reply_requires_fresh_observation_and_separate_attempt(self):self.interrupted(149)
    def test_lost150_commit_reply_requires_fresh_observation_and_separate_attempt(self):self.interrupted(150)
    def test_actual_executor_process_exit_after147_preserves_fence_and_allows_only_separate_forward_attempt(self):self.interrupted(147,crash=True)
    def test_actual_executor_process_exit_after150_never_replays_committed_sql(self):self.interrupted(150,crash=True)

    def parent_context(self):
        """Real coordinator method, process flocks and SQL; MODEL outer gates.

        This does not pass operational admission. It isolates the new root
        migration edge; authority, backup, sealed-container observations and
        installed-source ownership are explicitly synthetic test boundaries.
        """
        sys.path.insert(0,str(Path(__file__).parent))
        self.enterContext(patch.dict(os.environ,{'MADAR_TEST_REPOSITORY_ROOT':str(native.ROOT/'web')}))
        from test_completed_normal_parent_migration import ParentMigrationTests
        from test_schema150_admission import deletion_contract
        from deployment.lib import completed_normal_execution as execution
        from deployment.lib import completed_normal_migration as migration
        from deployment.lib import schema150_provider_adapter as provider
        from deployment.lib.control_plane_upgrade import acquire_lock
        contract=deletion_contract();contract['database']['system_identifier']=self.identifier
        fixture=ParentMigrationTests();fixture.setUp(contract=contract,native=True)
        self.addCleanup(fixture.doCleanups)
        actor=self.actor
        actor.contract=fixture.contract;actor.binding=fixture.actor.binding;actor.root=fixture.root
        actor.barrier=fixture.root/'provider-barrier.json';actor.barrier.write_text('{}')
        fixture.actor=actor;fixture.driver.actor.runtime=actor.runtime
        # Keep the native cursor guard, not the fixture's model callback.
        def observe(binding,*,cursor=None):
            if cursor is not None:return provider.Schema150ProviderAdapter.observe_quiescence(actor,binding,cursor=cursor)
            with self.connect() as db:
                return release.observe_database_quiescence(db.cursor(),fixture.contract,146)
        actor.observe_quiescence=Mock(side_effect=observe)
        fixture.driver.ops.upgrade_root.mkdir(mode=0o700)
        for path in (fixture.driver.ops.upgrade_root/'upgrade.lock',fixture.state/'deploy.lock'):path.touch(mode=0o600)
        fixture.driver.lock=acquire_lock(fixture.driver.ops.upgrade_root/'upgrade.lock',create=False)
        fixture.driver.ops.deploy_lock_descriptor=acquire_lock(fixture.state/'deploy.lock',create=False)
        actor.lock_descriptors=(fixture.driver.lock,fixture.driver.ops.deploy_lock_descriptor)
        def cleanup():
            for key,owner in (('lock',fixture.driver),('deploy_lock_descriptor',fixture.driver.ops)):
                value=getattr(owner,key)
                if value is not None:os.close(value);setattr(owner,key,None)
        self.addCleanup(cleanup)
        # Native flocks/PID/inodes, with synthetic metadata ownership only.
        self.enterContext(patch.object(provider,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(execution,'protected',lambda p,**kw:Path(p)))
        ops=fixture.driver.ops;ops.runtime_root=fixture.directory/'runtime';ops.runtime_root.mkdir(mode=0o700)
        ops.authorization_file=fixture.directory/'synthetic-credential'
        ops.write_authorization=Mock(side_effect=lambda *a,**kw:ops.authorization_file.write_bytes(b'not-a-production-credential'))
        ops.clear_authorization=Mock(side_effect=lambda:ops.authorization_file.unlink(missing_ok=True))
        ops.release_deployment_lock=Mock(side_effect=lambda:self.fail('Borrowed parent lock must remain held'))
        fixture.driver.root_credential=execution.CompletedNormalUpgrade.root_credential.__get__(fixture.driver)
        def schema():
            with self.connect() as db:
                return db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
        fixture.driver.actor.native=Mock(side_effect=schema)
        self.enterContext(patch.object(migration,'connection_factory',side_effect=lambda _:self.connect()))
        self.enterContext(patch.object(migration,'verify_migration_backup'))
        fixture.manifest=type(self.manifest)(fixture.sha,self.manifest.migrations,coordinated=True)
        fixture.admitted.return_value=fixture.manifest
        return fixture

    def test_parent_coordinator_runs_published_sql_with_actual_parent_locks_and_does_not_promote_origin(self):
        fixture=self.parent_context();original=(fixture.state/'state.json').read_bytes()
        result=fixture.run_parent()
        self.assertEqual(result['observed_schema'],150)
        self.assertEqual((fixture.state/'state.json').read_bytes(),original)
        with self.connect() as db:
            self.assertEqual(self.preserved(db),self.original)
            self.assertEqual(db.execute('select public.notification_delivery_protocol(),public.notification_outbox_protocol(),public.data_deletion_ownership_protocol()').fetchone(),(2,2,2))
        fixture.driver.ops.release_deployment_lock.assert_not_called()
        self.assertFalse(fixture.driver.ops.authorization_file.exists())
        from deployment.lib.schema150_provider_lifecycle import ProtectedProviderJournal
        self.assertEqual([r['payload']['schema'] for r in ProtectedProviderJournal(fixture.journal_root).read() if r['event']=='quiescence'],[146,147,148,149,150])

    def test_forked_child_cannot_borrow_parent_lock_ownership_to_run_migration(self):
        fixture=self.parent_context()
        def attempt():
            try:fixture.run_parent()
            except RuntimeError as error:
                os._exit(84 if str(error)=='schema150_provider_coordinator_lock_not_held' else 85)
            os._exit(86)
        child=multiprocessing.get_context('fork').Process(target=attempt);child.start();child.join(15)
        if child.is_alive():child.kill();child.join(5);self.fail('Owned child did not exit')
        self.assertEqual(child.exitcode,84)
        self.assertFalse((fixture.state/'migrations').exists())
        with self.connect() as db:
            self.assertEqual(db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],146)

    def test_parent_sql_refuses_a_foreign_session_without_migrating_or_promoting(self):
        fixture=self.parent_context()
        with self.connect() as other:
            with self.assertRaisesRegex(RuntimeError,'not_quiescent'):fixture.run_parent()
            self.assertEqual(other.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],146)
        self.assertEqual(json.loads((fixture.state/'state.json').read_bytes()),fixture.initial)

    def test_parent_lost150_commit_response_keeps_origin_unpromoted_and_revokes_credential(self):
        fixture=self.parent_context();parent=self
        from deployment.lib import completed_normal_migration as migration
        statement=self.manifest.migrations[-1].path.read_text()
        class Cursor:
            def __init__(self,inner):self.inner=inner
            def __getattr__(self,name):return getattr(self.inner,name)
            def __enter__(self):self.inner.__enter__();return self
            def __exit__(self,*args):return self.inner.__exit__(*args)
            def execute(self,body,*args):
                result=self.inner.execute(body,*args)
                if body==statement:raise OSError('synthetic_lost_commit_reply')
                return result
        class Connection:
            def __init__(self):self.inner=parent.connect()
            def __getattr__(self,name):return getattr(self.inner,name)
            @property
            def autocommit(self):return self.inner.autocommit
            @autocommit.setter
            def autocommit(self,value):self.inner.autocommit=value
            def cursor(self):return Cursor(self.inner.cursor())
        with patch.object(migration,'connection_factory',side_effect=lambda _:Connection()):
            with self.assertRaisesRegex(RuntimeError,'completed_migration_error_OSError'):fixture.run_parent()
        with self.connect() as observed:
            self.assertEqual(observed.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],150)
            self.assertEqual(self.preserved(observed),self.original)
        self.assertFalse(fixture.driver.ops.authorization_file.exists())
        self.assertEqual(json.loads((fixture.state/'state.json').read_bytes()),fixture.initial)
        state=json.loads((fixture.state/'migrations'/fixture.sha/'execution.json').read_bytes())
        self.assertEqual(state['status'],'failed')
        with self.assertRaisesRegex(RuntimeError,'provider_witness_changed'):fixture.run_parent()

    def test_late_session_after150_commit_prevents_completed_receipt_and_activation(self):
        fixture=self.parent_context();actor=fixture.actor
        original=actor.migration_completion_guard
        foreign=[]
        def late_writer(cursor):
            foreign.append(self.connect())
            return original(cursor)
        actor.migration_completion_guard=late_writer
        try:
            with self.assertRaisesRegex(RuntimeError,'completed_migration_error_RuntimeError'):fixture.run_parent()
        finally:
            for connection in foreign:connection.close()
        with self.connect() as db:
            self.assertEqual(db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],150)
            self.assertEqual(self.preserved(db),self.original)
        state=json.loads((fixture.state/'migrations'/fixture.sha/'execution.json').read_bytes())
        self.assertEqual((state['status'],state['observed_schema']),('failed',150))
        self.assertEqual(json.loads((fixture.state/'state.json').read_bytes()),fixture.initial)
        self.assertFalse(fixture.driver.ops.authorization_file.exists())

if __name__=='__main__':unittest.main()
