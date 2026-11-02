"""Central engine policy and isolated large-CSV deterministic analytics."""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

from fastapi import HTTPException

from data_analysis.core.analysis_core import ReportBuilder
from data_analysis.core.analysis_i18n import (
    direction_for,
    normalize_language,
    normalize_symbols,
    report_title,
)
from data_analysis.core.response_utils import sanitize_for_json


SMALL_DATASET_MAX_BYTES = 10 * 1024 * 1024
SMALL_DATASET_MAX_ROWS = 100_000
SCALABLE_CSV_MAX_BYTES = 250_000_000
SCALABLE_CSV_MAX_ROWS = 6_000_000
SCALABLE_DATE_MAX_BYTES = 100 * 1024 * 1024
SCALABLE_DATE_MAX_ROWS = 2_000_000
MAX_ANALYTICS_GROUPS = 500
MAX_ANALYTICS_COLUMNS = 256
MAX_ANALYTICS_RESULT_BYTES = 512 * 1024
# Polars maps substantially more virtual address space than resident memory.
# RLIMIT_AS admits the pinned runtime while the parent independently enforces
# the smaller resident-set ceiling below.
POLARS_WORKER_ADDRESS_SPACE_BYTES = 2048 * 1024 * 1024
POLARS_WORKER_RSS_BYTES = 384 * 1024 * 1024
POLARS_WORKER_FILE_BYTES = 256 * 1024 * 1024
POLARS_WORKER_TIMEOUT_SECONDS = 10.0
MAX_CONCURRENT_POLARS_ANALYTICS = 2
SUPPORTED_LARGE_METRICS = {
    "count", "sum", "mean", "min", "max", "distinct_count", "date_aggregate",
}
LARGE_METRIC_KEYS = {
    "operation", "label", "value_column", "group_column", "date_column",
    "aggregation", "period", "timezone", "start_date", "end_date",
}
_polars_slots = threading.BoundedSemaphore(MAX_CONCURRENT_POLARS_ANALYTICS)
_boundary_polars_slot = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class EngineDecision:
    engine: str
    reason: str
    estimated_cost: str
    bounded: bool


def _is_large(*, size_bytes: int, row_count: int | None) -> bool:
    return size_bytes > SMALL_DATASET_MAX_BYTES or (
        isinstance(row_count, int) and row_count > SMALL_DATASET_MAX_ROWS
    )


def select_engine(
    *, workload: str, file_format: str, size_bytes: int, row_count: int | None,
    operation: str | None = None, has_grouping: bool = False,
    cleaning_actions: bool = False, has_question: bool = False,
    polars_available: bool | None = None,
) -> EngineDecision:
    """Return a deterministic policy decision without touching dataset contents."""
    normalized_format = str(file_format or "").lower().lstrip(".")
    normalized_operation = str(operation or "").lower().strip()
    large = _is_large(size_bytes=max(0, int(size_bytes)), row_count=row_count)
    if not large:
        return EngineDecision("pandas", "small_compatible_dataset", "in_memory", True)
    if normalized_format != "csv":
        return EngineDecision("unsupported", "large_format_unsupported", "unbounded", False)
    if size_bytes > SCALABLE_CSV_MAX_BYTES or (
        isinstance(row_count, int) and row_count > SCALABLE_CSV_MAX_ROWS
    ):
        return EngineDecision("unsupported", "scalable_csv_limit_exceeded", "over_limit", False)
    if workload == "explore":
        return EngineDecision("duckdb", "bounded_relational_exploration", "bounded_scan", True)
    if workload != "metric":
        return EngineDecision("unsupported", "workload_unsupported", "unknown", False)
    if cleaning_actions:
        return EngineDecision("unsupported", "large_cleaning_pipeline_unsupported", "unverified", False)
    if has_question or not normalized_operation:
        return EngineDecision("unsupported", "large_freeform_analysis_unsupported", "unverified", False)
    if normalized_operation not in SUPPORTED_LARGE_METRICS:
        return EngineDecision("unsupported", "large_metric_unsupported", "unverified", False)
    if normalized_operation == "date_aggregate" and (
        size_bytes > SCALABLE_DATE_MAX_BYTES or (
            isinstance(row_count, int) and row_count > SCALABLE_DATE_MAX_ROWS
        )
    ):
        return EngineDecision(
            "unsupported", "large_date_metric_limit_exceeded", "over_limit", False,
        )
    available = importlib.util.find_spec("polars") is not None if polars_available is None else polars_available
    if not available:
        return EngineDecision("unsupported", "polars_runtime_unavailable", "unavailable", False)
    cost = "bounded_date_scan" if normalized_operation == "date_aggregate" else (
        "bounded_grouped_scan" if has_grouping else "bounded_scalar_scan"
    )
    return EngineDecision("polars", "verified_lazy_streaming_metric", cost, True)


