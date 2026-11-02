"""Tenant-bound dashboard and immutable report sharing for candidate schema 165."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services import project_dataset_service


BI_SHARING_SCHEMA = 165
DASHBOARD_PERMISSIONS = {"viewer", "editor"}
REPORT_PERMISSIONS = {"viewer"}
MAX_SHARES_PER_RESOURCE = 100


def _report_fields(*, client, include_storage: bool = False, summary: bool = False) -> str:
    if include_storage:
        return "*"
    if summary:
        fields = (
            "id,dashboard_id,schedule_id,dashboard_revision,trigger_type,status,version_vector,warnings,"
            "error_code,artifact_filename,artifact_size_bytes,created_at,completed_at"
        )
    else:
        fields = (
            "id,dashboard_id,schedule_id,dashboard_revision,trigger_type,due_slot,status,definition_snapshot,"
            "version_vector,result_snapshot,warnings,error_code,artifact_filename,artifact_size_bytes,"
            "artifact_sha256,created_at,started_at,completed_at,attempts,max_attempts,creator_user_id"
        )
    if project_dataset_service.schema_version(client=client) >= 166:
        fields += ",artifact_deleted_at"
    return fields


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def sharing_available(*, client=None) -> bool:
    return project_dataset_service.schema_version(client=client) >= BI_SHARING_SCHEMA


def require_sharing_schema(*, client=None) -> None:
    if not sharing_available(client=client):
        raise HTTPException(status_code=503, detail={
            "code": "bi_sharing_upgrade_required",
            "message": "Team dashboard sharing requires the database upgrade.",
        })


def _access(permission: str, *, owner_user_id: int, actor_user_id: int) -> dict[str, Any]:
    is_owner = int(owner_user_id) == int(actor_user_id)
    return {"is_owner": is_owner, "permission": "owner" if is_owner else permission,
            "can_edit": is_owner or permission == "editor", "can_share": is_owner}


def require_dashboard_access(*, tenant_id: int, project_id: str, user_id: int,
                             dashboard_id: str, minimum: str = "viewer", owner_only: bool = False,
                             client=None) -> dict[str, Any]:
    database = client or service_supabase
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    safe_project = project_dataset_service._safe_uuid(project_id)
    safe_dashboard = project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found.")
    owned = _rows(database.table("bi_dashboards").select("*")
        .eq("id", safe_dashboard).eq("tenant_id", tenant_id).eq("project_id", safe_project)
        .eq("creator_user_id", user_id).limit(1).execute())
    if owned:
        return {"resource": owned[0], "access": _access("owner", owner_user_id=user_id, actor_user_id=user_id)}
    if owner_only or not sharing_available(client=database):
        raise HTTPException(status_code=404, detail="Dashboard was not found.")
    shares = _rows(database.table("bi_dashboard_shares")
        .select("owner_user_id,permission,revision")
        .eq("dashboard_id", safe_dashboard).eq("tenant_id", tenant_id).eq("project_id", safe_project)
        .eq("member_user_id", user_id).limit(1).execute())
    if not shares or minimum == "editor" and shares[0].get("permission") != "editor":
        raise HTTPException(status_code=404, detail="Dashboard was not found.")
    owner_id = int(shares[0]["owner_user_id"])
    resources = _rows(database.table("bi_dashboards").select("*")
        .eq("id", safe_dashboard).eq("tenant_id", tenant_id).eq("project_id", safe_project)
        .eq("creator_user_id", owner_id).limit(1).execute())
    if not resources:
        raise HTTPException(status_code=404, detail="Dashboard was not found.")
    return {"resource": resources[0],
            "access": _access(str(shares[0]["permission"]), owner_user_id=owner_id, actor_user_id=user_id)}


def require_report_access(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
                          owner_only: bool = False, include_storage: bool = False, client=None) -> dict[str, Any]:
    database = client or service_supabase
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    safe_project = project_dataset_service._safe_uuid(project_id)
    safe_report = project_dataset_service._safe_uuid(report_id, detail="Report was not found.")
    fields = _report_fields(client=database, include_storage=include_storage)
    owned = _rows(database.table("bi_report_runs").select(fields)
        .eq("id", safe_report).eq("tenant_id", tenant_id).eq("project_id", safe_project)
        .eq("creator_user_id", user_id).is_("archived_at", "null").limit(1).execute())
    if owned:
        owned[0].setdefault("artifact_deleted_at", None)
        return {"resource": owned[0], "access": _access("owner", owner_user_id=user_id, actor_user_id=user_id)}
    if owner_only or not sharing_available(client=database):
        raise HTTPException(status_code=404, detail="Report was not found.")
    shares = _rows(database.table("bi_report_shares").select("owner_user_id,permission,revision")
        .eq("report_id", safe_report).eq("tenant_id", tenant_id).eq("project_id", safe_project)
        .eq("member_user_id", user_id).limit(1).execute())
    if not shares:
        raise HTTPException(status_code=404, detail="Report was not found.")
    owner_id = int(shares[0]["owner_user_id"])
    resources = _rows(database.table("bi_report_runs").select(fields)
        .eq("id", safe_report).eq("tenant_id", tenant_id).eq("project_id", safe_project)
        .eq("creator_user_id", owner_id).is_("archived_at", "null").limit(1).execute())
    if not resources:
        raise HTTPException(status_code=404, detail="Report was not found.")
    resources[0].setdefault("artifact_deleted_at", None)
    return {"resource": resources[0],
            "access": _access("viewer", owner_user_id=owner_id, actor_user_id=user_id)}


def _member_directory(*, tenant_id: int, owner_user_id: int, client) -> list[dict[str, Any]]:
    memberships = _rows(client.table("tenant_memberships").select("user_id,role")
        .eq("tenant_id", tenant_id).eq("status", "active").neq("user_id", owner_user_id)
        .limit(MAX_SHARES_PER_RESOURCE + 1).execute())[:MAX_SHARES_PER_RESOURCE]
    member_by_id = {int(row["user_id"]): row for row in memberships}
    if not member_by_id:
        return []
    users = _rows(client.table("users").select("id,first_name,last_name,email")
        .eq("tenant_id", tenant_id).eq("account_status", "active")
        .in_("id", list(member_by_id)).execute())
    return [{**user, "tenant_role": member_by_id[int(user["id"])].get("role")} for user in users]


def _enrich_shares(shares: list[dict[str, Any]], members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {int(member["id"]): member for member in members}
    return [{**share, "member": by_id.get(int(share["member_user_id"]), {
        "id": share["member_user_id"], "first_name": "", "last_name": "", "email": "",
    })} for share in shares]


def list_dashboard_shares(*, tenant_id: int, project_id: str, user_id: int,
                          dashboard_id: str, client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_sharing_schema(client=database)
    context = require_dashboard_access(tenant_id=tenant_id, project_id=project_id, user_id=user_id,
                                       dashboard_id=dashboard_id, owner_only=True, client=database)
    members = _member_directory(tenant_id=tenant_id, owner_user_id=user_id, client=database)
    shares = _rows(database.table("bi_dashboard_shares").select("id,member_user_id,permission,revision,updated_at")
        .eq("dashboard_id", context["resource"]["id"]).eq("tenant_id", tenant_id)
        .eq("project_id", project_dataset_service._safe_uuid(project_id)).eq("owner_user_id", user_id)
        .order("updated_at", desc=True).limit(MAX_SHARES_PER_RESOURCE).execute())
    return {"items": _enrich_shares(shares, members), "members": members}


def list_report_shares(*, tenant_id: int, project_id: str, user_id: int,
                       report_id: str, client=None) -> dict[str, Any]:
    database = client or service_supabase
    require_sharing_schema(client=database)
    context = require_report_access(tenant_id=tenant_id, project_id=project_id, user_id=user_id,
                                    report_id=report_id, owner_only=True, client=database)
    members = _member_directory(tenant_id=tenant_id, owner_user_id=user_id, client=database)
    shares = _rows(database.table("bi_report_shares").select("id,member_user_id,permission,revision,updated_at")
        .eq("report_id", context["resource"]["id"]).eq("tenant_id", tenant_id)
        .eq("project_id", project_dataset_service._safe_uuid(project_id)).eq("owner_user_id", user_id)
        .order("updated_at", desc=True).limit(MAX_SHARES_PER_RESOURCE).execute())
    return {"items": _enrich_shares(shares, members), "members": members}


def _rpc_result(name: str, params: dict[str, Any], *, client) -> Any:
    try:
        data = getattr(client.rpc(name, params).execute(), "data", None)
    except Exception as error:
        message = str(error).lower()
        if "revision_conflict" in message or "40001" in message:
            raise HTTPException(status_code=409, detail={"code": "share_revision_conflict",
                "message": "Sharing changed in another session. Reload and try again."}) from error
        if "forbidden" in message:
            raise HTTPException(status_code=422, detail="Choose an active member of this workspace.") from error
        if "not_found" in message:
            raise HTTPException(status_code=404, detail="Shared resource was not found.") from error
        raise
    if data in (None, False, []):
        raise RuntimeError("Sharing operation returned no result")
    return data[0] if isinstance(data, list) and len(data) == 1 else data


def set_dashboard_share(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                        expected_revision: int, member_user_id: int, permission: str, client=None) -> dict:
    database = client or service_supabase
    require_sharing_schema(client=database)
    permission = str(permission or "").lower()
    if permission not in DASHBOARD_PERMISSIONS:
        raise HTTPException(status_code=422, detail="Dashboard share permission is invalid.")
    return _rpc_result("set_bi_dashboard_share165", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_owner_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_expected_dashboard_revision": expected_revision, "p_member_user_id": int(member_user_id),
        "p_permission": permission,
    }, client=database)


def revoke_dashboard_share(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                           expected_revision: int, member_user_id: int, client=None) -> dict:
    database = client or service_supabase
    require_sharing_schema(client=database)
    return _rpc_result("revoke_bi_dashboard_share165", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_owner_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_expected_dashboard_revision": expected_revision, "p_member_user_id": int(member_user_id),
    }, client=database)


def set_report_share(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
                     member_user_id: int, expected_share_revision: int | None = None, client=None) -> dict:
    database = client or service_supabase
    require_sharing_schema(client=database)
    return _rpc_result("set_bi_report_share165", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_owner_user_id": user_id,
        "p_report_id": project_dataset_service._safe_uuid(report_id, detail="Report was not found."),
        "p_member_user_id": int(member_user_id), "p_expected_share_revision": expected_share_revision,
    }, client=database)


def revoke_report_share(*, tenant_id: int, project_id: str, user_id: int, report_id: str,
                        member_user_id: int, expected_share_revision: int, client=None) -> bool:
    database = client or service_supabase
    require_sharing_schema(client=database)
    return bool(_rpc_result("revoke_bi_report_share165", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_owner_user_id": user_id,
        "p_report_id": project_dataset_service._safe_uuid(report_id, detail="Report was not found."),
        "p_member_user_id": int(member_user_id), "p_expected_share_revision": expected_share_revision,
    }, client=database))


def list_shared_dashboards(*, tenant_id: int, project_id: str, user_id: int, client=None) -> dict:
    database = client or service_supabase
    if not sharing_available(client=database):
        return {"available": False, "items": []}
    safe_project = project_dataset_service._safe_uuid(project_id)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    shares = _rows(database.table("bi_dashboard_shares").select("dashboard_id,owner_user_id,permission")
        .eq("tenant_id", tenant_id).eq("project_id", safe_project).eq("member_user_id", user_id)
        .order("updated_at", desc=True).limit(MAX_SHARES_PER_RESOURCE).execute())
    resources = []
    for share in shares:
        rows = _rows(database.table("bi_dashboards").select("id,project_id,name,description,revision,created_at,updated_at,auto_refresh_enabled")
            .eq("id", share["dashboard_id"]).eq("tenant_id", tenant_id).eq("project_id", safe_project)
            .eq("creator_user_id", share["owner_user_id"]).limit(1).execute())
        if rows:
            resources.append({**rows[0], "access": _access(str(share["permission"]),
                owner_user_id=int(share["owner_user_id"]), actor_user_id=user_id)})
    return {"available": True, "items": resources}


def list_shared_reports(*, tenant_id: int, project_id: str, user_id: int, client=None) -> dict:
    database = client or service_supabase
    if not sharing_available(client=database):
        return {"available": False, "items": []}
    safe_project = project_dataset_service._safe_uuid(project_id)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    shares = _rows(database.table("bi_report_shares").select("report_id,owner_user_id")
        .eq("tenant_id", tenant_id).eq("project_id", safe_project).eq("member_user_id", user_id)
        .order("updated_at", desc=True).limit(MAX_SHARES_PER_RESOURCE).execute())
    resources = []
    fields = _report_fields(client=database, summary=True)
    for share in shares:
        rows = _rows(database.table("bi_report_runs")
            .select(fields)
            .eq("id", share["report_id"]).eq("tenant_id", tenant_id).eq("project_id", safe_project)
            .eq("creator_user_id", share["owner_user_id"]).is_("archived_at", "null").limit(1).execute())
        if rows:
            rows[0].setdefault("artifact_deleted_at", None)
            resources.append({**rows[0], "access": _access("viewer",
                owner_user_id=int(share["owner_user_id"]), actor_user_id=user_id)})
    return {"available": True, "items": resources}
