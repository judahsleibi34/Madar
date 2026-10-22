import asyncio
import hashlib
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import UploadFile

from data_analysis import services as data_services
from services import immutable_object_storage as objects
from services import project_dataset_service


RESERVATION = "11111111-1111-4111-8111-111111111111"


class FakeBucket:
    def __init__(self):
        self.items = {}

    def upload(self, *, path, file, file_options):
        if path in self.items:
            raise RuntimeError("already exists")
        self.items[path] = Path(file).read_bytes()

    def download(self, key):
        if key not in self.items:
            raise RuntimeError("not found")
        return self.items[key]

    def remove(self, keys):
        for key in keys:
            self.items.pop(key, None)


class FakeStorage:
    def __init__(self):
        self.bucket = FakeBucket()

    def get_bucket(self, name):
        if name != objects.IMMUTABLE_BUCKET:
            raise RuntimeError("not found")
        return {"public": False}

    def from_(self, name):
        if name != objects.IMMUTABLE_BUCKET:
            raise RuntimeError("not found")
        return self.bucket


class ImmutableObjectStorageTests(unittest.TestCase):
    def test_direct_transport_streams_verifies_retries_and_cleans_partial_files(self):
        class ByteStream(httpx.SyncByteStream):
            def __init__(self, content): self.content = content
            def __iter__(self):
                for offset in range(0, len(self.content), 64 * 1024):
                    yield self.content[offset:offset + 64 * 1024]

        payload = b"streamed-history\n" * 100_000
        descriptor = objects.ImmutableObject(
            backend="supabase_private", bucket=objects.IMMUTABLE_BUCKET,
            object_key=f"tenant_7/dataset/{RESERVATION}/{hashlib.sha256(payload).hexdigest()}.csv",
            size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
        )
        attempts = 0

        def handler(request):
            nonlocal attempts
            attempts += 1
            self.assertEqual(request.headers["accept-encoding"], "identity")
            if attempts == 1:
                raise httpx.ReadTimeout("synthetic timeout", request=request)
            return httpx.Response(200, headers={"Content-Length": str(len(payload))},
                                  stream=ByteStream(payload))

        client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
        store = objects.SupabaseImmutableObjectStore(
            client=SimpleNamespace(), use_streaming_transport=True,
            http_client_factory=client_factory,
        )
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "SUPABASE_URL": "https://storage.example.test",
            "SUPABASE_SERVICE_KEY": "service-secret",
        }, clear=False):
            target = Path(root) / "verified.csv"
            store.download_to_path(tenant_id=7, descriptor=descriptor, target_path=target)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(attempts, 2)

            truncated_factory = lambda: httpx.Client(transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, stream=ByteStream(payload[:-1]))
            ))
            truncated = objects.SupabaseImmutableObjectStore(
                client=SimpleNamespace(), use_streaming_transport=True,
                http_client_factory=truncated_factory,
            )
            bad_target = Path(root) / "truncated.csv"
            with self.assertRaises(objects.ImmutableObjectError) as corrupt:
                truncated.download_to_path(
                    tenant_id=7, descriptor=descriptor, target_path=bad_target,
                )
            self.assertEqual(corrupt.exception.category, objects.ObjectErrorCategory.CORRUPT)
            self.assertFalse(bad_target.exists())

            calls = 0
            def cancelled():
                nonlocal calls
                calls += 1
                return calls >= 3
            cancelled_target = Path(root) / "cancelled.csv"
            with self.assertRaises(objects.ImmutableObjectError) as stopped:
                store.download_to_path(
                    tenant_id=7, descriptor=descriptor,
                    target_path=cancelled_target, cancelled=cancelled,
                )
            self.assertEqual(stopped.exception.category, objects.ObjectErrorCategory.CANCELLED)
            self.assertFalse(cancelled_target.exists())

    def test_supabase_write_is_private_scoped_verified_and_idempotent(self):
        client = SimpleNamespace(storage=FakeStorage())
        store = objects.SupabaseImmutableObjectStore(client=client)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "chunk.csv"
            path.write_bytes(b"id,value\n1,alpha\n")
            first = store.write(
                tenant_id=7, reservation_id=RESERVATION,
                source_path=path, suffix=".csv",
            )
            second = store.write(
                tenant_id=7, reservation_id=RESERVATION,
                source_path=path, suffix=".csv",
            )
        self.assertEqual(first, second)
        self.assertEqual(store.read(tenant_id=7, descriptor=first), b"id,value\n1,alpha\n")
        self.assertTrue(first.object_key.startswith("tenant_7/dataset/"))
        with self.assertRaises(objects.ImmutableObjectError) as denied:
            store.read(tenant_id=8, descriptor=first)
        self.assertEqual(denied.exception.category, objects.ObjectErrorCategory.INVALID)

    def test_missing_corrupt_timeout_and_cancellation_are_explicit(self):
        client = SimpleNamespace(storage=FakeStorage())
        store = objects.SupabaseImmutableObjectStore(client=client)
        descriptor = objects.ImmutableObject(
            backend="supabase_private", bucket=objects.IMMUTABLE_BUCKET,
            object_key=f"tenant_1/dataset/{RESERVATION}/{'a' * 64}.csv",
            size_bytes=1, sha256="a" * 64,
        )
        with self.assertRaises(objects.ImmutableObjectError) as missing:
            store.read(tenant_id=1, descriptor=descriptor)
        self.assertEqual(missing.exception.category, objects.ObjectErrorCategory.MISSING)
        client.storage.bucket.items[descriptor.object_key] = b"x"
        with self.assertRaises(objects.ImmutableObjectError) as corrupt:
            store.read(tenant_id=1, descriptor=descriptor)
        self.assertEqual(corrupt.exception.category, objects.ObjectErrorCategory.CORRUPT)
        with self.assertRaises(objects.ImmutableObjectError) as cancelled:
            store.read(tenant_id=1, descriptor=descriptor, cancelled=lambda: True)
        self.assertEqual(cancelled.exception.category, objects.ObjectErrorCategory.CANCELLED)
        self.assertFalse(corrupt.exception.retryable)
        client.storage.bucket.download = lambda _key: (_ for _ in ()).throw(TimeoutError("slow"))
        with self.assertRaises(objects.ImmutableObjectError) as timed_out:
            store.read(tenant_id=1, descriptor=descriptor)
        self.assertEqual(timed_out.exception.category, objects.ObjectErrorCategory.TIMEOUT)
        self.assertTrue(timed_out.exception.retryable)

    def test_loopback_backend_is_impossible_outside_test(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            with self.assertRaises(objects.ImmutableObjectError):
                objects.LoopbackHttpImmutableObjectStore("http://127.0.0.1:9999")
        with patch.dict(os.environ, {"APP_ENV": "test"}, clear=False):
            with self.assertRaises(objects.ImmutableObjectError):
                objects.LoopbackHttpImmutableObjectStore("https://objects.example.test")

    def test_shared_upload_prepares_verifies_and_accounts_before_metadata(self):
        client = SimpleNamespace(storage=FakeStorage())
        store = objects.SupabaseImmutableObjectStore(client=client)
        calls = []
        with tempfile.TemporaryDirectory() as root, patch.dict(
            os.environ, {"DATA_UPLOAD_DIR": root, "STORAGE_DISK_FREE_FLOOR_BYTES": "1"}, clear=False,
        ), patch.object(
            data_services, "reserve_storage", return_value=RESERVATION,
        ), patch.object(
            data_services, "prepare_immutable_storage", side_effect=lambda **kw: calls.append(("prepare", kw)),
        ), patch.object(
            data_services, "verify_immutable_storage", side_effect=lambda **kw: calls.append(("verify", kw)),
        ), patch.object(
            data_services, "finish_immutable_storage", return_value="22222222-2222-4222-8222-222222222222",
        ) as finish:
            result = asyncio.run(data_services.process_upload(
                UploadFile(filename="history.csv", file=BytesIO(b"id,value\n1,alpha\n"),
                           headers={"content-type": "text/csv"}),
                tenant_id="7", user_id="9", shared_immutable=True,
                immutable_store=store,
                metadata_persister=lambda artifact: {
                    "persistent_dataset_id": "dataset-1", "hash_seen": artifact["sha256"],
                },
            ))
        self.assertEqual([item[0] for item in calls], ["prepare", "verify"])
        finish.assert_called_once()
        self.assertEqual(result["persistent_dataset_id"], "dataset-1")
        self.assertEqual(len(client.storage.bucket.items), 1)

    def test_shared_version_hydrates_a_verified_process_local_cache(self):
        descriptor = objects.ImmutableObject(
            backend="supabase_private", bucket=objects.IMMUTABLE_BUCKET,
            object_key=f"tenant_7/dataset/{RESERVATION}/{'c' * 64}.csv",
            size_bytes=4, sha256="c" * 64,
        )
        row = {
            "storage_backend": descriptor.backend, "storage_bucket": descriptor.bucket,
            "provider_object_key": descriptor.object_key,
            "verified_size_bytes": descriptor.size_bytes,
            "verified_sha256": descriptor.sha256,
            "storage_key": "tenant_7/user_9/cache.csv",
        }
        with tempfile.TemporaryDirectory() as root, patch.object(
            project_dataset_service, "get_data_upload_dir", return_value=Path(root),
        ), patch.object(
            project_dataset_service, "configured_store",
            return_value=SimpleNamespace(download_to_path=lambda **kwargs: (
                kwargs["target_path"].write_bytes(b"data") and kwargs["target_path"]
            )),
        ):
            project_dataset_service._hydrate_shared_object(
                row=row, tenant_id=7, user_id=9, client=SimpleNamespace(),
            )
            target = Path(root) / "tenant_7" / "user_9" / "cache.csv"
            self.assertEqual(target.read_bytes(), b"data")


if __name__ == "__main__":
    unittest.main()
