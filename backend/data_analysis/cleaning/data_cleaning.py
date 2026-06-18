import re
import unicodedata
import warnings as warning_tools
from pandas.util import hash_pandas_object

import pandas as pd
from typing import Any, Literal

from data_analysis.io.data_reading import DataReadingNormal


class DataCleaning(DataReadingNormal):
    EMPTY_TEXT_VALUES = {"", "-", "--", "na", "n/a", "none", "null", "nan"}
    TRUE_VALUES = {"true", "yes", "y", "1", "on", "checked", "\u0646\u0639\u0645", "\u0627\u062c\u0644", "\u0635\u062d"}
    FALSE_VALUES = {"false", "no", "n", "0", "off", "unchecked", "\u0644\u0627", "\u062e\u0637\u0623"}

    def __init__(
        self,
        input_path: str,
        tenant_id: str | int | None = None,
        user_id: str | int | None = None,
    ) -> None:
        super().__init__(input_path, tenant_id=tenant_id, user_id=user_id)
        self._prepared_cache: dict[str, tuple[pd.DataFrame, list[str]]] = {}
        self._profile_cache: dict[tuple[str, int], dict] = {}

    def preview(self, rows: int = 5) -> list[dict]:
        df = self.read()
        return df.head(rows).to_dict(orient="records")

    def preparation_report(self, max_unique_values: int = 20) -> dict:
        df = self.read()
        prepared, warnings = self.prepare_dataframe(df)

        return {
            "rows": int(len(prepared)),
            "columns": list(prepared.columns),
            "warnings": warnings,
            "profiles": self.profile_dataframe(prepared, max_unique_values=max_unique_values),
        }

    def data_inspection(self, max_unique_values: int = 20) -> dict:
        df, warnings = self.prepare_dataframe(self.read())

        inspection = {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "unique_values": {},
            "warnings": warnings,
            "profiles": self.profile_dataframe(df, max_unique_values=max_unique_values),
        }

        for column in df.columns:
            unique_values = df[column].dropna().unique().tolist()

            inspection["unique_values"][column] = {
                "count": int(df[column].nunique(dropna=True)),
                "sample": unique_values[:max_unique_values],
                "missing_values": int(df[column].isna().sum())
            }

        return inspection

    def statistical_inspection(self, max_unique_values: int = 20) -> dict:
        df, warnings = self.prepare_dataframe(self.read())

        statistics = {
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "numeric_columns": {},
            "categorical_columns": {},
            "warnings": warnings,
            "profiles": self.profile_dataframe(df, max_unique_values=max_unique_values),
        }

        for column in df.columns:
            missing_values = int(df[column].isna().sum())
            filled_values = int(df[column].count())
            missing_percentage = round((missing_values / len(df)) * 100, 2) if len(df) else 0

            if pd.api.types.is_numeric_dtype(df[column]):
                statistics["numeric_columns"][column] = {
                    "filled_values": filled_values,
                    "mean": self._safe_float(df[column].mean()),
                    "median": self._safe_float(df[column].median()),
                    "min": self._safe_float(df[column].min()),
                    "max": self._safe_float(df[column].max()),
                    "std": self._safe_float(df[column].std()),
                    "sum": self._safe_float(df[column].sum()),
                    "missing_values": missing_values,
                    "missing_percentage": missing_percentage,
                }

            else:
                unique_values = df[column].dropna().unique().tolist()
                most_common = df[column].mode(dropna=True).tolist()

                statistics["categorical_columns"][column] = {
                    "filled_values": filled_values,
                    "unique_count": int(df[column].nunique(dropna=True)),
                    "most_common": most_common[:max_unique_values],
                    "examples": unique_values[:max_unique_values],
                    "missing_values": missing_values,
                    "missing_percentage": missing_percentage,
                }

        return statistics

    def missing_values_report(self) -> dict:
        df, _warnings = self.prepare_dataframe(self.read())
        report = {}

        for column in df.columns:
            missing_count = int(df[column].isna().sum())
            missing_percentage = (missing_count / len(df)) * 100 if len(df) > 0 else 0

            report[column] = {
                "missing_count": missing_count,
                "missing_percentage": round(float(missing_percentage), 2)
            }

        return report

    def quality_report(self, max_unique_values: int = 100) -> dict:
        df, warnings = self.prepare_dataframe(self.read())

        duplicate_count = int(df.duplicated().sum())
        total_rows = int(len(df))
        total_cells = int(df.shape[0] * df.shape[1])
        missing_cells = int(df.isna().sum().sum())
        duplicate_percentage = round((duplicate_count / total_rows) * 100, 2) if total_rows else 0
        missing_percentage = round((missing_cells / total_cells) * 100, 2) if total_cells else 0
        complete_cells = total_cells - missing_cells
        completion_percentage = round((complete_cells / total_cells) * 100, 2) if total_cells else 0
        quality_score = max(0, round(100 - missing_percentage - duplicate_percentage, 2))
        recommended_actions = []

        if missing_cells:
            recommended_actions.append("Review or fill empty answers before reporting.")
        if duplicate_count:
            recommended_actions.append("Remove duplicate rows before reporting.")
        if warnings:
            recommended_actions.append("Check columns that may have mixed formats.")
        if not recommended_actions:
            recommended_actions.append("No major cleanup needed before reporting.")

        return {
            "rows": total_rows,
            "columns": int(len(df.columns)),
            "duplicate_rows": duplicate_count,
            "duplicate_percentage": duplicate_percentage,
            "total_cells": total_cells,
            "complete_cells": complete_cells,
            "completion_percentage": completion_percentage,
            "missing_cells": missing_cells,
            "missing_percentage": missing_percentage,
            "quality_score": quality_score,
            "readiness": "Ready to use" if quality_score >= 90 else "Needs review",
            "recommended_actions": recommended_actions,
            "column_types": {column: str(df[column].dtype) for column in df.columns},
            "warnings": warnings,
            "profiles": self.profile_dataframe(df, max_unique_values=max_unique_values),
        }

    def column_types(self) -> dict:
        df, _warnings = self.prepare_dataframe(self.read())
        return {column: str(df[column].dtype) for column in df.columns}

    def rename_column(self, rename_map: dict[str, str]) -> pd.DataFrame:
        self._validate_dict(rename_map, "rename_map")

        df = self.read()

        missing_columns = [
            old_column
            for old_column in rename_map.keys()
            if old_column not in df.columns
        ]

        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")

        return df.rename(columns=rename_map)

    def rename_value(self, rename_map: dict[str, dict[Any, Any]]) -> pd.DataFrame:
        self._validate_dict(rename_map, "rename_map")

        df = self.read()

        for column, values_map in rename_map.items():
            if column not in df.columns:
                raise ValueError(f"Column '{column}' was not found")

            self._validate_dict(values_map, f"values_map for column '{column}'")

            df[column] = df[column].replace(values_map)

        return df

    def drop_missing_rows(
        self,
        how: Literal["any", "all"] = "any",
        columns: list[str] | None = None
    ) -> pd.DataFrame:
        df = self.read()

        if columns:
            self._validate_columns_exist(df, columns)

        return df.dropna(axis=0, how=how, subset=columns)

    def drop_duplicates(
        self,
        columns: list[str] | None = None,
        keep: Literal["first", "last", False] = "first"
    ) -> pd.DataFrame:
        df = self.read()

        if columns:
            self._validate_columns_exist(df, columns)

        return df.drop_duplicates(subset=columns, keep=keep)

    def fill_missing(self, fill_map: dict[str, dict[str, Any]]) -> pd.DataFrame:
        self._validate_dict(fill_map, "fill_map")
        df = self.read()
        return self._fill_missing_on_dataframe(df, fill_map)

    def convert_column_types(self, type_map: dict[str, str]) -> pd.DataFrame:
        self._validate_dict(type_map, "type_map")
        df = self.read()
        return self._convert_types_on_dataframe(df, type_map)

    def clean_text_columns(
        self,
        columns: list[str],
        lower: bool = True,
        strip: bool = True,
        collapse_spaces: bool = True
    ) -> pd.DataFrame:
        df = self.read()
        self._validate_columns_exist(df, columns)

        return self._clean_text_on_dataframe(
            df=df,
            columns=columns,
            lower=lower,
            strip=strip,
            collapse_spaces=collapse_spaces
        )

    def drop_columns(self, columns: list[str]) -> pd.DataFrame:
        df = self.read()
        self._validate_columns_exist(df, columns)
        return df.drop(columns=columns)

    def encode_columns(
        self,
        columns: list[str],
        method: str = "one_hot",
        keep_original: bool = False,
        max_unique_values: int = 50,
    ) -> pd.DataFrame:
        df = self.read()
        return self._encode_columns_on_dataframe(
            df,
            columns,
            method=method,
            keep_original=keep_original,
            max_unique_values=max_unique_values,
        )

    def outlier_report_iqr(
        self,
        columns: list[str],
        multiplier: float = 1.5
    ) -> dict:
        df = self.read()
        self._validate_columns_exist(df, columns)

        report = {}

        for column in columns:
            self._validate_numeric_column(df, column, "outlier_report_iqr")

            q1 = df[column].quantile(0.25)
            q3 = df[column].quantile(0.75)
            iqr = q3 - q1

            lower_bound = q1 - multiplier * iqr
            upper_bound = q3 + multiplier * iqr

            outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]

            report[column] = {
                "lower_bound": self._safe_float(lower_bound),
                "upper_bound": self._safe_float(upper_bound),
                "outlier_count": int(len(outliers)),
                "outlier_percentage": round(float((len(outliers) / len(df)) * 100), 2)
                if len(df) > 0 else 0
            }

        return report

    def remove_outliers_iqr(
        self,
        columns: list[str],
        multiplier: float = 1.5
    ) -> pd.DataFrame:
        df = self.read()
        self._validate_columns_exist(df, columns)

        for column in columns:
            self._validate_numeric_column(df, column, "remove_outliers_iqr")

            q1 = df[column].quantile(0.25)
            q3 = df[column].quantile(0.75)
            iqr = q3 - q1

            lower_bound = q1 - multiplier * iqr
            upper_bound = q3 + multiplier * iqr

            df = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]

        return df

    def correlation_report(self) -> dict:
        df = self.read()
        numeric_df = df.select_dtypes(include="number")

        if numeric_df.empty:
            return {}

        return numeric_df.corr().round(3).to_dict()

    def group_summary(
        self,
        group_column: str,
        numeric_columns: list[str]
    ) -> list[dict]:
        df = self.read()

        if group_column not in df.columns:
            raise ValueError(f"Column '{group_column}' was not found")

        self._validate_columns_exist(df, numeric_columns)

        for column in numeric_columns:
            self._validate_numeric_column(df, column, "group_summary")

        summary = df.groupby(group_column)[numeric_columns].agg(
            ["count", "mean", "median", "min", "max", "sum"]
        )

        summary.columns = ["_".join(col).strip() for col in summary.columns.values]

        return summary.reset_index().to_dict(orient="records")

    def apply_pipeline(self, actions: list[dict]) -> pd.DataFrame:
        df = self.read()

        for action in actions:
            action_type = action.get("type")
            params = action.get("params", {})

            if action_type == "normalize_headers":
                df = self._normalize_headers_on_dataframe(df)

            elif action_type == "standardize_missing":
                df = self._standardize_missing_on_dataframe(df)

            elif action_type == "rename_column":
                rename_map = params["rename_map"]
                self._validate_dict(rename_map, "rename_map")
                df = df.rename(columns=rename_map)

            elif action_type == "rename_value":
                rename_map = params["rename_map"]
                self._validate_dict(rename_map, "rename_map")

                for column, values_map in rename_map.items():
                    if column not in df.columns:
                        raise ValueError(f"Column '{column}' was not found")
                    self._validate_dict(values_map, f"values_map for column '{column}'")
                    df[column] = df[column].replace(values_map)

            elif action_type == "drop_missing_rows":
                columns = params.get("columns")
                how = params.get("how", "any")

                if columns:
                    self._validate_columns_exist(df, columns)

                df = df.dropna(subset=columns, how=how)

            elif action_type == "drop_duplicates":
                columns = params.get("columns")
                keep = params.get("keep", "first")

                if columns:
                    self._validate_columns_exist(df, columns)

                df = df.drop_duplicates(subset=columns, keep=keep)

            elif action_type == "fill_missing":
                fill_map = params["fill_map"]
                self._validate_dict(fill_map, "fill_map")
                df = self._fill_missing_on_dataframe(df, fill_map)

            elif action_type == "convert_column_types":
                type_map = params["type_map"]
                self._validate_dict(type_map, "type_map")
                df = self._convert_types_on_dataframe(df, type_map)

            elif action_type == "clean_text_columns":
                columns = params["columns"]
                lower = params.get("lower", True)
                strip = params.get("strip", True)
                collapse_spaces = params.get("collapse_spaces", True)
                normalize_unicode = params.get("normalize_unicode", True)

                self._validate_columns_exist(df, columns)

                df = self._clean_text_on_dataframe(
                    df=df,
                    columns=columns,
                    lower=lower,
                    strip=strip,
                    collapse_spaces=collapse_spaces,
                    normalize_unicode=normalize_unicode,
                )

            elif action_type == "normalize_multi_select":
                columns = params["columns"]
                separator = params.get("separator", ",")
                self._validate_columns_exist(df, columns)
                df = self._normalize_multi_select_on_dataframe(df, columns, separator=separator)

            elif action_type == "drop_columns":
                columns = params["columns"]
                self._validate_columns_exist(df, columns)
                df = df.drop(columns=columns)

            elif action_type == "encode_columns":
                columns = params["columns"]
                method = params.get("method", "one_hot")
                keep_original = bool(params.get("keep_original", False))
                max_unique_values = int(params.get("max_unique_values", 50))
                df = self._encode_columns_on_dataframe(
                    df,
                    columns,
                    method=method,
                    keep_original=keep_original,
                    max_unique_values=max_unique_values,
                )

            elif action_type == "remove_outliers_iqr":
                columns = params["columns"]
                multiplier = params.get("multiplier", 1.5)

                self._validate_columns_exist(df, columns)

                for column in columns:
                    self._validate_numeric_column(df, column, "remove_outliers_iqr")

                    q1 = df[column].quantile(0.25)
                    q3 = df[column].quantile(0.75)
                    iqr = q3 - q1

                    lower_bound = q1 - multiplier * iqr
                    upper_bound = q3 + multiplier * iqr

                    df = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]

            else:
                raise ValueError(f"Unsupported pipeline action: {action_type}")

        return df

    def prepare_dataframe(self, df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
        df = self.read() if df is None else df.copy()
        cache_key = self._dataframe_cache_key(df, "prepared")
        if cache_key in self._prepared_cache:
            cached_df, cached_warnings = self._prepared_cache[cache_key]
            return cached_df.copy(deep=True), list(cached_warnings)

        warnings: list[str] = []

        df = self._normalize_headers_on_dataframe(df)
        df = self._standardize_missing_on_dataframe(df)

        for column in df.columns:
            series = df[column]
            if not self._is_object_like(series):
                continue

            cleaned_text = series.map(self._normalize_text_value)
            numeric = self._coerce_numeric_series(cleaned_text)
            with warning_tools.catch_warnings():
                warning_tools.simplefilter("ignore", UserWarning)
                dates = pd.to_datetime(cleaned_text, errors="coerce")
            booleans = self._coerce_boolean_series(cleaned_text)
            non_null = max(int(cleaned_text.notna().sum()), 1)

            numeric_ratio = numeric.notna().sum() / non_null
            date_ratio = dates.notna().sum() / non_null
            bool_ratio = booleans.notna().sum() / non_null

            if bool_ratio >= 0.9:
                df[column] = booleans.astype("boolean")
            elif numeric_ratio >= 0.85 or (
                numeric_ratio >= 0.5 and self._looks_numeric_column(column, cleaned_text)
            ):
                df[column] = numeric
            elif date_ratio >= 0.85 or (date_ratio >= 0.5 and self._looks_date_column(column)):
                df[column] = dates
                invalid_dates = int(dates.isna().sum() - cleaned_text.isna().sum())
                if invalid_dates > 0:
                    warnings.append(f"Column '{column}' has {invalid_dates} values that could not be parsed as dates.")
            else:
                df[column] = cleaned_text

            if 0 < numeric_ratio < 0.85 and self._looks_numeric_column(column, cleaned_text):
                warnings.append(f"Column '{column}' looks numeric but only {numeric_ratio:.0%} of values could be parsed.")
            if 0 < date_ratio < 0.85 and self._looks_date_column(column):
                warnings.append(f"Column '{column}' looks like a date but only {date_ratio:.0%} of values could be parsed.")

        self._prepared_cache[cache_key] = (df.copy(deep=True), list(warnings))
        return df.copy(deep=True), list(warnings)

    def profile_dataframe(self, df: pd.DataFrame, max_unique_values: int = 20) -> dict:
        cache_key = (self._dataframe_cache_key(df, "profile"), max_unique_values)
        if cache_key in self._profile_cache:
            return self._profile_cache[cache_key].copy()

        profiles = {}

        for column in df.columns:
            series = df[column]
            missing_values = int(series.isna().sum())
            unique_values = series.dropna().unique().tolist()

            if pd.api.types.is_bool_dtype(series):
                inferred_type = "boolean"
            elif pd.api.types.is_numeric_dtype(series):
                lowered = str(column).lower()
                inferred_type = "money" if any(word in lowered for word in ["amount", "cost", "price", "revenue", "budget", "expense", "cash", "fund"]) else "number"
            elif pd.api.types.is_datetime64_any_dtype(series):
                inferred_type = "date"
            elif self._is_multi_select_series(series):
                inferred_type = "multi_choice"
            elif series.nunique(dropna=True) <= max(20, len(series) * 0.2):
                inferred_type = "category"
            else:
                inferred_type = "text"

            profiles[column] = {
                "type": inferred_type,
                "dtype": str(series.dtype),
                "count": int(series.count()),
                "missing_values": missing_values,
                "missing_percentage": round((missing_values / len(df)) * 100, 2) if len(df) else 0,
                "unique_count": int(series.nunique(dropna=True)),
                "sample": unique_values[:max_unique_values],
            }

            if pd.api.types.is_numeric_dtype(series):
                profiles[column].update({
                    "sum": self._safe_float(series.sum()),
                    "mean": self._safe_float(series.mean()),
                    "median": self._safe_float(series.median()),
                    "min": self._safe_float(series.min()),
                    "max": self._safe_float(series.max()),
                    "std": self._safe_float(series.std()),
                })

        self._profile_cache[cache_key] = profiles.copy()
        return profiles.copy()

    def _dataframe_cache_key(self, df: pd.DataFrame, namespace: str) -> str:
        try:
            row_hash = int(hash_pandas_object(df, index=True).sum())
        except Exception:
            row_hash = hash(tuple(map(str, df.head(50).to_dict(orient="records"))))
        columns = tuple(str(column) for column in df.columns)
        dtypes = tuple(str(dtype) for dtype in df.dtypes)
        return f"{namespace}:{df.shape}:{columns}:{dtypes}:{row_hash}"

    def _fill_missing_on_dataframe(
        self,
        df: pd.DataFrame,
        fill_map: dict[str, dict[str, Any]]
    ) -> pd.DataFrame:
        df = df.copy()

        for column, config in fill_map.items():
            if column not in df.columns:
                raise ValueError(f"Column '{column}' was not found")

            self._validate_dict(config, f"config for column '{column}'")

            method = config.get("method")

            if method == "mean":
                self._validate_numeric_column(df, column, method)
                df[column] = df[column].fillna(df[column].mean())

            elif method == "median":
                self._validate_numeric_column(df, column, method)
                df[column] = df[column].fillna(df[column].median())

            elif method == "mode":
                mode_values = df[column].mode(dropna=True)

                if mode_values.empty:
                    raise ValueError(f"Column '{column}' has no mode value")

                df[column] = df[column].fillna(mode_values.iloc[0])

            elif method == "constant":
                if "value" not in config:
                    raise ValueError(
                        f"Column '{column}' uses constant method but no value was provided"
                    )

                df[column] = df[column].fillna(config["value"])

            elif method == "forward_fill":
                df[column] = df[column].ffill()

            elif method == "backward_fill":
                df[column] = df[column].bfill()

            else:
                raise ValueError(
                    f"Unsupported fill method '{method}' for column '{column}'"
                )

        return df

    def _convert_types_on_dataframe(
        self,
        df: pd.DataFrame,
        type_map: dict[str, str]
    ) -> pd.DataFrame:
        df = df.copy()

        for column, target_type in type_map.items():
            if column not in df.columns:
                raise ValueError(f"Column '{column}' was not found")

            if target_type in {"datetime", "date"}:
                df[column] = pd.to_datetime(df[column], errors="coerce")

            elif target_type in {"numeric", "number", "money"}:
                df[column] = self._coerce_numeric_series(df[column])

            elif target_type in {"percent", "percentage"}:
                df[column] = self._coerce_numeric_series(df[column])

            elif target_type == "string":
                df[column] = df[column].map(self._normalize_text_value).astype("string")

            elif target_type == "category":
                df[column] = df[column].map(self._normalize_text_value).astype("category")

            elif target_type == "boolean":
                df[column] = self._coerce_boolean_series(df[column]).astype("boolean")

            elif target_type in {"multi_choice", "multi_select"}:
                df = self._normalize_multi_select_on_dataframe(df, [column])

            else:
                raise ValueError(f"Unsupported target type: {target_type}")

        return df

    def _clean_text_on_dataframe(
        self,
        df: pd.DataFrame,
        columns: list[str],
        lower: bool = True,
        strip: bool = True,
        collapse_spaces: bool = True,
        normalize_unicode: bool = True,
    ) -> pd.DataFrame:
        df = df.copy()

        for column in columns:
            if normalize_unicode:
                df[column] = df[column].map(self._normalize_text_value).astype("string")
            else:
                df[column] = df[column].astype("string")

            if strip:
                df[column] = df[column].str.strip()

            if collapse_spaces:
                df[column] = df[column].str.replace(r"\s+", " ", regex=True)

            if lower:
                df[column] = df[column].str.lower()

        return df

    def _normalize_headers_on_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        seen: dict[str, int] = {}
        columns = []

        for index, column in enumerate(df.columns):
            name = self._normalize_header(column) or f"Column {index + 1}"
            if name in seen:
                seen[name] += 1
                name = f"{name} {seen[name]}"
            else:
                seen[name] = 1
            columns.append(name)

        df.columns = columns
        return df

    def _standardize_missing_on_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in df.columns:
            if self._is_object_like(df[column]):
                df[column] = df[column].map(
                    lambda value: pd.NA
                    if self._normalize_text_value(value).lower() in self.EMPTY_TEXT_VALUES
                    else value
                )
        return df

    def _normalize_multi_select_on_dataframe(
        self,
        df: pd.DataFrame,
        columns: list[str],
        separator: str = ",",
    ) -> pd.DataFrame:
        df = df.copy()
        for column in columns:
            df[column] = df[column].map(lambda value: self._normalize_multi_select_value(value, separator=separator))
        return df

    def _encode_columns_on_dataframe(
        self,
        df: pd.DataFrame,
        columns: list[str],
        method: str = "one_hot",
        keep_original: bool = False,
        max_unique_values: int = 50,
    ) -> pd.DataFrame:
        df = df.copy()
        self._validate_columns_exist(df, columns)

        if method not in {"one_hot", "label"}:
            raise ValueError(f"Unsupported encoding method: {method}")

        for column in columns:
            values = df[column].map(self._normalize_text_value).replace("", pd.NA)
            unique_count = int(values.nunique(dropna=True))

            if unique_count > max_unique_values:
                raise ValueError(
                    f"Column '{column}' has {unique_count} unique values. "
                    f"Choose a column with {max_unique_values} or fewer values for encoding."
                )

            if method == "one_hot":
                dummies = pd.get_dummies(values, prefix=column, prefix_sep="_", dummy_na=False)
                dummies = dummies.astype("Int64")
                df = pd.concat([df, dummies], axis=1)

            else:
                codes, _uniques = pd.factorize(values, sort=True)
                code_series = pd.Series(codes, index=df.index).replace(-1, pd.NA).astype("Int64")
                df[f"{column}_code"] = code_series

        if not keep_original:
            df = df.drop(columns=columns)

        return df

    def _normalize_header(self, value: Any) -> str:
        text = self._normalize_text_value(value)
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _normalize_text_value(self, value: Any) -> str:
        if pd.isna(value):
            return ""

        text = unicodedata.normalize("NFKC", str(value))
        text = text.replace("\u200f", "").replace("\u200e", "").replace("\u0640", "")
        text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u06D6-\u06ED]", "", text)
        text = text.translate(str.maketrans("\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9", "01234567890123456789"))
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _normalize_multi_select_value(self, value: Any, separator: str = ",") -> str | None:
        text = self._normalize_text_value(value)
        if not text:
            return None

        raw_parts = re.split(r"[,;|\u060C]+", text)
        parts = []
        seen = set()
        for part in raw_parts:
            item = re.sub(r"\s+", " ", part).strip()
            if item and item not in seen:
                parts.append(item)
                seen.add(item)
        return f"{separator} ".join(parts) if parts else None

    def _coerce_numeric_series(self, series: pd.Series) -> pd.Series:
        cleaned = (
            series.astype("string")
            .map(self._normalize_text_value)
            .str.replace(",", "", regex=False)
            .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
            .str.replace(r"[^\d.\-]", "", regex=True)
            .str.strip()
        )
        return pd.to_numeric(cleaned, errors="coerce")

    def _coerce_boolean_series(self, series: pd.Series) -> pd.Series:
        def convert(value: Any):
            text = self._normalize_text_value(value).lower()
            if text in self.TRUE_VALUES:
                return True
            if text in self.FALSE_VALUES:
                return False
            return pd.NA

        return series.map(convert)

    def _is_object_like(self, series: pd.Series) -> bool:
        dtype_name = str(series.dtype)
        return series.dtype == "object" or dtype_name == "str" or dtype_name.startswith("string")

    def _is_multi_select_series(self, series: pd.Series) -> bool:
        if not self._is_object_like(series):
            return False
        values = series.dropna().astype(str)
        if values.empty:
            return False
        separators = (",", ";", "|", "\u060C")
        contains_separator = values.map(
            lambda value: any(separator in value for separator in separators)
        )
        return bool(contains_separator.mean() >= 0.25)

    def _looks_numeric_column(self, column: str, series: pd.Series) -> bool:
        lowered = str(column).lower()
        if any(word in lowered for word in ["amount", "cost", "price", "revenue", "budget", "expense", "quantity", "score", "target", "actual", "total", "rate", "percent"]):
            return True
        return bool(series.dropna().astype(str).str.contains(r"\d").mean() >= 0.5)

    def _looks_date_column(self, column: str) -> bool:
        lowered = str(column).lower()
        return any(word in lowered for word in ["date", "day", "month", "year", "submitted", "created"])

    def _validate_columns_exist(self, df: pd.DataFrame, columns: list[str]) -> None:
        missing_columns = [
            column
            for column in columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")

    def _validate_numeric_column(
        self,
        df: pd.DataFrame,
        column: str,
        method: str
    ) -> None:
        if not pd.api.types.is_numeric_dtype(df[column]):
            converted = self._coerce_numeric_series(df[column])
            if converted.notna().sum() == 0:
                raise TypeError(
                    f"Method '{method}' requires numeric column, "
                    f"but '{column}' is not numeric"
                )
            df[column] = converted

    def _validate_dict(self, value: Any, name: str) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be a dictionary")

    def _safe_float(self, value: Any) -> float | None:
        if pd.isna(value):
            return None

        return float(value)

