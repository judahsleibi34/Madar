from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from services.readiness_service import get_readiness


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    readiness = get_readiness()
    if readiness["ready"]:
        return readiness

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=readiness,
    )
