"""Class B AST/policy and native size/lock acceptance, not release authority."""
import copy
import hashlib
import os
from pathlib import Path
import time
import unittest

import test_generic_migration_plan as fixtures
from deployment.lib.migration_inventory import discover,digest
from deployment.lib.migration_plan import generate
from deployment.lib.migration_risk import scaffold,analyze,measured_operations
from deployment.lib.migration_policy import assess,validate_policy,apply_class_b_limits


def class_b_policy(plan):
    now=int(time.time())
    policy={'version':2,'policy_id':'synthetic-model-policy','environment_id':'synthetic-isolated',
        'database_system_identifier':'123456789','controller_sha':'c'*40,
        'repository':'judahsleibi34/Madar','branch':'refs/heads/main','enabled':True,
        'expires_at':now+120,'max_migrations':3,'risk_classes':['A','B'],
        'automation_inputs_sha256':plan.document()['automation_inputs']['sha256'],
        'class_b':{'operations':['create_btree_index','add_nullable_column'],
            'max_table_bytes':1024**2,'max_table_rows':100,'max_lock_wait_ms':100,
            'max_statement_ms':2000,'measurement_max_age_seconds':30}}
    value=plan.document()
    observation={k:policy[k] for k in ('environment_id','database_system_identifier','controller_sha','repository','branch')}
    observation.update({k:value[k] for k in ('source_sha','origin_schema','target_schema','operation_id')})
    observation.update(plan_sha256=plan.sha256,evidence_expires_at=now+120,operation_consumed=False,
        gates={g:True for g in value['required_gates']},structure_sha256='a'*64)
    packet={'version':1,'source_sha':value['source_sha'],'plan_sha256':plan.sha256,
        'system_identifier':policy['database_system_identifier'],'origin_schema':value['origin_schema'],
        'structure_sha256':'a'*64,'observed_at':now,'read_only':True,'operations':[]}
    for row in value['migrations']:
        for op in row['measurable_operations']:
            packet['operations'].append({'migration':row['number'],'operation_sha256':digest(op),
                'table_bytes':8192,'table_rows':20,'conflicting_locks':0})
    observation['class_b_measurements']=packet
    return policy,observation


