import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File, Header, Query
from pydantic import BaseModel, Field

from data_analysis import services as data_services
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
)
from services import data_source_credential_service


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
    reservation = project_source_ingestion_service.reserve_ingestion(
        tenant_id=int(tenant_id),
        project_id=project_id,
        source_id=source_id,
        user_id=int(scoped_user_id),
        idempotency_key=idempotency_key,
        source_type=project_data_source_service.SOURCE_TYPE_API_PROVIDER,
        resource_key=resource_type,
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
            metadata_failure_resolver=lambda _error: (
                project_source_ingestion_service.recover_completed_ingestion(
                    tenant_id=int(tenant_id), project_id=project_id, source_id=source_id,
                    user_id=int(scoped_user_id), ingestion_run_id=ingestion_run_id,
                )
            ),
            resource_type=resource_type,
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
