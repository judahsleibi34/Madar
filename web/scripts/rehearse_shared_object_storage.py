#!/usr/bin/env python3
"""Isolated two-process immutable-storage rehearsal and bounded benchmark."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web/backend"


def _child_store():
    sys.path.insert(0, str(BACKEND))
    from services.immutable_object_storage import LoopbackHttpImmutableObjectStore
    return LoopbackHttpImmutableObjectStore(os.environ["DATA_IMMUTABLE_TEST_URL"])


def child_write(args) -> int:
    store = _child_store()
    started = time.perf_counter()
    descriptor = store.write(
        tenant_id=args.tenant, reservation_id=args.reservation,
        source_path=Path(args.path), suffix=".csv",
    )
    print(json.dumps({**descriptor.__dict__, "elapsed_seconds": time.perf_counter() - started}))
    return 0


def child_reconstruct(args) -> int:
    store = _child_store()
    from services.immutable_object_storage import ImmutableObject
    descriptor = ImmutableObject(**json.loads(args.descriptor))
    tracemalloc.start()
    started = time.perf_counter()
    read_started = time.perf_counter()
    content = store.read(tenant_id=args.tenant, descriptor=descriptor)
    read_seconds = time.perf_counter() - read_started
    hash_started = time.perf_counter()
    verified_hash = hashlib.sha256(content).hexdigest()
    hash_seconds = time.perf_counter() - hash_started
    state = {}
    for row in csv.DictReader(io.StringIO(content.decode("utf-8"))):
        record_id = row["_source_record_id"]
        if row["_change_operation"] == "delete":
            state.pop(record_id, None)
        else:
            state[record_id] = json.loads(row["_payload_json"])
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    state_hash = hashlib.sha256(canonical.encode()).hexdigest()
    output = io.StringIO(newline="")
    columns = sorted({key for value in state.values() for key in value})
    writer = csv.DictWriter(output, fieldnames=["_source_record_id", *columns], lineterminator="\n")
    writer.writeheader()
    for record_id in sorted(state):
        writer.writerow({"_source_record_id": record_id, **state[record_id]})
    checkpoint = Path(args.output)
    checkpoint.write_text(output.getvalue(), encoding="utf-8")
    checkpoint_upload_started = time.perf_counter()
    published = store.write(
        tenant_id=args.tenant, reservation_id=args.checkpoint_reservation,
        source_path=checkpoint, suffix=".csv",
    )
    checkpoint_upload_seconds = time.perf_counter() - checkpoint_upload_started
    _current, peak_python_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps({
        "descriptor": published.__dict__, "state_hash": state_hash,
        "records": len(state), "elapsed_seconds": time.perf_counter() - started,
        "read_seconds": read_seconds, "hash_seconds": hash_seconds,
        "verified_history_hash": verified_hash,
        "checkpoint_upload_seconds": checkpoint_upload_seconds,
        "peak_python_bytes": peak_python_bytes,
    }))
    return 0


def child_read(args) -> int:
    store = _child_store()
    from services.immutable_object_storage import ImmutableObject
    started = time.perf_counter()
    content = store.read(
        tenant_id=args.tenant, descriptor=ImmutableObject(**json.loads(args.descriptor)),
    )
    print(json.dumps({
        "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content),
        "elapsed_seconds": time.perf_counter() - started,
    }))
    return 0


class ObjectHandler(BaseHTTPRequestHandler):
    objects: dict[str, bytes] = {}
    lock = threading.Lock()

    def log_message(self, *_args):
        return

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", "0"))
        content = self.rfile.read(length)
        with self.lock:
            existing = self.objects.get(self.path)
            if existing is not None:
                self.send_response(412)
                self.end_headers()
                return
            self.objects[self.path] = content
        self.send_response(201)
        self.end_headers()

    def do_GET(self):
        with self.lock:
            content = self.objects.get(self.path)
        if content is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_DELETE(self):
        with self.lock:
            self.objects.pop(self.path, None)
        self.send_response(204)
        self.end_headers()


def _run_child(args: list[str], *, cwd: Path, url: str, check: bool = True):
    env = {**os.environ, "APP_ENV": "test", "DATA_IMMUTABLE_TEST_URL": url,
           "PYTHONPATH": str(BACKEND)}
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args], cwd=cwd, env=env,
        text=True, capture_output=True, check=False, timeout=30,
    )
    if check and result.returncode:
        raise RuntimeError(f"child_failed:{result.stderr.strip()}")
    return result


def parent() -> int:
    ObjectHandler.objects = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), ObjectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with tempfile.TemporaryDirectory() as root:
            process_a = Path(root) / "process-a"
            process_b = Path(root) / "process-b"
            process_a.mkdir()
            process_b.mkdir()
            history = process_a / "history.csv"
            payloads = (
                (f"record-{ordinal:06d}", "upsert", {
                    "value": ordinal, "label": f"Synthetic record {ordinal}",
                })
                for ordinal in range(1, 10_001)
            )
            with history.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "_source_record_id", "_change_operation", "_content_hash", "_payload_json",
                ], lineterminator="\n")
                writer.writeheader()
                for record_id, operation, payload in payloads:
                    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                    writer.writerow({"_source_record_id": record_id, "_change_operation": operation,
                                     "_content_hash": hashlib.sha256(body.encode()).hexdigest(),
                                     "_payload_json": body})
            write = _run_child([
                "--child-write", "--tenant", "1", "--reservation",
                "11111111-1111-4111-8111-111111111111", "--path", str(history),
            ], cwd=process_a, url=url)
            history_result = json.loads(write.stdout)
            history_descriptor = {key: history_result[key] for key in (
                "backend", "bucket", "object_key", "size_bytes", "sha256")}
            checkpoint_path = process_b / "checkpoint.csv"
            reconstructed = _run_child([
                "--child-reconstruct", "--tenant", "1", "--descriptor",
                json.dumps(history_descriptor), "--checkpoint-reservation",
                "22222222-2222-4222-8222-222222222222", "--output", str(checkpoint_path),
            ], cwd=process_b, url=url)
            reconstruction = json.loads(reconstructed.stdout)
            reopened = _run_child([
                "--child-read", "--tenant", "1", "--descriptor",
                json.dumps(reconstruction["descriptor"]),
            ], cwd=process_a, url=url)
            reopen_result = json.loads(reopened.stdout)
            duplicate = _run_child([
                "--child-write", "--tenant", "1", "--reservation",
                "11111111-1111-4111-8111-111111111111", "--path", str(history),
            ], cwd=process_b, url=url)
            duplicate_result = json.loads(duplicate.stdout)
            denied = _run_child([
                "--child-read", "--tenant", "2", "--descriptor",
                json.dumps(history_descriptor),
            ], cwd=process_b, url=url, check=False)
            if denied.returncode == 0:
                raise RuntimeError("cross_tenant_object_read_was_accepted")
            if duplicate_result["sha256"] != history_result["sha256"]:
                raise RuntimeError("duplicate_object_content_changed")
            if reopen_result["sha256"] != reconstruction["descriptor"]["sha256"]:
                raise RuntimeError("checkpoint_reopen_hash_mismatch")
            if reconstruction["verified_history_hash"] != history_result["sha256"]:
                raise RuntimeError("history_read_hash_mismatch")
            report = {
                "process_directories_distinct": process_a != process_b,
                "shared_application_directory": False,
                "transport": "loopback_http_in_memory_fixture",
                "history_bytes": history_result["size_bytes"],
                "history_sha256": history_result["sha256"],
                "checkpoint_bytes": reopen_result["size_bytes"],
                "checkpoint_sha256": reopen_result["sha256"],
                "state_hash": reconstruction["state_hash"],
                "records": reconstruction["records"],
                "upload_seconds": history_result["elapsed_seconds"],
                "upload_bytes_per_second": round(
                    history_result["size_bytes"] / history_result["elapsed_seconds"], 2
                ),
                "read_seconds": reconstruction["read_seconds"],
                "read_bytes_per_second": round(
                    history_result["size_bytes"] / reconstruction["read_seconds"], 2
                ),
                "hash_verification_seconds": reconstruction["hash_seconds"],
                "reconstruct_and_checkpoint_seconds": reconstruction["elapsed_seconds"],
                "checkpoint_upload_seconds": reconstruction["checkpoint_upload_seconds"],
                "checkpoint_reopen_seconds": reopen_result["elapsed_seconds"],
                "reconstruction_peak_python_bytes": reconstruction["peak_python_bytes"],
                "object_count": len(ObjectHandler.objects),
                "duplicate_idempotent": True,
                "cross_tenant_denied": True,
            }
            print(json.dumps(report, sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-write", action="store_true")
    parser.add_argument("--child-reconstruct", action="store_true")
    parser.add_argument("--child-read", action="store_true")
    parser.add_argument("--tenant", type=int, default=1)
    parser.add_argument("--reservation")
    parser.add_argument("--checkpoint-reservation")
    parser.add_argument("--path")
    parser.add_argument("--output")
    parser.add_argument("--descriptor")
    args = parser.parse_args()
    if args.child_write:
        return child_write(args)
    if args.child_reconstruct:
        return child_reconstruct(args)
    if args.child_read:
        return child_read(args)
    return parent()


if __name__ == "__main__":
    raise SystemExit(main())
