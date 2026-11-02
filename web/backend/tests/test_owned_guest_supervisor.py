"""Real private IPC/consumption files; modeled QEMU/SSH, not native resume evidence."""
import copy,json,tempfile,time,unittest,uuid
from pathlib import Path
from unittest.mock import Mock,patch
import test_phase7_privileged_vm as vm_fixture
import test_independent_restoration_retirement as retirement_fixture
from deployment.lib.migration_inventory import canonical,digest

vm=vm_fixture.vm


class OwnedGuestControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.g=vm.AutomaticReleaseGuest.__new__(vm.AutomaticReleaseGuest);self.g.directory=self.root/'guest';self.g.directory.mkdir(mode=0o700)
        self.g.evidence=self.root/'evidence';self.g.evidence.mkdir(mode=0o700)
        e,result,key,public,self.hold,self.packet=retirement_fixture.fixture()
        self.g.run_id='codex-20261102T200000Z-automatic-execution-abcdef02';self.g.uuid=self.hold['guest_uuid']
        self.g.pid=2147483647;self.g.record={'restoration_hold':self.hold};self.g.save=Mock()
        self.g.command=Mock();self.g.ssh_args=Mock(return_value=['ssh','pinned-disposable-guest'])
        self.g.require_owned_pid=Mock();self.g.resume_after_poweroff=Mock()
        self.release={'operation':'release-independent-restoration-source-hold','hold_sha256':digest(self.hold),
            'retirement_receipt_sha256':digest(self.packet),'receiver_id':self.hold['receiver_id'],
            'application_started':False,'migration_sql_executed':False,'deployment_authority_issued':False}
        self.g.command.return_value=canonical(self.release)

    def test_parent_and_source_consumptions_are_separate_and_no_implicit_start_occurs(self):
        result=self.g.resume_after_receiver_retirement(self.packet,digest(self.hold))
        self.g.resume_after_poweroff.assert_called_once();self.g.command.assert_called_once()
        args=self.g.command.call_args
        self.assertEqual(args.kwargs['data'],canonical(self.packet))
        self.assertIn('--release-independent-restore-hold',args.args[0][-1])
        self.assertNotIn('--recover-known-good',args.args[0][-1])
        self.assertTrue(result['application_recovery_pending'])
        self.assertTrue((self.g.evidence/'restoration-resume-consumed.json').exists())
        with self.assertRaisesRegex(RuntimeError,'consumed'):self.g.resume_after_receiver_retirement(self.packet,digest(self.hold))
        self.g.resume_after_poweroff.assert_called_once()

    def test_forged_wrong_or_expired_retirement_never_starts_qemu(self):
        for packet,hold_sha in ((dict(self.packet,signature='forged'),digest(self.hold)),(self.packet,'f'*64)):
            with self.subTest(hold_sha=hold_sha),self.assertRaises(RuntimeError):self.g.resume_after_receiver_retirement(packet,hold_sha)
        self.g.resume_after_poweroff.assert_not_called();self.g.command.assert_not_called()
        self.assertFalse((self.g.evidence/'restoration-resume-consumed.json').exists())

    def test_failed_source_release_does_not_claim_recovery_and_cannot_resume_again(self):
        self.g.command.return_value=canonical(dict(self.release,deployment_authority_issued=True))
        with self.assertRaisesRegex(RuntimeError,'release_invalid'):self.g.resume_after_receiver_retirement(self.packet,digest(self.hold))
        self.assertFalse((self.g.evidence/'restoration-resume-completed.json').exists())
        with self.assertRaisesRegex(RuntimeError,'consumed'):self.g.resume_after_receiver_retirement(self.packet,digest(self.hold))
        self.g.resume_after_poweroff.assert_called_once()

    def test_parent_pins_actual_root_observation_while_original_process_is_owned(self):
        self.g.record={};self.g.command.return_value=canonical(self.hold)
        result=self.g.pin_restoration_resume()
        self.g.require_owned_pid.assert_called_once();self.assertEqual(self.g.record['restoration_hold'],self.hold)
        self.assertEqual(result['hold_sha256'],digest(self.hold));self.g.save.assert_called_once()
        self.assertIn('inspect_independent_restoration_hold',self.g.command.call_args.args[0][-1])
        with self.assertRaisesRegex(RuntimeError,'already_pinned'):self.g.pin_restoration_resume()

    def test_wrong_guest_hold_cannot_pin_a_resume(self):
        self.g.record={};hold=copy.deepcopy(self.hold);hold['guest_uuid']=hold['source_guest_uuid']=str(uuid.uuid4())
        self.g.command.return_value=canonical(hold)
        with self.assertRaisesRegex(RuntimeError,'wrong_guest'):self.g.pin_restoration_resume()
        self.g.save.assert_not_called();self.assertNotIn('restoration_hold',self.g.record)

    def request(self,**changes):
        value={'version':1,'kind':'owned-guest-control','run_id':self.g.run_id,'guest_uuid':self.g.uuid,
            'nonce':str(uuid.uuid4()),'action':'pin-independent-restoration'};value.update(changes)
        path=self.root/'guest-control-request.json';path.write_bytes(canonical(value));path.chmod(0o600)
        return path,value

    def test_ipc_is_consumed_once_and_response_is_distinct_from_application_recovery(self):
        path,request=self.request();self.g.pin_restoration_resume=Mock(return_value={'phase':'pinned'})
        self.assertEqual(self.g.service_control(),{'phase':'pinned'});self.assertFalse(path.exists())
        response=self.root/('guest-control-response-'+request['nonce']+'.json')
        self.assertEqual(json.loads(response.read_bytes()),{'phase':'pinned'})
        path.write_bytes(canonical(request));path.chmod(0o600)
        with self.assertRaisesRegex(RuntimeError,'consumed'):self.g.service_control()
        self.g.pin_restoration_resume.assert_called_once()

    def test_foreign_control_request_does_not_reach_any_effect(self):
        for changes in ({'guest_uuid':str(uuid.uuid4())},{'run_id':'madar-staging'},{'action':'start-production'}, {'version':True}):
            path,request=self.request(**changes)
            with self.subTest(changes=changes),self.assertRaisesRegex(RuntimeError,'scope_invalid'):self.g.service_control()
            path.unlink()
        self.g.command.assert_not_called();self.g.resume_after_poweroff.assert_not_called()

    def test_original_supervisor_always_tears_down_on_interruption_or_expiration(self):
        self.g.deadline=time.time()+60;self.g.monotonic_deadline=time.monotonic()+60
        self.g.close=Mock();self.g.service_control=Mock(side_effect=RuntimeError('modeled supervisor interruption'))
        with self.assertRaisesRegex(RuntimeError,'interruption'):self.g.supervise()
        self.g.close.assert_called_once()
        self.g.close.reset_mock();self.g.deadline=0;self.g.supervise();self.g.close.assert_called_once()
