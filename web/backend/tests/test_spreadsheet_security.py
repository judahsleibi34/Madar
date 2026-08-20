import csv
from io import BytesIO, StringIO
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from data_analysis import services as data_services
from services.spreadsheet_security import (
    sanitize_spreadsheet_cell,
    sanitize_spreadsheet_dataframe,
    sanitize_spreadsheet_row,
    sanitize_spreadsheet_rows,
)


class SpreadsheetSecurityTests(unittest.TestCase):
    def test_formula_like_strings_are_prefixed_with_single_quote(self):
        cases = {
            '=HYPERLINK("http://evil.example","click")': '\'=HYPERLINK("http://evil.example","click")',
            "+cmd": "'+cmd",
            "-SUM(1,2)": "'-SUM(1,2)",
            "@formula": "'@formula",
            "\t=FORMULA": "'\t=FORMULA",
            "\r=FORMULA": "'\r=FORMULA",
            "   =FORMULA": "'   =FORMULA",
            "  +cmd": "'  +cmd",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sanitize_spreadsheet_cell(raw), expected)

    def test_safe_values_and_non_strings_are_preserved(self):
        self.assertEqual(sanitize_spreadsheet_cell("normal text"), "normal text")
        self.assertEqual(sanitize_spreadsheet_cell("123"), "123")
        self.assertIsNone(sanitize_spreadsheet_cell(None))
        self.assertEqual(sanitize_spreadsheet_cell(-123), -123)
        self.assertEqual(sanitize_spreadsheet_cell(0), 0)

    def test_string_negative_value_is_sanitized(self):
        self.assertEqual(sanitize_spreadsheet_cell("-123"), "'-123")

    def test_dataframe_sanitizes_string_cells_and_headers(self):
        df = pd.DataFrame(
            {
                "=header": ["=HYPERLINK()", "normal text"],
                "number": [-123, 7],
                "mixed": ["@formula", "\t=FORMULA"],
            }
        )

        sanitized = sanitize_spreadsheet_dataframe(df)

        self.assertEqual(list(sanitized.columns), ["'=header", "number", "mixed"])
        self.assertEqual(sanitized.iloc[0, 0], "'=HYPERLINK()")
        self.assertEqual(sanitized.iloc[1, 0], "normal text")
        self.assertEqual(sanitized.iloc[0, 1], -123)
        self.assertEqual(sanitized.iloc[0, 2], "'@formula")
        self.assertEqual(sanitized.iloc[1, 2], "'\t=FORMULA")
        self.assertEqual(list(df.columns), ["=header", "number", "mixed"])
        self.assertEqual(df.iloc[0, 0], "=HYPERLINK()")

    def test_row_helpers_sanitize_dicts_lists_and_headers(self):
        row = {"=field": ["+cmd", {"safe": "-SUM(1,2)"}], "count": -123}

        self.assertEqual(
            sanitize_spreadsheet_row(row),
            {"'=field": ["'+cmd", {"safe": "'-SUM(1,2)"}], "count": -123},
        )
        self.assertEqual(sanitize_spreadsheet_rows([["@formula"]]), [["'@formula"]])

    def test_csv_export_output_contains_sanitized_values(self):
        df = pd.DataFrame(
            {
                "name": [
                    '=HYPERLINK("http://evil.example","click")',
                    "+cmd",
                    "-SUM(1,2)",
                    "@formula",
                    "\t=FORMULA",
                    "\r=FORMULA",
                    "   =FORMULA",
                    "normal text",
                ],
                "amount": [-123, "-123", 0, 1, 2, 3, 4, 5],
            }
        )

        with patch.object(data_services, "read_dataset", return_value=df):
            result = data_services.export_dataset("dataset.csv", tenant_id="1", user_id="1")

        csv_output = result["csv"]
        rows = list(csv.DictReader(StringIO(csv_output)))

        self.assertEqual(rows[0]["name"], '\'=HYPERLINK("http://evil.example","click")')
        self.assertEqual(rows[1]["name"], "'+cmd")
        self.assertEqual(rows[2]["name"], "'-SUM(1,2)")
        self.assertEqual(rows[3]["name"], "'@formula")
        self.assertEqual(rows[4]["name"], "'\t=FORMULA")
        self.assertEqual(rows[5]["name"], "'\r=FORMULA")
        self.assertEqual(rows[6]["name"], "'   =FORMULA")
        self.assertEqual(rows[7]["name"], "normal text")
        self.assertEqual(rows[0]["amount"], "-123")
        self.assertEqual(rows[1]["amount"], "'-123")

    def test_excel_output_contains_sanitized_values_when_written(self):
        df = pd.DataFrame({"name": ["=FORMULA", "normal text"], "amount": [-123, "-123"]})
        output = BytesIO()

        sanitize_spreadsheet_dataframe(df).to_excel(output, index=False, engine="openpyxl")
        output.seek(0)

        worksheet = load_workbook(output, data_only=False).active
        self.assertEqual(worksheet["A2"].value, "'=FORMULA")
        self.assertEqual(worksheet["A3"].value, "normal text")
        self.assertEqual(worksheet["B2"].value, -123)
        self.assertEqual(worksheet["B3"].value, "'-123")


if __name__ == "__main__":
    unittest.main()
