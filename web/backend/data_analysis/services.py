import logging
import os
import re
import hashlib
import json
import time
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
import requests
from fastapi import HTTPException, UploadFile

from data_analysis.assisted.assisted_analysis import AssistedAnalysis
from data_analysis.cleaning.data_cleaning import DataCleaning
from data_analysis.core.analysis_catalog import ANALYSIS_CATALOG
from data_analysis.core.analysis_i18n import (
    direction_for,
    localized_catalog,
    normalize_language,
    normalize_symbols,
)
from data_analysis.core.response_utils import dataframe_preview, sanitize_for_json
from data_analysis.io.data_reading import DataReadingNormal, RemoteDatasetUrlsDisabledError
from data_analysis.router import AnalysisRouter
from data_analysis.visualization.visualization import DataVisualization
from services.spreadsheet_security import sanitize_spreadsheet_dataframe
from services.immutable_object_storage import (
    IMMUTABLE_BUCKET,
    ImmutableObject,
    ImmutableObjectError,
    ObjectErrorCategory,
    configured_store,
    generated_object_key,
)
from services.storage_quota_service import (
    StorageSafetyError,
    ensure_disk_capacity,
    finish_storage,
    finish_immutable_storage,
    mark_immutable_storage_ambiguous,
    prepare_immutable_storage,
    release_storage,
    reserve_storage,
    sha256_file,
    verify_immutable_storage,
)
from services.upload_config import (
    assert_path_within_root,
    get_data_upload_dir,
    get_private_charts_dir,
    resolve_private_user_file_path,
    safe_scope_part,
    validate_safe_filename,
)

logger = logging.getLogger(__name__)

PREVIEW_LIMIT = 100
MAX_DATASET_UPLOAD_BYTES = int(os.getenv("MAX_DATASET_UPLOAD_BYTES", "250000000"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(MAX_DATASET_UPLOAD_BYTES)))
MAX_CONCURRENT_DATASET_UPLOADS = max(1, int(os.getenv("MAX_CONCURRENT_DATASET_UPLOADS", "2")))
LARGE_DATASET_THRESHOLD_BYTES = int(os.getenv("LARGE_DATASET_THRESHOLD_BYTES", str(50 * 1024 * 1024)))
MAX_FULL_DATAFRAME_BYTES = int(os.getenv("MAX_FULL_DATAFRAME_BYTES", str(50 * 1024 * 1024)))
CSV_CHUNK_SIZE_ROWS = int(os.getenv("CSV_CHUNK_SIZE_ROWS", "3000"))
MAX_PREVIEW_ROWS = int(os.getenv("MAX_PREVIEW_ROWS", "120"))
MAX_EXCEL_UPLOAD_BYTES = int(os.getenv("MAX_EXCEL_UPLOAD_BYTES", str(50 * 1024 * 1024)))
CSV_DUPLICATE_TRACK_ROWS = int(os.getenv("CSV_DUPLICATE_TRACK_ROWS", "100000"))
UPLOAD_CHUNK_SIZE = 1024 * 1024
STALE_UPLOAD_PART_SECONDS = int(os.getenv("STALE_UPLOAD_PART_SECONDS", str(24 * 60 * 60)))
MAX_STALE_PARTS_PER_UPLOAD = 64
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xls", ".xlsx"}
ALLOWED_CHART_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".html"}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


def safe_scope_value(value: object) -> str:
    text = str(value).strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise HTTPException(status_code=400, detail="Invalid user storage scope.")

    return text


def get_user_upload_dir(tenant_id: str, user_id: str) -> Path:
    scoped_dir = get_data_upload_dir() / safe_scope_part("tenant", tenant_id) / safe_scope_part("user", user_id)
    scoped_dir.mkdir(parents=True, exist_ok=True)
    return scoped_dir


def get_user_chart_dir(tenant_id: str, user_id: str) -> Path:
    scoped_dir = get_private_charts_dir() / safe_scope_part("tenant", tenant_id) / safe_scope_part("user", user_id)
    scoped_dir.mkdir(parents=True, exist_ok=True)
    return scoped_dir


def validate_chart_id(chart_id: str) -> str:
    return validate_safe_filename(
        chart_id,
        allowed_extensions=ALLOWED_CHART_EXTENSIONS,
        error_type=lambda message: HTTPException(status_code=403, detail="Chart access is not allowed."),
    )


def resolve_private_chart_path(chart_id: str, *, tenant_id: str, user_id: str) -> Path:
    safe_chart_id = validate_chart_id(chart_id)
    chart_root = get_user_chart_dir(tenant_id, user_id).resolve()
    chart_path = assert_path_within_root(
        chart_root / safe_chart_id,
        chart_root,
        error=HTTPException(status_code=403, detail="Chart access is not allowed."),
    )

    if not chart_path.is_file():
        global_chart_root = get_private_charts_dir().resolve()
        for existing_chart in global_chart_root.glob(f"tenant_*/user_*/{safe_chart_id}"):
            if existing_chart.resolve() != chart_path and existing_chart.is_file():
                raise HTTPException(status_code=403, detail="Chart access is not allowed.")
        raise HTTPException(status_code=404, detail="Chart was not found.")

    return chart_path


def build_private_chart_url(*, user_id: str, chart_id: str) -> str:
    return f"/users/{user_id}/visualization/charts/{validate_chart_id(chart_id)}"


