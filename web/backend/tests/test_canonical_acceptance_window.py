import importlib.util
import os
from pathlib import Path
import unittest

root = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
path = root/'staging/integration/canonical_acceptance_window.py'
spec = importlib.util.spec_from_file_location('canonical_acceptance_window', path)
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


class AcceptanceWindowTests(unittest.TestCase):
    def registration(self, expires=9000):
        return {'kind':'isolated-canonical-controller-acceptance', 'created_at':1000, 'expires_at':expires}

    def test_complete_execution_business_reboot_and_retirement_budget(self):
        result = window.require_window(self.registration(), now=2000, supervisor_deadline=8000)
        self.assertEqual(result['deadline'], 8000)
        self.assertEqual(result['required_seconds'], 4140)
        self.assertIs(result['authority_issued'], False)

    def test_exact_boundary_and_one_second_short(self):
        window.require_window(self.registration(), now=2000, supervisor_deadline=6140)
        with self.assertRaisesRegex(RuntimeError, 'window_insufficient'):
            window.require_window(self.registration(), now=2000, supervisor_deadline=6139)

    def test_expired_future_and_unbounded_registration_refused(self):
        for now, expiry in ((9000,9000),(999,9000),(2000,11801)):
            with self.subTest(now=now,expiry=expiry), self.assertRaisesRegex(RuntimeError, 'expired_or_invalid'):
                window.require_window(self.registration(expiry), now=now, supervisor_deadline=20000)

    def test_expired_supervisor_and_short_registration_refused(self):
        for expiry, deadline in ((9000,1999),(5879,12000)):
            with self.subTest(expiry=expiry), self.assertRaisesRegex(RuntimeError, 'window_insufficient'):
                window.require_window(self.registration(expiry), now=2000, supervisor_deadline=deadline)

    def test_malformed_or_boolean_timestamps_refused(self):
        for item in (None, {}, self.registration(True), dict(self.registration(), created_at='1000')):
            with self.subTest(item=item), self.assertRaisesRegex(RuntimeError, 'lifetime_invalid'):
                window.require_window(item, now=2000, supervisor_deadline=9000)

    def test_input_never_renewed(self):
        record = self.registration(); original = dict(record)
        window.require_window(record, now=2000, supervisor_deadline=8000)
        self.assertEqual(record, original)

    def test_fault_recovery_has_separate_reserved_time_without_extending_deployment(self):
        record=self.registration();before=dict(record)
        value=window.require_window(record,now=2000,supervisor_deadline=9000,fault_boundary='ingress_finalization')
        self.assertEqual(value['required_seconds'],5940)
        self.assertEqual(window.REMOTE_REQUEST_TIMEOUT,2500)
        self.assertEqual(window.protected_execution_timeout(started=1000,now=1300),2140)
        self.assertEqual(record,before)
        with self.assertRaisesRegex(RuntimeError,'window_insufficient'):
            window.require_window(record,now=2000,supervisor_deadline=7939,fault_boundary='ingress_finalization')
        with self.assertRaisesRegex(RuntimeError,'fault_scope_unsupported'):
            window.phases('arbitrary-resumption')

    def test_fresh_enrollment_chain_fits_original_supervisor_without_renewal(self):
        from datetime import datetime,timezone
        manifest={'created_at':datetime.fromtimestamp(1000,timezone.utc).isoformat(),
                  'max_lifetime_seconds':10800,'fault_boundary':'ingress_finalization'}
        before=dict(manifest)
        expiry=window.fresh_historical_enrollment_expiry(manifest,now=1300)
        self.assertEqual(expiry,11800)
        backup=window.fresh_recovery_expiry(now=1900,origin_deadline=expiry,
            supervisor_deadline=11800,fault_boundary='ingress_finalization')
        window.require_window(self.registration(backup),now=3700,
            supervisor_deadline=11800,fault_boundary='ingress_finalization')
        self.assertEqual(manifest,before)
        with self.assertRaisesRegex(RuntimeError,'preparation_window_insufficient'):
            window.fresh_historical_enrollment_expiry(manifest,now=4061)
        for change in ({'max_lifetime_seconds':10801},{'max_lifetime_seconds':True},
                       {'created_at':'2026-11-05T00:00:00'},{'created_at':'invalid'}):
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'lifetime_invalid'):
                window.fresh_historical_enrollment_expiry(dict(manifest,**change),now=1300)
        routine=dict(manifest);routine.pop('fault_boundary')
        self.assertEqual(window.fresh_historical_enrollment_expiry(routine,now=1300),8500)

    def test_real_environment_producer_passes_bounded_epoch_to_remote_guard(self):
        import json,runpy,tempfile,time,types,sys
        from unittest.mock import patch,Mock
        from datetime import datetime,timezone
        now=int(time.time())
        class Captured(Exception):pass
        with tempfile.TemporaryDirectory() as tmp:
            rpc=types.ModuleType('automatic_rpc');rpc.EVIDENCE=Path(tmp)
            rpc.MANIFEST={'created_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),
                          'max_lifetime_seconds':10800,'fault_boundary':'ingress_finalization'}
            def capture(code,**kwargs):
                compile(code,'real-environment-producer','exec')
                self.assertIn('ENROLLMENT_DEADLINE='+str(now+10800),code)
                self.assertIn("assert not Path('/etc/madar/release-approval.key').exists()",code)
                self.assertIn('datetime.fromtimestamp(ENROLLMENT_DEADLINE,timezone.utc)',code)
                raise Captured()
            rpc.call=Mock(side_effect=capture)
            with patch.dict(sys.modules,{'automatic_rpc':rpc,'canonical_acceptance_window':window}),patch('time.time',return_value=now):
                with self.assertRaises(Captured):
                    runpy.run_path(str(path.parent/'enroll-historical-test-environment.py'))
            self.assertEqual(rpc.call.call_count,1)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_fresh_fault_evidence_covers_preparation_and_full_window(self):
        expiry=window.fresh_recovery_expiry(now=1000,origin_deadline=11000,
            supervisor_deadline=10000,fault_boundary='ingress_finalization')
        self.assertEqual(expiry,10000)
        value=window.require_window({'kind':'isolated-canonical-controller-acceptance',
            'created_at':2800,'expires_at':expiry},now=2800,supervisor_deadline=10000,
            fault_boundary='ingress_finalization')
        self.assertGreaterEqual(value['remaining_seconds'],value['required_seconds'])
        for origin,supervisor in ((6400,12000),(12000,6400),(12000,8739)):
            with self.subTest(origin=origin,supervisor=supervisor),self.assertRaisesRegex(RuntimeError,'preparation_window_insufficient'):
                window.fresh_recovery_expiry(now=1000,origin_deadline=origin,
                    supervisor_deadline=supervisor,fault_boundary='ingress_finalization')
        self.assertEqual(window.fresh_recovery_expiry(now=1000,origin_deadline=20000,
            supervisor_deadline=20000),6400)
        self.assertEqual(window.fresh_recovery_expiry(now=1000,origin_deadline=20000,
            supervisor_deadline=20000,fault_boundary='ingress_finalization'),11800)

    def test_real_backup_producer_refuses_short_window_before_fencing(self):
        import json,runpy,tempfile,time,types,sys
        from unittest.mock import patch,Mock
        from datetime import datetime,timezone
        now=int(time.time())
        with tempfile.TemporaryDirectory() as tmp:
            rpc=types.ModuleType('automatic_rpc');rpc.ROOT=Path(tmp);rpc.EVIDENCE=Path(tmp)
            rpc.GUEST={'guest_uuid':'owned-synthetic-test'};rpc.SSH=[]
            rpc.MANIFEST={'created_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),
                'max_lifetime_seconds':10800,'fault_boundary':'ingress_finalization'}
            rpc.call=Mock(return_value=json.dumps({'source':'a'*40,'slot':'blue','origin_expires_at':now+5400}))
            with patch.dict(sys.modules,{'automatic_rpc':rpc,'canonical_acceptance_window':window}):
                with self.assertRaisesRegex(RuntimeError,'preparation_window_insufficient'):
                    runpy.run_path(str(root/'staging/integration/prepare-historical-offhost-backup.py'))
            self.assertEqual(rpc.call.call_count,1)
            self.assertEqual(rpc.call.call_args.kwargs['name'],'offhost-source-known-good')
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_nested_execution_budget_covers_observed1600_second_kill(self):
        timeout = window.protected_execution_timeout(started=1000, now=1300)
        self.assertEqual(timeout, 2140)
        self.assertGreater(timeout, 1600)
        self.assertLessEqual(300 + timeout + window.REMOTE_COMPLETION_RESERVE,
                             window.REMOTE_REQUEST_TIMEOUT)
        # The parent also reserves journal capture and transport teardown.
        self.assertGreaterEqual(window.PHASES[0][1] - window.REMOTE_REQUEST_TIMEOUT, 200)

    def test_slow_approval_refuses_before_execution_without_resetting_clock(self):
        self.assertEqual(window.protected_execution_timeout(started=1000, now=1340), 2100)
        with self.assertRaisesRegex(RuntimeError, 'window_insufficient'):
            window.protected_execution_timeout(started=1000, now=1341)
        with self.assertRaisesRegex(RuntimeError, 'window_insufficient'):
            window.protected_execution_timeout(started=1000, now=3500)

    def test_invalid_execution_clock_refuses(self):
        for started, now in ((True, 10), (10, 9), (float('nan'), 10), (0, float('inf'))):
            with self.subTest(started=started, now=now), self.assertRaisesRegex(RuntimeError, 'clock_invalid'):
                window.protected_execution_timeout(started=started, now=now)

    def test_completion_then_business_then_reboot(self):
        calls = []; window.execute_steps(lambda name, timeout: calls.append((name,timeout)))
        self.assertEqual(tuple(calls), window.PHASES)

    def test_interruption_at_each_boundary_never_advances_or_retries(self):
        for failed in range(3):
            calls = []
            def run(name, timeout):
                calls.append(name)
                if len(calls) == failed+1: raise RuntimeError('interrupted')
            with self.subTest(failed=failed), self.assertRaisesRegex(RuntimeError, 'interrupted'):
                window.execute_steps(run)
            self.assertEqual(calls, [name for name,_ in window.PHASES[:failed+1]])


