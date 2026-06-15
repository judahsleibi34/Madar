import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
