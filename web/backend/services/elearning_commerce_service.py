"""Learning consumes generic Commerce offerings, orders and confirmed entitlements."""
import os
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import Field, model_validator
from services.elearning_structure_service import Payload
from services.elearning_player_service import call as player_call
from services.elearning_settings_service import settings_available, get_settings


class Plan(Payload):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    status: Literal["draft", "active", "archived"] = "draft"
    billing_type: Literal["one_time", "monthly", "yearly"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    access_scope: Literal["single_course", "selected_courses", "all_courses"]
    course_ids: list[UUID] = Field(default_factory=list, max_length=500)
    revision: int = Field(default=1, ge=1, strict=True)

    @model_validator(mode="after")
    def scope_relationships(self):
        size = len(self.course_ids)
        if len(set(self.course_ids)) != size or (self.access_scope == "single_course" and size != 1) or (self.access_scope == "selected_courses" and not size) or (self.access_scope == "all_courses" and size):
            raise ValueError("Select courses matching the access scope")
        return self


class Checkout(Payload):
    offering_id: UUID
    course_id: UUID | None = None
    idempotency_key: UUID


class LocalEvent(Payload):
    state: Literal["paid", "failed", "active", "expired", "cancelled", "refunded", "reversed"]
    cancel_at_period_end: bool = False


def call(name, actor, **args):
    if not settings_available(128):
        raise HTTPException(503, detail={"code": "learning_commerce_upgrade_required"})
    return player_call(name, actor, **args)


def local_adapter_enabled():
    # Native local launcher supplies these only after verifying the loopback DB.
    # APP_ENV alone or a forged request host can never enable payment simulation.
    return (
        os.getenv("APP_ENV") == "development"
        and os.getenv("MADAR_LOCAL_COMMERCE_ADAPTER") == "true"
        and urlsplit(os.getenv("SUPABASE_DB_URL", "")).hostname in {"localhost", "127.0.0.1", "::1"}
        and urlsplit(os.getenv("SUPABASE_DB_URL", "")).port == 54322
        and urlsplit(os.getenv("SUPABASE_URL", "")).hostname in {"localhost", "127.0.0.1", "::1"}
    )


def adapter(request):
    if not local_adapter_enabled() or not request.client or request.client.host not in {"127.0.0.1", "::1", "localhost"} or request.url.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(503, detail={"code": "payment_provider_unavailable", "message": "Live payments are disabled. Local simulation requires the isolated development database."})


def plans(actor, admin=False):
    return call("get_elearning_offerings", actor, p_admin=admin)


def save(actor, payload, plan_id=None):
    details = payload.model_dump(mode="json", exclude={"revision"})
    return call("manage_elearning_offering", actor, p_id=str(plan_id) if plan_id else None, p_revision=payload.revision, p_details=details)


def catalog(actor):
    return {**call("get_elearning_catalog", actor), **plans(actor), "settings": get_settings(actor.tenant_id), "local_adapter": local_adapter_enabled()}


def account(actor):
    return {**call("get_commerce_learning_account", actor), "settings": get_settings(actor.tenant_id), "local_adapter": local_adapter_enabled()}


def checkout(actor, payload, request):
    adapter(request)
    return call("create_commerce_learning_checkout", actor, p_offering_id=str(payload.offering_id), p_course_id=str(payload.course_id) if payload.course_id else None, p_idempotency_key=str(payload.idempotency_key), p_provider="local_test")


def simulate(actor, checkout_id, event, request):
    adapter(request)
    from datetime import datetime, timedelta, timezone
    from database import service_supabase
    history = account(actor)
    records = history["checkouts"]
    record = next((value for value in records if value["id"] == str(checkout_id)), None)
    if not record or record["provider"] != "local_test":
        raise HTTPException(404, "Local checkout not found")
    terms = record["terms"]
    period = None
    if terms["billing_type"] != "one_time" and event.state in {"paid", "active"}:
        period = (datetime.now(timezone.utc) + timedelta(days=30 if terms["billing_type"] == "monthly" else 365)).isoformat()
        if event.cancel_at_period_end:
            current = next((value for value in history["entitlements"] if value["checkout_id"] == str(checkout_id)), None)
            if current:
                period = current["expires_at"]
    # Amount, currency, transaction ownership and period are adapter data. The
    # client can select only a local test outcome, never authoritative prices.
    return service_supabase.rpc("apply_commerce_payment_event", {
        "p_tenant_id": actor.tenant_id, "p_checkout_id": str(checkout_id), "p_provider": "local_test",
        "p_event_id": str(uuid4()), "p_transaction_id": "local:" + str(checkout_id),
        "p_sequence": record["event_sequence"] + 1, "p_state": event.state,
        "p_amount": terms["amount"], "p_currency": terms["currency"],
        "p_period_end": period, "p_cancel_at_period_end": event.cancel_at_period_end,
    }).execute().data
