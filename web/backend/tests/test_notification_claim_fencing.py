import unittest
from unittest.mock import Mock, patch

from services import notification_delivery_queue_service as queue
from workers import notification_worker as worker


class ClaimFencingContractTests(unittest.TestCase):
    def setUp(self):
        for key in ("sent", "failed", "processed", "ownership_lost", "acknowledgement_failed"):
            worker.STATE[key] = 0

    def test_claim_clock_and_finish_clock_cannot_be_supplied_by_client(self):
        client = Mock()
        client.rpc.return_value.execute.return_value.data = [{"id": "fixture", "status": "sent"}]
        queue.claim_deliveries(client=client)
        self.assertEqual(client.rpc.call_args.args[0], "claim_notification_deliveries_v2")
        self.assertNotIn("p_now", client.rpc.call_args.args[1])
        queue.finish_delivery("fixture", claim_generation=4, outcome="sent", client=client)
        name, body = client.rpc.call_args.args
        self.assertEqual(name, "finish_notification_delivery_v2")
        self.assertEqual(body["p_claim_generation"], 4)
        self.assertNotIn("p_finished_at", body)
        self.assertNotIn("p_available_at", body)

    def test_invalid_generations_reject_without_rpc(self):
        client = Mock()
        for value in (None, True, False, 0, -1, 1.0, "1.0", "-1", {}, 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                queue.finish_delivery("fixture", claim_generation=value, outcome="sent", client=client)
        client.rpc.assert_not_called()

    def test_no_legacy_protocol_fallback(self):
        client = Mock()
        client.rpc.return_value.execute.side_effect = RuntimeError("missing v2")
        with self.assertRaises(RuntimeError):
            queue.claim_deliveries(client=client)
        self.assertEqual(client.rpc.call_count, 1)
        self.assertEqual(client.rpc.call_args.args[0], "claim_notification_deliveries_v2")

    def test_row_without_generation_never_reaches_provider(self):
        deliver, finish = Mock(), Mock()
        worker.process_batch(limit=1, claim=lambda **_: [{"id": "fixture"}], deliver=deliver, finish=finish)
        deliver.assert_not_called()
        finish.assert_not_called()
        self.assertFalse(worker.STATE["healthy"])

    def test_provider_acceptance_then_ownership_loss_has_no_resend_or_finalize(self):
        deliver = Mock()
        finish = Mock(side_effect=queue.DeliveryOwnershipLost("notification_delivery_claim_lost"))
        with patch.object(worker, "finalize_calendar_reminder_deliveries") as finalize, \
             self.assertLogs(worker.logger, level="WARNING") as logs:
            worker.process_batch(limit=1,
                claim=lambda **_: [{"id": "fixture", "claim_generation": 2, "outbox_id": "outbox", "attempts": 2}],
                deliver=deliver, finish=finish)
        deliver.assert_called_once()
        finish.assert_called_once()
        self.assertEqual(finish.call_args.kwargs["claim_generation"], 2)
        finalize.assert_not_called()
        self.assertEqual(worker.STATE["sent"], 0)
        self.assertEqual(worker.STATE["ownership_lost"], 1)
        self.assertIn("provider_outcome_unknown", str(logs.records[0].error_code))

    def test_database_unavailable_after_provider_acceptance_does_not_send_twice(self):
        deliver = Mock()
        with self.assertLogs(worker.logger, level="ERROR"):
            worker.process_batch(limit=1,
                claim=lambda **_: [{"id": "fixture", "claim_generation": 1}],
                deliver=deliver, finish=Mock(side_effect=RuntimeError("database unavailable")))
        deliver.assert_called_once()
        self.assertEqual(worker.STATE["acknowledgement_failed"], 1)
        self.assertEqual(worker.STATE["sent"], 0)

    def test_queue_poll_never_counts_unacknowledged_provider_acceptance_as_sent(self):
        original=worker.process_batch
        for error in (queue.DeliveryOwnershipLost('notification_delivery_claim_lost'),RuntimeError('database unavailable')):
            for key in ('sent','failed','dead','processed','ownership_lost','acknowledgement_failed'):worker.STATE[key]=0
            def delivery(**_):
                return original(limit=1,claim=lambda **_:[{'id':'fixture','claim_generation':1}],
                    deliver=Mock(),finish=Mock(side_effect=error))
            with self.subTest(error=type(error).__name__), \
                    patch.dict('os.environ',{'NOTIFICATION_WORKER_ENABLED':'true'}), \
                    patch('services.provider_recovery.worker_consumption_status',return_value=(True,True)), \
                    patch.object(worker,'require_delivery_fencing'),patch.object(worker,'archive_ended_calendar_tasks'), \
                    patch.object(worker,'enqueue_due_calendar_reminders'),patch.object(worker,'cleanup_delivery_data'), \
                    patch.object(worker,'process_resolution_batch',return_value=0), \
                    patch.object(worker,'process_batch',side_effect=delivery), \
                    patch.object(worker,'get_queue_metrics',return_value={'sent':40,'failed':7,'dead':5,'queue_depth':1,'oldest_pending_age_seconds':123}), \
                    patch.object(worker,'get_delivery_metrics',return_value={'deliveries_sent':0,'sent':100}), \
                    patch.object(worker,'STOP_EVENT') as stop,patch.object(worker,'ThreadingHTTPServer'), \
                    patch('signal.signal'):
                stop.is_set.side_effect=[False,True]
                self.assertEqual(worker.main(),0)
            self.assertEqual(worker.STATE['sent'],0)
            self.assertEqual(worker.STATE['failed'],1)
            self.assertEqual(worker.STATE['dead'],0)
            self.assertEqual(worker.STATE['queue_depth'],1)
            self.assertEqual(worker.STATE['oldest_pending_age_seconds'],123)

    def test_enabled_worker_rejects_missing_protocol_before_consumption(self):
        with patch.dict("os.environ", {"NOTIFICATION_WORKER_ENABLED": "true"}), \
             patch.object(worker, "require_delivery_fencing", side_effect=RuntimeError("schema147 required")), \
             patch.object(worker, "process_batch") as consume, \
             patch.object(worker, "process_resolution_batch") as resolve, \
             patch.object(worker, "archive_ended_calendar_tasks") as archive, \
             patch.object(worker, "STOP_EVENT") as stop, \
             patch.object(worker, "ThreadingHTTPServer"), \
             patch("signal.signal"), patch("threading.Thread"):
            stop.is_set.side_effect = [False, True]
            self.assertEqual(worker.main(), 0)
        consume.assert_not_called()
        resolve.assert_not_called()
        archive.assert_not_called()
        self.assertFalse(worker.STATE["consuming"])
        self.assertFalse(worker.STATE["healthy"])
