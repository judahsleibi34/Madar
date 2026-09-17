import unittest
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services import notification_preference_service as preferences
from services import notification_delivery_service as delivery
from workers import notification_worker


class Query:
    def __init__(self, client):
        self.client = client
        self.filters = {}
        self.payload = None

    def select(self, *_args, **_kwargs): return self
    def eq(self, key, value): self.filters[key] = value; return self
    def limit(self, *_args): return self
    def upsert(self, payload, **_kwargs): self.payload = payload; return self
    def execute(self):
        rows = [row for row in self.client.rows if all(row.get(key) == value for key, value in self.filters.items())]
        if self.payload is not None:
            rows = [row for row in self.client.rows if all(
                row.get(key) == self.payload[key]
                for key in ("tenant_id", "user_id", "category", "channel")
            )]
            if rows:
                rows[0].update(self.payload)
            else:
                self.client.rows.append(dict(self.payload))
                rows = [self.client.rows[-1]]
        return SimpleNamespace(data=[dict(row) for row in rows])


class Client:
    def __init__(self): self.rows = []
    def table(self, _name): return Query(self)


class NotificationPreferenceTests(unittest.TestCase):
    def test_missing_row_defaults_enabled_and_tenant_user_rows_are_isolated(self):
        client = Client()
        with patch.object(preferences, "service_supabase", client):
            self.assertTrue(preferences.preference_enabled(
                tenant_id=1, user_id=7, category="calendar", channel="email"
            ))
            self.assertTrue(preferences.preference_enabled(
                tenant_id=1, user_id=7, category="forms", channel="push"
            ))
            preferences.set_notification_preference(
                tenant_id=1, user_id=7, category="forms", channel="push", enabled=False
            )
            self.assertFalse(preferences.preference_enabled(
                tenant_id=1, user_id=7, category="forms", channel="push"
            ))
            self.assertTrue(preferences.preference_enabled(
                tenant_id=2, user_id=7, category="forms", channel="push"
            ))
            self.assertTrue(preferences.preference_enabled(
                tenant_id=1, user_id=8, category="forms", channel="push"
            ))

    def test_supported_pairs_are_strict(self):
        self.assertTrue(preferences.allowed_preference("calendar", "email"))
        self.assertFalse(preferences.allowed_preference("reservations", "email"))
        self.assertFalse(preferences.allowed_preference("unknown", "push"))

    def test_push_delivery_rechecks_disabled_preference_before_provider_use(self):
        """A queued row is terminal when the user disables Push before send."""
        row = {
            "tenant_id": 1,
            "user_id": 7,
            "subscription_id": "subscription-1",
            "payload": {"event_type": "builder.form_submitted", "source_type": "form"},
        }
        with patch.dict(os.environ, {
            "WEB_PUSH_ENABLED": "true",
            "WEB_PUSH_VAPID_PUBLIC_KEY": "public",
            "WEB_PUSH_VAPID_PRIVATE_KEY": "private",
            "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.invalid",
        }, clear=False), \
             patch.object(delivery, "_has_active_membership", return_value=True), \
             patch.object(delivery, "preference_enabled", return_value=False), \
             patch("pywebpush.webpush") as provider:
            with self.assertRaises(delivery.DeliveryError) as raised:
                delivery._deliver_web_push(row)

        self.assertEqual(raised.exception.code, "web_push_preference_disabled")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.terminal_outcome, "revoked")
        # The preference check happens before subscription/provider work, so a
        # later re-enable cannot resurrect this already-terminal delivery.
        provider.assert_not_called()

    def test_reenable_applies_only_to_a_new_future_delivery(self):
        """A terminal old row is never re-claimed; a newly resolved row can send."""
        client = Client()
        with patch.object(preferences, "service_supabase", client):
            preferences.set_notification_preference(
                tenant_id=1, user_id=7, category="forms", channel="push", enabled=False
            )
            self.assertFalse(preferences.preference_enabled(
                tenant_id=1, user_id=7, category="forms", channel="push"
            ))
            preferences.set_notification_preference(
                tenant_id=1, user_id=7, category="forms", channel="push", enabled=True
            )
            self.assertTrue(preferences.preference_enabled(
                tenant_id=1, user_id=7, category="forms", channel="push"
            ))

        claimed = []
        finished = []
        notification_worker.process_batch(
            limit=2,
            # The old disabled delivery is terminal/dead and therefore is not
            # eligible for a later claim. Only the freshly resolved row enters
            # the worker after re-enable.
            claim=lambda **_kwargs: claimed.append("claimed") or [
                {"id": "new-future-delivery", "channel": "web_push", "attempts": 1}
            ],
            deliver=lambda row: self.assertEqual(row["id"], "new-future-delivery"),
            finish=lambda delivery_id, **kwargs: finished.append((delivery_id, kwargs)) or {"status": "sent"},
        )
        self.assertEqual(claimed, ["claimed"])
        self.assertEqual(finished[0][0], "new-future-delivery")
        self.assertEqual(finished[0][1]["outcome"], "sent")

    def test_calendar_user_email_preference_and_customer_email_are_separate(self):
        user_row = {
            "tenant_id": 1,
            "recipient_reference": "user:7",
            "template": "calendar_reminder",
            "payload": {"event_type": "calendar_reminder", "source_type": "calendar_event"},
        }
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = smtp.return_value
        with patch.object(delivery, "service_supabase", MagicMock()), \
             patch.object(delivery, "_has_active_membership", return_value=True), \
             patch.object(delivery, "_rows", return_value=[{"email": "user@example.test"}]), \
             patch.object(delivery, "_smtp_settings", return_value=("smtp", 587, "", "", "from@example.test", False)), \
             patch.object(delivery.smtplib, "SMTP", smtp), \
             patch.object(delivery, "preference_enabled", return_value=True):
            delivery._deliver_email(user_row)
        smtp.return_value.send_message.assert_called_once()

        with patch.object(delivery, "service_supabase", MagicMock()), \
             patch.object(delivery, "_has_active_membership", return_value=True), \
             patch.object(delivery, "_rows", return_value=[{"email": "user@example.test"}]), \
             patch.object(delivery, "preference_enabled", return_value=False), \
             patch.object(delivery.smtplib, "SMTP") as blocked_smtp:
            with self.assertRaises(delivery.DeliveryError) as raised:
                delivery._deliver_email(user_row)
        self.assertEqual(raised.exception.code, "email_preference_disabled")
        blocked_smtp.assert_not_called()

        customer_row = {
            "tenant_id": 1,
            "recipient_reference": "reservation:reservation-1",
            "template": "reservation_confirmation",
            "payload": {},
        }
        customer_smtp = MagicMock()
        customer_smtp.return_value.__enter__.return_value = customer_smtp.return_value
        with patch.object(delivery, "service_supabase", MagicMock()), \
             patch.object(delivery, "_rows", return_value=[{"customer_email": "customer@example.test"}]), \
             patch.object(delivery, "_smtp_settings", return_value=("smtp", 587, "", "", "from@example.test", False)), \
             patch.object(delivery.smtplib, "SMTP", customer_smtp), \
             patch.object(delivery, "preference_enabled") as preference_check:
            delivery._deliver_email(customer_row)
        preference_check.assert_not_called()
        customer_smtp.return_value.send_message.assert_called_once()
