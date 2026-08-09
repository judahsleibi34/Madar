from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from services.push_subscription_security import UnsafePushEndpoint, validate_push_endpoint
from services.tenant_service import get_current_tenant_context
from services.notification_service import (
    get_web_push_public_config,
    list_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    revoke_web_push_subscription,
    upsert_web_push_subscription,
)


router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=80, max_length=128, pattern=r"^[A-Za-z0-9_-]+={0,2}$")
    auth: str = Field(..., min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+={0,2}$")


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2000)
    keys: PushSubscriptionKeys


class PushSubscriptionDeleteRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2000)


def _current_context(request: Request, response: Response):
    return get_current_tenant_context(
        request,
        response,
        allow_admin_account_access=False,
    )


@router.get("")
def list_notifications(
    request: Request,
    response: Response,
    limit: int = Query(default=30, ge=1, le=100),
    unread_only: bool = Query(default=False),
):
    context = _current_context(request, response)
    return {
        "success": True,
        **list_user_notifications(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            limit=limit,
            unread_only=unread_only,
        ),
    }


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, request: Request, response: Response):
    context = _current_context(request, response)
    notification = mark_notification_read(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        notification_id=notification_id,
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {
        "success": True,
        "notification": notification,
    }


@router.post("/read-all")
def mark_all_read(request: Request, response: Response):
    context = _current_context(request, response)
    count = mark_all_notifications_read(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )
    return {
        "success": True,
        "updated_count": count,
    }


@router.get("/push-public-key")
def get_push_public_key():
    return {
        "success": True,
        **get_web_push_public_config(),
    }


@router.post("/push-subscriptions")
def save_push_subscription(
    subscription: PushSubscriptionRequest,
    request: Request,
    response: Response,
):
    context = _current_context(request, response)
    try:
        endpoint = validate_push_endpoint(subscription.endpoint)
    except UnsafePushEndpoint as error:
        logger.warning(
            "notifications.push_subscription_rejected",
            extra={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "error_code": str(error),
            },
        )
        raise HTTPException(status_code=400, detail=str(error)) from error
    saved = upsert_web_push_subscription(
        user_id=context.user_id,
        tenant_id=context.tenant_id,
        endpoint=endpoint,
        p256dh=subscription.keys.p256dh,
        auth=subscription.keys.auth,
        user_agent=request.headers.get("user-agent", ""),
    )
    return {
        "success": True,
        "subscription": {
            "id": saved.get("id"),
            "endpoint": saved.get("endpoint"),
        },
    }


@router.delete("/push-subscriptions")
def delete_push_subscription(
    subscription: PushSubscriptionDeleteRequest,
    request: Request,
    response: Response,
):
    context = _current_context(request, response)
    revoked_count = revoke_web_push_subscription(
        user_id=context.user_id,
        endpoint=subscription.endpoint,
    )
    return {
        "success": True,
        "revoked_count": revoked_count,
    }
