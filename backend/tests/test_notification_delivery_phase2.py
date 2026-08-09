from pathlib import Path
import unittest
from unittest.mock import patch

from routes import public_site_routes
from services import notification_delivery_queue_service


class Response:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class RpcClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return Response(self.results.get(name))


class DomainRpcClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return Response(self.result)


class NotificationDeliveryQueueTests(unittest.TestCase):
    @staticmethod
    def repository_root() -> Path:
        local = Path(__file__).resolve().parents[2]
        return local if (local / "database/migrations").is_dir() else Path("/workspace")

    def test_claim_uses_durable_lease_parameters(self):
        client = RpcClient({"claim_notification_deliveries": [{"id": "delivery"}]})
        rows = notification_delivery_queue_service.claim_deliveries(
            limit=500, lease_seconds=1, client=client
        )
        self.assertEqual(rows, [{"id": "delivery"}])
        name, payload = client.calls[0]
        self.assertEqual(name, "claim_notification_deliveries")
        self.assertEqual(payload["p_limit"], 100)
        self.assertEqual(payload["p_lease_seconds"], 30)

    def test_permanent_and_retry_outcomes_are_explicit(self):
        client = RpcClient(
            {"finish_notification_delivery": {"id": "delivery", "status": "dead"}}
        )
        result = notification_delivery_queue_service.finish_delivery(
            "delivery",
            outcome="dead",
            error_code="invalid_payload",
            client=client,
        )
        self.assertEqual(result["status"], "dead")
        self.assertEqual(client.calls[0][1]["p_outcome"], "dead")
        self.assertIsNone(client.calls[0][1]["p_available_at"])

        client.results["finish_notification_delivery"] = {
            "id": "delivery-2",
            "status": "pending",
        }
        notification_delivery_queue_service.finish_delivery(
            "delivery-2",
            outcome="retry",
            error_code="provider_unavailable",
            retry_after_seconds=42,
            client=client,
        )
        self.assertIsNotNone(client.calls[-1][1]["p_available_at"])

    def test_migration_has_database_backed_delivery_invariants(self):
        root = self.repository_root()
        sql = (root / "database/migrations/073_create_notification_deliveries.sql").read_text()
        normalized = " ".join(sql.lower().split())
        self.assertIn("constraint notification_deliveries_dedup_unique unique", normalized)
        self.assertIn("for update skip locked", normalized)
        self.assertIn("processing_lease_until", normalized)
        self.assertIn("where status in ('sent', 'dead')", normalized)
        self.assertIn("on conflict (tenant_id, deduplication_key)", normalized)
        self.assertLess(
            normalized.index("insert into public.notification_deliveries"),
            normalized.index("set status = 'sent', sent_at = p_now"),
        )

    def test_migration_copies_full_event_data_into_resolution_payload(self):
        root = self.repository_root()
        sql = (root / "supabase/migrations/073_create_notification_deliveries.sql").read_text()
        self.assertIn("'data', event_row.data", sql)
        self.assertIn("'event_id', event_row.id", sql)

    def test_form_and_reservation_helpers_use_notified_transaction_rpcs(self):
        notification = {
            "event_type": "builder.form_submitted",
            "source_type": "form",
            "title": "Form",
            "body": "Submitted",
            "data": {"form_id": "contact"},
        }
        form_client = DomainRpcClient(
            {"duplicate": False, "submission": {"id": "submission"}}
        )
        with patch.object(public_site_routes, "service_supabase", form_client):
            public_site_routes.insert_builder_form_submission(
                {"tenant_id": 7},
                idempotency_key_hash=None,
                request_hash="a" * 64,
                notification=notification,
            )
        self.assertEqual(
            form_client.calls[0][0], "create_builder_form_submission_notified_safe"
        )
        self.assertEqual(form_client.calls[0][1]["p_notification"], notification)

        reservation_client = DomainRpcClient(
            {"duplicate": False, "reservation": {"id": "reservation"}}
        )
        with patch.object(public_site_routes, "service_supabase", reservation_client):
            public_site_routes.insert_builder_reservation(
                {"tenant_id": 7},
                idempotency_key_hash=None,
                request_hash="b" * 64,
                exclusive_slot=False,
                notification=notification,
            )
        self.assertEqual(
            reservation_client.calls[0][0],
            "create_builder_reservation_notified_safe",
        )
        self.assertEqual(
            reservation_client.calls[0][1]["p_notification"], notification
        )


if __name__ == "__main__":
    unittest.main()
