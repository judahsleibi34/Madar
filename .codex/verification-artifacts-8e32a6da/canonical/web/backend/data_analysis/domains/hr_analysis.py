from __future__ import annotations

import pandas as pd

from data_analysis.core.analysis_core import AnalysisBase


class HrAnalysis(AnalysisBase):
    domain = "hr"

    def workforce_summary(self, department_column: str | None = None) -> dict:
        report = self.report("workforce_summary", "Workforce summary", locals())
        headcount = int(len(self.df))
        report.add_kpi("Total employees", headcount)

        if department_column:
            self.validate_columns([department_column])
            result = self.value_counts(department_column)
            result = result.rename(columns={"count": "employee_count"})
            department_count = int(self.df[department_column].nunique(dropna=True))
            report.add_kpi("Departments", department_count)
            report.add_kpi(
                "Average employees per department",
                float(result["employee_count"].mean()) if not result.empty else None,
            )
            report.add_table("Headcount by department", result.to_dict(orient="records"))
            report.add_chart(
                "Headcount by department",
                "bar",
                result.to_dict(orient="records"),
                department_column,
                "employee_count",
            )
        else:
            report.add_table("Workforce summary", [{"total_employees": headcount}])

        report.summary = f"The dataset contains {headcount:,} employee records."
        return report.to_dict()

    def compensation_summary(
        self,
        salary_column: str,
        department_column: str | None = None,
    ) -> dict:
        report = self.report("compensation_summary", "Compensation summary", locals())
        salary = self.numeric(salary_column)
        report.add_kpi("Total payroll", float(salary.sum()))
        report.add_kpi("Average salary", float(salary.mean()))
        report.add_kpi("Median salary", float(salary.median()))
        report.add_kpi("Minimum salary", float(salary.min()))
        report.add_kpi("Maximum salary", float(salary.max()))

        if department_column:
            result = self.group_numeric(
                department_column,
                [salary_column],
                ["count", "sum", "mean", "median", "min", "max"],
            )
            report.add_table("Compensation by department", result.to_dict(orient="records"))
            report.add_chart(
                "Average salary by department",
                "bar",
                result.to_dict(orient="records"),
                department_column,
                f"{salary_column}_mean",
            )
        else:
            report.add_table(
                "Compensation statistics",
                [{
                    "count": int(salary.count()),
                    "total_payroll": float(salary.sum()),
                    "average_salary": float(salary.mean()),
                    "median_salary": float(salary.median()),
                    "minimum_salary": float(salary.min()),
                    "maximum_salary": float(salary.max()),
                }],
            )

        report.summary = f"Compensation statistics were calculated from {int(salary.count()):,} valid records."
        return report.to_dict()

    def attendance_summary(
        self,
        attended_days_column: str,
        working_days_column: str,
        department_column: str | None = None,
    ) -> dict:
        report = self.report("attendance_summary", "Attendance summary", locals())
        attended = self.numeric(attended_days_column)
        working = self.numeric(working_days_column)
        total_attended = float(attended.sum())
        total_working = float(working.sum())
        attendance_rate = self.pct(
            total_attended,
            total_working,
            "Attendance rate could not be calculated because total working days is zero.",
            report,
        )
        report.add_kpi("Attended days", total_attended)
        report.add_kpi("Working days", total_working)
        report.add_kpi("Attendance rate", attendance_rate, "%")
        report.add_kpi("Absent days", float(total_working - total_attended))

        work = pd.DataFrame({
            attended_days_column: attended,
            working_days_column: working,
        })
        if department_column:
            self.validate_columns([department_column])
            work[department_column] = self.df[department_column]
            result = work.groupby(department_column, dropna=False)[
                [attended_days_column, working_days_column]
            ].sum().reset_index()
            result["attendance_rate_percentage"] = result.apply(
                lambda row: self.pct(row[attended_days_column], row[working_days_column]),
                axis=1,
            )
            report.add_table("Attendance by department", result.to_dict(orient="records"))
            report.add_chart(
                "Attendance by department",
                "bar",
                result.to_dict(orient="records"),
                department_column,
                "attendance_rate_percentage",
            )
        else:
            report.add_table("Attendance totals", [{
                "attended_days": total_attended,
                "working_days": total_working,
                "absent_days": total_working - total_attended,
                "attendance_rate_percentage": attendance_rate,
            }])

        report.summary = "Attendance was calculated from mapped attended and working-day columns."
        return report.to_dict()
