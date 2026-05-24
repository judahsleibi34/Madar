import pandas as pd
import requests

from io import StringIO, BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class DataReadingNormal:
    SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}

    def __init__(self, input_path: str) -> None:
        if not input_path:
            raise ValueError("input_path is required")

        self.input_path = input_path

    def read(self) -> pd.DataFrame:
        try:
            if self._is_google_sheets_url(self.input_path):
                return self._read_google_sheet(self.input_path)

            if self._is_url(self.input_path):
                return self._read_from_url_or_api(self.input_path)

            return self._read_local_file(self.input_path)

        except Exception as e:
            raise RuntimeError(f"Failed to read data: {e}") from e

    def _read_local_file(self, file_path: str) -> pd.DataFrame:
        extension = self._get_extension(file_path)

        if extension == ".csv":
            return pd.read_csv(file_path)

        if extension in [".xls", ".xlsx"]:
            return pd.read_excel(file_path)

        raise ValueError(
            f"Unsupported file format: {extension}. "
            "Supported formats are .csv, .xls, and .xlsx"
        )

    def _read_from_url_or_api(self, url: str) -> pd.DataFrame:
        extension = self._get_extension(url)

        if extension == ".csv":
            return pd.read_csv(url)

        if extension in [".xls", ".xlsx"]:
            return pd.read_excel(url)

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        if "application/json" in content_type or url.lower().endswith(".json"):
            data = response.json()
            return self._json_to_dataframe(data)

        if "text/csv" in content_type or "csv" in content_type:
            return pd.read_csv(StringIO(response.text))

        if (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_type
            or "application/vnd.ms-excel" in content_type
        ):
            return pd.read_excel(BytesIO(response.content))

        raise ValueError(
            "Could not detect data format from URL/API. "
            "Expected CSV, Excel, JSON, or Google Sheets."
        )

    def _read_google_sheet(self, url: str) -> pd.DataFrame:
        csv_url = self._google_sheet_to_csv_url(url)
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(csv_url, timeout=30, headers=headers)

        if not response.ok:
            raise ValueError(
                "Google Sheet could not be read. Make sure it is shared with "
                "'Anyone with the link' or published to the web, and paste the "
                "full sheet link including the tab if needed."
            )

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" in content_type or response.text.lstrip().startswith("<"):
            raise ValueError(
                "Google returned a page instead of spreadsheet data. Share the "
                "sheet publicly or use File > Share > Publish to web, then try again."
            )

        return pd.read_csv(StringIO(response.text))

    def _google_sheet_to_csv_url(self, url: str) -> str:
        parsed = urlparse(url)

        if "docs.google.com" not in parsed.netloc:
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
            and "docs.google.com" in parsed.netloc
            and "/spreadsheets/" in parsed.path
        )

