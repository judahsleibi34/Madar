import unittest

import pandas as pd

from data_analysis.assisted_analysis import AssistedAnalysis


class AssistedAnalysisTests(unittest.TestCase):
    def test_offline_question_answers_missing_values(self):
        df = pd.DataFrame({"name": ["A", None], "score": [10, 20]})

        result = AssistedAnalysis(df).offline_question("show missing values")

        self.assertEqual(result["report_id"], "offline_question")
        self.assertEqual(result["tables"][0]["title"], "Missing values")
        self.assertEqual(result["tables"][0]["rows"][0]["column"], "name")

    def test_custom_metric_rate_by_group(self):
        df = pd.DataFrame({
            "department": ["A", "A", "B"],
            "completed": [5, 5, 2],
            "planned": [10, 10, 4],
        })

        result = AssistedAnalysis(df).custom_metric({
            "label": "Completion",
            "operation": "rate",
            "numerator_column": "completed",
            "denominator_column": "planned",
            "group_column": "department",
        })

        rows = result["tables"][0]["rows"]

        self.assertEqual(result["report_id"], "custom_metric")
        self.assertEqual(rows[0]["value"], 50.0)
        self.assertEqual(rows[1]["value"], 50.0)

    def test_custom_metric_sum(self):
        df = pd.DataFrame({"amount": ["$10", "$20"]})

        result = AssistedAnalysis(df).custom_metric({
            "label": "Total amount",
            "operation": "sum",
            "value_column": "amount",
        })

        self.assertEqual(result["kpis"][0]["value"], 30.0)


if __name__ == "__main__":
    unittest.main()
