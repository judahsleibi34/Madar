#!/usr/bin/env python3
"""Durable loopback-only traffic proxy for staging blue/green drills."""

from __future__ import annotations

import http.client
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


TARGET = Path(os.environ["MADAR_ACTIVE_TARGET_FILE"])


def load_target() -> dict:
    payload = json.loads(TARGET.read_text(encoding="utf-8"))
    if payload.get("slot") not in {"blue", "green"}:
        raise ValueError("invalid staging target")
    for key in ("backend_port", "frontend_port"):
        value = int(payload[key])
        if not 1024 <= value <= 65535:
            raise ValueError("invalid staging port")
    return payload


def handler_for(component: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MadarStagingProxy/1"

        def log_message(self, _format, *_args):
            return

        def _dispatch(self):
            if self.path == "/__target":
                try:
                    payload = load_target()
                    body = json.dumps(payload, sort_keys=True).encode()
                    status = 200
                except Exception:
                    body = json.dumps({"status": "invalid_target"}).encode()
                    status = 503
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                target = load_target()
                port = int(target[f"{component}_port"])
                length = int(self.headers.get("Content-Length", "0") or 0)
                body = self.rfile.read(length) if length else None
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
                headers = {
                    name: value for name, value in self.headers.items()
                    if name.lower() not in {"host", "content-length", "connection"}
                }
                headers["X-Madar-Staging-Proxy"] = target["slot"]
                connection.request(self.command, self.path, body=body, headers=headers)
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
                connection.close()
            except Exception:
                body = b'{"status":"upstream_unavailable"}'
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        do_GET = _dispatch
        do_POST = _dispatch
        do_PATCH = _dispatch
        do_PUT = _dispatch
        do_DELETE = _dispatch
        do_OPTIONS = _dispatch

    return Handler


if __name__ == "__main__":
    load_target()
    backend = ThreadingHTTPServer(("127.0.0.1", int(os.getenv("BACKEND_PROXY_PORT", "18001"))), handler_for("backend"))
    frontend = ThreadingHTTPServer(("127.0.0.1", int(os.getenv("FRONTEND_PROXY_PORT", "13000"))), handler_for("frontend"))
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    frontend.serve_forever()
