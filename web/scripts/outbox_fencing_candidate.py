"""Pin the unselected coordinated schema148→149 outbox resolver cutover."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = "ae4a2eca00b3f2b3fbecba58de2f56e6ce0df3d516066afd96442a40d9a6a9c4"
BRIDGE_SHA256 = "8730d54e63a8e4fdacb163b375d01729c015afbe8da3307ed206304f4bf30e02"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-148-149-outbox-fencing.json"
    bridge = release / "schema-148-149-outbox-fencing.json"
    manifest_bytes, bridge_bytes = manifest.read_bytes(), bridge.read_bytes()
    if (hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge_bytes).hexdigest() != BRIDGE_SHA256):
        raise ValueError("Outbox fencing candidate metadata changed")
    entries = json.loads(manifest_bytes)["migrations"]
    expected = {"number":149,"from_schema":148,"to_schema":149,"compatibility":"coordinated",
                "path":"web/database/migrations/149_fence_notification_outbox_claims.sql"}
    if len(entries) != 1 or {key:entries[0].get(key) for key in expected} != expected:
        raise ValueError("Outbox fencing transition invalid")
    original = root / expected["path"]
    mirror = root / "web/supabase/migrations" / original.name
    original_bytes = original.read_bytes()
    if (original_bytes != mirror.read_bytes()
            or hashlib.sha256(original_bytes).hexdigest() != entries[0]["sha256"]):
        raise ValueError("Outbox fencing SQL mirror/checksum invalid")
    value = json.loads(bridge_bytes)
    if (value["schema"] != {"compatible_min":149,"compatible_max":149,"target":149,
            "migration_class":"coordinated","rollback_compatible_min":149,"rollback_compatible_max":149}
            or value["migration_policy"] != "none"
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "notification-outbox-fencing148-149"):
        raise ValueError("Outbox fencing coordinated compatibility invalid")
    return entries
