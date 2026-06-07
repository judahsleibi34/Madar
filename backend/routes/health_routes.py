from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from database import get_config_readiness


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    checks = get_config_readiness()
    if all(checks.values()):
        return {"status": "ok", "checks": checks}

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "degraded", "checks": checks},
    )
