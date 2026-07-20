import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from data_analysis import services as data_services
from data_analysis.routes import data_routes


def fake_user_scope(user_id, request, response):
    if request.headers.get("x-test-unauthenticated") == "1":
        raise HTTPException(status_code=401, detail="Not authenticated")

    return SimpleNamespace(
        user_id=int(user_id),
        tenant_id=request.headers.get("x-test-tenant-id", "1"),
    )


class LargeDatasetProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.private_dir = self.root / "private_uploads"
        self.private_dir.mkdir()

        app = FastAPI()
        app.include_router(data_routes.router)
        self.client = TestClient(app)

        self.patches = [
            patch.dict("os.environ", {"DATA_UPLOAD_DIR": str(self.private_dir)}, clear=False),
            patch.object(data_routes, "require_active_tenant_user_id", side_effect=fake_user_scope),
            patch.object(data_routes, "enforce_data_workspace_rate_limit", return_value=None),
            patch.object(data_services, "ensure_disk_capacity", return_value=10**12),
            patch.object(data_services, "reserve_storage", return_value="reservation-1"),
            patch.object(data_services, "finish_storage", return_value="object-1"),
            patch.object(data_services, "MAX_DATASET_UPLOAD_BYTES", 1024 * 1024),
            patch.object(data_services, "LARGE_DATASET_THRESHOLD_BYTES", 40),
            patch.object(data_services, "MAX_FULL_DATAFRAME_BYTES", 40),
            patch.object(data_services, "CSV_CHUNK_SIZE_ROWS", 2),
            patch.object(data_services, "MAX_PREVIEW_ROWS", 2),
            patch.object(data_services, "MAX_EXCEL_UPLOAD_BYTES", 64),
        ]

        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def upload_csv(self, content: bytes, *, filename: str = "dataset.csv", user_id: int = 1):
        return self.client.post(
            f"/users/{user_id}/data/upload",
            files={"file": (filename, content, "text/csv")},
        )

    def test_large_csv_upload_is_saved_private_and_metadata_is_chunked(self):
        content = b"name,value,city\nA,1,Ramallah\nB,2,Nablus\nC,,Hebron\nA,1,Ramallah\n"
        response = self.upload_csv(content)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["processing_mode"], "large_dataset")
        self.assertEqual(body["rows"], 4)
        self.assertEqual(body["column_count"], 3)
        self.assertEqual(body["missing_values"]["value"], 1)
        self.assertEqual(body["duplicate_count"], 1)
        self.assertEqual(body["preview_rows"], 2)
        self.assertTrue(body["preview_is_partial"])
        self.assertEqual(body["dataset_id"], body["file_path"])
        self.assertFalse(Path(body["file_path"]).is_absolute())
        self.assertTrue((self.private_dir / "tenant_1" / "user_1" / body["dataset_id"]).is_file())

    def test_read_endpoint_returns_large_csv_preview_without_full_dataframe(self):
        upload_response = self.upload_csv(
            b"name,value\nAlpha,100\nBeta,200\nGamma,300\nDelta,400\nEpsilon,500\n",
        )
        self.assertEqual(upload_response.status_code, 200)

        read_response = self.client.post(
            "/users/1/data/read",
            json={"input_path": upload_response.json()["dataset_id"]},
        )

        self.assertEqual(read_response.status_code, 200)
        body = read_response.json()
        self.assertEqual(body["processing_mode"], "large_dataset")
        self.assertEqual(body["rows"], 5)
        self.assertEqual(body["preview_rows"], 2)
        self.assertTrue(body["preview_is_partial"])
        self.assertNotIn(str(self.private_dir), str(body))

    def test_large_dataset_full_dataframe_export_is_rejected(self):
        upload_response = self.upload_csv(
            b"name,value\nAlpha,100\nBeta,200\nGamma,300\nDelta,400\nEpsilon,500\n",
        )
        self.assertEqual(upload_response.status_code, 200)

        export_response = self.client.post(
            "/users/1/data/export",
            json={"input_path": upload_response.json()["dataset_id"]},
        )

        self.assertEqual(export_response.status_code, 413)
        self.assertIn("too large", export_response.json()["detail"])

    def test_small_csv_export_still_works(self):
        response = self.upload_csv(b"name,value\nA,1\n")
        self.assertEqual(response.status_code, 200)

        export_response = self.client.post(
            "/users/1/data/export",
            json={"input_path": response.json()["dataset_id"]},
        )

        self.assertEqual(export_response.status_code, 200)
        self.assertIn("name,value", export_response.json()["csv"])

    def test_malformed_csv_is_rejected_and_not_left_in_private_storage(self):
        response = self.upload_csv(b'name,value\n"unterminated,1\n')

        self.assertEqual(response.status_code, 400)
        stored_files = list((self.private_dir / "tenant_1" / "user_1").glob("*.csv"))
        self.assertEqual(stored_files, [])

    def test_excel_over_large_upload_limit_is_rejected_with_csv_guidance(self):
        response = self.client.post(
            "/users/1/data/upload",
            files={
                "file": (
                    "workbook.xlsx",
                    b"0" * 128,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("convert", response.json()["detail"].lower())
        self.assertIn("csv", response.json()["detail"].lower())

    def test_dataset_id_access_is_tenant_and_user_scoped(self):
        upload_response = self.upload_csv(b"name,value\nA,1\n", user_id=1)
        self.assertEqual(upload_response.status_code, 200)
        dataset_id = upload_response.json()["dataset_id"]

        wrong_user_response = self.client.post(
            "/users/2/data/read",
            json={"input_path": dataset_id},
        )
        wrong_tenant_response = self.client.post(
            "/users/1/data/read",
            json={"input_path": dataset_id},
            headers={"x-test-tenant-id": "2"},
        )
        traversal_response = self.client.post(
            "/users/1/data/read",
            json={"input_path": f"../user_2/{dataset_id}"},
        )
        unauthenticated_response = self.client.post(
            "/users/1/data/read",
            json={"input_path": dataset_id},
            headers={"x-test-unauthenticated": "1"},
        )

        self.assertEqual(wrong_user_response.status_code, 403)
        self.assertEqual(wrong_tenant_response.status_code, 403)
        self.assertEqual(traversal_response.status_code, 403)
        self.assertEqual(unauthenticated_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
