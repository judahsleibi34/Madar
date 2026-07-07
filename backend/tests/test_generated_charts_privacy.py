import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from data_analysis.routes import visualization_routes
from services.upload_config import validate_private_charts_not_publicly_mounted


def fake_user_scope(user_id, request, response):
    tenant_id = request.headers.get("x-test-tenant-id", "1")
    return SimpleNamespace(id=f"auth-{user_id}"), {
        "id": int(user_id),
        "tenant_id": tenant_id,
        "user_type": "user",
    }


class GeneratedChartsPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.public_dir = self.root / "public_uploads"
        self.data_dir = self.root / "private_uploads"
        self.charts_dir = self.root / "private_generated_charts"
        self.public_dir.mkdir()
        self.data_dir.mkdir()
        self.charts_dir.mkdir()

        self.dataset_dir = self.data_dir / "tenant_1" / "user_1"
        self.dataset_dir.mkdir(parents=True)
        self.dataset_path = self.dataset_dir / "scores.csv"
        self.dataset_path.write_text("department,score\nSales,10\nSupport,20\n", encoding="utf-8")

        app = FastAPI()
        app.include_router(visualization_routes.router)
        self.client = TestClient(app)

        self.patches = [
            patch.dict(
                "os.environ",
                {
                    "PUBLIC_UPLOADS_DIR": str(self.public_dir),
                    "DATA_UPLOAD_DIR": str(self.data_dir),
                    "PRIVATE_CHARTS_DIR": str(self.charts_dir),
                },
                clear=False,
            ),
            patch.object(visualization_routes, "get_storage_scope", side_effect=self.get_storage_scope),
            patch.object(visualization_routes, "enforce_data_workspace_rate_limit", return_value=None),
        ]

        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def get_storage_scope(self, request, response, user_id):
        if request.headers.get("x-test-unauthenticated") == "1":
            raise HTTPException(status_code=401, detail="Not authenticated")

        _, user_data = fake_user_scope(user_id, request, response)
        return str(user_data["tenant_id"]), str(user_data["id"])

    def create_chart(self, user_id=1, headers=None):
        return self.client.post(
            f"/users/{user_id}/visualization/create",
            json={
                "input_path": str(self.dataset_path),
                "cleaning_actions": [],
                "chart_config": {
                    "chart_type": "bar",
                    "x": "department",
                    "y": "score",
                    "title": "Scores",
                },
            },
            headers=headers or {},
        )

    def test_generated_charts_public_static_mount_is_not_available(self):
        response = self.client.get("/generated_charts/private-chart.png")

        self.assertEqual(response.status_code, 404)

    def test_visualization_creation_saves_chart_under_private_scoped_dir(self):
        response = self.create_chart()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        chart_id = body["chart_path"]
        chart_path = self.charts_dir / "tenant_1" / "user_1" / chart_id

        self.assertTrue(chart_path.is_file())
        self.assertEqual(body["chart_url"], f"/users/1/visualization/charts/{chart_id}")
        self.assertNotIn(str(self.charts_dir), str(body))
        self.assertNotIn("/generated_charts/", str(body))

    def test_authenticated_user_can_access_own_chart(self):
        create_response = self.create_chart()
        self.assertEqual(create_response.status_code, 200)
        chart_url = create_response.json()["chart_url"]

        chart_response = self.client.get(chart_url)

        self.assertEqual(chart_response.status_code, 200)
        self.assertEqual(chart_response.headers["content-type"], "image/png")
        self.assertTrue(chart_response.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_unauthenticated_user_cannot_access_private_chart(self):
        create_response = self.create_chart()
        self.assertEqual(create_response.status_code, 200)
        chart_url = create_response.json()["chart_url"]

        response = self.client.get(chart_url, headers={"x-test-unauthenticated": "1"})

        self.assertEqual(response.status_code, 401)

    def test_user_and_tenant_isolation_is_preserved_for_private_charts(self):
        create_response = self.create_chart(user_id=1)
        self.assertEqual(create_response.status_code, 200)
        chart_id = create_response.json()["chart_path"]

        other_user_response = self.client.get(f"/users/2/visualization/charts/{chart_id}")
        other_tenant_response = self.client.get(
            f"/users/1/visualization/charts/{chart_id}",
            headers={"x-test-tenant-id": "2"},
        )

        self.assertEqual(other_user_response.status_code, 403)
        self.assertEqual(other_tenant_response.status_code, 403)

    def test_path_traversal_attempt_is_rejected(self):
        response = self.client.get("/users/1/visualization/charts/%2e%2e%2fsecret.png")

        self.assertEqual(response.status_code, 403)

    def test_missing_chart_returns_404(self):
        response = self.client.get("/users/1/visualization/charts/missing.png")

        self.assertEqual(response.status_code, 404)

    def test_private_chart_dir_nested_under_public_dir_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "PRIVATE_CHARTS_DIR"):
            validate_private_charts_not_publicly_mounted(
                public_uploads_dir=self.public_dir,
                private_charts_dir=self.public_dir / "generated_charts",
            )


if __name__ == "__main__":
    unittest.main()
