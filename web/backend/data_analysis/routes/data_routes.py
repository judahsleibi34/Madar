import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File, Header, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from data_analysis import services as data_services
from database import service_supabase
from services.rate_limit_service import enforce_data_workspace_rate_limit
from services.tenant_service import require_active_tenant_user_id
from services.entitlement_service import require_entitlement
from services import (
    project_api_ingestion_service,
    automatic_source_sync_service,
    project_data_source_service,
    project_dataset_checkpoint_service,
    project_dataset_service,
    project_source_ingestion_service,
    webhook_ingestion_service,
    versioned_analytics_service,
    bi_dashboard_service,
    bi_reporting_service,
)
from services import data_source_credential_service
from services.provider_credentials import AuthorizedSource


router = APIRouter(
    prefix="/users/{user_id}/data",
    tags=["Data"]
)
logger = logging.getLogger(__name__)

class ReadDataRequest(BaseModel):
    input_path: str


class CreateProjectDataSourceRequest(BaseModel):
    source_type: Literal["spreadsheet_upload", "api_provider"] = "spreadsheet_upload"
    display_name: str = Field(min_length=1, max_length=255)
    provider_key: str | None = Field(default=None, min_length=1, max_length=80)
    resource_type: str | None = Field(default=None, min_length=1, max_length=80)


class UpdateProjectDataSourceRequest(BaseModel):
    status: Literal["active", "archived"]


class CreateDatasetCheckpointRequest(BaseModel):
    dataset_id: str = Field(min_length=36, max_length=36)
    target_revision: int = Field(ge=1)


class ProvisionDataSourceCredentialRequest(BaseModel):
    secret: str = Field(min_length=1, max_length=4096)
    credential_type: Literal["bearer"] = "bearer"
    expires_at: datetime | None = None


class RevokeDataSourceCredentialRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ConfigureAutomaticSyncRequest(BaseModel):
    enabled: bool = False
    interval_seconds: int = Field(default=3600, ge=900, le=604800)
    expected_fence: int | None = Field(default=None, ge=0)


class GoogleSheetsInspectRequest(BaseModel):
    spreadsheet_url: str = Field(min_length=30, max_length=2048)


class GoogleSheetsPreviewRequest(GoogleSheetsInspectRequest):
    sheet_id: int = Field(ge=0)
    header_row: int = Field(default=1, ge=1, le=1000)


class GoogleSheetsMappingRequest(GoogleSheetsPreviewRequest):
    selected_columns: list[str] = Field(min_length=1, max_length=128)
    record_id_column: str = Field(min_length=1, max_length=255)
    expected_revision: int | None = Field(default=None, ge=1)


class ProvisionWebhookRequest(BaseModel):
    enabled: bool = False
    expected_fence: int | None = Field(default=None, ge=1)
    resource_id: str | None = Field(default=None, min_length=36, max_length=36)


class ConfigureWebhookRequest(BaseModel):
    enabled: bool
    expected_fence: int = Field(ge=1)


class RevokeWebhookRequest(BaseModel):
    expected_fence: int = Field(ge=1)


class DatasetExploreFilter(BaseModel):
    field: str = Field(min_length=1, max_length=255)
    operator: Literal["eq", "gte", "lte", "missing", "not_missing"]
    value: Any = None


class DatasetExploreSort(BaseModel):
    field: str = Field(min_length=1, max_length=255)
    direction: Literal["asc", "desc"] = "asc"


class DatasetExploreRequest(BaseModel):
    columns: list[str] = Field(default_factory=list, max_length=64)
    filters: list[DatasetExploreFilter] = Field(default_factory=list, max_length=8)
    sort: list[DatasetExploreSort] = Field(default_factory=list, max_length=2)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class CreateDashboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class UpdateDashboardRequest(CreateDashboardRequest):
    expected_revision: int = Field(ge=1)


class DashboardWidgetRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    widget_type: Literal["kpi", "table", "bar", "line"]
    title: str = Field(min_length=1, max_length=160)
    dataset_id: str = Field(min_length=36, max_length=36)
    dataset_version_id: str = Field(min_length=36, max_length=36)
    version_policy: Literal["pinned", "latest_committed"] = "pinned"
    analysis_spec: dict[str, Any]
    layout_config: dict[str, Any] = Field(default_factory=dict)
    display_options: dict[str, Any] = Field(default_factory=dict)


class DashboardRevisionRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ExecuteDashboardWidgetRequest(BaseModel):
    refresh_latest: bool = False
    language: Literal["en", "ar"] = "en"


class ConfigureDashboardRefreshRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    enabled: bool


class ReportScheduleRequest(BaseModel):
    dashboard_id: str = Field(min_length=36, max_length=36)
    name: str = Field(min_length=1, max_length=120)
    cadence: Literal["daily", "weekly", "monthly"]
    timezone_name: str = Field(alias="timezone", min_length=1, max_length=64)
    local_time_value: str = Field(alias="local_time", min_length=5, max_length=5)
    weekday: int | None = Field(default=None, ge=0, le=6)
    month_day: int | None = Field(default=None, ge=1, le=31)
    enabled: bool = True
    require_ready_checkpoints: bool = False


class UpdateReportScheduleRequest(ReportScheduleRequest):
    expected_revision: int = Field(ge=1)


class ScheduleRevisionRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ManualReportRequest(BaseModel):
    dashboard_id: str = Field(min_length=36, max_length=36)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=160)


def get_storage_scope(
    request: Request,
    response: Response,
    user_id: int,
) -> tuple[str, str]:
    context = require_active_tenant_user_id(user_id, request, response)
    require_entitlement(
        context.tenant_id,
        "data_import",
        message="This plan does not include the data workspace.",
    )

    return (
        data_services.safe_scope_value(context.tenant_id),
        data_services.safe_scope_value(context.user_id),
    )


