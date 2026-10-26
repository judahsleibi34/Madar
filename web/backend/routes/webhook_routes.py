"""Unauthenticated machine ingress; verification replaces browser authentication."""

from fastapi import APIRouter, HTTPException, Request, Response

from services import webhook_ingestion_service
from services.webhook_registry import MAX_WEBHOOK_BODY_BYTES, MAX_WEBHOOK_HEADER_BYTES


router = APIRouter(prefix="/data/webhooks", tags=["Data source webhooks"])


@router.post("/{endpoint_id}", status_code=202)
async def receive_data_source_webhook(endpoint_id: str, request: Request, response: Response):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail={"code": "unsupported_media_type"})
    if sum(len(key) + len(value) for key, value in request.headers.items()) > MAX_WEBHOOK_HEADER_BYTES:
        raise HTTPException(status_code=431, detail={"code": "request_headers_too_large"})
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_WEBHOOK_BODY_BYTES):
        raise HTTPException(status_code=413, detail={"code": "webhook_payload_too_large"})
    raw_body = await request.body()
    if not raw_body or len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail={"code": "webhook_payload_too_large"})
    try:
        result = webhook_ingestion_service.receive(
            endpoint_id=endpoint_id, raw_body=raw_body, headers=dict(request.headers),
        )
    except webhook_ingestion_service.WebhookIngestionError as error:
        # Deliberately omit scope, provider, credential and payload details.
        raise HTTPException(status_code=error.status_code, detail={"code": error.code}) from error
    if result.get("disposition") == "duplicate":
        response.status_code = 200
    return {"accepted": True, "disposition": result.get("disposition"),
            "event_id": result.get("event_id")}
