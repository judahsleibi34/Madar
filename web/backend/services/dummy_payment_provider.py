"""Dummy (test-only) payment adapter behind the PaymentProvider interface.

It stands in for a real provider during development so the whole purchase flow —
checkout, Processing/Confirmed/Failed/Cancelled/Refunded, course unlock and
referral rewards — can be exercised without taking money. It is configured only
on a developer machine against the isolated local database (see
local_adapter_enabled); in production configured() is always False, so no
checkout, unlock, reward or withdrawal can ever be created through it.

Its checkouts use provider "local_test", which the database already marks as
simulated: those sales never count towards wallets, Tuition Support or revenue.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from services.learning_payment_provider import PROVIDERS, InvalidPaymentSignature, PaymentProvider, VerifiedPaymentEvent

NAME = "local_test"


class DummyPaymentProvider(PaymentProvider):
    name = NAME

    def configured(self) -> bool:
        from services.elearning_commerce_service import local_adapter_enabled
        return local_adapter_enabled()

    def test_mode(self) -> bool:
        return True

    def start_checkout(self, checkout: dict) -> dict:
        # The checkout is completed in-app with test outcomes; there is no
        # hosted page and no card data is ever collected.
        if not self.configured():
            raise HTTPException(503, detail={"code": "payment_provider_unavailable"})
        return {"mode": "test", "checkout_id": checkout["id"]}

    def verify_webhook(self, raw_body, headers) -> VerifiedPaymentEvent:
        raise InvalidPaymentSignature("The dummy adapter never accepts webhooks")

    def event(self, tenant_id: int, record: dict, state: str, current_period_end=None, cancel_at_period_end=False) -> VerifiedPaymentEvent:
        """A test outcome for one of this member's own dummy checkouts.

        Amount, currency, transaction identity and ordering come from the
        server-held checkout terms; the browser chooses only the outcome.
        """
        if not self.configured():
            raise HTTPException(503, detail={"code": "payment_provider_unavailable"})
        if record.get("provider") != NAME:
            raise HTTPException(404, "Local checkout not found")
        terms = record["terms"]
        period = None
        if terms["billing_type"] != "one_time" and state in {"paid", "active"}:
            period = (datetime.now(timezone.utc) + timedelta(days=30 if terms["billing_type"] == "monthly" else 365)).isoformat()
            if cancel_at_period_end and current_period_end:
                period = current_period_end
        return VerifiedPaymentEvent(
            tenant_id=tenant_id, checkout_id=record["id"], event_id=str(uuid4()), transaction_id="local:" + str(record["id"]),
            sequence=int(record["event_sequence"]) + 1, state=state, amount=Decimal(str(terms["amount"])), currency=terms["currency"],
            period_end=period, cancel_at_period_end=cancel_at_period_end,
        )


PROVIDERS[NAME] = DummyPaymentProvider()
