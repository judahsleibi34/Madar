from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import utc_now
from app.core.errors import ApiError
from app.db.models import RateLimitBucket


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class DatabaseRateLimiter:
    async def enforce(
        self,
        db: AsyncSession,
        *,
        action: str,
        identity: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        key_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        now = utc_now()
        row = await db.scalar(
            select(RateLimitBucket)
            .where(RateLimitBucket.key_hash == key_hash, RateLimitBucket.action == action)
            .with_for_update()
        )
        if row is None:
            row = RateLimitBucket(
                key_hash=key_hash,
                action=action,
                window_started_at=now,
                request_count=1,
                expires_at=now + timedelta(seconds=window_seconds),
            )
            db.add(row)
            try:
                await db.commit()
                return
            except IntegrityError:
                await db.rollback()
                row = await db.scalar(
                    select(RateLimitBucket)
                    .where(RateLimitBucket.key_hash == key_hash, RateLimitBucket.action == action)
                    .with_for_update()
                )
                if row is None:
                    raise ApiError(
                        503, "RATE_LIMIT_UNAVAILABLE", "The request cannot be processed now."
                    ) from None

        if as_utc(row.expires_at) <= now:
            row.window_started_at = now
            row.expires_at = now + timedelta(seconds=window_seconds)
            row.request_count = 1
        else:
            row.request_count += 1
            if row.request_count > limit:
                await db.rollback()
                retry_after = max(1, int((as_utc(row.expires_at) - now).total_seconds()))
                raise ApiError(
                    429,
                    "RATE_LIMITED",
                    "Too many requests. Try again later.",
                    {"Retry-After": str(retry_after)},
                )
        await db.commit()

    async def cleanup(self, db: AsyncSession) -> int:
        result = await db.execute(
            delete(RateLimitBucket).where(RateLimitBucket.expires_at < utc_now())
        )
        await db.commit()
        return int(getattr(result, "rowcount", 0) or 0)


rate_limiter = DatabaseRateLimiter()
