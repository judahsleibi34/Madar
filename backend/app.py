import os
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from data_analysis.routes.analysis_routes import router as analysis_router
from data_analysis.routes.cleaning_routes import router as cleaning_router
from data_analysis.routes.data_routes import router as data_router
from data_analysis.routes.visualization_routes import router as visualization_router

from routes.admin_billing_routes import router as admin_billing_router
from routes.admin_user_routes import router as admin_user_router
from routes.auth_routes import router as auth_router
from routes.billing_routes import router as billing_router
from routes.builder_routes import router as builder_router
from routes.health_routes import router as health_router
from routes.mfa_routes import router as mfa_router
from routes.password_routes import router as password_router
from routes.public_contact_routes import router as public_contact_router
from routes.public_site_routes import router as public_site_router
from routes.server_status_routes import router as server_status_router
from routes.user_routes import router as user_router
from routes.website_routes import router as website_router

from services.auth_service import get_authenticated_user_row, require_regular_user
from services.request_body_limits import RequestBodyLimitMiddleware
from services.request_security import (
    CSRF_HEADER_NAME,
    get_allowed_origins,
    validate_cookie_write_origin,
    validate_csrf_token,
)

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestBodyLimitMiddleware)

CHART_OUTPUT_DIR = Path(os.getenv("CHART_OUTPUT_DIR", "generated_charts")).resolve()
CHART_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated_charts", StaticFiles(directory=str(CHART_OUTPUT_DIR)), name="generated_charts")

UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

FRONTEND_URLS = os.getenv(
    "FRONTEND_URLS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
).split(",")

FRONTEND_URLS = [url.strip() for url in FRONTEND_URLS if url.strip()]


def require_authenticated_user(request: Request, response: Response):
    return get_authenticated_user_row(request, response)


def require_normal_user(request: Request, response: Response):
    return require_regular_user(request, response)


app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[CSRF_HEADER_NAME],
)

ALLOWED_CSRF_ORIGINS = get_allowed_origins(FRONTEND_URLS)


@app.middleware("http")
async def csrf_origin_middleware(request: Request, call_next):
    blocked_response = validate_cookie_write_origin(request, ALLOWED_CSRF_ORIGINS)

    if blocked_response is not None:
        return blocked_response

    blocked_response = validate_csrf_token(request)

    if blocked_response is not None:
        return blocked_response

    return await call_next(request)


@app.get("/")
def madar_status():
    return {"message": "All working"}


app.include_router(auth_router)
app.include_router(health_router)
app.include_router(user_router)
app.include_router(website_router)
app.include_router(password_router)
app.include_router(mfa_router)
app.include_router(server_status_router)
app.include_router(billing_router)
app.include_router(admin_billing_router)
app.include_router(admin_user_router)
app.include_router(builder_router)
app.include_router(public_contact_router)
app.include_router(public_site_router)

protected_data_dependencies = [Depends(require_normal_user)]

app.include_router(data_router, dependencies=protected_data_dependencies)
app.include_router(cleaning_router, dependencies=protected_data_dependencies)
app.include_router(analysis_router, dependencies=protected_data_dependencies)
app.include_router(visualization_router, dependencies=protected_data_dependencies)
