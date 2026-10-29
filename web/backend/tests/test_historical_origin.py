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
        self.observation={'version':1,'kind':origin.KIND,'source_sha':'a'*40,'controller_sha':'b'*40,
            'known_good':self.known,'protected_completion_claimed':False,'migration_authority_issued':False}
        self.p={'observation_sha256':digest(self.observation),'successor_intent_sha256':digest({'target':160}),
                'expires_at':self.now+3600,'max_request_seconds':300,'source_sha':'a'*40,'controller_sha':'b'*40,
                'kind':origin.KIND,'approval_key_sha256':__import__('hashlib').sha256(self.key).hexdigest()}
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
            ('journal_lock',locked),('readonly_configuration',lambda p,**k:Path(p)),('protected',lambda p,**k:Path(p))]:
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

    def test_recorded_origin_is_authentic_data_after_live_runtime_changes_not_authority(self):
        r,_,state=self.enrolled();binding=origin.attest(self.system,state)
        policy_file=self.root/'origin-policy.json';policy_file.write_bytes(canonical(self.p))
        key_file=self.root/'approval.key';key_file.write_bytes(self.key)
        with patch.object(origin,'POLICY',policy_file),patch.object(approval,'KEY',key_file):
            self.assertEqual(origin.recorded_observation(binding),self.observation)
            changed=copy.deepcopy(binding);changed['application_sha']='c'*40
            with self.assertRaisesRegex(RuntimeError,'recorded_evidence_changed'):origin.recorded_observation(changed)
        self.assertNotIn('completion_sha256',binding)


class HistoricalPreparationBindingTests(unittest.TestCase):
    def contract(self):
        from test_schema160_release import reconciled_contract
        from deployment.lib.automatic_release_admission import ROOT
        value=reconciled_contract();old=value['source_roles']
        path=ROOT/'historical-origins'/'00000000-0000-0000-0000-000000000001'
        value['source_roles']={'origin_kind':origin.KIND,'enrollment_root':str(path),'enrollment_sha256':'c'*64,
            'application_sha':old['application_sha'],'controller_sha':old['controller_sha'],'schema':146,'successor_intent_sha256':'0'*64}
        value['source_roles']['successor_intent_sha256']=digest(origin.successor_intent(value))
        value['origin']['write_contract_digest']=value['source_roles']['enrollment_sha256']
        value['historical_files']={str(path/name):'d'*64 for name in ('bootstrap-origin-request.json','bootstrap-origin-consumed.json')}
        return value
    def test_truthful_source_is_accepted_for_preparation_but_never_registers_execution(self):
        from deployment.lib.completed_normal_admission import validate_provider_preparation,validate_contract
        from deployment.lib.completed_normal_profile import RECONCILED,profile
        value=self.contract();self.assertEqual(validate_provider_preparation(value),RECONCILED)
        for function in (profile,validate_contract):
            with self.assertRaisesRegex(RuntimeError,'operation_profile_invalid'):function(value)
    def test_candidate_database_manifest_or_images_cannot_reuse_original_intent(self):
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        for section,key,changed in [('candidate','source_sha','e'*40),('database','system_identifier','123456789'),
                ('candidate','images',{'backend':'sha256:'+'e'*64,'frontend':'sha256:'+'f'*64})]:
            value=self.contract();value[section][key]=changed
            with self.assertRaisesRegex(RuntimeError,'successor_scope_changed'):validate_provider_preparation(value)
    def test_completed_history_alias_and_foreign_namespace_refuse(self):
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        value=self.contract();value['historical_files']={str(Path(value['source_roles']['enrollment_root'])/'normal-completion.json'):'d'*64}
        with self.assertRaisesRegex(RuntimeError,'history_invalid'):validate_provider_preparation(value)
        value=self.contract();value['source_roles']['enrollment_root']='/tmp/foreign'
        with self.assertRaisesRegex(RuntimeError,'evidence_path_invalid'):validate_provider_preparation(value)


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


class IndependentOperatorScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.key=b'independent operator identity key'*2
        self.key_file=self.root/'operator.key';self.key_file.write_bytes(self.key)
        self.auth={'Id':'a'*64,'Name':'/operator-auth','Image':'sha256:'+'b'*64,
            'Config':{'Labels':{'com.madar.operator-fixture':'realm'},'Env':['GOTRUE_JWT_SECRET='+self.key.decode(),
                'GOTRUE_DB_DATABASE_URL=postgres://postgres:test@operator-database:5432/operators']},
            'HostConfig':{'Privileged':False,'PortBindings':None,'CapAdd':None},
            'NetworkSettings':{'Networks':{'operator':{'NetworkID':'c'*64}}}}
        self.database=copy.deepcopy(self.auth);self.database.update(Id='d'*64,Name='/operator-database')
        self.service={'id':self.auth['Id'],'image':self.auth['Image'],'spec_sha256':'e'*64}
        self.facts={'created_container_ids':[self.auth['Id'],self.database['Id']],'realm_id':'realm','auth_service':self.service,'network_id':'c'*64}
        self.environment={'realm_id':'realm','database_system_identifier':'123456789','denied_database_identifiers':['987654321']}
        self.operator={'environment_id':'isolated-realm','database_system_identifier':'123456789','auth_service':self.service}
        self.policy_file=self.root/'operator-policy.json';self.policy_file.write_bytes(canonical(self.operator))
        self.facts_file=self.root/'facts.json';self.facts_file.write_bytes(canonical(self.facts))
        def protected(path,**_):return self.facts_file if str(path).endswith('/facts.json') else Path(path)
        stack=ExitStack();self.addCleanup(stack.close)
        from deployment.lib import control_plane_upgrade_authorization as auth,completed_normal_resources as resources,isolated_release_environment as environment
        stack.enter_context(patch.object(origin,'protected',protected))
        stack.enter_context(patch.object(auth,'RELEASE_OPERATOR_POLICY',self.policy_file))
        stack.enter_context(patch.object(auth,'RELEASE_OPERATOR_KEY',self.key_file))
        stack.enter_context(patch.object(resources,'measured_spec',lambda *_:'e'*64))
        self.native=stack.enter_context(patch.object(environment,'run',return_value=canonical(['operators','246813579'])))
    def observe(self):return origin.independent_operator_scope([self.auth,self.database],self.environment)
    def test_enrolled_operator_database_is_native_observed_and_separate(self):
        out=self.observe();self.assertEqual(out['database_system_identifier'],'246813579');self.assertEqual(len(out['actor_ids']),2)
    def test_operator_network_cannot_join_business_database_network(self):
        self.auth['NetworkSettings']['Networks']['business']={'NetworkID':'f'*64}
        with self.assertRaisesRegex(RuntimeError,'network_or_privilege_invalid'):self.observe()
        self.native.assert_not_called()
    def test_operator_authenticator_cannot_point_at_business_database(self):
        self.auth['Config']['Env'][1]='GOTRUE_DB_DATABASE_URL=postgres://postgres:test@supabase-db:5432/postgres'
        with self.assertRaisesRegex(RuntimeError,'database_transport_changed'):self.observe()
        self.native.assert_not_called()
    def test_source_or_production_database_identity_cannot_be_operator_database(self):
        for sid in ['123456789','987654321']:
            self.native.return_value=canonical(['operators',sid])
            with self.assertRaisesRegex(RuntimeError,'database_not_independent'):self.observe()