@router.post("/read")
def read_data(
    user_id: int,
    request: ReadDataRequest,
    fastapi_request: Request,
    response: Response,
):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "read",
            tenant_id=tenant_id,
        )
        return data_services.process_read(
            request.input_path,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.read.failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(
            status_code=400,
            detail="Could not read data file.",
        )


@router.post("/export")
def export_data(
    user_id: int,
    request: ReadDataRequest,
    fastapi_request: Request,
    response: Response,
):
    try:
        tenant_id, scoped_user_id = get_storage_scope(fastapi_request, response, user_id)
        require_entitlement(tenant_id, "data_exports")
        enforce_data_workspace_rate_limit(
            fastapi_request,
            scoped_user_id,
            "data_export",
            tenant_id=tenant_id,
        )
        return data_services.export_dataset(
            request.input_path,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.export.failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(
            status_code=400,
            detail="Could not export data file.",
        )


@router.post("/upload")
async def upload_data(
    user_id: int,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    try:
        tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
        enforce_data_workspace_rate_limit(
            request,
            scoped_user_id,
            "upload",
            tenant_id=tenant_id,
        )
        return await data_services.process_upload(
            file,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("data.upload.failed", extra={"user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(
            status_code=400,
            detail="Could not process uploaded data file.",
        )


@router.post("/projects/{project_id}/datasets/upload", status_code=201)
async def upload_project_dataset(
    user_id: int,
    project_id: str,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request,
        scoped_user_id,
        "upload",
        tenant_id=tenant_id,
    )
    project_dataset_service.require_project_datasets_schema()
    project_dataset_service.require_data_project(
        project_id,
        tenant_id=int(tenant_id),
    )

    def persist_metadata(artifact):
        return project_dataset_service.create_initial_dataset_version(
            tenant_id=int(tenant_id),
            project_id=project_id,
            creator_user_id=int(scoped_user_id),
            display_name=artifact.get("original_filename") or "Dataset",
            artifact=artifact,
        )

    return await data_services.process_upload(
        file,
        tenant_id=tenant_id,
        user_id=scoped_user_id,
        metadata_persister=persist_metadata,
    )


@router.get("/projects/{project_id}/datasets")
def list_project_datasets(
    user_id: int,
    project_id: str,
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    if not project_dataset_service.project_datasets_available():
        return {
            "available": False,
            "items": [],
            "pagination": {"limit": limit, "offset": offset, "has_more": False},
        }
    result = project_dataset_service.list_project_datasets(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(scoped_user_id),
        limit=limit,
        offset=offset,
    )
    return {"available": True, **result}


@router.get("/projects/{project_id}/datasets/{dataset_id}")
def reopen_project_dataset(
    user_id: int,
    project_id: str,
    dataset_id: str,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    project_dataset_service.require_project_datasets_schema()
    persistent = project_dataset_service.reopen_project_dataset(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(scoped_user_id),
        dataset_id=dataset_id,
    )
    loaded = data_services.process_read(
        persistent["storage_identifier"],
        tenant_id=tenant_id,
        user_id=scoped_user_id,
    )
    return {
        **loaded,
        "persistent_dataset_id": persistent["dataset"]["id"],
        "dataset_version_id": persistent["version"]["id"],
        "version_number": persistent["version"]["version_number"],
        "project_id": persistent["dataset"]["project_id"],
        "display_name": persistent["dataset"]["display_name"],
    }


@router.get("/projects/{project_id}/datasets/{dataset_id}/versions")
def list_project_dataset_versions(
    user_id: int, project_id: str, dataset_id: str, request: Request, response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    if not project_dataset_service.project_datasets_available():
        return {"available": False, "items": [], "pagination": {
            "limit": limit, "offset": offset, "has_more": False,
        }}
    result = project_dataset_service.list_project_dataset_versions(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dataset_id=dataset_id, limit=limit, offset=offset,
    )
    return {"available": True, **result}


@router.get("/projects/{project_id}/datasets/{dataset_id}/versions/{version_id}")
def reopen_project_dataset_version(
    user_id: int, project_id: str, dataset_id: str, version_id: str,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    project_dataset_service.require_project_datasets_schema()
    persistent = project_dataset_service.resolve_project_dataset_version(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dataset_id=dataset_id, version_id=version_id,
    )
    loaded = data_services.process_read(
        persistent["storage_identifier"], tenant_id=tenant_id, user_id=scoped_user_id,
    )
    return {
        **loaded,
        "persistent_dataset_id": persistent["dataset"]["id"],
        "dataset_version_id": persistent["version"]["id"],
        "version_number": persistent["version"]["version_number"],
        "version_kind": persistent["version"]["version_kind"],
        "content_hash": persistent["version"].get("content_hash"),
        "project_id": persistent["dataset"]["project_id"],
        "display_name": persistent["dataset"]["display_name"],
    }


@router.post("/projects/{project_id}/datasets/{dataset_id}/versions/{version_id}/explore")
def explore_project_dataset_version(
    user_id: int, project_id: str, dataset_id: str, version_id: str,
    payload: DatasetExploreRequest, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    project_dataset_service.require_project_datasets_schema()
    return versioned_analytics_service.explore_dataset_version(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dataset_id=dataset_id, version_id=version_id,
        columns=payload.columns,
        filters=[item.model_dump() for item in payload.filters],
        sort=[item.model_dump() for item in payload.sort],
        limit=payload.limit, offset=payload.offset,
    )


@router.get("/projects/{project_id}/datasets/{dataset_id}/freshness")
def get_project_dataset_freshness(
    user_id: int, project_id: str, dataset_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    return project_dataset_service.get_project_dataset_freshness(
        tenant_id=int(tenant_id), project_id=project_id,
        user_id=int(scoped_user_id), dataset_id=dataset_id,
    )


@router.get("/projects/{project_id}/dashboards")
def list_bi_dashboards(
    user_id: int, project_id: str, request: Request, response: Response,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    if not bi_dashboard_service.dashboards_available():
        return {"available": False, "items": [], "pagination": {
            "limit": limit, "offset": offset, "has_more": False,
        }}
    return {"available": True, **bi_dashboard_service.list_dashboards(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        limit=limit, offset=offset,
    )}


@router.post("/projects/{project_id}/dashboards", status_code=201)
def create_bi_dashboard(
    user_id: int, project_id: str, payload: CreateDashboardRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_dashboard_service.create_dashboard(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        name=payload.name, description=payload.description,
    )


@router.get("/projects/{project_id}/dashboards/{dashboard_id}")
def get_bi_dashboard(
    user_id: int, project_id: str, dashboard_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    return bi_dashboard_service.get_dashboard(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id,
    )


@router.patch("/projects/{project_id}/dashboards/{dashboard_id}")
def update_bi_dashboard(
    user_id: int, project_id: str, dashboard_id: str, payload: UpdateDashboardRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_dashboard_service.update_dashboard(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, expected_revision=payload.expected_revision,
        name=payload.name, description=payload.description,
    )


@router.delete("/projects/{project_id}/dashboards/{dashboard_id}")
def delete_bi_dashboard(
    user_id: int, project_id: str, dashboard_id: str, payload: DashboardRevisionRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    bi_dashboard_service.delete_dashboard(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, expected_revision=payload.expected_revision,
    )
    return {"deleted": True}


@router.post("/projects/{project_id}/dashboards/{dashboard_id}/widgets", status_code=201)
def add_bi_dashboard_widget(
    user_id: int, project_id: str, dashboard_id: str, payload: DashboardWidgetRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_dashboard_service.add_widget(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, **payload.model_dump(),
    )


@router.patch("/projects/{project_id}/dashboards/{dashboard_id}/widgets/{widget_id}")
def update_bi_dashboard_widget(
    user_id: int, project_id: str, dashboard_id: str, widget_id: str,
    payload: DashboardWidgetRequest, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_dashboard_service.update_widget(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, widget_id=widget_id, **payload.model_dump(),
    )


@router.delete("/projects/{project_id}/dashboards/{dashboard_id}/widgets/{widget_id}")
def delete_bi_dashboard_widget(
    user_id: int, project_id: str, dashboard_id: str, widget_id: str,
    payload: DashboardRevisionRequest, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_dashboard_service.delete_widget(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, widget_id=widget_id,
        expected_revision=payload.expected_revision,
    )


@router.post("/projects/{project_id}/dashboards/{dashboard_id}/widgets/{widget_id}/execute")
def execute_bi_dashboard_widget(
    user_id: int, project_id: str, dashboard_id: str, widget_id: str,
    payload: ExecuteDashboardWidgetRequest, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "analysis_assist", tenant_id=tenant_id)
    require_entitlement(tenant_id, "standard_data_analysis")
    return bi_dashboard_service.execute_widget(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, widget_id=widget_id,
        refresh_latest=payload.refresh_latest, language=payload.language,
    )


@router.patch("/projects/{project_id}/dashboards/{dashboard_id}/automatic-refresh")
def configure_bi_dashboard_automatic_refresh(
    user_id: int, project_id: str, dashboard_id: str,
    payload: ConfigureDashboardRefreshRequest, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_reporting_service.configure_auto_refresh(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=dashboard_id, expected_revision=payload.expected_revision,
        enabled=payload.enabled,
    )


@router.get("/projects/{project_id}/report-schedules")
def list_bi_report_schedules(
    user_id: int, project_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    if not bi_reporting_service.reporting_available():
        return {"available": False, "items": []}
    return {"available": True, **bi_reporting_service.list_schedules(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
    )}


@router.post("/projects/{project_id}/report-schedules", status_code=201)
def create_bi_report_schedule(
    user_id: int, project_id: str, payload: ReportScheduleRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    return bi_reporting_service.create_schedule(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        **payload.model_dump(),
    )


@router.patch("/projects/{project_id}/report-schedules/{schedule_id}")
def update_bi_report_schedule(
    user_id: int, project_id: str, schedule_id: str, payload: UpdateReportScheduleRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    values = payload.model_dump()
    expected_revision = values.pop("expected_revision")
    return bi_reporting_service.update_schedule(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        schedule_id=schedule_id, expected_revision=expected_revision, **values,
    )


@router.delete("/projects/{project_id}/report-schedules/{schedule_id}")
def delete_bi_report_schedule(
    user_id: int, project_id: str, schedule_id: str, payload: ScheduleRevisionRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    bi_reporting_service.delete_schedule(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        schedule_id=schedule_id, expected_revision=payload.expected_revision,
    )
    return {"deleted": True}


@router.post("/projects/{project_id}/reports", status_code=202)
def generate_bi_report(
    user_id: int, project_id: str, payload: ManualReportRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "analysis_assist", tenant_id=tenant_id)
    require_entitlement(tenant_id, "standard_data_analysis")
    return bi_reporting_service.enqueue_report(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        dashboard_id=payload.dashboard_id, trigger_type="manual",
        idempotency_key=payload.idempotency_key,
    )


@router.get("/projects/{project_id}/reports")
def list_bi_reports(
    user_id: int, project_id: str, request: Request, response: Response,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    if not bi_reporting_service.reporting_available():
        return {"available": False, "items": [], "pagination": {"limit": limit, "offset": offset, "has_more": False}}
    return {"available": True, **bi_reporting_service.list_reports(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id),
        limit=limit, offset=offset,
    )}


@router.get("/projects/{project_id}/reports/{report_id}")
def get_bi_report(
    user_id: int, project_id: str, report_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    return bi_reporting_service.get_report(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id), report_id=report_id,
    )


@router.get("/projects/{project_id}/reports/{report_id}/export.csv")
def download_bi_report(
    user_id: int, project_id: str, report_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    path, filename = bi_reporting_service.report_artifact(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id), report_id=report_id,
    )
    return FileResponse(path, media_type="text/csv", filename=filename,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/projects/{project_id}/reports/{report_id}/retry", status_code=202)
def retry_bi_report(
    user_id: int, project_id: str, report_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "analysis_assist", tenant_id=tenant_id)
    require_entitlement(tenant_id, "standard_data_analysis")
    return bi_reporting_service.retry_report(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id), report_id=report_id,
    )


@router.delete("/projects/{project_id}/reports/{report_id}")
def archive_bi_report(
    user_id: int, project_id: str, report_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    bi_reporting_service.archive_report(
        tenant_id=int(tenant_id), project_id=project_id, user_id=int(scoped_user_id), report_id=report_id,
    )
    return {"archived": True}


@router.post("/projects/{project_id}/sources", status_code=201)
def create_project_data_source(
    user_id: int,
    project_id: str,
    payload: CreateProjectDataSourceRequest,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request,
        scoped_user_id,
        "source_write",
        tenant_id=tenant_id,
    )
    project_data_source_service.require_project_data_sources_schema()
    source_options = {}
    if payload.provider_key is not None or payload.resource_type is not None:
        source_options = {
            "provider_key": payload.provider_key,
            "resource_type": payload.resource_type,
        }
    return project_data_source_service.create_project_data_source(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(scoped_user_id),
        source_type=payload.source_type,
        display_name=payload.display_name,
        **source_options,
    )


@router.get("/projects/{project_id}/source-capabilities")
def get_project_data_source_capabilities(
    user_id: int,
    project_id: str,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "read", tenant_id=tenant_id,
    )
    return project_data_source_service.project_data_source_capabilities(
        tenant_id=int(tenant_id), project_id=project_id,
        user_id=int(scoped_user_id),
    )


@router.get("/projects/{project_id}/sources")
def list_project_data_sources(
    user_id: int,
    project_id: str,
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    if not project_data_source_service.project_data_sources_available():
        return {
            "available": False,
            "items": [],
            "pagination": {"limit": limit, "offset": offset, "has_more": False},
        }
    result = project_data_source_service.list_project_data_sources(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(scoped_user_id),
        limit=limit,
        offset=offset,
    )
    return {"available": True, **result}


@router.get("/projects/{project_id}/sources/{source_id}")
def get_project_data_source(
    user_id: int,
    project_id: str,
    source_id: str,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    project_data_source_service.require_project_data_sources_schema()
    return project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(scoped_user_id),
        source_id=source_id,
    )


@router.patch("/projects/{project_id}/sources/{source_id}")
def update_project_data_source(
    user_id: int,
    project_id: str,
    source_id: str,
    payload: UpdateProjectDataSourceRequest,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request,
        scoped_user_id,
        "source_write",
        tenant_id=tenant_id,
    )
    project_data_source_service.require_project_data_sources_schema()
    return project_data_source_service.update_project_data_source_status(
        tenant_id=int(tenant_id),
        project_id=project_id,
        user_id=int(scoped_user_id),
        source_id=source_id,
        status=payload.status,
    )


def _credential_error(error: data_source_credential_service.DataSourceCredentialError) -> HTTPException:
    status = 409 if error.code in {
        "provider_credentials_write_conflict", "provider_credentials_revoked",
    } else 503
    return HTTPException(status_code=status, detail={
        "code": error.code,
        "message": "The provider credential operation could not be completed.",
    })


@router.post("/projects/{project_id}/sources/{source_id}/credentials", status_code=201)
def provision_data_source_credential(
    user_id: int, project_id: str, source_id: str,
    payload: ProvisionDataSourceCredentialRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "source_write", tenant_id=tenant_id,
    )
    source = project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id,
        user_id=int(scoped_user_id), source_id=source_id,
    )
    if source.get("source_type") != project_data_source_service.SOURCE_TYPE_API_PROVIDER:
        raise HTTPException(status_code=409, detail="This source does not use provider credentials.")
    try:
        return data_source_credential_service.provision_credential(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), provider_key=str(source.get("provider_key") or ""),
            credential_type=payload.credential_type, secret=payload.secret,
            expires_at=payload.expires_at.isoformat() if payload.expires_at else None,
        )
    except data_source_credential_service.DataSourceCredentialError as error:
        raise _credential_error(error) from error


@router.get("/projects/{project_id}/sources/{source_id}/credentials")
def list_data_source_credentials(
    user_id: int, project_id: str, source_id: str,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    source = project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id,
        user_id=int(scoped_user_id), source_id=source_id,
    )
    if source.get("source_type") != project_data_source_service.SOURCE_TYPE_API_PROVIDER:
        raise HTTPException(status_code=409, detail="This source does not use provider credentials.")
    try:
        items = data_source_credential_service.list_credential_metadata(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), provider_key=str(source.get("provider_key") or ""),
        )
    except data_source_credential_service.DataSourceCredentialError as error:
        raise _credential_error(error) from error
    return {"items": items}


@router.post("/projects/{project_id}/sources/{source_id}/credentials/revoke")
def revoke_data_source_credential(
    user_id: int, project_id: str, source_id: str,
    payload: RevokeDataSourceCredentialRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "source_write", tenant_id=tenant_id,
    )
    source = project_data_source_service.get_project_data_source(
        tenant_id=int(tenant_id), project_id=project_id,
        user_id=int(scoped_user_id), source_id=source_id,
    )
    try:
        return data_source_credential_service.revoke_credential(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), provider_key=str(source.get("provider_key") or ""),
            expected_revision=payload.expected_revision,
        )
    except data_source_credential_service.DataSourceCredentialError as error:
        raise _credential_error(error) from error


def _google_source_scope(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
) -> AuthorizedSource:
    source = project_data_source_service.get_project_data_source(
        tenant_id=tenant_id, project_id=project_id, source_id=source_id,
        user_id=user_id,
    )
    if source.get("source_type") != project_data_source_service.SOURCE_TYPE_API_PROVIDER \
            or source.get("provider_key") != "google_sheets":
        raise HTTPException(status_code=404, detail="Google Sheets source was not found.")
    return AuthorizedSource(tenant_id, project_id, source_id, "google_sheets", user_id)


def _google_client(scope: AuthorizedSource):
    from services.google_sheets_connector import (
        GoogleSheetsClient, GoogleSheetsError, google_sheets_config, refresh_access_token,
    )
    try:
        resolved = data_source_credential_service.resolve_persistent_credential(
            tenant_id=scope.tenant_id, project_id=scope.project_id,
            source_id=scope.source_id, user_id=int(scope.user_id or 0),
            provider_key="google_sheets", credential_type="oauth_refresh",
        )
        token = refresh_access_token(
            google_sheets_config(), resolved.secret.reveal_for_request(),
        )
        return GoogleSheetsClient(google_sheets_config(), token)
    except (GoogleSheetsError, data_source_credential_service.DataSourceCredentialError) as error:
        raise HTTPException(status_code=401, detail={
            "code": getattr(error, "code", "google_sheets_authorization_invalid"),
            "message": "Reconnect Google Sheets to continue.",
        }) from error


@router.post("/projects/{project_id}/sources/{source_id}/google-sheets/oauth/start")
def start_google_sheets_oauth(
    user_id: int, project_id: str, source_id: str,
    request: Request, response: Response,
):
    from services.google_sheets_connector import GoogleSheetsError, begin_oauth
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "source_write", tenant_id=tenant_id,
    )
    scope = _google_source_scope(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id),
    )
    try:
        return begin_oauth(scope, client=service_supabase)
    except GoogleSheetsError as error:
        raise HTTPException(status_code=503, detail={
            "code": error.code, "message": "Google Sheets authorization is not available.",
        }) from error


@router.post("/projects/{project_id}/sources/{source_id}/google-sheets/inspect")
def inspect_google_sheet(
    user_id: int, project_id: str, source_id: str, payload: GoogleSheetsInspectRequest,
    request: Request, response: Response,
):
    from services.google_sheets_connector import GoogleSheetsError, parse_spreadsheet_url
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    scope = _google_source_scope(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id),
    )
    client = _google_client(scope)
    try:
        spreadsheet_id, requested_sheet_id = parse_spreadsheet_url(payload.spreadsheet_url)
        result = client.metadata(spreadsheet_id)
        return {**result, "requested_sheet_id": requested_sheet_id}
    except GoogleSheetsError as error:
        raise HTTPException(status_code=422, detail={
            "code": error.code, "message": "The spreadsheet could not be inspected.",
        }) from error
    finally:
        client.close()


@router.post("/projects/{project_id}/sources/{source_id}/google-sheets/preview")
def preview_google_sheet(
    user_id: int, project_id: str, source_id: str, payload: GoogleSheetsPreviewRequest,
    request: Request, response: Response,
):
    from services.google_sheets_connector import (
        GoogleSheetsError, parse_spreadsheet_url, preview_mapping,
    )
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    scope = _google_source_scope(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id),
    )
    client = _google_client(scope)
    try:
        spreadsheet_id, _ = parse_spreadsheet_url(payload.spreadsheet_url)
        return preview_mapping(
            client, spreadsheet_id, payload.sheet_id, header_row=payload.header_row,
        )
    except GoogleSheetsError as error:
        raise HTTPException(status_code=422, detail={
            "code": error.code, "message": "The spreadsheet preview is not valid.",
        }) from error
    finally:
        client.close()


@router.put("/projects/{project_id}/sources/{source_id}/google-sheets/mapping")
def configure_google_sheet(
    user_id: int, project_id: str, source_id: str, payload: GoogleSheetsMappingRequest,
    request: Request, response: Response,
):
    from services.google_sheets_connector import (
        GoogleSheetsError, parse_spreadsheet_url, preview_mapping, save_mapping,
    )
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "source_write", tenant_id=tenant_id,
    )
    scope = _google_source_scope(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id),
    )
    client = _google_client(scope)
    try:
        spreadsheet_id, _ = parse_spreadsheet_url(payload.spreadsheet_url)
        preview = preview_mapping(
            client, spreadsheet_id, payload.sheet_id, header_row=payload.header_row,
        )
        selected = [value.strip() for value in payload.selected_columns]
        if len(set(selected)) != len(selected) or any(value not in preview["headers"] for value in selected) \
                or payload.record_id_column not in selected:
            raise GoogleSheetsError("google_sheets_mapping_invalid")
        identifiers = [str(row.get(payload.record_id_column) or "").strip()
                       for row in preview["rows"]]
        if any(not value for value in identifiers) or len(identifiers) != len(set(identifiers)):
            raise GoogleSheetsError("google_sheets_record_id_invalid")
        mapping = save_mapping(scope, {
            **preview, "selected_columns": selected,
            "record_id_column": payload.record_id_column,
            "expected_revision": payload.expected_revision,
        }, client=service_supabase)
        return {"mapping": mapping, "preview": preview,
                "deletion_mode": "retain_missing_records"}
    except GoogleSheetsError as error:
        raise HTTPException(status_code=422, detail={
            "code": error.code, "message": "The Google Sheets mapping is not valid.",
        }) from error
    finally:
        client.close()


@router.get("/projects/{project_id}/sources/{source_id}/google-sheets/mapping")
def get_google_sheet_mapping(
    user_id: int, project_id: str, source_id: str,
    request: Request, response: Response,
):
    from services.google_sheets_connector import GoogleSheetsError, get_mapping
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    scope = _google_source_scope(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id),
    )
    try:
        mapping = get_mapping(scope, client=service_supabase)
    except GoogleSheetsError as error:
        if error.code == "google_sheets_mapping_missing":
            return {"configured": False}
        raise
    safe = {key: mapping.get(key) for key in (
        "spreadsheet_id", "spreadsheet_title", "sheet_id", "sheet_title", "header_row",
        "selected_columns", "record_id_column", "resource_key", "mapping_revision",
        "last_snapshot_fingerprint", "last_validated_at", "updated_at",
    )}
    return {"configured": True, "mapping": safe,
            "deletion_mode": "retain_missing_records"}


def _ingestion_failure_code(error: Exception, *, metadata_started: bool) -> str:
    if metadata_started:
        return "metadata_commit_failed"
    if isinstance(error, HTTPException):
        if error.status_code == 413:
            return "upload_too_large"
        if error.status_code == 507:
            return "storage_unavailable"
        if 400 <= error.status_code < 500:
            return "upload_rejected"
    return "ingestion_failed"


@router.post("/projects/{project_id}/sources/{source_id}/ingestions/upload", status_code=201)
async def upload_source_ingestion(
    user_id: int,
    project_id: str,
    source_id: str,
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request,
        scoped_user_id,
        "upload",
        tenant_id=tenant_id,
    )
    project_source_ingestion_service.require_source_ingestions_schema()
    reservation = project_source_ingestion_service.reserve_ingestion(
        tenant_id=int(tenant_id),
        project_id=project_id,
        source_id=source_id,
        user_id=int(scoped_user_id),
        idempotency_key=idempotency_key,
    )
    disposition = reservation.get("disposition")
    if disposition == "succeeded":
        response.status_code = 200
        return {
            "persistent_dataset_id": reservation.get("result_dataset_id"),
            "dataset_version_id": reservation.get("result_version_id"),
            "project_id": project_id,
            "source_id": source_id,
            "ingestion_run_id": reservation.get("ingestion_run_id"),
            "ingestion_status": "succeeded",
            "idempotent_replay": True,
        }
    if disposition == "in_progress":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ingestion_in_progress",
                "message": "This import is already being processed.",
                "ingestion_run_id": reservation.get("ingestion_run_id"),
            },
        )
    if disposition == "failed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ingestion_previously_failed",
                "message": "This import attempt already failed. Start a new import to retry.",
                "ingestion_run_id": reservation.get("ingestion_run_id"),
            },
        )

    ingestion_run_id = reservation.get("ingestion_run_id")
    lease_token = reservation.get("lease_token")
    metadata_started = False

    def persist_metadata(artifact):
        nonlocal metadata_started
        metadata_started = True
        return project_source_ingestion_service.complete_ingestion(
            tenant_id=int(tenant_id),
            project_id=project_id,
            source_id=source_id,
            user_id=int(scoped_user_id),
            ingestion_run_id=ingestion_run_id,
            lease_token=lease_token,
            display_name=artifact.get("original_filename") or "Dataset",
            artifact=artifact,
        )

    try:
        upload_options = {
            "metadata_persister": persist_metadata,
            "metadata_failure_resolver": lambda _error: (
                project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=int(tenant_id),
                    project_id=project_id,
                    source_id=source_id,
                    user_id=int(scoped_user_id),
                    ingestion_run_id=ingestion_run_id,
                )
            ),
        }
        if lease_token:
            upload_options.update({
                "lifecycle_heartbeat": lambda: project_source_ingestion_service.heartbeat_ingestion(
                    tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                    lease_token=lease_token,
                ),
                "storage_reservation_persister": lambda reservation_id: (
                    project_source_ingestion_service.attach_storage_reservation(
                        tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                        lease_token=lease_token, storage_reservation_id=reservation_id,
                    )
                ),
                "storage_object_persister": lambda storage_object_id: (
                    project_source_ingestion_service.attach_storage_object(
                        tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                        lease_token=lease_token, storage_object_id=storage_object_id,
                    )
                ),
                "storage_object_failure_resolver": lambda storage_object_id: (
                    project_source_ingestion_service.storage_object_attachment_state(
                        tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                        lease_token=lease_token, storage_object_id=storage_object_id,
                    )
                ),
            })
        return await data_services.process_upload(
            file,
            tenant_id=tenant_id,
            user_id=scoped_user_id,
            **upload_options,
        )
    except Exception as error:
        if (
            isinstance(error, HTTPException)
            and isinstance(error.detail, dict)
            and error.detail.get("code") == "metadata_outcome_unknown"
        ):
            raise
        try:
            project_source_ingestion_service.fail_ingestion(
                tenant_id=int(tenant_id),
                project_id=project_id,
                source_id=source_id,
                user_id=int(scoped_user_id),
                ingestion_run_id=ingestion_run_id,
                lease_token=lease_token,
                failure_code=_ingestion_failure_code(error, metadata_started=metadata_started),
            )
        except Exception:
            logger.exception(
                "data.source_ingestion.failure_record_failed",
                extra={"tenant_id": tenant_id, "user_id": scoped_user_id},
            )
        raise


@router.post("/projects/{project_id}/sources/{source_id}/ingestions/api", status_code=201)
async def ingest_api_source(
    user_id: int,
    project_id: str,
    source_id: str,
    request: Request,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    resource_type: str | None = Query(default=None, min_length=2, max_length=80),
    fixture_batch: int = Query(default=1, ge=1, le=3),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "upload", tenant_id=tenant_id)
    project_source_ingestion_service.require_source_ingestions_schema()
    reservation_resource_key = resource_type
    provider_resource_type = resource_type
    if resource_type == "sheet":
        from services.google_sheets_connector import get_mapping
        mapping = get_mapping(AuthorizedSource(
            int(tenant_id), project_id, source_id, "google_sheets", int(scoped_user_id),
        ), client=service_supabase)
        reservation_resource_key = str(mapping["resource_key"])
        provider_resource_type = "sheet"
    reservation = project_source_ingestion_service.reserve_ingestion(
        tenant_id=int(tenant_id),
        project_id=project_id,
        source_id=source_id,
        user_id=int(scoped_user_id),
        idempotency_key=idempotency_key,
        source_type=project_data_source_service.SOURCE_TYPE_API_PROVIDER,
        resource_key=reservation_resource_key,
    )
    disposition = reservation.get("disposition")
    if disposition == "succeeded":
        response.status_code = 200
        return {
            "persistent_dataset_id": reservation.get("result_dataset_id"),
            "dataset_version_id": reservation.get("result_version_id"),
            "committed_revision": reservation.get("committed_revision"),
            "project_id": project_id,
            "source_id": source_id,
            "ingestion_run_id": reservation.get("ingestion_run_id"),
            "ingestion_status": "succeeded",
            "idempotent_replay": True,
        }
    if disposition == "in_progress":
        raise HTTPException(status_code=409, detail={
            "code": "ingestion_in_progress",
            "message": "This import is already being processed.",
            "ingestion_run_id": reservation.get("ingestion_run_id"),
        })
    if disposition == "failed":
        raise HTTPException(status_code=409, detail={
            "code": "ingestion_previously_failed",
            "message": "This import attempt already failed. Start a new import to retry.",
            "ingestion_run_id": reservation.get("ingestion_run_id"),
        })

    ingestion_run_id = reservation.get("ingestion_run_id")
    lease_token = reservation.get("lease_token")
    if not lease_token:
        raise HTTPException(status_code=503, detail={
            "code": "api_ingestion_recovery_required",
            "message": "API imports require the recovery-enabled database upgrade.",
        })
    metadata_started = False
    incremental = bool(reservation.get("source_resource_id"))

    def persist_metadata(artifact):
        nonlocal metadata_started
        metadata_started = True
        return project_source_ingestion_service.complete_ingestion(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
            lease_token=lease_token, display_name=f"{artifact.get('original_filename') or 'API dataset'}",
            artifact=artifact,
            source_type=project_data_source_service.SOURCE_TYPE_API_PROVIDER,
        )

    def persist_incremental(artifact, batch):
        nonlocal metadata_started
        metadata_started = True
        changes = [dict(change) for change in batch.changes]
        project_source_ingestion_service.stage_incremental_changes(
            tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
            lease_token=lease_token, changes=changes,
        )
        return project_source_ingestion_service.complete_incremental_ingestion(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
            lease_token=lease_token, storage_object_id=artifact["storage_object_id"],
            change_count=len(changes), manifest_hash=artifact["sha256"],
            next_cursor=batch.next_cursor,
            schema_fingerprint=batch.schema_fingerprint,
            credential_reference=(artifact.get("provider_metadata") or {}).get("credential"),
        )

    try:
        return await project_api_ingestion_service.process_api_source(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
            lifecycle_heartbeat=lambda: project_source_ingestion_service.heartbeat_ingestion(
                tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id, lease_token=lease_token,
            ),
            storage_reservation_persister=lambda reservation_id: (
                project_source_ingestion_service.attach_storage_reservation(
                    tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                    lease_token=lease_token, storage_reservation_id=reservation_id,
                )
            ),
            storage_object_persister=lambda storage_object_id: (
                project_source_ingestion_service.attach_storage_object(
                    tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                    lease_token=lease_token, storage_object_id=storage_object_id,
                )
            ),
            storage_object_failure_resolver=lambda storage_object_id: (
                project_source_ingestion_service.storage_object_attachment_state(
                    tenant_id=int(tenant_id), ingestion_run_id=ingestion_run_id,
                    lease_token=lease_token, storage_object_id=storage_object_id,
                )
            ),
            metadata_persister=persist_metadata,
            incremental_persister=persist_incremental if incremental else None,
            noop_persister=(
                lambda next_cursor, credential_reference:
                    project_source_ingestion_service.complete_noop_ingestion(
                        tenant_id=int(tenant_id), project_id=project_id,
                        source_id=source_id, user_id=int(scoped_user_id),
                        ingestion_run_id=ingestion_run_id, lease_token=lease_token,
                        next_cursor=next_cursor,
                        credential_reference=credential_reference,
                    )
            ) if incremental else None,
            metadata_failure_resolver=lambda _error: (
                project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
                    user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
                )
            ),
            resource_type=provider_resource_type,
            sync_cursor=reservation.get("expected_cursor"),
            fixture_batch=fixture_batch,
            shared_immutable=bool(reservation.get("shared_immutable_storage")),
            provider_audit=lambda metadata: logger.info(
                "data.api_provider.transport",
                extra={
                    "tenant_id": tenant_id,
                    "user_id": scoped_user_id,
                    "project_id": project_id,
                    "source_id": source_id,
                    **metadata,
                },
            ),
        )
    except Exception as error:
        if isinstance(error, HTTPException) and isinstance(error.detail, dict) \
                and error.detail.get("code") == "metadata_outcome_unknown":
            raise
        try:
            failure_code = project_api_ingestion_service.provider_failure_code(error)
            if failure_code == "ingestion_failed":
                failure_code = _ingestion_failure_code(error, metadata_started=metadata_started)
            project_source_ingestion_service.fail_ingestion(
                tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
                user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
                lease_token=lease_token, failure_code=failure_code,
            )
        except Exception:
            logger.exception("data.api_source_ingestion.failure_record_failed", extra={
                "tenant_id": tenant_id, "user_id": scoped_user_id,
            })
        raise


@router.get("/projects/{project_id}/sources/{source_id}/ingestions")
def list_source_ingestions(
    user_id: int,
    project_id: str,
    source_id: str,
    request: Request,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    if not project_source_ingestion_service.source_ingestions_available():
        return {
            "available": False,
            "items": [],
            "pagination": {"limit": limit, "offset": offset, "has_more": False},
        }
    result = project_source_ingestion_service.list_ingestions(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id), limit=limit, offset=offset,
    )
    return {"available": True, **result}


@router.get("/projects/{project_id}/sources/{source_id}/resources")
def list_source_resource_statuses(
    user_id: int,
    project_id: str,
    source_id: str,
    request: Request,
    response: Response,
    limit: int = Query(default=100, ge=1, le=100),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "read", tenant_id=tenant_id,
    )
    return project_source_ingestion_service.list_source_resource_statuses(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id), limit=limit,
    )


def _webhook_error(error: webhook_ingestion_service.WebhookIngestionError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={
        "code": error.code,
        "message": "The webhook operation could not be completed.",
    })


@router.get("/projects/{project_id}/sources/{source_id}/webhook")
def get_data_source_webhook_status(
    user_id: int, project_id: str, source_id: str, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    try:
        return webhook_ingestion_service.status(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id),
        )
    except webhook_ingestion_service.WebhookIngestionError as error:
        raise _webhook_error(error) from error


@router.post("/projects/{project_id}/sources/{source_id}/webhook", status_code=201)
def provision_data_source_webhook(
    user_id: int, project_id: str, source_id: str, payload: ProvisionWebhookRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    try:
        return webhook_ingestion_service.provision(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), enabled=payload.enabled,
            expected_fence=payload.expected_fence, resource_id=payload.resource_id,
        )
    except webhook_ingestion_service.WebhookIngestionError as error:
        raise _webhook_error(error) from error


@router.put("/projects/{project_id}/sources/{source_id}/webhook")
def configure_data_source_webhook(
    user_id: int, project_id: str, source_id: str, payload: ConfigureWebhookRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    try:
        return webhook_ingestion_service.configure(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), enabled=payload.enabled,
            expected_fence=payload.expected_fence,
        )
    except webhook_ingestion_service.WebhookIngestionError as error:
        raise _webhook_error(error) from error


@router.post("/projects/{project_id}/sources/{source_id}/webhook/revoke")
def revoke_data_source_webhook(
    user_id: int, project_id: str, source_id: str, payload: RevokeWebhookRequest,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    try:
        return webhook_ingestion_service.revoke(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            user_id=int(scoped_user_id), expected_fence=payload.expected_fence,
        )
    except webhook_ingestion_service.WebhookIngestionError as error:
        raise _webhook_error(error) from error


@router.post("/projects/{project_id}/sources/{source_id}/webhook/events/{event_id}/retry")
def retry_data_source_webhook_event(
    user_id: int, project_id: str, source_id: str, event_id: str,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "source_write", tenant_id=tenant_id)
    try:
        retried = webhook_ingestion_service.retry_event(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            event_id=event_id, user_id=int(scoped_user_id),
        )
    except webhook_ingestion_service.WebhookIngestionError as error:
        raise _webhook_error(error) from error
    if not retried:
        raise HTTPException(status_code=409, detail={"code": "webhook_event_not_retryable"})
    return {"retried": True}


@router.get("/projects/{project_id}/sources/{source_id}/resources/{resource_id}/schedule")
def get_automatic_sync_schedule(
    user_id: int, project_id: str, source_id: str, resource_id: str,
    request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    if not automatic_source_sync_service.automatic_sync_available():
        return {"available": False, "schedule": None}
    schedule = automatic_source_sync_service.get_schedule(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        resource_id=resource_id, user_id=int(scoped_user_id),
    )
    return {"available": True, "schedule": schedule}


@router.put("/projects/{project_id}/sources/{source_id}/resources/{resource_id}/schedule")
def configure_automatic_sync_schedule(
    user_id: int, project_id: str, source_id: str, resource_id: str,
    payload: ConfigureAutomaticSyncRequest, request: Request, response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(
        request, scoped_user_id, "write", tenant_id=tenant_id,
    )
    if not automatic_source_sync_service.automatic_sync_available():
        raise HTTPException(status_code=503, detail={
            "code": "automatic_sync_upgrade_required",
            "message": "Automatic synchronization requires the database upgrade.",
        })
    schedule = automatic_source_sync_service.configure_schedule(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        resource_id=resource_id, user_id=int(scoped_user_id),
        enabled=payload.enabled, interval_seconds=payload.interval_seconds,
        expected_fence=payload.expected_fence,
    )
    return {"available": True, "schedule": schedule}


@router.post(
    "/projects/{project_id}/sources/{source_id}/resources/{resource_id}/checkpoints",
    status_code=201,
)
async def create_incremental_checkpoint(
    user_id: int,
    project_id: str,
    source_id: str,
    resource_id: str,
    payload: CreateDatasetCheckpointRequest,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "upload", tenant_id=tenant_id)
    if not project_source_ingestion_service.incremental_ingestion_available():
        raise HTTPException(status_code=503, detail={
            "code": "incremental_ingestion_upgrade_required",
            "message": "Incremental checkpoints require the database upgrade.",
        })
    if project_dataset_checkpoint_service.background_checkpoints_available():
        response.status_code = 202
        return project_dataset_checkpoint_service.enqueue_dataset_checkpoint(
            tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
            resource_id=resource_id, dataset_id=payload.dataset_id,
            user_id=int(scoped_user_id), target_revision=payload.target_revision,
        )
    return await project_dataset_checkpoint_service.materialize_dataset_checkpoint(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        resource_id=resource_id, dataset_id=payload.dataset_id,
        user_id=int(scoped_user_id), target_revision=payload.target_revision,
    )


@router.get(
    "/projects/{project_id}/sources/{source_id}/resources/{resource_id}/checkpoints/{checkpoint_id}"
)
def get_incremental_checkpoint(
    user_id: int,
    project_id: str,
    source_id: str,
    resource_id: str,
    checkpoint_id: str,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    if not project_dataset_checkpoint_service.background_checkpoints_available():
        raise HTTPException(status_code=503, detail={
            "code": "background_checkpoints_upgrade_required",
            "message": "Background checkpoints require the database upgrade.",
        })
    return project_dataset_checkpoint_service.get_dataset_checkpoint(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        resource_id=resource_id, checkpoint_id=checkpoint_id,
        user_id=int(scoped_user_id),
    )


@router.get("/projects/{project_id}/sources/{source_id}/resources/{resource_id}/records")
def list_incremental_resource_records(
    user_id: int,
    project_id: str,
    source_id: str,
    resource_id: str,
    request: Request,
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    enforce_data_workspace_rate_limit(request, scoped_user_id, "read", tenant_id=tenant_id)
    return project_source_ingestion_service.list_incremental_records(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        resource_id=resource_id, user_id=int(scoped_user_id), limit=limit,
        offset=offset, include_deleted=include_deleted,
    )


@router.get("/projects/{project_id}/sources/{source_id}/ingestions/{ingestion_run_id}")
def get_source_ingestion(
    user_id: int,
    project_id: str,
    source_id: str,
    ingestion_run_id: str,
    request: Request,
    response: Response,
):
    tenant_id, scoped_user_id = get_storage_scope(request, response, user_id)
    project_source_ingestion_service.require_source_ingestions_schema()
    return project_source_ingestion_service.get_ingestion(
        tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
        user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
    )
