import logging

from fastapi import APIRouter, HTTPException, Request

from classes import ContactMessage
from database import service_supabase
from services.rate_limit_service import enforce_public_contact_rate_limit, get_client_ip


router = APIRouter(prefix="/public", tags=["public-contact"])
logger = logging.getLogger(__name__)


def clean_contact_payload(payload: ContactMessage) -> dict:
    name = payload.name.strip()
    phone = payload.phone.strip() if payload.phone else None
    message = payload.message.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    if phone == "":
        phone = None

    return {
        "name": name,
        "phone": phone,
        "message": message,
    }


@router.post("/contact")
def submit_public_contact(payload: ContactMessage, request: Request):
    client_ip = get_client_ip(request)

    try:
        enforce_public_contact_rate_limit(request, identifier=client_ip)
        contact_payload = clean_contact_payload(payload)

    except HTTPException as error:
        logger.info(
            "contact.message_rejected",
            extra={
                "client_ip": client_ip,
                "status_code": error.status_code,
                "reason": str(error.detail),
            },
        )
        raise

    try:
        service_supabase.table("contacts").insert(contact_payload).execute()

    except Exception as error:
        logger.warning(
            "contact.message_failed",
            extra={"client_ip": client_ip, "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=500, detail="Could not submit contact message")

    logger.info(
        "contact.message_received",
        extra={
            "client_ip": client_ip,
            "has_phone": bool(contact_payload.get("phone")),
            "message_length": len(contact_payload.get("message") or ""),
        },
    )

    return {
        "success": True,
        "message": "Contact message received",
    }
