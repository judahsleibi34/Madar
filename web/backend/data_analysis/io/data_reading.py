import math
import base64
import json
import os
import re
import shutil
import struct
import tempfile
import time
import zipfile
from contextlib import contextmanager
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import openpyxl
import pandas as pd
import requests
from fastapi import HTTPException

from services.upload_config import (
    get_data_upload_dir,
    resolve_private_user_file_path,
    safe_scope_part,
)


class RemoteDatasetUrlsDisabledError(ValueError):
    pass


class RemoteIngestionUnavailableError(HTTPException):
    def __init__(self, message: str = "Remote ingestion is temporarily unavailable") -> None:
        super().__init__(
            status_code=503,
            detail={"code": "remote_ingestion_unavailable", "message": message},
            headers={"Retry-After": "30"},
        )


class ParserWorkerUnavailableError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            detail={
                "code": "parser_worker_unavailable",
                "message": "Dataset parsing is temporarily unavailable",
            },
            headers={"Retry-After": "30"},
        )


class DataReadingNormal:
    SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}

    CSV_ENCODINGS = [
        "utf-8-sig",
        "utf-8",
        "cp1256",
        "windows-1256",
        "utf-16",
    ]
    SHARED_CACHE_MAX_ITEMS = int(os.getenv("DATAFRAME_CACHE_MAX_ITEMS", "16"))
    URL_CACHE_SECONDS = int(os.getenv("DATAFRAME_URL_CACHE_SECONDS", "60"))
    MAX_REMOTE_BYTES = int(os.getenv("MAX_REMOTE_DATA_BYTES", str(10 * 1024 * 1024)))
    MAX_CSV_BYTES = int(os.getenv("MAX_CSV_BYTES", os.getenv("MAX_FULL_DATAFRAME_BYTES", str(50 * 1024 * 1024))))
    MAX_ROWS = int(os.getenv("DATAFRAME_MAX_ROWS", "100000"))
    MAX_COLUMNS = int(os.getenv("DATAFRAME_MAX_COLUMNS", "500"))
    MAX_CELL_CHARS = int(os.getenv("DATAFRAME_MAX_CELL_CHARS", "10000"))
    MAX_TOTAL_CELL_CHARS = int(os.getenv("DATAFRAME_MAX_TOTAL_CELL_CHARS", str(10 * 1024 * 1024)))
    MAX_EXCEL_FILE_BYTES = int(os.getenv("MAX_EXCEL_FILE_BYTES", os.getenv("MAX_EXCEL_UPLOAD_BYTES", str(50 * 1024 * 1024))))
    MAX_EXCEL_UNCOMPRESSED_BYTES = int(os.getenv("MAX_EXCEL_UNCOMPRESSED_BYTES", str(50 * 1024 * 1024)))
    MAX_EXCEL_ZIP_ENTRIES = int(os.getenv("MAX_EXCEL_ZIP_ENTRIES", "200"))
    MAX_EXCEL_ZIP_ENTRY_NAME_CHARS = int(os.getenv("MAX_EXCEL_ZIP_ENTRY_NAME_CHARS", "240"))
    MAX_EXCEL_ZIP_COMPRESSION_RATIO = float(os.getenv("MAX_EXCEL_ZIP_COMPRESSION_RATIO", "100"))
    MAX_EXCEL_SHEETS = int(os.getenv("MAX_EXCEL_SHEETS", "20"))
    MAX_EXCEL_ROWS = int(os.getenv("MAX_EXCEL_ROWS", "100000"))
    MAX_EXCEL_COLUMNS = int(os.getenv("MAX_EXCEL_COLUMNS", "1000"))
    MAX_EXCEL_CELL_CHARS = int(os.getenv("MAX_EXCEL_CELL_CHARS", "10000"))
    PARSER_WORKSPACE_BASE = os.getenv("MADAR_UPLOAD_WORKSPACE_DIR", os.path.join(tempfile.gettempdir(), "madar_uploads"))
    REMOTE_DATASET_URLS_DISABLED_MESSAGE = (
        "Remote dataset URLs are disabled. Upload a CSV/XLS/XLSX file instead."
    )
    _shared_df_cache: OrderedDict[str, pd.DataFrame] = OrderedDict()

    def __init__(
        self,
        input_path: str,
        tenant_id: str | int | None = None,
        user_id: str | int | None = None,
    ) -> None:
        if not input_path:
            raise ValueError("input_path is required")

        self.input_path = input_path
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._cached_df: pd.DataFrame | None = None

    def read(self, refresh: bool = False) -> pd.DataFrame:
        if self._is_url(self.input_path):
            self._assert_remote_dataset_urls_enabled()

        if self._cached_df is not None and not refresh:
            return self._cached_df.copy(deep=True)

        try:
            cache_key = None if refresh else self._shared_cache_key()
            if cache_key:
                cached = self._get_shared_cache(cache_key)
                if cached is not None:
                    self._cached_df = cached.copy(deep=True)
                    return cached.copy(deep=True)

            if self._is_url(self.input_path) and not self._isolated_parser_enabled():
                raise RemoteIngestionUnavailableError(
                    "Remote ingestion requires the isolated worker topology"
                )

            if self._isolated_parser_enabled() and not self._is_parser_worker_process():
                df = self._read_via_isolated_worker()
                self._cached_df = df.copy(deep=True)
                if cache_key:
                    self._set_shared_cache(cache_key, df)
                return df.copy(deep=True)

            if self._is_url(self.input_path):
                raise RemoteIngestionUnavailableError(
                    "Remote ingestion requires the isolated worker topology"
                )
            df = self._read_local_file(self.input_path)

            self._cached_df = df.copy(deep=True)
            if cache_key:
                self._set_shared_cache(cache_key, df)
            return df.copy(deep=True)

        except (
            RemoteDatasetUrlsDisabledError,
            RemoteIngestionUnavailableError,
            ParserWorkerUnavailableError,
        ):
            raise
        except Exception as error:
            raise RuntimeError("Failed to read data") from error

    def _read_via_isolated_worker(self) -> pd.DataFrame:
        if self._is_url(self.input_path):
            parser_payload = self._fetch_remote_parser_payload(self.input_path)
        else:
            safe_path = self._resolve_uploaded_file(self.input_path)
            parser_payload = {
                "input_path": str(safe_path),
                "tenant_id": str(self.tenant_id) if self.tenant_id is not None else None,
                "user_id": str(self.user_id) if self.user_id is not None else None,
            }
        worker_url = os.getenv(
            "PARSER_WORKER_URL", "http://parser-worker:8092/parse"
        ).strip()
        timeout_seconds = max(
            1.0, min(float(os.getenv("PARSER_WORKER_TIMEOUT_SECONDS", "60")), 300.0)
        )
        max_result_bytes = max(
            1024,
            min(
                int(os.getenv("PARSER_WORKER_MAX_RESULT_BYTES", str(16 * 1024 * 1024))),
                64 * 1024 * 1024,
            ),
        )
        try:
            response = requests.post(
                worker_url,
                json=parser_payload,
                timeout=(2.0, timeout_seconds),
                stream=True,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise ParserWorkerUnavailableError() from error
        if response.status_code >= 500:
            response.close()
            raise ParserWorkerUnavailableError()
        if response.status_code != 200:
            response.close()
            raise ValueError("The isolated parser could not process this dataset")
        self._buffer_worker_response(response, max_result_bytes=max_result_bytes)
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("The isolated parser returned an invalid result") from error
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("columns"), list)
            or not isinstance(payload.get("data"), list)
        ):
            raise ValueError("The isolated parser returned an invalid result")
        columns = payload["columns"]
        data = payload["data"]
        if len(columns) > self.MAX_COLUMNS or len(data) > self.MAX_ROWS:
            raise ValueError("The isolated parser result exceeds dataset limits")
        if any(not isinstance(row, list) or len(row) != len(columns) for row in data):
            raise ValueError("The isolated parser returned an invalid result")
        return self._normalize_dataframe(pd.DataFrame(data, columns=columns))

    def _fetch_remote_parser_payload(self, url: str) -> dict:
        if not self._isolated_parser_enabled():
            raise RemoteIngestionUnavailableError(
                "Remote ingestion requires the isolated parser worker"
            )
        egress_url = os.getenv(
            "REMOTE_INGESTION_WORKER_URL", "http://remote-ingestion-worker:8093/fetch"
        ).strip()
        timeout_seconds = max(
            1.0,
            min(float(os.getenv("REMOTE_INGESTION_BACKEND_TIMEOUT_SECONDS", "45")), 65.0),
        )
        max_result_bytes = max(
            1024,
            min(
                int(os.getenv("REMOTE_INGESTION_MAX_RESULT_BYTES", str(14 * 1024 * 1024 + 65536))),
                20 * 1024 * 1024,
            ),
        )
        requested_url = self._google_sheet_to_csv_url(url) if self._is_google_sheets_url(url) else url
        request_id = uuid4().hex
        try:
            response = requests.post(
                egress_url,
                json={
                    "url": requested_url,
                    "tenant_id": str(self.tenant_id) if self.tenant_id is not None else None,
                    "user_id": str(self.user_id) if self.user_id is not None else None,
                    "request_id": request_id,
                },
                timeout=(2.0, timeout_seconds),
                stream=True,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise RemoteIngestionUnavailableError(
                "Remote ingestion worker is unavailable"
            ) from error
        if response.status_code >= 500:
            response.close()
            raise RemoteIngestionUnavailableError(
                "Remote ingestion worker is unavailable"
            )
        if response.status_code != 200:
            response.close()
            raise ValueError("The remote dataset could not be fetched safely")
        self._buffer_worker_response(response, max_result_bytes=max_result_bytes)
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise RemoteIngestionUnavailableError(
                "Remote ingestion worker returned an invalid result"
            ) from error
        if (
            not isinstance(payload, dict)
            or payload.get("status") != "ok"
            or payload.get("request_id") != request_id
            or not isinstance(payload.get("final_url"), str)
            or not isinstance(payload.get("content_type"), str)
            or not isinstance(payload.get("content_b64"), str)
        ):
            raise RemoteIngestionUnavailableError(
                "Remote ingestion worker returned an invalid result"
            )
        try:
            content_size = len(base64.b64decode(payload["content_b64"], validate=True))
        except (ValueError, TypeError) as error:
            raise RemoteIngestionUnavailableError(
                "Remote ingestion worker returned an invalid result"
            ) from error
        if content_size > self.MAX_REMOTE_BYTES:
            raise RemoteIngestionUnavailableError(
                "Remote ingestion worker returned an oversized result"
            )
        return {
            "content_b64": payload["content_b64"],
            "source_url": payload["final_url"],
            "content_type": payload["content_type"],
            "tenant_id": str(self.tenant_id) if self.tenant_id is not None else None,
            "user_id": str(self.user_id) if self.user_id is not None else None,
        }

    @staticmethod
    def _buffer_worker_response(response: requests.Response, *, max_result_bytes: int) -> None:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_result_bytes:
                    raise ValueError("The isolated parser result is too large")
            except (TypeError, ValueError) as error:
                response.close()
                raise ValueError("The isolated parser result is too large") from error
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_result_bytes:
                response.close()
                raise ValueError("The isolated parser result is too large")
            chunks.append(chunk)
        response._content = b"".join(chunks)
        response._content_consumed = True

    @staticmethod
    def _isolated_parser_enabled() -> bool:
        return (os.getenv("PARSER_ISOLATED_WORKER_ENABLED") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _is_parser_worker_process() -> bool:
        return (os.getenv("PARSER_WORKER_PROCESS") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def clear_cache(self) -> None:
        self._cached_df = None

    @classmethod
    def clear_shared_cache(cls) -> None:
        cls._shared_df_cache.clear()

    def _shared_cache_key(self) -> str | None:
        if self._is_url(self.input_path):
            ttl = max(self.URL_CACHE_SECONDS, 1)
            bucket = int(time.time() // ttl)
            return f"url:{bucket}:{self.input_path}"

        safe_path = self._resolve_uploaded_file(self.input_path)
        stat = safe_path.stat()
        return f"file:{safe_path}:{stat.st_size}:{stat.st_mtime_ns}"

    @classmethod
    def _get_shared_cache(cls, key: str) -> pd.DataFrame | None:
        cached = cls._shared_df_cache.get(key)
        if cached is None:
            return None
        cls._shared_df_cache.move_to_end(key)
        return cached.copy(deep=True)

    @classmethod
    def _set_shared_cache(cls, key: str, df: pd.DataFrame) -> None:
        cls._shared_df_cache[key] = df.copy(deep=True)
        cls._shared_df_cache.move_to_end(key)
        while len(cls._shared_df_cache) > cls.SHARED_CACHE_MAX_ITEMS:
            cls._shared_df_cache.popitem(last=False)

    def _read_local_file(self, file_path: str) -> pd.DataFrame:
        safe_path = self._resolve_uploaded_file(file_path)
        extension = self._get_extension(str(safe_path))

        with self._isolated_parser_workspace(safe_path) as workspace_path:
            if extension == ".csv":
                with open(workspace_path, "rb") as file:
                    return self._read_csv_bytes(file.read())

            if extension == ".xlsx":
                self._validate_xlsx_file(workspace_path)
                self._validate_xlsx_workbook(workspace_path)
                df = pd.read_excel(workspace_path, engine="openpyxl")
                self._validate_excel_dataframe(df)
                return self._normalize_dataframe(df)

            if extension == ".xls":
                self._validate_excel_file_size(workspace_path.stat().st_size)
                df = pd.read_excel(workspace_path)
                self._validate_excel_dataframe(df)
                return self._normalize_dataframe(df)

        raise ValueError(
            f"Unsupported file format: {extension}. "
            "Supported formats are .csv, .xls, and .xlsx"
        )

    def _read_excel_bytes(self, content: bytes, *, extension: str = "") -> pd.DataFrame:
        self._validate_excel_file_size(len(content))

        if extension == ".xlsx" or zipfile.is_zipfile(BytesIO(content)):
            self._validate_xlsx_file(content)
            self._validate_xlsx_workbook(content)
            df = pd.read_excel(BytesIO(content), engine="openpyxl")
        else:
            df = pd.read_excel(BytesIO(content))

        self._validate_excel_dataframe(df)
        return self._normalize_dataframe(df)

    def _validate_excel_file_size(self, size_bytes: int) -> None:
        if size_bytes > self.MAX_EXCEL_FILE_BYTES:
            raise ValueError("Excel file is too large")

    def _zip_source(self, source):
        if isinstance(source, (bytes, bytearray)):
            return BytesIO(source)
        return source

    def _zip_source_bytes(self, source) -> bytes:
        if isinstance(source, (bytes, bytearray)):
            return bytes(source)

        with open(source, "rb") as file:
            return file.read()

    @contextmanager
    def _isolated_parser_workspace(self, source_path: Path) -> Iterator[Path]:
        # The production parser worker uses this per-job workspace inside its
        # no-network, resource-limited container.
        base_dir = Path(self.PARSER_WORKSPACE_BASE).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        workspace = Path(
            tempfile.mkdtemp(prefix="parse_", suffix="_job", dir=str(base_dir))
        ).resolve()

        try:
            workspace_file = workspace / f"dataset{source_path.suffix.lower()}"
            shutil.copy2(source_path, workspace_file)
            yield workspace_file
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _validate_xlsx_file(self, source) -> None:
        if not isinstance(source, (bytes, bytearray)):
            self._validate_excel_file_size(Path(source).stat().st_size)
        self._validate_raw_zip_entry_names(source)

        try:
            with zipfile.ZipFile(self._zip_source(source)) as workbook_zip:
                entries = workbook_zip.infolist()

                if len(entries) > self.MAX_EXCEL_ZIP_ENTRIES:
                    raise ValueError("Excel workbook has too many ZIP entries")

                total_uncompressed = 0

                for entry in entries:
                    self._validate_xlsx_zip_entry(entry)
                    total_uncompressed += int(entry.file_size or 0)

                    if total_uncompressed > self.MAX_EXCEL_UNCOMPRESSED_BYTES:
                        raise ValueError("Excel workbook is too large after decompression")

        except zipfile.BadZipFile as error:
            raise ValueError("Invalid or corrupt Excel workbook") from error

    def _validate_xlsx_zip_entry(self, entry: zipfile.ZipInfo) -> None:
        raw_filename = str(getattr(entry, "orig_filename", "") or entry.filename or "")
        filename = str(entry.filename or "")

        if entry.flag_bits & 0x1:
            raise ValueError("Encrypted Excel workbooks are not supported")

        external_file_type = (entry.external_attr >> 16) & 0o170000
        if external_file_type in {0o120000, 0o020000, 0o060000}:
            raise ValueError("Excel workbook contains an unsafe ZIP entry type")

        compressed_size = int(entry.compress_size or 0)
        uncompressed_size = int(entry.file_size or 0)

        if (
            compressed_size > 0
            and uncompressed_size / compressed_size > self.MAX_EXCEL_ZIP_COMPRESSION_RATIO
            and uncompressed_size > 1024 * 1024
        ):
            raise ValueError("Excel workbook has a suspicious compression ratio")

        if uncompressed_size > self.MAX_EXCEL_UNCOMPRESSED_BYTES:
            raise ValueError("Excel workbook is too large after decompression")

        self._validate_xlsx_zip_entry_name(raw_filename)
        self._validate_xlsx_zip_entry_name(filename)

    def _validate_xlsx_zip_entry_name(self, filename: str) -> None:
        if len(filename) > self.MAX_EXCEL_ZIP_ENTRY_NAME_CHARS:
            raise ValueError("Excel workbook contains an unsafe ZIP entry path")

        if (
            not filename
            or filename.startswith(("/", "\\"))
            or "\\" in filename
            or "//" in filename
            or re.match(r"^[A-Za-z]:", filename)
            or ":" in filename.split("/", 1)[0]
            or any(part == "" for part in filename.split("/"))
            or any(part in {".", ".."} for part in filename.split("/"))
        ):
            raise ValueError("Excel workbook contains an unsafe ZIP entry path")

    def _validate_raw_zip_entry_names(self, source) -> None:
        data = self._zip_source_bytes(source)
        for raw_name in self._iter_raw_zip_entry_names(data):
            try:
                filename = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                filename = raw_name.decode("cp437", errors="replace")
            self._validate_xlsx_zip_entry_name(filename)

    def _iter_raw_zip_entry_names(self, data: bytes):
        signatures = (b"PK\x03\x04", b"PK\x01\x02")
        index = 0

        while index < len(data):
            positions = [data.find(signature, index) for signature in signatures]
            positions = [position for position in positions if position >= 0]
            if not positions:
                break

            position = min(positions)
            signature = data[position:position + 4]

            try:
                if signature == b"PK\x03\x04":
                    if position + 30 > len(data):
                        break
                    name_length, extra_length = struct.unpack_from("<HH", data, position + 26)
                    name_start = position + 30
                    next_index = name_start + name_length + extra_length
                elif signature == b"PK\x01\x02":
                    if position + 46 > len(data):
                        break
                    name_length, extra_length, comment_length = struct.unpack_from(
                        "<HHH", data, position + 28
                    )
                    name_start = position + 46
                    next_index = name_start + name_length + extra_length + comment_length
                else:
                    index = position + 1
                    continue

                name_end = name_start + name_length
                if name_length and name_end <= len(data):
                    yield data[name_start:name_end]

                index = max(next_index, position + 4)
            except struct.error:
                break

    def _validate_xlsx_workbook(self, source) -> None:
        try:
            workbook = openpyxl.load_workbook(
                self._zip_source(source),
                read_only=True,
                data_only=True,
                keep_links=False,
            )
        except zipfile.BadZipFile as error:
            raise ValueError("Invalid or corrupt Excel workbook") from error
        except Exception as error:
            raise ValueError("Invalid or corrupt Excel workbook") from error

        try:
            if len(workbook.sheetnames) > self.MAX_EXCEL_SHEETS:
                raise ValueError("Excel workbook has too many sheets")

            for worksheet in workbook.worksheets:
                if worksheet.max_row and worksheet.max_row > self.MAX_EXCEL_ROWS:
                    raise ValueError("Excel worksheet has too many rows")

                if worksheet.max_column and worksheet.max_column > self.MAX_EXCEL_COLUMNS:
                    raise ValueError("Excel worksheet has too many columns")
        finally:
            workbook.close()

    def _validate_excel_dataframe(self, df: pd.DataFrame) -> None:
        if len(df) > self.MAX_EXCEL_ROWS:
            raise ValueError("Excel worksheet has too many rows")

        if len(df.columns) > self.MAX_EXCEL_COLUMNS:
            raise ValueError("Excel worksheet has too many columns")

        for value in df.to_numpy(dtype=object).flat:
            if isinstance(value, str) and len(value) > self.MAX_EXCEL_CELL_CHARS:
                raise ValueError("Excel cell text is too large")

    def _read_csv_bytes(self, content: bytes) -> pd.DataFrame:
        if not content:
            raise ValueError("CSV file is empty.")

        if len(content) > self.MAX_CSV_BYTES:
            raise ValueError("CSV file is too large.")

        self._reject_binary_csv(content)

        last_error = None

        for encoding in self.CSV_ENCODINGS:
            try:
                df = pd.read_csv(BytesIO(content), encoding=encoding)
                return self._normalize_dataframe(df)
            except UnicodeDecodeError as error:
                last_error = error
            except ValueError:
                raise
            except Exception as error:
                last_error = error

        raise ValueError(f"Could not read CSV with supported encodings: {last_error}")

    def _reject_binary_csv(self, content: bytes) -> None:
        sample = content[:4096]
        if b"\x00" in sample:
            raise ValueError("CSV file appears to be binary.")

        if sample:
            control_bytes = sum(
                1 for byte in sample if byte < 32 and byte not in {9, 10, 13}
            )
            if control_bytes / len(sample) > 0.05:
                raise ValueError("CSV file appears to be binary.")

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")

        if len(df) > self.MAX_ROWS:
            raise ValueError("Dataset has too many rows")

        if len(df.columns) > self.MAX_COLUMNS:
            raise ValueError("Dataset has too many columns")

        total_cell_chars = 0
        for value in df.to_numpy(dtype=object).flat:
            if isinstance(value, str):
                value_length = len(value)
                if value_length > self.MAX_CELL_CHARS:
                    raise ValueError("Dataset cell text is too large")
                total_cell_chars += value_length
                if total_cell_chars > self.MAX_TOTAL_CELL_CHARS:
                    raise ValueError("Dataset text is too large")

        cleaned_columns = []
        seen = {}

        for index, column in enumerate(df.columns):
            name = str(column).replace("\ufeff", "").strip()

            if not name or name.lower().startswith("unnamed:"):
                name = f"Column {index + 1}"

            if name in seen:
                seen[name] += 1
                name = f"{name} {seen[name]}"
            else:
                seen[name] = 1

            cleaned_columns.append(name)

        df.columns = cleaned_columns

        # Replace Pandas missing values with Python None for JSON.
        df = df.astype(object)
        df = df.where(pd.notnull(df), None)

        # Convert problematic values for JSON safety.
        for column in df.columns:
            df[column] = df[column].map(self._json_safe_value)

        return df

    def _json_safe_value(self, value):
        if value is None:
            return None

        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return value

        if isinstance(value, pd.Timestamp):
            return value.isoformat()

        return value

    def _google_sheet_to_csv_url(self, url: str) -> str:
        parsed = urlparse(url)

        if parsed.hostname != "docs.google.com":
            raise ValueError("Not a valid Google Sheets URL")

        if "/pubhtml" in parsed.path or parsed.path.endswith("/pub"):
            base_url = url.split("?")[0].replace("/pubhtml", "/pub")
            query = parse_qs(parsed.query)
            gid = query.get("gid", [None])[0]
            return f"{base_url}?output=csv" + (f"&gid={gid}" if gid else "")

        parts = parsed.path.split("/")

        try:
            sheet_id = parts[parts.index("d") + 1]
        except (ValueError, IndexError):
            raise ValueError("Could not extract Google Sheet ID from URL")

        query = parse_qs(parsed.query)
        fragment = parse_qs(parsed.fragment)
        gid = query.get("gid", fragment.get("gid", [None]))[0]

        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        return f"{csv_url}&gid={gid}" if gid else csv_url

    def _json_to_dataframe(self, data) -> pd.DataFrame:
        if isinstance(data, list):
            return pd.DataFrame(data)

        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    return pd.DataFrame(value)

            return pd.DataFrame([data])

        raise ValueError("Unsupported JSON structure")

    def _is_excel_content_type(self, content_type: str) -> bool:
        return (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_type
            or "application/vnd.ms-excel" in content_type
        )

    def _get_extension(self, path_or_url: str) -> str:
        path = urlparse(path_or_url).path
        return Path(path).suffix.lower()

    def _is_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in ["http", "https"]

    def _is_google_sheets_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return (
            parsed.scheme in ["http", "https"]
            and parsed.hostname == "docs.google.com"
            and "/spreadsheets/" in parsed.path
        )

    def _resolve_uploaded_file(self, file_path: str) -> Path:
        if self.tenant_id is None or self.user_id is None:
            upload_root = get_data_upload_dir().resolve()
            requested = Path(file_path)
            resolved = (Path.cwd() / requested).resolve() if not requested.is_absolute() else requested.resolve()

            if upload_root != resolved and upload_root not in resolved.parents:
                raise ValueError("Only uploaded data files can be read")

            if not resolved.is_file():
                raise ValueError("Uploaded data file was not found")

            return resolved

        try:
            requested = Path(file_path)
            if not requested.is_absolute() and len(requested.parts) == 1:
                file_path = str(
                    self._scoped_upload_root(get_data_upload_dir())
                    / requested.name
                )
            return resolve_private_user_file_path(
                file_path,
                storage_root=get_data_upload_dir(),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                allowed_extensions=self.SUPPORTED_EXTENSIONS,
            )
        except FileNotFoundError as error:
            raise ValueError("Uploaded data file was not found") from error
        except (PermissionError, ValueError) as error:
            raise ValueError("Only uploaded data files can be read") from error

    def _scoped_upload_root(self, upload_root: Path) -> Path:
        if self.tenant_id is None or self.user_id is None:
            return upload_root

        return (
            upload_root
            / safe_scope_part("tenant", self.tenant_id)
            / safe_scope_part("user", self.user_id)
        ).resolve()

    def _safe_scope_part(self, prefix: str, value: str | int) -> str:
        try:
            return safe_scope_part(prefix, value)
        except ValueError as error:
            raise ValueError("Invalid upload storage scope") from error

    def _remote_dataset_urls_enabled(self) -> bool:
        return (os.getenv("ALLOW_REMOTE_DATASET_URLS") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _assert_remote_dataset_urls_enabled(self) -> None:
        if not self._remote_dataset_urls_enabled():
            raise RemoteDatasetUrlsDisabledError(self.REMOTE_DATASET_URLS_DISABLED_MESSAGE)
