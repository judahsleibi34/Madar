"""Minimal disposable Supabase URL-contract proxy for integration rehearsals."""

from __future__ import annotations

import os
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


UPSTREAM = os.environ.get("POSTGREST_UPSTREAM", "http://rest:3000").rstrip("/")
AUTH_TEST_TOKEN = os.environ.get("AUTH_TEST_TOKEN", "")
AUTH_TEST_USER_ID = os.environ.get("AUTH_TEST_USER_ID", "")
AUTH_TEST_EMAIL = os.environ.get("AUTH_TEST_EMAIL", "browser@example.invalid")
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self) -> None:
        if self.path == "/auth/v1/user" and AUTH_TEST_TOKEN and AUTH_TEST_USER_ID:
            supplied = self.headers.get("authorization", "")
            if supplied != f"Bearer {AUTH_TEST_TOKEN}":
                self._json(401, {"message": "invalid fixture session"})
                return
            self._json(200, {
                "id": AUTH_TEST_USER_ID,
                "aud": "authenticated",
                "role": "authenticated",
                "email": AUTH_TEST_EMAIL,
                "created_at": "2026-01-01T00:00:00Z",
                "email_confirmed_at": "2026-01-01T00:00:00Z",
                "confirmed_at": "2026-01-01T00:00:00Z",
                "user_metadata": {},
                "app_metadata": {"provider": "email", "providers": ["email"]},
            })
            return
        if not self.path.startswith("/rest/v1"):
            self.send_error(404)
            return
        path = self.path[len("/rest/v1"):] or "/"
        size = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(size) if size else None
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_HEADERS and key.lower() != "host"
        }
        with httpx.Client(timeout=30) as client:
            response = client.request(
                self.command, f"{UPSTREAM}{path}", headers=headers, content=body,
            )
        content = response.content
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in HOP_HEADERS and key.lower() != "content-length":
                self.send_header(key, value)
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _json(self, status: int, payload: dict) -> None:
        content = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = do_HEAD = _proxy

    def log_message(self, *_args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