def _is_remote_dataset(input_path: str) -> bool:
    if DataReadingNormal(input_path)._is_url(input_path):
        return True
    return False


def _private_dataset_path_from_identifier(input_path: str, *, tenant_id: str, user_id: str) -> Path:
    requested = Path(input_path)
    if not requested.is_absolute() and len(requested.parts) == 1:
        safe_name = validate_safe_filename(
            requested.name,
            allowed_extensions=ALLOWED_UPLOAD_EXTENSIONS,
            error_type=ValueError,
        )
        try:
            return resolve_private_user_file_path(
                str(get_user_upload_dir(tenant_id, user_id) / safe_name),
                storage_root=get_data_upload_dir(),
                tenant_id=tenant_id,
                user_id=user_id,
                allowed_extensions=ALLOWED_UPLOAD_EXTENSIONS,
            )
        except FileNotFoundError:
            upload_root = get_data_upload_dir().resolve()
            for existing_file in upload_root.glob(f"tenant_*/user_*/{safe_name}"):
                if existing_file.is_file():
                    raise PermissionError("File belongs to a different storage scope")
            raise

    return resolve_private_user_file_path(
        input_path,
        storage_root=get_data_upload_dir(),
        tenant_id=tenant_id,
        user_id=user_id,
        allowed_extensions=ALLOWED_UPLOAD_EXTENSIONS,
    )


def _processing_mode(file_size: int) -> str:
    return "large_dataset" if file_size > LARGE_DATASET_THRESHOLD_BYTES else "small_dataset"


def _raise_if_full_dataframe_blocked(file_path: Path, *, operation: str) -> None:
    if file_path.stat().st_size > MAX_FULL_DATAFRAME_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"This dataset is too large for {operation}. "
                "Use the preview/read endpoint for chunked metadata, or upload a smaller dataset."
            ),
        )


def authorize_dataset_input_path(
    input_path: str,
    *,
    tenant_id: str,
    user_id: str,
    require_small: bool = False,
    operation: str = "this operation",
) -> str:
    if _is_remote_dataset(input_path):
        return input_path

    try:
        file_path = _private_dataset_path_from_identifier(input_path, tenant_id=tenant_id, user_id=user_id)
        if require_small:
            _raise_if_full_dataframe_blocked(file_path, operation=operation)
        return str(file_path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Uploaded data file was not found.") from error
    except (PermissionError, ValueError) as error:
        raise HTTPException(status_code=403, detail="Dataset access is not allowed.") from error


def build_authorized_cleaner(input_path: str, *, tenant_id: str, user_id: str) -> DataCleaning:
    return DataCleaning(
        authorize_dataset_input_path(
            input_path,
            tenant_id=tenant_id,
            user_id=user_id,
            require_small=True,
            operation="full-dataframe analysis",
        ),
        tenant_id=tenant_id,
        user_id=user_id,
    )


def validate_upload_filename(filename: str) -> str:
    clean_filename = (filename or "").strip()

    if (
        not clean_filename
        or "\x00" in clean_filename
        or "/" in clean_filename
        or "\\" in clean_filename
        or Path(clean_filename).name != clean_filename
        or ".." in Path(clean_filename).parts
    ):
        raise HTTPException(status_code=400, detail="Invalid upload filename.")

    extension = Path(clean_filename).suffix.lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .xls, and .xlsx files are supported.",
        )

    return extension


def validate_upload_content_type(content_type: str | None) -> None:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()

    if normalized not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported upload content type.",
        )


def cleanup_stale_upload_parts(upload_dir: Path, *, now: float | None = None) -> int:
    """Remove only expired partial files created by Madar's streaming writer."""
    removed = 0
    cutoff = (time.time() if now is None else float(now)) - STALE_UPLOAD_PART_SECONDS
    for pattern in (".*.csv.uploading", ".*.xls.uploading", ".*.xlsx.uploading"):
        for candidate in upload_dir.glob(pattern):
            try:
                if candidate.is_file() and candidate.stat().st_mtime < cutoff:
                    candidate.unlink()
                    removed += 1
                    if removed >= MAX_STALE_PARTS_PER_UPLOAD:
                        return removed
            except FileNotFoundError:
                continue
            except OSError:
                logger.warning("data.upload.stale_partial_cleanup_failed", extra={"path": candidate.name})
    return removed


async def stream_upload_to_private_file(
    file: UploadFile, target_path: Path, *, progress_callback=None,
) -> tuple[int, str]:
    bytes_written = 0
    chunks_since_progress = 0
    max_upload_bytes = min(MAX_DATASET_UPLOAD_BYTES, MAX_UPLOAD_BYTES)
    digest = hashlib.sha256()
    partial_path = target_path.with_name(f".{target_path.name}.uploading")

    try:
        with partial_path.open("xb") as output:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)

                if not chunk:
                    break

                bytes_written += len(chunk)
                chunks_since_progress += 1

                if bytes_written > max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file is too large.",
                    )

                digest.update(chunk)
                output.write(chunk)
                if progress_callback is not None and chunks_since_progress >= 16:
                    progress_callback()
                    chunks_since_progress = 0
            output.flush()
            os.fsync(output.fileno())
        os.replace(partial_path, target_path)
    except BaseException:
        partial_path.unlink(missing_ok=True)
        raise

    if bytes_written == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    return bytes_written, digest.hexdigest()


