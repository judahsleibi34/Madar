"""Sanitized diagnostics retain stack/operation, never messages or private data."""
import json,os,sys,unittest
from pathlib import Path
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_candidate import DetachedRecoveryCandidate
from deployment.lib.active_recovery_resumption import sanitized_staging_failure
from tests import test_active_recovery_resumption as protocol

class DiagnosticTests(unittest.TestCase):
    def test_messages_locals_arguments_and_private_paths_are_redacted(self):
        private='credential=do-not-record customer@example.com /private/customer/location'
        c=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate)
        def fail():raise RuntimeError(private)
        try:c.staging_check('post-retirement-ports',fail)
        except RuntimeError as error:result=sanitized_staging_failure(error)
        rendered=json.dumps(result)
        self.assertNotIn(private,rendered);self.assertNotIn('customer',rendered)
        self.assertEqual(result['operation'],'post-retirement-ports');self.assertEqual(result['phase'],'detached_candidate_pending')
        self.assertEqual(result['exception_type'],'RuntimeError');self.assertTrue(result['traceback'])
        self.assertTrue(all(set(frame)=={'file','function','line'} for frame in result['traceback']))
    def test_nested_operation_keeps_precise_inner_stage(self):
        c=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate)
        def fail():raise RuntimeError('private')
        try:c.staging_check('previous-candidate-retirement',c.staging_check,'post-retirement-ports',fail)
        except RuntimeError as e:self.assertEqual(sanitized_staging_failure(e)['operation'],'post-retirement-ports')
    def test_errno_retained_without_exception_text(self):
        c=DetachedRecoveryCandidate.__new__(DetachedRecoveryCandidate)
        def fail():
            try:raise OSError(98,'private values')
            except OSError:raise RuntimeError('private error') from None
        try:c.staging_check('post-retirement-ports',fail)
        except RuntimeError as e:result=sanitized_staging_failure(e)
        self.assertEqual(result['os_errno'],98);self.assertNotIn('private',json.dumps(result))
    def test_failed_attempt_appends_diagnostic_and_cannot_replay(self):
        fixture=protocol.ActiveRecoveryResumptionTests();fixture.setUp()
        try:
            fixture.authorize();before=fixture.tx.authorization.read_bytes();fixture.ops.fail='stage_detached_read_only_candidate'
            with self.assertRaises(RuntimeError):fixture.tx.execute()
            records=[json.loads(line) for line in fixture.tx.journal.read_text().splitlines()]
            self.assertEqual(records[-1]['phase'],'detached_candidate_failed');self.assertIn('failure',records[-1])
            self.assertEqual(fixture.tx.authorization.read_bytes(),before)
            with self.assertRaisesRegex(RuntimeError,'attempt_already_used'):fixture.tx.execute()
            self.assertNotIn('publish_read_only_candidate',fixture.ops.calls)
        finally:fixture.doCleanups()
