from fastapi import APIRouter

router = APIRouter(tags=["Server Status"])


@router.get("/")
def madar_health():
    return {"message": "All working"}