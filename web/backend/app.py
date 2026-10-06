import os
import re
import logging
import time
from io import BytesIO

from pathlib import Path

# Load the repository environment before importing routes or services whose
# module-level configuration depends on it (notably Redis rate limiting).
import database as _database_config  # noqa: F401
from database import service_supabase

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from data_analysis.routes.analysis_routes import router as analysis_router
from data_analysis.routes.cleaning_routes import router as cleaning_router
from data_analysis.routes.data_routes import router as data_router
from data_analysis.routes.visualization_routes import router as visualization_router

from routes.admin_billing_routes import router as admin_billing_router
from routes.admin_account_access_routes import router as admin_account_access_router
from routes.admin_profile_routes import router as admin_profile_router
from routes.admin_user_routes import router as admin_user_router
from routes.auth_routes import router as auth_router
from routes.auth_callback_routes import router as auth_callback_router
from routes.billing_routes import router as billing_router
from routes.data_deletion_routes import router as data_deletion_router
from routes.calendar_routes import router as calendar_router
from routes.ecommerce_routes import router as ecommerce_router
from routes.builder_routes import router as builder_router
from routes.health_routes import router as health_router
from routes.installation_routes import router as installation_router
from routes.mfa_routes import router as mfa_router
from routes.notification_routes import router as notification_router
from routes.password_routes import router as password_router
from routes.public_contact_routes import router as public_contact_router
from routes.public_site_routes import build_authorized_public_schema, router as public_site_router
from routes.server_status_routes import router as server_status_router
from routes.storage_delivery_routes import router as storage_delivery_router
from services.storage_delivery_service import stream_storage_object
from routes.user_routes import router as user_router
from routes.website_routes import router as website_router
from routes.elearning_routes import router as elearning_router
from routes.elearning_courses_routes import router as elearning_courses_router
from routes.elearning_directory_routes import router as elearning_directory_router
from routes.elearning_participation_routes import router as elearning_participation_router
from routes.elearning_player_routes import router as elearning_player_router
from routes.elearning_commerce_routes import router as elearning_commerce_router
from routes.elearning_academy_routes import router as elearning_academy_router
from routes.elearning_relationships_routes import router as elearning_relationships_router
from routes.elearning_assessments_routes import router as elearning_assessments_router
from routes.elearning_structure_routes import router as elearning_structure_router
from routes.elearning_content_routes import router as elearning_content_router

from services.auth_service import get_authenticated_user_row, require_regular_user
from services.builder_asset_storage import (
    BuilderAssetStorageError,
    download_builder_asset,
)
from services.asset_registry_service import (
    extract_builder_asset_references,
    nonproject_asset_reference_count,
)
from services.request_body_limits import RequestBodyLimitMiddleware
from services.runtime_config import validate_runtime_configuration
from services.observability_service import (
    CORRELATION_ID,
    begin_request_timings,
    configure_structured_logging,
    correlation_id,
    end_request_timings,
    record_request,
    record_request_timing,
    request_timings_snapshot,
    server_timing_value,
    timed_operation,
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
RUNTIME_CONFIGURATION = validate_runtime_configuration()
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
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
RESPONSIVE_IMAGE_WIDTHS = {320, 480, 768, 1024, 1440, 1920, 2560}
PERFORMANCE_TIMING_ROUTES = {
    "/auth/login",
    "/auth/user_status",
    "/ecommerce/catalog",
    "/ecommerce/tags",
    "/ecommerce/categories",
    "/ecommerce/brands",
    "/ecommerce/products",
    "/ecommerce/catalog/options",
    "/calendar/bootstrap",
    "/builder/projects",
    "/builder/projects/{project_id}/site-members",
    "/screen-time/weekly",
    "/billing/usage",
    "/notifications",
}


def render_responsive_builder_image(source: bytes, media_type: str, width: int) -> tuple[bytes, str]:
    try:
        with Image.open(BytesIO(source)) as opened:
            if getattr(opened, "is_animated", False):
                return source, media_type
            image = ImageOps.exif_transpose(opened)
            original_width = image.width
            if image.width > width:
                target_height = max(1, round(image.height * width / image.width))
                image = image.resize((width, target_height), Image.Resampling.LANCZOS)
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            image = image.convert("RGBA" if has_alpha else "RGB")
            output = BytesIO()
            image.save(output, format="WEBP", quality=90, method=4, exact=has_alpha)
            optimized = output.getvalue()
            if original_width <= width and len(optimized) >= len(source):
                return source, media_type
            return optimized, "image/webp"
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return source, media_type


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
    timings_token = begin_request_timings()
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
        measured = request_timings_snapshot()
        record_request_timing("app", max(0.0, elapsed - sum(measured.values())))
        timing_header = server_timing_value()
        if timing_header:
            response.headers["Server-Timing"] = timing_header
        if route in PERFORMANCE_TIMING_ROUTES or elapsed >= 0.5:
            logger.info(
                "http.request_timing",
                extra={
                    "method": request.method,
                    "route": route,
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                    "timings": {
                        name: round(duration * 1000, 1)
                        for name, duration in request_timings_snapshot().items()
                    },
                },
            )
        return response
    except Exception as error:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.monotonic() - started
        record_request(method=request.method, route=route, status_code=500, elapsed_seconds=elapsed)
        measured = request_timings_snapshot()
        record_request_timing("app", max(0.0, elapsed - sum(measured.values())))
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
            headers={
                "X-Request-ID": request_id,
                **({"Server-Timing": server_timing_value()} if server_timing_value() else {}),
            },
        )
        return error_response
    finally:
        end_request_timings(timings_token)
        CORRELATION_ID.reset(context_token)