def _update_dtype_map(current: dict[str, str], chunk: pd.DataFrame) -> None:
    for column, dtype in chunk.dtypes.items():
        dtype_name = str(dtype)
        column_name = str(column)
        existing = current.get(column_name)
        if existing is None:
            current[column_name] = dtype_name
        elif existing != dtype_name:
            current[column_name] = "mixed"


def _exact_duplicate_count_from_hashes(
    chunk: pd.DataFrame,
    seen_hashes: set[tuple],
    *,
    max_tracked_rows: int,
) -> tuple[int, bool]:
    duplicates = 0
    limited = False
    normalized_chunk = chunk.astype(object).where(pd.notnull(chunk), None)
    for values in normalized_chunk.itertuples(index=False, name=None):
        if len(seen_hashes) >= max_tracked_rows:
            limited = True
            break
        row_hash = tuple(values)
        if row_hash in seen_hashes:
            duplicates += 1
        else:
            seen_hashes.add(row_hash)
    return duplicates, limited


def extract_csv_metadata(file_path: Path, *, original_filename: str | None = None,
                         progress_callback=None) -> dict:
    file_size = file_path.stat().st_size
    preview_frames: list[pd.DataFrame] = []
    row_count = 0
    columns: list[str] = []
    dtypes: dict[str, str] = {}
    missing_counts: dict[str, int] = {}
    duplicate_count = 0
    duplicate_count_limited = False
    seen_hashes: set[tuple] = set()
    last_error: Exception | None = None
    chunks_since_progress = 0
    try:
        with file_path.open("rb") as csv_file:
            DataReadingNormal(str(file_path))._reject_binary_csv(csv_file.read(4096))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    for encoding in DataReadingNormal.CSV_ENCODINGS:
        try:
            with pd.read_csv(
                file_path,
                encoding=encoding,
                chunksize=CSV_CHUNK_SIZE_ROWS,
                on_bad_lines="error",
            ) as chunks:
                for chunk in chunks:
                    chunks_since_progress += 1
                    if progress_callback is not None and chunks_since_progress >= 32:
                        progress_callback()
                        chunks_since_progress = 0
                    if not columns:
                        columns = [str(column) for column in chunk.columns]
                        if len(columns) > DataReadingNormal.MAX_COLUMNS:
                            raise HTTPException(
                                status_code=413,
                                detail="CSV column count exceeds the supported upload limit.",
                            )
                        missing_counts = {column: 0 for column in columns}

                    row_count += int(len(chunk))
                    _update_dtype_map(dtypes, chunk)
                    chunk_duplicates, duplicate_limited = _exact_duplicate_count_from_hashes(
                        chunk,
                        seen_hashes,
                        max_tracked_rows=CSV_DUPLICATE_TRACK_ROWS,
                    )
                    duplicate_count += chunk_duplicates
                    duplicate_count_limited = duplicate_count_limited or duplicate_limited

                    chunk_missing = chunk.isna().sum()
                    for column in columns:
                        missing_counts[column] = missing_counts.get(column, 0) + int(chunk_missing.get(column, 0))

                    preview_needed = MAX_PREVIEW_ROWS - sum(len(frame) for frame in preview_frames)
                    if preview_needed > 0:
                        preview_frames.append(chunk.head(preview_needed))

            preview_df = pd.concat(preview_frames, ignore_index=True) if preview_frames else pd.DataFrame(columns=columns)
            return sanitize_for_json(
                {
                    "dataset_id": file_path.name,
                    "file_path": file_path.name,
                    "original_filename": original_filename or file_path.name,
                    "storage": "private",
                    "file_size": int(file_size),
                    "processing_mode": _processing_mode(file_size),
                    "format": "csv",
                    "rows": int(row_count),
                    "columns": [sanitize_for_json(column) for column in columns],
                    "column_count": int(len(columns)),
                    "dtypes": dtypes,
                    "missing_values": missing_counts,
                    "duplicate_count": int(duplicate_count),
                    "duplicate_count_mode": "partial_hash_sample" if duplicate_count_limited else "exact_hash",
                    "preview": dataframe_preview(preview_df, MAX_PREVIEW_ROWS),
                    "preview_rows": int(len(preview_df)),
                    "preview_is_partial": bool(row_count > len(preview_df)),
                    "parse_errors": [],
                    "encoding": encoding,
                    "delimiter": ",",
                }
            )
        except UnicodeDecodeError as error:
            last_error = error
        except HTTPException:
            raise
        except (pd.errors.ParserError, ValueError) as error:
            last_error = error
            break
        except Exception as error:
            last_error = error
            break

    raise HTTPException(
        status_code=400,
        detail=f"Could not parse CSV file: {last_error}",
    )


