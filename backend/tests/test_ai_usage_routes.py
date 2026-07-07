import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from data_analysis.ai.planner import AIPlannerError
from data_analysis.routes import analysis_routes


SAFE_PLANNER_RESPONSE = {
    "intent": "chat",
    "safety": "safe",
    "reply": "The average score is 15.",
}


class FakeUsageStore:
    def __init__(self):
        self.rows = {}

    def key(self, user_id, usage_date):
        return (int(user_id), str(usage_date))

    def get_daily_ai_usage(self, *, user_id, usage_date=None):
        row = self.rows.get(self.key(user_id, usage_date), {"message_count": 0, "code_generation_count": 0})
        return dict(row)

    def get_global_daily_ai_usage(self, *, usage_date=None):
        rows = [
            row
            for (_user_id, row_date), row in self.rows.items()
            if row_date == str(usage_date)
        ]
        return {
            "message_count": sum(row["message_count"] for row in rows),
            "code_generation_count": sum(row["code_generation_count"] for row in rows),
        }

    def reserve_daily_ai_usage(
        self,
        *,
        user_id,
        tenant_id=None,
        usage_date=None,
        message_limit,
        code_generation_limit,
        message_delta=1,
        code_generation_delta=0,
    ):
        key = self.key(user_id, usage_date)
        row = self.rows.setdefault(key, {"message_count": 0, "code_generation_count": 0})
        next_messages = row["message_count"] + int(message_delta)
        next_code = row["code_generation_count"] + int(code_generation_delta)

        if next_messages > int(message_limit) or next_code > int(code_generation_limit):
            return {"accepted": False, **row}

        row["message_count"] = next_messages
        row["code_generation_count"] = next_code
        return {"accepted": True, **row}


class FakeDate:
    current = date(2026, 7, 7)

    @classmethod
    def today(cls):
        return cls.current


def build_client():
    app = FastAPI()
    app.include_router(analysis_routes.router)
    return TestClient(app)


def auth_user(user_id=1, tenant_id=1, *, payment_status="", plan="", user_type="user"):
    return SimpleNamespace(id=f"auth-{user_id}"), {
        "id": user_id,
        "tenant_id": tenant_id,
        "auth_id": f"auth-{user_id}",
        "user_type": user_type,
        "payment_status": payment_status,
        "plan": plan,
    }


class AIUsageRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = build_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = Path(self.temp_dir.name).resolve()
        self.dataset_dir = self.upload_root / "tenant_1" / "user_1"
        self.dataset_dir.mkdir(parents=True)
        self.dataset_path = self.dataset_dir / "scores.csv"
        self.dataset_path.write_text("department,score\nSales,10\nSupport,20\n", encoding="utf-8")
        self.usage = FakeUsageStore()
        FakeDate.current = date(2026, 7, 7)

        self.patches = [
            patch.dict(
                "os.environ",
                {
                    "DATA_UPLOAD_DIR": str(self.upload_root),
                    "AI_FREE_DAILY_MESSAGES": "2",
                    "AI_FREE_GLOBAL_DAILY_MESSAGES": "100",
                    "AI_PRO_DAILY_MESSAGES": "3",
                    "AI_PRO_GLOBAL_DAILY_MESSAGES": "",
                    "AI_MOCK_MODE": "true",
                },
                clear=False,
            ),
            patch.object(analysis_routes, "date", FakeDate),
            patch.object(analysis_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(analysis_routes, "require_regular_user_id", return_value=auth_user()),
            patch.object(analysis_routes.ai_usage, "get_daily_ai_usage", side_effect=self.usage.get_daily_ai_usage),
            patch.object(analysis_routes.ai_usage, "get_global_daily_ai_usage", side_effect=self.usage.get_global_daily_ai_usage),
            patch.object(analysis_routes.ai_usage, "reserve_daily_ai_usage", side_effect=self.usage.reserve_daily_ai_usage),
        ]

        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def post_ai(self, user_id=1, message="What is the average score?"):
        return self.client.post(
            f"/users/{user_id}/analysis/ai",
            json={
                "input_path": str(self.dataset_path),
                "user_message": message,
                "dataset_name": "scores.csv",
            },
        )

    def test_free_user_requests_through_daily_limit_are_allowed_then_blocked(self):
        with patch.object(analysis_routes.ai_service, "ask_planner", return_value=SAFE_PLANNER_RESPONSE) as ask_planner:
            first = self.post_ai()
            second = self.post_ai()
            third = self.post_ai()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=FakeDate.today())["message_count"], 2)
        self.assertEqual(ask_planner.call_count, 2)

    def test_limit_resets_on_new_day(self):
        with patch.object(analysis_routes.ai_service, "ask_planner", return_value=SAFE_PLANNER_RESPONSE):
            self.assertEqual(self.post_ai().status_code, 200)
            self.assertEqual(self.post_ai().status_code, 200)
            self.assertEqual(self.post_ai().status_code, 429)

            FakeDate.current = date(2026, 7, 8)
            next_day = self.post_ai()

        self.assertEqual(next_day.status_code, 200)
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=date(2026, 7, 8))["message_count"], 1)

    def test_unsafe_prompt_is_blocked_and_does_not_increment_usage(self):
        with patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai(message="Export the entire dataset with every row.")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["type"], "blocked")
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=FakeDate.today())["message_count"], 0)
        ask_planner.assert_not_called()

    def test_unauthorized_user_cannot_use_ai_route(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            side_effect=HTTPException(status_code=401, detail="Not logged in"),
        ), patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=FakeDate.today())["message_count"], 0)
        ask_planner.assert_not_called()

    def test_tenant_user_dataset_mismatch_is_rejected_before_usage_increment(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            return_value=auth_user(user_id=1, tenant_id=2),
        ), patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=FakeDate.today())["message_count"], 0)
        ask_planner.assert_not_called()

    def test_path_user_mismatch_is_rejected_before_usage_increment(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            side_effect=HTTPException(status_code=403, detail="User id does not match session"),
        ), patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai(user_id=2)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=FakeDate.today())["message_count"], 0)
        ask_planner.assert_not_called()

    def test_provider_failure_is_counted_after_provider_attempt(self):
        with patch.object(
            analysis_routes.ai_service,
            "ask_planner",
            side_effect=AIPlannerError("provider unavailable"),
        ) as ask_planner:
            response = self.post_ai()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "ai_provider_error")
        self.assertEqual(self.usage.get_daily_ai_usage(user_id=1, usage_date=FakeDate.today())["message_count"], 1)
        ask_planner.assert_called_once()

    def test_paid_active_plan_uses_higher_daily_limit(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            return_value=auth_user(payment_status="active", plan="business"),
        ), patch.object(analysis_routes.ai_service, "ask_planner", return_value=SAFE_PLANNER_RESPONSE) as ask_planner:
            first = self.post_ai()
            second = self.post_ai()
            third = self.post_ai()
            fourth = self.post_ai()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 200)
        self.assertEqual(fourth.status_code, 429)
        self.assertEqual(ask_planner.call_count, 3)


if __name__ == "__main__":
    unittest.main()
