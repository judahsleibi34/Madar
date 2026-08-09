from __future__ import annotations

import ipaddress
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.auth.password import (
    hash_password,
    password_needs_rehash,
    validate_password,
    verify_password,
)
from app.auth.sessions import issue_refresh_token, revoke_refresh_token, rotate_refresh_token
from app.auth.tokens import create_access_token, utc_now
from app.core.config import Settings, get_settings
from app.core.errors import ApiError, unauthorized
from app.db.models import User
from app.db.session import get_async_session
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.services.rate_limit import rate_limiter

router = APIRouter(prefix="/auth", tags=["authentication"])


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def client_identity(request: Request, suffix: str = "") -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{suffix}"


def client_ip(request: Request) -> str | None:
    value = request.client.host if request.client else ""
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def require_cookie_csrf(request: Request) -> None:
    cookie_value = request.cookies.get("cv_csrf_token", "")
    header_value = request.headers.get("X-CSRF-Token", "")
    if not cookie_value or not secrets.compare_digest(cookie_value, header_value):
        raise ApiError(403, "CSRF_VALIDATION_FAILED", "The request could not be verified.")


def refresh_from_request(request: Request, supplied: str | None, settings: Settings) -> str:
    if settings.refresh_token_cookie:
        require_cookie_csrf(request)
        value = request.cookies.get("cv_refresh_token", "")
    else:
        value = supplied or ""
    if len(value) < 32:
        raise unauthorized()
    return value


def attach_refresh_transport(
    response: Response,
    *,
    refresh_token: str,
    settings: Settings,
) -> str | None:
    if not settings.refresh_token_cookie:
        return refresh_token
    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.refresh_token_expire_days * 86400
    response.set_cookie(
        "cv_refresh_token",
        refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=f"{settings.api_v1_prefix}/auth",
    )
    response.set_cookie(
        "cv_csrf_token",
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=f"{settings.api_v1_prefix}/auth",
    )
    response.headers["X-CSRF-Token"] = csrf_token
    return None


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegisterResponse:
    if settings.rate_limit_enabled:
        await rate_limiter.enforce(
            db,
            action="register",
            identity=client_identity(request),
            limit=settings.registration_rate_limit,
            window_seconds=settings.rate_limit_window_seconds,
        )
    normalized = normalize_email(str(payload.email))
    validate_password(payload.password, minimum_length=settings.password_min_length)
    display_name = " ".join(payload.display_name.split())
    if not display_name:
        raise ApiError(422, "INVALID_DISPLAY_NAME", "A display name is required.")
    if await db.scalar(select(User.id).where(User.normalized_email == normalized)) is not None:
        raise ApiError(409, "ACCOUNT_CONFLICT", "An account cannot be created with these details.")
    user = User(
        email=normalized,
        normalized_email=normalized,
        password_hash=hash_password(payload.password),
        display_name=display_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise ApiError(
            409, "ACCOUNT_CONFLICT", "An account cannot be created with these details."
        ) from error
    await db.refresh(user)
    return RegisterResponse(user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    normalized = normalize_email(str(payload.email))
    if settings.rate_limit_enabled:
        await rate_limiter.enforce(
            db,
            action="login",
            identity=client_identity(request, normalized),
            limit=settings.login_rate_limit,
            window_seconds=settings.rate_limit_window_seconds,
        )
    user = await db.scalar(select(User).where(User.normalized_email == normalized))
    password_valid = verify_password(payload.password, user.password_hash if user else None)
    if not password_valid or user is None or not user.is_active or user.deleted_at is not None:
        raise ApiError(401, "INVALID_CREDENTIALS", "The email or password is incorrect.")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = utc_now()
    issued = await issue_refresh_token(
        db,
        user_id=user.id,
        settings=settings,
        user_agent=request.headers.get("User-Agent"),
        ip_address=client_ip(request),
    )
    await db.commit()
    access = create_access_token(user.id, settings)
    transported = attach_refresh_transport(response, refresh_token=issued.token, settings=settings)
    return TokenResponse(
        access_token=access.token,
        refresh_token=transported,
        expires_in=access.expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    if settings.rate_limit_enabled:
        await rate_limiter.enforce(
            db,
            action="refresh",
            identity=client_identity(request),
            limit=settings.refresh_rate_limit,
            window_seconds=settings.rate_limit_window_seconds,
        )
    token = refresh_from_request(request, payload.refresh_token, settings)
    user, issued = await rotate_refresh_token(
        db,
        refresh_token=token,
        settings=settings,
        user_agent=request.headers.get("User-Agent"),
        ip_address=client_ip(request),
    )
    access = create_access_token(user.id, settings)
    transported = attach_refresh_transport(response, refresh_token=issued.token, settings=settings)
    return TokenResponse(
        access_token=access.token,
        refresh_token=transported,
        expires_in=access.expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    request: Request,
    response: Response,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    token = refresh_from_request(request, payload.refresh_token, settings)
    await revoke_refresh_token(db, user_id=user.id, refresh_token=token)
    if settings.refresh_token_cookie:
        response.delete_cookie("cv_refresh_token", path=f"{settings.api_v1_prefix}/auth")
        response.delete_cookie("cv_csrf_token", path=f"{settings.api_v1_prefix}/auth")


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
