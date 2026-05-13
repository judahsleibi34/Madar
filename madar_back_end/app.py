from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from server_status import router as server_status_router
from auth import router as login_sign_up_router
from forget_password import router as forget_password_router
from contact_us import router as contact_us_router

app = FastAPI()

FRONTEND_URLS = os.getenv(
    "FRONTEND_URLS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

FRONTEND_URLS = [url.strip() for url in FRONTEND_URLS if url.strip()]

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