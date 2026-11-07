"""Offline database boundaries for tests exercising real candidate167 fences.

These records are synthetic, explicitly scoped test inputs, never integration
evidence or an alternative application authorization path.
"""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import jwt


def session_token(auth_id, session_id="offline-session"):
    return jwt.encode({"sub": auth_id, "session_id": session_id},
                      "offline-test-signing-material-not-a-provider-credential")


class Query:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self.filters = []
        self.fields = None
        self.maximum = None
        self.one = False

    def select(self, fields):
        self.fields = fields
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, count):
        assert count == 1
        self.maximum = count
        return self

    def single(self):
        self.one = True
        return self

    def execute(self):
        assert self.fields is not None and self.filters, "unscoped fixture query"
        rows = [row for row in self.rows
                if all(row.get(key) == value for key, value in self.filters)]
        if self.maximum is not None:
            rows = rows[:self.maximum]
        return SimpleNamespace(data=(rows[0] if rows else None) if self.one else rows)


class FenceClient:
    def __init__(self, identities=(), *, users=(), sessions=None, tables=None):
        self.identities = frozenset(identities)
        self.sessions = sessions if sessions is not None else set()
        self.calls = []
        self.tables = {
            "application_schema_state": [{"contract_key": "core", "schema_version": 167}],
            "users": list(users) or [
                {"id": user, "tenant_id": tenant, "account_status": "active"}
                for tenant, user in identities],
            **(tables or {}),
        }

    def table(self, name):
        assert name in self.tables, f"unexpected fixture table: {name}"
        return Query(self.tables[name])

    def rpc(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "account_fence_registration167":
            assert set(args) == {"p_tenant_id", "p_user_id"}
            allowed = (args["p_tenant_id"], args["p_user_id"]) in self.identities
        elif name == "account_session_allowed167":
            assert set(args) == {"p_auth_id", "p_session_id"}
            allowed = (args["p_auth_id"], args["p_session_id"]) in self.sessions
        else:
            raise AssertionError(f"unexpected fixture RPC: {name}")
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=allowed))


@contextmanager
def account_fixture(identities, *, tables=None):
    import database
    from services import account_work_fence
    client = FenceClient(identities, tables=tables)
    with TemporaryDirectory(prefix="madar-offline-fence-") as directory, \
            patch.object(database, "service_supabase", client), \
            patch.object(account_work_fence, "get_data_upload_dir", return_value=Path(directory)):
        yield client


@contextmanager
def route_account_fixture(identities):
    """Verify synthetic provider tokens, then execute real session/fence code."""
    from services import auth_service
    with account_fixture(identities) as client:
        client.tables["users"] = [
            {"id": user, "tenant_id": tenant, "auth_id": f"offline-{tenant}-{user}",
             "account_status": "active", "email_verified": True, "user_type": "user"}
            for tenant, user in identities]
        client.sessions.update((row["auth_id"], "offline-session") for row in client.tables["users"])

        def provider_user(token):
            from supabase_auth.errors import AuthApiError
            try:
                claims = jwt.decode(token, "offline-test-signing-material-not-a-provider-credential",
                                    algorithms=["HS256"])
            except jwt.PyJWTError as error:
                raise AuthApiError("Invalid offline fixture token", 401, None) from error
            if (claims.get("sub"), claims.get("session_id")) not in client.sessions:
                raise AuthApiError("Unknown offline fixture session", 401, None)
            return SimpleNamespace(user=SimpleNamespace(
                id=claims["sub"], email_confirmed_at="2026-01-01T00:00:00Z"))

        with patch.object(auth_service, "service_supabase", client), \
                patch.object(auth_service.supabase.auth, "get_user", side_effect=provider_user):
            yield client
