"""Authorized persistent BI dashboards backed by candidate schema 163."""
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from data_analysis import services as data_services
from database import service_supabase
from services import project_dataset_service
from services import versioned_analytics_service


BI_DASHBOARDS_SCHEMA = 163
WIDGET_TYPES = {"kpi", "table", "bar", "line"}
VERSION_POLICIES = {"pinned", "latest_committed"}
METRIC_OPERATIONS = {"count", "sum", "mean", "min", "max", "distinct_count", "date_aggregate"}
METRIC_KEYS = {
    "operation", "label", "value_column", "group_column", "date_column",
    "aggregation", "period", "timezone",
}


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return [] if data is None else [data]


def dashboards_available(*, client=None) -> bool:
    return project_dataset_service.schema_version(client=client) >= BI_DASHBOARDS_SCHEMA


def require_dashboard_schema(*, client=None) -> None:
    if not dashboards_available(client=client):
        raise HTTPException(status_code=503, detail={
            "code": "bi_dashboards_upgrade_required",
            "message": "Persistent Business Intelligence dashboards require the database upgrade.",
        })


def _name(value: object, *, maximum: int = 120, field: str = "Dashboard name") -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > maximum:
        raise HTTPException(status_code=422, detail=f"{field} must be between 1 and {maximum} characters.")
    return normalized


def _description(value: object) -> str:
    normalized = str(value or "")
    if len(normalized) > 1000:
        raise HTTPException(status_code=422, detail="Dashboard description must not exceed 1000 characters.")
    return normalized


def validate_analysis_spec(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - METRIC_KEYS:
        raise HTTPException(status_code=422, detail="Dashboard analysis specification is not supported.")
    operation = str(value.get("operation") or "").strip().lower()
    if operation not in METRIC_OPERATIONS:
        raise HTTPException(status_code=422, detail="Dashboard metric operation is not supported.")
    result: dict[str, Any] = {"operation": operation}
    for key in ("label", "value_column", "group_column", "date_column", "aggregation", "period", "timezone"):
        if value.get(key) is None:
            continue
        item = str(value[key]).strip()
        if not item or len(item) > (160 if key == "label" else 255):
            raise HTTPException(status_code=422, detail="Dashboard metric fields are invalid.")
        result[key] = item
    if operation in {"sum", "mean", "min", "max", "distinct_count"} and not result.get("value_column"):
        raise HTTPException(status_code=422, detail="The selected metric requires a value column.")
    if operation == "date_aggregate":
        if not result.get("date_column"):
            raise HTTPException(status_code=422, detail="Date aggregation requires a date column.")
        if result.get("period", "month") not in {"day", "week", "month"}:
            raise HTTPException(status_code=422, detail="Date aggregation period is not supported.")
        if result.get("aggregation", "count") not in {"count", "sum", "mean", "min", "max"}:
            raise HTTPException(status_code=422, detail="Date aggregation operation is not supported.")
        if result.get("aggregation", "count") != "count" and not result.get("value_column"):
            raise HTTPException(status_code=422, detail="This date aggregation requires a value column.")
        if result.get("timezone", "UTC") != "UTC":
            raise HTTPException(status_code=422, detail="Only UTC date aggregation is currently supported.")
    if len(json.dumps(result).encode("utf-8")) > 8192:
        raise HTTPException(status_code=422, detail="Dashboard analysis specification is too large.")
    return result


def validate_layout(value: object) -> dict[str, int]:
    if value in (None, {}):
        return {"x": 0, "y": 0, "w": 6, "h": 4}
    if not isinstance(value, dict) or set(value) - {"x", "y", "w", "h"}:
        raise HTTPException(status_code=422, detail="Dashboard widget layout is invalid.")
    try:
        result = {key: int(value.get(key, default)) for key, default in {"x": 0, "y": 0, "w": 6, "h": 4}.items()}
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Dashboard widget layout is invalid.") from error
    if not (0 <= result["x"] <= 11 and 0 <= result["y"] <= 1000
            and 1 <= result["w"] <= 12 and 1 <= result["h"] <= 12
            and result["x"] + result["w"] <= 12):
        raise HTTPException(status_code=422, detail="Dashboard widget layout is outside the supported grid.")
    return result


def validate_display_options(value: object) -> dict[str, Any]:
    if value in (None, {}):
        return {"show_table": True}
    if not isinstance(value, dict) or set(value) - {"show_table"} or not isinstance(value.get("show_table", True), bool):
        raise HTTPException(status_code=422, detail="Dashboard widget display options are invalid.")
    return {"show_table": value.get("show_table", True)}


def _rpc(name: str, params: dict[str, Any], *, client=None):
    database = client or service_supabase
    try:
        rows = _rows(database.rpc(name, params).execute())
    except Exception as error:
        message = str(error).lower()
        if "revision_conflict" in message or "40001" in message:
            raise HTTPException(status_code=409, detail={
                "code": "dashboard_revision_conflict",
                "message": "The dashboard changed in another session. Reload and try again.",
            }) from error
        if "not_found" in message:
            raise HTTPException(status_code=404, detail="Dashboard was not found.") from error
        raise
    if not rows:
        raise RuntimeError("Dashboard operation returned no result")
    return rows[0]


def list_dashboards(*, tenant_id: int, project_id: str, user_id: int, limit: int, offset: int, client=None) -> dict:
    database = client or service_supabase
    require_dashboard_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    fields = "id,project_id,name,description,revision,created_at,updated_at"
    if project_dataset_service.schema_version(client=database) >= 164:
        fields += ",auto_refresh_enabled"
    rows = _rows(database.table("bi_dashboards")
        .select(fields)
        .eq("tenant_id", tenant_id).eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).order("updated_at", desc=True)
        .range(offset, offset + limit).execute())
    for row in rows:
        row.setdefault("auto_refresh_enabled", False)
    return {"items": rows[:limit], "pagination": {
        "limit": limit, "offset": offset, "has_more": len(rows) > limit,
    }}


