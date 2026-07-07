from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from services.auth_service import get_authenticated_user_row
from services.notification_service import (
    get_web_push_public_config,
    list_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    revoke_web_push_subscription,
    upsert_web_push_subscription,
)


router = APIRouter(prefix="/notifications", tags=["Notifications"])


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=1)
    auth: str = Field(..., min_length=1)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2000)
    keys: PushSubscriptionKeys


class PushSubscriptionDeleteRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2000)


def _current_user(request: Request, response: Response):
    _, user = get_authenticated_user_row(
        request,
        response,
        allow_admin_account_access=False,
    )
    return user


@router.get("")
def list_notifications(
    request: Request,
    response: Response,
    limit: int = Query(default=30, ge=1, le=100),
    unread_only: bool = Query(default=False),
):
    user = _current_user(request, response)
    return {
        "success": True,
        **list_user_notifications(
            user_id=user["id"],
            limit=limit,
            unread_only=unread_only,
        ),
    }


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, request: Request, response: Response):
    user = _current_user(request, response)
    notification = mark_notification_read(
        user_id=user["id"],
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
    user = _current_user(request, response)
    count = mark_all_notifications_read(user_id=user["id"])
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
    user = _current_user(request, response)
    saved = upsert_web_push_subscription(
        user_id=user["id"],
        tenant_id=user.get("tenant_id"),
        endpoint=subscription.endpoint,
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
    user = _current_user(request, response)
    revoked_count = revoke_web_push_subscription(
        user_id=user["id"],
        endpoint=subscription.endpoint,
    )
    return {
        "success": True,
        "revoked_count": revoked_count,
    }
