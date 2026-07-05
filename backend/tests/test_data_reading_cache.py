import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from fastapi import HTTPException

from data_analysis import services as data_services
from data_analysis.data_reading import DataReadingNormal
from data_analysis.io.data_reading import RemoteDatasetUrlsDisabledError


class FakeReader(DataReadingNormal):
    def __init__(self):
        super().__init__("uploads/fake.csv")
        self.calls = 0

    def _read_local_file(self, file_path: str) -> pd.DataFrame:
        self.calls += 1
        return pd.DataFrame({"value": [self.calls]})

    def _shared_cache_key(self):
        return None


class DataReadingCacheTests(unittest.TestCase):
    def setUp(self):
        DataReadingNormal.clear_shared_cache()

    def test_read_uses_per_instance_cache_and_returns_copy(self):
        reader = FakeReader()

        first = reader.read()
        first.loc[0, "value"] = 999
        second = reader.read()

        self.assertEqual(reader.calls, 1)
        self.assertEqual(second.loc[0, "value"], 1)

    def test_read_refresh_bypasses_cache(self):
        reader = FakeReader()

        reader.read()
        refreshed = reader.read(refresh=True)

        self.assertEqual(reader.calls, 2)
        self.assertEqual(refreshed.loc[0, "value"], 2)

    def test_clear_cache_forces_next_read(self):
        reader = FakeReader()

        reader.read()
        reader.clear_cache()
        reader.read()

        self.assertEqual(reader.calls, 2)

    def test_shared_cache_reuses_data_across_instances(self):
        class SharedFakeReader(FakeReader):
            shared_calls = 0

            def _shared_cache_key(self) -> str:
                return "shared:test"

            def _read_local_file(self, file_path: str) -> pd.DataFrame:
                type(self).shared_calls += 1
                return pd.DataFrame({"value": [type(self).shared_calls]})

        first_reader = SharedFakeReader()
        second_reader = SharedFakeReader()

        first = first_reader.read()
        second = second_reader.read()

        self.assertEqual(SharedFakeReader.shared_calls, 1)
        self.assertEqual(first.loc[0, "value"], 1)
        self.assertEqual(second.loc[0, "value"], 1)

    def test_shared_cache_refresh_bypasses_cache(self):
        class SharedFakeReader(FakeReader):
            shared_calls = 0

            def _shared_cache_key(self) -> str:
                return "shared:refresh"

            def _read_local_file(self, file_path: str) -> pd.DataFrame:
                type(self).shared_calls += 1
                return pd.DataFrame({"value": [type(self).shared_calls]})

        reader = SharedFakeReader()

        reader.read()
        refreshed = reader.read(refresh=True)

        self.assertEqual(SharedFakeReader.shared_calls, 2)
        self.assertEqual(refreshed.loc[0, "value"], 2)


