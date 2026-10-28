"""Approval cryptography/journal/CLI models; real infrastructure is separate."""
import copy,json,time,uuid,tempfile,unittest,io,os
from pathlib import Path
from unittest.mock import patch,MagicMock
from contextlib import contextmanager
from deployment.lib import exceptional_release_approval as a
from deployment.lib import automatic_release_admission as admission
from deployment.lib.migration_inventory import digest
from deployment.lib.migration_risk import scaffold
from test_automatic_release_admission import sample


class SupportedExceptionalSqlTests(unittest.TestCase):
    def test_drop_is_still_class_d_but_exact_restrict_table_has_contract(self):
        value=a.supported(scaffold(160,161,'DROP TABLE public.retired_items;'),origin=160,target=161)
        self.assertEqual(value,{'contract':'drop-independent-table-v1','schema':'public','table':'retired_items'})

    def test_narrow_private_rls_change_has_class_c_contract(self):
        self.assertEqual(a.supported(scaffold(160,161,'ALTER TABLE public.private_items ENABLE ROW LEVEL SECURITY;'),
            origin=160,target=161)['contract'],'enable-private-table-rls-v1')

    def test_unknown_destructive_procedural_and_scope_expansion_are_never_approved(self):
        for body in ('DROP TABLE public.retired_items CASCADE;','DROP TABLE IF EXISTS public.retired_items;',
                'DROP TABLE public.retired_items,public.other_items;','DROP TABLE auth.users;',
                'DROP TABLE public.users;','TRUNCATE public.retired_items;',
                'ALTER TABLE public.retired_items DROP COLUMN id;',
                'DROP TABLE public.retired_items; SELECT 1;','SELECT unknown_function();',
                'ALTER TABLE public.retired_items DISABLE ROW LEVEL SECURITY;'):
            with self.subTest(body=body),self.assertRaises(RuntimeError):
                a.supported(scaffold(160,161,body),origin=160,target=161)

    def test_candidate_control_plane_or_protocol_change_cannot_approve_itself(self):
        from types import SimpleNamespace
        for mutation in ({'protected_control_plane_changed':True},{'worker_protocol_change':True},{'execution_class':'unsupported'}):
            document={'origin_schema':160,'target_schema':161,'protected_control_plane_changed':False,'worker_protocol_change':False,'execution_class':'transactional','compatibility_covers_path':True}
            document.update(mutation)
            plan=SimpleNamespace(document=lambda:document);inventory=SimpleNamespace(forward=lambda *_:[object()])
            with self.assertRaisesRegex(RuntimeError,'plan_unsupported'):a.inspect_contract(plan,inventory,None,{})

    def test_wrong_schema_envelope_and_transaction_refuse(self):
        sql=scaffold(160,161,'DROP TABLE public.retired_items;')
        for value in (sql.replace(b'BEGIN;',b''),sql.replace(b'COMMIT;',b''),sql):
            with self.assertRaises(RuntimeError):a.supported(value,origin=159,target=160)

    def test_routine_admission_cannot_acquire_class_d_from_aal2_or_pass_fields(self):
        v=sample();v['plan']['risk_class']='D'
        for data in (v,dict(v,aal='aal2'),dict(v,approval='PASS')):
            with self.assertRaises(RuntimeError):admission.validate(data)


class ApprovalJournalTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.path=Path(temp.name)
        self.key=b'approval-signing-only-independent-of-authentication-0123456789'
        self.request_id=str(uuid.uuid4());self.folder=self.path/self.request_id;self.folder.mkdir()
        self.policy={'max_approval_seconds':120}
        self.value=sample();self.value['expires_at']=int(time.time())+120;self.value['plan'].update(risk_class='D',migrations=[{'number':161}])
        self.value['exceptional']={'request_id':self.request_id,'policy_sha256':digest(self.policy),
            'writer_inventory_sha256':'d'*64,'contract':{'contract':'drop-independent-table-v1'}}
        self.operator={'operator_auth_id':str(uuid.uuid4()),'policy_sha256':'a'*64,
            'session_id_sha256':'b'*64,'aal':'aal2'}
        self.system=MagicMock();self.system.authenticate_operator.return_value=self.operator
        self.system.reobserve_automatic_admission.return_value=self.value
        self.enterContext(patch.object(a,'policy',return_value=(self.policy,self.key)))
        self.enterContext(patch.object(a,'root',return_value=self.path))
        self.enterContext(patch.object(a,'protected',side_effect=lambda p,**_:p))
        @contextmanager
        def lock(request_id):
            a.identifier(request_id)
            if request_id!=self.request_id:raise RuntimeError('foreign_model_request')
            yield self.folder
        self.enterContext(patch.object(a,'journal_lock',side_effect=lock))
        self.enterContext(patch('deployment.lib.schema150_provider_adapter.require_owned_lock'))
        self.enterContext(patch('deployment.lib.automatic_release_migration.prepared'))
        self.request={'version':1,'request_id':self.request_id,'admission':self.value,
            'admission_sha256':digest(self.value),'policy_sha256':digest(self.policy),
            'expires_at':int(time.time())+180,'created_at':int(time.time())}
        (self.folder/'request.json').write_text(json.dumps(a.sign(self.request,self.key)))
        for state in ('DISCOVERED','CI_PENDING','CI_ACCEPTED','STAGING_PENDING','STAGING_ACCEPTED',
                'TECHNICAL_REVIEW_REQUIRED','AWAITING_ADMIN_APPROVAL'):
            a.event(self.folder,self.key,state,{'model':True})

    def approve(self):return a.decide(self.system,self.request_id,'approve','secret-not-in-journal',digest(self.request))

    def test_approval_is_deliberate_fresh_identity_plus_exact_confirmation_and_revalidation(self):
        self.assertEqual(a.inspect(self.system,self.request_id)['state'],'AWAITING_ADMIN_APPROVAL')
        self.approve();out=a.inspect(self.system,self.request_id)
        self.assertEqual(out['state'],'APPROVED');self.assertFalse(out['consumed'])
        self.system.authenticate_operator.assert_called_once_with('secret-not-in-journal')
        self.system.reobserve_automatic_admission.assert_called_once_with(self.value)
        self.assertNotIn('secret-not-in-journal',json.dumps(out))

    def test_bad_confirmation_or_foreign_runtime_cannot_silently_replace_scope(self):
        original=(self.folder/'request.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError,'confirmation'):
            a.decide(self.system,self.request_id,'approve','token','wrong')
        self.system.reobserve_automatic_admission.return_value=dict(self.value,source_sha='f'*40)
        with self.assertRaisesRegex(RuntimeError,'observation_changed'):self.approve()
        self.assertEqual((self.folder/'request.json').read_bytes(),original)
        self.assertFalse((self.folder/'approval.json').exists())

    def test_request_expiry_is_durable_and_reauthentication_cannot_extend_it(self):
        self.request['expires_at']=int(time.time())-1
        (self.folder/'request.json').write_text(json.dumps(a.sign(self.request,self.key)))
        with self.assertRaisesRegex(RuntimeError,'expired'):self.approve()
        self.assertEqual(a.history(self.folder,self.key)[-1]['state'],'EXPIRED')

    def test_revocation_and_rejection_preserve_authentic_audit_and_cannot_be_reapproved(self):
        self.approve()
        a.decide(self.system,self.request_id,'revoke','token',digest(self.request))
        self.assertEqual(a.inspect(self.system,self.request_id)['state'],'REVOKED')
        with self.assertRaises(RuntimeError):self.approve()
        with self.assertRaises(RuntimeError):a.verify_execution(self.value,self.system,consume=True,token='token')

    def test_rejected_request_never_gets_approval(self):
        a.decide(self.system,self.request_id,'reject','token',digest(self.request))
        self.assertEqual(a.history(self.folder,self.key)[-1]['state'],'REJECTED')
        self.assertFalse((self.folder/'approval.json').exists())

    def test_single_use_consumption_survives_new_caller_and_process_identity_change(self):
        self.approve();a.verify_execution(self.value,self.system,consume=True,token='token')
        consumed=(self.folder/'approval-consumed.json').read_bytes()
        a.verify_execution(self.value,self.system)
        with self.assertRaisesRegex(RuntimeError,'consumed'):a.verify_execution(self.value,self.system,consume=True,token='token')
        with patch.object(a.os,'getpid',return_value=987654321):
            with self.assertRaisesRegex(RuntimeError,'not_owned'):a.verify_execution(self.value,self.system)
        self.assertEqual((self.folder/'approval-consumed.json').read_bytes(),consumed)
        with self.assertRaisesRegex(RuntimeError,'consumed'):
            a.decide(self.system,self.request_id,'revoke','token',digest(self.request))

    def test_missing_expired_and_forged_approval_refuse(self):
        with self.assertRaises(FileNotFoundError):a.verify_execution(self.value,self.system,consume=True,token='token')
        self.approve();path=self.folder/'approval.json';original=path.read_text()
        value=json.loads(original);value['payload']['expires_at']=0;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'signature'):a.verify_execution(self.value,self.system,consume=True,token='token')
        path.write_text(original)
        with patch.object(a.time,'time',return_value=self.request['expires_at']+1):
            with self.assertRaisesRegex(RuntimeError,'expired'):a.verify_execution(self.value,self.system,consume=True,token='token')

    def test_revoked_or_foreign_operator_session_and_policy_change_refuse(self):
        self.approve();self.system.authenticate_operator.return_value=dict(self.operator,session_id_sha256='c'*64)
        with self.assertRaisesRegex(RuntimeError,'operator_changed'):a.verify_execution(self.value,self.system,consume=True,token='token')
        self.system.authenticate_operator.side_effect=RuntimeError('release_operator_current_identity_unverified')
        with self.assertRaisesRegex(RuntimeError,'identity_unverified'):a.verify_execution(self.value,self.system,consume=True,token='token')
        self.policy['extra']='unauthorized'
        with self.assertRaisesRegex(RuntimeError,'scope_changed'):a.verify_execution(self.value,self.system,consume=True,token='token')
        self.assertFalse((self.folder/'approval-consumed.json').exists())

    def test_all_exact_release_scope_substitutions_refuse(self):
        self.approve()
        for mutate in (lambda v:v.update(source_sha='f'*40),lambda v:v.update(controller_sha='e'*40),
                lambda v:v['database'].update(system_identifier='987654321'),
                lambda v:v['database'].update(target_schema=162),lambda v:v['plan'].update(operation_id='changed'),
                lambda v:v['candidate']['images'].update(backend='substituted'),
                lambda v:v['evidence'].update(staging='f'*64),lambda v:v['evidence'].update(recovery='f'*64)):
            v=copy.deepcopy(self.value);mutate(v)
            with self.subTest(mutate=mutate),self.assertRaises(RuntimeError):a.verify_execution(v,self.system,consume=True,token='token')

    def test_failed_technical_revalidation_precedes_consumption(self):
        self.approve();self.system.reobserve_automatic_admission.side_effect=RuntimeError('backup_corrupt')
        with self.assertRaisesRegex(RuntimeError,'backup_corrupt'):a.verify_execution(self.value,self.system,consume=True,token='token')
        self.assertFalse((self.folder/'approval-consumed.json').exists())

    def test_failed_preflight_without_request_remains_visible_to_operator(self):
        (self.folder/'request.json').unlink()
        a.event(self.folder,self.key,'FAILED',{'error_type':'RuntimeError'})
        value=a.inspect(self.system,self.request_id)
        self.assertEqual(value['state'],'FAILED');self.assertIsNone(value['request'])
        self.assertEqual(len(value['audit']),8)

    def test_audit_removal_modification_and_invalid_transition_refuse(self):
        with self.assertRaisesRegex(RuntimeError,'transition'):a.event(self.folder,self.key,'COMPLETED',{})
        path=sorted(self.folder.glob('event-*.json'))[1];raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(RuntimeError,'sequence'):a.history(self.folder,self.key)
        path.write_bytes(raw);value=json.loads(raw);value['payload']['state']='COMPLETED';path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'signature'):a.history(self.folder,self.key)