def extract_csv_metadata_via_worker(
    file_path: Path, *, original_filename: str, tenant_id: str, user_id: str,
) -> dict:
    worker_url = os.getenv("PARSER_WORKER_URL", "http://parser-worker:8092/parse").strip()
    timeout_seconds = max(
        1.0, min(float(os.getenv("PARSER_WORKER_TIMEOUT_SECONDS", "60")), 300.0),
    )
    max_result_bytes = 2 * 1024 * 1024
    try:
        response = requests.post(
            worker_url,
            json={
                "operation": "csv_metadata", "input_path": str(file_path),
                "original_filename": original_filename,
                "tenant_id": str(tenant_id), "user_id": str(user_id),
            },
            timeout=(2.0, timeout_seconds), stream=True, allow_redirects=False,
        )
    except (OSError, requests.RequestException) as error:
        raise HTTPException(status_code=503, detail={
            "code": "parser_worker_unavailable",
            "message": "The isolated CSV metadata worker is unavailable.",
        }) from error
    try:
        if response.status_code == 503:
            raise HTTPException(status_code=503, detail={
                "code": "parser_worker_busy",
                "message": "The isolated CSV metadata capacity is currently in use.",
            }, headers={"Retry-After": "1"})
        if response.status_code != 200:
            raise HTTPException(status_code=422, detail={
                "code": "csv_metadata_rejected",
                "message": "The CSV could not be inspected safely.",
            })
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > max_result_bytes:
            raise HTTPException(status_code=413, detail="CSV metadata result is too large.")
        payload = response.raw.read(max_result_bytes + 1, decode_content=False)
        if len(payload) > max_result_bytes:
            raise HTTPException(status_code=413, detail="CSV metadata result is too large.")
        result = json.loads(payload.decode("utf-8"))
        if not isinstance(result, dict) or result.get("format") != "csv" \
                or not isinstance(result.get("rows"), int) \
                or not isinstance(result.get("columns"), list):
            raise ValueError("invalid_csv_metadata_result")
        return result
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=503, detail={
            "code": "parser_worker_invalid_response",
            "message": "The isolated CSV metadata worker returned an invalid response.",
        }) from error
    finally:
        response.close()


def build_dataset_response(df, *, file_path: str, original_filename: str | None = None):
    dataset_id = Path(file_path).name
    return {
        "dataset_id": dataset_id,
        "file_path": dataset_id,
        "original_filename": original_filename or dataset_id,
        "storage": "private",
        "file_size": int(Path(file_path).stat().st_size) if Path(file_path).is_file() else None,
        "processing_mode": _processing_mode(Path(file_path).stat().st_size) if Path(file_path).is_file() else "small_dataset",
        "format": Path(file_path).suffix.lower().removeprefix(".") or None,
        "rows": int(len(df)),
        "columns": [sanitize_for_json(column) for column in df.columns],
        "column_count": int(len(df.columns)),
        "preview": dataframe_preview(df, MAX_PREVIEW_ROWS),
        "preview_rows": min(int(len(df)), MAX_PREVIEW_ROWS),
        "preview_is_partial": bool(len(df) > MAX_PREVIEW_ROWS),
    }


