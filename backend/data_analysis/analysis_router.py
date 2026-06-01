from typing import Any

import pandas as pd

from data_analysis.finance_analysis import FinanceAnalysis
from data_analysis.forms_analysis import FormsAnalysis
from data_analysis.meal_analysis import MealAnalysis
from data_analysis.ngo_meal_analysis import NgoMealAnalysis
from data_analysis.assisted_analysis import AssistedAnalysis


class AnalysisRouter:
    def __init__(self, df: pd.DataFrame, language: str = "en", symbols: dict[str, Any] | None = None) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()
        self.language = language
        self.symbols = symbols or {}

    def run(self, analysis_requests: list[dict[str, Any]]) -> dict:
        results = {}
        analyzers: dict[str, Any] = {}

        for index, request in enumerate(analysis_requests):
            domain = request.get("domain")
            method = request.get("method")
            params = request.get("params", {})
            key = request.get("key", f"{domain}_{method}_{index}")

            analyzer = analyzers.get(domain)
            if analyzer is None:
                if domain == "finance":
                    analyzer = FinanceAnalysis(self.df, language=self.language, symbols=self.symbols)

                elif domain == "meal":
                    analyzer = MealAnalysis(self.df, language=self.language, symbols=self.symbols)

                elif domain == "ngo_meal":
                    analyzer = NgoMealAnalysis(self.df, language=self.language, symbols=self.symbols)

                elif domain == "forms":
                    analyzer = FormsAnalysis(self.df, language=self.language, symbols=self.symbols)

                elif domain == "assisted":
                    analyzer = AssistedAnalysis(self.df, language=self.language, symbols=self.symbols)

                else:
                    raise ValueError(f"Unsupported analysis domain: {domain}")

                analyzers[domain] = analyzer

            if not hasattr(analyzer, method):
                raise ValueError(f"Unsupported method '{method}' for domain '{domain}'")

            function = getattr(analyzer, method)
            results[key] = function(**params)

        return results

