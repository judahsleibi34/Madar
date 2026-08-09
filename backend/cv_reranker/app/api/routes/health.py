from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.dependencies.auth import DatabaseSession
from app.core.config import get_settings
from app.core.errors import ApiError

EXPECTED_MIGRATION_REVISION = "dd5c5f6e8e7d"
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: DatabaseSession) -> dict[str, str]:
    settings = get_settings()
    await db.execute(text("SELECT 1"))
    settings.ensure_storage()
    try:
        revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception as error:
        raise ApiError(503, "SCHEMA_NOT_READY", "The database schema is not ready.") from error
    if revision != EXPECTED_MIGRATION_REVISION:
        raise ApiError(503, "SCHEMA_NOT_READY", "The database schema is not ready.")
    return {"status": "ready"}
