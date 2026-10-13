import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from services import elearning_commerce_service as commerce
from services import learning_payment_provider as payments
from services.dummy_payment_provider import NAME, DummyPaymentProvider
from services.learning_payment_provider import InvalidPaymentSignature

LOCAL = {"APP_ENV": "development", "MADAR_LOCAL_COMMERCE_ADAPTER": "true",
         "SUPABASE_DB_URL": "postgresql://postgres@127.0.0.1:54322/postgres", "SUPABASE_URL": "http://127.0.0.1:54321"}
# Production with every other dummy switch forged on: only APP_ENV differs.
PRODUCTION = {**LOCAL, "APP_ENV": "production"}
HOSTED = {**LOCAL, "SUPABASE_DB_URL": "postgresql://postgres@db.example.supabase.co:5432/postgres"}
ACTOR = SimpleNamespace(tenant_id=18, user_id=7, role="member")
RECORD = {"id": str(uuid4()), "provider": NAME, "event_sequence": 0, "terms": {"billing_type": "one_time", "amount": "30.00", "currency": "USD"}}


def gated(value=True):
    return patch("services.elearning_academy_service.experience_for_tenant", return_value={"liveEnrollmentOnly": value})


class DummyAdapterProductionTests(unittest.TestCase):
    def test_dummy_adapter_is_never_configured_in_production_or_on_a_hosted_database(self):
        for env in (PRODUCTION, HOSTED, {}):
            with self.subTest(env=env.get("APP_ENV")), patch.dict(os.environ, env, clear=True):
                provider = DummyPaymentProvider()
                self.assertFalse(provider.configured())
                with self.assertRaises(HTTPException) as start:
                    provider.start_checkout({"id": RECORD["id"]})
                self.assertEqual(start.exception.status_code, 503)
                with self.assertRaises(HTTPException):
                    provider.event(18, RECORD, "paid")
                self.assertFalse(payments.available())

    def test_dummy_adapter_never_accepts_webhooks(self):
        with patch.dict(os.environ, LOCAL, clear=True), self.assertRaises(InvalidPaymentSignature):
            DummyPaymentProvider().verify_webhook(b"{}", {})

    def test_selecting_the_dummy_adapter_in_production_fails_closed(self):
        with patch.dict(os.environ, {**PRODUCTION, "MADAR_PAYMENT_PROVIDER": NAME}, clear=True):
            with self.assertRaises(HTTPException) as failure:
                payments.configured_provider()
        self.assertEqual(failure.exception.detail["code"], "payment_provider_unavailable")

    def test_test_outcomes_cannot_be_applied_in_production(self):
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), url=SimpleNamespace(hostname="127.0.0.1"))
        db = MagicMock()
        with patch.dict(os.environ, PRODUCTION, clear=True), patch("database.service_supabase", db), patch.object(payments, "service_supabase", db):
            for state in ("paid", "refunded"):
                with self.subTest(state=state), self.assertRaises(HTTPException) as failure:
                    commerce.simulate(ACTOR, RECORD["id"], commerce.LocalEvent(state=state), request)
                self.assertEqual(failure.exception.status_code, 503)
        db.rpc.assert_not_called()


class DummyAdapterDevelopmentTests(unittest.TestCase):
    def test_events_use_server_terms_and_only_this_adapter_checkouts(self):
        with patch.dict(os.environ, LOCAL, clear=True):
            provider = DummyPaymentProvider()
            self.assertTrue(provider.configured())
            event = provider.event(18, RECORD, "paid")
            self.assertEqual((str(event.amount), event.currency, event.sequence, event.state), ("30.00", "USD", 1, "paid"))
            self.assertEqual(event.transaction_id, "local:" + RECORD["id"])
            with self.assertRaises(HTTPException) as other:
                provider.event(18, {**RECORD, "provider": "stripe"}, "paid")
            self.assertEqual(other.exception.status_code, 404)

    def test_every_document_state_maps_to_a_payment_event(self):
        # Processing = pending checkout; Confirmed = paid; Failed; Cancelled; Refunded.
        with patch.dict(os.environ, LOCAL, clear=True):
            for state in ("paid", "failed", "cancelled", "refunded"):
                self.assertEqual(DummyPaymentProvider().event(18, RECORD, state).state, state)


class LiveEnrollmentGateTests(unittest.TestCase):
    def state(self, env, available, test_mode, flag=True):
        with patch.dict(os.environ, env, clear=True), gated(flag), \
                patch.object(payments, "available", return_value=available), patch.object(payments, "test_mode", return_value=test_mode):
            return commerce.payment_state(18)

    def test_production_without_a_live_provider_shows_enrollment_opens_soon(self):
        self.assertEqual(self.state(PRODUCTION, False, False)["enrollment_open"], False)
        self.assertEqual(self.state(PRODUCTION, True, True)["enrollment_open"], False)  # provider in test mode
        self.assertEqual(self.state(PRODUCTION, True, False)["enrollment_open"], True)  # live provider
        self.assertEqual(self.state(LOCAL, False, False)["enrollment_open"], True)  # dummy adapter, development only

    def test_checkout_is_refused_before_any_order_is_created(self):
        request = SimpleNamespace(headers={"origin": "https://aooloo.madarportal.com"})
        payload = commerce.Checkout(offering_id=uuid4(), idempotency_key=uuid4())
        with patch.dict(os.environ, PRODUCTION, clear=True), gated(), patch.object(payments, "available", return_value=True), \
                patch.object(payments, "test_mode", return_value=True), patch.object(payments, "checkout") as provider_checkout, patch.object(commerce, "call") as rpc:
            with self.assertRaises(HTTPException) as failure:
                commerce.checkout(ACTOR, payload, request)
        self.assertEqual((failure.exception.status_code, failure.exception.detail["code"]), (409, "enrollment_not_open"))
        provider_checkout.assert_not_called()
        rpc.assert_not_called()

    def test_other_academies_keep_their_payment_behaviour(self):
        state = self.state(PRODUCTION, True, True, flag=False)
        self.assertNotIn("enrollment_gate", state)
        self.assertNotIn("enrollment_open", state)
        request = SimpleNamespace(headers={"origin": "https://other.madarportal.com"})
        payload = commerce.Checkout(offering_id=uuid4(), idempotency_key=uuid4())
        with patch.dict(os.environ, PRODUCTION, clear=True), gated(False), patch("services.request_security.normalize_origin", return_value="https://other.madarportal.com"), \
                patch.object(payments, "checkout", return_value={"checkout": {"id": "c"}}) as provider_checkout:
            commerce.checkout(ACTOR, payload, request)
        provider_checkout.assert_called_once()


    def test_order_summary_shows_the_referral_attached_at_registration(self):
        db = MagicMock()
        tables = {"academy_referrals": [{"sender_id": 3}], "academy_referral_codes": [{"code": "6f1d2c9e-0000-4000-8000-000000000001"}]}
        db.table.side_effect = lambda name: MagicMock(**{"select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data": tables[name]})
        with patch("database.service_supabase", db):
            self.assertEqual(commerce.applied_referral_code(ACTOR), "6f1d2c9e-0000-4000-8000-000000000001")
        tables["academy_referrals"] = []
        with patch("database.service_supabase", db):
            self.assertIsNone(commerce.applied_referral_code(ACTOR))


if __name__ == "__main__":
    unittest.main()
