"""Issuer contract tests; not a claim of privileged preserved-upgrade acceptance."""
import copy,json,tempfile,time,unittest
from contextlib import contextmanager,ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import historical_origin as origin
from deployment.lib import exceptional_release_approval as approval
from deployment.lib.migration_inventory import digest,canonical


class HistoricalOriginTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state_root=self.root/'state';self.state_root.mkdir()
        self.journal=self.root/'historical-origins';self.journal.mkdir()
        self.now=int(time.time());self.key=b'new independent test approval key'*2
        self.known={'sha':'a'*40,'schema':146,'slot':'green'}
        self.observation={'version':1,'known_good':self.known,'protected_completion_claimed':False,'migration_authority_issued':False}
        self.p={'observation_sha256':digest(self.observation),'successor_intent_sha256':digest({'target':160}),
                'expires_at':self.now+3600,'max_request_seconds':300,'source_sha':'a'*40,'controller_sha':'b'*40}
        self.state={'known_good_release':copy.deepcopy(self.known),'active_slot':'green','history':[{'phase':'bootstrap_adopted'}]}
        (self.state_root/'state.json').write_bytes(canonical(self.state))
        self.system=SimpleNamespace(state_root=self.state_root,authenticate_operator=Mock(return_value={'aal':'aal2','operator_auth_id':'separate-operator'}))
        @contextmanager
        def locked(request_id,*,namespace=None):
            self.assertEqual(namespace,'historical-origins');approval.identifier(request_id)
            p=self.journal/request_id;p.mkdir(exist_ok=True);yield p
        stack=ExitStack();self.addCleanup(stack.close)
        for target,value in [
            ('policy',Mock(side_effect=lambda *_:(self.p,self.key,{}))),
            ('observe',Mock(side_effect=lambda *_:copy.deepcopy(self.observation))),
            ('operation_locks',lambda *_:__import__('contextlib').nullcontext(lambda:None)),
            ('journal_lock',locked),('readonly_configuration',lambda p,**k:Path(p))]:
            stack.enter_context(patch.object(origin,target,value))
        stack.enter_context(patch.object(approval,'protected',lambda p,**k:Path(p)))
        from deployment.lib import automatic_release_admission
        stack.enter_context(patch.object(automatic_release_admission,'ROOT',self.root))

    def prepared(self):return origin.prepare(self.system)
    def enrolled(self):
        r=self.prepared();receipt=origin.enroll(self.system,r['request_id'],'secret-token',r['request_sha256'])
        return r,receipt,json.loads((self.state_root/'state.json').read_bytes())

    def test_truthful_enrollment_is_distinct_from_completed_upgrade_and_migration_authority(self):
        r,receipt,state=self.enrolled();binding=origin.attest(self.system,state)
        self.assertEqual(binding['origin_kind'],origin.KIND)
        self.assertNotIn('completed_compatible_upgrade',binding)
        self.assertNotIn('completion_sha256',binding)
        self.assertNotIn('completed_normal_upgrade',state['known_good_release'])
        self.assertFalse(receipt['protected_completion_claimed']);self.assertFalse(receipt['migration_authority_issued'])
        self.assertEqual(self.system.authenticate_operator.call_count,2)
        self.system.authenticate_operator.assert_called_with('secret-token')
        self.assertNotIn('secret-token',json.dumps(receipt))

    def test_prepare_never_enrolls_or_changes_original_state(self):
        self.prepared();self.assertEqual(json.loads((self.state_root/'state.json').read_bytes()),self.state)
        self.system.authenticate_operator.assert_not_called()

    def test_bad_confirmation_does_not_consume(self):
        r=self.prepared()
        with self.assertRaisesRegex(RuntimeError,'expired_changed_or_consumed'):
            origin.enroll(self.system,r['request_id'],'token','c'*64)
        self.assertFalse((self.journal/r['request_id']/'bootstrap-origin-consumed.json').exists())
        self.system.authenticate_operator.assert_not_called()

    def test_missing_fresh_operator_aal2_cannot_consume(self):
        r=self.prepared();self.system.authenticate_operator.side_effect=RuntimeError('operator_mfa_refused')
        with self.assertRaisesRegex(RuntimeError,'operator_mfa_refused'):
            origin.enroll(self.system,r['request_id'],'AAL1',r['request_sha256'])
        self.assertFalse((self.journal/r['request_id']/'bootstrap-origin-consumed.json').exists())

    def test_operator_revoked_during_native_observation_is_rechecked_before_consumption(self):
        r=self.prepared();self.system.authenticate_operator.side_effect=[{'aal':'aal2','operator_auth_id':'separate-operator'},RuntimeError('operator_session_revoked')]
        with self.assertRaisesRegex(RuntimeError,'operator_session_revoked'):
            origin.enroll(self.system,r['request_id'],'token',r['request_sha256'])
        self.assertFalse((self.journal/r['request_id']/'bootstrap-origin-consumed.json').exists())

    def test_independent_observation_pin_is_not_caller_pass(self):
        self.p['observation_sha256']='c'*64
        with self.assertRaisesRegex(RuntimeError,'not_independently_pinned'):self.prepared()

    def test_original_worker_database_or_image_drift_invalidates_request(self):
        for field in ['worker_generation','database','images','source_sha']:
            with self.subTest(field=field):
                r=self.prepared();self.observation[field]='changed'
                with self.assertRaisesRegex(RuntimeError,'changed_before_enrollment'):
                    origin.enroll(self.system,r['request_id'],'token',r['request_sha256'])
                self.observation.pop(field)

    def test_expiry_and_policy_change_refuse_without_consumption(self):
        r=self.prepared()
        with patch.object(origin.time,'time',return_value=self.now+301):
            with self.assertRaisesRegex(RuntimeError,'expired_changed_or_consumed'):
                origin.enroll(self.system,r['request_id'],'token',r['request_sha256'])
        self.p['successor_intent_sha256']='c'*64
        with self.assertRaisesRegex(RuntimeError,'expired_changed_or_consumed'):
            origin.enroll(self.system,r['request_id'],'token',r['request_sha256'])

    def test_enrollment_is_non_replayable_after_new_process_or_reboot(self):
        r,_,_=self.enrolled()
        with self.assertRaisesRegex(RuntimeError,'expired_changed_or_consumed'):
            origin.enroll(self.system,r['request_id'],'token',r['request_sha256'])

    def test_forged_bootstrap_receipt_refuses(self):
        r,_,state=self.enrolled();path=self.journal/r['request_id']/'bootstrap-origin-consumed.json'
        packet=json.loads(path.read_bytes());packet['payload']['protected_completion_claimed']=True;path.write_bytes(canonical(packet))
        with self.assertRaisesRegex(RuntimeError,'signature_invalid'):origin.attest(self.system,state)

    def test_only_one_exact_successor_context_can_use_enrollment(self):
        _,_,state=self.enrolled();first=origin.bind_successor(self.system,state,{'target':160},'c'*64)
        self.assertFalse(first['migration_authority_issued'])
        with self.assertRaisesRegex(RuntimeError,'successor_already_bound'):
            origin.bind_successor(self.system,state,{'target':160},'d'*64)

    def test_changed_successor_intent_never_uses_enrollment(self):
        r,_,state=self.enrolled()
        with self.assertRaisesRegex(RuntimeError,'intent_changed'):
            origin.bind_successor(self.system,state,{'target':164},'c'*64)
        self.assertFalse((self.journal/r['request_id']/'bootstrap-origin-release-use.json').exists())

    def test_state_race_after_consumption_cannot_link_false_origin(self):
        r=self.prepared();changed=copy.deepcopy(self.state);changed['known_good_release']['schema']=160
        (self.state_root/'state.json').write_bytes(canonical(changed))
        with self.assertRaisesRegex(RuntimeError,'state_changed_during_enrollment'):
            origin.enroll(self.system,r['request_id'],'token',r['request_sha256'])
        self.assertTrue((self.journal/r['request_id']/'bootstrap-origin-consumed.json').exists())
        self.assertNotIn('historical_origin',json.loads((self.state_root/'state.json').read_bytes())['known_good_release'])

    def test_journal_namespace_cannot_select_an_arbitrary_root(self):
        with self.assertRaisesRegex(RuntimeError,'namespace_invalid'):
            with approval.journal_lock('00000000-0000-0000-0000-000000000000',namespace='/tmp/foreign'):pass


