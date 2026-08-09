import os
import re
import logging
import time

from pathlib import Path

# Load the repository environment before importing routes or services whose
# module-level configuration depends on it (notably Redis rate limiting).
import database as _database_config  # noqa: F401

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from data_analysis.routes.analysis_routes import router as analysis_router
from data_analysis.routes.cleaning_routes import router as cleaning_router
from data_analysis.routes.data_routes import router as data_router
from data_analysis.routes.visualization_routes import router as visualization_router

from routes.admin_billing_routes import router as admin_billing_router
from routes.admin_account_access_routes import router as admin_account_access_router
from routes.admin_profile_routes import router as admin_profile_router
from routes.admin_user_routes import router as admin_user_router
from routes.auth_routes import router as auth_router
from routes.billing_routes import router as billing_router
from routes.calendar_routes import router as calendar_router
from routes.ecommerce_routes import router as ecommerce_router
from routes.builder_routes import router as builder_router
from routes.health_routes import router as health_router
from routes.installation_routes import router as installation_router
from routes.mfa_routes import router as mfa_router
from routes.notification_routes import router as notification_router
from routes.password_routes import router as password_router
from routes.public_contact_routes import router as public_contact_router
from routes.public_site_routes import router as public_site_router
from routes.server_status_routes import router as server_status_router
from routes.user_routes import router as user_router
from routes.website_routes import router as website_router

from services.auth_service import get_authenticated_user_row, require_regular_user
from services.builder_asset_storage import load_builder_asset
from services.request_body_limits import RequestBodyLimitMiddleware
from services.observability_service import (
    CORRELATION_ID,
    configure_structured_logging,
    correlation_id,
    record_request,
)
from services.request_security import (
    CSRF_HEADER_NAME,
    add_cors_headers_for_allowed_origin,
    get_allowed_origins,
    validate_cookie_write_origin,
    validate_csrf_token,
)
from services.upload_config import (
    get_data_upload_dir,
    get_private_charts_dir,
    get_public_uploads_dir,
    assert_path_within_root,
    validate_safe_filename,
    validate_private_charts_not_publicly_mounted,
    validate_private_uploads_not_publicly_mounted,
)

configure_structured_logging()
logger = logging.getLogger(__name__)
app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestBodyLimitMiddleware)

PUBLIC_UPLOADS_DIR = get_public_uploads_dir()
DATA_UPLOAD_DIR = get_data_upload_dir()
PRIVATE_CHARTS_DIR = get_private_charts_dir()
validate_private_uploads_not_publicly_mounted(
    public_uploads_dir=PUBLIC_UPLOADS_DIR,
    data_upload_dir=DATA_UPLOAD_DIR,
)
validate_private_charts_not_publicly_mounted(
    public_uploads_dir=PUBLIC_UPLOADS_DIR,
    private_charts_dir=PRIVATE_CHARTS_DIR,
)
PUBLIC_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_CHARTS_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_UPLOAD_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

FRONTEND_URLS = os.getenv(
    "FRONTEND_URLS",
    (
        "http://localhost:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    ),
).split(",")

FRONTEND_URLS = [url.strip() for url in FRONTEND_URLS if url.strip()]


def require_authenticated_user(request: Request, response: Response):
    return get_authenticated_user_row(request, response)


def require_normal_user(request: Request, response: Response):
    return require_regular_user(request, response)


ALLOWED_CSRF_ORIGINS = get_allowed_origins(FRONTEND_URLS)


@app.middleware("http")
async def csrf_origin_middleware(request: Request, call_next):
    blocked_response = validate_cookie_write_origin(request, ALLOWED_CSRF_ORIGINS)

    if blocked_response is not None:
        return add_cors_headers_for_allowed_origin(
            blocked_response,
            request,
            ALLOWED_CSRF_ORIGINS,
        )

    blocked_response = validate_csrf_token(request)

    if blocked_response is not None:
        return add_cors_headers_for_allowed_origin(
            blocked_response,
            request,
            ALLOWED_CSRF_ORIGINS,
        )

    return await call_next(request)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = correlation_id(request.headers.get("X-Request-ID"))
    context_token = CORRELATION_ID.set(request_id)
    started = time.monotonic()
    try:
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.monotonic() - started
        record_request(
            method=request.method,
            route=route,
            status_code=response.status_code,
            elapsed_seconds=elapsed,
        )
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as error:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.monotonic() - started
        record_request(method=request.method, route=route, status_code=500, elapsed_seconds=elapsed)
        logger.error(
            "http.request_unhandled",
            extra={"method": request.method, "route": route, "status_code": 500, "error_type": type(error).__name__},
        )
        error_response = JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected server error occurred.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )
        return error_response
    finally:
        CORRELATION_ID.reset(context_token)


@app.get("/")
def madar_status():
    return {"message": "All working"}


@app.get("/uploads/tenant_{tenant_id}/builder_assets/{filename}")
def get_public_builder_asset(tenant_id: int, filename: str):
    if tenant_id <= 0:
        raise HTTPException(status_code=404, detail="Asset was not found.")

    try:
        safe_filename = validate_safe_filename(
            filename,
            allowed_extensions=set(PUBLIC_UPLOAD_MEDIA_TYPES),
            error_type=ValueError,
            error_message="Invalid public asset path",
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Asset was not found.") from error

    if not re.fullmatch(r"[a-f0-9]{32}\.(?:png|jpg|jpeg|webp)", safe_filename):
        raise HTTPException(status_code=404, detail="Asset was not found.")

    public_root = PUBLIC_UPLOADS_DIR.resolve()
    asset_path = assert_path_within_root(
        public_root / f"tenant_{tenant_id}" / "builder_assets" / safe_filename,
        public_root,
        error=HTTPException(status_code=404, detail="Asset was not found."),
    )

    response_headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": "inline",
    }
    media_type = PUBLIC_UPLOAD_MEDIA_TYPES[Path(asset_path).suffix.lower()]

    if asset_path.is_file():
        return FileResponse(
            path=str(asset_path),
            media_type=media_type,
            headers=response_headers,
        )

    storage_key = f"tenant_{tenant_id}/builder_assets/{safe_filename}"
    try:
        content = load_builder_asset(storage_key=storage_key)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Asset was not found.") from error

    return Response(
        content=content,
        media_type=media_type,
        headers=response_headers,
    )


app.include_router(auth_router)
app.include_router(health_router)
app.include_router(user_router)
app.include_router(website_router)
app.include_router(password_router)
app.include_router(mfa_router)
app.include_router(installation_router)
app.include_router(notification_router)
app.include_router(server_status_router)
app.include_router(billing_router)
app.include_router(calendar_router)
app.include_router(ecommerce_router)
app.include_router(admin_account_access_router)
app.include_router(admin_billing_router)
app.include_router(admin_profile_router)
app.include_router(admin_user_router)
app.include_router(builder_router)
app.include_router(public_contact_router)
app.include_router(public_site_router)

protected_data_dependencies = [Depends(require_normal_user)]

app.include_router(data_router, dependencies=protected_data_dependencies)
app.include_router(cleaning_router, dependencies=protected_data_dependencies)
app.include_router(analysis_router, dependencies=protected_data_dependencies)
app.include_router(visualization_router, dependencies=protected_data_dependencies)

# Keep CORS outermost so every response path, including the sanitized response
# produced by observability_middleware for an unhandled exception, is evaluated
# by the same exact-origin policy. Starlette inserts newly added middleware at
# the front of the user middleware stack, so this registration intentionally
# follows the function-based middleware declarations above.
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[CSRF_HEADER_NAME, "X-Request-ID"],
)
