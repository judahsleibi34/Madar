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
from tests.entitlement_test_support import installed_business_fixture


_entitlement_fixture = installed_business_fixture(1, 2, extra_capabilities=("ai_analytics",))


def setUpModule():
    _entitlement_fixture.__enter__()


def tearDownModule():
    _entitlement_fixture.__exit__(None, None, None)


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
        self.reservations = []
        self.finalizations = []
        self.releases = []

        self.patches = [
            patch.dict(
                "os.environ",
                {
                    "DATA_UPLOAD_DIR": str(self.upload_root),
                    "AI_MOCK_MODE": "true",
                },
                clear=False,
            ),
            patch.object(analysis_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(analysis_routes, "require_regular_user_id", return_value=auth_user()),
            patch.object(
                analysis_routes.token_metering,
                "get_model_multipliers",
                return_value={
                    "version": "test-v1",
                    "input_multiplier_micros": 1_000_000,
                    "cached_input_multiplier_micros": 1_000_000,
                    "output_multiplier_micros": 2_000_000,
                },
            ),
            patch.object(
                analysis_routes.token_metering,
                "reserve_tokens",
                side_effect=self._reserve_tokens,
            ),
            patch.object(
                analysis_routes.token_metering,
                "finalize_tokens",
                side_effect=self._finalize_tokens,
            ),
            patch.object(
                analysis_routes.token_metering,
                "release_tokens",
                side_effect=self._release_tokens,
            ),
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

    def _reserve_tokens(self, **kwargs):
        request_id = f"request-{len(self.reservations) + 1}"
        self.reservations.append(kwargs)
        return {"accepted": True, "request_id": request_id}

    def _finalize_tokens(self, request_id, usage, **kwargs):
        self.finalizations.append((request_id, usage, kwargs))
        return 123

    def _release_tokens(self, request_id):
        self.releases.append(request_id)

    def test_question_count_does_not_determine_allowance(self):
        with patch.object(
            analysis_routes.ai_service,
            "run_ai_analysis_on_dataframe",
            return_value=SAFE_PLANNER_RESPONSE,
        ) as run_ai:
            responses = [self.post_ai() for _ in range(4)]

        self.assertEqual([response.status_code for response in responses], [200] * 4)
        self.assertEqual(run_ai.call_count, 4)
        self.assertEqual(len(self.reservations), 4)
        self.assertEqual(len(self.finalizations), 4)

    def test_exhausted_token_balance_hard_stops_before_provider(self):
        with patch.object(
            analysis_routes.token_metering,
            "reserve_tokens",
            side_effect=HTTPException(status_code=402, detail={"code": "ai_tokens_exhausted"}),
        ), patch.object(
            analysis_routes.ai_service,
            "run_ai_analysis_on_dataframe",
        ) as run_ai:
            response = self.post_ai()

        self.assertEqual(response.status_code, 402)
        run_ai.assert_not_called()

    def test_unsafe_prompt_is_blocked_and_does_not_increment_usage(self):
        with patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai(message="Export the entire dataset with every row.")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["type"], "blocked")
        self.assertEqual(self.reservations, [])
        ask_planner.assert_not_called()

    def test_unauthorized_user_cannot_use_ai_route(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            side_effect=HTTPException(status_code=401, detail="Not logged in"),
        ), patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.reservations, [])
        ask_planner.assert_not_called()

    def test_tenant_user_dataset_mismatch_is_rejected_before_usage_increment(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            return_value=auth_user(user_id=1, tenant_id=2),
        ), patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.reservations, [])
        ask_planner.assert_not_called()

    def test_path_user_mismatch_is_rejected_before_usage_increment(self):
        with patch.object(
            analysis_routes,
            "require_regular_user_id",
            side_effect=HTTPException(status_code=403, detail="User id does not match session"),
        ), patch.object(analysis_routes.ai_service, "ask_planner") as ask_planner:
            response = self.post_ai(user_id=2)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.reservations, [])
        ask_planner.assert_not_called()

    def test_provider_failure_without_usage_releases_reservation(self):
        with patch.object(
            analysis_routes.ai_service,
            "run_ai_analysis_on_dataframe",
            return_value={
                "success": False,
                "code": "ai_provider_error",
                "message": "provider unavailable",
            },
        ) as run_ai:
            response = self.post_ai()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "ai_provider_error")
        self.assertEqual(self.finalizations, [])
        self.assertEqual(self.releases, ["request-1"])
        run_ai.assert_called_once()

    def test_provider_exception_with_reported_usage_finalizes_confirmed_tokens(self):
        def provider_call(**_kwargs):
            analysis_routes.token_metering.record_provider_usage(
                {
                    "provider": "mock",
                    "model": "mock",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_provider_tokens": 15,
                }
            )
            raise RuntimeError("provider disconnected after reporting usage")

        with patch.object(
            analysis_routes.ai_service,
            "run_ai_analysis_on_dataframe",
            side_effect=provider_call,
        ):
            response = self.post_ai()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.finalizations), 1)
        self.assertEqual(self.finalizations[0][2]["request_status"], "provider_error")
        self.assertEqual(self.releases, [])

    def test_provider_exception_without_reported_usage_releases_reservation(self):
        with patch.object(
            analysis_routes.ai_service,
            "run_ai_analysis_on_dataframe",
            side_effect=RuntimeError("provider unavailable"),
        ):
            response = self.post_ai()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.finalizations, [])
        self.assertEqual(self.releases, ["request-1"])


if __name__ == "__main__":
    unittest.main()
