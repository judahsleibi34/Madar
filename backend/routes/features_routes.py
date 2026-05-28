from fastapi import APIRouter, Depends, HTTPException, Request, Response

from classes import SubscriptionRequest
from database import service_supabase
from services.auth_service import get_authenticated_user_row

router = APIRouter()


def require_authenticated_user(request: Request, response: Response):
    return get_authenticated_user_row(request, response)


def normalize_authenticated_user(user):
    if isinstance(user, tuple):
        for item in user:
            if isinstance(item, dict):
                return item

    if isinstance(user, dict):
        return user

    raise HTTPException(
        status_code=401,
        detail="Invalid authenticated user data.",
    )


@router.post("/feature-type")
def feature_type(
    subscription: SubscriptionRequest,
    user=Depends(require_authenticated_user),
):
    try:
        current_user = normalize_authenticated_user(user)
        tenant_id = current_user.get("tenant_id")

        if tenant_id is None:
            raise HTTPException(
                status_code=400,
                detail="User does not have a tenant_id.",
            )

        if subscription.subscription_type == "full_platform":
            if subscription.builder_type is not None:
                raise HTTPException(
                    status_code=400,
                    detail="builder_type must be null for full platform subscriptions.",
                )

            existing = (
                service_supabase
                .table("features")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("subscription_type", "full_platform")
                .execute()
            )

            payload = {
                "tenant_id": tenant_id,
                "subscription_type": "full_platform",
                "plan": subscription.plan,
                "builder_type": None,
                "payment_status": "pending",
            }

            if existing.data:
                result = (
                    service_supabase
                    .table("features")
                    .update(payload)
                    .eq("id", existing.data[0]["id"])
                    .execute()
                )

                return {
                    "success": True,
                    "message": "Full platform subscription updated successfully.",
                    "data": result.data,
                }

            result = (
                service_supabase
                .table("features")
                .insert(payload)
                .execute()
            )

            return {
                "success": True,
                "message": "Full platform subscription saved successfully.",
                "data": result.data,
            }

        if subscription.subscription_type == "individual_builder":
            if subscription.builder_type is None:
                raise HTTPException(
                    status_code=400,
                    detail="builder_type is required for individual builder subscriptions.",
                )

            existing = (
                service_supabase
                .table("features")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("subscription_type", "individual_builder")
                .eq("builder_type", subscription.builder_type)
                .execute()
            )

            payload = {
                "tenant_id": tenant_id,
                "subscription_type": "individual_builder",
                "plan": subscription.plan,
                "builder_type": subscription.builder_type,
                "payment_status": "pending",
            }

            if existing.data:
                result = (
                    service_supabase
                    .table("features")
                    .update(payload)
                    .eq("id", existing.data[0]["id"])
                    .execute()
                )

                return {
                    "success": True,
                    "message": "Builder subscription updated successfully.",
                    "data": result.data,
                }

            result = (
                service_supabase
                .table("features")
                .insert(payload)
                .execute()
            )

            return {
                "success": True,
                "message": "Builder subscription saved successfully.",
                "data": result.data,
            }

        raise HTTPException(
            status_code=400,
            detail="Invalid subscription type.",
        )

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save subscription feature: {str(error)}",
        )