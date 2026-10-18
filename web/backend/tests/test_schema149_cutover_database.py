"""Exact146→149 executor and failure boundaries on disposable database clones.

Only protected authorization/consumer/provider transports are fixtures. SQL,
commits, row locks, protocol definitions, ACLs and durable journals are native.
"""
from dataclasses import replace
from pathlib import Path
import unittest

from deployment.lib import schema149_release as release
from tests import test_schema148_cutover_database as native
from deployment.lib.migration_executor import LockedMigrationExecutor


@unittest.skipUnless(native.DSN,'Requires marked disposable146 PostgreSQL')
class Schema149CutoverDatabaseTests(unittest.TestCase):
    connect=native.CoordinatedCutoverDatabaseTests.connect
    drop_owned=native.CoordinatedCutoverDatabaseTests.drop_owned

    def setUp(self):
        native.CoordinatedCutoverDatabaseTests.setUp(self)
        self.contract.update(version=6,operation='completed-normal-schema146-149-coordinated-release',
                             migration_manifest_sha256=release.MANIFEST_SHA256)
        self.manifest=release.admitted_manifest(native.ROOT,self.contract)
        self.db.close()  # An idle client is itself an invalid provider barrier.
        self.providers='fenced'

    def schema(self):
        with self.connect() as db:
            return db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]

    def guard(self,cursor,migration):
        def providers(before,after):
            if self.providers!='fenced':raise RuntimeError('synthetic_provider_resurrection')
        release.migration_guard(self.contract,cursor,migration,
            consumer_guard=lambda:None,provider_guard=providers)

    def executor(self,*,factory=None,guard=None,manifest=None,name='execution.json',backup=None):
        return LockedMigrationExecutor(connection_factory=factory or self.connect,manifest=manifest or self.manifest,
            state_file=self.directory/name,backup_dir=self.directory,backup_verifier=backup or (lambda _:None),
            migration_guard=guard or self.guard)

    def factory(self,number,*,after_commit=False):
        text=self.manifest.migrations[number-147].path.read_text()
        parent=self
        class Cursor:
            def __init__(self,inner):self.inner=inner
            def __getattr__(self,key):return getattr(self.inner,key)
            def __enter__(self):self.inner.__enter__();return self
            def __exit__(self,*args):return self.inner.__exit__(*args)
            def execute(self,statement,*args):
                if statement==text:
                    if not after_commit:
                        return self.inner.execute(statement.rsplit('commit;',1)[0]+'select 1/0; commit;')
                    self.inner.execute(statement,*args)
                    raise OSError('synthetic_lost_commit_response')
                return self.inner.execute(statement,*args)
        class Connection:
            def __init__(self):self.inner=parent.connect()
            def __getattr__(self,key):return getattr(self.inner,key)
            @property
            def autocommit(self):return self.inner.autocommit
            @autocommit.setter
            def autocommit(self,value):self.inner.autocommit=value
            def cursor(self):return Cursor(self.inner.cursor())
        return Connection

    def test_full_chain_reaches149_with_both_protocols_and_legacy_acl_denial(self):
        self.executor().run()
        with self.connect() as db:
            self.assertEqual(db.execute('select notification_delivery_protocol(),notification_outbox_protocol()').fetchone(),(2,2))
            self.assertFalse(db.execute("select has_table_privilege('service_role','public.notification_deliveries','UPDATE')").fetchone()[0])
            self.assertFalse(db.execute("select has_table_privilege('service_role','public.notification_outbox','UPDATE')").fetchone()[0])
        self.assertEqual(self.schema(),149)

    def test_sql_failure147_rolls_back_to146(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(147)).run()
        self.assertEqual(self.schema(),146)

    def test_sql_failure148_retains147_delivery_fence(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(148)).run()
        self.assertEqual(self.schema(),147)
        with self.connect() as db:self.assertEqual(db.execute('select notification_delivery_protocol()').fetchone()[0],2)

    def test_sql_failure149_retains148_and_requires_forward_repair(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(149)).run()
        self.assertEqual(self.schema(),148)
        with self.connect() as db:self.assertIsNone(db.execute("select to_regprocedure('public.notification_outbox_protocol()')").fetchone()[0])

    def test_lost_commit147_does_not_claim_schema146_rollback(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(147,after_commit=True)).run()
        self.assertEqual(self.schema(),147)

    def test_lost_commit148_does_not_reactivate_unfenced_delivery(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(148,after_commit=True)).run()
        self.assertEqual(self.schema(),148)

    def test_lost_commit149_retains_fenced149_without_success_receipt(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(149,after_commit=True)).run()
        self.assertEqual(self.schema(),149)
        self.assertTrue((self.directory/'execution.json').exists())
        with self.assertRaises(Exception):self.executor().run()

    def test_provider_resurrection_rejects_before_first_sql(self):
        self.providers='unknown'
        with self.assertRaisesRegex(RuntimeError,'provider_resurrection'):self.executor().run()
        self.assertEqual(self.schema(),146)

    def test_idle_unknown_database_session_rejects_quiescence(self):
        with self.connect():
            with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor().run()
        self.assertEqual(self.schema(),146)

    def test_fresh_separately_authorized_forward_attempt_after147(self):
        with self.assertRaises(Exception):self.executor(factory=self.factory(148)).run()
        self.assertEqual(self.schema(),147)
        remainder=replace(self.manifest,migrations=self.manifest.migrations[1:])
        self.executor(manifest=remainder,name='fresh-authorized-forward.json').run()
        self.assertEqual(self.schema(),149)

    def test_149_file_substitution_after_verification_cannot_execute(self):
        original=self.manifest.migrations[-1]
        path=self.directory/'149.sql';path.write_bytes(original.path.read_bytes())
        manifest=replace(self.manifest,migrations=(*self.manifest.migrations[:-1],replace(original,path=path)))
        def substitute(_):path.write_text(original.path.read_text()+'\ncreate table public.unapproved149(value int);')
        self.executor(manifest=manifest,backup=substitute).run()
        self.assertEqual(self.schema(),149)
        with self.connect() as db:self.assertIsNone(db.execute("select to_regclass('public.unapproved149')").fetchone()[0])
