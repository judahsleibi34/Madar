"""Exact canonical review through the existing signed journal; no SQL acceptance."""
import copy,json,hashlib,os,tempfile,time,unittest,uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from deployment.lib import exceptional_release_approval as approval
from deployment.lib import automatic_release_admission as admission
from deployment.lib import historical_origin as origin
from deployment.lib import schema160_release as release
from deployment.lib.completed_normal_execution import CompletedNormalUpgrade,SOURCE_PACKAGES
from deployment.lib.completed_normal_profile import RECONCILED
from deployment.lib.completed_normal_admission import digest as context_digest
from deployment.lib.migration_inventory import digest,canonical
from deployment.lib.migration_risk import Risk
import test_historical_origin as origin_fixtures


class CanonicalExceptionalReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.contract=origin_fixtures.HistoricalPreparationBindingTests().contract()
        self.document={'admission_contract':{k:v for k,v in self.contract.items() if k!='plan_sha256'},
            'source_bundle_sha256':'a'*64,'operation_id':str(uuid.uuid4()),'attempt_id':str(uuid.uuid4()),
            'fixture_only':True,'production_authorization':False,'independent_recovery':{'receipt_sha256':'b'*64}}
        self.contract['plan_sha256']=context_digest(self.document)
        self.system=SimpleNamespace(deploy_lock_descriptor=None,installed_sha=Mock(return_value=self.contract['candidate']['controller_sha']))
        self.system.upgrade_root=self.root/'upgrades';self.system.upgrade_root.mkdir()
        self.system.state_root=self.root/'state';self.system.state_root.mkdir()
        (self.system.state_root/'state.json').write_bytes(canonical({'model':'original historical state'}))
        (self.system.state_root/'state.json').chmod(0o600)
        for path in (self.system.upgrade_root/'upgrade.lock',self.system.state_root/'deploy.lock'):path.touch(mode=0o600)
        self.driver=CompletedNormalUpgrade.__new__(CompletedNormalUpgrade)
        self.driver.contract=self.contract;self.driver.document=self.document;self.driver.profile=RECONCILED
        self.driver.controller=self.contract['candidate']['controller_sha'];self.driver.ops=self.system
        self.driver.package=SOURCE_PACKAGES/('normal-source-'+self.document['source_bundle_sha256'])
        repository=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[3])
        self.driver.actor=SimpleNamespace(measure=Mock(return_value=(self.document,repository)))
        self.driver.preflight=Mock(return_value={'authorization_consumed':False})
        self.system.canonical_exceptional_driver=self.driver
        self.operator={'operator_auth_id':str(uuid.uuid4()),'policy_sha256':'d'*64,'session_id_sha256':'e'*64,'aal':'aal2'}
        self.system.authenticate_operator=Mock(return_value=self.operator)
        self.key=b'independent-approval-only-key-0123456789'
        self.p={'version':2,'policy_id':'canonical-test','environment_id':'isolated-test',
            'database_system_identifier':self.contract['database']['system_identifier'],'controller_sha':self.driver.controller,
            'enabled':True,'contracts':[approval.CANONICAL],'approval_key_sha256':hashlib.sha256(self.key).hexdigest(),
            'max_approval_seconds':120,'max_request_seconds':300,'execution_max_seconds':3600,
            'require_physical_restore':True,'physical_recovery_receipt_sha256':'b'*64,
            'canonical_scope':approval.canonical_scope(self.driver)}
        self.until=int(time.time())+3600
        (self.root/('b'*64+'.json')).write_bytes(canonical({'expires_at':self.until}))
        @contextmanager
        def lock(request_id,**kw):
            self.assertFalse(kw);approval.identifier(request_id)
            path=self.root/request_id;path.mkdir(exist_ok=True);yield path
        self.enterContext(patch.object(approval,'policy',side_effect=lambda _:(copy.deepcopy(self.p),self.key)))
        self.enterContext(patch.object(approval,'audit_policy',side_effect=lambda _:(copy.deepcopy(self.p),self.key)))
        self.enterContext(patch.object(approval,'journal_lock',side_effect=lock))
        self.enterContext(patch.object(approval,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch('deployment.lib.provider_recovery_runtime.readonly_configuration',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(admission,'PHYSICAL_RECOVERY',self.root))
        self.enterContext(patch.object(admission,'require_no_pending_operation'))
        self.enterContext(patch.object(release,'isolated_registration',return_value={'expires_at':self.until}))
        self.enterContext(patch.object(origin,'policy',return_value=({'expires_at':self.until},b'',{})))
        self.enterContext(patch('deployment.lib.migration_risk.analyze',return_value=Risk('D',('dynamic_or_procedural_sql_requires_review',),True,True,'MODEL')))

    def prepare(self):return approval.create_canonical(self.system)

    def test_review_binds_all_fourteen_canonical_checksums_without_ordinary_runtime_claim(self):
        result=self.prepare();self.assertEqual(result['state'],'AWAITING_ADMIN_APPROVAL')
        review=result['review'];self.assertEqual([r['number'] for r in review['sql']],list(range(147,161)))
        self.assertEqual(review['manifest_sha256'],release.MANIFEST_SHA256)
        self.assertEqual(review['protocols'],{'delivery2_from':157,'outbox2_from':159,'deletion2_at':160})
        self.driver.preflight.assert_called_once_with(locked=False)
        self.system.authenticate_operator.assert_not_called()
        request=approval.inspect(self.system,result['request_id'])['request']
        self.assertEqual(request['admission']['context_sha256'],context_digest(self.contract))
        self.assertNotIn('plan',request['admission']) # No false original146 compatibility-through160 range.
        self.assertFalse(approval.inspect(self.system,result['request_id'])['consumed'])

    def test_fresh_aal2_and_explicit_confirmation_revalidate_same_coordinator(self):
        result=self.prepare();approval.decide(self.system,result['request_id'],'approve','stdin-token',result['request_sha256'])
        status=approval.inspect(self.system,result['request_id'])
        self.assertEqual(status['state'],'APPROVED');self.assertFalse(status['consumed'])
        self.assertEqual(self.driver.preflight.call_count,2)
        self.system.authenticate_operator.assert_called_once_with('stdin-token')
        self.assertNotIn('stdin-token',json.dumps(status))
        with self.assertRaisesRegex(RuntimeError,'coordinator_lock_required'):
            approval.verify_execution(status['request']['admission'],self.system,consume=True,token='stdin-token')
        self.assertFalse((self.root/result['request_id']/'approval-consumed.json').exists())

    def test_source_database_artifact_or_plan_changes_cannot_use_old_independent_scope(self):
        result=self.prepare()
        original=copy.deepcopy(self.document)
        changes=(lambda d:d.update(changed_immutable_plan=True),
            lambda d:d['admission_contract']['source_roles'].update(enrollment_sha256='f'*64),
            lambda d:d.update(source_bundle_sha256='f'*64),
            lambda d:d['admission_contract']['candidate'].update(source_sha='f'*40),
            lambda d:d['admission_contract']['database'].update(system_identifier='987654321'),
            lambda d:d.update(operation_id=str(uuid.uuid4())))
        for change in changes:
            changed=copy.deepcopy(original);change(changed)
            self.driver.document=changed;self.driver.contract=dict(changed['admission_contract'],plan_sha256=context_digest(changed))
            self.driver.package=SOURCE_PACKAGES/('normal-source-'+changed['source_bundle_sha256'])
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'scope_not_independently_enrolled'):
                approval.decide(self.system,result['request_id'],'approve','token',result['request_sha256'])
        self.assertFalse((self.root/result['request_id']/'approval.json').exists())

    def test_failed_technical_gate_never_publishes_approval_ready_request(self):
        self.driver.preflight.side_effect=RuntimeError('schema160_independent_recovery_receipt_required')
        with self.assertRaisesRegex(RuntimeError,'independent_recovery'):self.prepare()
        folders=[p for p in self.root.iterdir() if (p/'event-000000.json').is_file()]
        self.assertEqual(len(folders),1);self.assertFalse((folders[0]/'request.json').exists())
        self.assertEqual(approval.history(folders[0],self.key)[-1]['state'],'FAILED')

    def test_policy_cannot_be_widened_or_changed_by_candidate_after_request(self):
        result=self.prepare();self.p['execution_max_seconds']+=1
        with self.assertRaisesRegex(RuntimeError,'policy_changed'):
            approval.decide(self.system,result['request_id'],'approve','token',result['request_sha256'])
        self.assertFalse((self.root/result['request_id']/'approval.json').exists())

    def test_unparseable_or_missing_ast_parser_is_not_approval_ready(self):
        with patch('deployment.lib.migration_risk.analyze',return_value=Risk('D',('postgresql_parser_unavailable',),False,False,'MODEL')):
            with self.assertRaisesRegex(RuntimeError,'sql_analysis_unavailable'):self.prepare()
        self.assertFalse(any(self.root.glob('*/request.json')))

    def test_candidate_cannot_supply_a_different_coordinator_or_production_package(self):
        for name,value in (('fixture_only',False),('production_authorization',True)):
            original=self.document[name];self.document[name]=value
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'measured_coordinator_required'):self.prepare()
            self.document[name]=original
        self.system.canonical_exceptional_driver=SimpleNamespace(**vars(self.driver))
        with self.assertRaisesRegex(RuntimeError,'measured_coordinator_required'):self.prepare()

    def test_revalidation_preserves_deadline_and_respects_existing_locks(self):
        result=self.prepare();value=approval.inspect(self.system,result['request_id'])['request']['admission']
        self.system.deploy_lock_descriptor=12
        self.assertEqual(approval.reobserve_review(self.system,value),value)
        self.driver.preflight.assert_called_with(locked=True)
        changed=dict(value,expires_at=self.until+1)
        with self.assertRaisesRegex(RuntimeError,'expired_or_extended'):approval.reobserve_review(self.system,changed)

    def test_existing_generic_execution_entrypoint_cannot_dispatch_canonical_as_automatic(self):
        from deployment.lib.control_plane_upgrade import SystemOperations
        result=self.prepare();status=approval.inspect(self.system,result['request_id'])
        system=SystemOperations.__new__(SystemOperations)
        with patch.object(approval,'inspect',return_value=status),patch.object(admission,'execution_policy'),patch.object(admission,'require_no_pending_operation'):
            with self.assertRaisesRegex(RuntimeError,'protected_coordinator_required'):
                system.exceptional_release_action('execute',request_id=result['request_id'],confirmation=result['request_sha256'])

    def test_independent_policy_parser_requires_exact_canonical_contract_and_distinct_key(self):
        config=self.root/'policy.json';key=self.root/'approval.key';auth=self.root/'auth.key'
        key.write_bytes(self.key);auth.write_bytes(b'separate-authentication-key-0123456789')
        execution={k:self.p[k] for k in ('controller_sha','environment_id')}
        from deployment.lib import control_plane_upgrade_authorization as authz
        with patch.object(approval,'POLICY',config),patch.object(approval,'KEY',key),patch.object(authz,'RELEASE_OPERATOR_KEY',auth):
            config.write_bytes(canonical(self.p))
            self.assertEqual(approval._policy_material(execution,self.p['database_system_identifier']),(self.p,self.key))
            for changed in (dict(self.p,version=1),dict(self.p,contracts=['drop-independent-table-v1']),
                    dict(self.p,execution_max_seconds=10801),dict(self.p,canonical_scope={}),dict(self.p,enabled=False)):
                config.write_bytes(canonical(changed))
                with self.subTest(changed=changed),self.assertRaises(RuntimeError):
                    approval._policy_material(execution,self.p['database_system_identifier'])
            config.write_bytes(canonical(self.p));auth.write_bytes(self.key)
            with self.assertRaisesRegex(RuntimeError,'authentication_key_reused'):
                approval._policy_material(execution,self.p['database_system_identifier'])

    @contextmanager
    def held_locks(self):
        from deployment.lib.control_plane_upgrade import acquire_lock
        from deployment.lib import schema150_provider_adapter as provider
        with patch.object(provider,'protected',lambda p,**kw:Path(p)):
            self.system.automatic_upgrade_lock=acquire_lock(self.system.upgrade_root/'upgrade.lock',create=False)
            self.system.deploy_lock_descriptor=acquire_lock(self.system.state_root/'deploy.lock',create=False)
            try:yield
            finally:
                os.close(self.system.deploy_lock_descriptor);os.close(self.system.automatic_upgrade_lock)
                self.system.deploy_lock_descriptor=None;self.system.automatic_upgrade_lock=None

    def approved(self):
        result=self.prepare();approval.decide(self.system,result['request_id'],'approve','stdin-token',result['request_sha256'])
        return result,approval.inspect(self.system,result['request_id'])['request']['admission']

    def test_exact_consumption_is_durable_under_real_flock_and_cannot_replay(self):
        result,value=self.approved()
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks') as bind,patch.object(origin,'require_successor_binding'):
            approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            consumed=self.root/result['request_id']/'approval-consumed.json'
            self.assertEqual(consumed.stat().st_mode&0o777,0o600)
            self.assertEqual(approval.history(self.root/result['request_id'],self.key)[-1]['state'],'AUTHORIZED_FOR_EXECUTION')
            self.assertEqual(bind.call_args.kwargs,{'upgrade_lock':self.system.automatic_upgrade_lock,'deploy_lock':self.system.deploy_lock_descriptor})
            approval.verify_execution(value,self.system)
            original=consumed.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'approval_consumed'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            self.assertEqual(consumed.read_bytes(),original);self.assertEqual(bind.call_count,1)

    def test_approval_expiry_does_not_extend_or_replace_consumed_execution_lease(self):
        result,value=self.approved();now=int(time.time())
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks'),patch.object(origin,'require_successor_binding'):
            approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            with patch.object(approval.time,'time',return_value=now+121):approval.verify_execution(value,self.system)
            with patch.object(approval.time,'time',return_value=value['expires_at']):
                with self.assertRaisesRegex(RuntimeError,'deadline_expired'):approval.verify_execution(value,self.system)

    def test_expired_or_revoked_unconsumed_approval_never_binds_origin(self):
        result,value=self.approved()
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks') as bind:
            with patch.object(approval.time,'time',return_value=int(time.time())+121):
                with self.assertRaisesRegex(RuntimeError,'approval_expired'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            bind.assert_not_called()
        self.assertFalse((self.root/result['request_id']/'approval-consumed.json').exists())

    def test_revoked_unconsumed_approval_never_binds_origin(self):
        result,value=self.approved()
        approval.decide(self.system,result['request_id'],'revoke','stdin-token',result['request_sha256'])
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks') as bind:
            with self.assertRaisesRegex(RuntimeError,'approval_revoked'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            bind.assert_not_called()
        self.assertFalse((self.root/result['request_id']/'approval-consumed.json').exists())

    def test_post_consumption_interruption_cannot_issue_or_reuse_authority(self):
        result,value=self.approved()
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks',side_effect=RuntimeError('simulated_binding_interruption')):
            with self.assertRaisesRegex(RuntimeError,'binding_interruption'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            self.assertTrue((self.root/result['request_id']/'approval-consumed.json').exists())
            with self.assertRaisesRegex(RuntimeError,'not_owned_or_revoked'):approval.verify_execution(value,self.system)
            with self.assertRaisesRegex(RuntimeError,'approval_consumed'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')

    def test_different_boot_or_process_cannot_reuse_authentic_consumed_record(self):
        result,value=self.approved()
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks'),patch.object(origin,'require_successor_binding'):
            approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            path=self.root/result['request_id']/'approval-consumed.json';original=approval.verified(path,self.key)
            for changed in (dict(original,boot_id=str(uuid.uuid4())),dict(original,pid=original['pid']+1),dict(original,process_start='0')):
                path.write_bytes(canonical(approval.sign(changed,self.key)))
                with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,'not_owned_or_revoked'):approval.verify_execution(value,self.system)

    def test_revoked_current_session_or_failed_revalidation_cannot_consume(self):
        result,value=self.approved()
        with self.held_locks(),patch.object(origin,'bind_successor_under_locks') as bind:
            self.driver.preflight.side_effect=RuntimeError('recovery_evidence_expired')
            with self.assertRaisesRegex(RuntimeError,'recovery_evidence_expired'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            self.driver.preflight.side_effect=None;self.system.authenticate_operator.side_effect=RuntimeError('current_operator_session_revoked')
            with self.assertRaisesRegex(RuntimeError,'session_revoked'):approval.verify_execution(value,self.system,consume=True,token='stdin-token')
            bind.assert_not_called()
        self.assertFalse((self.root/result['request_id']/'approval-consumed.json').exists())