def read_dataset(input_path: str, *, tenant_id: str, user_id: str):
    reader = DataCleaning(
        authorize_dataset_input_path(
            input_path,
            tenant_id=tenant_id,
            user_id=user_id,
            require_small=True,
            operation="full-dataframe processing",
        ),
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return reader.read()


async def process_upload(
    file: UploadFile,
    *,
    tenant_id: str,
    user_id: str,
    metadata_persister=None,
    metadata_failure_resolver=None,
    storage_reservation_persister=None,
    storage_object_persister=None,
    storage_object_failure_resolver=None,
    lifecycle_heartbeat=None,
    shared_immutable: bool = False,
    immutable_store=None,
    cancelled=lambda: False,
    prevalidated_csv_shape: tuple[int, tuple[str, ...]] | None = None,
):
    filename = file.filename or ""
    file_extension = validate_upload_filename(filename)
    validate_upload_content_type(file.content_type)

    unique_filename = f"{uuid4().hex}{file_extension}"
    upload_dir = get_user_upload_dir(tenant_id, user_id)
    cleanup_stale_upload_parts(upload_dir)
    try:
        ensure_disk_capacity(
            upload_dir,
            incoming_bytes=min(MAX_DATASET_UPLOAD_BYTES, MAX_UPLOAD_BYTES)
            * MAX_CONCURRENT_DATASET_UPLOADS,
        )
    except StorageSafetyError as error:
        raise HTTPException(status_code=507, detail={"code": error.code, "message": "Storage capacity is unavailable."}) from error
    file_path = upload_dir / unique_filename
    file_size, content_hash = await stream_upload_to_private_file(
        file, file_path, progress_callback=lifecycle_heartbeat
    )
    if lifecycle_heartbeat is not None:
        lifecycle_heartbeat()

    try:
        storage_reservation_id = reserve_storage(
            tenant_id=int(tenant_id),
            user_id=int(user_id),
            category="dataset",
            size_bytes=file_size,
            storage_root=upload_dir,
        )
    except StorageSafetyError as error:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=507, detail={"code": error.code, "message": "Storage quota is unavailable."}) from error

    if storage_reservation_persister is not None:
        try:
            storage_reservation_persister(storage_reservation_id)
        except Exception as error:
            accounting_released = False
            try:
                finish_storage(reservation_id=storage_reservation_id, succeeded=False)
                accounting_released = True
            except Exception:
                logger.exception(
                    "data.upload.reservation_attachment_compensation_failed",
                    extra={"tenant_id": tenant_id, "user_id": user_id},
                )
            if accounting_released:
                file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "ingestion_reservation_attachment_failed",
                    "message": "The import could not safely start. Retry with a new request key.",
                },
            ) from error

    if file_extension in {".xls", ".xlsx"} and file_size > MAX_EXCEL_UPLOAD_BYTES:
        file_path.unlink(missing_ok=True)
        finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        raise HTTPException(
            status_code=413,
            detail=(
                "Excel uploads over the configured limit are not supported. "
                "Please convert the workbook to CSV for large datasets."
            ),
        )

    try:
        if lifecycle_heartbeat is not None:
            lifecycle_heartbeat()
        if prevalidated_csv_shape is not None:
            if file_extension != ".csv":
                raise RuntimeError("prevalidated_csv_shape_requires_csv")
            row_count, columns = prevalidated_csv_shape
            if row_count < 0 or row_count > 100_000 or not columns \
                    or len(columns) > DataReadingNormal.MAX_COLUMNS \
                    or any(not isinstance(column, str) or not column for column in columns):
                raise RuntimeError("prevalidated_csv_shape_invalid")
            response = {
                "dataset_id": file_path.name,
                "file_path": file_path.name,
                "original_filename": filename,
                "storage": "private",
                "file_size": int(file_size),
                "processing_mode": _processing_mode(file_size),
                "format": "csv",
                "rows": int(row_count),
                "columns": [sanitize_for_json(column) for column in columns],
                "column_count": len(columns),
                "preview": [],
                "preview_rows": 0,
                "preview_is_partial": bool(row_count),
            }
        elif file_extension == ".csv":
            if DataReadingNormal._isolated_parser_enabled():
                response = extract_csv_metadata_via_worker(
                    file_path, original_filename=filename,
                    tenant_id=tenant_id, user_id=user_id,
                )
            else:
                response = extract_csv_metadata(
                    file_path, original_filename=filename,
                    progress_callback=lifecycle_heartbeat,
                )
        else:
            _raise_if_full_dataframe_blocked(file_path, operation="dataset preview")
            reader = DataCleaning(str(file_path), tenant_id=tenant_id, user_id=user_id)
            df = reader.read()
            response = build_dataset_response(
                df,
                file_path=str(file_path),
                original_filename=filename,
            )
    except HTTPException:
        file_path.unlink(missing_ok=True)
        finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        raise

    storage_key = f"tenant_{tenant_id}/user_{user_id}/{unique_filename}"
    shared_descriptor = None
    shared_store = None
    if shared_immutable:
        # Shared objects use a reservation-derived logical key so reconciliation
        # can finish an interrupted transfer without relying on process-local state.
        storage_key = f"tenant_{tenant_id}/user_{user_id}/{storage_reservation_id}{file_extension}"
        shared_store = immutable_store or configured_store()
        shared_descriptor = ImmutableObject(
            backend=getattr(shared_store, "backend", "supabase_private"),
            bucket=IMMUTABLE_BUCKET,
            object_key=generated_object_key(
                tenant_id=int(tenant_id), reservation_id=storage_reservation_id,
                sha256=content_hash, suffix=file_extension,
            ),
            size_bytes=file_size,
            sha256=content_hash,
        )
        try:
            prepare_immutable_storage(
                reservation_id=storage_reservation_id, descriptor=shared_descriptor,
            )
            written = shared_store.write(
                tenant_id=int(tenant_id), reservation_id=storage_reservation_id,
                source_path=file_path, suffix=file_extension, cancelled=cancelled,
            )
            if written != shared_descriptor:
                raise ImmutableObjectError(
                    ObjectErrorCategory.CORRUPT, "immutable_object_descriptor_mismatch",
                )
            verify_immutable_storage(reservation_id=storage_reservation_id)
        except ImmutableObjectError as error:
            if error.category in {ObjectErrorCategory.TIMEOUT, ObjectErrorCategory.UNAVAILABLE}:
                try:
                    mark_immutable_storage_ambiguous(reservation_id=storage_reservation_id)
                except Exception:
                    logger.exception("data.upload.immutable_ambiguity_record_failed")
                file_path.unlink(missing_ok=True)
                raise HTTPException(status_code=503, detail={
                    "code": "immutable_storage_outcome_unknown",
                    "message": "The private object transfer outcome is being reconciled.",
                }) from error
            try:
                finish_storage(reservation_id=storage_reservation_id, succeeded=False)
            finally:
                file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=503, detail={
                "code": error.code,
                "message": "Private immutable storage is temporarily unavailable.",
            }) from error
        except Exception as error:
            try:
                mark_immutable_storage_ambiguous(reservation_id=storage_reservation_id)
            except Exception:
                logger.exception("data.upload.immutable_ambiguity_record_failed")
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=503, detail={
                "code": "immutable_storage_outcome_unknown",
                "message": "The private object transfer outcome is being reconciled.",
            }) from error
    try:
        if shared_descriptor is not None:
            storage_object_id = finish_immutable_storage(
                reservation_id=storage_reservation_id, storage_key=storage_key,
            )
        else:
            storage_object_id = finish_storage(
                reservation_id=storage_reservation_id,
                succeeded=True,
                storage_key=storage_key,
                sha256_hex=content_hash,
            )
        if metadata_persister is not None and not storage_object_id:
            raise RuntimeError("Storage object identity was not returned")
    except Exception as error:
        if shared_descriptor is None:
            file_path.unlink(missing_ok=True)
        logger.error("data.upload.accounting_failed", extra={"tenant_id": tenant_id, "user_id": user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=503, detail={
            "code": "metadata_outcome_unknown" if shared_descriptor is not None else "storage_accounting_unavailable",
            "message": "Storage accounting is temporarily unavailable.",
        }) from error

    if storage_object_persister is not None:
        try:
            storage_object_persister(storage_object_id)
        except Exception as error:
            attached = None
            if storage_object_failure_resolver is not None:
                try:
                    attached = storage_object_failure_resolver(storage_object_id)
                except Exception:
                    attached = None
            if attached is not True:
                if attached is False:
                    try:
                        if release_storage(
                            tenant_id=int(tenant_id), category="dataset", storage_key=storage_key
                        ):
                            if shared_descriptor is not None:
                                shared_store.delete(
                                    tenant_id=int(tenant_id), descriptor=shared_descriptor,
                                )
                            file_path.unlink(missing_ok=True)
                    except Exception:
                        logger.exception(
                            "data.upload.storage_attachment_compensation_failed",
                            extra={"tenant_id": tenant_id, "user_id": user_id},
                        )
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "metadata_outcome_unknown",
                        "message": "The import outcome is being reconciled. Retry with the same request key.",
                    },
                ) from error

    if lifecycle_heartbeat is not None:
        lifecycle_heartbeat()

    if metadata_persister is not None:
        try:
            persisted = metadata_persister(
                {
                    "storage_object_id": storage_object_id,
                    "storage_key": storage_key,
                    "sha256": content_hash,
                    "original_filename": filename,
                    "content_type": file.content_type,
                    "file_extension": file_extension,
                    "file_size": file_size,
                    "response": response,
                }
            )
            if persisted:
                response = {**response, **persisted}
        except Exception as error:
            recovered = False
            if metadata_failure_resolver is not None:
                try:
                    recovered = metadata_failure_resolver(error)
                except Exception:
                    recovered = None
                    logger.exception(
                        "data.upload.metadata_recovery_failed",
                        extra={"tenant_id": tenant_id, "user_id": user_id},
                    )
            if isinstance(recovered, dict):
                response = {**response, **recovered}
                logger.warning(
                    "data.upload.metadata_response_recovered",
                    extra={"tenant_id": tenant_id, "user_id": user_id},
                )
                recovered = True
            if recovered is True:
                error = None
            elif recovered is None:
                logger.error(
                    "data.upload.metadata_outcome_unknown",
                    extra={
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "error_type": type(error).__name__,
                    },
                )
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "metadata_outcome_unknown",
                        "message": "The import outcome is being reconciled. Retry with the same request key.",
                    },
                ) from error
            else:
                compensation_complete = False
                try:
                    compensation_complete = release_storage(
                        tenant_id=int(tenant_id),
                        category="dataset",
                        storage_key=storage_key,
                    )
                except Exception:
                    logger.exception(
                        "data.upload.metadata_compensation_failed",
                        extra={"tenant_id": tenant_id, "user_id": user_id},
                    )
                if compensation_complete:
                    if shared_descriptor is not None:
                        try:
                            shared_store.delete(
                                tenant_id=int(tenant_id), descriptor=shared_descriptor,
                            )
                        except Exception:
                            logger.exception(
                                "data.upload.immutable_delete_failed_after_release",
                                extra={"tenant_id": tenant_id, "user_id": user_id},
                            )
                    file_path.unlink(missing_ok=True)
                logger.error(
                    "data.upload.metadata_failed",
                    extra={
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "compensation_complete": compensation_complete,
                        "error_type": type(error).__name__,
                    },
                )
                raise HTTPException(
                    status_code=503,
                    detail="Dataset metadata is temporarily unavailable.",
                ) from error

    if shared_descriptor is not None:
        file_path.unlink(missing_ok=True)

    logger.info(
        "data.upload.accepted",
        extra={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "file_size": int(file_size),
            "processing_mode": response.get("processing_mode"),
            "rows": response.get("rows"),
            "columns": response.get("column_count"),
        },
    )

    return response


