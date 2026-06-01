import unittest

import pandas as pd

from data_analysis.data_reading import DataReadingNormal


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


if __name__ == "__main__":
    unittest.main()
