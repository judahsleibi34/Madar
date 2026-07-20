import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from services import storage_quota_service


class Response:
    def __init__(self, data): self.data = data


class Rpc:
    def __init__(self, result=None, error=None): self.result, self.error = result, error
    def execute(self):
        if self.error: raise RuntimeError(self.error)
        return Response(self.result)


class Client:
    def __init__(self, result=None, error=None): self.result, self.error, self.calls = result, error, []
    def rpc(self, name, params): self.calls.append((name, params)); return Rpc(self.result, self.error)


class StorageQuotaTests(unittest.TestCase):
    def test_migration_uses_atomic_locked_upserts_and_nonnegative_release(self):
        candidates = (
            Path.cwd() / "database/migrations/056_add_storage_quota_accounting.sql",
            Path(__file__).resolve().parents[2] / "database/migrations/056_add_storage_quota_accounting.sql",
        )
        migration_path = next(path for path in candidates if path.is_file())
        migration = migration_path.read_text().lower()
        self.assertIn("on conflict(tenant_id,scope_key) do update", migration)
        self.assertIn("used_bytes + tenant_row.reserved_bytes + p_bytes >", migration)
        self.assertIn("greatest(0,reserved_bytes-item.bytes)", migration)
        self.assertIn("release_storage_object", migration)
        self.assertIn("from public,anon,authenticated", migration)
    def test_disk_floor_allows_exact_floor_and_rejects_below(self):
        Usage = namedtuple("Usage", "total used free")
        with tempfile.TemporaryDirectory() as root, patch.dict("os.environ", {"STORAGE_DISK_FREE_FLOOR_BYTES": "100"}):
            with patch("services.storage_quota_service.shutil.disk_usage", return_value=Usage(1000, 800, 200)):
                self.assertEqual(storage_quota_service.ensure_disk_capacity(Path(root), incoming_bytes=100), 200)
                with self.assertRaisesRegex(storage_quota_service.StorageSafetyError, "storage_disk_floor_breached"):
                    storage_quota_service.ensure_disk_capacity(Path(root), incoming_bytes=101)

    def test_reservation_passes_tenant_and_optional_user_quota(self):
        client = Client(result="reservation-1")
        with tempfile.TemporaryDirectory() as root, patch.object(storage_quota_service, "ensure_disk_capacity", return_value=10**9):
            result = storage_quota_service.reserve_storage(
                tenant_id=7, user_id=9, category="dataset", size_bytes=10,
                storage_root=Path(root), client=client,
            )
        self.assertEqual(result, "reservation-1")
        self.assertEqual(client.calls[0][1]["p_tenant_id"], 7)
        self.assertGreater(client.calls[0][1]["p_user_quota"], 0)

    def test_quota_errors_have_stable_codes(self):
        with tempfile.TemporaryDirectory() as root, patch.object(storage_quota_service, "ensure_disk_capacity", return_value=10**9):
            for provider_error, code in (
                ("tenant_storage_quota_exceeded", "tenant_storage_quota_exceeded"),
                ("user_storage_quota_exceeded", "user_storage_quota_exceeded"),
            ):
                with self.subTest(code=code), self.assertRaises(storage_quota_service.StorageSafetyError) as raised:
                    storage_quota_service.reserve_storage(
                        tenant_id=1, user_id=2, category="dataset", size_bytes=5,
                        storage_root=Path(root), client=Client(error=provider_error),
                    )
                self.assertEqual(raised.exception.code, code)

    def test_finish_records_hash_without_raw_content(self):
        client = Client(result="object-1")
        result = storage_quota_service.finish_storage(
            reservation_id="reservation-1", succeeded=True,
            storage_key="tenant_1/user_2/file.csv", sha256_hex="a" * 64,
            client=client,
        )
        self.assertEqual(result, "object-1")
        self.assertEqual(client.calls[0][1]["p_sha256"], "a" * 64)


if __name__ == "__main__": unittest.main()
