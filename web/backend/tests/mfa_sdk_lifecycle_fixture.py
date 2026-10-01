"""Real pinned provider SDK and application session code; HTTP/database boundaries only."""
import base64
import json
import time
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI, Request, Response
from supabase import ClientOptions

import database
from routes import auth_routes, mfa_routes, admin_user_routes
from services import auth_service, mfa_login_service, request_security
from services.supabase_api_key import create_api_key_compatible_client
from mfa_cookie_fixture import ADMIN, MemoryRedis


class ProviderHttp:
    def __init__(self):
        self.now = int(time.time())
        self.tokens = {}
        self.identities = {}
        self.refresh_identities = {}
        self.refresh = {}
        self.challenges = set()
        self.serial = 0
        self.verify_count = 0
        self.refresh_count = 0
        self.calls = []
        self.downgrade = False
        self.factors = [{"id": "synthetic-factor", "factor_type": "totp", "status": "verified", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}]

    def user(self, identity=None):
        identity = identity or ADMIN["auth_id"]
        return {"id": identity, "aud": "authenticated", "app_metadata": {}, "user_metadata": {}, "email": ADMIN["email"], "email_confirmed_at": "2026-01-01T00:00:00Z", "created_at": "2026-01-01T00:00:00Z", "factors": self.factors if identity == ADMIN["auth_id"] else []}

    def issue(self, level, identity=None):
        identity = identity or ADMIN["auth_id"]
        self.serial += 1
        exp = self.now + 900
        def encode(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
        token = encode({"alg": "HS256", "typ": "JWT"}) + "." + encode({"sub": identity, "exp": exp, "aal": level, "jti": self.serial}) + ".c3ludGhldGlj"
        refresh = "synthetic-refresh-" + str(self.serial)
        self.tokens[token] = (level, exp)
        self.identities[token] = identity
        self.refresh_identities[refresh] = identity
        self.refresh[refresh] = level
        return {"access_token": token, "refresh_token": refresh, "token_type": "bearer", "expires_in": 900, "expires_at": exp, "user": self.user(identity)}

    def handle(self, request):
        path = request.url.path.removeprefix("/auth/v1/")
        self.calls.append((request.method, path))
        body = json.loads(request.content or b"{}")
        if path == "token":
            if request.url.params.get("grant_type") == "password":
                if body.get("password") != "synthetic-password":
                    return httpx.Response(400, json={"msg": "Invalid credentials"})
                return httpx.Response(200, json=self.issue("aal1"))
            level = self.refresh.pop(body.get("refresh_token"), None)
            if level is None:
                return httpx.Response(400, json={"msg": "Invalid refresh token"})
            self.refresh_count += 1
            return httpx.Response(200, json=self.issue("aal1" if self.downgrade else level, self.refresh_identities[body["refresh_token"]]))
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        active = self.tokens.get(token)
        if not active or active[1] <= self.now:
            return httpx.Response(401, json={"msg": "Expired or invalid JWT"})
        if path == "user":
            return httpx.Response(200, json=self.user(self.identities[token]))
        if path.startswith("factors/") and self.identities[token] != ADMIN["auth_id"]:
            return httpx.Response(403, json={"msg": "Factor belongs to another account"})
        if path == "factors/synthetic-factor/challenge":
            challenge = "synthetic-challenge-" + str(len(self.challenges) + self.serial)
            self.challenges.add(challenge)
            return httpx.Response(200, json={"id": challenge, "type": "totp", "expires_at": self.now + 300})
        if path == "factors/synthetic-factor/verify":
            if body.get("challenge_id") not in self.challenges or body.get("code") != "123456":
                return httpx.Response(400, json={"msg": "Invalid TOTP"})
            self.challenges.remove(body["challenge_id"])
            self.verify_count += 1
            return httpx.Response(200, json=self.issue("aal2"))
        raise AssertionError("Unexpected synthetic provider operation: " + path)


class ProfileStore:
    def __init__(self):
        self.single_row = False
        self.found = True
    def table(self, _name):
        return ProfileStore()
    def select(self, *_args): return self
    def eq(self, field, value):
        if field in {"auth_id", "id"} and value != ADMIN[field]:
            self.found = False
        return self
    def limit(self, *_args): return self
    def single(self):
        self.single_row = True
        return self
    def execute(self):
        row = dict(ADMIN) if self.found else None
        return SimpleNamespace(data=row if self.single_row else [row] if row else [])


def sdk_cookie_fixture(secure=True):
    stack = ExitStack()
    provider, store = ProviderHttp(), MemoryRedis()
    http_client = httpx.Client(transport=httpx.MockTransport(provider.handle))
    stack.callback(http_client.close)
    shared = create_api_key_compatible_client(database.SUPABASE_URL, database.SUPABASE_ANON_KEY, options=ClientOptions(auto_refresh_token=False, persist_session=False, httpx_client=http_client))
    stale = provider.issue("aal1")
    shared.auth.set_session(stale["access_token"], stale["refresh_token"])
    for target, name, value in [
        (database, "supabase", shared),
        (auth_service, "supabase", shared),
        (auth_service, "service_supabase", ProfileStore()),
        (auth_service, "COOKIE_SECURE", secure),
        (auth_routes, "supabase", shared),
        (auth_routes, "get_local_user_by_auth_id", lambda _id: dict(ADMIN)),
        (auth_routes, "enforce_auth_rate_limit", lambda *_args: None),
        (auth_routes, "get_user_security_settings", lambda _id: {"mfa_required": False}),
        (auth_routes, "get_billing_summary_for_tenant", lambda _id: {}),
        (auth_routes, "get_login_audit_user", lambda _email: None),
        (auth_routes, "record_security_event", lambda **_kw: None),
        (mfa_login_service, "COOKIE_SECURE", secure),
        (mfa_login_service, "pending_mfa_store", lambda: store),
        (mfa_routes, "supabase", shared),
        (mfa_routes, "service_supabase", ProfileStore()),
        (mfa_routes, "get_user_security_settings", lambda _id: {"mfa_required": False, "last_aal2_at": "2026-10-01T10:53:24Z"}),
        (mfa_routes, "mark_aal2_verified", lambda **_kw: None),
        (mfa_routes, "record_mfa_event", lambda **_kw: None),
        (mfa_routes, "record_security_event", lambda **_kw: None),
        (admin_user_routes, "list_users_with_features", lambda **_kw: {"items": [], "users": [{**ADMIN, "first_name": "Lifecycle", "last_name": "Administrator", "features": []}], "pagination": {"total_count": 1, "total_pages": 1, "page": 1}}),
    ]:
        stack.enter_context(patch.object(target, name, value))
    # Clock advancement exercises real SDK expiry; never replace refresh/session/AAL helpers.
    stack.enter_context(patch.object(time, "time", lambda: provider.now))
    auth_service._AUTH_REFRESH_REPLAY.clear()
    stack.callback(auth_service._AUTH_REFRESH_REPLAY.clear)
    backend = FastAPI()
    backend.include_router(auth_routes.router)
    backend.include_router(mfa_routes.router)
    backend.include_router(admin_user_routes.router)
    @backend.get("/lifecycle/protected")
    def protected(request: Request, response: Response):
        _, user = auth_service.require_system_admin(request, response, require_aal2=True)
        return {"user_id": user["id"]}
    @backend.middleware("http")
    async def security(request, call_next):
        denied = request_security.validate_cookie_write_origin(request, {"https://testserver", "http://127.0.0.1:5179"})
        if denied is not None: return denied
        denied = request_security.validate_csrf_token(request)
        return denied if denied is not None else await call_next(request)
    return backend, provider, store, shared, stack
