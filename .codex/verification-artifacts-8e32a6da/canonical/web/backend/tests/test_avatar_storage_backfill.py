from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import backfill_avatar_storage as backfill


class Query:
    def __init__(self, rows):
        self.rows, self.filters = rows, []

    def select(self, *_args):
        return self

    @property
    def not_(self):
        return self

    def is_(self, key, _value):
        self.filters.append(("not_null", key, None))
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        rows = list(self.rows)
        for operation, key, value in self.filters:
            if operation == "not_null": rows = [row for row in rows if row.get(key) is not None]
            else: rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=rows)


class Bucket:
    def __init__(self, objects):
        self.objects = objects

    def download(self, key):
        if key not in self.objects:
            raise RuntimeError("not found")
        return self.objects[key]


class Client:
    def __init__(self, users, objects=(), blobs=None):
        self.users, self.objects = users, list(objects)
        self.storage = SimpleNamespace(from_=lambda _bucket: Bucket(blobs or {}))

    def table(self, name):
        return Query(self.users if name == "users" else self.objects)


class AvatarBackfillTests(unittest.TestCase):
    def user(self, user_id=9, key="avatar.png"):
        auth = "00000000-0000-0000-0000-000000000009"
        return {"id": user_id, "tenant_id": 7, "auth_id": auth, "avatar": f"https://fixture.invalid{backfill.MARKER}users/{auth}/{key}"}

    def test_inventory_is_redaction_safe_and_detects_ready_object(self):
        user = self.user()
        key = f"users/{user['auth_id']}/avatar.png"
        rows = backfill.inventory(client=Client([user], blobs={key: b"avatar-bytes"}))
        self.assertEqual(rows[0]["status"], "ready")
        self.assertEqual(rows[0]["size_bytes"], 12)
        self.assertNotIn(str(user["avatar"]), str({k: v for k, v in rows[0].items() if k != "storage_key"}))

    def test_existing_and_missing_objects_are_not_double_counted(self):
        user = self.user()
        key = f"users/{user['auth_id']}/avatar.png"
        existing = [{"tenant_id": 7, "category": "avatar", "storage_key": key, "status": "active", "user_id": 9, "size_bytes": 12}]
        self.assertEqual(backfill.inventory(client=Client([user], existing))[0]["status"], "already_accounted")
        self.assertEqual(backfill.inventory(client=Client([self.user(key="missing.png")]))[0]["status"], "avatar_object_missing")

    def test_duplicate_key_is_refused(self):
        rows = backfill.inventory(client=Client([self.user(9), self.user(10)]))
        self.assertEqual([row["status"] for row in rows], ["duplicate_avatar_key", "duplicate_avatar_key"])

    def test_apply_reserves_and_finalizes_exact_bytes(self):
        row = {"tenant_id": 7, "user_id": 9, "storage_key_sha256": "a" * 64, "storage_key": "users/auth/avatar.png", "size_bytes": 12, "sha256": "b" * 64, "status": "ready"}
        with patch.object(backfill, "reserve_storage", return_value="reservation") as reserve, patch.object(backfill, "finish_storage") as finish:
            result = backfill.apply_inventory([row], client=object(), storage_root=backfill.Path("/tmp/avatar-backfill-test"))
        self.assertEqual(result[0]["status"], "accounted")
        self.assertEqual(reserve.call_args.kwargs["size_bytes"], 12)
        self.assertEqual(finish.call_args.kwargs["storage_key"], row["storage_key"])


if __name__ == "__main__":
    unittest.main()
