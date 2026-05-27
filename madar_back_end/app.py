from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import os

from server_status import router as server_status_router
from auth import get_authenticated_user_row, router as login_sign_up_router
from forget_password import router as forget_password_router
from contact_us import router as contact_us_router

from data_analysis.data_routes import router as data_router
from data_analysis.cleaning_routes import router as cleaning_router
from data_analysis.analysis_routes import router as analysis_router
from data_analysis.visualization_routes import router as visualization_router


app = FastAPI(
    title="Madar Backend",
    version="1.0.0"
)

FRONTEND_URLS = os.getenv(
    "FRONTEND_URLS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

FRONTEND_URLS = [url.strip() for url in FRONTEND_URLS if url.strip()]


def require_authenticated_user(request: Request, response: Response):
    return get_authenticated_user_row(request, response)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(server_status_router)
app.include_router(login_sign_up_router)
app.include_router(forget_password_router)
app.include_router(contact_us_router)

protected_data_dependencies = [Depends(require_authenticated_user)]

app.include_router(data_router, dependencies=protected_data_dependencies)
app.include_router(cleaning_router, dependencies=protected_data_dependencies)
app.include_router(analysis_router, dependencies=protected_data_dependencies)
app.include_router(visualization_router, dependencies=protected_data_dependencies)
