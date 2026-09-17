import unittest

import pandas as pd

from data_analysis.data_cleaning import DataCleaning


class DataCleaningPreparationTests(unittest.TestCase):
    def setUp(self):
        self.cleaner = DataCleaning("uploads/dummy.csv")

    def test_prepare_dataframe_normalizes_headers_and_money(self):
        df = pd.DataFrame({
            " Total Cost ": ["$1,200.50", "(300)", "₪ 40"],
            "Submitted At": ["2026-01-01", "2026-01-02", "bad"],
        })

        prepared, warnings = self.cleaner.prepare_dataframe(df)

        self.assertIn("Total Cost", prepared.columns)
        self.assertEqual(float(prepared["Total Cost"].sum()), 940.5)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(prepared["Submitted At"]))
        self.assertTrue(any("dates" in warning for warning in warnings))

    def test_boolean_and_arabic_digits_are_normalized(self):
        df = pd.DataFrame({
            "Approved": ["Yes", "no", "\u0646\u0639\u0645"],
            "Score": ["\u0661\u0662", "\u0663", "5"],
        })

        prepared, _warnings = self.cleaner.prepare_dataframe(df)

        self.assertTrue(pd.api.types.is_bool_dtype(prepared["Approved"]))
        self.assertEqual(float(prepared["Score"].sum()), 20.0)

    def test_convert_types_supports_multi_choice_and_money(self):
        df = pd.DataFrame({
            "Tags": ["Food; Water|Shelter", "Food, Health"],
            "Amount": ["$10", "$20"],
        })

        converted = self.cleaner._convert_types_on_dataframe(
            df,
            {"Tags": "multi_choice", "Amount": "money"},
        )

        self.assertEqual(converted["Tags"].iloc[0], "Food, Water, Shelter")
        self.assertEqual(float(converted["Amount"].sum()), 30.0)

    def test_profile_dataframe_detects_multi_choice(self):
        df = pd.DataFrame({"Needs": ["Food, Water", "Food, Health", "Shelter"]})

        profile = self.cleaner.profile_dataframe(df)

        self.assertEqual(profile["Needs"]["type"], "multi_choice")

    def test_prepare_dataframe_cache_returns_safe_copy(self):
        df = pd.DataFrame({"Amount": ["$10", "$20"]})

        first, _warnings = self.cleaner.prepare_dataframe(df)
        first.loc[0, "Amount"] = 999
        second, _warnings = self.cleaner.prepare_dataframe(df)

        self.assertEqual(float(second["Amount"].sum()), 30.0)


if __name__ == "__main__":
    unittest.main()
