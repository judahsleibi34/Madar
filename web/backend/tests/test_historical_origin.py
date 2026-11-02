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

    def test_successor_binding_borrows_real_coordinator_locks_without_reacquiring(self):
        import os
        from deployment.lib import schema150_provider_adapter as provider,control_plane_upgrade
        r,_,state=self.enrolled();self.system.upgrade_root=self.root/'upgrades';self.system.upgrade_root.mkdir()
        self.system.interlock_file=self.root/'interlock'
        paths=(self.system.upgrade_root/'upgrade.lock',self.state_root/'deploy.lock')
        for path in paths:path.touch(mode=0o600)
        fds=[control_plane_upgrade.acquire_lock(p,create=False) for p in paths]
        try:
            with patch.object(provider,'protected',lambda p,**kw:Path(p)),patch.object(control_plane_upgrade,'acquire_lock',side_effect=AssertionError('recursive_lock_acquisition')):
                value=origin.bind_successor_under_locks(self.system,state,{'target':160},'c'*64,upgrade_lock=fds[0],deploy_lock=fds[1])
                self.assertEqual(value['context_sha256'],'c'*64);self.assertFalse(value['migration_authority_issued'])
                for fd,path in zip(fds,paths):provider.require_owned_lock(fd,path)
        finally:
            for fd in fds:os.close(fd)

    def test_unheld_coordinator_lock_cannot_bind_origin(self):
        import os
        from deployment.lib import schema150_provider_adapter as provider
        r,_,state=self.enrolled();self.system.upgrade_root=self.root/'upgrades';self.system.upgrade_root.mkdir()
        self.system.interlock_file=self.root/'interlock'
        paths=(self.system.upgrade_root/'upgrade.lock',self.state_root/'deploy.lock')
        for path in paths:path.touch(mode=0o600)
        fds=[os.open(p,os.O_RDWR) for p in paths]
        try:
            with patch.object(provider,'protected',lambda p,**kw:Path(p)):
                with self.assertRaisesRegex(RuntimeError,'coordinator_lock_not_held'):
                    origin.bind_successor_under_locks(self.system,state,{'target':160},'c'*64,upgrade_lock=fds[0],deploy_lock=fds[1])
            self.assertFalse((self.journal/r['request_id']/'bootstrap-origin-release-use.json').exists())
        finally:
            for fd in fds:os.close(fd)

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
        value['provider_record_sha256']=value['historical_files'][str(path/'bootstrap-origin-consumed.json')]
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

    def test_manual_transaction_on_an_autocommit_connection_is_not_touched(self):
        db=Mock(autocommit=True);db.info.transaction_status=2
        with self.assertRaisesRegex(RuntimeError,'readonly_connection_required'):origin.preservation_roots(db)
        db.execute.assert_not_called()

    def test_native_snapshot_error_rolls_back_its_own_readonly_transaction(self):
        db=Mock(autocommit=True);db.info.transaction_status=0;db.execute.return_value.fetchall.return_value=[]
        with self.assertRaisesRegex(RuntimeError,'table_budget'):origin.preservation_roots(db)
        self.assertEqual(db.execute.call_args_list[0].args,('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY',))
        self.assertEqual(db.execute.call_args_list[-1].args,('ROLLBACK',))
        self.assertFalse(any('COMMIT'==c.args[0] for c in db.execute.call_args_list))

    def test_oversize_relation_refuses_before_data_aggregation(self):
        db=Mock(autocommit=True);db.info.transaction_status=0
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
                'GOTRUE_DB_DATABASE_URL=postgres://supabase_auth_admin:test@operator-db:5432/operators']},
            'HostConfig':{'Privileged':False,'PortBindings':None,'CapAdd':None},
            'NetworkSettings':{'Networks':{'operator':{'NetworkID':'c'*64}}}}
        self.database=copy.deepcopy(self.auth);self.database.update(Id='d'*64,Name='/operator-database');self.database['NetworkSettings']['Networks']['operator']['Aliases']=['operator-db']
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
        self.native=stack.enter_context(patch.object(environment,'run',return_value=canonical(['operators','246813579',True])))
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
            self.native.return_value=canonical(['operators',sid,True])
            with self.assertRaisesRegex(RuntimeError,'database_not_independent'):self.observe()


class HistoricalBootstrapDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'original-bootstrap.json'
        # CI runs without a host madar account or writable installation tree.
        # Model installation ancestors only; exercise actual private-file modes,
        # symlink opens and bounded contents in the writable test workspace.
        operator_patch=patch('pwd.getpwnam',return_value=SimpleNamespace(pw_uid=__import__('os').getuid()))
        operator_patch.start();self.addCleanup(operator_patch.stop)
        ancestors=set(Path(self.tmp.name).parents)
        original=Path.lstat
        def installation_stat(path):
            value=original(path)
            return SimpleNamespace(st_uid=0,st_mode=value.st_mode&~0o022) if path in ancestors else value
        ancestor_patch=patch.object(Path,'lstat',installation_stat);ancestor_patch.start();self.addCleanup(ancestor_patch.stop)
        self.value={'phase':'bootstrap_adopted','status':'known_good','schema':{'observed':146}}
        self.path.write_bytes(canonical(self.value));self.path.chmod(0o600)
    def test_real_operator_owned_record_is_data_without_root_receipt_reclassification(self):
        self.assertEqual(origin.bootstrap_record(self.path),self.value)
    def test_shared_bootstrap_record_refuses(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError,'bootstrap_data_untrusted'):origin.bootstrap_record(self.path)
    def test_symlink_bootstrap_refuses(self):
        link=self.path.with_name('link.json');link.symlink_to(self.path)
        with self.assertRaises(OSError):origin.bootstrap_record(link)
    def test_unbounded_original_record_refuses(self):
        self.path.write_bytes(b' '*65537)
        with self.assertRaisesRegex(RuntimeError,'bootstrap_data_untrusted'):origin.bootstrap_record(self.path)
    def test_untrusted_original_data_parent_refuses(self):
        self.path.parent.chmod(0o777)
        try:
            with self.assertRaisesRegex(RuntimeError,'bootstrap_parent_untrusted'):origin.bootstrap_record(self.path)
        finally:self.path.parent.chmod(0o700)


class NativeOperatorPrivilegeTests(IndependentOperatorScopeTests):
    def test_operator_database_superuser_or_unbounded_connections_refuse(self):
        self.native.return_value=canonical(['operators','246813579',False])
        with self.assertRaisesRegex(RuntimeError,'database_not_independent'):self.observe()
    def test_unbound_dns_alias_refuses(self):
        self.database['NetworkSettings']['Networks']['operator']['Aliases']=[]
        with self.assertRaisesRegex(RuntimeError,'database_transport_changed'):self.observe()
    def test_colliding_private_alias_refuses(self):
        self.auth['NetworkSettings']['Networks']['operator']['Aliases']=['operator-db']
        with self.assertRaisesRegex(RuntimeError,'database_transport_changed'):self.observe()