class PreservationBudgetTests(unittest.TestCase):
    def test_existing_transaction_is_never_committed_or_rolled_back(self):
        db=Mock(autocommit=False)
        with self.assertRaisesRegex(RuntimeError,'readonly_connection_required'):origin.preservation_roots(db)
        db.execute.assert_not_called()

    def test_native_snapshot_error_rolls_back_its_own_readonly_transaction(self):
        db=Mock(autocommit=True);db.execute.return_value.fetchall.return_value=[]
        with self.assertRaisesRegex(RuntimeError,'table_budget'):origin.preservation_roots(db)
        self.assertEqual(db.execute.call_args_list[0].args,('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY',))
        self.assertEqual(db.execute.call_args_list[-1].args,('ROLLBACK',))
        self.assertFalse(any('COMMIT'==c.args[0] for c in db.execute.call_args_list))

    def test_oversize_relation_refuses_before_data_aggregation(self):
        db=Mock(autocommit=True)
        db.execute.return_value.fetchall.return_value=[('public','tenant_data')]
        db.execute.return_value.fetchone.return_value=[100001]
        with self.assertRaisesRegex(RuntimeError,'row_budget'):origin.preservation_roots(db)
        self.assertEqual(db.execute.call_args_list[-1].args,('ROLLBACK',))
        self.assertFalse(any('string_agg' in str(c.args[0]) for c in db.execute.call_args_list))


class HistoricalServingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        from deployment.lib.control_plane_upgrade import SystemOperations
        self.system=SystemOperations.__new__(SystemOperations);self.system.state_root=self.root
        self.state={'known_good_release':{'sha':'a'*40,'historical_origin':{'request_id':'test'}}}
        (self.root/'state.json').write_bytes(canonical(self.state))
        self.system.historical_origin_binding=Mock(return_value={'origin_kind':origin.KIND,'application_sha':'a'*40,'schema':146})
    def test_genuine_enrollment_does_not_claim_a_migration_completion(self):
        self.assertEqual(self.system.migration_terminal('a'*40,146),'not_requested')
        self.system.historical_origin_binding.assert_called_once_with(self.state)
    def test_invalid_enrollment_never_falls_back_to_ordinary_migration_path(self):
        self.system.historical_origin_binding.side_effect=RuntimeError('historical_origin_enrollment_or_runtime_changed')
        with self.assertRaisesRegex(RuntimeError,'runtime_changed'):self.system.migration_terminal('a'*40,146)
    def test_conflicting_historical_migration_state_refuses(self):
        p=self.root/'migrations'/('a'*40);p.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError,'history_conflict'):self.system.migration_terminal('a'*40,146)
    def test_fabricated_completed_marker_never_uses_bootstrap_as_a_fallback(self):
        self.state['known_good_release']['completed_normal_upgrade']={'context_sha256':'fake'}
        (self.root/'state.json').write_bytes(canonical(self.state))
        self.system.completed_compatible_binding=Mock(side_effect=RuntimeError('completed_compatible_marker_invalid'))
        with self.assertRaisesRegex(RuntimeError,'completed_compatible_marker_invalid'):self.system.migration_terminal('a'*40,146)
        self.system.historical_origin_binding.assert_not_called()


class HistoricalPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.key=b'independent approval signature key'*2
        self.policy_file=self.root/'policy.json';self.key_file=self.root/'approval.key';self.auth_file=self.root/'auth.key'
        self.key_file.write_bytes(self.key);self.auth_file.write_bytes(b'a distinct authentication credential')
        self.execution={'environment':'isolated-test','environment_id':'isolated-realm','controller_sha':'c'*40,'denied_database_identifiers':['987654321']}
        self.environment={'realm_id':'realm','version':2,'database_system_identifier':'123456789'}
        self.p={'version':1,'kind':origin.KIND,'environment_id':'isolated-realm','database_system_identifier':'123456789',
            'controller_sha':'c'*40,'source_sha':'a'*40,'source_tree_sha':'b'*40,
            'images':{'backend':'sha256:'+'d'*64,'frontend':'sha256:'+'e'*64},
            'observation_sha256':'f'*64,'approval_key_sha256':__import__('hashlib').sha256(self.key).hexdigest(),
            'successor_intent_sha256':'1'*64,'expires_at':int(time.time())+3600,'max_request_seconds':300}
        stack=ExitStack();self.addCleanup(stack.close)
        for target,value in [('POLICY',self.policy_file),('protected',lambda p,**k:Path(p))]:stack.enter_context(patch.object(origin,target,value))
        from deployment.lib import automatic_release_admission as admission, isolated_release_environment as environment, control_plane_upgrade_authorization as auth
        stack.enter_context(patch.object(admission,'execution_policy_configuration',lambda *_:self.execution))
        stack.enter_context(patch.object(environment,'observe',lambda:self.environment))
        stack.enter_context(patch.object(approval,'KEY',self.key_file))
        stack.enter_context(patch.object(auth,'RELEASE_OPERATOR_KEY',self.auth_file))
        self.system=SimpleNamespace(installed_sha=lambda:'c'*40)
    def read(self):
        self.policy_file.write_bytes(canonical(self.p));return origin.policy(self.system)
    def test_positive_policy_has_separate_root_trust_and_no_authority_effects(self):
        p,key,_=self.read();self.assertEqual(p,self.p);self.assertEqual(key,self.key)
    def test_production_scope_and_known_production_database_are_always_refused(self):
        self.execution['environment']='production'
        with self.assertRaisesRegex(RuntimeError,'independent_policy_invalid'):self.read()
        self.execution['environment']='isolated-test';self.execution['denied_database_identifiers'].append('123456789')
        with self.assertRaisesRegex(RuntimeError,'independent_policy_invalid'):self.read()
    def test_foreign_controller_images_and_expired_policy_refuse(self):
        for key,value in [('controller_sha','d'*40),('images',{'backend':'mutable:latest'}),('expires_at',int(time.time())-1)]:
            saved=copy.deepcopy(self.p);self.p[key]=value
            with self.assertRaisesRegex(RuntimeError,'independent_policy_invalid'):self.read()
            self.p=saved
    def test_business_authentication_key_cannot_sign_enrollment(self):
        self.auth_file.write_bytes(self.key)
        with self.assertRaisesRegex(RuntimeError,'issuer_key_invalid'):self.read()
