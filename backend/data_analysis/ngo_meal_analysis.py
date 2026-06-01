from __future__ import annotations

import pandas as pd

from data_analysis.analysis_core import AnalysisBase


class NgoMealAnalysis(AnalysisBase):
    domain = "ngo_meal"

    def indicator_progress(self, indicator_column: str, actual_column: str, target_column: str, group_column: str | None = None) -> dict:
        report = self.report("indicator_progress", "Indicator progress", locals())
        group_cols = [indicator_column] if not group_column else [group_column, indicator_column]
        result = self._sum_actual_target(group_cols, actual_column, target_column, "achievement_percentage", report)
        report.summary = f"Indicator achievement was calculated for {len(result):,} rows of grouped progress."
        report.insights.extend(self._achievement_insights(result, "achievement_percentage"))
        report.add_table("Indicator progress", result.to_dict(orient="records"))
        report.add_chart("Indicator achievement", "bar", result.to_dict(orient="records"), indicator_column, "achievement_percentage")
        return report.to_dict()

    def target_achievement(self, actual_column: str, target_column: str) -> dict:
        report = self.report("target_achievement", "Target achievement", locals())
        actual = float(self.numeric(actual_column).sum())
        target = float(self.numeric(target_column).sum())
        achievement = self.pct(actual, target, "Achievement could not be calculated because total target is zero.", report)
        gap = target - actual
        report.add_kpi("Actual", actual)
        report.add_kpi("Target", target)
        report.add_kpi("Gap", gap)
        report.add_kpi("Achievement", achievement, "%")
        report.summary = f"Actual progress is {actual:,.2f} against a target of {target:,.2f}."
        if achievement is not None:
            report.insights.append(f"Achievement is {achievement:.2f}%, leaving a gap of {gap:,.2f}.")
        report.add_table("Target achievement", [{
            "actual": actual,
            "target": target,
            "gap": gap,
            "achievement_percentage": achievement,
        }])
        return report.to_dict()

    def beneficiary_summary(self, beneficiary_column: str, group_columns: list[str] | None = None) -> dict:
        report = self.report("beneficiary_summary", "Beneficiary summary", locals())
        if group_columns:
            result = self.group_numeric(group_columns, [beneficiary_column], ["sum", "mean", "count"])
            result = result.rename(columns={f"{beneficiary_column}_sum": "total_beneficiaries"})
            report.add_table("Beneficiaries by group", result.to_dict(orient="records"))
            report.add_chart("Beneficiaries by group", "bar", result.to_dict(orient="records"), group_columns[0], "total_beneficiaries")
        else:
            values = self.numeric(beneficiary_column)
            result = pd.DataFrame([{
                "total_beneficiaries": float(values.sum()),
                "average_beneficiaries": float(values.mean()),
                "max_beneficiaries": float(values.max()),
                "min_beneficiaries": float(values.min()),
            }])
            report.add_table("Beneficiary summary", result.to_dict(orient="records"))
        report.add_kpi("Total beneficiaries", float(self.numeric(beneficiary_column).sum()))
        report.summary = "Beneficiary totals were calculated from the mapped beneficiary column."
        return report.to_dict()

    def disaggregation_summary(self, value_column: str, disaggregation_columns: list[str]) -> dict:
        report = self.report("disaggregation_summary", "Disaggregation summary", locals())
        result = self.group_numeric(disaggregation_columns, [value_column], ["sum", "count"])
        result = result.rename(columns={f"{value_column}_sum": "total"})
        report.summary = f"Values were disaggregated by {', '.join(disaggregation_columns)}."
        report.add_table("Disaggregation", result.to_dict(orient="records"))
        report.add_chart("Disaggregation", "bar", result.to_dict(orient="records"), disaggregation_columns[0], "total")
        return report.to_dict()

    def baseline_endline_change(self, group_column: str, baseline_column: str, endline_column: str) -> dict:
        report = self.report("baseline_endline_change", "Baseline to endline change", locals())
        work = self.df[[group_column]].copy()
        work[baseline_column] = self.numeric(baseline_column)
        work[endline_column] = self.numeric(endline_column)
        result = work.groupby(group_column, dropna=False)[[baseline_column, endline_column]].mean().reset_index()
        result["absolute_change"] = result[endline_column] - result[baseline_column]
        result["percentage_change"] = result.apply(
            lambda row: self.pct(row["absolute_change"], row[baseline_column], "Percentage change could not be calculated for at least one zero baseline row.", report),
            axis=1,
        )
        report.summary = f"Baseline and endline averages were compared across {len(result):,} groups."
        if not result.empty:
            improved = int((result["absolute_change"] > 0).sum())
            report.insights.append(f"{improved} groups improved from baseline to endline.")
        report.add_table("Baseline to endline change", result.to_dict(orient="records"))
        report.add_chart("Change by group", "bar", result.to_dict(orient="records"), group_column, "absolute_change")
        return report.to_dict()

    def activity_completion_rate(self, completed_column: str, planned_column: str, group_column: str | None = None) -> dict:
        return self._rate_report("activity_completion_rate", "Activity completion rate", completed_column, planned_column, "completion_rate_percentage", group_column)

    def survey_question_summary(self, question_column: str, response_column: str) -> dict:
        report = self.report("survey_question_summary", "Survey question summary", locals())
        self.validate_columns([question_column, response_column])
        result = self.df.groupby([question_column, response_column], dropna=False).size().reset_index(name="count")
        totals = result.groupby(question_column)["count"].transform("sum")
        result["percentage"] = round((result["count"] / totals) * 100, 2)
        report.summary = f"Survey responses were summarized for {result[question_column].nunique():,} questions."
        report.add_table("Survey question summary", result.to_dict(orient="records"))
        report.add_chart("Survey response distribution", "bar", result.to_dict(orient="records"), response_column, "count")
        return report.to_dict()

    def location_summary(self, location_column: str, value_columns: list[str]) -> dict:
        return self._group_values("location_summary", "Location summary", location_column, value_columns)

    def partner_summary(self, partner_column: str, value_columns: list[str]) -> dict:
        return self._group_values("partner_summary", "Partner summary", partner_column, value_columns)

    def vulnerability_summary(self, vulnerability_column: str, beneficiary_column: str) -> dict:
        report = self.report("vulnerability_summary", "Vulnerability summary", locals())
        result = self.group_numeric(vulnerability_column, [beneficiary_column], ["sum", "count"])
        result = result.rename(columns={f"{beneficiary_column}_sum": "total_beneficiaries"}).sort_values("total_beneficiaries", ascending=False)
        report.summary = f"Beneficiaries were summarized across {len(result):,} vulnerability groups."
        report.add_table("Vulnerability summary", result.to_dict(orient="records"))
        report.add_chart("Vulnerability summary", "bar", result.to_dict(orient="records"), vulnerability_column, "total_beneficiaries")
        return report.to_dict()

    def complaint_feedback_summary(self, channel_column: str, status_column: str) -> dict:
        report = self.report("complaint_feedback_summary", "Complaint and feedback summary", locals())
        self.validate_columns([channel_column, status_column])
        result = self.df.groupby([channel_column, status_column], dropna=False).size().reset_index(name="count")
        report.summary = f"Feedback records were summarized by {channel_column} and {status_column}."
        report.add_table("Complaint and feedback summary", result.to_dict(orient="records"))
        report.add_chart("Feedback status by channel", "bar", result.to_dict(orient="records"), channel_column, "count")
        return report.to_dict()

    def case_status_summary(self, status_column: str, group_column: str | None = None) -> dict:
        report = self.report("case_status_summary", "Case status summary", locals())
        if group_column:
            self.validate_columns([status_column, group_column])
            result = self.df.groupby([group_column, status_column], dropna=False).size().reset_index(name="count")
            x_col = group_column
        else:
            result = self.value_counts(status_column)
            x_col = status_column
        report.summary = f"Case statuses were summarized across {len(result):,} rows of results."
        report.add_table("Case status summary", result.to_dict(orient="records"))
        report.add_chart("Case status summary", "bar", result.to_dict(orient="records"), x_col, "count")
        return report.to_dict()

    def attendance_rate(self, attended_column: str, registered_column: str, group_column: str | None = None) -> dict:
        return self._rate_report("attendance_rate", "Attendance rate", attended_column, registered_column, "attendance_rate_percentage", group_column)

    def _sum_actual_target(self, group_cols: list[str], actual_column: str, target_column: str, rate_name: str, report) -> pd.DataFrame:
        work = self.df[group_cols].copy() if group_cols else pd.DataFrame(index=self.df.index)
        work[actual_column] = self.numeric(actual_column)
        work[target_column] = self.numeric(target_column)
        if group_cols:
            result = work.groupby(group_cols, dropna=False)[[actual_column, target_column]].sum().reset_index()
        else:
            result = pd.DataFrame([{
                actual_column: work[actual_column].sum(),
                target_column: work[target_column].sum(),
            }])
        result["gap"] = result[target_column] - result[actual_column]
        result[rate_name] = result.apply(lambda row: self.pct(row[actual_column], row[target_column], f"{rate_name} could not be calculated for at least one zero target/planned row.", report), axis=1)
        return result

    def _rate_report(self, report_id: str, title: str, numerator_column: str, denominator_column: str, rate_name: str, group_column: str | None = None) -> dict:
        report = self.report(report_id, title, locals())
        group_cols = [group_column] if group_column else []
        result = self._sum_actual_target(group_cols, numerator_column, denominator_column, rate_name, report) if group_cols else self._sum_actual_target([], numerator_column, denominator_column, rate_name, report)
        report.summary = f"{title} was calculated as {numerator_column} divided by {denominator_column}."
        report.insights.extend(self._achievement_insights(result, rate_name))
        report.add_table(title, result.to_dict(orient="records"))
        if group_column:
            report.add_chart(title, "bar", result.to_dict(orient="records"), group_column, rate_name)
        return report.to_dict()

    def _group_values(self, report_id: str, title: str, group_column: str, value_columns: list[str]) -> dict:
        report = self.report(report_id, title, locals())
        result = self.group_numeric(group_column, value_columns, ["sum", "mean", "count"])
        report.summary = f"{title} grouped {len(value_columns):,} value columns by {group_column}."
        report.add_table(title, result.to_dict(orient="records"))
        for column in value_columns:
            report.add_chart(f"{column} by {group_column}", "bar", result.to_dict(orient="records"), group_column, f"{column}_sum")
        return report.to_dict()

    def _achievement_insights(self, result: pd.DataFrame, rate_column: str) -> list[str]:
        if result.empty or rate_column not in result:
            return []
        valid = result[rate_column].dropna()
        if valid.empty:
            return []
        return [
            f"Average achievement is {valid.mean():.2f}%.",
            f"{int((valid >= 100).sum())} rows reached or exceeded 100%.",
        ]
