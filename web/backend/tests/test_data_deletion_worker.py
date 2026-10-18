"""The successor worker must not consume the retained unfenced deletion queue."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services import provider_recovery
from workers import data_deletion_worker as worker


class DeletionWorkerOwnershipBarrierTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.dict(worker.STATE, {
            'healthy': False, 'consuming': False, 'last_poll_at': None,
            'processed': 0, 'failed': 0,
        })
        self.state.start()
        self.addCleanup(self.state.stop)
        self.client = Mock()
        self.client.rpc.return_value.execute.return_value = SimpleNamespace(data=2)

    def test_only_exact_supported_integer_protocol_is_accepted(self):
        worker.require_deletion_ownership_protocol(client=self.client)
        self.client.rpc.assert_called_once_with('data_deletion_ownership_protocol', {})
        for value in (None, 0, 1, 3, True, False, '2', 2.0, [], {'protocol': 2}):
            with self.subTest(value=value):
                self.client.reset_mock()
                self.client.rpc.return_value.execute.return_value = SimpleNamespace(data=value)
                with self.assertRaisesRegex(RuntimeError, '^data_deletion_ownership_protocol_required$'):
                    worker.require_deletion_ownership_protocol(client=self.client)
                self.client.rpc.assert_called_once_with('data_deletion_ownership_protocol', {})

    def test_missing_or_unavailable_protocol_has_no_legacy_fallback_or_error_leak(self):
        self.client.rpc.return_value.execute.side_effect = RuntimeError('private-provider-detail')
        with self.assertRaisesRegex(RuntimeError, '^data_deletion_ownership_protocol_required$') as caught:
            worker.require_deletion_ownership_protocol(client=self.client)
        self.assertNotIn('private-provider-detail', str(caught.exception))
        self.client.rpc.assert_called_once_with('data_deletion_ownership_protocol', {})
        self.client.table.assert_not_called()

    def test_failed_protocol_never_claims_or_processes_deletion(self):
        self.client.rpc.return_value.execute.side_effect = RuntimeError('missing RPC at149')
        with patch('database.service_supabase', self.client), patch.object(
                provider_recovery, 'worker_consumption_allowed', return_value=True), patch.object(
                worker, 'claim_deletion_requests') as claim, patch.object(
                worker, 'process_deletion_request') as process:
            with self.assertRaisesRegex(RuntimeError, 'data_deletion_ownership_protocol_required'):
                worker.run_batch(worker_id='synthetic-worker', batch_size=1)
        claim.assert_not_called()
        process.assert_not_called()
        self.assertFalse(worker.STATE['healthy'])
        self.assertFalse(worker.STATE['consuming'])
        self.assertEqual(worker.STATE['processed'], 0)

    def test_future_supported_protocol_allows_original_claim_to_be_processed(self):
        request = {'id': 'synthetic-request', 'lease_owner': 'synthetic-worker', 'attempt_count': 1}
        with patch('database.service_supabase', self.client), patch.object(
                provider_recovery, 'worker_consumption_allowed', return_value=True), patch.object(
                worker, 'claim_deletion_requests', return_value=[request]) as claim, patch.object(
                worker, 'process_deletion_request', return_value={'state': 'completed'}) as process:
            self.assertEqual(worker.run_batch(worker_id='synthetic-worker', batch_size=1), 1)
        self.client.rpc.assert_called_once_with('data_deletion_ownership_protocol', {})
        claim.assert_called_once_with(worker_id='synthetic-worker', limit=1)
        process.assert_called_once_with(request)
        self.assertEqual(worker.STATE['processed'], 1)

    def test_every_poll_rechecks_protocol_after_database_replacement(self):
        self.client.rpc.return_value.execute.side_effect = [
            SimpleNamespace(data=2), SimpleNamespace(data=1),
        ]
        with patch('database.service_supabase', self.client), patch.object(
                provider_recovery, 'worker_consumption_allowed', return_value=True), patch.object(
                worker, 'claim_deletion_requests', return_value=[]) as claim:
            self.assertEqual(worker.run_batch(worker_id='synthetic-worker', batch_size=1), 0)
            with self.assertRaisesRegex(RuntimeError, 'data_deletion_ownership_protocol_required'):
                worker.run_batch(worker_id='synthetic-worker', batch_size=1)
        self.assertEqual(self.client.rpc.call_count, 2)
        claim.assert_called_once()

    def test_enabled_worker_rejects149_before_starting_health_or_claims(self):
        self.client.rpc.return_value.execute.side_effect = RuntimeError('missing RPC at149')
        with patch.dict(os.environ, {'DATA_DELETION_WORKER_ENABLED': 'true'}), patch(
                'database.service_supabase', self.client), patch.object(
                provider_recovery, 'prohibit_worker_start'), patch.object(
                worker, 'ThreadingHTTPServer') as server, patch.object(
                worker, 'claim_deletion_requests') as claim:
            with self.assertLogs(worker.logger, level='ERROR') as logs:
                with self.assertRaisesRegex(RuntimeError, 'data_deletion_ownership_protocol_required'):
                    worker.main()
        self.assertIn('deletion.ownership_protocol_required', ' '.join(logs.output))
        server.assert_not_called()
        claim.assert_not_called()
        self.assertFalse(worker.STATE['healthy'])
        self.assertFalse(worker.STATE['consuming'])

    def test_ownership_loss_is_observable_without_stale_acknowledgement(self):
        request = {'id': 'synthetic-request'}
        with patch('database.service_supabase', self.client), patch.object(
                provider_recovery, 'worker_consumption_allowed', return_value=True), patch.object(
                worker, 'claim_deletion_requests', return_value=[request]), patch.object(
                worker, 'process_deletion_request', side_effect=worker.DeletionOwnershipLost('deletion_claim_lost')):
            before = worker.STATE.get('ownership_lost', 0)
            with self.assertLogs(worker.logger, level='WARNING'):
                self.assertEqual(worker.run_batch(worker_id='synthetic-worker', batch_size=1), 1)
            self.assertEqual(worker.STATE['ownership_lost'], before + 1)
        self.client.table.assert_not_called()

    def test_valid_read_only_startup_is_healthy_and_never_calls_provider_or_claims(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {'DATA_DELETION_WORKER_ENABLED':'true'}))
            stack.enter_context(patch.object(provider_recovery,'prohibit_worker_start'))
            stack.enter_context(patch.object(provider_recovery,'worker_consumption_status',return_value=(False,True)))
            event=stack.enter_context(patch.object(worker,'STOP_EVENT'));event.is_set.side_effect=[False,True]
            stack.enter_context(patch.object(worker,'ThreadingHTTPServer'))
            stack.enter_context(patch('signal.signal'));stack.enter_context(patch('threading.Thread'))
            protocol=stack.enter_context(patch.object(worker,'require_deletion_ownership_protocol'))
            claim=stack.enter_context(patch.object(worker,'claim_deletion_requests'))
            self.assertEqual(worker.main(),0)
            protocol.assert_not_called();claim.assert_not_called()
            self.assertTrue(worker.STATE['healthy']);self.assertFalse(worker.STATE['consuming'])

    def test_disabled_worker_does_not_attempt_protocol_or_claim(self):
        with patch.dict(os.environ, {'DATA_DELETION_WORKER_ENABLED': 'false'}), patch.object(
                provider_recovery, 'prohibit_worker_start'), patch.object(
                worker, 'require_deletion_ownership_protocol') as protocol, patch.object(
                worker, 'claim_deletion_requests') as claim:
            self.assertEqual(worker.main(), 0)
        protocol.assert_not_called()
        claim.assert_not_called()

    def test_read_only_batch_does_not_probe_or_claim(self):
        with patch.object(provider_recovery, 'worker_consumption_allowed', return_value=False), patch.object(
                worker, 'require_deletion_ownership_protocol') as protocol, patch.object(
                worker, 'claim_deletion_requests') as claim:
            self.assertEqual(worker.run_batch(worker_id='standby', batch_size=1), 0)
        protocol.assert_not_called()
        claim.assert_not_called()