@app.get("/")
def madar_status():
    return {"message": "All working"}


def _legacy_asset_visibility(*, tenant_id: int, storage_key: str, request: Request, response: Response) -> tuple[bool, bool]:
    """Secure bridge while schema 112 is live before migration 113 runs."""
    rows = getattr(
        service_supabase.table("builder_assets").select("id,status,metadata").eq("tenant_id", tenant_id).eq("storage_key", storage_key).limit(2).execute(),
        "data", None,
    ) or []
    if len(rows) != 1 or rows[0].get("status") not in {"active", "unreferenced"}:
        return False, False
    asset_id = rows[0]["id"]
    settings = getattr(
        service_supabase.table("website_settings")
        .select("*")
        .eq("tenant_id", tenant_id).limit(1).execute(), "data", None,
    ) or []
    bound_id = settings[0].get("published_project_id") if settings and (
        settings[0].get("subdomain") or settings[0].get("standard_path_slug")
    ) else None
    if bound_id:
        reference = getattr(
            service_supabase.table("builder_asset_references").select("asset_id")
            .eq("asset_id", asset_id).eq("project_id", bound_id).limit(1).execute(),
            "data", None,
        ) or []
        if reference:
            projects = getattr(
                service_supabase.table("builder_projects").select("id,published_schema,status")
                .eq("tenant_id", tenant_id).eq("status", "published").eq("id", bound_id).limit(1).execute(),
                "data", None,
            ) or []
            public_schema = build_authorized_public_schema(
                projects[0].get("published_schema") or {},
            ) if projects else {}
            if storage_key in extract_builder_asset_references(public_schema, tenant_id=tenant_id):
                return True, False
    metadata = rows[0].get("metadata")
    usage_hint = metadata.get("usage") if isinstance(metadata, dict) else None
    if nonproject_asset_reference_count(
        tenant_id=tenant_id, storage_key=storage_key, public_only=True,
        usage_hint=usage_hint, settings_row=settings[0] if settings else {},
        client=service_supabase,
    ):
        return True, False
    try:
        _, user = get_authenticated_user_row(request, response, allow_admin_account_access=False)
        if int(user.get("tenant_id")) == tenant_id:
            from services.elearning_player_service import media_access
            if media_access(tenant_id, int(user["id"]), storage_key):
                return True, True
    except Exception:
        pass
    return False, False


def _asset_visibility(*, tenant_id: int, storage_key: str, request: Request, response: Response) -> tuple[bool, bool]:
    try:
        result = service_supabase.rpc(
            "get_managed_asset_visibility_context",
            {"p_tenant_id": tenant_id, "p_storage_key": storage_key},
        ).execute()
    except Exception as error:
        # The release controller deploys compatible code before its guarded
        # schema migration. Only a definitively missing RPC uses the existing
        # complete authorization path; network and database errors fail closed.
        if getattr(error, "code", None) == "PGRST202":
            return _legacy_asset_visibility(
                tenant_id=tenant_id, storage_key=storage_key, request=request, response=response,
            )
        raise

    rows = getattr(result, "data", None)
    if not isinstance(rows, list) or len(rows) > 1:
        raise ValueError("managed_asset_visibility_response_invalid")
    if not rows:
        return False, False
    row = rows[0]
    if not isinstance(row, dict) or row.get("asset_status") not in {"active", "unreferenced"}:
        raise ValueError("managed_asset_visibility_response_invalid")
    settings = row.get("settings")
    metadata = row.get("metadata")
    schema = row.get("published_schema")
    if (settings is not None and not isinstance(settings, dict)
            or metadata is not None and not isinstance(metadata, dict)
            or schema is not None and not isinstance(schema, dict)):
        raise ValueError("managed_asset_visibility_response_invalid")

    if schema is not None:
        public_schema = build_authorized_public_schema(schema)
        if storage_key in extract_builder_asset_references(public_schema, tenant_id=tenant_id):
            return True, False

    usage_hint = metadata.get("usage") if metadata else None
    if nonproject_asset_reference_count(
        tenant_id=tenant_id, storage_key=storage_key, public_only=True,
        usage_hint=usage_hint, settings_row=settings or {}, client=service_supabase,
    ):
        return True, False
    try:
        _, user = get_authenticated_user_row(request, response, allow_admin_account_access=False)
        if int(user.get("tenant_id")) == tenant_id:
            from services.elearning_player_service import media_access
            if media_access(tenant_id, int(user["id"]), storage_key):
                return True, True
    except Exception:
        pass
    return False, False


