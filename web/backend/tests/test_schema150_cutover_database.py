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
import unittest
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

if __name__=='__main__':unittest.main()