class MeasuredPolicyTests(unittest.TestCase):
    git=fixtures.PlanTests.git;write=fixtures.PlanTests.write;commit=fixtures.PlanTests.commit
    intent=fixtures.PlanTests.intent

    def setUp(self):fixtures.PlanTests.setUp(self)

    def plan(self,body='CREATE INDEX future_one_idx ON public.future_one(id);'):
        self.write(2,scaffold(1,2,body));head=self.commit()
        inventory=discover(self.root,source_sha=head,history_base_sha=self.base)
        return generate(self.root,inventory,origin=1)

    def test_exact_btree_and_nullable_builtin_are_measurable_without_lowering_risk(self):
        for body,kind in (('CREATE INDEX future_one_idx ON public.future_one(id);','create_btree_index'),
                          ('ALTER TABLE public.future_one ADD COLUMN note pg_catalog.text;','add_nullable_column')):
            sql=scaffold(160,161,body)
            self.assertEqual(analyze(sql,origin=160,target=161).classification,'B')
            self.assertEqual(measured_operations(sql,origin=160,target=161)[0]['kind'],kind)

    def test_expressions_constraints_defaults_critical_or_unknown_operations_are_not_automatic(self):
        for body in ('CREATE UNIQUE INDEX future_one_idx ON public.future_one(id);',
            'CREATE INDEX future_one_idx ON public.future_one((lower(payload)));',
            'CREATE INDEX future_one_idx ON public.future_one(id) WHERE id>0;',
            'CREATE INDEX CONCURRENTLY future_one_idx ON public.future_one(id);',
            'ALTER TABLE public.future_one ADD COLUMN note pg_catalog.int8 DEFAULT 1;',
            'ALTER TABLE public.future_one ADD COLUMN note pg_catalog.int8 NOT NULL;',
            'ALTER TABLE public.users ADD COLUMN note pg_catalog.text;',
            'DROP TABLE public.future_one;','SELECT public.unreviewed();'):
            with self.subTest(body=body):self.assertEqual(measured_operations(scaffold(160,161,body),origin=160,target=161),[])

    def test_matching_measured_policy_is_preparation_only(self):
        plan=self.plan();policy,observation=class_b_policy(plan)
        value=assess(plan,policy,observation)
        self.assertTrue(value['policy_match'],value['reasons'])
        self.assertEqual(value['decision'],'PREPARATION_ELIGIBLE')
        self.assertFalse(value['authority_issued']);self.assertFalse(value['production_execution_allowed'])

    def test_threshold_contention_staleness_and_substitution_refuse(self):
        plan=self.plan();policy,observation=class_b_policy(plan)
        for change in ('bytes','rows','locks','future','expired','source','database','plan','catalog','operation','bool'):
            bad=copy.deepcopy(observation);packet=bad['class_b_measurements'];row=packet['operations'][0]
            if change=='bytes':row['table_bytes']=policy['class_b']['max_table_bytes']+1
            elif change=='rows':row['table_rows']=101
            elif change=='locks':row['conflicting_locks']=1
            elif change=='future':packet['observed_at']+=600
            elif change=='expired':packet['observed_at']-=600
            elif change=='source':packet['source_sha']='f'*40
            elif change=='database':packet['system_identifier']='987654321'
            elif change=='plan':packet['plan_sha256']='f'*64
            elif change=='catalog':packet['structure_sha256']='f'*64
            elif change=='operation':row['operation_sha256']='f'*64
            else:row['table_rows']=True
            with self.subTest(change=change):self.assertFalse(assess(plan,policy,bad)['policy_match'])

    def test_root_policy_cannot_enable_unsupported_classes_or_unbounded_budgets(self):
        plan=self.plan();policy,_=class_b_policy(plan)
        for update in ({'risk_classes':['A','B','C']},{'risk_classes':['D']},{'version':1}):
            with self.assertRaises(RuntimeError):validate_policy(dict(policy,**update))
        for key,value in (('max_lock_wait_ms',True),('max_statement_ms',0),('measurement_max_age_seconds',10000),('operations',['any_ddl'])):
            bad=copy.deepcopy(policy);bad['class_b'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_policy(bad)

    def test_unapproved_b_shape_stays_blocked_even_if_packet_says_pass(self):
        plan=self.plan('ALTER TABLE public.future_one ADD COLUMN note pg_catalog.int8 DEFAULT 1;')
        policy,observation=class_b_policy(plan);observation['class_b_measurements']['PASS']=True
        self.assertIn('class_b_operation_not_supported',assess(plan,policy,observation)['reasons'])


DSN=os.getenv('GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN')
BACKUP=os.getenv('GENERIC_MIGRATION_SYNTHETIC_BACKUP')

@unittest.skipUnless(DSN and BACKUP,'Requires marked disposable PostgreSQL and verified pg_dump')
class NativeMeasuredPolicyTests(unittest.TestCase):
    git=fixtures.PlanTests.git;write=fixtures.PlanTests.write;commit=fixtures.PlanTests.commit
    intent=fixtures.PlanTests.intent

    def setUp(self):
        fixtures.PlanTests.setUp(self)
        from deployment.lib.migration_rehearsal import connect
        self.db=connect(DSN);self.addCleanup(self.db.close)
        self.db.execute('DROP TABLE IF EXISTS public.future_one CASCADE')
        self.db.execute('CREATE TABLE public.future_one(id pg_catalog.int8 PRIMARY KEY)')
        self.db.execute('INSERT INTO public.future_one SELECT generate_series(1,50)')
        self.db.execute("UPDATE public.application_schema_state SET schema_version=150 WHERE contract_key='core'")
        for number in range(2,151):self.write(number,b'-- synthetic historical input\n')
        self.base=self.commit()

    def measured(self,body='CREATE INDEX future_one_idx ON public.future_one(id);'):
        from deployment.lib.migration_drift import measure_class_b,observe
        self.write(151,scaffold(150,151,body));head=self.commit()
        self.inventory=discover(self.root,source_sha=head,history_base_sha=self.base)
        self.plan=generate(self.root,self.inventory,origin=150)
        baseline=observe(self.db,required_protocols={})
        self.policy,self.observation=class_b_policy(self.plan)
        self.policy['database_system_identifier']=baseline.system_identifier
        self.observation.update(database_system_identifier=baseline.system_identifier,structure_sha256=baseline.structure_sha256)
        packet=measure_class_b(self.db,self.plan,expected_system_identifier=baseline.system_identifier,
            expected_structure_sha256=baseline.structure_sha256)
        self.observation['class_b_measurements']=packet
        return packet

    def execute(self):
        from deployment.lib.migration_executor import LockedMigrationExecutor,MigrationManifest,Migration
        from deployment.lib.migration_rehearsal import connect
        source=self.inventory.forward(150,151)[0];path=self.root/'captured.sql';path.write_bytes(source.sql)
        def backup(directory):
            import json
            data=(Path(directory)/'database.dump').read_bytes();meta=json.loads((Path(directory)/'manifest.json').read_bytes())
            if data[:5]!=b'PGDMP' or hashlib.sha256(data).hexdigest()!=meta['sha256']:raise RuntimeError('native_backup_changed')
            if meta['system_identifier']!=self.policy['database_system_identifier']:raise RuntimeError('native_backup_database_changed')
            actual=self.db.execute("SELECT encode(sha256(convert_to(string_agg(id::text,',' ORDER BY id),'UTF8')),'hex') FROM public.future_one").fetchone()[0]
            if actual!=meta['class_b_fixture_sha256']:raise RuntimeError('native_backup_fixture_changed')
        return LockedMigrationExecutor(connection_factory=lambda:connect(DSN),
            manifest=MigrationManifest(self.inventory.source_sha,(Migration(151,path,source.sha256,150,151,'forward-compatible'),),coordinated=True),
            state_file=self.root/'execution.json',backup_dir=Path(BACKUP),backup_verifier=backup,expected_origin=150,
            migration_guard=lambda cursor,migration:apply_class_b_limits(cursor,self.policy,expected_schema=migration.from_schema)).run()

    def test_real_measurement_then_existing_executor_preserves_records(self):
        packet=self.measured();self.assertEqual(packet['operations'][0]['table_rows'],50)
        self.assertTrue(assess(self.plan,self.policy,self.observation)['policy_match'])
        self.assertEqual(self.execute()['observed_schema'],151)
        self.assertEqual(self.db.execute('SELECT count(*) FROM public.future_one').fetchone(),(50,))
        self.assertIsNotNone(self.db.execute("SELECT to_regclass('public.future_one_idx')").fetchone()[0])
        with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):self.execute()

    def test_real_lock_contention_is_measured_and_denies_policy(self):
        from deployment.lib.migration_rehearsal import connect
        with connect(DSN) as holder:
            holder.execute('BEGIN');holder.execute('UPDATE public.future_one SET id=id WHERE id=1')
            packet=self.measured()
            self.assertGreater(packet['operations'][0]['conflicting_locks'],0)
            self.assertIn('class_b_lock_contention',assess(self.plan,self.policy,self.observation)['reasons'])
            holder.rollback()

    def test_contention_appearing_after_measurement_rolls_back_with_bounded_lock_wait(self):
        from deployment.lib.migration_rehearsal import connect
        self.measured('ALTER TABLE public.future_one ADD COLUMN note pg_catalog.text;')
        with connect(DSN) as holder:
            holder.execute('BEGIN');holder.execute('SELECT * FROM public.future_one')
            started=time.monotonic()
            with self.assertRaises(Exception):self.execute()
            self.assertLess(time.monotonic()-started,3)
            holder.rollback()
        self.assertEqual(self.db.execute("SELECT schema_version FROM public.application_schema_state WHERE contract_key='core'").fetchone(),(150,))
        self.assertEqual(self.db.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='future_one' AND column_name='note'").fetchone(),(0,))

    def test_wrong_database_and_catalog_refuse_native_measurements(self):
        from deployment.lib.migration_drift import measure_class_b
        self.measured()
        for identifier,structure in (('123456789',self.observation['structure_sha256']),
                (self.policy['database_system_identifier'],'f'*64)):
            with self.assertRaises(RuntimeError):measure_class_b(self.db,self.plan,
                expected_system_identifier=identifier,expected_structure_sha256=structure)

    def test_unreviewed_ddl_hook_is_refused_without_invoking_it(self):
        self.db.execute("CREATE FUNCTION public.synthetic_ddl_hook() RETURNS event_trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic_hook_must_not_run'; END;$$")
        self.db.execute('CREATE EVENT TRIGGER synthetic_ddl_hook ON ddl_command_start EXECUTE FUNCTION public.synthetic_ddl_hook()')
        try:
            with self.assertRaisesRegex(RuntimeError,'ddl_hooks_unsupported'):self.measured()
        finally:
            self.db.execute('ALTER EVENT TRIGGER synthetic_ddl_hook DISABLE')
            self.db.execute('DROP EVENT TRIGGER synthetic_ddl_hook')
            self.db.execute('DROP FUNCTION public.synthetic_ddl_hook()')
