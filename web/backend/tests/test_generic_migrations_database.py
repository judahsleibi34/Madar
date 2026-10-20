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
        self.db.execute('drop table if exists public.future_one,public.future_two')
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
