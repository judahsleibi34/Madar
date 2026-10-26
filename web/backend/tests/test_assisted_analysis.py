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

    def test_distinct_count_excludes_missing_values_and_groups_deterministically(self):
        df = pd.DataFrame({
            "region": ["North", "North", "South", "South"],
            "customer": ["A", "A", "A", None],
        })

        result = AssistedAnalysis(df).custom_metric({
            "label": "Customers", "operation": "distinct_count",
            "value_column": "customer", "group_column": "region",
        })

        self.assertEqual(result["tables"][0]["rows"], [
            {"region": "North", "value": 1},
            {"region": "South", "value": 1},
        ])

    def test_date_aggregate_uses_utc_excludes_invalid_and_reports_partial_periods(self):
        df = pd.DataFrame({
            "observed_at": ["2026-01-15T23:30:00-02:00", "2026-01-31T10:00:00Z", "bad", None],
            "amount": [10, 20, 999, 999],
        })

        result = AssistedAnalysis(df).custom_metric({
            "label": "Monthly amount", "operation": "date_aggregate",
            "date_column": "observed_at", "value_column": "amount",
            "aggregation": "sum", "period": "month", "timezone": "UTC",
        })

        self.assertEqual(result["tables"][0]["rows"], [{"period": "2026-01", "value": 30}])
        mappings = result["metadata"]["mappings_used"]
        self.assertEqual(mappings["invalid_date_count"], 2)
        self.assertTrue(mappings["partial_periods"])
        self.assertEqual(len(result["warnings"]), 2)

    def test_date_aggregate_rejects_unverified_date_field(self):
        with self.assertRaisesRegex(ValueError, "no valid values|not a verified date"):
            AssistedAnalysis(pd.DataFrame({"date": ["x", "y"]})).custom_metric({
                "operation": "date_aggregate", "date_column": "date",
            })


if __name__ == "__main__":
    unittest.main()
