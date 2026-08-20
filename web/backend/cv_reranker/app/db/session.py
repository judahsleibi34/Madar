from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def build_async_engine(settings: Settings) -> AsyncEngine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if settings.app_env == "test" and settings.database_url.startswith("postgresql"):
        options["poolclass"] = NullPool
    elif settings.database_url.startswith("postgresql"):
        options.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
        )
    return create_async_engine(settings.database_url, **options)


def build_sync_engine(settings: Settings) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if settings.worker_database_url.startswith("postgresql"):
        options.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
        )
    return create_engine(settings.worker_database_url, **options)


settings = get_settings()
async_engine = build_async_engine(settings)
sync_engine = build_sync_engine(settings)
AsyncSessionFactory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
SyncSessionFactory = sessionmaker(sync_engine, expire_on_commit=False, class_=Session)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session


@contextmanager
def get_sync_session() -> Iterator[Session]:
    with SyncSessionFactory() as session:
        yield session