def _managed_asset_failure(status_code: int, detail: str = "Asset was not found.") -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers={"Cache-Control": "no-store", "CDN-Cache-Control": "no-store"},
    )


@app.get("/uploads/tenant_{tenant_id}/builder_assets/{filename}")
def get_public_builder_asset(
    tenant_id: int,
    filename: str,
    request: Request,
    response: Response,
    w: int | None = None,
):
    if tenant_id <= 0:
        raise _managed_asset_failure(404)

    try:
        safe_filename = validate_safe_filename(
            filename,
            allowed_extensions=set(PUBLIC_UPLOAD_MEDIA_TYPES),
            error_type=ValueError,
            error_message="Invalid public asset path",
        )
    except ValueError as error:
        raise _managed_asset_failure(404) from error

    if not re.fullmatch(r"[a-f0-9]{32}\.(?:png|jpg|jpeg|webp|mp4|webm|pdf|doc|docx|mp3|wav)", safe_filename):
        raise _managed_asset_failure(404)

    public_root = PUBLIC_UPLOADS_DIR.resolve()
    tenant_root = public_root / f"tenant_{tenant_id}"
    builder_root = tenant_root / "builder_assets"
    if tenant_root.is_symlink() or builder_root.is_symlink():
        raise _managed_asset_failure(404)
    asset_path = assert_path_within_root(
        builder_root / safe_filename,
        builder_root,
        error=_managed_asset_failure(404),
    )

    response_headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "CDN-Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": "inline",
        # Media byte ranges describe the stored representation. Prevent the
        # global GZip middleware from changing its length after FileResponse
        # has calculated Content-Range and Content-Length.
        "Content-Encoding": "identity",
    }
    media_type = PUBLIC_UPLOAD_MEDIA_TYPES[Path(asset_path).suffix.lower()]
    storage_key = f"tenant_{tenant_id}/builder_assets/{safe_filename}"
    try:
        with timed_operation("managed_asset_auth"):
            visible, private_preview = _asset_visibility(
                tenant_id=tenant_id, storage_key=storage_key, request=request, response=response,
            )
    except Exception as error:
        logger.warning("builder.asset_visibility_lookup_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        raise _managed_asset_failure(503, "Asset visibility is temporarily unavailable") from error
    if not visible:
        raise _managed_asset_failure(404)
    if private_preview:
        response_headers = {
            **response_headers,
            "Cache-Control": "private, no-store",
            "CDN-Cache-Control": "no-store",
        }

    if w is not None:
        if w not in RESPONSIVE_IMAGE_WIDTHS or not media_type.startswith("image/"):
            raise _managed_asset_failure(400, "Unsupported image width.")
        try:
            source = asset_path.read_bytes() if asset_path.is_file() else download_builder_asset(
                storage_key=f"tenant_{tenant_id}/builder_assets/{safe_filename}"
            )
        except (OSError, BuilderAssetStorageError) as error:
            raise _managed_asset_failure(404) from error
        content, response_media_type = render_responsive_builder_image(source, media_type, w)
        return Response(content=content, media_type=response_media_type, headers=response_headers)

    if asset_path.is_file():
        return FileResponse(
            path=str(asset_path),
            media_type=media_type,
            headers=response_headers,
        )

    if private_preview:
        response_headers['Vary'] = 'Cookie, Authorization'
    return stream_storage_object(
        bucket='builder-assets', path=storage_key, request=request, headers=response_headers,
    )


app.include_router(storage_delivery_router)
app.include_router(auth_callback_router)
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(user_router)
app.include_router(website_router)
app.include_router(elearning_router)
app.include_router(elearning_courses_router)
app.include_router(elearning_directory_router)
app.include_router(elearning_structure_router)
app.include_router(elearning_content_router)
app.include_router(elearning_participation_router)
from routes.elearning_credentials_routes import router as elearning_credentials_router
app.include_router(elearning_credentials_router)
app.include_router(elearning_player_router)
app.include_router(elearning_commerce_router)
app.include_router(elearning_academy_router)
app.include_router(elearning_relationships_router)
app.include_router(elearning_assessments_router)
app.include_router(password_router)
app.include_router(mfa_router)
app.include_router(installation_router)
app.include_router(notification_router)
app.include_router(server_status_router)
app.include_router(billing_router)
app.include_router(data_deletion_router)
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
    expose_headers=[CSRF_HEADER_NAME, "X-Request-ID", "Server-Timing"],
)
