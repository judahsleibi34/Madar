import logging

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, File
from pydantic import BaseModel

from data_analysis import services as data_services
from services.rate_limit_service import enforce_data_workspace_rate_limit
from services.tenant_service import require_active_tenant_user_id


router = APIRouter(
    prefix="/users/{user_id}/data",
    tags=["Data"]
)
logger = logging.getLogger(__name__)

class ReadDataRequest(BaseModel):
    input_path: str


def get_storage_scope(
    request: Request,
    response: Response,
    user_id: int,
) -> tuple[str, str]:
    context = require_active_tenant_user_id(user_id, request, response)

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
