"""Optional automatic sign-in installed exclusively by the local API launcher."""
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class LocalTestLoginMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        from database import SUPABASE_URL
        if os.getenv("APP_ENV") != "development" or any(
            urlsplit(value).hostname not in LOOPBACK_HOSTS
            for value in (SUPABASE_URL, os.getenv("SUPABASE_DB_URL", ""))
        ):
            raise RuntimeError("Test auto-login requires the isolated local database")
        self.email = os.getenv("MADAR_TEST_EMAIL", "")
        self.password = os.getenv("MADAR_TEST_PASSWORD", "")
        if not self.email or not self.password:
            raise RuntimeError("Test auto-login credentials are missing")

    async def dispatch(self, request, call_next):
        if request.method != "GET" or request.url.path != "/auth/user_status":
            return await call_next(request)
        origin = request.headers.get("origin")
        if (
            not request.client or request.client.host not in LOOPBACK_HOSTS
            or request.url.hostname not in LOOPBACK_HOSTS
            or (origin and urlsplit(origin).hostname not in LOOPBACK_HOSTS)
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"detail": "Local test sign-in requires localhost"}, status_code=403)

        from classes import LogIn
        from routes.auth_routes import login, user_status
        cookies = Response()
        try:
            payload = await run_in_threadpool(user_status, request, cookies)
            if not payload.get("logged_in"):
                cookies = Response()
                payload = await run_in_threadpool(
                    login, LogIn(email=self.email, password=self.password), cookies, request,
                )
                # MFA/restricted login responses do not establish an ordinary session.
                payload["logged_in"] = bool(payload.get("user")) and not payload.get("restricted_session")
            response = JSONResponse(payload)
            response.raw_headers.extend(
                (key, value) for key, value in cookies.raw_headers
                if key.lower() not in {b"content-length", b"content-type"}
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code, headers=error.headers)
