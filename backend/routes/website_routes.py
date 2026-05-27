from fastapi import APIRouter, HTTPException, Response, Request
from database import supabase
from classes import WebsiteSettingsUpdate
from services.auth_service import get_authenticated_user_row

router = APIRouter(prefix="/website", tags=["Website"])


@router.put("/settings")
def update_website_settings(
    settings: WebsiteSettingsUpdate,
    request: Request,
    response: Response,
):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        update_payload = {}

        if settings.subdomain is not None:
            update_payload["subdomain"] = settings.subdomain.strip()
        if settings.brand is not None:
            update_payload["brand"] = settings.brand.strip()
        if settings.footer_store_name is not None:
            update_payload["footer_store_name"] = settings.footer_store_name.strip()
        if settings.logo_url is not None:
            update_payload["logo_url"] = settings.logo_url.strip()
        if settings.contact_email is not None:
            update_payload["contact_email"] = str(settings.contact_email).strip().lower()
        if settings.phone is not None:
            update_payload["phone"] = settings.phone.strip()
        if settings.description is not None:
            update_payload["description"] = settings.description.strip()

        if not update_payload:
            return {
                "success": True,
                "website": None,
            }

        update_payload["user_id"] = user_data["id"]

        save_response = supabase.table("website_settings").upsert(
            update_payload,
            on_conflict="user_id",
        ).execute()

        updated_website = save_response.data[0] if save_response.data else update_payload

        return {
            "success": True,
            "message": "Website settings updated",
            "website": updated_website,
        }

    except HTTPException:
        raise
    except Exception as e:
        print("WEBSITE SETTINGS UPDATE ERROR:", repr(e))
        raise HTTPException(status_code=500, detail="Could not update website settings")


@router.get("/settings")
def get_website_settings(request: Request, response: Response):
    try:
        _, user_data = get_authenticated_user_row(request, response)

        website_response = supabase.table("website_settings").select("*").eq(
            "user_id", user_data["id"]
        ).maybe_single().execute()

        return {
            "success": True,
            "website": website_response.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        print("WEBSITE SETTINGS FETCH ERROR:", repr(e))
        raise HTTPException(status_code=500, detail="Could not fetch website settings")