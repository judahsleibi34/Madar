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