def process_read(input_path: str, *, tenant_id: str, user_id: str):
    authorized_input_path = authorize_dataset_input_path(input_path, tenant_id=tenant_id, user_id=user_id)
    authorized_path = Path(authorized_input_path)

    if (
        not _is_remote_dataset(authorized_input_path)
        and authorized_path.suffix.lower() == ".csv"
        and not DataReadingNormal._isolated_parser_enabled()
    ):
        return extract_csv_metadata(authorized_path, original_filename=Path(input_path).name)

    if not _is_remote_dataset(authorized_input_path):
        _raise_if_full_dataframe_blocked(authorized_path, operation="dataset preview")

    reader = DataReadingNormal(authorized_input_path, tenant_id=tenant_id, user_id=user_id)

    try:
        df = reader.read()
    except RemoteDatasetUrlsDisabledError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return build_dataset_response(
        df,
        file_path=input_path,
        original_filename=input_path,
    )


def export_dataset(input_path: str, *, tenant_id: str, user_id: str):
    df = read_dataset(input_path, tenant_id=tenant_id, user_id=user_id)
    export_df = sanitize_spreadsheet_dataframe(df)
    output = StringIO()
    export_df.to_csv(output, index=False)

    return sanitize_for_json(
        {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": dataframe_preview(df, 20),
            "csv": output.getvalue(),
        }
    )


def inspect_dataset(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.data_inspection())


def preparation_report(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.preparation_report())


def statistical_inspection(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.statistical_inspection())


def missing_values_report(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.missing_values_report())


def quality_report(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.quality_report())


