import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services import bi_report_delivery_service, account_work_fence
from fastapi import HTTPException
import database


DELIVERY = "11111111-1111-4111-8111-111111111111"
REPORT = "22222222-2222-4222-8222-222222222222"
TOKEN = "33333333-3333-4333-8333-333333333333"


class Rpc:
    def __init__(self, value=None, error=None): self.value, self.error = value, error
    def execute(self):
        if self.error: raise self.error
        return SimpleNamespace(data=self.value)


class Client:
    def __init__(self, responses): self.responses, self.calls = responses, []
    def rpc(self, name, params):
        self.calls.append((name, params))
        value = self.responses[name]
        return Rpc(error=value if isinstance(value, Exception) else None,
                   value=None if isinstance(value, Exception) else value)


class FenceRegistrationClient:
    """Only schema discovery and exact account registration are permitted offline."""
    def __init__(self):
        self.allowed = True
        self.calls = []
    def table(self, name):
        assert name == "application_schema_state"
        return self
    def select(self, fields):
        assert fields == "schema_version"
        return self
    def eq(self, field, value):
        assert (field, value) == ("contract_key", "core")
        return self
    def limit(self, count):
        assert count == 1
        return self
    def execute(self):
        return SimpleNamespace(data=[{"schema_version": 167}])
    def rpc(self, name, params):
        assert name == "account_fence_registration167"
        assert params == {"p_tenant_id": 3, "p_user_id": 5}
        self.calls.append((name, dict(params)))
        return Rpc(value=self.allowed)


class ReportDeliveryServiceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.fence_root = Path(directory.name)
        self.registration = FenceRegistrationClient()
        # scoped_work currently uses the global client for registration, rather
        # than the job's injected client. Isolate that dependency, not the fence.
        for target, name, value in (
            (database, "service_supabase", self.registration),
            (account_work_fence, "get_data_upload_dir", lambda: self.fence_root),
        ):
            replacement = patch.object(target, name, value)
            replacement.start(); self.addCleanup(replacement.stop)
        spy = patch.object(account_work_fence, "account_lock", wraps=account_work_fence.account_lock)
        self.fence = spy.start(); self.addCleanup(spy.stop)

    def row(self):
        return {"tenant_id": 3, "owner_user_id": 5, "id": DELIVERY, "report_id": REPORT, "lease_token": TOKEN, "lease_fence": 2}

    def cleanup_row(self):
        return {**self.row(), "tenant_id": 3, "project_id": "44444444-4444-4444-8444-444444444444",
                "owner_user_id": 5}

    def test_offline_adapter_receives_only_bounded_verified_private_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("reports/tenant_3") / REPORT / f"{'a' * 64}.csv"
            path = root / relative
            path.parent.mkdir(parents=True)
            content = b"metric,value\nrows,3\n"
            path.write_bytes(content)
            report = {"id": REPORT, "artifact_storage_key": relative.as_posix(),
                      "artifact_filename": "report.csv", "artifact_content_type": "text/csv",
                      "artifact_size_bytes": len(content), "artifact_sha256": hashlib.sha256(content).hexdigest(),
                      "artifact_deleted_at": None}
            client = Client({
                "authorize_bi_report_delivery166": {"recipient_email": "Member@Example.com", "report": report},
                "finish_bi_report_delivery166": {"status": "sent", "last_error_code": None},
            })
            adapter = bi_report_delivery_service.OfflineTestEmailAdapter()
            with patch.object(bi_report_delivery_service, "get_private_charts_dir", return_value=root):
                result = bi_report_delivery_service.process_delivery(self.row(), adapter=adapter, client=client)
        self.assertEqual(result["status"], "sent")
        self.fence.assert_called_once_with(3, 5)
        self.assertEqual(self.registration.calls, [("account_fence_registration167", {"p_tenant_id": 3, "p_user_id": 5})])
        self.assertEqual(client.calls[0], ("authorize_bi_report_delivery166", {
            "p_delivery_id": DELIVERY, "p_lease_token": TOKEN, "p_lease_fence": 2}))
        self.assertEqual(client.calls[-1][1]["p_lease_token"], TOKEN)
        self.assertEqual(client.calls[-1][1]["p_lease_fence"], 2)
        with account_work_fence.account_lock(3, 5, exclusive=True):
            pass  # The real shared filesystem lock was released on completion.
        self.assertEqual(adapter.delivered[0]["recipient"], "member@example.com")
        self.assertEqual(adapter.delivered[0]["sha256"], hashlib.sha256(content).hexdigest())
        self.assertTrue(adapter.delivered[0]["provider_message_id"].startswith("offline-"))

    def test_revoked_access_is_rechecked_before_adapter_and_never_delivered(self):
        client = Client({
            "authorize_bi_report_delivery166": RuntimeError("report_delivery_access_revoked"),
            "finish_bi_report_delivery166": {"status": "revoked", "last_error_code": "recipient_access_revoked"},
        })
        adapter = bi_report_delivery_service.OfflineTestEmailAdapter()
        result = bi_report_delivery_service.process_delivery(self.row(), adapter=adapter, client=client)
        self.assertEqual(result["status"], "revoked")
        self.assertEqual(adapter.delivered, [])
        finish = client.calls[-1][1]
        self.assertEqual(finish["p_outcome"], "revoked")

    def test_invalid_email_is_terminal_and_not_handed_to_adapter(self):
        client = Client({
            "authorize_bi_report_delivery166": {"recipient_email": "bad\n@example.com", "report": {"id": REPORT}},
            "finish_bi_report_delivery166": {"status": "revoked", "last_error_code": "recipient_email_invalid"},
        })
        adapter = bi_report_delivery_service.OfflineTestEmailAdapter()
        result = bi_report_delivery_service.process_delivery(self.row(), adapter=adapter, client=client)
        self.assertEqual(result["status"], "revoked")
        self.assertFalse(adapter.delivered)

    def test_adapter_failure_is_retryable_and_deduplicated_by_persisted_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("reports/tenant_3") / REPORT / f"{'b' * 64}.csv"
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"safe")
            report = {"id": REPORT, "artifact_storage_key": relative.as_posix(), "artifact_filename": "report.csv",
                      "artifact_content_type": "text/csv", "artifact_size_bytes": 4,
                      "artifact_sha256": hashlib.sha256(b"safe").hexdigest(), "artifact_deleted_at": None}
            client = Client({
                "authorize_bi_report_delivery166": {"recipient_email": "member@example.com", "report": report},
                "finish_bi_report_delivery166": {"status": "retry_pending", "last_error_code": "offline_failure"},
            })
            adapter = bi_report_delivery_service.OfflineTestEmailAdapter(failure_code="offline_failure")
            with patch.object(bi_report_delivery_service, "get_private_charts_dir", return_value=root):
                result = bi_report_delivery_service.process_delivery(self.row(), adapter=adapter, client=client)
        self.assertEqual(result["status"], "retry_pending")
        self.assertEqual(client.calls[-1][1]["p_outcome"], "retry")

    def test_no_adapter_can_be_implicitly_enabled(self):
        with self.assertRaises(RuntimeError):
            bi_report_delivery_service.run_delivery_batch(worker_id="worker", adapter=None, client=object())

    def test_delivery_batch_claims_each_batch_once(self):
        adapter = bi_report_delivery_service.OfflineTestEmailAdapter()
        row = self.row()
        with patch.object(bi_report_delivery_service, "claim_deliveries", return_value=[row]) as claim, \
                patch.object(bi_report_delivery_service, "process_delivery", return_value={"status": "sent"}) as process:
            result = bi_report_delivery_service.run_delivery_batch(
                worker_id="worker", adapter=adapter, limit=4, lease_seconds=60, client="database"
            )
        claim.assert_called_once_with(
            worker_id="worker", limit=4, lease_seconds=60, client="database"
        )
        process.assert_called_once_with(row, adapter=adapter, client="database")
        self.assertEqual(result, {"claimed": 1, "results": [{"status": "sent"}]})

    def test_cleanup_removes_only_the_bounded_private_report_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("reports/tenant_3") / REPORT / "primary.csv"
            primary = root / relative
            export = primary.parent / "exports" / "report.pdf"
            export.parent.mkdir(parents=True)
            primary.write_bytes(b"primary")
            export.write_bytes(b"private export")
            report = {"artifact_storage_key": relative.as_posix(), "artifact_filename": "report.csv",
                      "artifact_content_type": "text/csv", "artifact_size_bytes": 7,
                      "artifact_sha256": hashlib.sha256(b"primary").hexdigest(), "artifact_deleted_at": None}
            with patch.object(bi_report_delivery_service, "get_private_charts_dir", return_value=root):
                size, digest = bi_report_delivery_service._cleanup_private_report(report)
            self.assertEqual(size, 7)
            self.assertEqual(digest, hashlib.sha256(b"primary").hexdigest())
            self.assertFalse(primary.parent.exists())
            self.assertTrue(root.exists())

    def test_cleanup_rechecks_owner_setting_before_deleting(self):
        client = Client({
            "authorize_bi_report_cleanup166": {"authorized": False, "status": "cancelled"},
        })
        with patch.object(bi_report_delivery_service, "_cleanup_private_report") as cleanup:
            result = bi_report_delivery_service.process_cleanup(self.cleanup_row(), client=client)
        cleanup.assert_not_called()
        self.assertEqual(result["status"], "cancelled")

    def test_registration_denial_prevents_authorization_and_delivery(self):
        self.registration.allowed = False
        client = Client({})
        adapter = bi_report_delivery_service.OfflineTestEmailAdapter()
        with self.assertRaises(HTTPException) as caught:
            bi_report_delivery_service.process_delivery(self.row(), adapter=adapter, client=client)
        self.assertEqual(caught.exception.status_code, 409)
        self.fence.assert_called_once_with(3, 5)
        self.assertFalse(client.calls)
        self.assertFalse(adapter.delivered)

    def test_real_account_hold_prevents_delivery_and_cleanup(self):
        with account_work_fence.account_lock(3, 5, exclusive=True) as marker:
            account_work_fence.publish_hold(marker, {"state": "offline-test-hold"})
        client = Client({})
        adapter = bi_report_delivery_service.OfflineTestEmailAdapter()
        with self.assertRaises(HTTPException):
            bi_report_delivery_service.process_delivery(self.row(), adapter=adapter, client=client)
        with self.assertRaises(HTTPException):
            bi_report_delivery_service.process_cleanup(self.cleanup_row(), client=client)
        self.assertFalse(client.calls)
        self.assertFalse(adapter.delivered)


if __name__ == "__main__":
    unittest.main()