def _limit_worker_resources() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (
        POLARS_WORKER_ADDRESS_SPACE_BYTES, POLARS_WORKER_ADDRESS_SPACE_BYTES,
    ))
    cpu_seconds = max(1, int(POLARS_WORKER_TIMEOUT_SECONDS))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (POLARS_WORKER_FILE_BYTES, POLARS_WORKER_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    os.umask(0o077)


def _worker_error(code: str, status_code: int = 422) -> HTTPException:
    messages = {
        "analytics_group_cardinality_exceeded": "The grouped result exceeds the bounded analytics limit.",
        "analytics_column_limit_exceeded": "The dataset has too many columns for bounded analytics.",
        "analytics_incompatible_schema": "The selected metric is not compatible with this CSV schema.",
        "analytics_invalid_date_field": "The selected date field is not compatible with bounded date analytics.",
        "analytics_result_limit_exceeded": "The bounded analytics result is too large.",
    }
    return HTTPException(status_code=status_code, detail={
        "code": code,
        "message": messages.get(code, "The deterministic metric could not be executed safely."),
    })


def _resident_bytes(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        return 0
    return 0


def _run_polars_worker(*, authorized_path: str, request: dict[str, Any]) -> dict[str, Any]:
    if not _polars_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail={
            "code": "adaptive_analytics_busy",
            "message": "The bounded analytics capacity is currently in use.",
        }, headers={"Retry-After": "1"})
    boundary_acquired = False
    try:
        source = Path(authorized_path)
        source_format = str(request.get("source_format") or "csv").lower()
        if source_format not in {"csv", "parquet"} \
                or source.suffix.lower() != f".{source_format}" or not source.is_file():
            raise _worker_error("analytics_incompatible_schema")
        with source.open("rb") as source_file:
            actual_size = os.fstat(source_file.fileno()).st_size
            original_size = int(request.get("source_size_bytes") or actual_size)
            if actual_size <= 0 or original_size <= 0 or original_size > SCALABLE_CSV_MAX_BYTES:
                raise HTTPException(status_code=413, detail={
                    "code": "scalable_csv_limit_exceeded",
                    "message": "The CSV exceeds the bounded analytics source limit.",
                })
            metric = request.get("metric") if isinstance(request.get("metric"), dict) else {}
            if str(metric.get("operation") or "").lower() == "date_aggregate" \
                    and original_size > SCALABLE_DATE_MAX_BYTES:
                raise HTTPException(status_code=413, detail={
                    "code": "large_date_metric_limit_exceeded",
                    "message": "Date aggregation exceeds its verified bounded source limit.",
                })
            if original_size > 100 * 1024 * 1024:
                boundary_acquired = _boundary_polars_slot.acquire(blocking=False)
                if not boundary_acquired:
                    raise HTTPException(status_code=429, detail={
                        "code": "adaptive_analytics_boundary_busy",
                        "message": "The boundary-size analytics capacity is currently in use.",
                    }, headers={"Retry-After": "1"})
            payload = json.dumps({**request, "source_fd": source_file.fileno()}, separators=(",", ":"))
            if len(payload.encode("utf-8")) > 16 * 1024:
                raise _worker_error("analytics_request_limit_exceeded")
            with tempfile.TemporaryDirectory(prefix="madar-polars-", dir=source.parent) as scratch:
                environment = {
                    "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                    "POLARS_MAX_THREADS": "1",
                    "POLARS_TEMP_DIR": scratch,
                    "TMPDIR": scratch,
                    "PYTHONHASHSEED": "0",
                    "TZ": "UTC",
                }
                worker = Path(__file__).with_name("adaptive_analytics_worker.py")
                result_path = Path(scratch) / "result.json"
                maximum_rss = 0
                with result_path.open("wb") as output:
                    process = subprocess.Popen(
                        [sys.executable, "-I", str(worker)], stdin=subprocess.PIPE,
                        stdout=output, stderr=subprocess.DEVNULL,
                        pass_fds=(source_file.fileno(),), cwd=scratch, env=environment,
                        preexec_fn=_limit_worker_resources,
                    )
                    assert process.stdin is not None
                    process.stdin.write(payload.encode("utf-8"))
                    process.stdin.close()
                    deadline = time.monotonic() + POLARS_WORKER_TIMEOUT_SECONDS
                    resource_exceeded = False
                    while process.poll() is None:
                        maximum_rss = max(maximum_rss, _resident_bytes(process.pid))
                        scratch_bytes = sum(
                            item.stat().st_size for item in Path(scratch).rglob("*") if item.is_file()
                        )
                        if maximum_rss > POLARS_WORKER_RSS_BYTES or scratch_bytes > POLARS_WORKER_FILE_BYTES:
                            resource_exceeded = True
                            process.kill()
                            break
                        if time.monotonic() >= deadline:
                            process.kill()
                            process.wait()
                            raise HTTPException(status_code=408, detail={
                                "code": "adaptive_analytics_deadline_exceeded",
                                "message": "The bounded analytics query exceeded its execution deadline.",
                            })
                        time.sleep(0.01)
                    process.wait()
                if resource_exceeded:
                    raise HTTPException(status_code=413, detail={
                        "code": "adaptive_analytics_resource_limit_exceeded",
                        "message": "The bounded analytics worker exceeded its memory or scratch-disk limit.",
                    })
                encoded = result_path.read_bytes()
                if len(encoded) > MAX_ANALYTICS_RESULT_BYTES:
                    raise _worker_error("analytics_result_limit_exceeded", 413)
                try:
                    result = json.loads(encoded.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise HTTPException(status_code=413, detail={
                        "code": "adaptive_analytics_resource_limit_exceeded",
                        "message": "The bounded analytics worker exceeded a resource limit.",
                    }) from error
                if process.returncode != 0 or not result.get("ok"):
                    code = str(result.get("code") or "adaptive_analytics_resource_limit_exceeded")
                    status = 413 if code.endswith("limit_exceeded") or code in {
                        "analytics_group_cardinality_exceeded",
                        "analytics_column_limit_exceeded",
                        "analytics_row_limit_exceeded",
                    } else 422
                    raise _worker_error(code, status)
                scratch_bytes = sum(
                    item.stat().st_size for item in Path(scratch).rglob("*") if item.is_file()
                )
                if scratch_bytes > POLARS_WORKER_FILE_BYTES:
                    raise _worker_error("analytics_scratch_limit_exceeded", 413)
                result["scratch_bytes"] = scratch_bytes
                result["peak_rss_bytes"] = maximum_rss
                return result
    except OSError as error:
        raise HTTPException(status_code=503, detail={
            "code": "adaptive_analytics_storage_unavailable",
            "message": "The authorized dataset or bounded scratch storage is unavailable.",
        }) from error
    finally:
        if boundary_acquired:
            _boundary_polars_slot.release()
        _polars_slots.release()


def _build_report(
    *, metric: dict[str, Any], worker: dict[str, Any], language: str, symbols: dict[str, Any],
) -> dict[str, Any]:
    operation = str(metric.get("operation") or "").lower()
    label = str(metric.get("label") or operation.replace("_", " ").title() or "Custom metric")
    normalized_language = normalize_language(language)
    normalized_symbols = normalize_symbols(symbols)
    report = ReportBuilder(
        report_id="custom_metric", domain="assisted",
        title=report_title("custom_metric", label, normalized_language),
        rows_used=int(worker["rows_used"]), columns_used=list(worker["columns_used"]),
        mappings=dict(metric), language=normalized_language, symbols=normalized_symbols,
    )
    rows = list(worker.get("rows") or [])
    group_column = metric.get("group_column")
    if operation == "date_aggregate":
        mappings = dict(worker.get("mappings") or {})
        report.mappings.update(mappings)
        for field, text in (
            ("invalid_date_count", "invalid date values were excluded from date grouping."),
            ("missing_date_count", "missing date values were excluded from date grouping."),
            ("outside_period_count", "valid dated rows were outside the selected reporting period."),
        ):
            if int(mappings.get(field) or 0):
                report.warnings.append(f"{int(mappings[field])} {text}")
        if mappings.get("partial_periods"):
            report.warnings.append(
                "The first or last grouped period is partial for the requested boundaries or observed dataset coverage."
            )
        if not rows:
            report.warnings.append("No valid dated rows fall inside the selected reporting period.")
        report.set_summary(
            f"Values were grouped by {mappings['period']} using the verified date field '{mappings['date_column']}'.",
            f"تم تجميع القيم حسب {mappings['period']} باستخدام حقل التاريخ المتحقق منه '{mappings['date_column']}'.",
        )
        report.add_table(label, rows)
        report.add_chart(label, "line", rows, "period", "value")
    else:
        report.set_summary(
            f"Custom metric '{label}' was calculated using {operation}.",
            f"تم حساب المؤشر المخصص '{label}' باستخدام {operation}.",
        )
        report.add_table(label, rows)
        if group_column:
            report.add_chart(label, "bar", rows, str(group_column), "value")
        elif rows:
            report.add_kpi(label, rows[0].get("value"))
    return report.to_dict()


def run_large_metric(
    *, authorized_path: str, metric: dict[str, Any], language: str, symbols: dict[str, Any],
    declared_rows: int | None, source_size_bytes: int | None = None,
    source_format: str = "csv",
) -> dict[str, Any]:
    if not isinstance(metric, dict) or set(metric) - LARGE_METRIC_KEYS:
        raise _worker_error("analytics_incompatible_schema")
    for key, value in metric.items():
        if value is not None and (not isinstance(value, str) or len(value) > (160 if key == "label" else 255)):
            raise _worker_error("analytics_incompatible_schema")
    worker = _run_polars_worker(
        authorized_path=authorized_path,
        request={
            "metric": metric,
            "declared_rows": declared_rows,
            "source_format": source_format,
            "source_size_bytes": source_size_bytes,
            "max_groups": MAX_ANALYTICS_GROUPS,
            "max_columns": MAX_ANALYTICS_COLUMNS,
            "max_rows": (
                SCALABLE_DATE_MAX_ROWS
                if str(metric.get("operation") or "").lower() == "date_aggregate"
                else SCALABLE_CSV_MAX_ROWS
            ),
        },
    )
    result = _build_report(metric=metric, worker=worker, language=language, symbols=symbols)
    normalized_language = normalize_language(language)
    normalized_symbols = normalize_symbols(symbols)
    response = sanitize_for_json({
        "rows_used": int(worker["rows_used"]),
        "columns_used": list(worker["columns_used"]),
        "warnings": [],
        "metadata": {
            "cleaning_actions_applied": [],
            "language": normalized_language,
            "direction": direction_for(normalized_language),
            "symbols": normalized_symbols,
            "profiles": {},
            "ai_connected": False,
            "analytics_engine": "polars",
            "engine_reason": "verified_lazy_streaming_metric",
            "scratch_bytes": int(worker.get("scratch_bytes") or 0),
            "worker_peak_rss_bytes": int(worker.get("peak_rss_bytes") or 0),
        },
        "result": result,
    })
    if len(json.dumps(response, default=str).encode("utf-8")) > MAX_ANALYTICS_RESULT_BYTES:
        raise _worker_error("analytics_result_limit_exceeded", 413)
    return response