class DataReadingRemoteUrlSecurityTests(unittest.TestCase):
    def setUp(self):
        DataReadingNormal.clear_shared_cache()

    def test_remote_https_url_is_disabled_by_default(self):
        reader = DataReadingNormal("https://example.com/file.csv")

        with self.assertRaisesRegex(
            RemoteDatasetUrlsDisabledError,
            DataReadingNormal.REMOTE_DATASET_URLS_DISABLED_MESSAGE,
        ):
            reader.read()

    def test_remote_http_url_is_disabled_by_default(self):
        reader = DataReadingNormal("http://example.com/file.csv")

        with self.assertRaisesRegex(
            RemoteDatasetUrlsDisabledError,
            DataReadingNormal.REMOTE_DATASET_URLS_DISABLED_MESSAGE,
        ):
            reader.read()

    def test_process_read_returns_clear_http_error_when_remote_urls_disabled(self):
        with self.assertRaises(HTTPException) as context:
            data_services.process_read("https://example.com/file.csv", tenant_id=1, user_id=2)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            DataReadingNormal.REMOTE_DATASET_URLS_DISABLED_MESSAGE,
        )

    def test_uploaded_dataset_read_still_works_when_remote_urls_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_root = Path(temp_dir).resolve()
            data_dir = upload_root / "tenant_1" / "user_2"
            data_dir.mkdir(parents=True)
            csv_path = data_dir / "data.csv"
            csv_path.write_text("name,value\nA,1\n", encoding="utf-8")

            with patch.dict("os.environ", {"DATA_UPLOAD_DIR": str(upload_root)}, clear=False):
                reader = DataReadingNormal(str(csv_path), tenant_id=1, user_id=2)
                df = reader.read()

        self.assertEqual(df.to_dict("records"), [{"name": "A", "value": 1}])

    def test_remote_enabled_still_blocks_ssrf_and_unsafe_schemes(self):
        reader = DataReadingNormal("uploads/fake.csv")
        blocked_urls = [
            "https://127.0.0.1/file.csv",
            "https://localhost/file.csv",
            "https://169.254.169.254/latest/meta-data",
            "https://10.0.0.1/file.csv",
            "https://172.16.0.1/file.csv",
            "https://192.168.1.1/file.csv",
            "https://[::1]/file.csv",
            "file:///etc/passwd",
            "ftp://example.com/file.csv",
            "gopher://example.com/file.csv",
            "//evil.com/file.csv",
        ]

        with patch.dict("os.environ", {"ALLOW_REMOTE_DATASET_URLS": "true"}, clear=False):
            for url in blocked_urls:
                with self.subTest(url=url):
                    with self.assertRaises(ValueError):
                        reader._validate_public_url(url)

    def test_remote_enabled_requires_https_by_default(self):
        reader = DataReadingNormal("uploads/fake.csv")

        with patch.dict("os.environ", {"ALLOW_REMOTE_DATASET_URLS": "true"}, clear=False):
            with self.assertRaisesRegex(ValueError, "must use HTTPS"):
                reader._validate_public_url("http://example.com/file.csv")

    def test_remote_enabled_redirect_to_private_target_is_blocked(self):
        redirect_response = Mock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"Location": "http://127.0.0.1/private.csv"}
        redirect_response.close = Mock()

        public_address = [(2, 1, 6, "", ("93.184.216.34", 80))]
        private_address = [(2, 1, 6, "", ("127.0.0.1", 80))]

        def fake_getaddrinfo(host, port, type=None):
            if host == "example.com":
                return public_address
            if host == "127.0.0.1":
                return private_address
            raise AssertionError(f"Unexpected host: {host}")

        with patch.dict(
            "os.environ",
            {
                "ALLOW_REMOTE_DATASET_URLS": "true",
                "ALLOW_INSECURE_REMOTE_DATASET_HTTP": "true",
            },
            clear=False,
        ), patch("data_analysis.io.data_reading.requests.get", return_value=redirect_response), patch(
            "data_analysis.io.data_reading.socket.getaddrinfo", side_effect=fake_getaddrinfo
        ):
            reader = DataReadingNormal("http://example.com/file.csv")
            with self.assertRaisesRegex(ValueError, "Private or local network"):
                reader._fetch_public_url("http://example.com/file.csv")


