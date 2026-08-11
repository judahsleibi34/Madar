import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import builder_asset_storage


class Bucket:
    def __init__(self, signed_url):
        self.signed_url = signed_url
        self.calls = []

    def create_signed_url(self, storage_key, expires_in):
        self.calls.append((storage_key, expires_in))
        return {"signedURL": self.signed_url}


class BuilderAssetStorageTests(unittest.TestCase):
    def setUp(self):
        self.previous_ready = builder_asset_storage._bucket_ready
        builder_asset_storage._bucket_ready = True

    def tearDown(self):
        builder_asset_storage._bucket_ready = self.previous_ready

    def client(self, bucket):
        return SimpleNamespace(storage=SimpleNamespace(from_=lambda _name: bucket))

    def test_creates_short_lived_exact_object_signed_url(self):
        bucket = Bucket("https://project.supabase.co/storage/v1/object/sign/builder-assets/exact?token=test")
        with patch.dict(os.environ, {"SUPABASE_URL": "https://project.supabase.co"}):
            result = builder_asset_storage.create_builder_asset_signed_url(
                storage_key="tenant_7/builder_assets/asset.mp4",
                expires_in=60,
                client=self.client(bucket),
            )
        self.assertEqual(result, bucket.signed_url)
        self.assertEqual(bucket.calls, [("tenant_7/builder_assets/asset.mp4", 60)])

    def test_rejects_signed_url_on_another_origin(self):
        bucket = Bucket("https://evil.example/internal?token=test")
        with patch.dict(os.environ, {"SUPABASE_URL": "https://project.supabase.co"}), self.assertRaises(
            builder_asset_storage.BuilderAssetStorageError
        ):
            builder_asset_storage.create_builder_asset_signed_url(
                storage_key="tenant_7/builder_assets/asset.mp4",
                client=self.client(bucket),
            )


if __name__ == "__main__":
    unittest.main()
