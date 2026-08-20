from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

import pandas as pd


SENSITIVE_COLUMN_KEYWORDS = {
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_key",
    "refresh_token",
    "jwt",
    "auth",
    "credential",
    "credentials",
    "email",
    "e_mail",
    "mail",
    "phone",
    "mobile",
    "telephone",
    "tel",
    "address",
    "location",
    "latitude",
    "longitude",
    "lat",
    "lng",
    "name",
    "full_name",
    "firstname",
    "lastname",
    "first_name",
    "last_name",
    "username",
    "user_name",
    "customer_name",
    "client_name",
    "national_id",
    "ssn",
    "passport",
    "iban",
    "bank",
    "card",
    "credit",
    "debit",
    "cvv",
    "cvc",
    "pin",
    "otp",
    "ip",
    "ip_address",
    "session",
    "cookie",
    "uuid",
    "guid",
    "id_number",
    "رقم",
    "كلمة_المرور",
    "كلمةالمرور",
    "كلمة السر",
    "كلمه السر",
    "الرقم السري",
    "رمز",
    "توكن",
    "سر",
    "مفتاح",
    "مفتاح_سري",
    "البريد",
    "بريد",
    "ايميل",
    "إيميل",
    "البريد الإلكتروني",
    "الهاتف",
    "جوال",
    "موبايل",
    "تلفون",
    "العنوان",
    "عنوان",
    "الموقع",
    "الاسم",
    "اسم",
    "الاسم الكامل",
    "الاسم_الكامل",
    "الهوية",
    "رقم الهوية",
    "الرقم الوطني",
    "جواز",
    "جواز السفر",
    "بطاقة",
    "بطاقة ائتمان",
    "ائتمان",
    "بنك",
    "حساب",
    "ايبان",
    "آيبان",
}

SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE),
    re.compile(r"(\+?\d[\d\s().\-]{7,}\d)"),
    re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b[A-Za-z0-9_\-]{24,}\b"),
]

MAX_TEXT_VALUE_LENGTH = 120


def normalize_column_name(column_name: Any) -> str:
    return str(column_name).strip().lower().replace("-", "_").replace(" ", "_")


def is_sensitive_column(column_name: Any) -> bool:
    normalized = normalize_column_name(column_name)
    raw = str(column_name).strip().lower()

    for keyword in SENSITIVE_COLUMN_KEYWORDS:
        normalized_keyword = normalize_column_name(keyword)
        raw_keyword = str(keyword).strip().lower()

        if normalized_keyword and normalized_keyword in normalized:
            return True

        if raw_keyword and raw_keyword in raw:
            return True

    return False


def looks_sensitive_value(value: Any) -> bool:
    if value is None:
        return False

    text = str(value).strip()

    if not text:
        return False

    return any(pattern.search(text) for pattern in SENSITIVE_VALUE_PATTERNS)


def redact_if_sensitive(value: Any, column_name: Any) -> Any:
    if is_sensitive_column(column_name) or looks_sensitive_value(value):
        return "[REDACTED]"

    return make_json_safe(value)


def truncate_text(value: str, max_length: int = MAX_TEXT_VALUE_LENGTH) -> str:
    if len(value) <= max_length:
        return value

    return value[:max_length] + "..."


def make_json_safe(value: Any) -> Any:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

        return float(value)

    if isinstance(value, int):
        return int(value)

    if isinstance(value, bool):
        return bool(value)

    if isinstance(value, str):
        return truncate_text(value)

    return truncate_text(str(value))

def _safe_to_datetime(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
        )
    except TypeError:
        return pd.to_datetime(
            series,
            errors="coerce",
        )

