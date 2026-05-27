import pandas as pd


class MealAnalysis:
    def __init__(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()

    def department_summary(
        self,
        department_column: str,
        numeric_columns: list[str]
    ) -> list[dict]:
        self._validate_columns_exist([department_column] + numeric_columns)
        self._validate_numeric_columns(numeric_columns)

        summary = self.df.groupby(department_column)[numeric_columns].agg(
            ["count", "sum", "mean", "median", "min", "max"]
        )

        summary.columns = ["_".join(col).strip() for col in summary.columns.values]

        return summary.reset_index().to_dict(orient="records")

    def top_meals(
        self,
        meal_column: str,
        value_column: str,
        rows: int = 10
    ) -> list[dict]:
        self._validate_columns_exist([meal_column, value_column])
        self._validate_numeric_columns([value_column])

        result = (
            self.df.groupby(meal_column)[value_column]
            .sum()
            .sort_values(ascending=False)
            .head(rows)
            .reset_index()
        )

        return result.to_dict(orient="records")

    def average_price_by_department(
        self,
        department_column: str,
        price_column: str
    ) -> list[dict]:
        self._validate_columns_exist([department_column, price_column])
        self._validate_numeric_columns([price_column])

        result = (
            self.df.groupby(department_column)[price_column]
            .mean()
            .round(2)
            .reset_index(name="average_price")
        )

        return result.to_dict(orient="records")

    def meal_counts(
        self,
        column: str
    ) -> list[dict]:
        self._validate_columns_exist([column])

        result = (
            self.df[column]
            .value_counts(dropna=False)
            .reset_index()
        )

        result.columns = [column, "count"]

        return result.to_dict(orient="records")

    def revenue_by_meal(
        self,
        meal_column: str,
        revenue_column: str
    ) -> list[dict]:
        self._validate_columns_exist([meal_column, revenue_column])
        self._validate_numeric_columns([revenue_column])

        result = (
            self.df.groupby(meal_column)[revenue_column]
            .sum()
            .sort_values(ascending=False)
            .reset_index(name="total_revenue")
        )

        return result.to_dict(orient="records")

    def quantity_by_department(
        self,
        department_column: str,
        quantity_column: str
    ) -> list[dict]:
        self._validate_columns_exist([department_column, quantity_column])
        self._validate_numeric_columns([quantity_column])

        result = (
            self.df.groupby(department_column)[quantity_column]
            .sum()
            .sort_values(ascending=False)
            .reset_index(name="total_quantity")
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