def column_types(input_path: str, *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    return sanitize_for_json(cleaner.column_types())


def apply_cleaning(input_path: str, actions: list[dict], *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(actions)

    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "preview": dataframe_preview(df, 20),
    }


def export_cleaned_dataframe(input_path: str, actions: list[dict], *, tenant_id: str, user_id: str):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(actions)
    export_df = sanitize_spreadsheet_dataframe(df)
    output = StringIO()
    export_df.to_csv(output, index=False)

    return sanitize_for_json(
        {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": dataframe_preview(df, 20),
            "csv": output.getvalue(),
        }
    )


def get_analysis_catalog(language: str = "en"):
    language = normalize_language(language)
    symbols = normalize_symbols()
    return sanitize_for_json(
        {
            "language": language,
            "direction": direction_for(language),
            "symbols": symbols,
            "domains": localized_catalog(ANALYSIS_CATALOG, language),
            "response_shape": {
                "report_id": "string",
                "domain": "string",
                "title": "string",
                "summary": "string",
                "insights": "string[]",
                "kpis": "metric[]",
                "tables": "table[]",
                "charts": "chart[]",
                "warnings": "string[]",
                "metadata": "object",
            },
        }
    )


def run_analysis(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    analysis_requests: list[dict],
    language: str,
    symbols: dict,
    tenant_id: str,
    user_id: str,
):
    try:
        cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
        df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
        df, preparation_warnings = cleaner.prepare_dataframe(df)
        language = normalize_language(language)
        symbols = normalize_symbols(symbols)

        analysis_router = AnalysisRouter(df, language=language, symbols=symbols)
        results = analysis_router.run(analysis_requests)

        return sanitize_for_json(
            {
                "rows_used": int(len(df)),
                "columns_used": list(df.columns),
                "warnings": preparation_warnings,
                "metadata": {
                    "cleaning_actions_applied": cleaning_actions,
                    "analysis_request_count": len(analysis_requests),
                    "language": language,
                    "direction": direction_for(language),
                    "symbols": symbols,
                    "profiles": cleaner.profile_dataframe(df),
                },
                "results": results,
            }
        )

    except Exception as error:
        logger.warning(
            "data.analysis.failed",
            extra={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "error_type": type(error).__name__,
            },
        )
        raise


def run_assisted_analysis(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    question: str | None,
    metric: dict | None,
    language: str,
    symbols: dict,
    tenant_id: str,
    user_id: str,
    dataset_version: dict | None = None,
    dataset_identity: dict | None = None,
):
    from services import adaptive_analytics_service

    authorized_path = authorize_dataset_input_path(
        input_path, tenant_id=tenant_id, user_id=user_id, require_small=False,
        operation="adaptive deterministic analytics",
    )
    authorized_file = Path(authorized_path)
    actual_size = authorized_file.stat().st_size if authorized_file.is_file() else 0
    version = dataset_version if isinstance(dataset_version, dict) else {}
    metadata = version.get("file_metadata") if isinstance(version.get("file_metadata"), dict) else {}
    declared_rows = metadata.get("rows") if isinstance(metadata.get("rows"), int) else None
    declared_size = int(version.get("size_bytes") or 0)
    effective_size = max(actual_size, declared_size)
    file_format = authorized_file.suffix.lower().lstrip(".") or Path(input_path).suffix.lower().lstrip(".")
    operation = str((metric or {}).get("operation") or "").lower() if isinstance(metric, dict) else None
    decision = adaptive_analytics_service.select_engine(
        workload="metric", file_format=file_format, size_bytes=effective_size,
        row_count=declared_rows, operation=operation,
        has_grouping=bool(isinstance(metric, dict) and metric.get("group_column")),
        cleaning_actions=bool(cleaning_actions), has_question=bool(question),
    )
    if decision.engine == "unsupported":
        status = 413 if decision.reason in {
            "large_format_unsupported", "scalable_csv_limit_exceeded",
            "large_cleaning_pipeline_unsupported", "large_freeform_analysis_unsupported",
            "large_metric_unsupported", "large_date_metric_limit_exceeded",
        } else 503
        raise HTTPException(status_code=status, detail={
            "code": decision.reason,
            "message": "This dataset operation is not supported by a bounded compatible analytics engine.",
        })
    if decision.engine == "polars":
        metric_source = authorized_file
        metric_source_format = "csv"
        identity = dataset_identity if isinstance(dataset_identity, dict) else {}
        if all(identity.get(key) for key in (
            "project_id", "dataset_id", "version_id",
        )) and version.get("content_hash"):
            from services import parquet_cache_service
            artifact = parquet_cache_service.get_existing(
                source_path=str(authorized_file), tenant_id=int(tenant_id),
                user_id=int(user_id), project_id=str(identity["project_id"]),
                dataset_id=str(identity["dataset_id"]), version_id=str(identity["version_id"]),
                source_hash=str(version["content_hash"]), source_size=actual_size,
                declared_rows=declared_rows,
            )
            if artifact is not None and parquet_cache_service.is_metric_compatible(
                artifact, dict(metric or {}),
            ):
                metric_source = artifact.path
                metric_source_format = "parquet"
        return adaptive_analytics_service.run_large_metric(
            authorized_path=str(metric_source), metric=dict(metric or {}), language=language,
            symbols=symbols, declared_rows=declared_rows,
            source_size_bytes=effective_size, source_format=metric_source_format,
        )

    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
    df, preparation_warnings = cleaner.prepare_dataframe(df)
    language = normalize_language(language)
    symbols = normalize_symbols(symbols)

    analyzer = AssistedAnalysis(df, language=language, symbols=symbols)
    result = analyzer.answer_question(question=question, metric=metric)

    return sanitize_for_json(
        {
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
            "warnings": preparation_warnings,
            "metadata": {
                "cleaning_actions_applied": cleaning_actions,
                "language": language,
                "direction": direction_for(language),
                "symbols": symbols,
                "profiles": cleaner.profile_dataframe(df),
                "ai_connected": False,
                "analytics_engine": "pandas",
                "engine_reason": decision.reason,
            },
            "result": result,
        }
    )


def create_visualization(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    chart_config: dict,
    tenant_id: str,
    user_id: str,
):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
    visualizer = DataVisualization(df)

    if not isinstance(chart_config, dict):
        raise HTTPException(
            status_code=400,
            detail="Choose plot settings before creating the visualization.",
        )

    chart_id = f"madar-visualization-{uuid4().hex}.png"
    chart_storage_dir = get_user_chart_dir(tenant_id, user_id)
    chart_save_path = chart_storage_dir / chart_id
    explorer_id = f"{Path(chart_id).stem}-explorer.html"
    explorer_save_path = chart_storage_dir / explorer_id

    plot_kwargs = {
        key: value
        for key, value in chart_config.items()
        if key
        in {
            "chart_type",
            "x",
            "y",
            "hue",
            "title",
            "x_label",
            "y_label",
            "palette",
            "color",
            "font_family",
            "title_font_size",
            "label_font_size",
            "tick_font_size",
            "legend_font_size",
            "series_count",
            "features",
            "language",
            "orientation",
            "style",
            "figsize",
            "marker",
            "rotation",
            "gradient",
        }
    }

    if isinstance(plot_kwargs.get("figsize"), list):
        plot_kwargs["figsize"] = tuple(plot_kwargs["figsize"])

    try:
        chart_path = visualizer.plot(**plot_kwargs, save_path=str(chart_save_path))
    except ValueError as error:
        logger.warning(
            "data.visualization.chart_validation_failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.warning(
            "data.visualization.chart_failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=400,
            detail="Could not create the visualization. Please check the selected fields and chart type.",
        ) from error

    explorer_path = None
    explorer_url = None
    try:
        explorer_path = visualizer.explorer(save_path=str(explorer_save_path))
        explorer_url = (
            build_private_chart_url(user_id=user_id, chart_id=Path(explorer_path).name)
            if explorer_path
            else None
        )
    except Exception as error:
        logger.info(
            "data.visualization.explorer_skipped",
            extra={"error_type": type(error).__name__},
        )

    returned_chart_id = Path(chart_path).name if chart_path else None
    chart_url = (
        build_private_chart_url(user_id=user_id, chart_id=returned_chart_id)
        if returned_chart_id
        else None
    )

    generated_paths = [Path(path) for path in (chart_path, explorer_path) if path]
    reservations: list[str] = []
    try:
        for generated_path in generated_paths:
            size = generated_path.stat().st_size
            reservation_id = reserve_storage(
                tenant_id=int(tenant_id),
                user_id=int(user_id),
                category="generated_artifact",
                size_bytes=size,
                storage_root=chart_storage_dir,
            )
            reservations.append(reservation_id)
            finish_storage(
                reservation_id=reservation_id,
                succeeded=True,
                storage_key=f"tenant_{tenant_id}/user_{user_id}/{generated_path.name}",
                sha256_hex=sha256_file(generated_path),
                retention_until=None,
            )
    except (OSError, StorageSafetyError, RuntimeError) as error:
        for generated_path in generated_paths:
            generated_path.unlink(missing_ok=True)
        logger.error(
            "data.visualization.accounting_failed",
            extra={"tenant_id": tenant_id, "user_id": user_id, "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=507, detail="Generated artifact storage is unavailable.") from error

    return sanitize_for_json(
        {
            "chart_path": returned_chart_id,
            "chart_url": chart_url,
            "explorer_path": Path(explorer_path).name if explorer_path else None,
            "explorer_url": explorer_url,
            "visualization_engine": "seaborn",
            "inspection_engine": "pygwalker" if explorer_url else None,
            "fallback_reason": None if explorer_url else "Interactive inspection was not available.",
            "rows_used": int(len(df)),
            "columns_used": list(df.columns),
        }
    )


def profile_visualization_columns(
    *,
    input_path: str,
    cleaning_actions: list[dict],
    columns: list[str],
    tenant_id: str,
    user_id: str,
):
    cleaner = build_authorized_cleaner(input_path, tenant_id=tenant_id, user_id=user_id)
    df = cleaner.apply_pipeline(cleaning_actions) if cleaning_actions else cleaner.read()
    selected_columns = [column for column in columns if column in df.columns]

    profiles = {}
    for column in selected_columns:
        series = df[column]
        non_null = series.dropna()
        unique_values = non_null.unique().tolist()
        profiles[column] = {
            "unique_count": int(non_null.nunique(dropna=True)),
            "missing_count": int(series.isna().sum()),
            "sample_values": [str(value) for value in unique_values[:50]],
            "is_numeric": bool(pd.api.types.is_numeric_dtype(series)),
        }

    missing_columns = [column for column in columns if column not in df.columns]

    return sanitize_for_json(
        {
            "rows_used": int(len(df)),
            "profiles": profiles,
            "missing_columns": missing_columns,
        }
    )
