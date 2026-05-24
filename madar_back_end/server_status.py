from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def madar_health():
    return {"message": "All working"}

