from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_refresh_token, hash_refresh_token, utc_now
from app.core.config import Settings
from app.core.errors import unauthorized
from app.db.models import AuthSession, User


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class IssuedRefreshToken:
    token: str
    session: AuthSession


async def issue_refresh_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    settings: Settings,
    user_agent: str | None,
    ip_address: str | None,
    family_id: uuid.UUID | None = None,
    parent_token_id: uuid.UUID | None = None,
) -> IssuedRefreshToken:
    token = create_refresh_token()
    row = AuthSession(
        user_id=user_id,
        token_hash=hash_refresh_token(token),
        token_family_id=family_id or uuid.uuid4(),
        parent_token_id=parent_token_id,
        expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
        user_agent=(user_agent or "")[:512] or None,
        ip_address=ip_address,
    )
    db.add(row)
    await db.flush()
    return IssuedRefreshToken(token=token, session=row)


async def revoke_token_family(
    db: AsyncSession,
    *,
    family_id: uuid.UUID,
    reason: str,
) -> None:
    now = utc_now()
    await db.execute(
        update(AuthSession)
        .where(AuthSession.token_family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason)
    )


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    refresh_token: str,
    settings: Settings,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, IssuedRefreshToken]:
    token_hash = hash_refresh_token(refresh_token)
    row = await db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash).with_for_update()
    )
    if row is None:
        raise unauthorized()

    now = utc_now()
    if row.revoked_at is not None or row.rotated_at is not None:
        await revoke_token_family(db, family_id=row.token_family_id, reason="refresh_token_reuse")
        await db.commit()
        raise unauthorized()
    if as_utc(row.expires_at) <= now:
        row.revoked_at = now
        row.revoke_reason = "expired"
        await db.commit()
        raise unauthorized()

    user = await db.scalar(
        select(User).where(
            User.id == row.user_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        row.revoked_at = now
        row.revoke_reason = "inactive_user"
        await db.commit()
        raise unauthorized()

    row.rotated_at = now
    row.revoked_at = now
    row.revoke_reason = "rotated"
    row.last_used_at = now
    issued = await issue_refresh_token(
        db,
        user_id=user.id,
        settings=settings,
        user_agent=user_agent,
        ip_address=ip_address,
        family_id=row.token_family_id,
        parent_token_id=row.id,
    )
    await db.commit()
    return user, issued


async def revoke_refresh_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    refresh_token: str,
    reason: str = "logout",
) -> None:
    row = await db.scalar(
        select(AuthSession)
        .where(
            AuthSession.token_hash == hash_refresh_token(refresh_token),
            AuthSession.user_id == user_id,
        )
        .with_for_update()
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = utc_now()
        row.revoke_reason = reason
    await db.commit()


async def revoke_all_user_sessions(db: AsyncSession, *, user_id: uuid.UUID, reason: str) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now(), revoke_reason=reason)
    )
    await db.commit()
