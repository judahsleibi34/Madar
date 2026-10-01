"""Synthetic provider/Redis boundaries; real routes, crypto and cookie helpers."""
import time
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from routes import auth_routes, mfa_routes
from services import auth_service, mfa_login_service, request_security

ADMIN = {"id": 5, "auth_id": "synthetic-auth", "account_kind": "platform", "user_type": "admin", "email": "synthetic@example.com", "email_verified": True, "account_status": "active", "tenant_id": None}


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.deadlines = {}
    def set(self, key, value, ex=None):
        self.values[key] = value
        self.deadlines[key] = time.time() + ex if ex else float("inf")
        return True
    def get(self, key):
        if self.deadlines.get(key, 0) <= time.time():
            self.delete(key)
        return self.values.get(key)
    def delete(self, key):
        return int(self.values.pop(key, None) is not None)
    def getdel(self, key):
        value = self.get(key)
        self.delete(key)
        return value
    def incr(self, key):
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        return value
    def expire(self, key, seconds):
        self.deadlines[key] = time.time() + seconds
        return True


class Provider:
    def __init__(self):
        self.level = "aal1"
        self.auth = self
        self.mfa = self
        self.challenges = set()
    def set_session(self, access, refresh):
        assert access == "synthetic-aal1-access" and refresh == "synthetic-aal1-refresh"
        self.level = "aal1"
    def sign_in_with_password(self, payload):
        if payload["password"] != "synthetic-password":
            raise ValueError("Invalid credentials")
        self.level = "aal1"
        return SimpleNamespace(user=SimpleNamespace(id=ADMIN["auth_id"], email_confirmed_at="2026-01-01T00:00:00Z"), session=SimpleNamespace(access_token="synthetic-aal1-access", refresh_token="synthetic-aal1-refresh"))
    def list_factors(self):
        return {"all": [{"id": "synthetic-factor", "factor_type": "totp", "status": "verified"}]}
    def challenge(self, payload):
        if payload["factor_id"] != "synthetic-factor":
            raise ValueError("Factor belongs to another account")
        challenge = "challenge-" + str(len(self.challenges) + 1)
        self.challenges.add(challenge)
        return {"id": challenge}
    def verify(self, payload):
        if payload["challenge_id"] not in self.challenges or payload["code"] != "123456":
            raise ValueError("Wrong code")
        self.challenges.remove(payload["challenge_id"])
        self.level = "aal2"
        return {"session": {"access_token": "synthetic-aal2-access", "refresh_token": "synthetic-aal2-refresh"}}
    def get_authenticator_assurance_level(self):
        return {"current_level": self.level, "next_level": "aal2"}


class UserStore:
    def __init__(self, user):
        self.user = user
    def table(self, _name): return self
    def select(self, _fields): return self
    def eq(self, _field, _value): return self
    def limit(self, _value): return self
    def execute(self): return SimpleNamespace(data=[dict(self.user)])


def cookie_fixture(secure=False, normal=False):
    stack = ExitStack()
    provider, store = Provider(), MemoryRedis()
    user = {**ADMIN, "user_type": "user"} if normal else dict(ADMIN)
    for target, name, value in [
        (mfa_login_service, "pending_mfa_store", lambda: store),
        (mfa_login_service, "create_supabase_client", lambda _key: provider),
        (mfa_login_service, "COOKIE_SECURE", secure),
        (auth_service, "COOKIE_SECURE", secure),
        (auth_routes, "supabase", provider),
        (auth_routes, "get_local_user_by_auth_id", lambda _id: user),
        (auth_routes, "enforce_auth_rate_limit", lambda *_a: None),
        (auth_routes, "get_user_security_settings", lambda _id: {"mfa_required": False}),
        (auth_routes, "get_billing_summary_for_tenant", lambda _id: {}),
        (auth_routes, "get_login_audit_user", lambda _email: None),
        (auth_routes, "record_security_event", lambda **_kw: None),
        (mfa_routes, "service_supabase", UserStore(user)),
        (mfa_routes, "mark_aal2_verified", lambda **_kw: None),
        (mfa_routes, "record_security_event", lambda **_kw: None),
        (mfa_routes, "record_mfa_event", lambda **_kw: None),
    ]:
        stack.enter_context(patch.object(target, name, value))
    backend = FastAPI()
    backend.include_router(auth_routes.router)
    backend.include_router(mfa_routes.router)
    @backend.middleware("http")
    async def security(request, call_next):
        blocked = request_security.validate_cookie_write_origin(request, {"http://127.0.0.1:5179", "https://testserver", "http://testserver"})
        if blocked is not None: return blocked
        blocked = request_security.validate_csrf_token(request)
        return blocked if blocked is not None else await call_next(request)
    # The mount models the deployed /api prefix while still testing direct routes.
    app = FastAPI()
    app.middleware("http")(security)
    app.include_router(auth_routes.router)
    app.include_router(mfa_routes.router)
    app.mount("/api", backend)
    return app, provider, store, stack
