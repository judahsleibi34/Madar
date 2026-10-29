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
            ('operation_locks',lambda *_:__import__('contextlib').nullcontext()),
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
        self.system.authenticate_operator.assert_called_once_with('secret-token')
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
