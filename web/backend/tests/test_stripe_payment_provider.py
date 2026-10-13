import hashlib
import hmac
import json
import os
import time
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from services import learning_payment_provider as payments
from services.stripe_payment_provider import StripeProvider, major_units, minor_units

SECRET = 'whsec_test_secret'
ENV = {'STRIPE_SECRET_KEY': 'sk_test_123', 'STRIPE_WEBHOOK_SECRET': SECRET, 'MADAR_STRIPE_LIVE_MODE': ''}


def signed(payload, secret=SECRET, stamp=None):
    body = json.dumps(payload).encode()
    stamp = str(int(time.time()) if stamp is None else stamp)
    signature = hmac.new(secret.encode(), stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return body, {'stripe-signature': f't={stamp},v1={signature}'}


def session_event(kind='checkout.session.completed', status='paid', checkout_id=None):
    return {'type': kind, 'data': {'object': {
        'payment_status': status, 'payment_intent': 'pi_123', 'amount_total': 3000, 'currency': 'usd',
        'metadata': {'madar_checkout_id': checkout_id or str(uuid4()), 'madar_tenant_id': '18'}}}}


class StripeProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV); self.env.start(); self.addCleanup(self.env.stop)
        self.provider = StripeProvider()

    def test_registered_and_test_mode_only_by_default(self):
        self.assertIsInstance(payments.PROVIDERS['stripe'], StripeProvider)
        self.assertTrue(self.provider.configured())
        with patch.dict(os.environ, {'STRIPE_SECRET_KEY': 'sk_live_123'}):
            self.assertFalse(self.provider.configured())
            with patch.dict(os.environ, {'MADAR_STRIPE_LIVE_MODE': 'true'}):
                self.assertTrue(self.provider.configured())
        with patch.dict(os.environ, {'STRIPE_WEBHOOK_SECRET': ''}):
            self.assertFalse(self.provider.configured())

    def test_currency_minor_units(self):
        self.assertEqual(minor_units('30.00', 'USD'), 3000)
        self.assertEqual(minor_units('5.25', 'OMR'), 5250)
        self.assertEqual(minor_units('500', 'JPY'), 500)
        self.assertEqual(major_units(5250, 'OMR'), Decimal('5.25'))
        self.assertEqual(major_units(3000, 'USD'), Decimal('30.00'))

    def test_paid_session_maps_to_stable_paid_event(self):
        checkout_id = str(uuid4())
        event = self.provider.verify_webhook(*signed(session_event(checkout_id=checkout_id)))
        self.assertEqual((event.tenant_id, str(event.checkout_id), event.state, event.amount, event.currency), (18, checkout_id, 'paid', Decimal('30.00'), 'USD'))
        self.assertEqual((event.event_id, event.transaction_id, event.sequence), ('pi_123:paid', 'pi_123', 2))

    def test_forged_stale_or_missing_signatures_are_rejected(self):
        body, _ = signed(session_event())
        for headers in [{}, signed(session_event(), secret='whsec_other')[1], signed(session_event(), stamp=int(time.time()) - 3600)[1], {'stripe-signature': 't=1,v1=00'}]:
            with self.assertRaises(payments.InvalidPaymentSignature):
                self.provider.verify_webhook(body, headers)

    def test_unpaid_and_unrelated_events_are_ignored(self):
        for payload in [session_event(status='unpaid'), {'type': 'customer.created', 'data': {'object': {}}}]:
            with self.assertRaises(payments.IgnoredPaymentEvent):
                self.provider.verify_webhook(*signed(payload))
        foreign = session_event(); foreign['data']['object']['metadata'] = {}
        with self.assertRaises(payments.IgnoredPaymentEvent):
            self.provider.verify_webhook(*signed(foreign))

    def test_checkout_session_uses_server_terms_and_idempotency(self):
        checkout = {'id': str(uuid4()), 'tenant_id': 18, 'success_url': 'https://madarportal.com/x?payment=success', 'cancel_url': 'https://madarportal.com/x?payment=cancelled',
                    'terms': {'name': 'EduHope', 'amount': 30, 'currency': 'USD', 'billing_type': 'one_time'}}
        with patch('services.stripe_payment_provider.requests.request') as request:
            request.return_value = MagicMock(ok=True, json=lambda: {'url': 'https://checkout.stripe.com/c/pay/cs_test'})
            session = self.provider.start_checkout(checkout)
        self.assertEqual(session, {'provider': 'stripe', 'url': 'https://checkout.stripe.com/c/pay/cs_test', 'test_mode': True})
        form = request.call_args.kwargs['data']
        self.assertEqual((form['line_items[0][price_data][unit_amount]'], form['line_items[0][price_data][currency]'], form['client_reference_id']), ('3000', 'usd', checkout['id']))
        self.assertEqual(form['payment_intent_data[metadata][madar_checkout_id]'], checkout['id'])
        self.assertEqual(request.call_args.kwargs['headers']['Idempotency-Key'], 'madar-checkout-' + checkout['id'])

    def test_recurring_terms_are_refused_before_contacting_stripe(self):
        checkout = {'id': str(uuid4()), 'tenant_id': 18, 'success_url': '', 'cancel_url': '', 'terms': {'amount': 10, 'currency': 'USD', 'billing_type': 'monthly'}}
        with patch('services.stripe_payment_provider.requests.request') as request, self.assertRaises(HTTPException):
            self.provider.start_checkout(checkout)
        request.assert_not_called()

    def test_reconcile_matches_webhook_identity(self):
        checkout_id = str(uuid4())
        intent = {'id': 'pi_123', 'status': 'succeeded', 'amount_received': 3000, 'currency': 'usd', 'metadata': {'madar_checkout_id': checkout_id, 'madar_tenant_id': '18'}}
        with patch('services.stripe_payment_provider.requests.request') as request:
            request.return_value = MagicMock(ok=True, json=lambda: {'data': [intent]})
            event = self.provider.reconcile({'id': checkout_id})
        self.assertEqual(event, self.provider.verify_webhook(*signed(session_event(checkout_id=checkout_id))))
        with patch('services.stripe_payment_provider.requests.request') as request:
            request.return_value = MagicMock(ok=True, json=lambda: {'data': [{**intent, 'status': 'requires_payment_method'}]})
            with self.assertRaises(HTTPException):
                self.provider.reconcile({'id': checkout_id})


if __name__ == '__main__':
    unittest.main()
