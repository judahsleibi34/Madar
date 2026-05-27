from fastapi import APIRouter, HTTPException
from classes import ContactMessage
from database import service_supabase

router = APIRouter()

@router.post("/contact")
def create_contact_message(contact: ContactMessage):
    try:
        service_supabase.table("contacts").insert({
            "name": contact.name,
            "email": contact.email,
            "message": contact.message,
        }).execute()

        return {
            "status": "received",
            "message": "Message sent successfully"
        }

    except Exception as e:
        print("CONTACT ERROR:", repr(e))
        raise HTTPException(status_code=400, detail="Could not send message")
