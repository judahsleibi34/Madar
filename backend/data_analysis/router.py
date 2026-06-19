from typing import Any

import pandas as pd

from data_analysis.domains.finance_analysis import FinanceAnalysis
from data_analysis.domains.forms_analysis import FormsAnalysis
from data_analysis.domains.meal_analysis import MealAnalysis
from data_analysis.domains.ngo_meal_analysis import NgoMealAnalysis
from data_analysis.domains.hr_analysis import HrAnalysis
from data_analysis.assisted.assisted_analysis import AssistedAnalysis
from data_analysis.core.analysis_catalog import ANALYSIS_CATALOG


ANALYZER_CLASSES = {
    "finance": FinanceAnalysis,
    "meal": MealAnalysis,
    "ngo_meal": NgoMealAnalysis,
    "hr": HrAnalysis,
    "forms": FormsAnalysis,
    "assisted": AssistedAnalysis,
}

ALLOWED_ANALYSIS_METHODS = {
    domain: {
        str(report.get("id"))
        for report in config.get("reports", [])
        if report.get("id")
    }
    for domain, config in ANALYSIS_CATALOG.items()
}


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
                analyzer_class = ANALYZER_CLASSES.get(domain)

                if analyzer_class is None:
                    raise ValueError(f"Unsupported analysis domain: {domain}")

                analyzer = analyzer_class(self.df, language=self.language, symbols=self.symbols)
                analyzers[domain] = analyzer

            if method not in ALLOWED_ANALYSIS_METHODS.get(domain, set()):
                raise ValueError(f"Unsupported method '{method}' for domain '{domain}'")

            function = getattr(analyzer, method, None)
            if not callable(function):
                raise ValueError(f"Configured method '{method}' is unavailable for domain '{domain}'")

            results[key] = function(**params)

        return results