class NativeChildAdapterTests(unittest.TestCase):
    """Real harmless subprocesses under the runner UID; no approval or SQL."""
    def test_actual_adapter_success_once_and_private_log(self):
        import tempfile, sys, json
        with tempfile.TemporaryDirectory() as directory:
            log=Path(directory)/'execution.log'
            argv=[sys.executable,'-c','import os,json,sys; print("diagnostic",file=sys.stderr); print(json.dumps({"uid":os.getuid(),"gid":os.getgid()}))']
            result=window.execute_protected_child(argv,started=0,clock=lambda:1,expires_at=3000,wall_clock=lambda:1,log=log)
            self.assertEqual(result.returncode,0)
            self.assertEqual(result.stderr,b'diagnostic\n')
            self.assertEqual(json.loads(result.stdout),{'uid':os.getuid(),'gid':os.getgid()})
            self.assertEqual(log.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):
                window.execute_protected_child(argv,started=0,clock=lambda:1,expires_at=3000,wall_clock=lambda:1,log=log)

    def test_actual_adapter_insufficient_budget_has_no_child_effect(self):
        import tempfile,sys
        with tempfile.TemporaryDirectory() as directory:
            effect=Path(directory)/'effect';log=Path(directory)/'log'
            with self.assertRaisesRegex(RuntimeError,'window_insufficient'):
                window.execute_protected_child([sys.executable,'-c',f'open({str(effect)!r},"w").close()'],
                                               started=0,clock=lambda:400,expires_at=3000,wall_clock=lambda:1,log=log)
            self.assertFalse(effect.exists());self.assertFalse(log.exists())

    def test_timeout_retains_diagnostics_and_kills_owned_descendants(self):
        import tempfile,sys,subprocess,time
        with tempfile.TemporaryDirectory() as directory:
            log=Path(directory)/'timeout.log'
            code='import subprocess,sys,time,os; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); print(os.getpid(),p.pid,flush=True); time.sleep(60)'
            with self.assertRaises(subprocess.TimeoutExpired):
                window.bounded_child([sys.executable,'-c',code],timeout=1,log=log)
            parent,descendant=map(int,log.read_text().split())
            self.assertFalse(Path(f'/proc/{parent}').exists())
            # Orphan zombies may briefly await init reaping, but no live child
            # may survive the exact process-group retirement.
            for _ in range(50):
                state=Path(f'/proc/{descendant}/stat')
                if not state.exists() or state.read_text().split()[2]=='Z':break
                time.sleep(.02)
            else:self.fail('owned descendant survived timeout')

    def test_real_request_wrapper_uses_shared_adapter_and_no1600_limit(self):
        source=(path.parent/'request-and-execute-approved-canonical-upgrade.py').read_text()
        self.assertIn('executed=execute_protected_child(',source)
        self.assertIn("expires_at=scope['request']['admission']['expires_at']",source)
        self.assertIn('timeout=REMOTE_REQUEST_TIMEOUT',source)
        self.assertNotIn('timeout=1600',source)
        self.assertEqual(window.WINDOW_TIMEOUT,3960)

    def test_signed_admission_expiry_refuses_even_with_remote_time_remaining(self):
        import tempfile,sys
        with tempfile.TemporaryDirectory() as directory:
            log=Path(directory)/'log'
            for expiry in (1800,2159):
                with self.assertRaisesRegex(RuntimeError,'signed_execution_window_insufficient'):
                    window.execute_protected_child([sys.executable,'-c','raise AssertionError("must not launch")'],
                        started=0,clock=lambda:0,expires_at=expiry,wall_clock=lambda:0,log=log)
            self.assertFalse(log.exists())

    def test_new_enrollment_uses_same_bounded_contract(self):
        source=(path.parent/'enroll-frozen-canonical-operation.py').read_text()
        self.assertIn("'execution_max_seconds':REMOTE_REQUEST_TIMEOUT",source)
        self.assertNotIn("'execution_max_seconds':1800",source)