class DataReadingExcelSafetyTests(unittest.TestCase):
    def setUp(self):
        DataReadingNormal.clear_shared_cache()

    def _scoped_path(self, filename: str):
        temp_dir = tempfile.TemporaryDirectory()
        upload_root = Path(temp_dir.name).resolve()
        data_dir = upload_root / "tenant_1" / "user_2"
        data_dir.mkdir(parents=True)
        return temp_dir, upload_root, data_dir / filename

    def _write_workbook(self, path: Path, rows=None, sheet_count: int = 1):
        from openpyxl import Workbook

        workbook = Workbook()
        active = workbook.active
        active.title = "Sheet1"

        for row in rows or [["name", "value"], ["A", 1]]:
            active.append(row)

        for index in range(2, sheet_count + 1):
            sheet = workbook.create_sheet(f"Sheet{index}")
            sheet.append(["name", "value"])
            sheet.append(["B", index])

        workbook.save(path)
        workbook.close()

    def test_normal_small_xlsx_is_accepted(self):
        temp_dir, upload_root, xlsx_path = self._scoped_path("small.xlsx")
        with temp_dir:
            self._write_workbook(xlsx_path)

            with patch.dict("os.environ", {"DATA_UPLOAD_DIR": str(upload_root)}, clear=False):
                reader = DataReadingNormal(str(xlsx_path), tenant_id=1, user_id=2)
                df = reader.read()

        self.assertEqual(df.to_dict("records"), [{"name": "A", "value": 1}])

    def test_corrupt_xlsx_is_rejected_cleanly(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("corrupt.xlsx")
        with temp_dir:
            xlsx_path.write_bytes(b"not-a-valid-zip")
            reader = DataReadingNormal("uploads/fake.csv")

            with self.assertRaisesRegex(ValueError, "Invalid or corrupt Excel workbook"):
                reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_too_many_zip_entries_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("entries.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr("a.xml", "a")
                archive.writestr("b.xml", "b")
                archive.writestr("c.xml", "c")

            reader = DataReadingNormal("uploads/fake.csv")
            with patch.object(DataReadingNormal, "MAX_EXCEL_ZIP_ENTRIES", 2):
                with self.assertRaisesRegex(ValueError, "too many ZIP entries"):
                    reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_excessive_uncompressed_size_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("large-uncompressed.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("xl/worksheets/sheet1.xml", "x" * 128)

            reader = DataReadingNormal("uploads/fake.csv")
            with patch.object(DataReadingNormal, "MAX_EXCEL_UNCOMPRESSED_BYTES", 64):
                with self.assertRaisesRegex(ValueError, "too large after decompression"):
                    reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_path_traversal_entry_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("traversal.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr("xl/../evil.xml", "bad")

            reader = DataReadingNormal("uploads/fake.csv")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP entry path"):
                reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_backslash_entry_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("backslash.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr("xl/evil.xml", "bad")
            xlsx_path.write_bytes(xlsx_path.read_bytes().replace(b"xl/evil.xml", b"xl\\evil.xml"))

            reader = DataReadingNormal("uploads/fake.csv")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP entry path"):
                reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_absolute_entry_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("absolute.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr("/xl/evil.xml", "bad")

            reader = DataReadingNormal("uploads/fake.csv")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP entry path"):
                reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_windows_drive_entry_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("drive.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr("C:/evil.xml", "bad")

            reader = DataReadingNormal("uploads/fake.csv")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP entry path"):
                reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_with_long_zip_entry_name_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("long-name.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w") as archive:
                archive.writestr(f"xl/{'a' * 64}.xml", "bad")

            reader = DataReadingNormal("uploads/fake.csv")
            with patch.object(DataReadingNormal, "MAX_EXCEL_ZIP_ENTRY_NAME_CHARS", 20):
                with self.assertRaisesRegex(ValueError, "unsafe ZIP entry path"):
                    reader._validate_xlsx_file(xlsx_path)

    def test_xlsx_zip_bomb_ratio_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("ratio.xlsx")
        with temp_dir:
            with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("xl/worksheets/sheet1.xml", "x" * (1024 * 1024 + 1))

            reader = DataReadingNormal("uploads/fake.csv")
            with patch.object(DataReadingNormal, "MAX_EXCEL_ZIP_COMPRESSION_RATIO", 2):
                with self.assertRaisesRegex(ValueError, "suspicious compression ratio"):
                    reader._validate_xlsx_file(xlsx_path)

    def test_workbook_with_too_many_sheets_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("sheets.xlsx")
        with temp_dir:
            self._write_workbook(xlsx_path, sheet_count=2)
            reader = DataReadingNormal("uploads/fake.csv")

            with patch.object(DataReadingNormal, "MAX_EXCEL_SHEETS", 1):
                with self.assertRaisesRegex(ValueError, "too many sheets"):
                    reader._validate_xlsx_workbook(xlsx_path)

    def test_workbook_with_too_many_rows_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("rows.xlsx")
        with temp_dir:
            self._write_workbook(xlsx_path, rows=[["name"], ["A"]])
            reader = DataReadingNormal("uploads/fake.csv")

            with patch.object(DataReadingNormal, "MAX_EXCEL_ROWS", 1):
                with self.assertRaisesRegex(ValueError, "too many rows"):
                    reader._validate_xlsx_workbook(xlsx_path)

    def test_workbook_with_too_many_columns_is_rejected(self):
        temp_dir, _upload_root, xlsx_path = self._scoped_path("columns.xlsx")
        with temp_dir:
            self._write_workbook(xlsx_path, rows=[["a", "b"], [1, 2]])
            reader = DataReadingNormal("uploads/fake.csv")

            with patch.object(DataReadingNormal, "MAX_EXCEL_COLUMNS", 1):
                with self.assertRaisesRegex(ValueError, "too many columns"):
                    reader._validate_xlsx_workbook(xlsx_path)

    def test_workbook_cell_text_limit_is_enforced_after_parse(self):
        temp_dir, upload_root, xlsx_path = self._scoped_path("cell-text.xlsx")
        with temp_dir:
            self._write_workbook(xlsx_path, rows=[["note"], ["x" * 16]])

            with patch.dict("os.environ", {"DATA_UPLOAD_DIR": str(upload_root)}, clear=False), patch.object(
                DataReadingNormal, "MAX_EXCEL_CELL_CHARS", 8
            ):
                reader = DataReadingNormal(str(xlsx_path), tenant_id=1, user_id=2)
                with self.assertRaisesRegex(RuntimeError, "Failed to read data") as context:
                    reader.read()

        self.assertIsInstance(context.exception.__cause__, ValueError)
        self.assertIn("Excel cell text is too large", str(context.exception.__cause__))

    def test_valid_small_csv_is_accepted(self):
        temp_dir, upload_root, csv_path = self._scoped_path("small.csv")
        with temp_dir:
            csv_path.write_text("name,value\nA,1\n", encoding="utf-8")

            with patch.dict("os.environ", {"DATA_UPLOAD_DIR": str(upload_root)}, clear=False):
                reader = DataReadingNormal(str(csv_path), tenant_id=1, user_id=2)
                df = reader.read()

        self.assertEqual(df.to_dict("records"), [{"name": "A", "value": 1}])

    def test_empty_csv_is_rejected(self):
        reader = DataReadingNormal("uploads/fake.csv")

        with self.assertRaisesRegex(ValueError, "CSV file is empty"):
            reader._read_csv_bytes(b"")

    def test_oversized_csv_is_rejected(self):
        reader = DataReadingNormal("uploads/fake.csv")

        with patch.object(DataReadingNormal, "MAX_CSV_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "CSV file is too large"):
                reader._read_csv_bytes(b"name,value\nA,1\n")

    def test_binary_csv_is_rejected(self):
        reader = DataReadingNormal("uploads/fake.csv")

        with self.assertRaisesRegex(ValueError, "binary"):
            reader._read_csv_bytes(b"name,value\nA,\x00\x01\x02\n")

    def test_csv_cell_text_limit_is_enforced(self):
        reader = DataReadingNormal("uploads/fake.csv")

        with patch.object(DataReadingNormal, "MAX_CELL_CHARS", 4):
            with self.assertRaisesRegex(ValueError, "cell text is too large"):
                reader._read_csv_bytes(b"name\nabcdef\n")

    def test_parser_workspace_is_cleaned_after_success(self):
        temp_dir, upload_root, csv_path = self._scoped_path("workspace-success.csv")
        workspace_root = Path(tempfile.mkdtemp())
        try:
            with temp_dir:
                csv_path.write_text("name,value\nA,1\n", encoding="utf-8")

                with patch.dict(
                    "os.environ",
                    {
                        "DATA_UPLOAD_DIR": str(upload_root),
                        "MADAR_UPLOAD_WORKSPACE_DIR": str(workspace_root),
                    },
                    clear=False,
                ), patch.object(DataReadingNormal, "PARSER_WORKSPACE_BASE", str(workspace_root)):
                    reader = DataReadingNormal(str(csv_path), tenant_id=1, user_id=2)
                    reader.read()

            self.assertEqual(list(workspace_root.iterdir()), [])
        finally:
            workspace_root.rmdir()

    def test_parser_workspace_is_cleaned_after_failure(self):
        temp_dir, upload_root, csv_path = self._scoped_path("workspace-failure.csv")
        workspace_root = Path(tempfile.mkdtemp())
        try:
            with temp_dir:
                csv_path.write_bytes(b"\x00\x01not-csv")

                with patch.dict(
                    "os.environ",
                    {
                        "DATA_UPLOAD_DIR": str(upload_root),
                        "MADAR_UPLOAD_WORKSPACE_DIR": str(workspace_root),
                    },
                    clear=False,
                ), patch.object(DataReadingNormal, "PARSER_WORKSPACE_BASE", str(workspace_root)):
                    reader = DataReadingNormal(str(csv_path), tenant_id=1, user_id=2)
                    with self.assertRaisesRegex(RuntimeError, "Failed to read data"):
                        reader.read()

            self.assertEqual(list(workspace_root.iterdir()), [])
        finally:
            workspace_root.rmdir()


if __name__ == "__main__":
    unittest.main()