class ExceptionalCliTests(unittest.TestCase):
    def test_display_never_reads_operator_secret_or_executes_release(self):
        from deployment.lib import control_plane_upgrade as c
        ops=MagicMock();ops.exceptional_release_action.return_value={'state':'AWAITING_ADMIN_APPROVAL'}
        stream=MagicMock();out=io.StringIO()
        with patch.object(c.os,'geteuid',return_value=0),patch.object(c,'SystemOperations',return_value=ops),patch.object(c.sys,'stdin',stream),patch.object(c.sys,'stdout',out):
            self.assertEqual(c.main(['--exceptional','inspect','--request-id',str(uuid.uuid4())]),0)
        stream.read.assert_not_called();ops.write_authorization.assert_not_called()
        self.assertEqual(ops.exceptional_release_action.call_args.args,('inspect',))

    def test_approval_token_is_stdin_only_and_never_echoed(self):
        from deployment.lib import control_plane_upgrade as c
        ops=MagicMock();ops.exceptional_release_action.return_value={'state':'APPROVED'};out=io.StringIO()
        with patch.object(c.os,'geteuid',return_value=0),patch.object(c,'SystemOperations',return_value=ops),patch.object(c.sys,'stdin',io.StringIO('sensitive-token')),patch.object(c.sys,'stdout',out):
            self.assertEqual(c.main(['--exceptional','approve','--request-id',str(uuid.uuid4()),'--confirm-request-digest','a'*64]),0)
        self.assertNotIn('sensitive',out.getvalue());self.assertEqual(ops.exceptional_release_action.call_args.kwargs['token'],'sensitive-token')


