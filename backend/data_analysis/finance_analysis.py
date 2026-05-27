import pandas as pd


class FinanceAnalysis:
    def __init__(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()

    def profit_loss_summary(
        self,
        revenue_column: str,
        cost_column: str
    ) -> dict:
        self._validate_columns_exist([revenue_column, cost_column])
        self._validate_numeric_columns([revenue_column, cost_column])

        revenue = self.df[revenue_column].sum()
        cost = self.df[cost_column].sum()
        profit = revenue - cost
        profit_margin = (profit / revenue) * 100 if revenue != 0 else None

        return {
            "total_revenue": float(revenue),
            "total_cost": float(cost),
            "total_profit": float(profit),
            "profit_margin_percentage": round(float(profit_margin), 2)
            if profit_margin is not None else None
        }

    def add_profit_column(
        self,
        revenue_column: str,
        cost_column: str,
        profit_column: str = "profit"
    ) -> pd.DataFrame:
        self._validate_columns_exist([revenue_column, cost_column])
        self._validate_numeric_columns([revenue_column, cost_column])

        self.df[profit_column] = self.df[revenue_column] - self.df[cost_column]

        return self.df

    def budget_vs_actual(
        self,
        budget_column: str,
        actual_column: str,
        group_column: str | None = None
    ) -> dict | list[dict]:
        self._validate_columns_exist([budget_column, actual_column])
        self._validate_numeric_columns([budget_column, actual_column])

        df = self.df.copy()
        df["variance"] = df[budget_column] - df[actual_column]
        df["burn_rate_percentage"] = df.apply(
            lambda row: (row[actual_column] / row[budget_column]) * 100
            if row[budget_column] != 0 else None,
            axis=1
        )

        if group_column:
            self._validate_columns_exist([group_column])

            grouped = (
                df.groupby(group_column)
                .agg({
                    budget_column: "sum",
                    actual_column: "sum",
                    "variance": "sum"
                })
                .reset_index()
            )

            grouped["burn_rate_percentage"] = grouped.apply(
                lambda row: (row[actual_column] / row[budget_column]) * 100
                if row[budget_column] != 0 else None,
                axis=1
            )

            return grouped.to_dict(orient="records")

        total_budget = df[budget_column].sum()
        total_actual = df[actual_column].sum()
        variance = total_budget - total_actual

        return {
            "total_budget": float(total_budget),
            "total_actual": float(total_actual),
            "variance": float(variance),
            "burn_rate_percentage": round(float((total_actual / total_budget) * 100), 2)
            if total_budget != 0 else None
        }

    def expense_summary(
        self,
        expense_column: str,
        category_column: str | None = None
    ) -> dict:
        self._validate_columns_exist([expense_column])
        self._validate_numeric_columns([expense_column])

        result = {
            "total_expense": float(self.df[expense_column].sum()),
            "average_expense": float(self.df[expense_column].mean()),
            "max_expense": float(self.df[expense_column].max()),
            "min_expense": float(self.df[expense_column].min())
        }

        if category_column:
            self._validate_columns_exist([category_column])
            result["expense_by_category"] = (
                self.df.groupby(category_column)[expense_column]
                .sum()
                .sort_values(ascending=False)
                .to_dict()
            )

        return result

    def revenue_by_group(
        self,
        revenue_column: str,
        group_column: str
    ) -> list[dict]:
        self._validate_columns_exist([revenue_column, group_column])
        self._validate_numeric_columns([revenue_column])

        result = (
            self.df.groupby(group_column)[revenue_column]
            .agg(["count", "sum", "mean", "median", "min", "max"])
            .reset_index()
        )

        return result.to_dict(orient="records")

    def monthly_summary(
        self,
        date_column: str,
        value_columns: list[str]
    ) -> list[dict]:
        self._validate_columns_exist([date_column] + value_columns)
        self._validate_numeric_columns(value_columns)

        df = self.df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        df = df.dropna(subset=[date_column])
        df["month"] = df[date_column].dt.to_period("M").astype(str)

        summary = df.groupby("month")[value_columns].sum().reset_index()

        return summary.to_dict(orient="records")

    def daily_summary(
        self,
        date_column: str,
        value_columns: list[str]
    ) -> list[dict]:
        self._validate_columns_exist([date_column] + value_columns)
        self._validate_numeric_columns(value_columns)

        df = self.df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        df = df.dropna(subset=[date_column])
        df["date"] = df[date_column].dt.date.astype(str)

        summary = df.groupby("date")[value_columns].sum().reset_index()

        return summary.to_dict(orient="records")

    def cash_flow_summary(
        self,
        inflow_column: str,
        outflow_column: str
    ) -> dict:
        self._validate_columns_exist([inflow_column, outflow_column])
        self._validate_numeric_columns([inflow_column, outflow_column])

        total_inflow = self.df[inflow_column].sum()
        total_outflow = self.df[outflow_column].sum()
        net_cash_flow = total_inflow - total_outflow

        return {
            "total_inflow": float(total_inflow),
            "total_outflow": float(total_outflow),
            "net_cash_flow": float(net_cash_flow)
        }

    def top_expenses(
        self,
        expense_column: str,
        rows: int = 10
    ) -> list[dict]:
        self._validate_columns_exist([expense_column])
        self._validate_numeric_columns([expense_column])

        result = (
            self.df.sort_values(by=expense_column, ascending=False)
            .head(rows)
        )

        return result.to_dict(orient="records")

    def financial_ratios(
        self,
        revenue_column: str,
        cost_column: str,
        expense_column: str | None = None
    ) -> dict:
        self._validate_columns_exist([revenue_column, cost_column])
        self._validate_numeric_columns([revenue_column, cost_column])

        revenue = self.df[revenue_column].sum()
        cost = self.df[cost_column].sum()
        gross_profit = revenue - cost

        result = {
            "gross_profit": float(gross_profit),
            "gross_margin_percentage": round(float((gross_profit / revenue) * 100), 2)
            if revenue != 0 else None,
            "cost_to_revenue_percentage": round(float((cost / revenue) * 100), 2)
            if revenue != 0 else None
        }

        if expense_column:
            self._validate_columns_exist([expense_column])
            self._validate_numeric_columns([expense_column])

            expense = self.df[expense_column].sum()
            net_profit = gross_profit - expense

            result["total_expense"] = float(expense)
            result["net_profit"] = float(net_profit)
            result["net_margin_percentage"] = round(
                float((net_profit / revenue) * 100),
                2
            ) if revenue != 0 else None

        return result

    def detect_negative_values(self, columns: list[str]) -> dict:
        self._validate_columns_exist(columns)
        self._validate_numeric_columns(columns)

        report = {}

        for column in columns:
            negative_rows = self.df[self.df[column] < 0]

            report[column] = {
                "negative_count": int(len(negative_rows)),
                "negative_percentage": round(
                    float((len(negative_rows) / len(self.df)) * 100),
                    2
                ) if len(self.df) > 0 else 0,
                "sample": negative_rows.head(10).to_dict(orient="records")
            }

        return report

    def transaction_summary(
        self,
        amount_column: str,
        transaction_id_column: str | None = None
    ) -> dict:
        self._validate_columns_exist([amount_column])
        self._validate_numeric_columns([amount_column])

        result = {
            "total_amount": float(self.df[amount_column].sum()),
            "average_amount": float(self.df[amount_column].mean()),
            "median_amount": float(self.df[amount_column].median()),
            "min_amount": float(self.df[amount_column].min()),
            "max_amount": float(self.df[amount_column].max()),
            "transaction_rows": int(len(self.df))
        }

        if transaction_id_column:
            self._validate_columns_exist([transaction_id_column])
            result["unique_transactions"] = int(self.df[transaction_id_column].nunique())

        return result

    def cost_per_beneficiary(
        self,
        cost_column: str,
        beneficiary_column: str,
        group_column: str | None = None
    ) -> dict | list[dict]:
        self._validate_columns_exist([cost_column, beneficiary_column])
        self._validate_numeric_columns([cost_column, beneficiary_column])

        if group_column:
            self._validate_columns_exist([group_column])

            grouped = (
                self.df.groupby(group_column)
                .agg({
                    cost_column: "sum",
                    beneficiary_column: "sum"
                })
                .reset_index()
            )

            grouped["cost_per_beneficiary"] = grouped.apply(
                lambda row: row[cost_column] / row[beneficiary_column]
                if row[beneficiary_column] != 0 else None,
                axis=1
            )

            return grouped.to_dict(orient="records")

        total_cost = self.df[cost_column].sum()
        total_beneficiaries = self.df[beneficiary_column].sum()

        return {
            "total_cost": float(total_cost),
            "total_beneficiaries": float(total_beneficiaries),
            "cost_per_beneficiary": float(total_cost / total_beneficiaries)
            if total_beneficiaries != 0 else None
        }

    def donor_funding_summary(
        self,
        donor_column: str,
        amount_column: str
    ) -> list[dict]:
        self._validate_columns_exist([donor_column, amount_column])
        self._validate_numeric_columns([amount_column])

        result = (
            self.df.groupby(donor_column)[amount_column]
            .agg(["count", "sum", "mean"])
            .sort_values(by="sum", ascending=False)
            .reset_index()
        )

        return result.to_dict(orient="records")

    def _validate_columns_exist(self, columns: list[str]) -> None:
        missing_columns = [
            column for column in columns
            if column not in self.df.columns
        ]

        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")

    def _validate_numeric_columns(self, columns: list[str]) -> None:
        for column in columns:
            if not pd.api.types.is_numeric_dtype(self.df[column]):
                raise TypeError(f"Column '{column}' must be numeric")

