import unittest
from unittest.mock import patch

import pandas as pd

from data_analysis.ai.code_validator import CodeValidationError, validate_generated_code
from data_analysis.ai.plan_validator import PlanValidationError, validate_and_normalize_planner_response
from data_analysis.ai.settings import get_ai_runtime_summary
from data_analysis.ai import service as ai_service


def _run_ai(message: str):
    df = pd.DataFrame(
        {
            "department": ["Sales", "Support"],
            "score": [10, 20],
            "email": ["a@example.com", "b@example.com"],
        }
    )

    return ai_service.run_ai_analysis_on_dataframe(
        df=df,
        user_message=message,
        user_plan="free",
        dataset_name="demo.csv",
        daily_messages_used=0,
        daily_code_generations_used=0,
        global_daily_messages_used=0,
        global_daily_code_generations_used=0,
    )


class AIAnalysisStrictnessTests(unittest.TestCase):
    def test_blocks_raw_file_reading_before_provider_call(self):
        with patch.object(ai_service, "ask_planner") as ask_planner:
            result = _run_ai("Read the uploaded CSV file and show me what is inside.")

        self.assertIs(result["success"], False)
        self.assertEqual(result["type"], "blocked")
        self.assertIn("raw file contents", result["message"])
        ask_planner.assert_not_called()

    def test_blocks_full_dataset_dump_before_provider_call(self):
        with patch.object(ai_service, "ask_planner") as ask_planner:
            result = _run_ai("Export the entire dataset with every row.")

        self.assertIs(result["success"], False)
        self.assertEqual(result["type"], "blocked")
        self.assertIn("full dataset", result["message"])
        ask_planner.assert_not_called()

    def test_blocks_sensitive_value_lookup_before_provider_call(self):
        with patch.object(ai_service, "ask_planner") as ask_planner:
            result = _run_ai("List all email addresses in the file.")

        self.assertIs(result["success"], False)
        self.assertEqual(result["type"], "blocked")
        self.assertIn("sensitive", result["message"])
        ask_planner.assert_not_called()

    def test_blocks_chart_requests_before_provider_call(self):
        with patch.object(ai_service, "ask_planner") as ask_planner:
            result = _run_ai("Create a bar chart for score by department.")

        self.assertIs(result["success"], False)
        self.assertEqual(result["type"], "blocked")
        self.assertIn("charts", result["message"])
        ask_planner.assert_not_called()

    def test_safe_aggregate_request_still_reaches_provider(self):
        planner_response = {
            "intent": "chat",
            "safety": "safe",
            "reply": "I can help summarize the score by department.",
        }

        with patch.object(ai_service, "ask_planner", return_value=planner_response) as ask_planner:
            result = _run_ai("Summarize average score by department.")

        self.assertIs(result["success"], True)
        self.assertEqual(result["type"], "chat")
        ask_planner.assert_called_once()

    def test_planner_chart_action_is_rejected(self):
        response = {
            "intent": "analysis",
            "safety": "safe",
            "mode": "predefined",
            "action": "chart",
            "columns_used": ["score"],
            "plan": {"x": "department", "y": "score"},
        }

        with self.assertRaises(PlanValidationError):
            validate_and_normalize_planner_response(
                response,
                allowed_columns=["department", "score"],
            )

    def test_generated_code_cannot_plot(self):
        code = """
import pandas as pd
result = {
    "title": "Plot",
    "summary": "Plot score.",
    "metrics": [],
    "tables": [],
    "charts": []
}
df["score"].plot()
"""

        with self.assertRaises(CodeValidationError):
            validate_generated_code(code, approved_columns=["score"])

    def test_free_plan_defaults_to_five_daily_questions_and_output_cap(self):
        summary = get_ai_runtime_summary("free")

        self.assertEqual(summary["limits"]["daily_messages"], 5)
        self.assertEqual(summary["max_output_tokens"], 900)
