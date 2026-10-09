"""A healthy standby worker must not claim or schedule business work."""
import unittest
from unittest.mock import Mock, patch
from services import provider_recovery
from workers import notification_worker, calendar_sync_worker, data_deletion_worker


class TransitionWorkerFenceTests(unittest.TestCase):
    def test_missing_or_invalid_authority_denies_consumption(self):
        for error in (RuntimeError('binding'), FileNotFoundError(), ValueError('invalid')):
            with self.subTest(error=type(error).__name__), patch.object(
                    provider_recovery, 'restricted', side_effect=error):
                self.assertFalse(provider_recovery.worker_consumption_allowed())

    def test_invalid_authority_is_unhealthy_but_valid_standby_is_healthy(self):
        with patch.object(provider_recovery, 'restricted', return_value=True):
            self.assertEqual(provider_recovery.worker_consumption_status(), (False, True))
        with patch.object(provider_recovery, 'restricted', side_effect=FileNotFoundError()):
            self.assertEqual(provider_recovery.worker_consumption_status(), (False, False))

    def test_live_authority_is_read_on_every_poll(self):
        with patch.object(provider_recovery, 'restricted', side_effect=[True, False, True]):
            self.assertEqual([provider_recovery.worker_consumption_allowed() for _ in range(3)],
                             [False, True, False])

    def test_restricted_batches_never_claim_or_schedule(self):
        with patch.object(provider_recovery, 'restricted', return_value=True):
            claim = Mock()
            self.assertEqual(notification_worker.process_resolution_batch(limit=1, claim=claim), 0)
            self.assertEqual(notification_worker.process_batch(limit=1, claim=claim), 0)
            claim.assert_not_called()
            with patch.object(calendar_sync_worker, 'claim_task_sync_jobs') as tasks, patch.object(
                    calendar_sync_worker, 'claim_connection_sync_jobs') as connections, patch.object(
                    calendar_sync_worker, 'eligible_inbound_connections') as schedules:
                self.assertEqual(calendar_sync_worker.process_sync_batch(), 0)
                self.assertEqual(calendar_sync_worker.process_connection_batch(), 0)
                self.assertEqual(calendar_sync_worker.schedule_periodic_inbound(interval_seconds=60), 0)
                tasks.assert_not_called()
                connections.assert_not_called()
                schedules.assert_not_called()
            with patch.object(data_deletion_worker, 'claim_deletion_requests') as deletions:
                self.assertEqual(data_deletion_worker.run_batch(worker_id='standby', batch_size=1), 0)
                deletions.assert_not_called()

    def test_all_worker_main_loops_skip_mutating_auxiliary_work(self):
        from contextlib import ExitStack
        cases = [
            (notification_worker, 'NOTIFICATION_WORKER_ENABLED', 'ThreadingHTTPServer',
             ['archive_ended_calendar_tasks', 'enqueue_due_calendar_reminders',
              'process_resolution_batch', 'process_batch', 'cleanup_delivery_data']),
            (calendar_sync_worker, 'CALENDAR_SYNC_WORKER_ENABLED', '_start_health_server',
             ['schedule_periodic_inbound', 'process_sync_batch', 'process_connection_batch']),
            (data_deletion_worker, 'DATA_DELETION_WORKER_ENABLED', 'ThreadingHTTPServer', ['run_batch']),
        ]
        for worker, enabled, server, mutations in cases:
            with self.subTest(worker=worker.__name__), ExitStack() as stack:
                stack.enter_context(patch.dict('os.environ', {enabled: 'true', 'MADAR_RECOVERY_PROFILE': ''}))
                stack.enter_context(patch.object(provider_recovery, 'restricted', return_value=True))
                event = stack.enter_context(patch.object(worker, 'STOP_EVENT'))
                event.is_set.side_effect = [False, True]
                stack.enter_context(patch.object(worker, server))
                stack.enter_context(patch('signal.signal'))
                stack.enter_context(patch('threading.Thread'))
                probes = [stack.enter_context(patch.object(worker, name)) for name in mutations]
                self.assertEqual(worker.main(), 0)
                self.assertFalse(worker.STATE['consuming'])
                for probe in probes:
                    probe.assert_not_called()