class HistoricalControllerConsumerTests(unittest.TestCase):
    def setUp(self):
        from test_schema150_actor_inventory import row
        from deployment.lib.completed_normal_resources import measured_spec
        self.contract=HistoricalPreparationBindingTests().contract();self.rows={}
        runtimes={}
        for n,role in enumerate(origin.ROLES,1):
            r=row(f'{n:064x}','madar-'+self.contract['origin']['slot']+'-'+role,running=False,source=self.contract['source_roles']['application_sha'])
            r['HostConfig']['RestartPolicy']['Name']='no';r['Image']=self.contract['origin']['images']['frontend' if role=='frontend' else 'backend']
            self.rows[r['Id']]=r;runtimes['/madar-'+self.contract['origin']['slot']+'-'+role]={'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)}
        self.observed={'database':{'schema':146,'system_identifier':self.contract['database']['system_identifier']},
            'database_networks':{self.contract['database']['network_name']:self.contract['database']['network_id'],
                'historical-control':'7'*64},
            'known_good':{'slot':self.contract['origin']['slot']},'worker_authority':{'generation':self.contract['origin']['worker_generation']},'runtime':runtimes}
        self.enterContext(patch.object(origin,'recorded_observation',return_value=self.observed))
        self.runtime=Mock();self.runtime.inspect.side_effect=lambda ids:{i:self.rows[i] for i in ids if i in self.rows}
    def test_original_actor_projection_is_not_a_previous_completed_runtime(self):
        out=origin.original_runtime(self.contract)
        self.assertEqual(set(out['runtimes']),set(origin.ROLES));self.assertEqual(out['origin_kind'],origin.KIND)
        self.assertNotIn('context_sha256',out);self.assertNotIn('completion_root',out)
        self.assertEqual(origin.validate_history_witness(self.contract,origin.history_witness(self.contract)),out)
    def test_root_projection_cannot_change_source_database_or_actor_identity(self):
        for key in ('source_roles','origin','database','historical_files'):
            value=origin.history_witness(self.contract);value[key]={}
            with self.assertRaisesRegex(RuntimeError,'child_history_changed'):origin.validate_history_witness(self.contract,value)
        value=origin.history_witness(self.contract);roles=value['original_runtime']['runtimes'];roles['frontend']['id']=roles['backend']['id']
        with self.assertRaisesRegex(RuntimeError,'actor_ambiguous'):origin.validate_history_witness(self.contract,value)
    def test_old_writers_must_actually_be_stopped_without_a_synthetic_grant(self):
        out=origin.original_runtime(self.contract);origin.stopped_originals(self.contract,self.runtime,out)
        for role in ('backend','notification-worker','redis'):
            identity=out['runtimes'][role]['id'];self.rows[identity]['State']['Running']=True
            with self.assertRaisesRegex(RuntimeError,'writer_not_fenced'):origin.stopped_originals(self.contract,self.runtime,out)
            self.rows[identity]['State']['Running']=False
        self.rows[out['runtimes']['backend']['id']]['Config']['Env'].append('MADAR_BUSINESS_WRITE_CONTRACT='+'a'*64)
        with self.assertRaisesRegex(RuntimeError,'writer_not_fenced'):origin.stopped_originals(self.contract,self.runtime,out)
    def test_missing_original_is_not_evidence_of_successful_fencing(self):
        out=origin.original_runtime(self.contract);del self.rows[out['runtimes']['backend']['id']]
        with self.assertRaisesRegex(RuntimeError,'fence_actor_missing'):origin.stopped_originals(self.contract,self.runtime,out)
    def test_child_uses_only_current_root_authenticated_projection(self):
        from deployment.lib import completed_normal_admission as admission
        value=origin.history_witness(self.contract)
        with patch.object(admission.os,'geteuid',return_value=1000),patch.object(admission,'require_fresh_authorization') as authority,patch.object(admission,'credential_witness',return_value=value):
            self.assertEqual(admission.origin_runtime(self.contract),value['original_runtime']);admission.verify_history(self.contract)
            self.assertEqual(authority.call_count,2)

    def test_network_topology_is_explicit_signed_data_not_configuration_hash(self):
        expected=self.observed['database_networks']
        self.assertEqual(origin.enrolled_database_networks(self.contract),expected)
        for changed in (None,{},dict(expected,foreign='x'*64),
                {self.contract['database']['network_name']:'0'*64},
                dict(expected,duplicate=self.contract['database']['network_id'])):
            with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,'database_networks_changed'):
                origin.validate_database_networks(self.contract,changed)
        del self.observed['database_networks']
        with self.assertRaisesRegex(RuntimeError,'database_networks_changed'):
            origin.enrolled_database_networks(self.contract)

    def test_child_networks_require_fresh_context_bound_issuer_witness(self):
        from deployment.lib import completed_normal_admission as admission
        value=origin.history_witness(self.contract)
        with patch.object(origin.os,'geteuid',return_value=1000),patch.object(admission,'require_fresh_authorization') as authority,patch.object(admission,'credential_witness',return_value=value) as witness:
            self.assertEqual(origin.database_networks(self.contract),self.observed['database_networks'])
            authority.assert_called_once_with(self.contract)
            witness.assert_called_once_with('historical_origin','historical_origin_sha256')
            value['database']={}
            with self.assertRaisesRegex(RuntimeError,'child_history_changed'):
                origin.database_networks(self.contract)


