"""Provider boundary for learning commerce; no live provider is installed by default.

A concrete adapter must verify its provider's signature over raw webhook bytes,
verify/reconcile payment ownership, derive authoritative event ordering, and map
provider outcomes into the existing commerce event contract. An HTTP success
redirect is never a payment event. Adapters are registered by application code,
never imported from a user-controlled path or selected by request parameters.
"""
import os
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Literal, Mapping
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from database import service_supabase


class VerifiedPaymentEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: int = Field(ge=1, strict=True)
    checkout_id: UUID
    event_id: str = Field(min_length=1, max_length=200)
    transaction_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1, strict=True)
    state: Literal['paid', 'failed', 'active', 'expired', 'cancelled', 'refunded', 'reversed']
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    period_end: str | None = None
    cancel_at_period_end: bool = False


class InvalidPaymentSignature(Exception):
    pass


class IgnoredPaymentEvent(Exception):
    """A verified provider notification that carries no payment state change."""


class PaymentProvider(ABC):
    def reconcile(self, checkout: dict) -> VerifiedPaymentEvent:
        """Retrieve provider truth for this server-owned checkout.

        Concrete adapters must implement authenticated provider lookup and derive
        the same stable event identity/order used by webhook verification.
        """
        raise HTTPException(503, detail={'code': 'payment_reconciliation_unavailable'})

    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    def start_checkout(self, checkout: dict) -> dict:
        """Create/recover provider session idempotently using checkout['id'].

        Return public session information only. No credentials or client-provided
        prices. Validate provider redirect destinations in the concrete adapter.
        """

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> VerifiedPaymentEvent:
        """Verify signature/time/replay policy and provider-confirmed payment.

        Raise InvalidPaymentSignature for unauthenticated/unverified events. The
        adapter must reconcile provider truth if a webhook is ambiguous or out
        of order; supplied event ordering cannot come from a browser.
        """


PROVIDERS: dict[str, PaymentProvider] = {}


def configured_provider():
    name = os.getenv('MADAR_PAYMENT_PROVIDER', '').strip()
    provider = PROVIDERS.get(name)
    if not provider or not provider.configured():
        raise HTTPException(503, detail={'code': 'payment_provider_unavailable', 'message': 'Live payments are not configured.'})
    return name, provider


def available():
    try: configured_provider(); return True
    except HTTPException: return False


def apply_verified_event(provider_name, event):
    # Existing SQL validates tenant/checkout/provider, amount/currency/ownership,
    # ordering, duplicate identity, refunds and atomic access/referral effects.
    return service_supabase.rpc('apply_commerce_payment_event', {
        'p_tenant_id': event.tenant_id, 'p_checkout_id': str(event.checkout_id), 'p_provider': provider_name,
        'p_event_id': event.event_id, 'p_transaction_id': event.transaction_id, 'p_sequence': event.sequence,
        'p_state': event.state, 'p_amount': str(event.amount), 'p_currency': event.currency,
        'p_period_end': event.period_end, 'p_cancel_at_period_end': event.cancel_at_period_end,
    }).execute().data


def checkout(actor, payload, origin):
    from services.elearning_commerce_service import call
    name, provider = configured_provider()
    result = call('create_commerce_learning_checkout', actor, p_offering_id=str(payload.offering_id),
                  p_course_id=str(payload.course_id) if payload.course_id else None,
                  p_idempotency_key=str(payload.idempotency_key), p_provider=name)
    # Return URLs: a CSRF-verified origin plus a validated relative path only.
    back = origin + payload.return_path
    joiner = '&' if '?' in back else '?'
    session = provider.start_checkout({**result['checkout'], 'success_url': f"{back}{joiner}payment=success&checkout={result['checkout']['id']}", 'cancel_url': f'{back}{joiner}payment=cancelled'})
    return {**result, 'provider_session': session}


def test_mode():
    try: return bool(getattr(configured_provider()[1], 'test_mode', lambda: False)())
    except HTTPException: return False


def reconcile_checkout(actor, checkout_id):
    rows = service_supabase.table('ecommerce_checkouts').select('*').eq('tenant_id', actor.tenant_id).eq('id', str(checkout_id)).limit(1).execute().data or []
    if not rows: raise HTTPException(404, 'Checkout not found')
    record = rows[0]
    if record['user_id'] != actor.user_id and actor.role not in {'owner', 'admin'}:
        raise HTTPException(403, 'Purchase access required')
    provider_name = record['provider']
    provider = PROVIDERS.get(provider_name)
    if not provider or not provider.configured():
        raise HTTPException(503, detail={'code': 'payment_provider_unavailable'})
    event = provider.reconcile(record)
    if event.tenant_id != actor.tenant_id or str(event.checkout_id) != str(record['id']):
        raise HTTPException(409, 'Provider reconciliation ownership mismatch')
    return apply_verified_event(provider_name, event)


# Concrete adapters register into PROVIDERS; MADAR_PAYMENT_PROVIDER selects one.
import services.stripe_payment_provider  # noqa: E402,F401
