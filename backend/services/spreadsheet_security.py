from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
from pandas.api.types import is_object_dtype, is_string_dtype


DANGEROUS_SPREADSHEET_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_spreadsheet_cell(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value

    candidate = value.lstrip(" ")
    if candidate and candidate[0] in DANGEROUS_SPREADSHEET_PREFIXES:
        return f"'{value}"

    return value


def sanitize_spreadsheet_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    sanitized = df.copy()
    sanitized.columns = [sanitize_spreadsheet_cell(column) for column in sanitized.columns]

    for index in range(len(sanitized.columns)):
        series = sanitized.iloc[:, index]
        if is_object_dtype(series.dtype) or is_string_dtype(series.dtype):
            sanitized.iloc[:, index] = series.map(sanitize_spreadsheet_cell)

    return sanitized


def sanitize_spreadsheet_row(row: Any) -> Any:
    if isinstance(row, Mapping):
        return {
            sanitize_spreadsheet_cell(key): sanitize_spreadsheet_row(value)
            for key, value in row.items()
        }

    if isinstance(row, tuple):
        return tuple(sanitize_spreadsheet_row(value) for value in row)

    if isinstance(row, list):
        return [sanitize_spreadsheet_row(value) for value in row]

    return sanitize_spreadsheet_cell(row)


def sanitize_spreadsheet_rows(rows: Sequence[Any]) -> list[Any]:
    return [sanitize_spreadsheet_row(row) for row in rows]