class HistoricalFenceRecordTests(HistoricalControllerConsumerTests):
    def fence(self,original):
        from deployment.lib.completed_normal_admission import digest as context_digest
        return {'version':1,'kind':'historical-origin-provider-fence','operation':self.contract['operation'],
            'context_sha256':context_digest(self.contract),'enrollment_sha256':self.contract['source_roles']['enrollment_sha256'],
            'original_runtime_sha256':context_digest(original),'original_actor_ids':{k:r['id'] for k,r in original['runtimes'].items()},
            'database_system_identifier':self.contract['database']['system_identifier'],'source_schema':146,
            'provider_journal_count':3,'provider_journal_sha256':'d'*64,'legacy_write_grant_existed':False}
    def test_fence_binds_exact_original_operation_without_a_write_grant(self):
        original=origin.original_runtime(self.contract);value=self.fence(original)
        self.assertEqual(origin.validate_fence(self.contract,original,value),value)
        for key,changed in [('context_sha256','f'*64),('enrollment_sha256','f'*64),('database_system_identifier','999999'),('source_schema',160),('legacy_write_grant_existed',True),('provider_journal_count',0),('original_actor_ids',{})]:
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'fence_record_changed'):origin.validate_fence(self.contract,original,dict(value,**{key:changed}))
    def test_old_grant_is_not_accepted_as_a_historical_fence(self):
        original=origin.original_runtime(self.contract)
        with self.assertRaisesRegex(RuntimeError,'fence_record_changed'):origin.validate_fence(self.contract,original,{'version':2,'mode':'READ_ONLY','schema':146})


