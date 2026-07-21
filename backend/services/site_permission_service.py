from __future__ import annotations

import re
from typing import Any

from database import service_supabase

CAPABILITIES = frozenset({
    "view_protected_page",
    "submit_protected_form",
    "make_reservation",
})
ROLE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,160}$")
CAPABILITY_PERMISSION_KEYS = {
    "view_protected_page": "viewProtectedPages",
    "submit_protected_form": "submitForms",
    "make_reservation": "makeReservations",
}
RESOURCE_ACCESS_KEYS = {
    "page": "pageIds",
    "form": "formIds",
    "reservation": "reservationBlockIds",
}


def _project_schema(project: dict[str, Any]) -> dict[str, Any]:
    schema = project.get("published_schema") or project.get("draft_schema") or {}
    return schema if isinstance(schema, dict) else {}


def project_role_keys(project: dict[str, Any]) -> set[str]:
    keys = {
        str(role.get("id") or "").strip()
        for role in (_project_schema(project).get("roles") or [])
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


def get_project_role(*, membership: dict[str, Any], project_id: str, client=None) -> dict[str, Any] | None:
    if str(membership.get("status") or "").lower() != "active":
        return None
    if membership.get("_access_kind") == "staff":
        return {"role_key": "staff", "capabilities": list(CAPABILITIES), "_staff": True}
    membership_id = membership.get("id")
    if membership_id is None:
        return None
    database_client = client or service_supabase
    assignments = getattr(
        database_client.table("tenant_site_project_role_assignments")
        .select("role_id")
        .eq("membership_id", int(membership_id))
        .eq("project_id", project_id)
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    if not assignments:
        return None
    roles = getattr(
        database_client.table("tenant_site_project_roles")
        .select("role_key,capabilities,deleted_at")
        .eq("id", assignments[0]["role_id"])
        .eq("project_id", project_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    return roles[0] if roles else None


def _schema_role(project: dict[str, Any] | None, role_key: str) -> dict[str, Any] | None:
    if not project:
        return None
    return next(
        (
            role
            for role in (_project_schema(project).get("roles") or [])
            if isinstance(role, dict) and str(role.get("id") or "") == role_key
        ),
        None,
    )


def resource_is_role_restricted(*, project: dict[str, Any], resource_type: str, resource_id: str) -> bool:
    access_key = RESOURCE_ACCESS_KEYS.get(resource_type)
    if not access_key or not resource_id:
        return False
    for role in (_project_schema(project).get("roles") or []):
        if not isinstance(role, dict):
            continue
        values = (role.get("resourceAccess") or {}).get(access_key)
        if isinstance(values, list) and resource_id in {str(value) for value in values}:
            return True
    return False


def has_project_permission(
    *,
    membership: dict[str, Any],
    project_id: str,
    capability: str,
    client=None,
    project: dict[str, Any] | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> bool:
    if capability not in CAPABILITIES:
        return False
    role = get_project_role(
        membership=membership,
        project_id=project_id,
        client=client,
    )
    if not role:
        return False
    if role.get("_staff"):
        return True
    if capability not in (role.get("capabilities") or []):
        return False

    configured_role = _schema_role(project, str(role.get("role_key") or ""))
    permission_key = CAPABILITY_PERMISSION_KEYS[capability]
    permissions = (configured_role or {}).get("permissions") or {}
    if permission_key in permissions and not bool(permissions.get(permission_key)):
        return False

    access_key = RESOURCE_ACCESS_KEYS.get(str(resource_type or ""))
    clean_resource_id = str(resource_id or "")
    if not access_key or not clean_resource_id or not project:
        return True
    role_access = (configured_role or {}).get("resourceAccess") or {}
    allowed = role_access.get(access_key) or []
    if resource_type == "page" and access_key in role_access:
        return clean_resource_id in {str(value) for value in allowed}
    if not resource_is_role_restricted(
        project=project,
        resource_type=str(resource_type),
        resource_id=clean_resource_id,
    ):
        return True
    return clean_resource_id in {str(value) for value in allowed}