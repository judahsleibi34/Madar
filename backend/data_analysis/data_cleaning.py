import pandas as pd
from typing import Any, Literal

from data_analysis.data_reading import DataReadingNormal


class DataCleaning(DataReadingNormal):
    def preview(self, rows: int = 5) -> list[dict]:
        df = self.read()
        return df.head(rows).to_dict(orient="records")

    def data_inspection(self, max_unique_values: int = 20) -> dict:
        df = self.read()

        inspection = {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "unique_values": {}
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
        df = self.read()

        statistics = {
            "numeric_columns": {},
            "categorical_columns": {}
        }

        for column in df.columns:
            missing_values = int(df[column].isna().sum())

            if pd.api.types.is_numeric_dtype(df[column]):
                statistics["numeric_columns"][column] = {
                    "count": int(df[column].count()),
                    "mean": self._safe_float(df[column].mean()),
                    "median": self._safe_float(df[column].median()),
                    "min": self._safe_float(df[column].min()),
                    "max": self._safe_float(df[column].max()),
                    "std": self._safe_float(df[column].std()),
                    "sum": self._safe_float(df[column].sum()),
                    "missing_values": missing_values
                }

            else:
                unique_values = df[column].dropna().unique().tolist()
                most_common = df[column].mode(dropna=True).tolist()

                statistics["categorical_columns"][column] = {
                    "count": int(df[column].count()),
                    "unique_count": int(df[column].nunique(dropna=True)),
                    "unique_values_sample": unique_values[:max_unique_values],
                    "most_common": most_common[:max_unique_values],
                    "missing_values": missing_values
                }

        return statistics

    def missing_values_report(self) -> dict:
        df = self.read()
        report = {}

        for column in df.columns:
            missing_count = int(df[column].isna().sum())
            missing_percentage = (missing_count / len(df)) * 100 if len(df) > 0 else 0

            report[column] = {
                "missing_count": missing_count,
                "missing_percentage": round(float(missing_percentage), 2)
            }

        return report

    def quality_report(self) -> dict:
        df = self.read()

        duplicate_count = int(df.duplicated().sum())
        total_rows = int(len(df))
        total_cells = int(df.shape[0] * df.shape[1])
        missing_cells = int(df.isna().sum().sum())

        return {
            "rows": total_rows,
            "columns": int(len(df.columns)),
            "duplicate_rows": duplicate_count,
            "duplicate_percentage": round((duplicate_count / total_rows) * 100, 2) if total_rows else 0,
            "total_cells": total_cells,
            "missing_cells": missing_cells,
            "missing_percentage": round((missing_cells / total_cells) * 100, 2) if total_cells else 0,
            "column_types": self.column_types()
        }

    def column_types(self) -> dict:
        df = self.read()
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

            if action_type == "rename_column":
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

                self._validate_columns_exist(df, columns)

                df = self._clean_text_on_dataframe(
                    df=df,
                    columns=columns,
                    lower=lower,
                    strip=strip,
                    collapse_spaces=collapse_spaces
                )

            elif action_type == "drop_columns":
                columns = params["columns"]
                self._validate_columns_exist(df, columns)
                df = df.drop(columns=columns)

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

            if target_type == "datetime":
                df[column] = pd.to_datetime(df[column], errors="coerce")

            elif target_type == "numeric":
                df[column] = pd.to_numeric(df[column], errors="coerce")

            elif target_type == "string":
                df[column] = df[column].astype("string")

            elif target_type == "category":
                df[column] = df[column].astype("category")

            elif target_type == "boolean":
                df[column] = df[column].astype("boolean")

            else:
                raise ValueError(f"Unsupported target type: {target_type}")

        return df

    def _clean_text_on_dataframe(
        self,
        df: pd.DataFrame,
        columns: list[str],
        lower: bool = True,
        strip: bool = True,
        collapse_spaces: bool = True
    ) -> pd.DataFrame:
        df = df.copy()

        for column in columns:
            df[column] = df[column].astype("string")

            if strip:
                df[column] = df[column].str.strip()

            if collapse_spaces:
                df[column] = df[column].str.replace(r"\s+", " ", regex=True)

            if lower:
                df[column] = df[column].str.lower()

        return df

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
            raise TypeError(
                f"Method '{method}' requires numeric column, "
                f"but '{column}' is not numeric"
            )

    def _validate_dict(self, value: Any, name: str) -> None:
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be a dictionary")

    def _safe_float(self, value: Any) -> float | None:
        if pd.isna(value):
            return None

        return float(value)

