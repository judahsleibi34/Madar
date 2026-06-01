from __future__ import annotations

import pandas as pd

from data_analysis.analysis_core import AnalysisBase


class FormsAnalysis(AnalysisBase):
    domain = "forms"

    def response_overview(self, date_column: str | None = None, status_column: str | None = None) -> dict:
        report = self.report("response_overview", "Form response overview", locals())
        total_rows = int(len(self.df))
        total_cells = int(self.df.shape[0] * self.df.shape[1])
        missing_cells = int(self.df.isna().sum().sum())
        answered_cells = total_cells - missing_cells
        completion = self.pct(answered_cells, total_cells, "Completion rate could not be calculated because the dataset has no cells.", report)
        report.add_kpi("Responses", total_rows)
        report.add_kpi("Questions / columns", int(len(self.df.columns)))
        report.add_kpi("Completion rate", completion, "%")
        report.add_kpi("Missing answers", missing_cells)
        report.summary = f"The dataset contains {total_rows:,} responses and {len(self.df.columns):,} columns."
        report.insights.append(f"Overall answer completion is {completion:.2f}%." if completion is not None else "Completion could not be calculated.")

        missing = pd.DataFrame({
            "column": self.df.columns,
            "missing_count": [int(self.df[column].isna().sum()) for column in self.df.columns],
            "missing_percentage": [self.pct(int(self.df[column].isna().sum()), total_rows) or 0 for column in self.df.columns],
        }).sort_values("missing_count", ascending=False)
        report.add_table("Missing answers by column", missing.to_dict(orient="records"))

        if status_column:
            report.add_table("Responses by status", self.value_counts(status_column).to_dict(orient="records"))
        if date_column:
            dates = self.date(date_column)
            invalid = int(dates.isna().sum())
            if invalid:
                report.warnings.append(f"{invalid} rows had invalid dates and were excluded from the response trend.")
            trend = dates.dropna().dt.date.astype(str).value_counts().sort_index().reset_index()
            trend.columns = ["date", "count"]
            report.add_chart("Responses over time", "line", trend.to_dict(orient="records"), "date", "count")
        return report.to_dict()

    def question_distribution(self, question_column: str, rows: int = 20) -> dict:
        report = self.report("question_distribution", "Question distribution", locals())
        result = self.value_counts(question_column, rows)
        report.summary = f"Distribution calculated for {question_column}."
        if not result.empty:
            report.insights.append(f"Most common answer is {result.iloc[0][question_column]}.")
        report.add_table("Question distribution", result.to_dict(orient="records"))
        report.add_chart("Question distribution", "bar", result.to_dict(orient="records"), question_column, "count")
        return report.to_dict()

    def numeric_question_summary(self, numeric_columns: list[str]) -> dict:
        report = self.report("numeric_question_summary", "Numeric question summary", locals())
        rows = []
        for column in numeric_columns:
            values = self.numeric(column)
            rows.append({
                "column": column,
                "count": int(values.count()),
                "sum": float(values.sum()),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "min": float(values.min()),
                "max": float(values.max()),
                "std": float(values.std()) if values.count() > 1 else None,
            })
        report.summary = f"Numeric summaries were calculated for {len(numeric_columns):,} columns."
        report.add_table("Numeric question summary", rows)
        return report.to_dict()

    def rating_summary(self, rating_column: str, max_rating: int = 5, group_column: str | None = None) -> dict:
        report = self.report("rating_summary", "Rating summary", locals())
        values = self.numeric(rating_column)
        report.add_kpi("Average rating", float(values.mean()))
        report.add_kpi("Median rating", float(values.median()))
        report.add_kpi("Responses", int(values.count()))
        report.summary = f"Average rating is {values.mean():.2f} out of {max_rating}."
        distribution = self.value_counts(rating_column)
        report.add_table("Rating distribution", distribution.to_dict(orient="records"))
        report.add_chart("Rating distribution", "bar", distribution.to_dict(orient="records"), rating_column, "count")
        if group_column:
            grouped = self.group_numeric(group_column, [rating_column], ["count", "mean", "median"])
            report.add_table("Rating by group", grouped.to_dict(orient="records"))
        return report.to_dict()

    def multi_select_summary(self, column: str, separator: str = ",") -> dict:
        report = self.report("multi_select_summary", "Multi-select summary", locals())
        self.validate_columns([column])
        counts: dict[str, int] = {}
        for value in self.df[column].dropna():
            parts = [part.strip() for part in str(value).replace(";", separator).replace("|", separator).split(separator)]
            for part in parts:
                if part:
                    counts[part] = counts.get(part, 0) + 1
        result = pd.DataFrame([{"option": key, "count": value} for key, value in counts.items()]).sort_values("count", ascending=False)
        report.summary = f"Multi-select answers in {column} produced {len(result):,} unique options."
        report.add_table("Multi-select summary", result.to_dict(orient="records"))
        report.add_chart("Multi-select summary", "bar", result.to_dict(orient="records"), "option", "count")
        return report.to_dict()

    def column_suggestions(self) -> dict:
        report = self.report("column_suggestions", "Column suggestions", {})
        profiles = self.column_profile()
        rows = [{"column": column, **profile} for column, profile in profiles.items()]
        report.summary = "Columns were profiled to suggest suitable report mappings."
        report.add_table("Column suggestions", rows)
        return report.to_dict()
