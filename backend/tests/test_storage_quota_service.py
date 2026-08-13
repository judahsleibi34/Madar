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

class UsageQuery:
    def __init__(self, rows): self.rows, self.filters = rows, []
    def select(self, *_args): return self
    def eq(self, field, value): self.filters.append(("eq", field, value)); return self
    def is_(self, field, value): self.filters.append(("is", field, value)); return self
    def limit(self, *_args): return self
    def execute(self):
        rows = list(self.rows)
        for operation, field, value in self.filters:
            if operation == "eq": rows = [row for row in rows if row.get(field) == value]
            if operation == "is" and value == "null": rows = [row for row in rows if row.get(field) is None]
        return Response(rows[:1])


class UsageClient:
    def __init__(self, row): self.rows = [row]
    def table(self, _name): return UsageQuery(self.rows)


class StorageMutationQuery(UsageQuery):
    def __init__(self, rows):
        super().__init__(rows)
        self.update_payload = None
    def update(self, payload): self.update_payload = payload; return self
    def execute(self):
        rows = list(self.rows)
        for operation, field, value in self.filters:
            if operation == "eq": rows = [row for row in rows if row.get(field) == value]
            if operation == "is" and value == "null": rows = [row for row in rows if row.get(field) is None]
        if self.update_payload is not None:
            for row in rows: row.update(self.update_payload)
        return Response(rows)


class StorageMutationClient:
    def __init__(self, rows): self.rows = rows
    def table(self, _name): return StorageMutationQuery(self.rows)


class StorageQuotaTests(unittest.TestCase):
    def setUp(self):
        self.quota_patch = patch.object(
            storage_quota_service,
            "get_storage_quota_bytes",
            return_value=5 * 1024 * 1024 * 1024,
        )
        self.quota_patch.start()

    def tearDown(self):
        self.quota_patch.stop()

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
        self.assertEqual(client.calls[0][1]["p_tenant_quota"], 5 * 1024 * 1024 * 1024)
        self.assertEqual(client.calls[0][1]["p_user_quota"], 1024 * 1024 * 1024)

    def test_tenant_and_user_scopes_report_once_and_quota_sync_updates_only_tenant(self):
        gib = 1024 * 1024 * 1024
        rows = [
            {"tenant_id": 7, "scope_key": "tenant", "user_id": None, "used_bytes": 1234, "reserved_bytes": 0, "quota_bytes": 5 * gib},
            {"tenant_id": 7, "scope_key": "user:9", "user_id": 9, "used_bytes": 1234, "reserved_bytes": 0, "quota_bytes": gib},
        ]
        client = StorageMutationClient(rows)

        usage = storage_quota_service.get_tenant_storage_usage(7, client=client)
        self.assertEqual(usage["used_bytes"], 1234)

        self.quota_patch.stop()
        self.quota_patch = patch.object(
            storage_quota_service,
            "get_storage_quota_bytes",
            return_value=2 * gib,
        )
        self.quota_patch.start()
        storage_quota_service.sync_tenant_storage_quota(7, client=client)

        self.assertEqual(rows[0]["quota_bytes"], 2 * gib)
        self.assertEqual(rows[0]["used_bytes"], 1234)
        self.assertEqual(rows[0]["reserved_bytes"], 0)
        self.assertEqual(rows[1]["quota_bytes"], gib)
        self.assertEqual(rows[1]["used_bytes"], 1234)

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

    def test_downgrade_below_usage_reports_over_capacity_without_deleting_objects(self):
        gib = 1024 * 1024 * 1024
        self.quota_patch.stop()
        self.quota_patch = patch.object(
            storage_quota_service,
            "get_storage_quota_bytes",
            return_value=1 * gib,
        )
        self.quota_patch.start()
        usage = storage_quota_service.get_tenant_storage_usage(
            7,
            client=UsageClient({
                "tenant_id": 7,
                "scope_key": "tenant",
                "user_id": None,
                "used_bytes": 2 * gib,
                "reserved_bytes": 0,
                "quota_bytes": 5 * gib,
            }),
        )
        self.assertEqual(usage["used_bytes"], 2 * gib)
        self.assertEqual(usage["quota_bytes"], 1 * gib)
        self.assertTrue(usage["over_capacity"])

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