class HistoricalInventoryBindingTests(unittest.TestCase):
    def setUp(self):
        from test_schema150_actor_inventory import historical_fixture,row
        from deployment.lib.completed_normal_resources import measured_spec
        from deployment.lib.schema150_provider_lifecycle import digest as inventory_digest
        (self.inventory,_),self.rows=historical_fixture()
        self.contract={'source_roles':self.inventory['historical_origin']}
        self.environment={'version':2,'realm_id':'test-realm','guest_uuid':'guest','machine_id':'machine',
            'root_filesystem_uuid':'filesystem','database_system_identifier':'123456789'}
        operator_rows=[row(f'{n:064x}','operator-'+str(n)) for n in (80,81)]
        self.scope={'actor_ids':[r['Id'] for r in operator_rows],'network_id':'7'*64,'database_system_identifier':'987654321'}
        self.rows+=operator_rows
        for r in operator_rows:self.inventory['exclusions'][r['Id']]={'image':r['Image'],
            'spec_sha256':measured_spec(r),'proof_sha256':inventory_digest(self.scope)}
        unit=self.inventory['supervisors']['madar-release-proxy.service']
        dropins={'/etc/systemd/system/madar-release-proxy.service.d/original.conf':'6'*64}
        unit['dropins_sha256']=inventory_digest(dropins)
        controls={'units':{'madar-release-proxy.service':{'fragment':'/etc/systemd/system/madar-release-proxy.service',
            'dropins':list(dropins),'state':{'enabled':'enabled'}}},'files':{k:{'sha256':v} for k,v in dropins.items()}}
        controls['files']['/etc/systemd/system/madar-release-proxy.service']={'sha256':unit['fragment_sha256']}
        self.observed={'runtime':{r['Name']:{'id':r['Id'],'image':r['Image'],'spec_sha256':measured_spec(r)} for r in self.rows},
            'independent_operator_scope':self.scope,'boot_controls':controls,'environment_id':'isolated-test-realm',
            'host':{k:self.environment[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id')},
            'database':{'system_identifier':'123456789'}}
        self.enterContext(patch.object(origin,'recorded_observation',return_value=self.observed))
        self.enterContext(patch.object(origin,'original_runtime',return_value={'runtimes':{
            k.split(':',1)[1]:{n:v[n] for n in ('id','image','spec_sha256')} for k,v in self.inventory['containers'].items() if k.startswith('origin:')}}))
        self.enterContext(patch.object(origin,'independent_operator_scope',return_value=self.scope))
        self.enterContext(patch('deployment.lib.isolated_release_environment.observe_host',return_value=self.environment))
        self.enterContext(patch('deployment.lib.isolated_release_environment.observe_effect_fence'))
    def verify(self):return origin.verify_actor_inventory(self.contract,self.inventory,self.rows)
    def test_enrolled_alert_template_bytes_remain_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'madar-ops-alert@.service';path.write_bytes(b'exact alert template')
            metadata=path.stat();controls=self.observed['boot_controls']
            controls['templates']={'madar-ops-alert@.service':{'fragment':str(path),'dropins':[],
                'state':{'enabled':'static','active':None},'instances':[]}}
            controls['files'][str(path)]={'sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest(),
                'uid':metadata.st_uid,'mode':metadata.st_mode&0o7777}
            with patch.object(origin,'protected',lambda p,**kw:Path(p)),patch.object(origin,'alert_template_control',return_value=controls['templates']['madar-ops-alert@.service']),patch('deployment.lib.control_plane_upgrade.SystemOperations'):
                self.verify()
                path.write_bytes(b'substituted template')
                with self.assertRaisesRegex(RuntimeError,'alert_template_changed'):self.verify()
    def test_root_projection_matches_entire_original_universe_and_separate_operator_scope(self):
        self.assertEqual(self.verify(),self.scope)
    def test_operator_exclusion_is_not_arbitrary_exclusion_authority(self):
        self.inventory['exclusions'][self.scope['actor_ids'][0]]['proof_sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'exclusion_changed'):self.verify()
    def test_missing_original_and_changed_supervisor_refuse(self):
        actor=self.inventory['containers'].pop('native:storage')
        with self.assertRaisesRegex(RuntimeError,'actor_universe_changed'):self.verify()
        self.inventory['containers']['native:storage']=actor
        self.inventory['supervisors']['madar-release-proxy.service']['fragment_sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'supervisor_preimage_changed'):self.verify()
    def test_changed_physical_environment_and_origin_image_refuse(self):
        self.environment['guest_uuid']='wrong-guest'
        with self.assertRaisesRegex(RuntimeError,'inventory_host_changed'):self.verify()
        self.environment['guest_uuid']='guest'
        self.inventory['containers']['native:db']['image']='sha256:'+'0'*64
        with self.assertRaisesRegex(RuntimeError,'inventory_actor_changed'):self.verify()
    def test_changed_inventory_reference_cannot_substitute_enrollment(self):
        self.inventory['historical_origin']=dict(self.contract['source_roles'],enrollment_sha256='0'*64)
        with self.assertRaisesRegex(RuntimeError,'enrollment_changed'):self.verify()


class HistoricalSupervisorProjectionTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        from deployment.lib.completed_normal_admission import digest as context_digest
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.units=self.root/'units';self.units.mkdir()
        self.name='madar-release-proxy.service';self.directory=self.units/(self.name+'.d');self.directory.mkdir()
        self.original=self.directory/'original.conf';self.original.write_bytes(b'original exact control')
        self.gate=self.directory/'successor.conf';self.gate.write_bytes(b'exact successor gate')
        self.checksum=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.contract={'operation':'completed-normal-schema146-160-coordinated-release','source_roles':{}}
        self.controls={'files':{str(self.original):{'sha256':self.checksum(self.original)}},'units':{
            self.name:{'dropins':[str(self.original)],'state':{'enabled':'enabled'}}}}
        self.record={'operation':self.contract['operation'],'context_sha256':context_digest(self.contract),
            'historical_units_deleted':False,'superseded_units':[],'superseded_proxy_dropins':{},
            'resources':{str(self.gate):self.checksum(self.gate)}}
        self.path=self.root/'boot-installation.json';self.save()
        self.enterContext(patch.object(origin,'recorded_observation',return_value=self.controls))
        # recorded_observation normally returns the entire signed observation.
        origin.recorded_observation.return_value={'boot_controls':self.controls}
        self.enterContext(patch.object(origin,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch('deployment.lib.completed_normal_boot_installation.UNITS',self.units))
    def save(self):self.path.write_bytes(canonical(self.record))
    def observe(self):return origin.supervisor_controls(self.contract,self.name,self.root)
    def test_only_original_and_exact_installer_addition_are_projected(self):
        result,enabled=self.observe();self.assertEqual(set(result),{str(self.original),str(self.gate)});self.assertEqual(enabled,'enabled')
    def test_tampered_installed_bytes_or_context_refuse(self):
        self.gate.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'supervisor_controls_changed'):self.observe()
        self.record['context_sha256']='0'*64;self.save()
        with self.assertRaisesRegex(RuntimeError,'boot_installation_changed'):self.observe()
    def test_replacement_requires_enrolled_original_and_real_preimage_bytes(self):
        old=self.root/'proxy-originals';old.mkdir();(old/self.original.name).write_bytes(self.original.read_bytes())
        self.original.write_bytes(b'exact replacement');self.record['superseded_proxy_dropins']={str(self.original):self.checksum(self.original)};self.save()
        self.assertEqual(self.observe()[0][str(self.original)],self.checksum(self.original))
        (old/self.original.name).write_bytes(b'not the enrolled preimage')
        with self.assertRaisesRegex(RuntimeError,'replacement_preimage_changed'):self.observe()
    def test_addition_cannot_overwrite_an_original(self):
        self.record['resources'][str(self.original)]=self.checksum(self.original);self.save()
        with self.assertRaisesRegex(RuntimeError,'addition_overwrites_original'):self.observe()


class HistoricalDatabaseEndpointTests(unittest.TestCase):
    def setUp(self):
        from test_schema150_actor_inventory import historical_fixture,repin
        from deployment.lib.completed_normal_resources import measured_spec
        from deployment.lib.completed_normal_admission import digest as context_digest,encoded
        (data,scope),rows=historical_fixture();self.row=next(r for r in rows if r['Name']=='/supabase-db')
        self.row['HostConfig']['PortBindings']={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'25432'}]}
        self.row['NetworkSettings']['Networks']['historical-control']={'NetworkID':'7'*64,'IPAddress':'10.7.0.2'}
        native=self.row['NetworkSettings']['Networks']['madar-local-supabase_default'];native['IPAddress']='10.1.0.2'
        data['target_networks']['historical-control']='7'*64
        db=data['containers']['native:db'];db['networks']['historical-control']='7'*64
        db['spec_sha256']=measured_spec(self.row);data,scope=repin(data,scope)
        self.contract={'operation':scope['operation'],'version':8,'source_roles':data['historical_origin'],
            'candidate':{'source_sha':scope['source_sha'],'controller_sha':scope['controller_sha']},
            'writer_inventory_sha256':scope['inventory_sha256'],'database':{'container_id':db['id'],
                'image':db['image'],'system_identifier':scope['system_identifier']}}
        self.environment={'version':2,'guest_uuid':'guest','machine_id':'machine','root_filesystem_uuid':'filesystem',
            'realm_id':'realm','database_container_id':db['id'],'database_system_identifier':scope['system_identifier'],
            'runtime_scope':{db['id']:{'spec_sha256':db['spec_sha256']}}}
        observed={'runtime':{'/supabase-db':{k:db[k] for k in ('id','image','spec_sha256')}},
            'host':{k:self.environment[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','realm_id')},
            'database':{'system_identifier':scope['system_identifier']}}
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name)
        destination=root/context_digest(self.contract);destination.mkdir();(destination/'provider-inventory.json').write_bytes(encoded(data))
        self.enterContext(patch('deployment.lib.completed_normal_admission.ADMISSIONS',root))
        self.enterContext(patch.object(origin,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(origin,'recorded_observation',return_value=observed))
        self.enterContext(patch('deployment.lib.isolated_release_environment.observe_host',return_value=self.environment))
        self.enterContext(patch('deployment.lib.isolated_release_environment.observe_effect_fence'))
    def observe(self):return origin.native_database_endpoint(self.contract,self.row)
    def test_parent_lease_uses_enrolled_native_endpoint_not_loopback_control_bridge(self):
        self.assertEqual(self.observe()['IPAddress'],'10.1.0.2')
    def test_changed_network_id_without_spec_change_refuses(self):
        self.row['NetworkSettings']['Networks']['madar-local-supabase_default']['NetworkID']='0'*64
        with self.assertRaisesRegex(RuntimeError,'database_transport_changed'):self.observe()
    def test_changed_database_identity_or_public_port_refuses(self):
        old=self.row['Id'];self.row['Id']='0'*64
        with self.assertRaisesRegex(RuntimeError,'database_transport_changed'):self.observe()
        self.row['Id']=old;self.row['HostConfig']['PortBindings']['5432/tcp'][0]['HostIp']='0.0.0.0'
        with self.assertRaisesRegex(RuntimeError,'database_transport_changed'):self.observe()


class HistoricalBootControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.names=['madar-release-proxy.service','madar-ops-alert@.service']
        self.active='inactive';self.template_state='static';self.instances=''
        for name in self.names:(self.root/name).write_text('authenticated '+name)
        def command(label,args):
            if label=='historical_boot_units':
                return SimpleNamespace(stdout='\n'.join(n+' '+self.template_state+' -' for n in self.names))
            if label=='historical_alert_instances':return SimpleNamespace(stdout=self.instances)
            name=args[2]
            return SimpleNamespace(stdout='\n'.join([
                'FragmentPath='+str(self.root/name),'DropInPaths=',
                'LoadState=loaded','ActiveState='+self.active,'UnitFileState=static']))
        self.system=SimpleNamespace(command=Mock(side_effect=command))
        self.enterContext(patch.object(origin,'BOOT_UNIT_ROOT',self.root))
        self.enterContext(patch.object(origin,'protected',lambda p,**kw:self.root/Path(p).name))

    def test_static_alert_template_is_measured_but_is_not_a_stoppable_actor(self):
        value=origin.boot_controls(self.system)
        self.assertEqual(set(value['units']),{'madar-release-proxy.service'})
        self.assertEqual(set(value['templates']),{'madar-ops-alert@.service'})
        self.assertIn(str(self.root/'madar-ops-alert@.service'),value['files'])
        self.assertIsNone(value['templates']['madar-ops-alert@.service']['state']['active'])

    def test_unknown_template_is_not_silently_ignored_or_admitted(self):
        self.names.append('madar-unknown@.service')
        with self.assertRaisesRegex(RuntimeError,'boot_unit_inventory_invalid'):origin.boot_controls(self.system)
        self.assertEqual(self.system.command.call_count,1)

    def test_nonstatic_template_cannot_claim_inert_configuration(self):
        self.template_state='enabled'
        with self.assertRaisesRegex(RuntimeError,'alert_template_state_invalid'):origin.boot_controls(self.system)

    def test_actual_alert_instance_cannot_be_hidden_as_a_template(self):
        self.instances='madar-ops-alert@failed.service loaded active running diagnostic alert'
        with self.assertRaisesRegex(RuntimeError,'alert_instances_require_review'):origin.boot_controls(self.system)


class HistoricalServingReadinessTests(unittest.TestCase):
    def setUp(self):
        self.version={'release_sha':'a'*40,'release_slot':'green','schema_compatible_min':144,'schema_compatible_max':146}
        self.ready={'ready':True,'components':{k:'ok' for k in ('environment','database','redis','auth','storage','schema','admin_mfa_policy','parser_isolation','notification_worker','data_deletion_worker')}}
        self.ready['components']['calendar_sync_worker']='disabled'
        self.system=SimpleNamespace(http_json=Mock(side_effect=lambda url:copy.deepcopy(self.version if url.endswith('/version') else self.ready)),http_ok=Mock())
    def test_real_route_and_active_slot_are_read_without_modern_completion(self):
        observed=origin.serving_observation(self.system,'a'*40,'green')
        self.assertEqual(set(observed),{'stable','active'})
        self.assertEqual([v.args[0] for v in self.system.http_json.call_args_list], [
            'http://127.0.0.1:8001/health/version','http://127.0.0.1:8001/health/ready',
            'http://127.0.0.1:8201/health/version','http://127.0.0.1:8201/health/ready'])
        self.assertEqual([v.args[0] for v in self.system.http_ok.call_args_list], [
            'http://127.0.0.1:3000/','http://127.0.0.1:3200/'])
    def test_live_but_backlogged_or_unready_origin_cannot_be_enrolled(self):
        self.ready['ready']=False;self.ready['components']['notification_queue']='backlogged'
        with self.assertRaisesRegex(RuntimeError,'serving_unready'):
            origin.serving_observation(self.system,'a'*40,'green')
    def test_wrong_source_or_schema_and_missing_core_provider_refuse(self):
        for key,value in [('release_sha','b'*40),('schema_compatible_max',160),('release_slot','blue')]:
            with self.subTest(key=key),patch.dict(self.version,{key:value}),self.assertRaisesRegex(RuntimeError,'serving_identity_changed'):
                origin.serving_observation(self.system,'a'*40,'green')
        self.ready['components'].pop('auth')
        with self.assertRaisesRegex(RuntimeError,'serving_unready'):
            origin.serving_observation(self.system,'a'*40,'green')
