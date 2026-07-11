from fastapi import APIRouter, Request, Response

from classes import AdminBillingUpdateRequest
from services.audit_service import record_audit_event
from services.auth_service import require_system_admin
from services.billing_service import apply_verified_billing_update


router = APIRouter(prefix="/admin/billing", tags=["Admin Billing"])


@router.post("/features")
def update_tenant_feature(
    update: AdminBillingUpdateRequest,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response, require_aal2=True)

    feature = apply_verified_billing_update(
        tenant_id=update.tenant_id,
        subscription_type=update.subscription_type,
        plan=update.plan,
        builder_type=update.builder_type,
        payment_status=update.payment_status,
        source="admin",
        updated_by_user_id=admin_user.get("id"),
    )

    record_audit_event(
        request=request,
        tenant_id=feature.get("tenant_id", update.tenant_id),
        actor_user_id=admin_user.get("id"),
        action="admin.billing_feature_updated",
        target_type="billing_feature",
        target_id=feature.get("id") or update.tenant_id,
        metadata={
            "plan_type": feature.get("subscription_type"),
            "subscription_type": feature.get("subscription_type"),
            "plan": feature.get("plan"),
            "builder_type": feature.get("builder_type"),
            "payment_status": feature.get("payment_status"),
            "source": "admin",
        },
    )

    return {
        "success": True,
        "data": feature,
    }
