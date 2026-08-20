from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any

from data_analysis.io.data_reading import DataReadingNormal

logger = logging.getLogger(__name__)
MAX_CONTENT_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = 14 * 1024 * 1024 + 64 * 1024
MAX_RESULT_BYTES = 16 * 1024 * 1024
PARSE_SLOT = threading.BoundedSemaphore(value=1)


def parse_dataset(payload: dict[str, Any]) -> dict[str, Any]:
    input_path = payload.get("input_path")
    content_b64 = payload.get("content_b64")
    source_url = payload.get("source_url")
    content_type = payload.get("content_type")
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    if (
        tenant_id in (None, "")
        or user_id in (None, "")
    ):
        raise ValueError("invalid_parse_request")
    if content_b64 is not None:
        if (
            input_path is not None
            or not isinstance(content_b64, str)
            or not isinstance(source_url, str)
            or not source_url.startswith("https://")
            or len(source_url) > 4096
            or not isinstance(content_type, str)
            or len(content_type) > 512
        ):
            raise ValueError("invalid_parse_request")
        try:
            content = base64.b64decode(content_b64, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("invalid_parse_request") from error
        if not content or len(content) > MAX_CONTENT_BYTES:
            raise ValueError("remote_content_invalid")
        reader = DataReadingNormal(source_url)
        extension = reader._get_extension(source_url)
        normalized_content_type = content_type.lower()
        content_prefix = content.lstrip()[:128].lower()
        if (
            "text/html" in normalized_content_type
            or content_prefix.startswith(b"<!doctype html")
            or content_prefix.startswith(b"<html")
        ):
            raise ValueError("remote_content_invalid")
        if extension == ".csv" or "csv" in normalized_content_type:
            dataframe = reader._read_csv_bytes(content)
        elif extension in {".xls", ".xlsx"} or reader._is_excel_content_type(
            normalized_content_type
        ):
            dataframe = reader._read_excel_bytes(content, extension=extension)
        elif "application/json" in normalized_content_type or extension == ".json":
            try:
                decoded = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("remote_content_invalid") from error
            dataframe = reader._normalize_dataframe(reader._json_to_dataframe(decoded))
        else:
            raise ValueError("remote_content_invalid")
    else:
        if (
            not isinstance(input_path, str)
            or not input_path
            or len(input_path) > 4096
        ):
            raise ValueError("invalid_parse_request")
        if DataReadingNormal(input_path)._is_url(input_path):
            raise ValueError("remote_input_not_allowed")
        dataframe = DataReadingNormal(
            input_path, tenant_id=str(tenant_id), user_id=str(user_id)
        ).read(refresh=True)
    result = json.loads(dataframe.to_json(orient="split", date_format="iso"))
    bounded = {"columns": result.get("columns", []), "data": result.get("data", [])}
    encoded = json.dumps(bounded, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError("parse_result_too_large")
    return bounded


def _parse_child(payload: dict[str, Any], result_path: str, parse_target) -> None:
    try:
        result = parse_target(payload)
        envelope = {"ok": True, "result": result}
    except Exception as error:
        envelope = {"ok": False, "error_type": type(error).__name__}
    Path(result_path).write_text(
        json.dumps(envelope, separators=(",", ":")), encoding="utf-8"
    )


def parse_dataset_with_timeout(
    payload: dict[str, Any], *, parse_target=None, timeout_seconds: float | None = None
) -> dict[str, Any]:
    """Run one parse in a killable child inside the sandboxed worker container."""
    target = parse_target or parse_dataset
    configured_timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else float(os.getenv("PARSER_JOB_TIMEOUT_SECONDS", "55"))
    )
    bounded_timeout = max(1.0, min(configured_timeout, 295.0))
    result_path = ""
    process = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="madar-parser-result-", suffix=".json", delete=False
        ) as result_file:
            result_path = result_file.name
        # The HTTP server is multi-threaded, so use spawn rather than forking a
        # live interpreter with library locks held by another request thread.
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=_parse_child,
            args=(payload, result_path, target),
            daemon=True,
        )
        process.start()
        process.join(bounded_timeout)
        if process.is_alive():
            process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill()
                process.join(2)
            raise TimeoutError("parser_job_timeout")
        if process.exitcode != 0:
            raise RuntimeError("parser_child_failed")
        result_file_path = Path(result_path)
        if not result_file_path.is_file() or result_file_path.stat().st_size > MAX_RESULT_BYTES:
            raise RuntimeError("parser_child_result_invalid")
        envelope = json.loads(result_file_path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict) or envelope.get("ok") is not True:
            raise ValueError("parser_input_rejected")
        result = envelope.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("parser_child_result_invalid")
        return result
    finally:
        if process is not None and process.is_alive():
            process.kill()
            process.join(2)
        if result_path:
            Path(result_path).unlink(missing_ok=True)


class ParserWorkerHandler(BaseHTTPRequestHandler):
    server_version = "MadarParser/1"

    def log_message(self, _format: str, *_args) -> None:
        return

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._write_json(404, {"status": "not_found"})
            return
        self._write_json(200, {"status": "ok", "isolation": "parser_worker"})

    def do_POST(self) -> None:
        if self.path != "/parse":
            self._write_json(404, {"status": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._write_json(413, {"status": "invalid_request"})
            return
        try:
            started_at = time.monotonic()
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("invalid_parse_request")
            if not PARSE_SLOT.acquire(blocking=False):
                logger.warning("parser_worker.busy")
                self._write_json(503, {"status": "busy"})
                return
            try:
                result = parse_dataset_with_timeout(payload)
            finally:
                PARSE_SLOT.release()
        except ValueError as error:
            logger.warning(
                "parser_worker.rejected", extra={"error_code": str(error)[:80]}
            )
            self._write_json(422, {"status": "rejected"})
            return
        except Exception as error:
            logger.error(
                "parser_worker.failed", extra={"error_type": type(error).__name__}
            )
            self._write_json(500, {"status": "failed"})
            return
        logger.info(
            "parser_worker.succeeded",
            extra={"duration_ms": round((time.monotonic() - started_at) * 1000)},
        )
        self._write_json(200, result)


def main() -> int:
    # Keep this worker independent from database/service-role configuration.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    host = os.getenv("PARSER_WORKER_HEALTH_HOST", "0.0.0.0").strip()
    port = int(os.getenv("PARSER_WORKER_PORT", "8092"))
    server = ThreadingHTTPServer((host, port), ParserWorkerHandler)
    logger.info("parser_worker.started", extra={"port": port})
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