class ExistingDeployerExceptionalLifecycleTests(unittest.TestCase):
    def run_cycle(self,fail=False):
        from test_release_deployer import FakeOperations
        from deployment.lib.release_deployer import ReleaseDeployer,Compatibility
        class Operations(FakeOperations):
            automatic_release_admission={'exceptional':{'request_id':'model-only'}}
            def begin_exceptional_maintenance(self,origin):
                self._call('maintenance_fence');self.deactivate_workers(origin);return True
            def apply_selected_migrations(self,sha):
                self._call('locked_executor');self.schema=83;return {'native':'separate acceptance required'}
            def validate_fenced_rollback_target(self,origin,schema):self._call('frozen_origin_contract',schema)
            def fence_exceptional_failure(self):self._call('maintenance_failure_fence');self.worker_owner='none'
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);path=Path(temp.name)
        seed=FakeOperations(schema=82)
        ReleaseDeployer(state_root=path,compatibility=Compatibility(81,83,82,'none',81,83),operations=seed).deploy('b'*40)
        ops=Operations(fail_at='validate_candidate' if fail else None,schema=82)
        deployer=ReleaseDeployer(state_root=path,compatibility=Compatibility(81,83,83,'expand-only',81,83),operations=ops)
        return ops,deployer,path

    def test_existing_engine_fences_before_sql_then_uses_same_worker_and_traffic_handoff(self):
        ops,deployer,path=self.run_cycle();result=deployer.deploy('a'*40)
        names=[x[0] for x in ops.calls]
        self.assertLess(names.index('maintenance_fence'),names.index('locked_executor'))
        self.assertLess(names.index('locked_executor'),names.index('start_candidate'))
        self.assertLess(names.index('activate_workers'),names.index('switch_traffic'))
        self.assertEqual(result['status'],'known_good');self.assertEqual(result['schema']['observed'],83)

    def test_failed_target_after_exceptional_sql_never_restarts_old_workers(self):
        ops,deployer,path=self.run_cycle(fail=True)
        with self.assertRaises(RuntimeError):deployer.deploy('a'*40)
        names=[x[0] for x in ops.calls]
        self.assertIn('maintenance_failure_fence',names);self.assertNotIn('restore_workers',names)
        self.assertNotIn('switch_traffic',names)
        state=json.loads((path/'state.json').read_text())
        self.assertEqual(state['in_progress_release']['status'],'recovery_required')


