from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

import os

from services.observability_service import metrics_access_allowed, prometheus_metrics
from services.notification_delivery_queue_service import get_delivery_channel_metrics
from services.readiness_service import get_readiness


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("/version")
def version():
    return {
        "release_sha": os.getenv("MADAR_RELEASE_SHA", "development"),
        "build_timestamp": os.getenv("MADAR_BUILD_TIMESTAMP", "unknown"),
        "schema_compatible_min": int(os.getenv("SCHEMA_COMPATIBLE_MIN", "81")),
        "schema_compatible_max": int(os.getenv("SCHEMA_COMPATIBLE_MAX", "82")),
    }


@router.get("/ready")
def ready():
    readiness = get_readiness()
    if readiness["ready"]:
        return readiness

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=readiness,
    )


@router.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    client_host = request.client.host if request.client else None
    if not metrics_access_allowed(
        client_host=client_host,
        authorization=request.headers.get("Authorization"),
    ):
        raise HTTPException(status_code=404, detail="Not found")
    return PlainTextResponse(prometheus_metrics(), media_type="text/plain; version=0.0.4")


@router.get("/diagnostics", include_in_schema=False)
def diagnostics(request: Request):
    client_host = request.client.host if request.client else None
    if not metrics_access_allowed(
        client_host=client_host,
        authorization=request.headers.get("Authorization"),
    ):
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "release": version(),
        "readiness": get_readiness(use_cache=False),
        "notification_channels": get_delivery_channel_metrics(),
    }
