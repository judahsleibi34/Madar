import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import webhook_routes
from services import webhook_ingestion_service


def make_client():
    app = FastAPI()
    app.include_router(webhook_routes.router)
    return TestClient(app)


class WebhookRouteTests(unittest.TestCase):
    def test_ingress_acknowledges_only_service_acceptance(self):
        with patch.object(webhook_ingestion_service, "receive", return_value={
            "event_id": "event-1", "disposition": "accepted",
        }):
            result = make_client().post("/data/webhooks/00000000-0000-4000-8000-000000000001",
                content=b"{}", headers={"content-type": "application/json"})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json(), {"accepted": True, "disposition": "accepted", "event_id": "event-1"})

    def test_duplicate_delivery_gets_idempotent_success(self):
        with patch.object(webhook_ingestion_service, "receive", return_value={
            "event_id": "event-1", "disposition": "duplicate",
        }):
            result = make_client().post("/data/webhooks/00000000-0000-4000-8000-000000000001",
                content=b"{}", headers={"content-type": "application/json"})
        self.assertEqual(result.status_code, 200)

    def test_ingress_rejects_media_type_and_oversized_declared_body(self):
        unsupported = make_client().post("/data/webhooks/00000000-0000-4000-8000-000000000001",
            content=b"{}", headers={"content-type": "text/plain"})
        self.assertEqual(unsupported.status_code, 415)
        oversized = make_client().post("/data/webhooks/00000000-0000-4000-8000-000000000001",
            content=b"{}", headers={"content-type": "application/json", "content-length": str(65 * 1024)})
        self.assertEqual(oversized.status_code, 413)

    def test_ingress_errors_do_not_expose_scope_or_secret(self):
        error = webhook_ingestion_service.WebhookIngestionError("webhook_not_found", status_code=404)
        with patch.object(webhook_ingestion_service, "receive", side_effect=error):
            result = make_client().post("/data/webhooks/00000000-0000-4000-8000-000000000001",
                content=b"{}", headers={"content-type": "application/json"})
        self.assertEqual(result.status_code, 404)
        body = result.text.lower()
        self.assertNotIn("tenant", body)
        self.assertNotIn("project", body)
        self.assertNotIn("secret", body)


if __name__ == "__main__":
    unittest.main()
