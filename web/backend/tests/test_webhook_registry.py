import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

from services.webhook_registry import (
    SyntheticHmacWebhookAdapter, WebhookAdapterError,
    get_webhook_adapter, public_webhook_providers,
)

SECRET = "test-webhook-secret"
NOW = 1_800_000_000


def signed(payload, *, timestamp=NOW, event_id="evt_test_0001", secret=SECRET):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {"X-Madar-Signature": f"v1={digest}", "X-Madar-Timestamp": str(timestamp),
                 "X-Madar-Event-Id": event_id}


def upsert(version=1):
    return {"event_type": "record.upsert", "resource": "records",
            "record": {"id": "order-1", "version": version, "data": {"amount": 42}}}


class WebhookRegistryTests(unittest.TestCase):
    def test_valid_authoritative_event_is_normalized(self):
        raw, headers = signed(upsert())
        event = SyntheticHmacWebhookAdapter().verify_and_normalize(
            raw_body=raw, headers=headers, secret=SECRET, received_at_epoch=NOW)
        self.assertEqual(event.delivery_kind, "authoritative_record")
        self.assertEqual(event.record_id, "order-1")
        self.assertEqual(event.source_order, 1)

    def test_valid_notification_is_not_interpreted_as_rows(self):
        raw, headers = signed({"event_type": "resource.changed", "resource": "records",
                               "notification": {"reason": "updated"}})
        event = SyntheticHmacWebhookAdapter().verify_and_normalize(
            raw_body=raw, headers=headers, secret=SECRET, received_at_epoch=NOW)
        self.assertEqual(event.delivery_kind, "change_notification")
        self.assertIsNone(event.record_id)

    def test_signature_replay_and_identity_fail_closed(self):
        cases = (
            (lambda raw, headers: (raw + b" ", headers), "webhook_signature_invalid"),
            (lambda raw, headers: (raw, {**headers, "X-Madar-Signature": "v1=" + "0" * 64}),
             "webhook_signature_invalid"),
            (lambda raw, headers: (raw, {**headers, "X-Madar-Timestamp": str(NOW - 301)}),
             "webhook_timestamp_expired"),
            (lambda raw, headers: (raw, {**headers, "X-Madar-Event-Id": "x"}),
             "webhook_event_id_invalid"),
        )
        for mutation, code in cases:
            with self.subTest(code=code):
                raw, headers = mutation(*signed(upsert()))
                with self.assertRaises(WebhookAdapterError) as caught:
                    SyntheticHmacWebhookAdapter().verify_and_normalize(
                        raw_body=raw, headers=headers, secret=SECRET, received_at_epoch=NOW)
                self.assertEqual(caught.exception.code, code)

    def test_duplicate_json_keys_are_rejected_after_valid_signature(self):
        raw = b'{"event_type":"record.upsert","event_type":"resource.changed"}'
        digest = hmac.new(SECRET.encode(), str(NOW).encode() + b"." + raw, hashlib.sha256).hexdigest()
        with self.assertRaises(WebhookAdapterError) as caught:
            SyntheticHmacWebhookAdapter().verify_and_normalize(raw_body=raw, secret=SECRET,
                received_at_epoch=NOW, headers={"X-Madar-Signature": f"v1={digest}",
                "X-Madar-Timestamp": str(NOW), "X-Madar-Event-Id": "evt_test_0002"})
        self.assertEqual(caught.exception.code, "webhook_payload_invalid")

    def test_unknown_and_delete_events_are_explicitly_rejected(self):
        for event_type, code in (("record.deleted", "webhook_deletion_unsupported"),
                                 ("record.changed", "webhook_event_type_unsupported")):
            with self.subTest(event_type=event_type):
                raw, headers = signed({"event_type": event_type, "resource": "records"})
                with self.assertRaises(WebhookAdapterError) as caught:
                    SyntheticHmacWebhookAdapter().verify_and_normalize(
                        raw_body=raw, headers=headers, secret=SECRET, received_at_epoch=NOW)
                self.assertEqual(caught.exception.code, code)

    def test_adapter_is_absent_by_default(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            os.environ.pop("MADAR_TEST_WEBHOOK_ADAPTER_ENABLED", None)
            self.assertIsNone(get_webhook_adapter("webhook_fixture"))
            self.assertEqual(public_webhook_providers(), [])

    def test_fixture_requires_both_exact_test_gates(self):
        with patch.dict(os.environ, {"APP_ENV": "test", "MADAR_TEST_WEBHOOK_ADAPTER_ENABLED": "true"}):
            self.assertIsNotNone(get_webhook_adapter("webhook_fixture"))
            self.assertFalse(public_webhook_providers()[0]["webhook"]["deletion_supported"])


if __name__ == "__main__":
    unittest.main()
