"""Real signatures and journal bytes with modeled host trust, not a restore test."""
import copy,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from deployment.lib import automatic_release_admission as admission
from deployment.lib import exceptional_release_approval as approval
from deployment.lib import historical_origin as origin
from deployment.lib import schema160_release as release
from deployment.lib.migration_inventory import canonical,digest
import test_automatic_release_admission as admission_fixtures
import test_historical_origin as origin_fixtures


class HistoricalPhysicalRecoveryTests(unittest.TestCase):
    def setUp(self):
        # Reuse the independently signed receiver fixture without inheriting
        # ordinary-completion tests or treating their results as restoration.
        self.fixture=admission_fixtures.PhysicalRecoveryAdmissionTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);f=self.fixture
        self.enterContext(patch.object(admission,'ROOT',f.root))
        self.binding=origin_fixtures.HistoricalPreparationBindingTests().contract()['source_roles']
        self.binding['application_sha']='b'*40
        self.observed={'database':{'schema':146,'system_identifier':'123456789'},
            'source_sha':'b'*40,'history_sha256':'5'*64,'host':{'guest_uuid':f.trust['source_guest_uuid']}}
        self.request={'observation':self.observed}
        self.enrollment={'request_sha256':digest(self.request),'expires_at':int(time.time())+200,
            'successor_intent_sha256':self.binding['successor_intent_sha256'],
            'protected_completion_claimed':False,'migration_authority_issued':False}
        self.binding['enrollment_sha256']=digest(self.enrollment)
        self.directory=Path(self.binding['enrollment_root']);self.directory.mkdir(parents=True)
        self.key=b'only-source-journal-test-key-0123456789'
        key_file=f.root/'source.key';key_file.write_bytes(self.key)
        self.enterContext(patch.object(approval,'KEY',key_file))
        self.enterContext(patch.object(origin,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(approval,'protected',lambda p,**kw:Path(p)))
        self.enterContext(patch.object(origin,'recorded_observation',return_value=self.observed))
        self.context={'kind':origin.KIND,'source_binding':self.binding,
            'request_record':approval.sign(self.request,self.key),
            'enrollment_record':approval.sign(self.enrollment,self.key),'history':self.observed['database']}
        (self.directory/'bootstrap-origin-request.json').write_bytes(canonical(self.context['request_record']))
        (self.directory/'bootstrap-origin-consumed.json').write_bytes(canonical(self.context['enrollment_record']))
        f.receipt['release_context']=copy.deepcopy(self.context)
        f.receipt['database_observation'].update(schema=146,protocols=[1,1,0])
        f.receipt['functional_acceptance']['schema']=146
        f.trust.pop('completion_sha256');f.trust.update(version=2,schema=146,
            historical_origin=copy.deepcopy(self.binding),source_origin_sha256=digest(self.context))
        f.seal_receiver()

    def check(self,*,binding=True):
        f=self.fixture
        recovery={'kind':'independent-physical-application-v1','source_system_identifier':'123456789',
            'restore_system_identifier':'123456789','restored_schema':146,'receipt_sha256':f.trust['receipt_sha256']}
        return admission.physical_recovery_evidence(recovery,f.policy,'b'*40,{'delivery':1,'outbox':1,'deletion':0},
            now=int(time.time()),**({'historical_binding':self.binding} if binding else {}))

    def test_exact_historical_receipt_requires_no_fabricated_completion(self):
        self.assertTrue(self.check())
        self.assertNotIn('completion_sha256',self.context)
        self.assertNotIn('completion_sha256',self.fixture.trust)

    def test_ordinary_caller_cannot_implicitly_accept_historical_receipt(self):
        with self.assertRaisesRegex(RuntimeError,'root_binding_invalid'):self.check(binding=False)

    def test_receiver_signature_cannot_invent_source_enrollment_or_successor(self):
        for key in ('enrollment_sha256','successor_intent_sha256','controller_sha'):
            original=copy.deepcopy(self.fixture.receipt)
            self.fixture.receipt['release_context']['source_binding'][key]='f'*(40 if key=='controller_sha' else 64)
            self.fixture.trust['source_origin_sha256']=digest(self.fixture.receipt['release_context'])
            self.fixture.seal_receiver()
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'restored_context_changed_or_expired'):self.check()
            self.fixture.receipt=original

    def test_local_journal_signature_is_checked_independently_of_receiver(self):
        path=self.directory/'bootstrap-origin-consumed.json'
        packet=copy.deepcopy(self.context['enrollment_record']);packet['signature']='0'*64
        path.write_bytes(canonical(packet))
        self.fixture.receipt['release_context']['enrollment_record']=packet
        self.fixture.trust['source_origin_sha256']=digest(self.fixture.receipt['release_context'])
        self.fixture.seal_receiver()
        with self.assertRaisesRegex(RuntimeError,'signature_invalid'):self.check()

    def test_expired_local_enrollment_does_not_gain_new_lifetime_from_restore(self):
        with patch.object(admission.time,'time',return_value=self.enrollment['expires_at']+1):
            # Keep receiver trust fresh to isolate expiration of source authority.
            self.fixture.trust['expires_at']=self.enrollment['expires_at']+300
            self.fixture.seal_receiver()
            with self.assertRaisesRegex(RuntimeError,'restored_context_changed_or_expired'):self.check()

    def test_wrong_source_guest_or_history_refuses_even_with_receiver_signature(self):
        self.fixture.trust['source_guest_uuid']=str(uuid.uuid4())
        self.fixture.receipt['source_guest_uuid']=self.fixture.trust['source_guest_uuid'];self.fixture.seal_receiver()
        with self.assertRaisesRegex(RuntimeError,'historical_observation_changed'):self.check()

    def test_failed_application_acceptance_is_not_replaced_by_successful_database_restore(self):
        self.fixture.receipt['functional_acceptance']['ready']=False;self.fixture.seal_receiver()
        with self.assertRaisesRegex(RuntimeError,'application_unaccepted'):self.check()

    def test_changed_original_private_objects_tenant_or_mfa_refuse(self):
        for key in ('tenant_isolation','original_mfa_totp','anonymous_storage_denied'):
            self.fixture.receipt['functional_acceptance'][key]=False;self.fixture.seal_receiver()
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'application_unaccepted'):self.check()
            self.fixture.receipt['functional_acceptance'][key]=True