def infer_column_kind(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    non_null_series = series.dropna()

    if non_null_series.empty:
        return "empty"

    converted_numeric = pd.to_numeric(non_null_series, errors="coerce")
    numeric_ratio = float(converted_numeric.notna().mean()) if len(non_null_series) else 0

    if numeric_ratio >= 0.9:
        return "numeric_like_text"

    converted_datetime = _safe_to_datetime(non_null_series)
    datetime_ratio = float(converted_datetime.notna().mean()) if len(non_null_series) else 0

    if datetime_ratio >= 0.9:
        return "datetime_like_text"

    unique_count = int(non_null_series.nunique(dropna=True))
    non_null_count = int(non_null_series.count())

    if unique_count <= min(50, max(10, non_null_count // 2)):
        return "categorical"

    average_length = float(non_null_series.astype(str).str.len().mean())

    if average_length > 80:
        return "long_text"

    return "text"


def get_safe_sample_values(
    series: pd.Series,
    column_name: Any,
    max_values: int = 5,
) -> list[Any]:
    values = series.dropna().drop_duplicates().head(max_values).tolist()

    if is_sensitive_column(column_name):
        return ["[REDACTED]"] if values else []

    safe_values = []

    for value in values:
        safe_values.append(redact_if_sensitive(value, column_name))

    return safe_values


def get_numeric_profile(series: pd.Series) -> dict[str, Any]:
    numeric_series = pd.to_numeric(series, errors="coerce").dropna()

    if numeric_series.empty:
        return {}

    result = {
        "min": make_json_safe(numeric_series.min()),
        "max": make_json_safe(numeric_series.max()),
        "mean": make_json_safe(numeric_series.mean()),
        "median": make_json_safe(numeric_series.median()),
        "std": make_json_safe(numeric_series.std()) if len(numeric_series) > 1 else None,
        "q1": make_json_safe(numeric_series.quantile(0.25)),
        "q3": make_json_safe(numeric_series.quantile(0.75)),
        "zero_count": int((numeric_series == 0).sum()),
        "negative_count": int((numeric_series < 0).sum()),
        "positive_count": int((numeric_series > 0).sum()),
    }

    return result


def get_datetime_profile(series: pd.Series) -> dict[str, Any]:
    datetime_series = pd.to_datetime(series, errors="coerce").dropna()

    if datetime_series.empty:
        return {}

    return {
        "min": make_json_safe(datetime_series.min()),
        "max": make_json_safe(datetime_series.max()),
    }


def get_categorical_profile(
    series: pd.Series,
    column_name: Any,
    max_top_values: int = 5,
) -> dict[str, Any]:
    if is_sensitive_column(column_name):
        return {"top_values": []}

    value_counts = series.dropna().astype(str).value_counts().head(max_top_values)

    top_values = []

    for value, count in value_counts.items():
        if looks_sensitive_value(value):
            safe_value = "[REDACTED]"
        else:
            safe_value = make_json_safe(value)

        top_values.append(
            {
                "value": safe_value,
                "count": int(count),
            }
        )

    return {"top_values": top_values}

def get_text_profile(series: pd.Series) -> dict[str, Any]:
    text_series = series.dropna().astype(str)

    if text_series.empty:
        return {}

    lengths = text_series.str.len()

    return {
        "min_length": int(lengths.min()),
        "max_length": int(lengths.max()),
        "mean_length": make_json_safe(lengths.mean()),
    }


def build_column_profile(
    df: pd.DataFrame,
    column_name: Any,
    max_sample_values: int = 5,
    max_top_values: int = 5,
) -> dict[str, Any]:
    series = df[column_name]
    row_count = int(len(df))
    missing_count = int(series.isna().sum())
    non_null_count = int(series.notna().sum())
    unique_count = int(series.nunique(dropna=True))
    kind = infer_column_kind(series)

    profile: dict[str, Any] = {
        "name": str(column_name),
        "dtype": str(series.dtype),
        "kind": kind,
        "is_sensitive": is_sensitive_column(column_name),
        "missing_count": missing_count,
        "missing_percent": round((missing_count / row_count) * 100, 2) if row_count else 0,
        "non_null_count": non_null_count,
        "unique_count": unique_count,
        "sample_values": get_safe_sample_values(
            series=series,
            column_name=column_name,
            max_values=max_sample_values,
        ),
    }

    if kind in {"numeric", "numeric_like_text"}:
        profile.update(get_numeric_profile(series))

    elif kind in {"datetime", "datetime_like_text"}:
        profile.update(get_datetime_profile(series))

    elif kind in {"categorical", "boolean"}:
        profile.update(
            get_categorical_profile(
                series=series,
                column_name=column_name,
                max_top_values=max_top_values,
            )
        )

    elif kind in {"text", "long_text"}:
        profile.update(get_text_profile(series))

    return profile


def build_safe_sample_rows(
    df: pd.DataFrame,
    max_rows: int = 3,
) -> list[dict[str, Any]]:
    if df.empty:
        return []

    sample_df = df.head(max_rows).copy()
    rows: list[dict[str, Any]] = []

    for _, row in sample_df.iterrows():
        safe_row: dict[str, Any] = {}

        for column_name, value in row.items():
            safe_row[str(column_name)] = redact_if_sensitive(value, column_name)

        rows.append(safe_row)

    return rows


def build_dataframe_profile(
    df: pd.DataFrame,
    dataset_name: str | None = None,
    max_columns: int = 100,
    max_sample_rows: int = 3,
    max_sample_values: int = 5,
    max_top_values: int = 5,
) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("build_dataframe_profile expects a pandas DataFrame")

    safe_df = df.copy()
    safe_df.columns = [str(column) for column in safe_df.columns]

    limited_columns = list(safe_df.columns[:max_columns])
    limited_df = safe_df[limited_columns].copy()

    duplicate_columns = safe_df.columns[safe_df.columns.duplicated()].tolist()

    return {
        "dataset_name": dataset_name or "uploaded_dataset",
        "row_count": int(len(safe_df)),
        "column_count": int(len(safe_df.columns)),
        "profiled_column_count": int(len(limited_columns)),
        "columns_truncated": bool(len(safe_df.columns) > max_columns),
        "duplicate_columns": [str(column) for column in duplicate_columns],
        "columns": [
            build_column_profile(
                df=limited_df,
                column_name=column_name,
                max_sample_values=max_sample_values,
                max_top_values=max_top_values,
            )
            for column_name in limited_columns
        ],
        "sample_rows": build_safe_sample_rows(
            df=limited_df,
            max_rows=max_sample_rows,
        ),
    }


def get_allowed_columns_from_profile(profile: dict[str, Any]) -> set[str]:
    return {
        str(column["name"])
        for column in profile.get("columns", [])
        if "name" in column
    }