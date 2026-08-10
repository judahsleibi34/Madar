import json
from pathlib import Path
import unittest

from services.notification_action_service import (
    build_notification_action,
    normalize_notification_data,
    validate_notification_action_path,
)
from services.notification_delivery_service import (
    MAX_WEB_PUSH_PAYLOAD_BYTES,
    build_web_push_payload,
)


class NotificationActionContractTests(unittest.TestCase):
    def test_accepts_only_the_current_allowlisted_relative_route(self):
        self.assertEqual(
            validate_notification_action_path("/notifications"), "/notifications"
        )
        rejected = [
            "https://evil.example/notifications",
            "//evil.example/notifications",
            "javascript:alert(1)",
            "data:text/html,evil",
            "https://user:pass@evil.example",
            "/\\evil.example",
            "/%2f%2fevil.example",
            "/notifications#secret",
            "/notifications?next=https://evil.example",
            "/unsupported/object/1",
            "/" + ("a" * 301),
        ]
        for path in rejected:
            with self.subTest(path=path):
                self.assertIsNone(validate_notification_action_path(path))

    def test_invalid_action_falls_back_without_preserving_unsafe_path(self):
        result = normalize_notification_data(
            {
                "action": {
                    "kind": "reservation",
                    "object_id": "reservation-1",
                    "path": "https://evil.example/steal",
                }
            },
            default_kind="reservation",
            object_id="reservation-1",
        )
        self.assertEqual(
            result["action"],
            {
                "kind": "reservation",
                "object_id": "reservation-1",
                "path": "/notifications",
            },
        )

    def test_object_identity_has_a_bounded_non_url_shape(self):
        valid = build_notification_action(kind="calendar_event", object_id="event:123")
        self.assertEqual(valid["object_id"], "event:123")
        invalid = build_notification_action(
            kind="calendar_event", object_id="../../secret?token=1"
        )
        self.assertNotIn("object_id", invalid)


class WebPushPayloadPrivacyTests(unittest.TestCase):
    def test_form_payload_excludes_public_answers_and_contact_details(self):
        row = {
            "event_id": "8da92bca-55a4-4e44-8653-55c60285241c",
            "payload": {
                "event_type": "form_submission_received",
                "source_type": "form",
                "source_id": "form-7",
                "title": "Alice Smith submitted Medical Intake",
                "body": "alice@example.test +1-555-0100 private diagnosis",
                "data": {
                    "answers": {"diagnosis": "private diagnosis"},
                    "customer_email": "alice@example.test",
                    "customer_phone": "+1-555-0100",
                    "action": build_notification_action(
                        kind="form_submission", object_id="form-7"
                    ),
                },
            },
        }
        encoded = build_web_push_payload(row)
        payload = json.loads(encoded)
        self.assertEqual(payload["title"], "New form submission")
        self.assertEqual(payload["body"], "A new form submission was received.")
        self.assertEqual(
            payload["data"],
            {
                "action": {
                    "kind": "form_submission",
                    "object_id": "form-7",
                    "path": "/notifications",
                }
            },
        )
        self.assertNotIn("alice", encoded.lower())
        self.assertNotIn("diagnosis", encoded.lower())
        self.assertLessEqual(len(encoded.encode("utf-8")), MAX_WEB_PUSH_PAYLOAD_BYTES)
        self.assertEqual(payload["tag"], f"madar-event:{row['event_id']}")

    def test_reservation_payload_is_privacy_minimized(self):
        encoded = build_web_push_payload(
            {
                "payload": {
                    "event_type": "reservation_created",
                    "source_type": "reservationBlock",
                    "source_id": "reservation-1",
                    "title": "Private consultation for Alice",
                    "body": "2026-08-12 09:00 with alice@example.test",
                    "data": {
                        "payload": {"customer_email": "alice@example.test"},
                        "action": build_notification_action(
                            kind="reservation", object_id="reservation-1"
                        ),
                    },
                }
            }
        )
        payload = json.loads(encoded)
        self.assertEqual(payload["title"], "New reservation received")
        self.assertNotIn("Alice", encoded)
        self.assertNotIn("2026-08-12", encoded)
        self.assertNotIn("example.test", encoded)

    def test_atomic_producer_source_identity_populates_push_action(self):
        payload = json.loads(build_web_push_payload({
            "payload": {
                "event_type": "builder.form_submitted",
                "source_type": "form",
                "source_id": "saved-submission-id",
                "data": {"action": build_notification_action(kind="form_submission")},
            }
        }))
        self.assertEqual(
            payload["data"]["action"]["object_id"], "saved-submission-id"
        )


class PushLifecycleMigrationContractTests(unittest.TestCase):
    def test_migration_preserves_history_and_scopes_permission_revocation(self):
        local = Path(__file__).resolve().parents[2]
        root = local if (local / "database/migrations").is_dir() else Path("/workspace")
        sql = (root / "database/migrations/075_harden_web_push_lifecycle.sql").read_text()
        normalized = " ".join(sql.lower().split())
        self.assertIn("notification_permission <> 'granted'", normalized)
        self.assertIn("not notifications_enabled or notification_permission = 'granted'", normalized)
        self.assertIn("where app_installation_id = installation.id", normalized)
        self.assertIn("existing_subscription.p256dh <> p_p256dh", normalized)
        self.assertIn("existing_subscription.auth <> p_auth", normalized)
        self.assertIn("set endpoint = concat( 'revoked:'", normalized)
        self.assertNotIn("delete from public.web_push_subscriptions", normalized)


if __name__ == "__main__":
    unittest.main()
