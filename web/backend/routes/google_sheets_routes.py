"""Fixed Google Sheets OAuth callback; no provider data is accepted here."""

from __future__ import annotations

import os
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from database import service_supabase
from services import data_source_credential_service, project_data_source_service
from services.google_sheets_connector import (
    PROVIDER_KEY, GoogleSheetsError, consume_oauth_transaction, credential_payload,
    exchange_authorization_code, google_sheets_config,
)
from services.tenant_service import require_active_tenant_user_id


router = APIRouter(prefix="/data/oauth/google-sheets", tags=["Data"])


def _frontend_result(project_id: str, result: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
        base = "http://localhost:5173"
    return f"{base}/data-sources/projects/{project_id}/data?" + urlencode({
        "google_sheets": result,
    })


@router.get("/callback")
def google_sheets_oauth_callback(
    request: Request,
    response: Response,
    state: str = Query(min_length=1, max_length=512),
    code: str | None = Query(default=None, min_length=1, max_length=4096),
    error: str | None = Query(default=None, max_length=120),
):
    transaction = None
    try:
        transaction = consume_oauth_transaction(state, client=service_supabase)
        actor = int(transaction["actor_user_id"])
        context = require_active_tenant_user_id(actor, request, response)
        if int(context.tenant_id) != int(transaction["tenant_id"]):
            raise GoogleSheetsError("google_sheets_oauth_scope_mismatch")
        project_id = str(transaction["project_id"])
        source_id = str(transaction["source_id"])
        source = project_data_source_service.get_project_data_source(
            tenant_id=int(context.tenant_id), project_id=project_id,
            source_id=source_id, user_id=actor, client=service_supabase,
        )
        if source.get("provider_key") != PROVIDER_KEY:
            raise GoogleSheetsError("google_sheets_oauth_scope_mismatch")
        if error is not None:
            return RedirectResponse(_frontend_result(project_id, "denied"), status_code=303)
        if not code:
            raise GoogleSheetsError("google_sheets_authorization_invalid")
        pkce = data_source_credential_service.resolve_persistent_credential(
            tenant_id=int(context.tenant_id), project_id=project_id, source_id=source_id,
            user_id=actor, provider_key=PROVIDER_KEY, credential_type="oauth_pkce",
            client=service_supabase,
        )
        token = exchange_authorization_code(
            google_sheets_config(), code, pkce.secret.reveal_for_request(),
        )
        data_source_credential_service.provision_credential(
            tenant_id=int(context.tenant_id), project_id=project_id, source_id=source_id,
            user_id=actor, provider_key=PROVIDER_KEY, credential_type="oauth_refresh",
            secret=credential_payload(token), client=service_supabase,
        )
        return RedirectResponse(_frontend_result(project_id, "connected"), status_code=303)
    except HTTPException:
        raise
    except Exception as exc:
        project_id = str((transaction or {}).get("project_id") or "")
        if project_id:
            return RedirectResponse(_frontend_result(project_id, "failed"), status_code=303)
        code_value = getattr(exc, "code", "google_sheets_oauth_failed")
        raise HTTPException(status_code=400, detail={
            "code": code_value,
            "message": "Google Sheets authorization could not be completed.",
        }) from exc
