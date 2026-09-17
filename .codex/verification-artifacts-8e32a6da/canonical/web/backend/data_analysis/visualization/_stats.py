from ._deps import pd


class StatsMixin:
    def _box_summary_stats(self, values: pd.Series) -> dict[str, float | int] | None:
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return None

        q1 = float(numeric_values.quantile(0.25))
        q3 = float(numeric_values.quantile(0.75))
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        outlier_count = int(
            ((numeric_values < lower_fence) | (numeric_values > upper_fence)).sum()
        )

        return {
            "count": int(numeric_values.count()),
            "mean": float(numeric_values.mean()),
            "q1": q1,
            "median": float(numeric_values.median()),
            "q3": q3,
            "iqr": iqr,
            "min": float(numeric_values.min()),
            "max": float(numeric_values.max()),
            "outliers": outlier_count,
        }

    def _numeric_summary_values(self, values: pd.Series) -> tuple[float, float] | None:
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return None

        return float(numeric_values.mean()), float(numeric_values.median())

    def _box_grouping_is_useful(
        self,
        data: pd.DataFrame,
        x_column: str,
        series_column: str | None = None,
    ) -> bool:
        if x_column not in data.columns:
            return False

        unique_count = int(data[x_column].dropna().nunique())
        if unique_count < 2 or unique_count > 18:
            return False

        group_columns = [x_column]
        if series_column and series_column in data.columns:
            group_columns.append(series_column)

        group_sizes = data.groupby(group_columns, dropna=False).size()
        if group_sizes.empty:
            return False

        return bool((group_sizes >= 2).mean() >= 0.6)

    def _box_series_scales_need_panels(
        self,
        data: pd.DataFrame,
        series_column: str,
        value_column: str,
    ) -> bool:
        ranges = []

        for _series_name, group in data.groupby(series_column, dropna=False):
            values = pd.to_numeric(group[value_column], errors="coerce").dropna()
            if values.empty:
                continue

            low = float(values.quantile(0.25))
            high = float(values.quantile(0.75))
            spread = max(abs(high - low), abs(float(values.median())), 1.0)
            ranges.append(spread)

        if len(ranges) < 2:
            return False

        return max(ranges) / max(min(ranges), 1.0) >= 25