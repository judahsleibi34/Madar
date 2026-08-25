#!/usr/bin/env python3
"""Local-only Supabase facade for Madar staging drills.

PostgREST requests are proxied to the disposable PostgreSQL service. Auth and
Storage provider calls use deterministic synthetic fixtures and never contact a
real provider. This service must never be used as a production auth service.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


UPSTREAM = urlsplit(os.getenv("POSTGREST_URL", "http://postgrest:3000"))
JWT_SECRET = os.getenv("PGRST_JWT_SECRET", "")


def decode_token(value: str) -> dict:
    token = value.removeprefix("Bearer ").strip()
    parts = token.split(".")
    if len(parts) != 3 or not JWT_SECRET:
        return {}
    signing = f"{parts[0]}.{parts[1]}".encode()
    expected = hmac.new(JWT_SECRET.encode(), signing, hashlib.sha256).digest()
    signature = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
    if not hmac.compare_digest(expected, signature):
        return {}
    return json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))


class Handler(BaseHTTPRequestHandler):
    server_version = "MadarStagingGateway/1"

    def log_message(self, _format, *_args):
        return

    def _reply(self, status: int, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _auth(self):
        if self.path == "/auth/v1/health":
            return self._reply(200, {"status": "ok", "fixture": True})
        claims = decode_token(self.headers.get("Authorization", ""))
        subject = claims.get("sub")
        if self.path == "/auth/v1/user":
            if not subject:
                return self._reply(401, {"code": "bad_jwt"})
            return self._reply(200, {
                "id": subject,
                "email": claims.get("email", f"{subject}@staging.invalid"),
                "role": "authenticated",
                "app_metadata": {"provider": "email", "providers": ["email"]},
                "user_metadata": {},
                "aal": claims.get("aal", "aal1"),
            })
        if self.path.startswith("/auth/v1/admin/users/"):
            if self.command == "DELETE":
                return self._reply(200, {})
            if self.command == "GET":
                return self._reply(404, {"code": "user_not_found"})
        if "/factors" in self.path:
            return self._reply(200, [])
        return self._reply(404, {"code": "staging_auth_fixture_unimplemented"})

    def _storage(self):
        # Synthetic staging storage is modeled as already absent after delete.
        # Host-file deletion is exercised separately against real staging files.
        if self.command in {"DELETE", "POST"}:
            return self._reply(200, [])
        if self.command == "GET":
            return self._reply(200, [])
        return self._reply(404, {"code": "staging_storage_fixture_unimplemented"})

    def _proxy_rest(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        connection = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=15)
        headers = {
            name: value for name, value in self.headers.items()
            if name.lower() not in {"host", "content-length", "connection"}
        }
        try:
            connection.request(self.command, self.path.removeprefix("/rest/v1") or "/", body=body, headers=headers)
            response = connection.getresponse()
            content = response.read()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() not in {"connection", "transfer-encoding", "content-length"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(content)
        finally:
            connection.close()

    def _dispatch(self):
        if self.path.startswith("/rest/v1"):
            return self._proxy_rest()
        if self.path.startswith("/auth/v1"):
            return self._auth()
        if self.path.startswith("/storage/v1"):
            return self._storage()
        if self.path == "/health":
            return self._reply(200, {"status": "ok", "isolation": "staging_fixture"})
        return self._reply(404, {"code": "staging_gateway_not_found"})

    do_GET = _dispatch
    do_POST = _dispatch
    do_PATCH = _dispatch
    do_PUT = _dispatch
    do_DELETE = _dispatch
    do_HEAD = _dispatch


if __name__ == "__main__":
    if not JWT_SECRET:
        raise SystemExit("PGRST_JWT_SECRET is required")
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "5430"))), Handler).serve_forever()
