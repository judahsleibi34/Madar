import unittest

import pandas as pd

from data_analysis.analysis_catalog import ANALYSIS_CATALOG
from data_analysis.analysis_i18n import localized_catalog
from data_analysis.analysis_router import AnalysisRouter
from data_analysis.finance_analysis import FinanceAnalysis
from data_analysis.forms_analysis import FormsAnalysis
from data_analysis.meal_analysis import MealAnalysis
from data_analysis.ngo_meal_analysis import NgoMealAnalysis


class AnalysisEngineTests(unittest.TestCase):
    def test_finance_profit_loss_report_shape_and_margin(self):
        df = pd.DataFrame({"revenue": [100, 200], "cost": [40, 100]})

        result = FinanceAnalysis(df).profit_loss_summary("revenue", "cost")

        self.assertEqual(result["report_id"], "profit_loss_summary")
        self.assertEqual(result["domain"], "finance")
        self.assertEqual(result["kpis"][2]["value"], 160)
        self.assertEqual(result["kpis"][3]["value"], 53.33)
        self.assertIn("summary", result)
        self.assertIn("metadata", result)

    def test_finance_zero_budget_returns_warning(self):
        df = pd.DataFrame({"budget": [0], "actual": [10]})

        result = FinanceAnalysis(df).budget_vs_actual("budget", "actual")

        self.assertIsNone(result["kpis"][3]["value"])
        self.assertTrue(result["warnings"])

    def test_meal_department_summary_coerces_numeric_strings(self):
        df = pd.DataFrame({"department": ["A", "A", "B"], "quantity": ["2", "3", "5"]})

        result = MealAnalysis(df).quantity_by_department("department", "quantity")
        rows = result["tables"][0]["rows"]

        self.assertEqual(result["domain"], "meal")
        self.assertEqual(sum(row["total_quantity"] for row in rows), 10)

    def test_ngo_target_achievement(self):
        df = pd.DataFrame({"actual": [40, 30], "target": [100, 100]})

        result = NgoMealAnalysis(df).target_achievement("actual", "target")

        self.assertEqual(result["kpis"][3]["value"], 35.0)
        self.assertEqual(result["tables"][0]["rows"][0]["gap"], 130)

    def test_forms_response_overview(self):
        df = pd.DataFrame({
            "Submitted at": ["2026-01-01", "2026-01-02"],
            "Status": ["Submitted", "Submitted"],
            "Rating": [5, None],
        })

        result = FormsAnalysis(df).response_overview("Submitted at", "Status")

        self.assertEqual(result["domain"], "forms")
        self.assertEqual(result["kpis"][0]["value"], 2)
        self.assertTrue(result["charts"])

    def test_router_supports_forms_domain(self):
        df = pd.DataFrame({"answer": ["Yes", "No", "Yes"]})

        result = AnalysisRouter(df).run([
            {
                "domain": "forms",
                "method": "question_distribution",
                "key": "distribution",
                "params": {"question_column": "answer"},
            }
        ])

        self.assertEqual(result["distribution"]["report_id"], "question_distribution")

    def test_catalog_contains_current_domains(self):
        for domain in ["finance", "meal", "ngo_meal", "forms"]:
            self.assertIn(domain, ANALYSIS_CATALOG)
            self.assertTrue(ANALYSIS_CATALOG[domain]["reports"])

    def test_arabic_catalog_localizes_labels(self):
        catalog = localized_catalog(ANALYSIS_CATALOG, "ar")

        self.assertEqual(catalog["finance"]["label"], "المالية")
        self.assertEqual(catalog["finance"]["reports"][0]["label"], "ملخص الربح والخسارة")

    def test_router_passes_arabic_language_and_symbols(self):
        df = pd.DataFrame({"revenue": [100], "cost": [40]})

        result = AnalysisRouter(
            df,
            language="ar",
            symbols={"percent": "٪", "decimal_separator": ",", "thousands_separator": "."},
        ).run([
            {
                "domain": "finance",
                "method": "profit_loss_summary",
                "key": "report",
                "params": {"revenue_column": "revenue", "cost_column": "cost"},
            }
        ])

        report = result["report"]
        self.assertEqual(report["title"], "ملخص الربح والخسارة")
        self.assertEqual(report["metadata"]["direction"], "rtl")
        self.assertEqual(report["kpis"][3]["unit"], "٪")
        self.assertIn("٪", report["kpis"][3]["display_value"])

    def test_missing_required_column_raises(self):
        with self.assertRaises(ValueError):
            FinanceAnalysis(pd.DataFrame({"revenue": [1]})).profit_loss_summary("revenue", "cost")

    def test_non_numeric_column_raises(self):
        with self.assertRaises(TypeError):
            FinanceAnalysis(pd.DataFrame({"revenue": ["bad"], "cost": [1]})).profit_loss_summary("revenue", "cost")

    def test_analysis_numeric_cache_returns_safe_copy(self):
        analyzer = FinanceAnalysis(pd.DataFrame({"amount": ["$10", "$20"]}))

        first = analyzer.numeric("amount")
        first.iloc[0] = 999
        second = analyzer.numeric("amount")

        self.assertEqual(float(second.sum()), 30.0)


if __name__ == "__main__":
    unittest.main()