@unittest.skipUnless(os.getenv('GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN'),'native disposable PostgreSQL fixture required')
class NativeExceptionalContractTests(unittest.TestCase):
    """Real AST/catalog/ACL/lock observations; not full controller acceptance."""
    def setUp(self):
        import psycopg
        from types import SimpleNamespace
        self.db=psycopg.connect(os.environ['GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN'],autocommit=True)
        marker=self.db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if marker!='madar-generic-migration-synthetic-rehearsal':
            self.db.close();raise RuntimeError('native_exceptional_database_not_disposable')
        self.table='exceptional_'+uuid.uuid4().hex[:12];self.foreign=self.table+'_fk'
        self.db.execute('CREATE TABLE public.'+self.table+'(id bigint PRIMARY KEY,payload text)')
        self.db.execute('INSERT INTO public.'+self.table+" VALUES(1,'retained-in-backup'),(2,'approved-destruction-only')")
        self.sql=scaffold(150,151,'DROP TABLE public.'+self.table+';')
        self.plan=SimpleNamespace(document=lambda:{'origin_schema':150,'target_schema':151,'execution_class':'transactional',
            'protected_control_plane_changed':False,'worker_protocol_change':False,'compatibility_covers_path':True})
        self.inventory=SimpleNamespace(forward=lambda *_:[SimpleNamespace(sql=self.sql,sha256=__import__('hashlib').sha256(self.sql).hexdigest())])
        self.policy={'contracts':['drop-independent-table-v1'],'relation_owner':'postgres','max_table_bytes':1048576,'max_table_rows':10}

    def tearDown(self):
        self.db.rollback()
        self.db.execute('DROP TABLE IF EXISTS public.'+self.foreign)
        self.db.execute('DROP TABLE IF EXISTS public.'+self.table)
        self.db.close()

    def inspect(self,**kw):return a.inspect_contract(self.plan,self.inventory,self.db,self.policy,**kw)

    def test_real_private_leaf_impact_is_stable_under_exclusive_transaction_lock(self):
        observed=self.inspect();self.assertEqual(observed['rows'],2)
        with self.db.transaction():
            self.assertEqual(self.inspect(locked=True),observed)
            locks=self.db.execute("SELECT count(*) FROM pg_locks WHERE pid=pg_backend_pid() AND relation=%s AND mode='AccessExclusiveLock' AND granted",(observed['relation_oid'],)).fetchone()[0]
            self.assertEqual(locks,1)

    def test_real_application_grants_rls_and_foreign_dependencies_refuse(self):
        self.db.execute('GRANT SELECT ON public.'+self.table+' TO PUBLIC')
        with self.assertRaisesRegex(RuntimeError,'application_grants'):self.inspect()
        self.db.execute('REVOKE SELECT ON public.'+self.table+' FROM PUBLIC')
        self.db.execute('ALTER TABLE public.'+self.table+' ENABLE ROW LEVEL SECURITY')
        with self.assertRaisesRegex(RuntimeError,'not_independent'):self.inspect()
        self.db.execute('ALTER TABLE public.'+self.table+' DISABLE ROW LEVEL SECURITY')
        self.db.execute('CREATE TABLE public.'+self.foreign+'(id bigint REFERENCES public.'+self.table+'(id))')
        with self.assertRaisesRegex(RuntimeError,'not_independent'):self.inspect()

    def test_native_inherited_owner_privilege_is_not_mistaken_for_private_acl(self):
        role='exceptional_login_'+uuid.uuid4().hex[:10]
        self.db.execute('CREATE ROLE '+role+' LOGIN')
        try:
            self.db.execute('GRANT postgres TO '+role)
            with self.assertRaisesRegex(RuntimeError,'application_grants'):self.inspect()
        finally:
            self.db.execute('REVOKE postgres FROM '+role)
            self.db.execute('DROP ROLE '+role)

    def test_real_data_drift_and_measurement_limits_cannot_reuse_reviewed_impact(self):
        before=self.inspect();self.db.execute('UPDATE public.'+self.table+" SET payload='changed' WHERE id=1")
        self.assertNotEqual(self.inspect()['data_sha256'],before['data_sha256'])
        self.policy['max_table_rows']=1
        with self.assertRaisesRegex(RuntimeError,'data_budget'):self.inspect()

    def test_later_native_lock_contention_refuses_inside_finite_budget(self):
        import psycopg
        with psycopg.connect(os.environ['GENERIC_MIGRATION_SYNTHETIC_DATABASE_DSN'],autocommit=True) as other:
            other.execute('BEGIN');other.execute('SELECT * FROM public.'+self.table)
            with self.assertRaises(psycopg.errors.LockNotAvailable):
                with self.db.transaction():
                    self.db.execute("SET LOCAL lock_timeout='100ms'")
                    self.inspect(locked=True)
            other.rollback()
