from fastapi import APIRouter, Request, Response

from classes import AdminBillingUpdateRequest
from services.auth_service import require_system_admin
from services.billing_service import apply_verified_billing_update


router = APIRouter(prefix="/admin/billing", tags=["Admin Billing"])


@router.post("/features")
def update_tenant_feature(
    update: AdminBillingUpdateRequest,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response)

    feature = apply_verified_billing_update(
        tenant_id=update.tenant_id,
        subscription_type=update.subscription_type,
        plan=update.plan,
        builder_type=update.builder_type,
        payment_status=update.payment_status,
        source="admin",
        updated_by_user_id=admin_user.get("id"),
    )

    return {
        "success": True,
        "data": feature,
    }
