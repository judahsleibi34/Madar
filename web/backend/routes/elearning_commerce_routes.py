from uuid import UUID
from fastapi import APIRouter, Request, Response
from routes.elearning_assessments_routes import owner
from routes.elearning_player_routes import member
from routes.elearning_structure_routes import operation
from services import elearning_commerce_service as service
from services.audit_service import record_audit_event

router = APIRouter(prefix="/elearning", tags=["Learning Commerce"])


def audit(request, actor, action, target):
    record_audit_event(request=request, actor_user_id=actor.user_id, tenant_id=actor.tenant_id,
                       action="commerce.learning." + action, target_type="commerce_offering", target_id=str(target))


@router.get("/plans")
def plans(request: Request, response: Response):
    actor = owner(request, response)
    return operation(lambda: service.plans(actor, True))


@router.post("/plans")
def create(payload: service.Plan, request: Request, response: Response):
    actor = owner(request, response)
    def execute():
        result = service.save(actor, payload)
        audit(request, actor, "plan_created", result["saved_plan_id"])
        return result
    return operation(execute)


@router.put("/plans/{plan_id}")
def update(plan_id: UUID, payload: service.Plan, request: Request, response: Response):
    actor = owner(request, response)
    def execute():
        result = service.save(actor, payload, plan_id)
        audit(request, actor, "plan_updated", plan_id)
        return result
    return operation(execute)


@router.get("/catalog")
def catalog(request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.catalog(actor))


@router.post("/catalog/{course_id}/enrollment")
def enroll(course_id: UUID, request: Request, response: Response):
    actor = member(request, response)
    def execute():
        result = service.call("enroll_elearning_catalog", actor, p_course_id=str(course_id))
        audit(request, actor, "enrolled", course_id)
        return result
    return operation(execute)


@router.get("/my-plans")
def account(request: Request, response: Response):
    actor = member(request, response)
    return operation(lambda: service.account(actor))


@router.post("/checkout")
def checkout(payload: service.Checkout, request: Request, response: Response):
    actor = member(request, response)
    def execute():
        result = service.checkout(actor, payload, request)
        audit(request, actor, "checkout_created", result["checkout"]["id"])
        return result
    return operation(execute)


@router.post("/checkout/{checkout_id}/reconcile")
def reconcile(checkout_id: UUID, request: Request, response: Response):
    """The buyer confirms a hosted payment on return; provider truth decides."""
    actor = member(request, response)
    def execute():
        from services.learning_payment_provider import reconcile_checkout
        result = reconcile_checkout(actor, checkout_id)
        audit(request, actor, "payment_reconciled", checkout_id)
        return result
    return operation(execute)


@router.post("/checkout/{checkout_id}/local-event")
def local_event(checkout_id: UUID, payload: service.LocalEvent, request: Request, response: Response):
    actor = member(request, response)
    def execute():
        result = service.simulate(actor, checkout_id, payload, request)
        audit(request, actor, "local_payment_" + payload.state, checkout_id)
        return result
    return operation(execute)


@router.post('/payments/webhook')
async def payment_webhook(request: Request):
    from fastapi import HTTPException
    from services import learning_payment_provider as payments
    from services.elearning_settings_service import settings_available
    name, provider = payments.configured_provider()
    if not settings_available(129): raise HTTPException(503, 'Learning commerce requires an upgrade')
    body = await request.body()
    if len(body) > 1024 * 1024: raise HTTPException(413, 'Webhook too large')
    try:
        event = provider.verify_webhook(body, request.headers)
    except payments.InvalidPaymentSignature as error:
        raise HTTPException(400, 'Payment verification failed') from error
    except payments.IgnoredPaymentEvent:
        return {'ignored': True}
    return operation(lambda: payments.apply_verified_event(name, event))
