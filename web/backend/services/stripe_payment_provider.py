"""Stripe Checkout adapter for learning commerce one-time purchases.

Stripe is the payment source of truth. The browser only starts a hosted session;
access is granted from a signed webhook or a server-side reconciliation, both of
which derive the same stable event identity so the atomic SQL deduplicates them.
Live keys are refused unless MADAR_STRIPE_LIVE_MODE=true is set explicitly.
"""
import hashlib
import hmac
import os
import time
import json
from decimal import Decimal
from typing import Mapping

import requests
from fastapi import HTTPException

from services.learning_payment_provider import (
    PROVIDERS, IgnoredPaymentEvent, InvalidPaymentSignature, PaymentProvider, VerifiedPaymentEvent,
)

API = 'https://api.stripe.com/v1'
SIGNATURE_TOLERANCE_SECONDS = 300
# Stripe minor units: https://docs.stripe.com/currencies#zero-decimal
ZERO_DECIMAL = frozenset('BIF CLP DJF GNF JPY KMF KRW MGA PYG RWF UGX VND VUV XAF XOF XPF'.split())
THREE_DECIMAL = frozenset('BHD JOD KWD OMR TND'.split())
# Paid supersedes failed for the same checkout; failure never follows payment.
SEQUENCE = {'failed': 1, 'paid': 2}


def minor_units(amount, currency):
    amount = Decimal(str(amount))
    if currency in ZERO_DECIMAL: return int(amount)
    if currency in THREE_DECIMAL: return int(amount * 100) * 10  # Stripe requires a trailing zero
    return int(amount * 100)


def major_units(value, currency):
    value = Decimal(int(value))
    if currency in ZERO_DECIMAL: return value
    return (value / (1000 if currency in THREE_DECIMAL else 100)).quantize(Decimal('0.01'))


class StripeProvider(PaymentProvider):
    def secret(self): return os.getenv('STRIPE_SECRET_KEY', '').strip()

    def configured(self):
        key = self.secret()
        live = os.getenv('MADAR_STRIPE_LIVE_MODE', '').strip().lower() == 'true'
        return bool(os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()) and (key.startswith('sk_test_') or (live and key.startswith('sk_live_')))

    def test_mode(self): return self.secret().startswith('sk_test_')

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(method, API + path, auth=(self.secret(), ''), timeout=20, **kwargs)
        except requests.RequestException as error:
            raise HTTPException(503, detail={'code': 'payment_provider_unavailable'}) from error
        if not response.ok:
            raise HTTPException(502, detail={'code': 'payment_provider_rejected'})
        return response.json()

    def start_checkout(self, checkout):
        terms = checkout['terms']
        if terms['billing_type'] != 'one_time':
            raise HTTPException(409, detail={'code': 'payment_billing_type_unsupported', 'message': 'Online payment currently supports one-time plans.'})
        currency = terms['currency']
        metadata = {'madar_checkout_id': checkout['id'], 'madar_tenant_id': str(checkout['tenant_id'])}
        form = {
            'mode': 'payment', 'client_reference_id': checkout['id'],
            'success_url': checkout['success_url'], 'cancel_url': checkout['cancel_url'],
            'line_items[0][quantity]': '1',
            'line_items[0][price_data][currency]': currency.lower(),
            'line_items[0][price_data][unit_amount]': str(minor_units(terms['amount'], currency)),
            'line_items[0][price_data][product_data][name]': terms.get('name') or 'Course access',
        }
        for key, value in metadata.items():
            form[f'metadata[{key}]'] = value
            form[f'payment_intent_data[metadata][{key}]'] = value
        # Retrying the same server-owned checkout recovers the same session.
        session = self.request('POST', '/checkout/sessions', data=form, headers={'Idempotency-Key': 'madar-checkout-' + checkout['id']})
        return {'provider': 'stripe', 'url': session['url'], 'test_mode': self.test_mode()}

    def event(self, session_or_intent, state, transaction_id, amount, currency):
        metadata = session_or_intent.get('metadata') or {}
        try:
            tenant_id = int(metadata['madar_tenant_id']); checkout_id = metadata['madar_checkout_id']
        except (KeyError, ValueError) as error:
            raise IgnoredPaymentEvent() from error
        return VerifiedPaymentEvent(
            tenant_id=tenant_id, checkout_id=checkout_id, event_id=f'{transaction_id}:{state}',
            transaction_id=transaction_id, sequence=SEQUENCE[state], state=state,
            amount=major_units(amount, currency.upper()), currency=currency.upper(),
        )

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]):
        secret = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
        parts = [item.split('=', 1) for item in headers.get('stripe-signature', '').split(',') if '=' in item]
        stamps = [value for key, value in parts if key == 't']
        signatures = [value for key, value in parts if key == 'v1']
        if not secret or len(stamps) != 1 or not signatures or not stamps[0].isdigit():
            raise InvalidPaymentSignature()
        if abs(time.time() - int(stamps[0])) > SIGNATURE_TOLERANCE_SECONDS:
            raise InvalidPaymentSignature()
        expected = hmac.new(secret.encode(), stamps[0].encode() + b'.' + raw_body, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in signatures):
            raise InvalidPaymentSignature()
        payload = json.loads(raw_body)
        kind, item = payload.get('type'), (payload.get('data') or {}).get('object') or {}
        if kind in {'checkout.session.completed', 'checkout.session.async_payment_succeeded'} and item.get('payment_status') == 'paid' and item.get('payment_intent'):
            return self.event(item, 'paid', item['payment_intent'], item['amount_total'], item['currency'])
        if kind == 'checkout.session.async_payment_failed' and item.get('payment_intent'):
            return self.event(item, 'failed', item['payment_intent'], item['amount_total'], item['currency'])
        raise IgnoredPaymentEvent()

    def reconcile(self, checkout):
        query = f"metadata['madar_checkout_id']:'{checkout['id']}'"
        intents = self.request('GET', '/payment_intents/search', params={'query': query, 'limit': 10}).get('data', [])
        paid = [intent for intent in intents if intent.get('status') == 'succeeded']
        if not paid:
            raise HTTPException(409, detail={'code': 'payment_not_confirmed', 'message': 'Payment is not confirmed yet.'})
        intent = paid[0]
        return self.event(intent, 'paid', intent['id'], intent['amount_received'], intent['currency'])


PROVIDERS['stripe'] = StripeProvider()
