from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.api.routes import auth, health, jobs
from app.core.config import get_settings
from app.core.errors import ApiError, api_error_handler, error_response, unhandled_error_handler
from app.core.logging import configure_logging
from app.db.session import async_engine

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_storage()
    async with async_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    yield
    await async_engine.dispose()


app = FastAPI(
    title="CV Semantic Reranker API",
    version="1.0.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.refresh_token_cookie,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID", "")[:128] or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "user_id": getattr(request.state, "user_id", None),
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
    return response


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
    return await api_error_handler(request, error)


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, _error: RequestValidationError) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="The request did not pass validation.",
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
    code = "RESOURCE_NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
    message = (
        "The requested resource was not found." if error.status_code == 404 else str(error.detail)
    )
    return error_response(request, status_code=error.status_code, code=code, message=message)


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_request_error",
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return await unhandled_error_handler(request, error)


app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(jobs.router, prefix=settings.api_v1_prefix)
