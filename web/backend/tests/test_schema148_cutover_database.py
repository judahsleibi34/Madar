"""Actual exact-coordinator SQL/journal interruption tests on disposable clones.

Only authorization and consumer transport are fixtures; PostgreSQL transactions,
leases, locks, disconnects, schema/grants and executor journals are real.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from tests.disposable_database_support import connect_disposable_database
from deployment.lib import schema148_release as release
from deployment.lib.migration_executor import LockedMigrationExecutor

DSN=os.getenv('SCHEMA148_SYNTHETIC_DATABASE_DSN')
ROOT=Path(os.getenv('SCHEMA148_SOURCE_ROOT','/release'))
MARKER='madar-notification-synthetic-rehearsal'


def crash_executor_child(dsn,root,state_file,point):
    def connect():return connect_disposable_database(dsn,markers={MARKER})
    with connect() as db:identifier=db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
    contract={'version':5,'operation':'completed-normal-schema146-148-coordinated-release',
        'database':{'system_identifier':identifier},'migration_manifest_sha256':release.MANIFEST_SHA256,
        'candidate':{'source_sha':'a'*40}}
    with patch('deployment.lib.completed_normal_admission.require_fresh_authorization'):
        manifest=release.admitted_manifest(root,contract);first=manifest.migrations[0].path.read_text()
        class Cursor:
            def __init__(self,inner):self.inner=inner
            def __getattr__(self,name):return getattr(self.inner,name)
            def __enter__(self):self.inner.__enter__();return self
            def __exit__(self,*args):return self.inner.__exit__(*args)
            def execute(self,statement,*args):
                if statement==first and point=='before_sql':os._exit(80)
                result=self.inner.execute(statement,*args)
                if statement==first and point=='after_commit':os._exit(81)
                return result
        class Connection:
            def __init__(self):self.inner=connect()
            def __getattr__(self,name):return getattr(self.inner,name)
            @property
            def autocommit(self):return self.inner.autocommit
            @autocommit.setter
            def autocommit(self,value):self.inner.autocommit=value
            def cursor(self):return Cursor(self.inner.cursor())
        executor=LockedMigrationExecutor(connection_factory=Connection,manifest=manifest,state_file=Path(state_file),
            backup_dir=Path(state_file).parent,backup_verifier=lambda _:None,
            migration_guard=lambda cursor,migration:release.migration_guard(contract,cursor,migration,consumer_guard=lambda:None))
        executor.run()


@unittest.skipUnless(DSN,'Requires marked disposable schema146 PostgreSQL')
class CoordinatedCutoverDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.name='madar_cutover_'+uuid4().hex
        self.admin=connect_disposable_database(DSN,markers={MARKER});self.addCleanup(self.admin.close)
        self.assertEqual(self.admin.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0],146)
        self.admin.execute(sql.SQL('create database {} template postgres').format(sql.Identifier(self.name)))
        self.addCleanup(self.drop_owned)
        self.dsn=make_conninfo(DSN,dbname=self.name)
        self.admin.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(self.name),sql.Literal(MARKER)))
        self.db=self.connect();self.addCleanup(self.db.close)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.directory=Path(temporary.name)
        self.contract={'version':5,'operation':'completed-normal-schema146-148-coordinated-release',
            'database':{'system_identifier':self.db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]},
            'migration_manifest_sha256':release.MANIFEST_SHA256,'candidate':{'source_sha':'a'*40}}
        item=patch('deployment.lib.completed_normal_admission.require_fresh_authorization');self.authorization=item.start();self.addCleanup(item.stop)
        self.manifest=release.admitted_manifest(ROOT,self.contract)
        self.consumer_state='stopped'

    def drop_owned(self):
        # Fresh unguessable clone name plus verified marker; never drop the base.
        with self.connect() as db:
            self.assertEqual(db.execute('select current_database()').fetchone()[0],self.name)
        self.admin.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(self.name)))

    def connect(self):return connect_disposable_database(self.dsn,markers={MARKER})
    def schema(self):return self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
    def consumers(self):
        if self.consumer_state!='stopped':raise RuntimeError('synthetic_supervisor_resurrection')
    def guard(self,cursor,migration):release.migration_guard(self.contract,cursor,migration,consumer_guard=self.consumers)
    def executor(self,*,guard=None,factory=None,manifest=None,name='execution.json'):
        return LockedMigrationExecutor(connection_factory=factory or self.connect,manifest=manifest or self.manifest,
            state_file=self.directory/name,backup_dir=self.directory,backup_verifier=lambda _:None,
            migration_guard=guard or self.guard)
    def add_processing(self,expired=False):
        identifier=uuid4()
        self.db.execute("insert into public.notification_deliveries(id,channel,template,deduplication_key,status,processing_lease_until) values(%s,'internal','synthetic',%s,'processing',clock_timestamp()+(%s)::interval)",(identifier,str(identifier),'-1 second' if expired else '1 minute'))
        return identifier
    def apply147(self):self.db.execute((ROOT/self.manifest.migrations[0].path).read_text())

    def test_root_preservation_includes_all_auth_storage_tables_and_detects_change(self):
        from deployment.lib.completed_normal_database import migration_customer_snapshot,verify_migration_customer_preservation
        from types import SimpleNamespace
        self.db.execute("create table auth.identities(id uuid); create table auth.mfa_factors(id uuid,secret text); create table auth.sessions(id int,marker text); insert into auth.sessions values(1,'synthetic-original'); create table storage.recovery_fixture(id int,marker text); insert into storage.recovery_fixture values(1,'synthetic-object-metadata')")
        def command(args):
            cursor=self.db.execute(args[-1]);lines=[]
            while True:
                if cursor.description:lines += [str(row[0]) for row in cursor.fetchall()]
                if not cursor.nextset():break
            return '\n'.join(lines)
        runtime=SimpleNamespace(command=command)
        self.contract['database']['container_id']='synthetic-transport-only'
        with patch('deployment.lib.completed_normal_database.observe_native',side_effect=lambda *a,**kw:self.schema()):
            before=migration_customer_snapshot(self.contract,runtime)
            self.assertIn('auth.sessions',before['columns']);self.assertIn('storage.recovery_fixture',before['columns'])
            self.executor().run()
            after=migration_customer_snapshot(self.contract,runtime,columns=before['columns'])
            self.assertTrue(verify_migration_customer_preservation(before,after,contract=self.contract)['full_auth_storage_inventory_verified'])
            self.db.execute("update auth.sessions set marker='synthetic-changed'")
            changed=migration_customer_snapshot(self.contract,runtime,columns=before['columns'])
            with self.assertRaisesRegex(RuntimeError,'existing_customer_values_changed'):
                verify_migration_customer_preservation(before,changed,contract=self.contract)

    def test_exact_executor_completes147_then148_and_records_both_checksums(self):
        result=self.executor().run()
        self.assertEqual(self.schema(),148);self.assertEqual(result['status'],'completed')
        self.assertEqual([(r['number'],r['checksum']) for r in result['migrations']],[(147,release.SQL_SHA256[147]),(148,release.SQL_SHA256[148])])
        self.assertEqual(self.db.execute('select public.notification_delivery_protocol()').fetchone()[0],2)
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.notification_deliveries','UPDATE')").fetchone()[0])
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.builder_reservations','UPDATE')").fetchone()[0])

    def test_live_processing_blocks_before147(self):
        self.add_processing()
        with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor().run()
        self.assertEqual(self.schema(),146)
    def test_expired_uncertain_provider_outcome_also_blocks(self):
        identifier=self.add_processing(True)
        with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor().run()
        self.assertEqual(self.db.execute('select status from public.notification_deliveries where id=%s',(identifier,)).fetchone()[0],'processing')
        self.assertEqual(self.schema(),146)
    def test_running_or_resurrected_old_supervisor_blocks(self):
        self.consumer_state='restarted'
        with self.assertRaisesRegex(RuntimeError,'resurrection'):self.executor().run()
        self.assertEqual(self.schema(),146)
    def test_legacy_transaction_and_queue_lock_block(self):
        with self.connect() as other:
            other.execute('begin');other.execute('lock public.notification_deliveries in access share mode')
            with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor().run()
            other.execute('rollback')
        self.assertEqual(self.schema(),146)
    def test_competing_legacy_claim_cannot_cross_admission(self):
        self.db.execute("insert into public.notification_deliveries(channel,template,deduplication_key) values('internal','synthetic',%s)",(str(uuid4()),))
        with self.connect() as other:
            other.execute('begin');other.execute('select public.claim_notification_deliveries(1,clock_timestamp(),30)')
            with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor().run()
            other.execute('rollback')
        self.assertEqual(self.schema(),146)
    def crash_and_recover(self,point,expected_schema,exit_code):
        process=subprocess.run([sys.executable,'-c',
            'from tests.test_schema148_cutover_database import crash_executor_child; import sys; crash_executor_child(*sys.argv[1:])',
            self.dsn,str(ROOT),str(self.directory/'execution.json'),point],capture_output=True,text=True,timeout=20)
        self.assertEqual(process.returncode,exit_code,process.stderr)
        self.assertEqual(self.schema(),expected_schema)
        journal=json.loads((self.directory/'execution.json').read_text())
        self.assertEqual((journal['status'],journal['phase']),('running','migration_147'))
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):self.executor().run()
        result=self.executor(name='fresh-authorization-after-crash.json').run()
        self.assertEqual((self.schema(),result['status']),(148,'completed'))
    def test_real_executor_crash_before_sql_keeps146_and_requires_new_attempt(self):
        self.crash_and_recover('before_sql',146,80)
    def test_real_executor_crash_after147_commit_recovers_from_database_not_old_journal(self):
        self.crash_and_recover('after_commit',147,81)

    def test_wrong_schema_identity_refuses_without_sql(self):
        self.contract['database']['system_identifier']='different'
        with self.assertRaisesRegex(RuntimeError,'not_quiescent'):self.executor().run()
        self.assertEqual(self.schema(),146)
    def test_checksum_failure_happens_before_backup_or_connection(self):
        from unittest.mock import Mock
        factory=Mock(side_effect=AssertionError('must not connect'))
        bad=replace(self.manifest,migrations=(replace(self.manifest.migrations[0],sha256='0'*64),self.manifest.migrations[1]))
        with self.assertRaisesRegex(RuntimeError,'checksum_mismatch'):self.executor(factory=factory,manifest=bad).run()
        factory.assert_not_called();self.assertEqual(self.schema(),146)

    def file_substitution_attempt(self,stage):
        original=self.manifest.migrations[0]
        captured=self.directory/'captured147.sql'
        approved=original.path.read_text()
        captured.write_text(approved)
        manifest=replace(self.manifest,migrations=(replace(original,path=captured),self.manifest.migrations[1]))
        def substitute():
            captured.write_text(approved.replace('begin;','begin;\nCREATE TABLE public.unreviewed_sql_substitution(id integer);',1))
            self.assertNotEqual(captured.read_text(),approved)
        def backup(_):
            if stage=='backup':substitute()
        def guard(cursor,migration):
            self.guard(cursor,migration)
            if stage=='guard' and migration.number==147:substitute()
        result=LockedMigrationExecutor(connection_factory=self.connect,manifest=manifest,
            state_file=self.directory/'snapshot-execution.json',backup_dir=self.directory,
            backup_verifier=backup,migration_guard=guard).run()
        self.assertEqual((self.schema(),result['status']),(148,'completed'))
        self.assertIsNone(self.db.execute("select to_regclass('public.unreviewed_sql_substitution')").fetchone()[0])
        self.assertEqual(result['migrations'][0]['checksum'],release.SQL_SHA256[147])
        self.assertEqual(self.db.execute('select public.notification_delivery_protocol()').fetchone()[0],2)

    def test_backup_time_sql_substitution_never_reaches_postgresql(self):
        self.file_substitution_attempt('backup')

    def test_guard_time_sql_substitution_never_reaches_postgresql(self):
        self.file_substitution_attempt('guard')
    def test_sql_failure_before147_commit_preserves_schema_and_original_grants(self):
        # Run the exact immutable147 text, but disconnect after its DDL before COMMIT.
        migration=self.manifest.migrations[0]
        connection=self.connect()
        connection.execute(migration.path.read_text().removesuffix('commit;\n'))
        connection.close()
        self.assertEqual(self.schema(),146)
        self.assertTrue(self.db.execute("select has_table_privilege('service_role','public.notification_deliveries','UPDATE')").fetchone()[0])
    def test_failure_after147_commit_keeps_protocol2_and_rejects_same_attempt(self):
        def guard(cursor,migration):
            if migration.number==148:raise RuntimeError('synthetic_candidate_failure_after147')
            self.guard(cursor,migration)
        executor=self.executor(guard=guard)
        with self.assertRaisesRegex(RuntimeError,'after147'):executor.run()
        self.assertEqual(self.schema(),147)
        self.assertEqual(self.db.execute('select public.notification_delivery_protocol()').fetchone()[0],2)
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):executor.run()
        self.assertEqual(self.schema(),147)
    def test_fresh_forward_attempt_retains147_and_applies_only148(self):
        self.apply147()
        result=self.executor(name='fresh-reviewed-forward.json').run()
        self.assertEqual([r['status'] for r in result['migrations']],['already_applied','applied'])
        self.assertEqual(self.schema(),148)
    def test_148_disconnect_keeps_committed147_and_original_reservation_grants(self):
        self.apply147()
        with self.connect() as other:
            other.execute(self.manifest.migrations[1].path.read_text().removesuffix('commit;\n'))
            other.close()
        self.assertEqual(self.schema(),147)
        self.assertTrue(self.db.execute("select has_table_privilege('service_role','public.builder_reservations','UPDATE')").fetchone()[0])
        self.assertFalse(self.db.execute("select has_table_privilege('service_role','public.notification_deliveries','UPDATE')").fetchone()[0])
    def test_lock_race_after_quiescence_times_out_without_committing147(self):
        with self.connect() as other:
            def guard(cursor,migration):
                self.guard(cursor,migration)
                other.execute('begin');other.execute('lock public.notification_deliveries in access share mode')
            with self.assertRaises(psycopg.errors.LockNotAvailable):self.executor(guard=guard).run()
            other.execute('rollback')
        self.assertEqual(self.schema(),146)

    def test148_lock_timeout_preserves_committed147(self):
        self.apply147()
        with self.connect() as other:
            def guard(cursor,migration):
                self.guard(cursor,migration)
                other.execute('begin');other.execute('lock public.builder_reservations in access exclusive mode')
            with self.assertRaises(psycopg.errors.LockNotAvailable):self.executor(guard=guard).run()
            other.execute('rollback')
        self.assertEqual(self.schema(),147)

    def test_missing147_prerequisite_cannot_apply148(self):
        with self.assertRaisesRegex(psycopg.Error,'expected_schema_147'):
            self.db.execute(self.manifest.migrations[1].path.read_text())
        self.db.execute('rollback');self.assertEqual(self.schema(),146)
    def test_supervisor_resurrection_between_commits_blocks148(self):
        def guard(cursor,migration):
            if migration.number==148:self.consumer_state='restarted'
            self.guard(cursor,migration)
        with self.assertRaisesRegex(RuntimeError,'resurrection'):self.executor(guard=guard).run()
        self.assertEqual(self.schema(),147)


if __name__=='__main__':unittest.main(verbosity=2)