class CanonicalRecoveryPlanTests(unittest.TestCase):
    def test_only_exact_receipt_in_immutable_plan_reaches_existing_verifier(self):
        contract=origin_fixtures.HistoricalPreparationBindingTests().contract()
        policy={'controller_sha':contract['candidate']['controller_sha']}
        environment={'database_system_identifier':contract['database']['system_identifier']}
        with patch.object(admission,'execution_policy',return_value=(policy,environment)),patch.object(admission,'physical_recovery_evidence') as verify:
            document={'independent_recovery':{'receipt_sha256':'a'*64}}
            result=release.require_independent_recovery(document,contract,object())
            self.assertEqual(result['restored_schema'],146)
            self.assertEqual(verify.call_args.kwargs['historical_binding'],contract['source_roles'])
            for changed in (None,True,{'verified':True},{'receipt_sha256':'invalid'}):
                with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,'receipt_required'):
                    release.require_independent_recovery({'independent_recovery':changed},contract,object())

    def test_database_and_controller_substitution_refuse_before_receipt_use(self):
        contract=origin_fixtures.HistoricalPreparationBindingTests().contract();document={'independent_recovery':{'receipt_sha256':'a'*64}}
        for policy,environment in (({'controller_sha':'f'*40},{'database_system_identifier':contract['database']['system_identifier']}),
                ({'controller_sha':contract['candidate']['controller_sha']},{'database_system_identifier':'987654321'})):
            with patch.object(admission,'execution_policy',return_value=(policy,environment)),patch.object(admission,'physical_recovery_evidence') as verify:
                with self.assertRaisesRegex(RuntimeError,'scope_changed'):release.require_independent_recovery(document,contract,object())
                verify.assert_not_called()
