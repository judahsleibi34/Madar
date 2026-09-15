#!/usr/bin/env python3
"""Tiny HTTP processes used only by the isolated release-controller rehearsal."""

from __future__ import annotations

import argparse
import json
import os
import socket
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


STARTED = time.monotonic()


def reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


class Handler(BaseHTTPRequestHandler):
    role = ""

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, value: object) -> None:
        self.send(status, json.dumps(value, sort_keys=True).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.role == "schema":
            self.send_json(200, [{"schema_version": int(os.getenv("SCHEMA", "96"))}])
            return
        if self.role == "frontend":
            if self.path == "/assets/app.js":
                self.send(200, b"const api='https://api.madarportal.com';", "text/javascript")
            else:
                self.send(200, b'<script src="/assets/app.js"></script>', "text/html")
            return
        if self.role == "proxy":
            self.proxy()
            return
        if self.role in {"notification", "calendar", "deletion", "aux"}:
            delay = float(os.getenv("HEALTH_DELAY", "0"))
            self.send_json(200 if time.monotonic() - STARTED >= delay else 503, {"ok": True})
            return
        if self.path == "/health/live":
            self.send_json(200, {"live": True})
            return
        if self.path == "/health/version":
            identity = {
                "release_sha": os.environ["MADAR_RELEASE_SHA"],
                "build_timestamp": os.getenv("MADAR_BUILD_TIMESTAMP", "fixture"),
                "schema_compatible_min": int(
                    os.environ["SCHEMA_COMPATIBLE_MIN"]
                ),
                "schema_compatible_max": int(
                    os.environ["SCHEMA_COMPATIBLE_MAX"]
                ),
            }
            if os.getenv(
                "MADAR_OMIT_RELEASE_SLOT", "false"
            ).lower() != "true":
                identity["release_slot"] = os.environ["MADAR_RELEASE_SLOT"]
            self.send_json(200, identity)
            return
        if self.path == "/health/ready":
            required = os.getenv("NOTIFICATION_WORKER_REQUIRED", "false") == "true"
            checks = {
                "notification_worker": reachable("notification-worker", 8090),
                "calendar_sync_worker": reachable("calendar-sync-worker", 8091),
                "data_deletion_worker": reachable("data-deletion-worker", 8094),
            }
            components = {
                "environment": "ok", "database": "ok", "redis": "ok",
                "auth": "ok", "storage": "ok", "schema": "ok",
                "parser_isolation": "ok",
            }
            for name, healthy in checks.items():
                components[name] = "ok" if healthy else (
                    "unavailable" if required else "disabled"
                )
            ready = not required or all(checks.values())
            self.send_json(200 if ready else 503, {"ready": ready, "components": components})
            return
        self.send_json(404, {"error": "not_found"})

    def proxy(self) -> None:
        try:
            target = json.loads(Path(os.environ["ACTIVE_TARGET_FILE"]).read_text())
            port_key = "backend_port" if self.server.server_port == 8001 else "frontend_port"
            port = int(target[port_key])
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{self.path}", timeout=2) as response:
                self.send(response.status, response.read(), response.headers.get_content_type())
        except urllib.error.HTTPError as error:
            self.send(error.code, error.read(), "application/json")
        except Exception:
            self.send_json(503, {"ready": False, "components": {"proxy": "unavailable"}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=(
        "backend", "frontend", "notification", "calendar", "deletion",
        "aux", "proxy", "schema",
    ))
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    Handler.role = args.role
    default_ports = {
        "backend": 8000, "frontend": 8080, "notification": 8090,
        "calendar": 8091, "deletion": 8094, "aux": 8092,
        "schema": 54321,
    }
    ports = [8001, 3000] if args.role == "proxy" else [args.port or default_ports[args.role]]
    servers = [ThreadingHTTPServer(("0.0.0.0", port), Handler) for port in ports]
    if len(servers) == 1:
        servers[0].serve_forever()
    import threading
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())
