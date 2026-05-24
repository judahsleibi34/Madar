from typing import Any

import pandas as pd

from data_analysis.finance_analysis import FinanceAnalysis
from data_analysis.meal_analysis import MealAnalysis
from data_analysis.ngo_meal_analysis import NgoMealAnalysis


class AnalysisRouter:
    def __init__(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()

    def run(self, analysis_requests: list[dict[str, Any]]) -> dict:
        results = {}

        for index, request in enumerate(analysis_requests):
            domain = request.get("domain")
            method = request.get("method")
            params = request.get("params", {})
            key = request.get("key", f"{domain}_{method}_{index}")

            if domain == "finance":
                analyzer = FinanceAnalysis(self.df)

            elif domain == "meal":
                analyzer = MealAnalysis(self.df)

            elif domain == "ngo_meal":
                analyzer = NgoMealAnalysis(self.df)

            else:
                raise ValueError(f"Unsupported analysis domain: {domain}")

            if not hasattr(analyzer, method):
                raise ValueError(f"Unsupported method '{method}' for domain '{domain}'")

            function = getattr(analyzer, method)
            results[key] = function(**params)

        return results

