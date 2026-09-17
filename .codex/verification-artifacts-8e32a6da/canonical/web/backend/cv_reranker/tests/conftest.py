from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "test.db"
POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")
worker_database_url = POSTGRES_TEST_URL or f"sqlite:///{DB_PATH.as_posix()}"
database_url = (
    worker_database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    if POSTGRES_TEST_URL
    else f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"
)
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": database_url,
        "WORKER_DATABASE_URL": worker_database_url,
        "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests",
        "RATE_LIMIT_ENABLED": "false",
        "UPLOAD_DIRECTORY": str(ROOT / "test-data" / "uploads"),
        "TEMP_DIRECTORY": str(ROOT / "test-data" / "tmp"),
        "MODEL_CACHE_DIRECTORY": str(ROOT / "test-data" / "models"),
    }
)

from sqlalchemy import text  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import sync_engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    if POSTGRES_TEST_URL is None:
        DB_PATH.unlink(missing_ok=True)
        Base.metadata.create_all(sync_engine)
        with sync_engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            )
            connection.execute(text("INSERT INTO alembic_version VALUES ('dd5c5f6e8e7d')"))
    yield
    sync_engine.dispose()
    if POSTGRES_TEST_URL is None:
        DB_PATH.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def clean_database():
    yield
    with sync_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
