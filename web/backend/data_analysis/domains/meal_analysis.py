from __future__ import annotations

from data_analysis.core.analysis_core import AnalysisBase


class MealAnalysis(AnalysisBase):
    domain = "meal"

    def department_summary(self, department_column: str, numeric_columns: list[str]) -> dict:
        report = self.report("department_summary", "Department summary", locals())
        result = self.group_numeric(department_column, numeric_columns)
        report.summary = f"Summarized {len(numeric_columns):,} numeric fields across {len(result):,} departments."
        if not result.empty and numeric_columns:
            sum_col = f"{numeric_columns[0]}_sum"
            top = result.sort_values(sum_col, ascending=False).iloc[0]
            report.insights.append(f"Top department by {numeric_columns[0]} is {top[department_column]}.")
        report.add_table("Department summary", result.to_dict(orient="records"))
        for column in numeric_columns:
            report.add_chart(f"{column} by department", "bar", result.to_dict(orient="records"), department_column, f"{column}_sum")
        return report.to_dict()

    def top_meals(self, meal_column: str, value_column: str, rows: int = 10) -> dict:
        report = self.report("top_meals", "Top items", locals())
        work = self.df[[meal_column]].copy()
        work[value_column] = self.numeric(value_column)
        result = (
            work.groupby(meal_column, dropna=False)[value_column]
            .sum()
            .sort_values(ascending=False)
            .head(rows)
            .reset_index(name="total_value")
        )
        total = float(result["total_value"].sum())
        result["share_percentage"] = result["total_value"].map(lambda value: round(float(value / total * 100), 2) if total else None)
        report.summary = f"Top {len(result):,} items are ranked by total {value_column}."
        if not result.empty:
            report.insights.append(f"Highest item is {result.iloc[0][meal_column]} with {result.iloc[0]['total_value']:,.2f}.")
        report.add_table("Top items", result.to_dict(orient="records"))
        report.add_chart("Top items", "bar", result.to_dict(orient="records"), meal_column, "total_value")
        return report.to_dict()

    def average_price_by_department(self, department_column: str, price_column: str) -> dict:
        report = self.report("average_price_by_department", "Average price by department", locals())
        result = self.group_numeric(department_column, [price_column], ["count", "mean", "median", "min", "max"])
        result = result.rename(columns={f"{price_column}_mean": "average_price"})
        report.summary = f"Average price is calculated across {len(result):,} departments."
        if not result.empty:
            top = result.sort_values("average_price", ascending=False).iloc[0]
            report.insights.append(f"Highest average price is in {top[department_column]}.")
        report.add_table("Average price by department", result.to_dict(orient="records"))
        report.add_chart("Average price by department", "bar", result.to_dict(orient="records"), department_column, "average_price")
        return report.to_dict()

    def meal_counts(self, column: str) -> dict:
        report = self.report("meal_counts", "Item counts", locals())
        result = self.value_counts(column)
        report.summary = f"Counted {len(result):,} unique values in {column}."
        if not result.empty:
            report.insights.append(f"Most common value is {result.iloc[0][column]} with {int(result.iloc[0]['count']):,} rows.")
        report.add_table("Item counts", result.to_dict(orient="records"))
        report.add_chart("Item counts", "bar", result.to_dict(orient="records"), column, "count")
        return report.to_dict()

    def revenue_by_meal(self, meal_column: str, revenue_column: str) -> dict:
        report = self.report("revenue_by_meal", "Revenue by item", locals())
        work = self.df[[meal_column]].copy()
        work[revenue_column] = self.numeric(revenue_column)
        result = (
            work.groupby(meal_column, dropna=False)[revenue_column]
            .sum()
            .sort_values(ascending=False)
            .reset_index(name="total_revenue")
        )
        report.add_kpi("Total revenue", float(result["total_revenue"].sum()))
        report.summary = f"Revenue was summarized for {len(result):,} items."
        if not result.empty:
            report.insights.append(f"Top revenue item is {result.iloc[0][meal_column]}.")
        report.add_table("Revenue by item", result.to_dict(orient="records"))
        report.add_chart("Revenue by item", "bar", result.to_dict(orient="records"), meal_column, "total_revenue")
        return report.to_dict()

    def quantity_by_department(self, department_column: str, quantity_column: str) -> dict:
        report = self.report("quantity_by_department", "Quantity by department", locals())
        result = self.group_numeric(department_column, [quantity_column], ["count", "sum", "mean"])
        result = result.rename(columns={f"{quantity_column}_sum": "total_quantity"})
        report.add_kpi("Total quantity", float(result["total_quantity"].sum()))
        report.summary = f"Quantity was summarized across {len(result):,} departments."
        if not result.empty:
            report.insights.append(f"Highest quantity department is {result.sort_values('total_quantity', ascending=False).iloc[0][department_column]}.")
        report.add_table("Quantity by department", result.to_dict(orient="records"))
        report.add_chart("Quantity by department", "bar", result.to_dict(orient="records"), department_column, "total_quantity")
        return report.to_dict()
