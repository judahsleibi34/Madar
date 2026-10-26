import unittest
from unittest.mock import Mock, patch

from services import notification_outbox_service as outbox
from services import notification_delivery_queue_service as queue
from workers import notification_worker as worker


class OutboxFencingContractTests(unittest.TestCase):
    def setUp(self):
        for key in ('failed', 'resolved', 'ownership_lost', 'acknowledgement_failed', 'processed'):
            worker.STATE[key] = 0

    def test_claim_and_finish_have_generation_and_no_client_clock(self):
        client = Mock(); client.rpc.return_value.execute.return_value.data = [{'id': 'fixture'}]
        outbox.claim_notifications(client=client)
        self.assertEqual(client.rpc.call_args.args[0], 'claim_notification_outbox_v2')
        self.assertNotIn('p_now', client.rpc.call_args.args[1])
        outbox.mark_notification_result('fixture', claim_generation=8, succeeded=False, client=client)
        name, body = client.rpc.call_args.args
        self.assertEqual(name, 'finish_notification_outbox_v2')
        self.assertEqual(body['p_claim_generation'], 8)
        self.assertEqual(body['p_outcome'], 'retry')
        self.assertNotIn('p_finished_at', body)
        self.assertNotIn('p_available_at', body)
        client.table.assert_not_called()

    def test_invalid_tokens_reject_before_any_rpc(self):
        client = Mock()
        for value in (None, True, False, 0, -1, 1.0, '1.0', '-1', {}, 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                outbox.mark_notification_result('fixture', claim_generation=value, succeeded=True, client=client)
            with self.subTest(resolve=value), self.assertRaises(ValueError):
                queue.resolve_outbox_notification({'id': 'fixture', 'claim_generation': value}, client=client)
        client.rpc.assert_not_called()

    def test_resolution_rpc_is_fenced_and_uses_no_pre_read(self):
        client = Mock(); client.rpc.return_value.execute.return_value.data = 1
        self.assertEqual(queue.resolve_outbox_notification({'id': 'fixture', 'claim_generation': 2}, client=client), 1)
        name, body = client.rpc.call_args.args
        self.assertEqual(name, 'resolve_notification_outbox_v3')
        self.assertEqual(body['p_claim_generation'], 2)
        self.assertNotIn('p_now', body)
        client.table.assert_not_called()

    def test_missing_rpc_and_unsupported_protocol_never_fall_back(self):
        client = Mock(); client.rpc.return_value.execute.side_effect = RuntimeError('missing fenced RPC')
        with self.assertRaises(RuntimeError): outbox.claim_notifications(client=client)
        self.assertEqual(client.rpc.call_count, 1)
        self.assertEqual(client.rpc.call_args.args[0], 'claim_notification_outbox_v2')
        client.rpc.reset_mock(); client.rpc.return_value.execute.side_effect = None
        for value in (None, 1, '2', 3):
            client.rpc.return_value.execute.return_value.data = value
            with self.assertRaises(RuntimeError): outbox.require_outbox_fencing(client=client)

    def test_missing_generation_never_reaches_resolver_or_finish(self):
        resolve, finish = Mock(), Mock()
        worker.process_resolution_batch(limit=1, claim=lambda **_: [{'id': 'fixture'}], resolve=resolve, finish=finish)
        resolve.assert_not_called(); finish.assert_not_called()

    def test_lost_resolution_never_retries_finish_or_finalizes_reminder(self):
        finish = Mock()
        row = {'id': 'fixture', 'claim_generation': 1, 'template': 'calendar_reminder'}
        with patch.object(worker, 'mark_calendar_reminder_delivery') as finalizer:
            worker.process_resolution_batch(limit=1, claim=lambda **_: [row],
                resolve=Mock(side_effect=outbox.OutboxOwnershipLost()), finish=finish)
        self.assertEqual(worker.STATE['ownership_lost'], 1)
        self.assertEqual(worker.STATE['resolved'], 0)
        finish.assert_not_called(); finalizer.assert_not_called()

    def test_failed_resolver_passes_same_generation_to_finish(self):
        finish = Mock(return_value=True)
        row = {'id': 'fixture', 'claim_generation': 7, 'attempts': 1}
        worker.process_resolution_batch(limit=1, claim=lambda **_: [row],
            resolve=Mock(side_effect=RuntimeError('resolution failed')), finish=finish)
        self.assertEqual(finish.call_args.kwargs['claim_generation'], 7)
        self.assertFalse(finish.call_args.kwargs['succeeded'])

    def test_lost_failure_ack_and_database_failure_are_distinct(self):
        for error, counter in [(outbox.OutboxOwnershipLost(), 'ownership_lost'),
                               (RuntimeError('database unavailable'), 'acknowledgement_failed')]:
            self.setUp()
            worker.process_resolution_batch(limit=1, claim=lambda **_: [{'id': 'fixture', 'claim_generation': 1}],
                resolve=Mock(side_effect=RuntimeError('resolution failed')), finish=Mock(side_effect=error))
            self.assertEqual(worker.STATE[counter], 1)
            self.assertEqual(worker.STATE['resolved'], 0)

    def test_successor_worker_rejects_schema148_before_all_business_work(self):
        with patch.dict('os.environ', {'NOTIFICATION_WORKER_ENABLED': 'true'}), \
             patch('services.provider_recovery.worker_consumption_status', return_value=(True, True)), \
             patch.object(worker, 'require_delivery_fencing'), \
             patch.object(worker, 'require_outbox_fencing', side_effect=RuntimeError('schema149 required')), \
             patch.object(worker, 'process_batch') as deliveries, \
             patch.object(worker, 'process_resolution_batch') as resolve, \
             patch.object(worker, 'archive_ended_calendar_tasks') as archive, \
             patch.object(worker, 'enqueue_due_calendar_reminders') as enqueue, \
             patch.object(worker, 'cleanup_delivery_data') as cleanup, \
             patch.object(worker, 'STOP_EVENT') as stop, \
             patch.object(worker, 'ThreadingHTTPServer'), patch('signal.signal'), patch('threading.Thread'):
            stop.is_set.side_effect = [False, True]
            self.assertEqual(worker.main(), 0)
        for effect in (deliveries, resolve, archive, enqueue, cleanup): effect.assert_not_called()
        self.assertFalse(worker.STATE['consuming'])


if __name__ == '__main__':
    unittest.main()
