from __future__ import annotations

import re
from typing import Any

from database import service_supabase

CAPABILITIES = frozenset({"view_protected_page", "submit_protected_form", "make_reservation"})
ROLE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,160}$")


def project_role_keys(project: dict[str, Any]) -> set[str]:
    schema = project.get("draft_schema") or project.get("published_schema") or {}
    keys = {
        str(role.get("id") or "").strip()
        for role in (schema.get("roles") or [])
        if isinstance(role, dict) and ROLE_KEY_PATTERN.fullmatch(str(role.get("id") or "").strip())
    }
    keys.add("customer")
    return keys


def assign_project_role(*, membership_id: int, tenant_id: int, project: dict[str, Any], role_key: str, actor_user_id: int | None, client=None) -> str:
    clean_role = str(role_key or "customer").strip()
    if not ROLE_KEY_PATTERN.fullmatch(clean_role) or clean_role not in project_role_keys(project):
        raise ValueError("project_role_invalid")
    database_client = client or service_supabase
    response = database_client.rpc("assign_tenant_site_project_role", {
        "target_membership_id": int(membership_id),
        "target_tenant_id": int(tenant_id),
        "target_project_id": project["id"],
        "target_role_key": clean_role,
        "actor_user_id": actor_user_id,
    }).execute()
    if getattr(response, "data", None) is None:
        raise RuntimeError("project_role_assignment_failed")
    return clean_role


def has_project_permission(*, membership: dict[str, Any], project_id: str, capability: str, client=None) -> bool:
    if capability not in CAPABILITIES or str(membership.get("status") or "").lower() != "active":
        return False
    if membership.get("_access_kind") == "staff":
        return True
    membership_id = membership.get("id")
    if membership_id is None:
        return False
    database_client = client or service_supabase
    assignments = getattr(database_client.table("tenant_site_project_role_assignments").select("role_id").eq("membership_id", int(membership_id)).eq("project_id", project_id).limit(1).execute(), "data", None) or []
    if not assignments:
        return False
    roles = getattr(database_client.table("tenant_site_project_roles").select("capabilities,deleted_at").eq("id", assignments[0]["role_id"]).eq("project_id", project_id).is_("deleted_at", "null").limit(1).execute(), "data", None) or []
    return bool(roles and capability in (roles[0].get("capabilities") or []))
