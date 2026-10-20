"""Actual PostgreSQL future-schema/rollback/lock/replay tests on a marked DB.

Minimal schema-state fixture, not full-provider or protected release acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import migration_rehearsal as rehearsal
from deployment.lib.migration_inventory import canonical, discover
from deployment.lib.migration_plan import generate
from deployment.lib.migration_risk import scaffold
import test_generic_migration_plan as plan_fixture

DSN=os.getenv('GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN')
BACKUP=os.getenv('GENERIC_MIGRATION_SYNTHETIC_BACKUP')


@unittest.skipUnless(DSN and BACKUP,'Requires owned disposable PostgreSQL and actual pg_dump archive')
class FutureSchemaDatabaseTests(unittest.TestCase):
    git=plan_fixture.PlanTests.git
    write=plan_fixture.PlanTests.write
    commit=plan_fixture.PlanTests.commit
    intent=plan_fixture.PlanTests.intent

    def setUp(self):
        plan_fixture.PlanTests.setUp(self)
        self.db=rehearsal.connect(DSN); self.addCleanup(self.db.close)
        self.db.execute('drop table if exists public.future_one,public.future_two,public.future_three')
        self.db.execute("update public.application_schema_state set schema_version=150 where contract_key='core'")
        for number in range(2,151): self.write(number,b'-- synthetic historical SQL\n')
        self.base=self.commit()
        self.state=self.root/'journal/attempt.json'

    def plan(self,first=150,second=False,body=None):
        self.write(151,scaffold(150,151,body or 'CREATE TABLE public.future_one (id pg_catalog.int8 PRIMARY KEY);'))
        if second: self.write(152,scaffold(151,152,'CREATE TABLE public.future_two (id pg_catalog.int8);'))
        head=self.commit(); inventory=discover(self.root,source_sha=head,history_base_sha=self.base)
        return generate(self.root,inventory,origin=first),inventory

    def backup(self,directory):
        path=Path(directory)/'database.dump'; meta=json.loads((Path(directory)/'manifest.json').read_bytes())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),meta['sha256'])
        self.assertEqual(path.read_bytes()[:5],b'PGDMP')
        self.assertEqual(meta['system_identifier'],self.db.execute('select system_identifier::text from pg_control_system()').fetchone()[0])

    def run_plan(self,plan,inventory,verifier=None):
        return rehearsal.run(self.root,inventory,plan,dsn=DSN,state_file=self.state,
            backup_dir=BACKUP,backup_verifier=verifier or self.backup)

    def schema(self):
        return self.db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]

    def test_future_two_migrations_and_preserved_data(self):
        plan,inventory=self.plan(second=True)
        result=self.run_plan(plan,inventory)
        self.assertEqual(result['observed_schema'],152)
        self.assertEqual(self.db.execute('select payload from public.synthetic_preserved').fetchone()[0],'retained')
        self.assertEqual([row['status'] for row in result['migrations']],['applied','applied'])

    def test_three_sequential_future_migrations(self):
        plan,inventory=self.plan(second=True)
        self.write(153,scaffold(152,153,'CREATE TABLE public.future_three (id pg_catalog.int8);'))
        head=self.commit(); inventory=discover(self.root,source_sha=head,history_base_sha=self.base)
        plan=generate(self.root,inventory,origin=150)
        self.run_plan(plan,inventory)
        self.assertEqual(self.schema(),153)
        self.assertEqual([row['number'] for row in plan.document()['migrations']],[151,152,153])

    def test_schema_row_lock_wait_is_bounded_and_rolls_back(self):
        plan,inventory=self.plan()
        with rehearsal.connect(DSN) as holder:
            holder.execute('begin')
            holder.execute("select schema_version from public.application_schema_state where contract_key='core' for update")
            with self.assertRaises(Exception): self.run_plan(plan,inventory)
            holder.execute('rollback')
        self.assertEqual(self.schema(),150)
        self.assertIsNone(self.db.execute("select to_regclass('public.future_one')").fetchone()[0])

    def test_real_child_process_killed_after_commit_keeps_consumed_attempt(self):
        import select,signal
        plan,inventory=self.plan(second=True)
        cluster=self.db.execute('select system_identifier::text from pg_control_system()').fetchone()[0]
        original_connect=rehearsal.connect
        read_fd,write_fd=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(read_fd)
            class Cursor:
                def __init__(self,database): self.real=database.cursor()
                def __enter__(self): self.real.__enter__(); return self
                def __exit__(self,*args): return self.real.__exit__(*args)
                def execute(self,sql,*args):
                    self.real.execute(sql,*args)
                    if isinstance(sql,str) and 'CREATE TABLE public.future_one' in sql:
                        os.write(write_fd,b'committed'); signal.pause()
                def fetchone(self): return self.real.fetchone()
            class Connection:
                def __init__(self): self.real=original_connect(DSN)
                @property
                def autocommit(self): return self.real.autocommit
                @autocommit.setter
                def autocommit(self,value): self.real.autocommit=value
                def cursor(self): return Cursor(self.real)
                def rollback(self): self.real.rollback()
                def close(self): self.real.close()
                def __enter__(self): return self.real.__enter__()
                def __exit__(self,*args): return self.real.__exit__(*args)
            def backup(directory):
                path=Path(directory); meta=json.loads((path/'manifest.json').read_bytes())
                assert hashlib.sha256((path/'database.dump').read_bytes()).hexdigest()==meta['sha256']
                assert meta['system_identifier']==cluster
            try:
                with patch.object(rehearsal,'connect',lambda _:Connection()): self.run_plan(plan,inventory,backup)
            except BaseException:
                os.write(write_fd,b'failed')
            os._exit(1)
        os.close(write_fd)
        try:
            ready=select.select([read_fd],[],[],25)[0]
            self.assertTrue(ready,'owned child did not reach the real commit boundary')
            self.assertEqual(os.read(read_fd,32),b'committed')
        finally:
            os.close(read_fd)
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass
            os.waitpid(pid,0)
        self.assertEqual(self.schema(),151)
        journal=json.loads(self.state.read_bytes())
        self.assertEqual(journal['status'],'running')
        self.assertEqual(journal['migrations'][0]['status'],'applying')
        with self.assertRaises(FileExistsError): self.run_plan(plan,inventory)
        self.assertIsNone(self.db.execute("select to_regclass('public.future_two')").fetchone()[0])

    def test_readonly_catalog_drift_detects_schema_grants_and_never_repairs(self):
        from deployment.lib.migration_drift import observe,compare,history_digest
        _,inventory=self.plan()
        first=observe(self.db,required_protocols={})
        baseline={'version':1,**{k:v for k,v in first.document().items() if k!='read_only'},
                  'history_sha256':history_digest(inventory,150)}
        self.assertEqual(compare(inventory,first,expected=baseline)['status'],'PASS')
        self.db.execute('alter table public.synthetic_preserved add column extra integer')
        try:
            changed=observe(self.db,required_protocols={})
            with self.assertRaisesRegex(RuntimeError,'drift_detected'): compare(inventory,changed,expected=baseline)
        finally: self.db.execute('alter table public.synthetic_preserved drop column extra')
        acl_origin=observe(self.db,required_protocols={})
        acl_baseline={**baseline,**{k:v for k,v in acl_origin.document().items() if k!='read_only'}}
        self.db.execute('grant select on public.synthetic_preserved to public')
        try:
            changed=observe(self.db,required_protocols={})
            with self.assertRaisesRegex(RuntimeError,'drift_detected'): compare(inventory,changed,expected=acl_baseline)
        finally: self.db.execute('revoke select on public.synthetic_preserved from public')
        # Missing hash history is not learned from the current schema number.
        bad=dict(baseline); bad.pop('history_sha256')
        with self.assertRaisesRegex(RuntimeError,'protected_baseline'): compare(inventory,first,expected=bad)
        self.assertEqual(self.schema(),150)

    def test_changed_protocol_function_is_not_executed_before_catalog_check(self):
        from deployment.lib.migration_drift import observe
        first=observe(self.db,required_protocols={})
        with self.assertRaisesRegex(RuntimeError,'catalog_baseline'):
            observe(self.db,required_protocols={'delivery':2})
        self.db.execute("create function public.notification_delivery_protocol() returns integer language plpgsql as $$ begin raise exception 'untrusted_protocol_must_not_run'; end $$")
        try:
            with self.assertRaisesRegex(RuntimeError,'before_protocol_execution'):
                observe(self.db,required_protocols={'delivery':2},expected_structure_sha256=first.structure_sha256)
        finally: self.db.execute('drop function public.notification_delivery_protocol()')
        self.assertEqual(self.schema(),150)

    def test_catalog_observer_refuses_existing_writer_transaction(self):
        from deployment.lib.migration_drift import observe
        self.db.execute('begin')
        try:
            with self.assertRaisesRegex(RuntimeError,'existing_transaction'): observe(self.db,required_protocols={})
            self.assertNotEqual(self.db.info.transaction_status,0)
        finally: self.db.execute('rollback')

    def test_catalog_hash_cannot_be_forged_through_search_path_shadow(self):
        from deployment.lib.migration_drift import observe
        original=observe(self.db,required_protocols={})
        expected=original.structure_sha256
        self.db.execute("create function public.sha256(bytea) returns bytea language sql immutable as $$ select pg_catalog.decode('"+expected+"','hex') $$")
        self.db.execute('set search_path=public,pg_catalog')
        try:
            changed=observe(self.db,required_protocols={})
            self.assertNotEqual(changed.structure_sha256,expected,'Untrusted public.sha256 forged the original catalog digest')
        finally:
            self.db.execute('reset search_path')
            self.db.execute('drop function public.sha256(bytea)')

    def test_historical_digest_and_identity_sql_pin_catalog_namespace(self):
        from deployment.lib.completed_normal_database import STRUCTURE_SQL,IDENTITY_SQL
        def single_result(query):
            with self.db.cursor() as cursor:
                cursor.execute(query); result=None
                while True:
                    if cursor.description is not None: result=cursor.fetchone()[0]
                    if not cursor.nextset(): break
                return result
        expected=single_result(STRUCTURE_SQL)
        identifier=self.db.execute('select system_identifier::text from pg_catalog.pg_control_system()').fetchone()[0]
        self.db.execute("create function public.sha256(bytea) returns bytea language sql immutable as $$ select pg_catalog.decode('"+expected+"','hex') $$")
        self.db.execute("create function public.pg_control_system() returns table(system_identifier bigint) language sql as $$ select 0::bigint $$")
        self.db.execute('set search_path=public,pg_catalog')
        try:
            self.assertNotEqual(single_result(STRUCTURE_SQL),expected)
            identity=json.loads(single_result(IDENTITY_SQL))
            self.assertEqual(identity,{'system_identifier':identifier,'schema':150})
        finally:
            self.db.execute('reset search_path')
            self.db.execute('drop function public.sha256(bytea),public.pg_control_system()')

    def test_database_ownership_marker_cannot_be_redirected_by_search_path(self):
        import disposable_database_support
        self.db.execute("comment on database restored_fixture is '"+rehearsal.MARKER+"'")
        self.db.execute("create function public.current_database() returns name language sql as $$ select 'restored_fixture'::pg_catalog.name $$")
        self.db.execute("comment on database postgres is 'deliberately-unmarked-negative-fixture'")
        self.db.execute('alter role postgres set search_path=public,pg_catalog')
        self.db.execute('set search_path=public,pg_catalog')
        try:
            # Prove the original lookup could read a different DB's marker.
            old=self.db.execute("select pg_catalog.shobj_description(oid,'pg_database') from pg_catalog.pg_database where datname=current_database()").fetchone()
            self.assertEqual(old,(rehearsal.MARKER,))
            with self.assertRaisesRegex(RuntimeError,'not_verified'): rehearsal.connect(DSN)
            with self.assertRaisesRegex(RuntimeError,'ownership'):
                disposable_database_support.connect_disposable_database(DSN,markers={rehearsal.MARKER})
        finally:
            self.db.execute('reset search_path')
            self.db.execute('alter role postgres reset search_path')
            self.db.execute('drop function public.current_database()')
            self.db.execute("comment on database postgres is '"+rehearsal.MARKER+"'")

    def test_completed_operation_replay_rejected(self):
        plan,inventory=self.plan(); self.run_plan(plan,inventory)
        with self.assertRaises(FileExistsError): self.run_plan(plan,inventory)
        self.assertEqual(self.schema(),151)

    def test_wrong_origin_rejected_before_sql(self):
        plan,inventory=self.plan(); self.db.execute("update public.application_schema_state set schema_version=149 where contract_key='core'")
        with self.assertRaisesRegex(RuntimeError,'schema_drift'): self.run_plan(plan,inventory)
        self.assertEqual(self.schema(),149)

    def test_missing_backup_rejected_before_migration(self):
        plan,inventory=self.plan()
        def reject(_): raise RuntimeError('backup_missing')
        with self.assertRaisesRegex(RuntimeError,'backup_missing'): self.run_plan(plan,inventory,reject)
        self.assertEqual(self.schema(),150)
        self.assertIsNone(self.db.execute("select to_regclass('public.future_one')").fetchone()[0])

    def test_sql_failure_rolls_back_entire_transition(self):
        self.db.execute('create table public.future_one(id bigint)')
        plan,inventory=self.plan()
        with self.assertRaises(Exception): self.run_plan(plan,inventory)
        self.assertEqual(self.schema(),150)
        self.assertEqual(json.loads(self.state.read_bytes())['status'],'failed')

    def test_existing_session_lock_blocks_competing_actor(self):
        from deployment.lib.migration_executor import LockedMigrationExecutor
        plan,inventory=self.plan()
        self.db.execute('select pg_advisory_lock(%s)',(LockedMigrationExecutor.LOCK_KEY,))
        try:
            with self.assertRaisesRegex(RuntimeError,'migration_lock_held'): self.run_plan(plan,inventory)
            self.assertEqual(self.schema(),150)
        finally: self.db.execute('select pg_advisory_unlock(%s)',(LockedMigrationExecutor.LOCK_KEY,))

    def test_lost_commit_acknowledgement_requires_observation_and_new_attempt(self):
        import psycopg
        plan,inventory=self.plan(second=True)
        actual=rehearsal.connect
        class Cursor:
            def __init__(self,db): self.real=db.cursor()
            def __enter__(self): self.real.__enter__(); return self
            def __exit__(self,*args): return self.real.__exit__(*args)
            def execute(self,sql,*args):
                self.real.execute(sql,*args)
                if isinstance(sql,str) and 'CREATE TABLE public.future_one' in sql:
                    # Real COMMIT succeeded. Only the caller's acknowledgement
                    # is lost; do not assert that rollback reverses this.
                    raise psycopg.OperationalError('synthetic lost commit acknowledgement')
            def fetchone(self): return self.real.fetchone()
        class Connection:
            def __init__(self): self.real=actual(DSN)
            @property
            def autocommit(self): return self.real.autocommit
            @autocommit.setter
            def autocommit(self,value): self.real.autocommit=value
            def cursor(self): return Cursor(self.real)
            def rollback(self): self.real.rollback()
            def close(self): self.real.close()
            def __enter__(self): return self.real.__enter__()
            def __exit__(self,*args): return self.real.__exit__(*args)
        with patch.object(rehearsal,'connect',lambda _:Connection()):
            with self.assertRaises(psycopg.OperationalError): self.run_plan(plan,inventory)
        self.assertEqual(self.schema(),151)
        self.assertIsNone(self.db.execute("select to_regclass('public.future_two')").fetchone()[0])
        with self.assertRaises(FileExistsError): self.run_plan(plan,inventory)
        # No automatic retry or old-schema rollback. A fresh inspected plan is
        # required for the remainder; production also requires new authority.
        remaining=generate(self.root,inventory,origin=151)
        self.state=self.root/'journal/fresh-attempt.json'
        self.run_plan(remaining,inventory)
        self.assertEqual(self.schema(),152)

    def test_destructive_and_coordinated_not_routine_execution(self):
        for sql in ('DROP TABLE public.synthetic_preserved;',
                    'CREATE FUNCTION public.notification_outbox_protocol() RETURNS int LANGUAGE sql AS $$ SELECT 3 $$;'):
            plan,inventory=self.plan(body=sql)
            with self.assertRaisesRegex(RuntimeError,'routine_plan_required'): self.run_plan(plan,inventory)
            self.assertEqual(self.schema(),150)


if __name__=='__main__': unittest.main()