def get_dashboard(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str, client=None) -> dict:
    database = client or service_supabase
    require_dashboard_schema(client=database)
    project_dataset_service.require_data_project(project_id, tenant_id=tenant_id, client=database)
    normalized_dashboard = project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found.")
    dashboards = _rows(database.table("bi_dashboards").select("*")
        .eq("id", normalized_dashboard).eq("tenant_id", tenant_id)
        .eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).limit(1).execute())
    if not dashboards:
        raise HTTPException(status_code=404, detail="Dashboard was not found.")
    widgets = _rows(database.table("bi_dashboard_widgets")
        .select("id,dashboard_id,widget_type,title,dataset_id,dataset_version_id,version_policy,analysis_spec,layout_config,display_options,created_at,updated_at")
        .eq("dashboard_id", normalized_dashboard).eq("tenant_id", tenant_id)
        .eq("project_id", project_dataset_service._safe_uuid(project_id))
        .eq("creator_user_id", user_id).order("created_at").execute())
    return {**dashboards[0], "widgets": widgets}


def create_dashboard(*, tenant_id: int, project_id: str, user_id: int, name: str, description: str, client=None) -> dict:
    require_dashboard_schema(client=client)
    return _rpc("create_bi_dashboard163", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id, "p_name": _name(name), "p_description": _description(description),
    }, client=client)


def update_dashboard(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                     expected_revision: int, name: str, description: str, client=None) -> dict:
    require_dashboard_schema(client=client)
    return _rpc("update_bi_dashboard163", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_expected_revision": expected_revision, "p_name": _name(name),
        "p_description": _description(description),
    }, client=client)


def _widget_params(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                   expected_revision: int, widget_type: str, title: str, dataset_id: str,
                   dataset_version_id: str, version_policy: str, analysis_spec: object,
                   layout_config: object, display_options: object) -> dict:
    normalized_type = str(widget_type or "").strip().lower()
    normalized_policy = str(version_policy or "").strip().lower()
    if normalized_type not in WIDGET_TYPES or normalized_policy not in VERSION_POLICIES:
        raise HTTPException(status_code=422, detail="Dashboard widget type or version policy is unsupported.")
    return {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_expected_revision": expected_revision, "p_widget_type": normalized_type,
        "p_title": _name(title, maximum=160, field="Widget title"),
        "p_dataset_id": project_dataset_service._safe_uuid(dataset_id, detail="Dataset version was not found."),
        "p_dataset_version_id": project_dataset_service._safe_uuid(dataset_version_id, detail="Dataset version was not found."),
        "p_version_policy": normalized_policy, "p_analysis_spec": validate_analysis_spec(analysis_spec),
        "p_layout_config": validate_layout(layout_config),
        "p_display_options": validate_display_options(display_options),
    }


def add_widget(**kwargs) -> dict:
    client = kwargs.pop("client", None)
    require_dashboard_schema(client=client)
    return _rpc("add_bi_dashboard_widget163", _widget_params(**kwargs), client=client)


def update_widget(*, widget_id: str, client=None, **kwargs) -> dict:
    require_dashboard_schema(client=client)
    params = _widget_params(**kwargs)
    params["p_widget_id"] = project_dataset_service._safe_uuid(widget_id, detail="Dashboard widget was not found.")
    return _rpc("update_bi_dashboard_widget163", params, client=client)


