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
        self.assertEqual(result['required_seconds'], 3880)
        self.assertIs(result['authority_issued'], False)

    def test_exact_boundary_and_one_second_short(self):
        window.require_window(self.registration(), now=2000, supervisor_deadline=5880)
        with self.assertRaisesRegex(RuntimeError, 'window_insufficient'):
            window.require_window(self.registration(), now=2000, supervisor_deadline=5879)

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
