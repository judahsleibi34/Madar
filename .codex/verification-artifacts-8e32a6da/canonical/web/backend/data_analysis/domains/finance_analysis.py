from __future__ import annotations

import pandas as pd

from data_analysis.core.analysis_core import AnalysisBase


class FinanceAnalysis(AnalysisBase):
    domain = "finance"

    def profit_loss_summary(self, revenue_column: str, cost_column: str) -> dict:
        report = self.report("profit_loss_summary", "Profit and loss summary", locals())
        revenue = float(self.numeric(revenue_column).sum())
        cost = float(self.numeric(cost_column).sum())
        profit = revenue - cost
        margin = self.pct(profit, revenue, "Profit margin could not be calculated because total revenue is zero.", report)

        report.add_kpi("Total revenue", revenue)
        report.add_kpi("Total cost", cost)
        report.add_kpi("Total profit", profit)
        report.add_kpi("Profit margin", margin, "%")
        report.summary = f"Total revenue is {revenue:,.2f}, total cost is {cost:,.2f}, and profit is {profit:,.2f}."
        if margin is not None:
            report.insights.append(f"Profit margin is {margin:.2f}%.")
        report.add_table("Profit and loss", [{
            "total_revenue": revenue,
            "total_cost": cost,
            "total_profit": profit,
            "profit_margin_percentage": margin,
        }])
        return report.to_dict()

    def add_profit_column(self, revenue_column: str, cost_column: str, profit_column: str = "profit") -> dict:
        report = self.report("add_profit_column", "Rows with calculated profit", locals())
        work = self.df.copy()
        work[profit_column] = self.numeric(revenue_column) - self.numeric(cost_column)
        report.summary = f"Calculated '{profit_column}' as {revenue_column} minus {cost_column} for {len(work):,} rows."
        report.add_kpi("Total profit", float(work[profit_column].sum()))
        report.add_table("Calculated rows", work.head(100).to_dict(orient="records"))
        return report.to_dict()

    def budget_vs_actual(self, budget_column: str, actual_column: str, group_column: str | None = None) -> dict:
        report = self.report("budget_vs_actual", "Budget vs actual", locals())
        work = self.df.copy()
        work[budget_column] = self.numeric(budget_column)
        work[actual_column] = self.numeric(actual_column)

        if group_column:
            self.validate_columns([group_column])
            result = work.groupby(group_column, dropna=False)[[budget_column, actual_column]].sum().reset_index()
        else:
            result = pd.DataFrame([{budget_column: work[budget_column].sum(), actual_column: work[actual_column].sum()}])

        result["variance"] = result[budget_column] - result[actual_column]
        result["burn_rate_percentage"] = result.apply(
            lambda row: self.pct(row[actual_column], row[budget_column], "Burn rate could not be calculated for at least one zero budget row.", report),
            axis=1,
        )

        total_budget = float(result[budget_column].sum())
        total_actual = float(result[actual_column].sum())
        report.add_kpi("Total budget", total_budget)
        report.add_kpi("Total actual", total_actual)
        report.add_kpi("Variance", float(total_budget - total_actual))
        report.add_kpi("Burn rate", self.pct(total_actual, total_budget, "Overall burn rate could not be calculated because total budget is zero.", report), "%")
        report.summary = f"Actual spending is {total_actual:,.2f} against a budget of {total_budget:,.2f}."
        report.insights.append("Positive variance means budget remains; negative variance means overspend.")
        report.add_table("Budget vs actual", result.to_dict(orient="records"))
        if group_column:
            report.add_chart("Budget vs actual by group", "bar", result.to_dict(orient="records"), group_column, actual_column)
        return report.to_dict()

    def expense_summary(self, expense_column: str, category_column: str | None = None) -> dict:
        report = self.report("expense_summary", "Expense summary", locals())
        expense = self.numeric(expense_column)
        report.add_kpi("Total expense", float(expense.sum()))
        report.add_kpi("Average expense", float(expense.mean()))
        report.add_kpi("Max expense", float(expense.max()))
        report.add_kpi("Min expense", float(expense.min()))
        report.summary = f"Total expense is {expense.sum():,.2f} across {expense.notna().sum():,} valid rows."
        if category_column:
            result = self.group_numeric(category_column, [expense_column], ["count", "sum", "mean"])
            result = result.sort_values(f"{expense_column}_sum", ascending=False)
            top = result.iloc[0]
            report.insights.append(f"The largest expense category is {top[category_column]} with {top[f'{expense_column}_sum']:,.2f}.")
            report.add_table("Expense by category", result.to_dict(orient="records"))
            report.add_chart("Expense by category", "bar", result.to_dict(orient="records"), category_column, f"{expense_column}_sum")
        return report.to_dict()

    def revenue_by_group(self, revenue_column: str, group_column: str) -> dict:
        report = self.report("revenue_by_group", "Revenue by group", locals())
        result = self.group_numeric(group_column, [revenue_column])
        result = result.sort_values(f"{revenue_column}_sum", ascending=False)
        report.summary = f"Revenue is grouped by {group_column} across {len(result):,} groups."
        if not result.empty:
            report.insights.append(f"Top revenue group: {result.iloc[0][group_column]}.")
        report.add_table("Revenue by group", result.to_dict(orient="records"))
        report.add_chart("Revenue by group", "bar", result.to_dict(orient="records"), group_column, f"{revenue_column}_sum")
        return report.to_dict()

    def monthly_summary(self, date_column: str, value_columns: list[str]) -> dict:
        return self._time_summary("monthly_summary", "Monthly summary", date_column, value_columns, "monthly")

    def daily_summary(self, date_column: str, value_columns: list[str]) -> dict:
        return self._time_summary("daily_summary", "Daily summary", date_column, value_columns, "daily")

    def cash_flow_summary(self, inflow_column: str, outflow_column: str) -> dict:
        report = self.report("cash_flow_summary", "Cash flow summary", locals())
        inflow = float(self.numeric(inflow_column).sum())
        outflow = float(self.numeric(outflow_column).sum())
        net = inflow - outflow
        report.add_kpi("Total inflow", inflow)
        report.add_kpi("Total outflow", outflow)
        report.add_kpi("Net cash flow", net)
        report.summary = f"Net cash flow is {net:,.2f}, from {inflow:,.2f} inflow and {outflow:,.2f} outflow."
        report.insights.append("Positive net cash flow indicates more cash entered than left during the selected period." if net >= 0 else "Negative net cash flow indicates cash outflow exceeded inflow.")
        report.add_table("Cash flow", [{"total_inflow": inflow, "total_outflow": outflow, "net_cash_flow": net}])
        return report.to_dict()

    def top_expenses(self, expense_column: str, rows: int = 10) -> dict:
        report = self.report("top_expenses", "Top expenses", locals())
        work = self.df.copy()
        work[expense_column] = self.numeric(expense_column)
        result = work.sort_values(expense_column, ascending=False).head(rows)
        report.summary = f"Showing the top {len(result):,} expense rows by {expense_column}."
        if not result.empty:
            report.insights.append(f"Largest single expense is {float(result.iloc[0][expense_column]):,.2f}.")
        report.add_table("Top expenses", result.to_dict(orient="records"))
        return report.to_dict()

    def financial_ratios(self, revenue_column: str, cost_column: str, expense_column: str | None = None) -> dict:
        report = self.report("financial_ratios", "Financial ratios", locals())
        revenue = float(self.numeric(revenue_column).sum())
        cost = float(self.numeric(cost_column).sum())
        gross_profit = revenue - cost
        report.add_kpi("Gross profit", gross_profit)
        report.add_kpi("Gross margin", self.pct(gross_profit, revenue, "Gross margin could not be calculated because revenue is zero.", report), "%")
        report.add_kpi("Cost to revenue", self.pct(cost, revenue, "Cost-to-revenue could not be calculated because revenue is zero.", report), "%")
        row = {"gross_profit": gross_profit}
        if expense_column:
            expense = float(self.numeric(expense_column).sum())
            net_profit = gross_profit - expense
            row.update({"total_expense": expense, "net_profit": net_profit})
            report.add_kpi("Net profit", net_profit)
            report.add_kpi("Net margin", self.pct(net_profit, revenue, "Net margin could not be calculated because revenue is zero.", report), "%")
        report.summary = "Financial ratios were calculated from total revenue, cost, and optional expenses."
        report.add_table("Ratios", [row])
        return report.to_dict()

    def detect_negative_values(self, columns: list[str]) -> dict:
        report = self.report("detect_negative_values", "Negative value check", locals())
        rows = []
        for column in columns:
            values = self.numeric(column)
            negative_count = int((values < 0).sum())
            percentage = self.pct(negative_count, len(values)) or 0
            rows.append({"column": column, "negative_count": negative_count, "negative_percentage": percentage})
            if negative_count:
                report.warnings.append(f"{column} contains {negative_count} negative values.")
        report.summary = f"Checked {len(columns):,} numeric columns for negative values."
        report.add_table("Negative values", rows)
        return report.to_dict()

    def transaction_summary(self, amount_column: str, transaction_id_column: str | None = None) -> dict:
        report = self.report("transaction_summary", "Transaction summary", locals())
        amount = self.numeric(amount_column)
        report.add_kpi("Total amount", float(amount.sum()))
        report.add_kpi("Average amount", float(amount.mean()))
        report.add_kpi("Median amount", float(amount.median()))
        report.add_kpi("Rows", int(len(self.df)))
        if transaction_id_column:
            self.validate_columns([transaction_id_column])
            report.add_kpi("Unique transactions", int(self.df[transaction_id_column].nunique(dropna=True)))
        report.summary = f"Transaction amount totals {amount.sum():,.2f} over {len(self.df):,} rows."
        report.add_table("Transaction summary", [{
            "total_amount": float(amount.sum()),
            "average_amount": float(amount.mean()),
            "median_amount": float(amount.median()),
            "min_amount": float(amount.min()),
            "max_amount": float(amount.max()),
            "transaction_rows": int(len(self.df)),
        }])
        return report.to_dict()

    def cost_per_beneficiary(self, cost_column: str, beneficiary_column: str, group_column: str | None = None) -> dict:
        report = self.report("cost_per_beneficiary", "Cost per beneficiary", locals())
        work = self.df.copy()
        work[cost_column] = self.numeric(cost_column)
        work[beneficiary_column] = self.numeric(beneficiary_column)
        if group_column:
            self.validate_columns([group_column])
            result = work.groupby(group_column, dropna=False)[[cost_column, beneficiary_column]].sum().reset_index()
        else:
            result = pd.DataFrame([{cost_column: work[cost_column].sum(), beneficiary_column: work[beneficiary_column].sum()}])
        result["cost_per_beneficiary"] = result.apply(
            lambda row: self.safe_divide(row[cost_column], row[beneficiary_column], "Cost per beneficiary could not be calculated for at least one zero-beneficiary row.", report),
            axis=1,
        )
        report.summary = "Cost per beneficiary was calculated as total cost divided by total beneficiaries."
        report.add_table("Cost per beneficiary", result.to_dict(orient="records"))
        if group_column:
            report.add_chart("Cost per beneficiary by group", "bar", result.to_dict(orient="records"), group_column, "cost_per_beneficiary")
        return report.to_dict()

    def donor_funding_summary(self, donor_column: str, amount_column: str) -> dict:
        report = self.report("donor_funding_summary", "Donor funding summary", locals())
        result = self.group_numeric(donor_column, [amount_column], ["count", "sum", "mean"])
        result = result.sort_values(f"{amount_column}_sum", ascending=False)
        report.summary = f"Funding is summarized across {len(result):,} donors."
        if not result.empty:
            report.insights.append(f"Top donor by amount is {result.iloc[0][donor_column]}.")
        report.add_table("Donor funding", result.to_dict(orient="records"))
        report.add_chart("Donor funding", "bar", result.to_dict(orient="records"), donor_column, f"{amount_column}_sum")
        return report.to_dict()

    def _time_summary(self, report_id: str, title: str, date_column: str, value_columns: list[str], bucket: str) -> dict:
        report = self.report(report_id, title, locals())
        result, warnings = self.timeseries_sum(date_column, value_columns, bucket)
        report.warnings.extend(warnings)
        report.summary = f"{title} grouped {len(value_columns):,} value columns into {len(result):,} periods."
        report.add_table(title, result.to_dict(orient="records"))
        for column in value_columns:
            report.add_chart(f"{column} by period", "line", result[["period", column]].to_dict(orient="records"), "period", column)
        return report.to_dict()
