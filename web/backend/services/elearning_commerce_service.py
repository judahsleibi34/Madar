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
    # Where the hosted provider returns the learner; a same-origin relative path.
    return_path: str = Field(default="/my-learning/plans", max_length=500, pattern=r"^/(?:[^/\\\s][^\s]*)?$")


class LocalEvent(Payload):
    state: Literal["paid", "failed", "active", "expired", "cancelled", "refunded", "reversed"]
    cancel_at_period_end: bool = False


def call(name, actor, **args):
    if not settings_available(129):
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


def payment_state(tenant_id=None):
    from services import learning_payment_provider as payments
    local = local_adapter_enabled()
    state = {"local_adapter": local, "payments_available": local or payments.available(), "payments_test_mode": not local and payments.test_mode()}
    if tenant_id is not None and live_enrollment_only(tenant_id):
        state.update(enrollment_gate=True, enrollment_open=enrollment_open(state))
    return state


def live_enrollment_only(tenant_id):
    """Academies that opt in (academyExperience.liveEnrollmentOnly) sell only
    through a live provider in production: test payments — the dummy adapter or
    a provider in test mode — never unlock their courses or create rewards
    there; checkout shows "Enrollment opens soon" instead."""
    from services.elearning_academy_service import experience_for_tenant
    return experience_for_tenant(tenant_id).get("liveEnrollmentOnly") is True


def enrollment_open(state):
    if state["local_adapter"]:
        return True
    if not state["payments_available"]:
        return False
    return not state["payments_test_mode"] or os.getenv("APP_ENV") == "development"


def catalog(actor):
    return {**call("get_elearning_catalog", actor), **plans(actor), "settings": get_settings(actor.tenant_id), **payment_state(actor.tenant_id)}


def account(actor):
    result = {**call("get_commerce_learning_account", actor), "settings": get_settings(actor.tenant_id), **payment_state(actor.tenant_id)}
    if result.get("enrollment_gate"):
        result["referral_code"] = applied_referral_code(actor)
    return result


def applied_referral_code(actor):
    """The referral code attached when this member registered, for the order
    summary. Read-only; rewards are still decided by the database on payment."""
    from database import service_supabase
    try:
        rows = service_supabase.table("academy_referrals").select("sender_id").eq("tenant_id", actor.tenant_id).eq("referred_id", actor.user_id).limit(1).execute().data or []
        if not rows:
            return None
        codes = service_supabase.table("academy_referral_codes").select("code").eq("tenant_id", actor.tenant_id).eq("user_id", rows[0]["sender_id"]).limit(1).execute().data or []
        return str(codes[0]["code"]) if codes else None
    except Exception:
        return None


def checkout(actor, payload, request):
    if live_enrollment_only(actor.tenant_id) and not enrollment_open(payment_state()):
        raise HTTPException(409, detail={"code": "enrollment_not_open", "message": "Enrollment opens soon."})
    if not local_adapter_enabled():
        from services.learning_payment_provider import checkout as provider_checkout
        from services.request_security import normalize_origin
        origin = normalize_origin(request.headers.get("origin"))
        if not origin:
            raise HTTPException(400, detail={"code": "checkout_origin_required"})
        return provider_checkout(actor, payload, origin)
    adapter(request)
    return call("create_commerce_learning_checkout", actor, p_offering_id=str(payload.offering_id), p_course_id=str(payload.course_id) if payload.course_id else None, p_idempotency_key=str(payload.idempotency_key), p_provider="local_test")


def simulate(actor, checkout_id, event, request):
    adapter(request)
    from services.dummy_payment_provider import NAME, PROVIDERS
    from services.learning_payment_provider import apply_verified_event
    history = account(actor)
    record = next((value for value in history["checkouts"] if value["id"] == str(checkout_id)), None)
    if not record:
        raise HTTPException(404, "Local checkout not found")
    current = next((value for value in history["entitlements"] if value["checkout_id"] == str(checkout_id)), None) if event.cancel_at_period_end else None
    # Amount, currency, transaction ownership and period are adapter data. The
    # client can select only a local test outcome, never authoritative prices.
    verified = PROVIDERS[NAME].event(actor.tenant_id, record, event.state, current_period_end=current and current["expires_at"], cancel_at_period_end=event.cancel_at_period_end)
    return apply_verified_event(NAME, verified)