def delete_widget(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                  widget_id: str, expected_revision: int, client=None) -> dict:
    require_dashboard_schema(client=client)
    return _rpc("delete_bi_dashboard_widget163", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_widget_id": project_dataset_service._safe_uuid(widget_id, detail="Dashboard widget was not found."),
        "p_expected_revision": expected_revision,
    }, client=client)


def delete_dashboard(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                     expected_revision: int, client=None) -> bool:
    require_dashboard_schema(client=client)
    return bool(_rpc("delete_bi_dashboard163", {
        "p_tenant_id": tenant_id, "p_project_id": project_dataset_service._safe_uuid(project_id),
        "p_creator_user_id": user_id,
        "p_dashboard_id": project_dataset_service._safe_uuid(dashboard_id, detail="Dashboard was not found."),
        "p_expected_revision": expected_revision,
    }, client=client))


def execute_widget(*, tenant_id: int, project_id: str, user_id: int, dashboard_id: str,
                   widget_id: str, refresh_latest: bool, language: str, client=None) -> dict:
    database = client or service_supabase
    dashboard = get_dashboard(
        tenant_id=tenant_id, project_id=project_id, user_id=user_id,
        dashboard_id=dashboard_id, client=database,
    )
    widget = next((item for item in dashboard["widgets"] if item["id"] == widget_id), None)
    if not widget:
        raise HTTPException(status_code=404, detail="Dashboard widget was not found.")
    target_version_id = widget["dataset_version_id"]
    latest_available = False
    if widget["version_policy"] == "latest_committed":
        versions = project_dataset_service.list_project_dataset_versions(
            tenant_id=tenant_id, project_id=project_id, user_id=user_id,
            dataset_id=widget["dataset_id"], limit=1, offset=0, client=database,
        )["items"]
        if versions:
            latest_available = versions[0]["id"] != target_version_id
            if refresh_latest:
                target_version_id = versions[0]["id"]
    persistent = project_dataset_service.resolve_project_dataset_version(
        tenant_id=tenant_id, project_id=project_id, user_id=user_id,
        dataset_id=widget["dataset_id"], version_id=target_version_id, client=database,
    )
    version = persistent["version"]
    metadata = version.get("file_metadata") if isinstance(version.get("file_metadata"), dict) else {}
    if (int(version.get("size_bytes") or 0) > versioned_analytics_service.MAX_EXPLORATION_SOURCE_BYTES
            or isinstance(metadata.get("rows"), int)
            and metadata["rows"] > versioned_analytics_service.MAX_EXPLORATION_ROWS):
        return {
            "status": "needs_attention", "reason": "analysis_limit_exceeded",
            "message": "This dataset version exceeds the bounded dashboard analysis limit.",
            "widget": widget, "latest_available": latest_available,
        }
    try:
        analysis = data_services.run_assisted_analysis(
            input_path=persistent["storage_identifier"], cleaning_actions=[], question=None,
            metric=validate_analysis_spec(widget["analysis_spec"]), language=language,
            symbols={}, tenant_id=str(tenant_id), user_id=str(user_id),
        )
    except (KeyError, TypeError, ValueError) as error:
        return {
            "status": "needs_attention", "reason": "schema_incompatible",
            "message": "The selected operation is incompatible with this dataset version.",
            "widget": widget, "latest_available": latest_available,
        }
    if refresh_latest and target_version_id != widget["dataset_version_id"]:
        mutation = update_widget(
            tenant_id=tenant_id, project_id=project_id, user_id=user_id,
            dashboard_id=dashboard_id, widget_id=widget_id,
            expected_revision=int(dashboard["revision"]), widget_type=widget["widget_type"],
            title=widget["title"], dataset_id=widget["dataset_id"],
            dataset_version_id=target_version_id, version_policy=widget["version_policy"],
            analysis_spec=widget["analysis_spec"], layout_config=widget["layout_config"],
            display_options=widget["display_options"], client=database,
        )
        widget = mutation["widget"]
        dashboard_revision = mutation["dashboard"]["revision"]
    else:
        dashboard_revision = dashboard["revision"]
    return {
        "status": "ready", "widget": widget, "dashboard_revision": dashboard_revision,
        "latest_available": latest_available and not refresh_latest,
        "result": analysis.get("result", analysis),
        "provenance": {
            "project_id": project_id, "dataset_id": widget["dataset_id"],
            "dataset_version_id": version["id"], "version_number": version["version_number"],
            "version_kind": version["version_kind"], "content_hash": version.get("content_hash"),
            "operation": widget["analysis_spec"].get("operation"),
        },
    }
