from __future__ import annotations

from typing import Any

import pandas as pd

from data_analysis.core.analysis_core import AnalysisBase


class AssistedAnalysis(AnalysisBase):
    domain = "assisted"

    def answer_question(self, question: str | None = None, metric: dict[str, Any] | None = None) -> dict:
        if metric:
            return self.custom_metric(metric)
        return self.offline_question(question or "")

    def offline_question(self, question: str) -> dict:
        report = self.report("offline_question", "Assisted analysis", {"question": question})
        q = question.lower().strip()
        numeric_cols = [column for column in self.df.columns if self._can_parse_numeric(column)]

        if not q:
            report.set_summary(
                "Ask a question or provide a custom metric definition to calculate a new indicator.",
                "ط§ظƒطھط¨ ط³ط¤ط§ظ„ط§ ط£ظˆ ظˆظپط± طھط¹ط±ظٹظپ ظ…ط¤ط´ط± ظ…ط®طµطµ ظ„ط­ط³ط§ط¨ ظ‚ظٹظ…ط© ط¬ط¯ظٹط¯ط©.",
            )
            report.add_table("Column suggestions", self._column_rows())
            return report.to_dict()

        if any(term in q for term in ["missing", "null", "empty", "blank"]):
            rows = []
            for column in self.df.columns:
                missing = int(self.df[column].isna().sum())
                rows.append({
                    "column": column,
                    "missing_count": missing,
                    "missing_percentage": self.pct(missing, len(self.df)) or 0,
                })
            rows = sorted(rows, key=lambda row: row["missing_count"], reverse=True)
            report.set_summary("Missing values were calculated for every column.", "طھظ… ط­ط³ط§ط¨ ط§ظ„ظ‚ظٹظ… ط§ظ„ظ…ظپظ‚ظˆط¯ط© ظ„ظƒظ„ ط¹ظ…ظˆط¯.")
            report.add_table("Missing values", rows)
            return report.to_dict()

        if any(term in q for term in ["correlation", "corr", "relationship"]):
            if len(numeric_cols) < 2:
                report.warnings.append("At least two numeric columns are required for correlation analysis.")
                report.set_summary("Correlation could not be calculated.", "ظ„ط§ ظٹظ…ظƒظ† ط­ط³ط§ط¨ ط§ظ„ط§ط±طھط¨ط§ط· ط¨ط¯ظˆظ† ط¹ظ…ظˆط¯ظٹظ† ط±ظ‚ظ…ظٹظٹظ† ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„.")
                return report.to_dict()
            numeric_df = pd.DataFrame({column: self.numeric(column) for column in numeric_cols})
            corr = numeric_df.corr().stack().reset_index()
            corr.columns = ["column_a", "column_b", "correlation"]
            corr = corr[corr["column_a"] < corr["column_b"]]
            corr["absolute_correlation"] = corr["correlation"].abs()
            corr = corr.sort_values("absolute_correlation", ascending=False).head(10)
            report.set_summary("Strongest numeric correlations were calculated.", "طھظ… ط­ط³ط§ط¨ ط£ظ‚ظˆظ‰ ط§ظ„ط§ط±طھط¨ط§ط·ط§طھ ط¨ظٹظ† ط§ظ„ط£ط¹ظ…ط¯ط© ط§ظ„ط±ظ‚ظ…ظٹط©.")
            report.add_table("Strongest correlations", corr.to_dict(orient="records"))
            return report.to_dict()

        if any(term in q for term in ["mean", "average", "avg"]):
            rows = self._numeric_summary_rows(numeric_cols, ["mean"])
            report.set_summary("Averages were calculated for numeric columns.", "طھظ… ط­ط³ط§ط¨ ط§ظ„ظ…طھظˆط³ط·ط§طھ ظ„ظ„ط£ط¹ظ…ط¯ط© ط§ظ„ط±ظ‚ظ…ظٹط©.")
            report.add_table("Averages", rows)
            return report.to_dict()

        if "median" in q:
            rows = self._numeric_summary_rows(numeric_cols, ["median"])
            report.set_summary("Medians were calculated for numeric columns.", "طھظ… ط­ط³ط§ط¨ ط§ظ„ظˆط³ظٹط· ظ„ظ„ط£ط¹ظ…ط¯ط© ط§ظ„ط±ظ‚ظ…ظٹط©.")
            report.add_table("Medians", rows)
            return report.to_dict()

        if any(term in q for term in ["sum", "total"]):
            rows = self._numeric_summary_rows(numeric_cols, ["sum"])
            report.set_summary("Totals were calculated for numeric columns.", "طھظ… ط­ط³ط§ط¨ ط§ظ„ظ…ط¬ط§ظ…ظٹط¹ ظ„ظ„ط£ط¹ظ…ط¯ط© ط§ظ„ط±ظ‚ظ…ظٹط©.")
            report.add_table("Totals", rows)
            return report.to_dict()

        if any(term in q for term in ["summary", "describe", "overview"]):
            report.set_summary("Dataset overview and column profiles are ready.", "ط§ظ„ظ†ط¸ط±ط© ط§ظ„ط¹ط§ظ…ط© ط¹ظ„ظ‰ ط§ظ„ط¨ظٹط§ظ†ط§طھ ظˆظ…ظ„ظپط§طھ ط§ظ„ط£ط¹ظ…ط¯ط© ط¬ط§ظ‡ط²ط©.")
            report.add_table("Column suggestions", self._column_rows())
            return report.to_dict()

        report.set_summary(
            "No fixed offline rule matched this question. The backend prepared dataset context and suggested columns for a future chatbot or assisted UI.",
            "ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ ظ‚ط§ط¹ط¯ط© ظ…ط­ظ„ظٹط© ط«ط§ط¨طھط© ظ„ظ‡ط°ط§ ط§ظ„ط³ط¤ط§ظ„. ط¬ظ‡ط²طھ ط§ظ„ظˆط§ط¬ظ‡ط© ط§ظ„ط®ظ„ظپظٹط© ط³ظٹط§ظ‚ ط§ظ„ط¨ظٹط§ظ†ط§طھ ظˆط§ظ‚طھط±ط§ط­ط§طھ ط§ظ„ط£ط¹ظ…ط¯ط© ظ„ظ„ط§ط³طھط®ط¯ط§ظ… ظ„ط§ط­ظ‚ط§.",
        )
        report.add_table("Column suggestions", self._column_rows())
        report.add_table("Prompt-ready context", [{
            "question": question,
            "rows": int(len(self.df)),
            "columns": list(self.df.columns),
            "numeric_columns": numeric_cols,
        }])
        return report.to_dict()

    def custom_metric(self, metric: dict[str, Any]) -> dict:
        operation = str(metric.get("operation", "")).lower().strip()
        label = metric.get("label") or operation.replace("_", " ").title() or "Custom metric"
        group_column = metric.get("group_column")
        report = self.report("custom_metric", str(label), metric)

        if operation in {"sum", "mean", "average", "median", "min", "max", "count"}:
            value_column = metric.get("value_column")
            if operation == "count" and not value_column:
                rows = self._group_or_total_count(group_column)
            else:
                rows = self._aggregate(value_column, operation, group_column)
            report.set_summary(f"Custom metric '{label}' was calculated using {operation}.", f"طھظ… ط­ط³ط§ط¨ ط§ظ„ظ…ط¤ط´ط± ط§ظ„ظ…ط®طµطµ '{label}' ط¨ط§ط³طھط®ط¯ط§ظ… {operation}.")
            report.add_table(str(label), rows)
            if group_column:
                report.add_chart(str(label), "bar", rows, group_column, "value")
            elif rows:
                report.add_kpi(str(label), rows[0].get("value"))
            return report.to_dict()

        if operation == "distinct_count":
            value_column = metric.get("value_column")
            self.validate_columns([value_column, group_column])
            if not value_column:
                raise ValueError("value_column is required")
            if group_column:
                rows = (
                    self.df.groupby(group_column, dropna=False)[value_column]
                    .nunique(dropna=True).reset_index(name="value").to_dict(orient="records")
                )
            else:
                rows = [{"value": int(self.df[value_column].nunique(dropna=True))}]
            report.set_summary(
                f"Distinct non-missing values in '{value_column}' were counted.",
                f"تم حساب القيم المميزة غير المفقودة في '{value_column}'.",
            )
            report.add_table(str(label), rows)
            if group_column:
                report.add_chart(str(label), "bar", rows, group_column, "value")
            else:
                report.add_kpi(str(label), rows[0]["value"])
            return report.to_dict()

        if operation == "date_aggregate":
            rows, date_metadata = self._date_aggregate(metric)
            report.mappings.update(date_metadata)
            invalid_count = date_metadata["invalid_date_count"]
            if invalid_count:
                report.warnings.append(
                    f"{invalid_count} missing or invalid date values were excluded from date grouping."
                )
            if date_metadata["partial_periods"]:
                report.warnings.append(
                    "The first or last period may be partial for the selected dataset coverage."
                )
            report.set_summary(
                f"Values were grouped by {date_metadata['period']} using the verified date field '{date_metadata['date_column']}'.",
                f"تم تجميع القيم حسب {date_metadata['period']} باستخدام حقل التاريخ المتحقق منه '{date_metadata['date_column']}'.",
            )
            report.add_table(str(label), rows)
            report.add_chart(str(label), "line", rows, "period", "value")
            return report.to_dict()

        if operation in {"rate", "ratio", "percentage"}:
            numerator_column = metric.get("numerator_column")
            denominator_column = metric.get("denominator_column")
            rows = self._rate(numerator_column, denominator_column, group_column)
            report.set_summary(f"Custom metric '{label}' was calculated as numerator divided by denominator.", f"طھظ… ط­ط³ط§ط¨ ط§ظ„ظ…ط¤ط´ط± ط§ظ„ظ…ط®طµطµ '{label}' ط¨ظ‚ط³ظ…ط© ط§ظ„ط¨ط³ط· ط¹ظ„ظ‰ ط§ظ„ظ…ظ‚ط§ظ….")
            report.add_table(str(label), rows)
            if group_column:
                report.add_chart(str(label), "bar", rows, group_column, "value")
            elif rows:
                report.add_kpi(str(label), rows[0].get("value"), "%")
            return report.to_dict()

        if operation in {"difference", "variance", "gap"}:
            actual_column = metric.get("actual_column") or metric.get("left_column")
            target_column = metric.get("target_column") or metric.get("right_column")
            rows = self._difference(actual_column, target_column, group_column)
            report.set_summary(f"Custom metric '{label}' was calculated as actual minus target.", f"طھظ… ط­ط³ط§ط¨ ط§ظ„ظ…ط¤ط´ط± ط§ظ„ظ…ط®طµطµ '{label}' ظƒظپط±ظ‚ ط¨ظٹظ† ط§ظ„ظپط¹ظ„ظٹ ظˆط§ظ„ظ‡ط¯ظپ.")
            report.add_table(str(label), rows)
            if rows and not group_column:
                report.add_kpi(str(label), rows[0].get("value"))
            return report.to_dict()

        raise ValueError(f"Unsupported custom metric operation: {operation}")

    def _date_aggregate(self, metric: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        date_column = metric.get("date_column")
        value_column = metric.get("value_column")
        aggregation = str(metric.get("aggregation") or "count").lower().strip()
        period = str(metric.get("period") or "month").lower().strip()
        timezone = str(metric.get("timezone") or "UTC").strip()
        if period not in {"day", "week", "month"}:
            raise ValueError("Unsupported date aggregation period")
        if aggregation not in {"count", "sum", "mean", "min", "max"}:
            raise ValueError("Unsupported date aggregation")
        if timezone != "UTC":
            raise ValueError("Only UTC date aggregation is currently supported")
        self.validate_columns([date_column, value_column])
        if not date_column:
            raise ValueError("date_column is required")
        raw_dates = self.df[date_column]
        dates = pd.to_datetime(raw_dates, errors="coerce", utc=True, format="mixed")
        non_missing_count = int(raw_dates.notna().sum())
        invalid_count = int(dates.isna().sum())
        if non_missing_count == 0 or int(dates.notna().sum()) == 0:
            raise ValueError("The selected date column has no valid values")
        invalid_non_missing = int((raw_dates.notna() & dates.isna()).sum())
        if invalid_non_missing and invalid_non_missing == non_missing_count:
            raise ValueError("The selected date column is not a verified date field")
        if aggregation != "count" and not value_column:
            raise ValueError("value_column is required for this date aggregation")

        if period == "day":
            keys = dates.dt.strftime("%Y-%m-%d")
        else:
            naive_dates = dates.dt.tz_convert("UTC").dt.tz_localize(None)
            frequency = "W-SUN" if period == "week" else "M"
            keys = naive_dates.dt.to_period(frequency).astype("string")
        work = pd.DataFrame({"period": keys})
        if aggregation == "count":
            work["value"] = 1
            grouped = work.dropna(subset=["period"]).groupby("period", sort=True)["value"].sum()
        else:
            work["value"] = self.numeric(value_column)
            grouped = work.dropna(subset=["period"]).groupby("period", sort=True)["value"].agg(aggregation)
        rows = grouped.reset_index(name="value").to_dict(orient="records")
        if not rows:
            raise ValueError("No valid rows remain for date aggregation")

        valid_dates = dates.dropna()
        minimum = valid_dates.min()
        maximum = valid_dates.max()
        partial_periods = False
        if period == "month":
            partial_periods = minimum.day != 1 or maximum.day != maximum.days_in_month
        elif period == "week":
            partial_periods = minimum.weekday() != 0 or maximum.weekday() != 6
        return rows, {
            "date_column": str(date_column),
            "value_column": str(value_column) if value_column else None,
            "aggregation": aggregation,
            "period": period,
            "timezone": timezone,
            "invalid_date_count": invalid_count,
            "coverage_start": minimum.isoformat(),
            "coverage_end": maximum.isoformat(),
            "partial_periods": partial_periods,
        }

    def _aggregate(self, value_column: str, operation: str, group_column: str | None = None) -> list[dict[str, Any]]:
        if not value_column:
            raise ValueError("value_column is required")
        values = self.numeric(value_column)
        agg = "mean" if operation == "average" else operation
        if group_column:
            self.validate_columns([group_column])
            work = pd.DataFrame({group_column: self.df[group_column], value_column: values})
            result = work.groupby(group_column, dropna=False)[value_column].agg(agg).reset_index(name="value")
            return result.to_dict(orient="records")
        return [{"value": self._series_agg(values, agg)}]

    def _rate(self, numerator_column: str, denominator_column: str, group_column: str | None = None) -> list[dict[str, Any]]:
        if not numerator_column or not denominator_column:
            raise ValueError("numerator_column and denominator_column are required")
        numerator = self.numeric(numerator_column)
        denominator = self.numeric(denominator_column)
        if group_column:
            self.validate_columns([group_column])
            work = pd.DataFrame({group_column: self.df[group_column], "numerator": numerator, "denominator": denominator})
            result = work.groupby(group_column, dropna=False)[["numerator", "denominator"]].sum().reset_index()
            result["value"] = result.apply(lambda row: self.pct(row["numerator"], row["denominator"]), axis=1)
            return result.to_dict(orient="records")
        return [{"value": self.pct(float(numerator.sum()), float(denominator.sum()))}]

    def _difference(self, actual_column: str, target_column: str, group_column: str | None = None) -> list[dict[str, Any]]:
        if not actual_column or not target_column:
            raise ValueError("actual_column and target_column are required")
        actual = self.numeric(actual_column)
        target = self.numeric(target_column)
        if group_column:
            self.validate_columns([group_column])
            work = pd.DataFrame({group_column: self.df[group_column], "actual": actual, "target": target})
            result = work.groupby(group_column, dropna=False)[["actual", "target"]].sum().reset_index()
            result["value"] = result["actual"] - result["target"]
            return result.to_dict(orient="records")
        return [{"value": float(actual.sum() - target.sum())}]

    def _group_or_total_count(self, group_column: str | None = None) -> list[dict[str, Any]]:
        if group_column:
            self.validate_columns([group_column])
            result = self.df.groupby(group_column, dropna=False).size().reset_index(name="value")
            return result.to_dict(orient="records")
        return [{"value": int(len(self.df))}]

    def _series_agg(self, values: pd.Series, agg: str) -> float | int:
        if agg == "sum":
            return float(values.sum())
        if agg == "mean":
            return float(values.mean())
        if agg == "median":
            return float(values.median())
        if agg == "min":
            return float(values.min())
        if agg == "max":
            return float(values.max())
        if agg == "count":
            return int(values.count())
        raise ValueError(f"Unsupported aggregation: {agg}")

    def _numeric_summary_rows(self, numeric_cols: list[str], aggregations: list[str]) -> list[dict[str, Any]]:
        rows = []
        for column in numeric_cols:
            values = self.numeric(column)
            row = {"column": column}
            for agg in aggregations:
                row[agg] = self._series_agg(values, agg)
            rows.append(row)
        return rows

    def _column_rows(self) -> list[dict[str, Any]]:
        return [{"column": column, **profile} for column, profile in self.column_profile().items()]

    def _can_parse_numeric(self, column: str) -> bool:
        try:
            self.numeric(column)
            return True
        except Exception:
            return False
